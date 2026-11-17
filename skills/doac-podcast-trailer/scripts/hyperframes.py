"""Turn the plan into a HyperFrames project you can preview, tweak and render.
usage: hyperframes.py plan.json outdir/        (run audio.py and sfx.py first; they write audio_mix.wav and sfx.json next to the plan)

  cd outdir && npx hyperframes preview      live Studio: scrub, retime clips, edit caption text and style
  cd outdir && npx hyperframes render -o trailer.mp4

What it writes:
  index.html              the edit: one muted <video> per bite, the soundtrack, and the captions layer
  compositions/captions.html   every caption as HTML text (a block per phrase with data-start/data-duration,
                          a span per word with data-at), plus the caption style block
  assets/clips/NN-*.mp4   each bite pre-cut from the source (frame-accurate, 30 fps, muted); NN-*-2.mp4... for a
                          bite's further pieces (tighten.py), a punch-in piece scaled up by CSS on its .shot
  assets/audio_mix.wav    the dialogue track from audio.py (-14 LUFS, plus music if the plan has a track)
  assets/sfx/             each sound effect from sfx.py (HyperFrames' sound library), one clip per boom / riser / whoosh
  assets/fonts/           Montserrat, Playfair Display (from ~/.cache/doac-trailer/fonts)
  assets/vendor/          GSAP (the animation library HyperFrames drives), so nothing loads from the network

The caption look (fonts, colours, sizes, shadow, animation timing) lives in one block at the top of
compositions/captions.html: <style id="caption-style">. Caption grouping, roles, colours and each block's place in the frame
(from the faces in shot) come from captions.py, the same code render.py uses, so both paths show the same words in the same
places. 16:9 bites are the untouched full frame; 9:16 and
per-bite "zoom" framing are baked into the clip with render.py's crop maths.
"""
import html, json, math, os, re, shutil, subprocess, sys
from common import load_plan, words, probe, spans, punches, FONTS
import captions as C



def frames(t):
    return int(round(t * C.FPS))


def secs(n_frames):
    """Frame n's time, rounded down to 0.1 ms: a clip must already be on screen at exactly n/30 s."""
    return f"{math.floor(n_frames / C.FPS * 1e4) / 1e4:.4f}"


def num(x):
    return f"{x:.3f}"


# ---------- clips ----------
def cut_plain(src, start, n, sw, sh, out):
    """Full frame, no crop: the same ffmpeg decode render.py uses (input seek, scale, 30 fps), encoded."""
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{start:.3f}", "-i", src, "-t", f"{n / C.FPS + 0.5:.3f}",
                    "-vf", f"scale={sw}:{sh}", "-r", str(C.FPS), "-frames:v", str(n), "-an",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "16", "-g", "15", "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart", out], check=True)


def cut_reframed(src, b, start, t0, n, sw, sh, W, H, out):
    """9:16 speaker crop or a zoom: render.py's per-frame crop maths, baked into the clip (a piece t0 s into the bite)."""
    import numpy as np, cv2
    dec = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-ss", f"{start:.3f}", "-i", src, "-t", f"{n / C.FPS + 0.5:.3f}",
                            "-vf", f"scale={sw}:{sh}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-r", str(C.FPS), "-"], stdout=subprocess.PIPE)
    enc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}",
                            "-r", str(C.FPS), "-i", "-", "-c:v", "libx264", "-preset", "fast", "-crf", "16", "-g", "15",
                            "-pix_fmt", "yuv420p", "-movflags", "+faststart", out], stdin=subprocess.PIPE)
    shots = b.get("shots") or [[0, b.get("cx", 0.5)]]
    cy = b.get("cy", 0.5)
    z0, z1 = b.get("zoom", (1.0, 1.0))
    last = None
    for k in range(n):
        raw = dec.stdout.read(sw * sh * 3)
        img = np.frombuffer(raw, np.uint8).reshape(sh, sw, 3) if len(raw) == sw * sh * 3 else last
        last = img
        lt = t0 + k / C.FPS
        if "track" in b:
            tr = b["track"]; cx = float(np.interp(lt, [p[0] for p in tr], [p[1] for p in tr]))
        else:
            cx = [s[1] for s in shots if s[0] <= lt][-1]
        zp = lt / b["dur"]; zp = zp * zp * (3 - 2 * zp)
        z = z0 + (z1 - z0) * zp
        ch = sh / z; cw = ch * W / H
        x0 = min(max(cx * sw - cw / 2, 0), sw - cw)
        y0 = min(max(cy * sh - ch / 2, 0), sh - ch)
        s = W / cw
        M = np.float32([[s, 0, -x0 * s], [0, s, -y0 * s]])
        enc.stdin.write(cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE).tobytes())
    dec.kill(); enc.stdin.close(); enc.wait()


