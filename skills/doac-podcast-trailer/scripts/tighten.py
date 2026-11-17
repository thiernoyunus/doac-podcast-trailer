"""Tighten every bite to the DOAC pace (someone talking ~98% of the time).
usage: tighten.py plan.json       (after snap.py, before audio.py; edits the plan in place)
       tighten.py --selftest      (checks the piece maths)
Writes each bite's "pieces": the source spans that play back to back as one line. Machine-written: change
start/end, parts, cut or keep instead, and re-run. It removes:
  - the bite's "cut" ranges (a stumble, a repeated word, an aside). Each edge may move up to 70 ms OUTWARD to a quieter
    point, never inward, so the words you cut stay cut. Put the edges on the cut words' outer boundaries (words.py/edge.py)
  - every silence inside the bite longer than plan "max_pause" (default 0.2 s), down to 0.1 s of air, and the silence
    at every piece edge down to 0.05 s (so two joined pieces never add up to a pause). Found from the audio's loudness,
    not from Whisper's word times (those are stretched)
  - fillers in the transcript (um, uh, erm, er, ah, "you know"), only when quiet on both sides
"parts" bites: each part's edges are snapped the way snap.py snaps start/end.
"keep": [[s, e]] protects those source seconds from the automatic removals (to veto a filler or a pause it printed).
"keep_pauses": true leaves the bite's pauses alone (the one dramatic pause before the last line).
"lock": true uses start/end/parts/cut exactly as written (no snapping); pauses and fillers are still removed.
Safe to re-run: the pieces are always recomputed from those keys. A cut edge marked <-- check is not quiet."""
import json, re, sys
import numpy as np
from common import load_plan, words, quiet, subtract, tight_key, bite_time, src_time, punches, QUIET, LOUD

AIR = 0.05   # quiet kept each side of a removed silence
FILL = {"um", "uh", "erm", "er", "ah"}


def pauses(P, rms, max_pause, step=0.01):
    """Silences to remove from pieces P, as [(start, end)]: edges trimmed to AIR, inner ones over max_pause to 2*AIR."""
    R = []
    for a, z in P:
        ts = np.arange(a, z, step)
        q = np.array([rms(t) for t in ts]) < QUIET
        i = 0
        while i < len(ts):
            if not q[i]:
                i += 1; continue
            j = i
            while j < len(ts) and q[j]: j += 1
            r0, r1 = ts[i], (ts[j - 1] + step if j < len(ts) else z)
            if i == 0 and j == len(ts): x = y = 0               # a silent piece: leave it to the editor
            elif i == 0: x, y = a, r1 - AIR
            elif j == len(ts): x, y = r0 + AIR, z
            elif r1 - r0 > max_pause: x, y = r0 + AIR, r1 - AIR
            else: x = y = 0
            if y - x >= 0.02: R.append((round(float(x), 3), round(float(y), 3)))
            i = j
    return R


def fillers(P, ws, rms):
    """Isolated fillers inside pieces P: [(start, end, text)], each between two quiet points, one sound in between."""
    toks = [(w, re.sub(r"[^\w']", "", w["w"]).lower()) for w in ws if any(a <= w["s"] < z for a, z in P)]
    R = []
    for k, (w, c) in enumerate(toks):
        grp = [w] if c in FILL else [w, toks[k + 1][0]] if c == "you" and k + 1 < len(toks) and toks[k + 1][1] == "know" else None
        if not grp: continue
        s, e = grp[0]["s"], grp[-1]["e"]
        xs, ys = np.arange(s - 0.25, s + 0.05, 0.01), np.arange(e - 0.05, e + 0.3, 0.01)
        x = float(xs[np.argmin([rms(t) for t in xs])]); y = float(ys[np.argmin([rms(t) for t in ys])])
        loud = np.array([rms(t) for t in np.arange(x, y, 0.01)]) >= QUIET
        sounds = int(np.sum(loud[1:] & ~loud[:-1]) + (loud[0] if len(loud) else 0))
        if rms(x) < QUIET and rms(y) < QUIET and 1 <= sounds <= len(grp) and y - x < 1.2:
            R.append((round(x, 3), round(y, 3), " ".join(g["w"].strip() for g in grp)))
    return R


