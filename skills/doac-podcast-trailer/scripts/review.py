"""Check a render before sharing it.  usage: review.py trailer.mp4 [plan.json]
Writes trailer_sheet.jpg: 20 frames spread over the whole trailer (last one on the ending), each labelled with its time.
Prints the running order and the captions exactly as they appear on screen (from trailer_captions.json).
With the plan, it also checks every caption block against the faces under it (trailer_faces.jpg shows any it flags),
that its letters stand out from what's around them on the rendered frame, and whether it sits on a busy background (a mic, a shelf),
prints each stitched or cut bite's "original" next to the words that play (the honesty check), and measures the pace
from the dialogue track (audio_mix.wav next to the plan, else the mp4's sound): words per second, how much of the time
someone is speaking, and the longest silences.
Check: captions never cover a face (each block's place is printed; any that fell back to the bottom is marked), every bite but the last (and a tease) starts and ends on a full sentence, length is
75-110 s with 17-30 bites, no silence over 0.35 s outside a keep_pauses bite, ends on black."""
import io, json, os, re, subprocess, sys
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont
from common import load_plan, probe, words, spans, src_time, punches, grab, QUIET, CACHE
import captions as C


def intro_check(plan, blocks):
    """Everyone who speaks twice needs an intro bite (`introduces`) that says their name, so viewers know who is who."""
    count = {}
    for b in plan["bites"]:
        count[b.get("speaker", "?")] = count.get(b.get("speaker", "?"), 0) + 1
    intros = {}
    for b in plan["bites"]:
        if b.get("introduces"):
            said = " ".join(w["w"] for bl in blocks if bl["bite"] is b for w in bl["words"])   # the captions, fixes applied
            intros.setdefault(b["introduces"], []).append(said.lower())
    print("\nintroductions (everyone who speaks twice needs their name and credential)")
    ok = True
    for who, n in sorted(count.items(), key=lambda kv: -kv[1]) + [(w, 0) for w in intros if w not in count]:
        if (n < 2 and who not in intros) or (who.lower().startswith("host") and who not in intros):
            continue
        name = plan.get("names", {}).get(who, who)
        if who not in intros:
            print(f"  {who}: {n} bites, never introduced  <-- add an intro bite with \"introduces\": \"{who}\"")
            ok = False
        elif not any(name.split()[0].lower() in t for t in intros[who]):
            print(f"  {who}: introduced, but \"{name}\" isn't said in it  <-- start the bite on \"we have {name}...\" "
                  "(or set plan \"names\" / fix a garbled name)")
            ok = False
        else:
            print(f"  {who}: ok")
    if ok:
        print("  ok")