# ---------- captions ----------
def block_html(i, bl, prev_end):
    """One caption block: a timed group placed where captions.place put it, its lines, and one span per word
    (data-at = when the word appears). Line breaks and word sizes are the ones render.py draws."""
    x, y, w, h = bl["box"]
    start = max(bl["s"] - 0.01, prev_end)       # render.py shows a block from 10 ms before its first word
    cls = f'caption-group at-{bl["place"].rstrip("!")} align-{bl["align"]}' + (" host" if bl["host"] else "") + (" low" if bl["low"] else "")
    out = [f'    <div id="cap-{i:03d}" class="clip {cls}" data-start="{num(start)}" data-duration="{num(bl["e"] - start)}" data-track-index="0"'
           f' style="left: {x:.0f}px; top: {y:.0f}px; width: {w:.0f}px; --fit: {bl["fit"]:.4f}; --small: {min(1, bl["fit"] / 0.8):.4f}"><div class="caption-block">']
    for ln in bl["lines"]:
        spans = []
        for it in ln:
            c = ["caption-word", it["r"]] + ([f"c-{it['c']}"] if it["c"] else [])
            text = it["w"]["w"].strip('.,;:!"') if it["r"] == "big" else it["t"]   # CSS upper-cases big words, so the text stays easy to edit
            at = bl["s"] if it["r"] == "sub" else it["w"]["s"]                  # a subtitle shows whole
            spans.append(f'<span class="{" ".join(c)}" data-at="{num(at)}">{html.escape(text)}</span>')
        out.append(f'      <div class="caption-line {ln[0]["r"]}">{" ".join(spans)}</div>')
    out[-1] += "</div></div>"
    return "\n".join(out)