def tighten(b, ws, rms, best, snap, max_pause):
    """(pieces, notes) for one bite."""
    notes, lock = [], b.get("lock")
    P = [list(p) for p in (b.get("parts") or [[b["start"], b["end"]]])]
    if "parts" in b and not lock:
        for p in P:
            r = snap(p[0], p[1], ws)
            if r:
                p[0], p[1] = r[0], r[1]
                if max(rms(p[0]), rms(p[1])) > LOUD: notes.append(f"part {p[0]:.2f}-{p[1]:.2f} edge in speech (rms {max(rms(p[0]), rms(p[1])):.3f}) <-- check")
    # The bite's last word always plays out: an end still in speech (a hand-placed or locked end, or Whisper ending a
    # long word early) moves on to where the sound stops, plus AIR, if that comes within 0.4 s (printed, so a next word pulled in shows).
    z = P[-1][1]
    # An end in a pause just before the sentence's last word: "a very simple ... reason." Whisper's word (ending the
    # sentence) starts before z and runs on past it, with speech between z and its end, so the word never played. Play it
    # out. Only for a word that ends a sentence: a deliberate mid-sentence end ("I concluded | that") is left alone.
    lw = [w for w in ws if w["s"] < z - 0.05]
    if lw and lw[-1]["e"] > z + 0.1 and re.search(r"[.?!]['\"]?$", lw[-1]["w"].strip()):
        nxt = [w for w in ws if w["s"] > lw[-1]["s"]]
        hi = min(lw[-1]["e"] + 0.3, nxt[0]["s"] if nxt else 1e9)
        loud = [t for t in np.arange(z, hi, 0.01) if rms(t) > LOUD]
        if loud:
            stop = next((t for t in np.arange(loud[-1], loud[-1] + 0.4, 0.01) if max(rms(t + k) for k in (0, 0.02, 0.04, 0.06)) < QUIET), loud[-1])
            P[-1][1] = round(float(stop) + AIR, 3)
            notes.append(f'end {z:.2f} -> {P[-1][1]:.2f} ("{lw[-1]["w"].strip()}" was still to come after a pause; check no next word came in)')
            z = P[-1][1]
    if rms(z - 0.015) > QUIET:
        stop = next((t for t in np.arange(z, z + 0.4, 0.01) if max(rms(t + k) for k in (0, 0.02, 0.04, 0.06)) < QUIET), None)
        if stop is None: notes.append(f"end {z:.2f} is in speech, no pause within 0.4 s <-- check")
        else: P[-1][1] = round(float(stop) + AIR, 3); notes.append(f"end {z:.2f} -> {P[-1][1]:.2f} (last word was still sounding)")
    cuts = []
    for x, y in b.get("cut", []):
        if not lock:
            # A cut only grows: each edge may move up to 70 ms outward to a quieter point, never inward, so every word
            # inside the cut stays removed (inward, a fast speaker's "quiet point" can sit past the cut word's start).
            (x1, _), (y1, _) = best(x - 0.1, x - 0.03, +1), best(y + 0.03, y + 0.1, -1)
            x, y = round(min(x, x1 + 0.03), 3), round(max(y, y1 - 0.03), 3)
            if max(rms(x), rms(y)) > LOUD: notes.append(f"cut {x:.2f}-{y:.2f} edge in speech (rms {max(rms(x), rms(y)):.3f}) <-- check")
        cuts.append((x, y)); notes.append(f"cut {x:.2f}-{y:.2f}")
    P = subtract(P, cuts)
    kept = lambda R: [r for r in R if not any(r[0] < k1 and r[1] > k0 for k0, k1 in b.get("keep", []))]
    fl = fillers(P, ws, rms)
    notes += [f'"{t}" kept (keep)' for x, y, t in fl if (x, y, t) not in kept(fl)]
    fl = kept(fl); notes += [f'"{t}" {x:.2f}-{y:.2f}' for x, y, t in fl]
    P = subtract(P, [(x, y) for x, y, _ in fl])
    if not b.get("keep_pauses"):
        pr = kept(pauses(P, rms, max_pause))
        long_ = [(x, y) for x, y in pr if y - x > 2 * AIR + 0.01 and not any(abs(x - a) < 0.001 or abs(y - z) < 0.001 for a, z in P)]
        notes += [f"pause {y - x + 2 * AIR:.2f}s @{x:.2f}" for x, y in long_]
        edge = sum(y - x for x, y in pr if (x, y) not in long_)
        if edge > 0.005: notes.append(f"{edge:.2f}s of silence at piece edges")
        P = subtract(P, pr)
    return [[round(a, 3), round(z, 3)] for a, z in P], notes