def face_check(vid, plan, blocks, timeline):
    """Captions must never cover a face. For each caption block, compare a trailer frame (with captions) to the same
    source frame (without, cropped like the shown frame on a punch-in piece), so the difference near the block's place is
    exactly the caption; then find the faces in that frame."""
    W, H = 960, 540
    det = cv2.FaceDetectorYN.create(os.path.join(CACHE, "yunet.onnx"), "", (W, H), 0.8)   # real faces score ~0.9; hands ~0.5-0.7
    wide = plan.get("aspect", "16:9") != "9:16"
    flagged, skipped, checked, faint, unscored = [], 0, 0, [], []
    for bl in blocks:
        for k, t in enumerate((bl["s"] + (bl["e"] - bl["s"]) * 0.6, bl["e"] - 0.2)):   # most words on screen, before the exit
            t0, b = [(a, b) for a, b in timeline if a <= t][-1]
            if not wide or b.get("zoom") or t < bl["s"]:
                skipped += not wide or bool(b.get("zoom")); continue
            st, j = src_time(spans(b), t - t0)
            fr, src = grab(vid, t, W, H), grab(plan["source"], st, W, H)
            if fr is None or src is None: continue
            z = punches(b, plan)[j]
            if z != 1:   # a punch-in piece: compare with the same centred crop
                h, w = int(round(H / z)), int(round(W / z))
                src = cv2.resize(src[(H - h) // 2:(H - h) // 2 + h, (W - w) // 2:(W - w) // 2 + w], (W, H), interpolation=cv2.INTER_CUBIC)
            checked += 1
            diff = cv2.dilate((np.abs(fr.astype(int) - src.astype(int)).max(2) > 60).astype(np.uint8), np.ones((5, 5), np.uint8))
            cap = np.zeros_like(diff)   # captions only live where the block was placed; ignore motion elsewhere
            x, y, w, h = (int(v / 2) for v in bl["box"])
            cap[max(0, y - 15):y + h + 15, max(0, x - 15):x + w + 15] = diff[max(0, y - 15):y + h + 15, max(0, x - 15):x + w + 15]
            if k == 0:
                c = legibility(fr, src, cap, C.HOST_RGB if bl["host"] else (255, 255, 255))
                if c is None: unscored.append((t, bl))
                elif c < C.READABLE: faint.append((t, bl, c))
            _, faces = det.detect(src)
            for f in faces if faces is not None else []:
                x, y, w, h = (int(v) for v in f[:4])
                x0, y0 = max(0, x), max(0, y)
                cover = cap[y0:y + h, x0:x + w].mean() if w > 0 and h > 0 else 0
                if cover > 0.02:
                    im = fr.copy(); cv2.rectangle(im, (x, y), (x + w, y + h), (0, 0, 255), 3)
                    flagged.append((t, bl, cover, im)); break
            else:
                continue
            break
    print("\ncaption contrast (the letters against what's right around them, shadow or halo included)")
    for t, bl, c in faint:
        print(f"  {t:5.1f}s  contrast {c:.1f} (under {C.READABLE:g}): \"{' '.join(w['w'] for w in bl['words'])}\"  <-- hard to read: a `cap_pos`"
              " on a darker side, or raise captions.SHADOW_LOW")
    for t, bl in unscored:
        print(f"  {t:5.1f}s  not checked (its letters couldn't be told from the background): \"{' '.join(w['w'] for w in bl['words'])}\"  <-- look at it yourself")
    if not faint and not unscored: print("  ok: every block checked is readable")
    if skipped:
        sk = [bl for bl in blocks if not wide or bl["bite"].get("zoom")]
        print(f"  skipped on the rendered frames: {len(sk)} block{'s' * (len(sk) != 1)} (9:16 / zoom). captions.py measured the background"
              f" under them before rendering and gave {sum(bl['low'] for bl in sk)} the dark halo; look at the rest yourself")
    busy = [bl for bl in blocks if bl.get("busy", 0) > C.BUSY]
    print(f"\ncaptions over busy backgrounds (a mic, a shelf, a plant: over {C.BUSY:.0%} strong edges under the block)")
    for bl in busy:
        print(f"  {bl['s']:5.1f}s  {bl['busy']:.0%} {bl['place']}: \"{' '.join(w['w'] for w in bl['words'])}\"  <-- look at it: is it covering"
              " something the viewer needs to see, or hard to read? `cap_pos` moves it")
    if not busy: print("  ok")
    print(f"\nfaces vs captions: {checked} frames checked" + (f", {skipped} skipped (9:16 / zoom: check those by eye)" if skipped else ""))
    if not flagged:
        print("  ok: no caption covers a face")
        return
    for t, bl, cover, _ in flagged:
        print(f"  {t:5.1f}s  covers {cover:.0%} of a face ({bl['place']}): \"{' '.join(w['w'] for w in bl['words'])}\"  <-- fix")
    sheet = np.vstack([im for *_, im in flagged[:6]])
    out = vid.rsplit(".", 1)[0] + "_faces.jpg"
    cv2.imwrite(out, sheet)
    print(f"  see {out}. Fix: fewer words per block (lower `gap`, `drop` filler), a `cap_pos` that has room, or a different bite")


def legibility(fr, src, cap, rgb):
    """Contrast ratio (WCAG) of the caption's letters against the pixels just around them (1-3 px out at 960 wide, where
    the shadow or halo is), measured on the rendered frame: fr = with captions, src = the same frame without, cap = where
    the caption changed the picture. Letters = changed pixels close to the line colour rgb. None if too few letters show."""
    colour = (cap > 0) & (np.abs(fr.astype(int) - np.array(rgb[::-1])).max(2) < 50)
    glyph = colour & (np.abs(fr.astype(int) - src.astype(int)).max(2) > 60)
    if glyph.sum() < 150 or glyph.sum() < 0.8 * colour.sum(): return None   # letters lost in a same-colour background: unchecked
    g8 = glyph.astype(np.uint8)
    ring = (cv2.dilate(g8, np.ones((7, 7), np.uint8)) > 0) & ~(cv2.dilate(g8, np.ones((3, 3), np.uint8)) > 0)
    grey = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
    return (C.lum(rgb) + 0.05) / (float(np.median(C.lum(grey[ring]))) + 0.05)


def honesty_check(plan, blocks):
    """A stitch may shorten a line, never change its meaning: show what was said next to what plays."""
    edited = [b for b in plan["bites"] if b.get("parts") or b.get("cut")]
    if not edited: return
    print("\nstitched / cut bites: does what plays keep the meaning of what was said?")
    for b in edited:
        plays = " ".join(w["w"] for bl in blocks if bl["bite"] is b for w in bl["words"])
        print(f"  {b['id']:>3} said:  {b.get('original') or '(no original)  <-- add \"original\": the sentence(s) exactly as said'}")
        print(f"      plays: {plays}")


def pace(timeline, total, blocks):
    """Pace from the dialogue: words per second, % of time someone speaks (a silence = 0.1 s+ under the quiet level)."""
    base = os.path.dirname(os.path.abspath(sys.argv[2]))
    src = os.path.join(base, "audio_mix.wav") if os.path.exists(os.path.join(base, "audio_mix.wav")) else vid
    r = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", src, "-ac", "1", "-ar", "16000", "-f", "f32le", "-"], capture_output=True)
    x = np.frombuffer(r.stdout, np.float32)[: int(total * 16000)]
    if r.returncode or len(x) < 0.9 * total * 16000:
        print(f"\npace: couldn't read the sound from {os.path.basename(src)} ({len(x) / 16000:.1f}s of {total:.1f}s)  <-- pace not checked")
        return
    env = np.sqrt(np.mean(x[: len(x) // 160 * 160].reshape(-1, 160) ** 2, axis=1))   # 10 ms steps
    quiet, runs, i = env < QUIET, [], 0
    while i < len(quiet):
        j = i
        while j < len(quiet) and quiet[j]: j += 1
        if j - i >= 10: runs.append((i / 100, (j - i) / 100))
        i = max(j, i + 1)
    nw = sum(len(bl["words"]) for bl in blocks)
    print(f"\npace (from {os.path.basename(src)}): {total:.1f}s of dialogue, {nw / total:.1f} words/s (DOAC 3.2-4.1), "
          f"someone speaking {1 - sum(d for _, d in runs) / total:.0%} of the time (DOAC ~98%)")
    def bite_at(t): return [b for t0, b in timeline if t0 <= t][-1]
    for s, d in sorted(runs, key=lambda r: -r[1])[:5]:
        b = bite_at(s); ok = b.get("keep_pauses") or bite_at(s + d).get("keep_pauses")
        print(f"  silence {d:.2f}s at {s:5.1f}s (bite {b['id']})" + ("" if d <= 0.35 or ok else "  <-- over 0.35 s: tighten, or keep_pauses if deliberate"))
    flagged = sum(1 for s, d in runs if d > 0.35 and not (bite_at(s).get("keep_pauses") or bite_at(s + d).get("keep_pauses")))
    print(f"  {flagged} silence{'s' * (flagged != 1)} over 0.35 s outside keep_pauses bites" if flagged else "  ok: no silence over 0.35 s outside keep_pauses bites")


vid = sys.argv[1]
_, _, _, dur = probe(vid)
ts = [dur * (i + 0.5) / 20 for i in range(19)] + [dur - 0.3]
tiles = []
for t in ts:
    b = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", vid, "-frames:v", "1", "-vf", "scale=480:-2",
                        "-f", "image2pipe", "-vcodec", "mjpeg", "-"], capture_output=True).stdout
    im = Image.open(io.BytesIO(b)).convert("RGB"); d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 92, 26], fill=(0, 0, 0)); d.text((6, 3), f"{t:5.1f}s", fill=(255, 220, 0), font=ImageFont.load_default(20))
    tiles.append(im)
w, h = tiles[0].size
sheet = Image.new("RGB", (w * 4, h * 5))
for i, im in enumerate(tiles):
    sheet.paste(im, ((i % 4) * w, (i // 4) * h))
out = vid.rsplit(".", 1)[0] + "_sheet.jpg"
sheet.save(out, quality=85)
print(f"length {dur:.1f}s   sheet: {out}")
if not 75 <= dur <= 110: print(f"  <-- length {dur:.0f}s: aim for 75-110 s")
if len(sys.argv) > 2:
    plan = load_plan(sys.argv[2])
    timeline, t = C.place_bites(plan["bites"])
    blocks = C.build_blocks(timeline, words(plan["transcript"]))
    C.place(blocks, plan)
    n = len(plan["bites"])
    print(f"\nrunning order ({n} bites" + (": aim for 17-30)" if not 17 <= n <= 30 else ")"))
    for k, (t0, b) in enumerate(timeline):
        a, P = spans(b)[0][0], spans(b)
        said = " ".join(w["w"] for bl in blocks if bl["bite"] is b for w in bl["words"])
        mid = "" if k == n - 1 or "tease" in str(b.get("role", "")) or re.search(r"[.?!]['\"]?$", said) else "  <-- ends mid-sentence?"
        print(f"{t0:5.1f}s {b['id']:>3} {b.get('role', ''):<12} {b.get('speaker', '')[:18]:<18} {b['dur']:4.1f}s  src {int(a // 60)}:{a % 60:04.1f}"
              + (f" ({len(P)} pieces)" if len(P) > 1 else "") + mid)
    share = {}
    for b in plan["bites"]:
        share[b.get("speaker", "?")] = share.get(b.get("speaker", "?"), 0) + b["dur"]
    print("\nspeaking time by speaker (in a guest episode the guest should be 50% or more)")
    for k, v in sorted(share.items(), key=lambda kv: -kv[1]):
        print(f"  {v / t:4.0%}  {v:5.1f}s  {k}")
    g = plan.get("guest")
    if g:
        gs = share.get(g, 0) / t
        print(f"  guest '{g}': {gs:.0%}" + ("  <-- under 50%: give the guest more of the trailer" if gs < 0.5 else "  ok"))
    intro_check(plan, blocks)
    honesty_check(plan, blocks)
    pace(timeline, t, blocks)
    face_check(vid, plan, blocks, timeline)
cap = vid.rsplit(".", 1)[0] + "_captions.json"   # render.py writes this; with a plan, rebuild from it (same code)
shown = json.load(open(cap)) if os.path.exists(cap) and len(sys.argv) < 3 else []
if len(sys.argv) > 2:
    shown = [dict(s=bl["s"], words=[C.display_text(w, r) for w, r in zip(bl["words"], bl["roles"])], roles=bl["roles"],
                  place=bl["place"], host=bl["host"]) for bl in blocks]
if shown:
    print("\ncaptions on screen and where ([WORD] = hero word; left/right = beside the head, between = between two people,"
          " sub = no face, a small subtitle; host lines are yellow)")
    fell = 0
    for c in shown:
        ws = c.get("words") or c["text"].split()   # a fix may hold several words ("It became"): keep them one caption word
        rs = c.get("roles", ["lead"] * len(ws))
        low = c.get("place", "").startswith("bottom") and not (len(sys.argv) > 2 and plan["aspect"] == "9:16")
        fell += low
        print(f"{c['s']:5.1f}s  {c.get('place', ''):<8}{'host ' if c.get('host') else ''}" + " ".join(f"[{w}]" if r in C.HERO else w for w, r in zip(ws, rs))
              + (("  <-- nothing fit, even at the bottom: shown as a small subtitle" if c["place"] == "bottom!"
                  else "  <-- no room beside or between the faces: fell back to the bottom") if low else ""))
    if fell:
        print(f"  {fell} block{'s' * (fell != 1)} at the bottom. Fine now and then; for more, use fewer words per block (`gap`, `drop`) or `cap_pos`")