# ---------- files ----------
CAPTIONS = """<!-- Captions for the DOAC trailer (made by hyperframes.py; regenerating overwrites this file).
     Each .caption-group is one caption block: data-start / data-duration in seconds on the trailer timeline, and its place
     (left/top/width in px) chosen by captions.py from the faces in shot: at-left / at-right (beside the head, text leaning
     toward the face), at-between (between two people), at-bottom, at-sub (no face: a small subtitle). host = a host line;
     low = a light background under it (captions.py measures it), so its words get the dark halo (--cap-shadow-low).
     Each .caption-word appears at its data-at time. Word roles: lead (small), big (the hero word, caps), serif (a soft hero
     word, italic serif), tail (medium), sub (subtitle). Colour: c-red, c-yellow, c-green, c-pink, c-gold, c-box (white on a
     red box); no class = the line's colour. Edit the words freely; restyle everything in the CAPTION STYLE block below. -->
<template>
  <!-- ======================= CAPTION STYLE: fonts, colours, sizes, motion ======================= -->
  <style id="caption-style">
    @font-face { font-family: "Montserrat"; src: url("assets/fonts/Montserrat.ttf") format("truetype"); font-weight: 100 900; }
    @font-face { font-family: "Playfair Display"; src: url("assets/fonts/PlayfairDisplay-Italic.ttf") format("truetype"); font-style: italic; font-weight: 400 900; }
    #captions-root {
      /* colour */
      --cap-color: #ffffff;              /* the guest, and everyone but the host */
      --cap-host: rgb(%(host)s);    /* every word the host says */
      %(colors)s   /* accent colours, one class per colour (c-red...) */
      --cap-box: rgb(%(box)s);   /* c-box: a white word on this box */
      --cap-shadow: %(shadow)s;   /* soft drop shadow; no outline, no box */
      --cap-shadow-low: %(shadow_low)s;   /* .low: a dark halo, for a block on a light background */
      /* motion (seconds / px), read by the script at the bottom */
      --cap-enter: %(enter)s;         /* each word blurs in, sharpens and settles over this long... */
      --cap-enter-hero: %(enter_hero)s;    /* ...hero words over this long */
      --cap-enter-scale: %(escale)s;  /* ...from this scale to 1 */
      --cap-enter-blur: %(eblur)s;     /* ...from this blur */
      --cap-exit: %(exit)s;           /* the block fades and blurs out over its last this-many seconds */
      --cap-exit-blur: %(xblur)s;
      position: absolute; inset: 0; width: %(W)dpx; height: %(H)dpx; pointer-events: none;
    }
    .caption-group { position: absolute; }   /* left / top / width per block: its place in the frame */
    .caption-group.host { --cap-color: var(--cap-host); }
    .caption-block { display: flex; flex-direction: column; }
    .align-left .caption-block { align-items: flex-start; }    /* right of a face: lines lean left, toward it */
    .align-right .caption-block { align-items: flex-end; }     /* left of a face */
    .align-center .caption-block { align-items: center; }
    .caption-line { display: flex; align-items: baseline; white-space: nowrap; }
    .caption-word { display: inline-block; color: var(--cap-color); text-shadow: var(--cap-shadow); transform-origin: 50%% 50%%; }
    /* type: size in px at %(W)dx%(H)d (a hero word is scaled by its block's --fit so it fills its place, the other words by
       --small when the hero had to shrink a lot); line = the font's
       own height (x font size); after = space under each line; gap = space between words */
%(role_rules)s
    .caption-word.big { text-transform: uppercase; }
%(color_rules)s
    .caption-group.low .caption-word:not(.c-box) { text-shadow: var(--cap-shadow-low); }
    .caption-word.c-box { color: #ffffff; text-shadow: none; padding: 0 %(box_pad)sem;
                          background: linear-gradient(var(--cap-box), var(--cap-box)) 0 var(--box-top) / 100%% var(--box-h) no-repeat; }
  </style>
  <!-- ======================= end of caption style ======================= -->

  <div id="captions-root" data-composition-id="captions" data-width="%(W)d" data-height="%(H)d">
%(caps)s
  </div>

  <script>
    (() => {
      window.__timelines = window.__timelines || {};
      const tl = gsap.timeline({ paused: true });
      const root = document.getElementById("captions-root");
      const css = getComputedStyle(root);
      const v = (name) => parseFloat(css.getPropertyValue(name));
      const ENTER = v("--cap-enter"), HERO = v("--cap-enter-hero"), SCALE = v("--cap-enter-scale"), BLUR = v("--cap-enter-blur");
      const EXIT = v("--cap-exit"), EXIT_BLUR = v("--cap-exit-blur");
      root.querySelectorAll(".caption-group").forEach((group) => {
        const start = parseFloat(group.dataset.start), end = start + parseFloat(group.dataset.duration);
        const block = group.querySelector(".caption-block");
        group.querySelectorAll(".caption-word").forEach((word) => {
          const d = word.classList.contains("big") || word.classList.contains("serif") ? HERO : ENTER;
          tl.fromTo(word, { opacity: 0, scale: SCALE, filter: `blur(${BLUR}px)` },
                          { opacity: 1, scale: 1, filter: "blur(0px)", duration: d, ease: "power2.out" }, parseFloat(word.dataset.at));
        });
        if (end - start > 0.31) {   // blocks shorter than 0.3 s just cut
          tl.fromTo(block, { opacity: 1 }, { opacity: 0, duration: EXIT, ease: "power1.in", immediateRender: false }, end - EXIT);
          tl.fromTo(block, { filter: "blur(0px)" }, { filter: `blur(${EXIT_BLUR}px)`, duration: EXIT, ease: "none", immediateRender: false }, end - EXIT);
        }
        tl.set(block, { opacity: 0, visibility: "hidden" }, end);   // hard stop at the block's end
      });
      tl.set({}, {}, %(total)s);
      window.__timelines["captions"] = tl;
    })();
  </script>
</template>
"""

