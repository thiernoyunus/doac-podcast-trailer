"""Render the trailer: source bites in plan order, DOAC-style captions, the audio mix from audio.py.
usage: render.py plan.json trailer.mp4        (run audio.py first; it writes audio_mix.wav next to the plan)

Framing (plan "aspect"):
  16:9 (default)  the full two-shot, no zoom, no crop. Everyone in frame, exactly as the episode was shot.
  9:16            a crop that follows the speaker; run track.py first so each bite has a "track".
Per-bite "zoom": [z_start, z_end] opts one bite into a slow push-in (off unless asked for).
Captions go where captions.py places them (beside the speaker's head, between two people, or at the bottom) and are
built from the transcript words inside each bite. See reference/plan-format.md for the caption keys (big, accent, fix, drop, cap_start...).
"""
import json, os, subprocess, sys
import numpy as np, cv2
from PIL import Image, ImageDraw
from common import load_plan, words, probe, spans, punches
import captions as C

plan = load_plan(sys.argv[1])
out_path = sys.argv[2]
bites = plan["bites"]
SRC = plan["source"]
WIDE = plan["aspect"] == "16:9"
W, H = (1920, 1080) if WIDE else (1080, 1920)
FPS = C.FPS
sw0, sh0, _, _ = probe(SRC)
SH = min(sh0, 1080); SW = int(round(sw0 * SH / sh0 / 2)) * 2   # decode size (source aspect, at most 1080p)
END_HOLD = plan.get("end_hold", 1.2)
COLORS = {**C.COLORS, **{k: tuple(v) for k, v in plan.get("colors", {}).items() if k != "box"}}   # plan "colors" can retune a shade
BOX = tuple(plan.get("colors", {}).get("box", C.BOX_RGB))
words_all = words(plan["transcript"])

# ---------- timeline + caption blocks (shared with hyperframes.py, see captions.py) ----------
timeline, TOTAL = C.place_bites(bites)  # (out_start, bite)
blocks = C.build_blocks(timeline, words_all)
C.place(blocks, plan)   # where each block goes (beside the head, between two people, bottom), its lines and word sizes

# ---------- sprites ----------
PAD = 40
def sprite(text, font, color, box=None, shadow=C.SHADOW):
    """A word as an RGBA sprite with a soft shadow (C.SHADOW_LOW, a dark halo, on a light background). box = (rgb, top, height) from captions.box_rows: the word sits on a
    solid box, no shadow, as wide as the ink plus BOX_PAD each side (like the CSS background in hyperframes.py)."""
    l, t_, r, b_ = font.getbbox(text)
    asc, desc = font.getmetrics()
    padx = int(round(font.size * C.BOX_PAD)) if box else 0
    w, h = r - l + 2 * PAD + 2 * padx, asc + desc + 2 * PAD
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).text((PAD + padx - l, PAD), text, font=font, fill=255)
    m = np.asarray(mask, np.float32) / 255
    shape = m
    if box:
        bm = np.zeros_like(m)
        y0 = int(round(PAD + box[1]))
        bm[max(0, y0):y0 + int(round(box[2])), PAD:w - PAD] = 1
        shape = np.maximum(m, bm)
    # soft drop shadow hugging the letters (none on a box); no outline, no darkening of the footage elsewhere
    sh = np.zeros_like(m)
    for rad, a, dy in (() if box else shadow):
        k = cv2.GaussianBlur(np.roll(shape, dy, 0), (0, 0), rad / 2)
        sh = 1 - (1 - sh) * (1 - np.clip(k * a * 1.6, 0, 1))
    alpha = 1 - (1 - sh) * (1 - shape)
    rgb = np.zeros((h, w, 3), np.float32)
    col = np.array(color[::-1], np.float32)  # frames are BGR
    if box:
        bg = np.array(box[0][::-1], np.float32)
        fill = bg * (1 - m[..., None]) + col * m[..., None]    # letters over the box
        rgb[:] = fill * (shape / np.maximum(alpha, 1e-4))[..., None]
    else:
        rgb[:] = col * (m / np.maximum(alpha, 1e-4))[..., None]
    return np.dstack([rgb, alpha * 255]).astype(np.float32)

for bl in blocks:
    bl["items"] = [i for ln in bl["lines"] for i in ln]
    for it in bl["items"]:
        f = C.font(it["r"], it["px"])
        box = (BOX, *C.box_rows(f, it["r"])) if it["c"] == "box" else None
        color = (255, 255, 255) if box else COLORS.get(it["c"], C.HOST_RGB if bl["host"] else (255, 255, 255))
        it["spr"] = sprite(it["t"], f, color, box, C.SHADOW_LOW if bl["low"] else C.SHADOW)
        it["at"] = bl["s"] if it["r"] == "sub" else it["w"]["s"]   # a subtitle shows whole; other words on their word