def selftest():
    def eq(a, b):
        return a is None and b is None or a is not None and b is not None and all(abs(x - y) < 1e-9 for x, y in zip(a, b))
    P = [[10.0, 12.0], [20.0, 21.0], [5.0, 6.0]]        # a stitch: three moments, out of order
    assert subtract([[0, 10]], [(2, 3), (9.98, 12)]) == [[0, 2], [3, 9.98]]
    assert subtract([[0, 10]], [(0.02, 5)]) == [[5, 10]]                 # a 20 ms sliver is dropped
    assert eq(src_time(P, 0.5), (10.5, 0)) and eq(src_time(P, 2.25), (20.25, 1)) and eq(src_time(P, 3.5), (5.5, 2))
    assert eq(bite_time(P, 20.3, 20.6), (2.3, 2.6))                       # second piece starts 2 s into the bite
    assert bite_time(P, 13.0, 13.4) is None                             # not played
    assert eq(bite_time(P, 11.9, 12.5), (1.9, 2.0))                       # clipped at the join, not into the next piece
    assert eq(bite_time(P, 5.5, 7.0), (3.5, 5.0))                         # last piece: end not clipped (as before)
    Q = [[10.0, 11.0], [11.6, 13.0]]                                    # a pause 11.0-11.6 removed
    assert eq(bite_time(Q, 11.3, 11.9), (1.0, 1.3))                       # early Whisper start: appears at the join
    assert bite_time(Q, 11.2, 11.5) is None                             # a word inside the removed stretch: gone
    assert eq(bite_time([[10.0, 12.0]], 9.96, 10.5, lo=9.9), (0, 0.5))    # old single-span behaviour
    plan = {}
    assert punches({"start": 0, "end": 1}, plan) == [1.0]
    assert punches({"parts": [[0, 1], [1.1, 2], [3, 4], [0.5, 0.8]]}, plan) == [1.0, 1.0, 1.12, 1.0]
    assert punches({"parts": [[0, 1], [3, 4]], "punch": False}, plan) == [1.0, 1.0]
    speech = [(0.0, 1.0), (1.5, 2.5), (2.62, 3.0)]                       # 0.5 s pause, then a 0.12 s gap
    rms = lambda t: 0.1 if any(a <= t < b for a, b in speech) else 0.001
    R = pauses([[-0.3, 3.4]], rms, 0.2)
    assert [(round(x, 2), round(y, 2)) for x, y in R] == [(-0.3, -0.05), (1.05, 1.45), (3.05, 3.4)], R
    # A cut over two fast words with a quiet gap between them ("I mean, | very simple."): the old snap moved both edges
    # inward into that gap and played the cut words back. Every word inside the cut must stay out of the pieces.
    import os, tempfile, wave
    SR, d = 16000, tempfile.mkdtemp()
    t = np.arange(int(2.8 * SR)) / SR
    loud = ((t >= 0.4) & (t < 1.08)) | ((t >= 1.52) & (t < 2.4))    # kept 0.4-1.0, cut "I" 1.0-1.08, gap, cut "mean" 1.52-1.6, kept
    with wave.open(os.path.join(d, "audio.wav"), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.where(loud, 0.3 * np.sin(2 * np.pi * 200 * t), 0) * 32767).astype(np.int16).tobytes())
    ws = [{"w": " so", "s": 0.4, "e": 1.0}, {"w": " I", "s": 1.0, "e": 1.08}, {"w": " mean", "s": 1.52, "e": 1.6}, {"w": " but", "s": 1.6, "e": 2.4}]
    rms, best, snap = quiet({"transcript": os.path.join(d, "t.json"), "source": ""})
    P, _ = tighten({"start": 0.4, "end": 2.4, "cut": [[1.0, 1.6]], "keep_pauses": True}, ws, rms, best, snap, 0.2)
    for w in ws:
        m = (w["s"] + w["e"]) / 2
        played = any(a < w["e"] and z > w["s"] for a, z in P)
        assert played == (not 1.0 <= m <= 1.6), (w, P)
    # A locked end placed 0.1 s before the last word stops (speech runs to 2.4): it plays out, plus a short tail.
    P, _ = tighten({"start": 0.4, "end": 2.3, "lock": True, "keep_pauses": True}, ws, rms, best, snap, 0.2)
    assert 2.43 <= P[-1][1] <= 2.5, P
    # The last word comes after a pause ("simple ... reason."), Whisper's word spanning it: an end in that pause moves on.
    ws2 = ws[:-1] + [{"w": " simple", "s": 1.6, "e": 2.0}, {"w": " reason.", "s": 2.0, "e": 2.75}]
    with wave.open(os.path.join(d, "audio.wav"), "wb") as w:   # speech 1.6-2.0, a pause, "reason" 2.5-2.75
        loud = ((t >= 0.4) & (t < 1.08)) | ((t >= 1.6) & (t < 2.0)) | ((t >= 2.5) & (t < 2.75))
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.where(loud, 0.3 * np.sin(2 * np.pi * 200 * t), 0) * 32767).astype(np.int16).tobytes())
    rms, best, snap = quiet({"transcript": os.path.join(d, "t.json"), "source": ""})
    P, _ = tighten({"start": 0.4, "end": 2.2, "lock": True, "keep_pauses": True}, ws2, rms, best, snap, 0.2)
    assert 2.77 <= P[-1][1] <= 2.85, P
    ws2[-1] = dict(ws2[-1], w=" reason")   # not a sentence end: a deliberate mid-sentence end stays where it is
    assert tighten({"start": 0.4, "end": 2.2, "lock": True, "keep_pauses": True}, ws2, rms, best, snap, 0.2)[0][-1][1] == 2.2
    print("selftest ok")