INDEX = """<!doctype html>
<!-- DOAC trailer from %(plan)s, made by hyperframes.py (regenerating overwrites this project's html).
     Preview / tweak:  npx hyperframes preview        Render:  npx hyperframes render -o trailer.mp4
     Bites are muted clips cut from the episode. The dialogue is one track; every sound effect is its own clip below it.
     Captions and their style: compositions/captions.html -->
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=%(W)d, height=%(H)d" />
    <script src="%(gsap)s"></script>
    <style>
      * { margin: 0; padding: 0; box-sizing: border-box; }
      html, body { width: %(W)dpx; height: %(H)dpx; overflow: hidden; background: #000; }
      #root { position: relative; width: %(W)dpx; height: %(H)dpx; overflow: hidden; background: #000; }
      #studio, .shot { position: absolute; inset: 0; }
      .bite { position: absolute; inset: 0; width: 100%%; height: 100%%; object-fit: cover; }
      #captions { position: absolute; inset: 0; z-index: 10; }
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="%(total)s" data-width="%(W)d" data-height="%(H)d">
      <!-- ============ BITES, in trailer order: one clip each (start/duration in seconds on the trailer) ============ -->
      <div id="studio">
%(bites)s
      </div>

      <!-- ============ DIALOGUE: the bites' sound at -14 LUFS, from audio.py ============ -->
      <audio id="soundtrack" src="assets/audio_mix.wav" data-start="0" data-duration="%(total)s" data-track-index="2" data-volume="1"></audio>

      <!-- ============ SOUND EFFECTS: one clip each, from HyperFrames' sound library (sfx.py). Move, re-level or delete freely ============ -->
%(sfx)s

      <!-- ============ CAPTIONS: text, timing and style live in compositions/captions.html ============ -->
      <div id="captions" data-composition-id="captions" data-composition-src="compositions/captions.html" data-track-kind="captions"
           data-start="0" data-duration="%(total)s" data-track-index="1" data-width="%(W)d" data-height="%(H)d"></div>
      <!-- the last %(hold)s s are black -->
    </div>
    <script>
      window.__timelines = window.__timelines || {};
      const tl = gsap.timeline({ paused: true });
      // focus pull: a bite with data-focus-pull="0.5" starts soft and sharpens over that many seconds
      document.querySelectorAll(".shot[data-focus-pull]").forEach((shot) => {
        const t0 = parseFloat(shot.querySelector("video").dataset.start), d = parseFloat(shot.dataset.focusPull);
        tl.fromTo(shot, { filter: "blur(9px)" }, { filter: "blur(0px)", duration: d, ease: "power1.out", immediateRender: false }, t0);
      });
      tl.set({}, {}, %(total)s);
      window.__timelines["main"] = tl;
    </script>
  </body>
</html>
"""


GSAP_URL = "https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"