# ---------- compositing ----------
def blend(frame, spr, x, y, opacity):
    h, w = spr.shape[:2]
    x0, y0 = int(round(x)), int(round(y))
    fx0, fy0 = max(0, x0), max(0, y0)
    fx1, fy1 = min(W, x0 + w), min(H, y0 + h)
    if fx1 <= fx0 or fy1 <= fy0: return
    s = spr[fy0 - y0:fy1 - y0, fx0 - x0:fx1 - x0]
    a = s[..., 3:4] / 255 * opacity
    reg = frame[fy0:fy1, fx0:fx1].astype(np.float32)
    frame[fy0:fy1, fx0:fx1] = (reg * (1 - a) + s[..., :3] * a).astype(np.uint8)

def draw_captions(frame, tt):
    for bl in blocks:
        if not (bl["s"] - 0.01 <= tt < bl["e"]): continue
        exit_ = min(1, max(0, (tt - (bl["e"] - C.EXIT_S)) / C.EXIT_S)) if bl["e"] - bl["s"] > 0.3 else 0
        for it in bl["items"]:
            dt = tt - it["at"]
            if dt < 0: continue
            p = min(1, dt / (C.HERO_ENTER_S if it["r"] in C.HERO else C.ENTER_S)); p = 1 - (1 - p) ** 3
            op = p * (1 - exit_ ** 2)
            if op <= 0.01: continue
            spr = it["spr"]; x, y = it["x"] - PAD, it["y"] - PAD
            sc = C.ENTER_SCALE - (C.ENTER_SCALE - 1) * p
            blur = C.ENTER_BLUR * (1 - p) + C.EXIT_BLUR * exit_
            if sc != 1 or blur > 0.3:
                h, w = spr.shape[:2]
                nw, nh = int(w * sc), int(h * sc)
                spr = cv2.resize(spr, (nw, nh), interpolation=cv2.INTER_LINEAR)
                if blur > 0.3: spr = cv2.GaussianBlur(spr, (0, 0), blur / 2)
                x -= (nw - w) / 2; y -= (nh - h) / 2
            blend(frame, spr, x, y, op)

# ---------- video ----------
enc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(FPS),
                        "-i", "-", "-i", plan.get("audio", os.path.join(os.path.dirname(os.path.abspath(sys.argv[1])), "audio_mix.wav")), "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", out_path], stdin=subprocess.PIPE)
fi = 0
segs = []   # one decode per piece: (bite start, bite, source start, seconds into the bite, length, punch-in scale)
for out0, b in timeline:
    t0 = 0.0
    for (a, z), p in zip(spans(b), punches(b, plan)):
        segs.append((out0, b, a, t0, z - a, p)); t0 += z - a
for out0, b, a, t0, dur_p, punch in segs:
    n = int(round((out0 + t0 + dur_p) * FPS)) - int(round((out0 + t0) * FPS))
    dec = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-ss", f"{a:.3f}", "-i", SRC, "-t", f"{n / FPS + 0.5:.3f}",
                            "-vf", f"scale={SW}:{SH}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-r", str(FPS), "-"], stdout=subprocess.PIPE)
    shots = b.get("shots") or [[0, b.get("cx", 0.5)]]
    cy = b.get("cy", 0.5)
    z0, z1 = b.get("zoom", (1.0, 1.0))   # 1.0 = no zoom; in 16:9 that is the untouched full frame
    last = None
    for k in range(n):
        raw = dec.stdout.read(SW * SH * 3)
        src = np.frombuffer(raw, np.uint8).reshape(SH, SW, 3) if len(raw) == SW * SH * 3 else last
        last = src
        lt = t0 + k / FPS
        if "track" in b:
            tr = b["track"]; cx = float(np.interp(lt, [p[0] for p in tr], [p[1] for p in tr]))
        else:
            cx = [s[1] for s in shots if s[0] <= lt][-1]
        zp = lt / b["dur"]; zp = zp * zp * (3 - 2 * zp)
        z = (z0 + (z1 - z0) * zp) * punch   # punch: tighten.py's centred punch-in on this piece (1 = none)
        ch = SH / z; cw = ch * W / H
        x0 = min(max(cx * SW - cw / 2, 0), SW - cw)
        y0 = min(max(cy * SH - ch / 2, 0), SH - ch)
        s = W / cw
        M = np.float32([[s, 0, -x0 * s], [0, s, -y0 * s]])
        frame = cv2.warpAffine(src, M, (W, H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        fp = b.get("focus_pull", 0)
        if fp and lt < fp:
            sig = 9 * (1 - lt / fp) ** 2
            if sig > 0.3: frame = cv2.GaussianBlur(frame, (0, 0), sig)
        draw_captions(frame, (fi) / FPS)
        enc.stdin.write(frame.tobytes()); fi += 1
    dec.kill()
for k in range(int(END_HOLD * FPS)):
    enc.stdin.write(np.zeros((H, W, 3), np.uint8).tobytes()); fi += 1
enc.stdin.close(); enc.wait()
print("frames", fi, "dur", TOTAL)
json.dump([dict(s=bl["s"], e=bl["e"], text=" ".join(w["w"] for w in bl["words"]), words=[w["w"] for w in bl["words"]], roles=bl["roles"], place=bl["place"]) for bl in blocks], open(out_path.rsplit(".", 1)[0] + "_captions.json", "w"), indent=1)