if __name__ == "__main__":
    if sys.argv[1] == "--selftest":
        selftest(); sys.exit()
    path = sys.argv[1]
    raw = json.load(open(path)); plan = load_plan(path)
    rms, best, snap = quiet(plan)
    ws = words(plan["transcript"])
    mp = plan.get("max_pause", 0.2)
    total0 = total1 = 0
    for b in (raw["bites"] if isinstance(raw, dict) else raw):
        P, notes = tighten(b, ws, rms, best, snap, mp)
        d0 = sum(z - a for a, z in (b.get("parts") or [[b["start"], b["end"]]])); d1 = sum(z - a for a, z in P)
        total0 += d0; total1 += d1
        b["pieces"], b["_tightened"] = P, tight_key(b)
        print(f"{b.get('id', '?'):>3}: {d0:5.2f}s -> {d1:5.2f}s (-{d0 - d1:.2f}s), {len(P)} piece{'s' * (len(P) > 1)}"
              + ("  (keep_pauses)" if b.get("keep_pauses") else "") + "".join(f"\n       {n}" for n in notes))
    json.dump(raw, open(path, "w"), indent=1)
    print(f"total {total0:.1f}s -> {total1:.1f}s. Veto a removal with the bite's \"keep\": [[start, end]], then re-run.")