def vendor_gsap(outdir):
    """A local copy of GSAP, so preview and render work offline (and behind proxies Chrome doesn't trust).
    Falls back to the CDN link HyperFrames' own templates use."""
    rel = "assets/vendor/gsap.min.js"
    path = os.path.join(outdir, rel)
    if not os.path.exists(path):
        try:
            import urllib.request
            data = urllib.request.urlopen(GSAP_URL, timeout=30).read()
            os.makedirs(os.path.dirname(path), exist_ok=True)
            open(path, "wb").write(data)
        except Exception as e:
            print(f"(could not download GSAP, using the CDN link: {e})")
            return GSAP_URL
    return rel


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    plan_path, outdir = sys.argv[1], sys.argv[2]
    plan = load_plan(plan_path)
    wide = plan["aspect"] == "16:9"
    W, H = (1920, 1080) if wide else (1080, 1920)
    base_px = C.base(wide)
    fonts = sorted({f for f, _ in C.FONT.values()})
    audio = plan.get("audio", os.path.join(os.path.dirname(os.path.abspath(plan_path)), "audio_mix.wav"))
    if not os.path.exists(audio):
        sys.exit(f"no soundtrack at {audio}: run audio.py {plan_path} first")
    for f in fonts:
        if not os.path.exists(f"{FONTS}/{f}"):
            sys.exit(f"missing font {FONTS}/{f}: run setup.sh")
    src = plan["source"]
    sw0, sh0, _, _ = probe(src)
    sh = min(sh0, 1080); sw = int(round(sw0 * sh / sh0 / 2)) * 2   # render.py's decode size
    hold = plan.get("end_hold", 1.2)

    for d in ("assets/clips", "assets/fonts", "compositions"):
        os.makedirs(os.path.join(outdir, d), exist_ok=True)
    shutil.copy(audio, os.path.join(outdir, "assets/audio_mix.wav"))
    for f in fonts:
        shutil.copy(f"{FONTS}/{f}", os.path.join(outdir, "assets/fonts", f))

    sfx_html = []
    sfx_path = os.path.join(os.path.dirname(os.path.abspath(plan_path)), "sfx.json")
    fx = json.load(open(sfx_path))["sounds"] if os.path.exists(sfx_path) else []
    if any(b.get(k) for b in plan["bites"] for k in ("boom", "riser", "whoosh")) and not os.path.exists(sfx_path):
        sys.exit(f"the plan has sound effects but no sfx.json: run sfx.py {plan_path} first")
    if fx:
        os.makedirs(os.path.join(outdir, "assets/sfx"), exist_ok=True)
    old = os.path.join(outdir, "assets/sfx")
    for f in (os.listdir(old) if os.path.isdir(old) else []):   # sounds no longer in the plan
        if f not in {os.path.basename(s["file"]) for s in fx}:
            os.remove(os.path.join(old, f))
    tracks = {"boom": 3, "riser": 4, "whoosh": 5}   # one track per kind, so effects never overlap on a track
    for s in fx:
        name = os.path.basename(s["file"])
        shutil.copy(s["file"], os.path.join(outdir, "assets/sfx", name))
        sfx_html.append(f'      <audio id="sfx-{name[:-4]}" class="sfx" src="assets/sfx/{name}" data-start="{s["start"]:.4f}" data-duration="{s["dur"]:.4f}"'
                        f' data-media-start="0" data-track-index="{tracks[s["kind"]]}" data-volume="1"></audio>  <!-- {s["kind"]} on bite {html.escape(str(s["bite"]))} -->')

    timeline, total = C.place_bites(plan["bites"])
    blocks = C.build_blocks(timeline, words(plan["transcript"]))
    C.place(blocks, plan)   # each block's place from the faces in shot, its lines and word sizes (same as render.py)

    # bites: frame-exact, as in render.py (bite k covers frames round(out0*30) up to round(out1*30))
    cache_path = os.path.join(outdir, "assets/clips/.cuts.json")   # skip re-cutting unchanged bites
    cache = json.load(open(cache_path)) if os.path.exists(cache_path) else {}
    keep, bite_html = {}, []
    for k, (out0, b) in enumerate(timeline, 1):
        P, zs, t0 = spans(b), punches(b, plan), 0.0
        slug = re.sub(r"[^a-z0-9]+", "-", str(b.get("role", "")).lower()).strip("-")[:24] or "bite"
        label = " / ".join(str(x) for x in (b["id"], b.get("role"), b.get("speaker")) if x)
        for j, ((a, z), zoom) in enumerate(zip(P, zs)):   # one clip per piece, back to back
            f0, f1 = frames(out0 + t0), frames(out0 + t0 + z - a)
            sub = f"-{j + 1}" if len(P) > 1 else ""
            name, vid = f"{k:02d}-{slug}{sub}.mp4", f"bite-{k:02d}{sub}"
            path = os.path.join(outdir, "assets/clips", name)
            key = json.dumps([src, a, f1 - f0, wide, b.get("zoom"), b.get("track"), b.get("shots"), b.get("cx"), b.get("cy"), t0])
            if not (os.path.exists(path) and cache.get(name) == key):
                print(f"cut {name}  src {a:.2f}-{z:.2f}  {f1 - f0} frames", flush=True)
                if wide and list(b.get("zoom", (1.0, 1.0))) == [1.0, 1.0]:
                    cut_plain(src, a, f1 - f0, sw, sh, path)
                else:
                    cut_reframed(src, b, a, t0, f1 - f0, sw, sh, W, H, path)
            keep[name] = key
            fp = b.get("focus_pull", 0) if j == 0 else 0
            pull = f' data-focus-pull="{fp}"' if fp else ""
            punch = f' style="transform: scale({zoom:g})"' if zoom != 1 else ""   # punch-in: a centred tighter crop
            comment = html.escape(f"{label}: source {a:.2f}-{z:.2f}".replace("--", "-") + (f", punch-in {zoom:g}x" if punch else ""))
            bite_html.append(
                f'      <!-- {comment} -->\n'
                f'      <div class="shot"{pull}{punch}><video id="{vid}" class="bite" src="assets/clips/{name}" data-start="{secs(f0)}"'
                f' data-duration="{float(secs(f1)) - float(secs(f0)):.4f}" data-media-start="0" data-track-index="0" muted playsinline></video></div>')
            t0 += z - a
    for f in os.listdir(os.path.join(outdir, "assets/clips")):   # clips of bites no longer in the plan
        if f.endswith(".mp4") and f not in keep:
            os.remove(os.path.join(outdir, "assets/clips", f))
    json.dump(keep, open(cache_path, "w"), indent=1)

    nfr = frames(total) + int(hold * C.FPS)
    colors = {**C.COLORS, **{k: v for k, v in plan.get("colors", {}).items() if k != "box"}}

    def role_rule(role):
        """render.py stacks lines (ascent + descent) * LINE apart with the text at the top of each line: in CSS that is
        line-height = (ascent + descent) and a (LINE - 1) share of it as space after."""
        px = base_px * C.SIZE[role]
        font = C.font(role, int(px)); a = sum(font.getmetrics()) / int(px)
        k = C.LINE_BIG if role in C.HERO else C.LINE_OTHER
        size = f"calc({px:g}px * var(--{'fit' if role in C.HERO else 'small'}, 1))"
        family = "\"Playfair Display\", serif; font-style: italic" if role == "serif" else "\"Montserrat\", sans-serif"
        t, h = C.box_rows(font, role)
        return (f"    .caption-word.{role} {{ font-family: {family}; font-weight: {C.WEIGHT[C.FONT[role][1]]}; font-size: {size};"
                f" line-height: {a:.4f}; margin-bottom: {a * (k - 1):.4f}em; --box-top: {t / int(px):.4f}em; --box-h: {h / int(px):.4f}em; }}\n"
                f"    .caption-line.{role} {{ column-gap: {C.GAP_EM}em; font-size: {size}; }}")
    captions = CAPTIONS % dict(
        W=W, H=H, host=", ".join(map(str, C.HOST_RGB)),
        colors="  ".join(f"--cap-{k}: rgb({', '.join(map(str, v))});" for k, v in colors.items()),
        color_rules="\n".join(f"    .caption-word.c-{k} {{ color: var(--cap-{k}); }}" for k in colors),
        box=", ".join(map(str, plan.get("colors", {}).get("box", C.BOX_RGB))), box_pad=f"{C.BOX_PAD:g}",
        role_rules="\n".join(role_rule(r) for r in C.FONT),
        shadow=", ".join(f"0 {dy}px {r}px rgba(0, 0, 0, {a})" for r, a, dy in C.SHADOW),
        shadow_low=", ".join(f"0 {dy}px {r}px rgba(0, 0, 0, {a})" for r, a, dy in C.SHADOW_LOW),
        enter=C.ENTER_S, enter_hero=C.HERO_ENTER_S, escale=C.ENTER_SCALE,
        eblur=f"{C.ENTER_BLUR / 2:g}", exit=C.EXIT_S, xblur=f"{C.EXIT_BLUR / 2:g}",   # render.py blur sigma = px / 2
        caps="\n".join(block_html(i, bl, blocks[i - 2]["e"] if i > 1 else 0) for i, bl in enumerate(blocks, 1)),
        total=secs(nfr))
    open(os.path.join(outdir, "compositions/captions.html"), "w").write(captions)
    open(os.path.join(outdir, "index.html"), "w").write(INDEX % dict(
        gsap=vendor_gsap(outdir), plan=html.escape(os.path.basename(plan_path)), W=W, H=H, total=secs(nfr), hold=hold, bites="\n".join("  " + l for h in bite_html for l in h.split("\n")),
        sfx="\n".join(sfx_html) or "      <!-- (none in the plan) -->"))

    # project files, as `hyperframes init` writes them
    name = re.sub(r"[^a-z0-9-]+", "-", os.path.basename(os.path.abspath(outdir)).lower())
    files = {
        "hyperframes.json": {"$schema": "https://hyperframes.heygen.com/schema/hyperframes.json",
                             "registry": "https://raw.githubusercontent.com/heygen-com/hyperframes/main/registry",
                             "paths": {"blocks": "compositions", "components": "compositions/components", "assets": "assets"},
                             "media": {"autoProxy": True}},
        "meta.json": {"id": name, "name": name},
        "package.json": {"name": name, "private": True, "type": "module",
                         "scripts": {"dev": "npx --yes hyperframes preview", "check": "npx --yes hyperframes check",
                                     "render": "npx --yes hyperframes render -o trailer.mp4"}},
    }
    for f, data in files.items():
        p = os.path.join(outdir, f)
        if not os.path.exists(p):
            json.dump(data, open(p, "w"), indent=2)
    print(f"{len(timeline)} bites, {len(blocks)} caption blocks, {nfr / C.FPS:.2f}s -> {outdir}")


if __name__ == "__main__":
    main()
