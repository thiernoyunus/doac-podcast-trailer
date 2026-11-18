"""Shared helpers: plan loading, cache paths, source probing."""
import json, os, re, subprocess, sys

CACHE = os.environ.get("DOAC_CACHE", os.path.expanduser("~/.cache/doac-trailer"))
FONTS = os.path.join(CACHE, "fonts")


def load_plan(path):
    """A plan is {"source", "transcript", "aspect", "bites": [...]} (a bare list of bites also works)."""
    p = json.load(open(path))
    if isinstance(p, list):
        p = {"bites": p}
    base = os.path.dirname(os.path.abspath(path))
    for k, d in (("source", "original.mp4"), ("transcript", "transcript.json")):
        v = p.get(k, d)
        p[k] = v if os.path.isabs(v) else os.path.join(base, v)
    p.setdefault("aspect", "16:9")
    for i, b in enumerate(p["bites"], 1):
        b.setdefault("id", str(i))
        b["_max_pause"] = p.get("max_pause", 0.2)   # tighten.py's pieces depend on it too (tight_key)
    return p


def words(transcript):
    return [w for s in json.load(open(transcript)) for w in s["words"]]


def probe(src):
    """(width, height, fps, duration) of the first video stream, via ffmpeg (ffprobe may be missing)."""
    err = subprocess.run(["ffmpeg", "-hide_banner", "-i", src], capture_output=True, text=True).stderr
    w, h = map(int, re.search(r"Video:.*?(\d{3,5})x(\d{3,5})", err).groups())
    fps = float(re.search(r"([\d.]+) fps", err).group(1))
    hh, mm, ss = re.search(r"Duration: (\d+):(\d+):([\d.]+)", err).groups()
    return w, h, fps, int(hh) * 3600 + int(mm) * 60 + float(ss)


def grab(src, t, w, h):
    """One frame at t seconds, scaled to w x h, as a BGR numpy array (None past the end)."""
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", f"{t:.3f}", "-i", src, "-frames:v", "1", "-vf", f"scale={w}:{h}",
                          "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], capture_output=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(h, w, 3) if len(raw) == w * h * 3 else None


# ---------- a bite's pieces: the source ranges it plays back to back as one line ----------
def tight_key(b):
    """What tighten.py's pieces were computed from: if any of it changed, the pieces are stale."""
    return [b.get(k) for k in ("start", "end", "parts", "cut", "keep", "keep_pauses", "lock", "_max_pause")]


def spans(b):
    """[[start, end], ...] in source seconds: tighten.py's "pieces", else "parts", else [[start, end]]."""
    if ("pieces" in b or b.get("cut")) and b.get("_tightened") != tight_key(b):
        sys.exit(f"bite {b.get('id')}: start/end/parts/cut/keep or max_pause changed since tighten.py ran (or it never ran): run tighten.py plan.json")
    if "pieces" in b:
        if not b["pieces"]: sys.exit(f"bite {b.get('id')}: tighten.py removed all of it: drop the bite or fix its cut")
        return b["pieces"]
    return b.get("parts") or [[b["start"], b["end"]]]


def bite_time(P, s, e, lo=None, hi=None):
    """Where a word heard at source s..e plays inside a bite made of pieces P: (start, end) in seconds from the bite's
    start, or None if it isn't played. A word belongs to a piece when it starts inside it (50 ms slack; lo/hi =
    cap_start/cap_end move the bite's outer edges). A word whose start lies in a removed stretch but runs on into the
    next piece (Whisper often starts words early) appears at the join; one that ends there (a filler, a cut) is gone."""
    off = 0.0
    for j, (a, z) in enumerate(P):
        first, last = j == 0, j == len(P) - 1
        l = (lo if first and lo is not None else a) - 0.05
        h = (hi if last and hi is not None else z) - 0.05
        early = not first and P[j - 1][1] - 0.05 <= s < l and e > a + 0.1
        if l <= s < h or early:
            return off + max(s - a, 0), off + (e - a if last else min(e - a, z - a))
        off += z - a
    return None


def src_time(P, t):
    """(source second, piece index) shown t seconds into a bite made of pieces P."""
    off = 0.0
    for j, (a, z) in enumerate(P):
        if t < off + z - a or j == len(P) - 1:
            return a + t - off, j
        off += z - a


def punches(b, plan):
    """Picture scale per piece: a join that removed more than 0.15 s (or jumps elsewhere in the episode) toggles between
    the full frame and a centred punch-in (plan "punch_scale", default 1.12), which hides the jump cut."""
    P, z, out = spans(b), plan.get("punch_scale", 1.12), [1.0]
    for (_, e0), (a1, _) in zip(P, P[1:]):
        small = 0 <= a1 - e0 <= 0.15 or b.get("punch") is False
        out.append(out[-1] if small else (z if out[-1] == 1.0 else 1.0))
    return out


def subtract(P, R):
    """Pieces P with the ranges R removed (both [[start, end], ...] in source seconds); slivers under 50 ms are dropped."""
    for x, y in R:
        P = [q for a, z in P for q in ([[a, min(z, x)], [max(a, y), z]] if x < z and y > a else [[a, z]])]
    return [[a, z] for a, z in P if z - a >= 0.05]


# ---------- quiet points on the episode's audio (snap.py, tighten.py) ----------
QUIET = 0.01   # rms under this is a clean place to cut
HOLD = 0.12    # a real pause stays quiet this long; a gap inside a word ("twenty-eigh|teen") doesn't


LOUD = 0.03   # rms over this AT a cut edge itself means the cut lands in speech (<-- check). Measured at the edge, not over
              # the 0.12 s beside it: a fast speaker's next word right after a clean dip is not a clipped edge


def quiet(plan):
    """rms(t), best(lo, hi, side) and snap(start, end, words) on the episode's 16 kHz audio.wav (from transcribe.py)."""
    import wave
    import numpy as np
    wav = os.path.join(os.path.dirname(plan["transcript"]), "audio.wav")
    if not os.path.exists(wav):
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", plan["source"], "-vn", "-ac", "1", "-ar", "16000", wav], check=True)
    w = wave.open(wav); SR = w.getframerate()
    A = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768

    def rms(t):
        i = int(t * SR); h = int(0.015 * SR)
        x = A[max(0, i - h):i + h]
        return float(np.sqrt(np.mean(x ** 2))) if len(x) else 0.0   # past the end: silence

    def best(lo, hi, side):
        """Quietest point in [lo, hi] that is followed (side=+1, an end) or preceded (side=-1, a start) by HOLD s of quiet.
        Returns (time, loudness of the loudest moment in that HOLD window)."""
        ts = np.arange(lo, max(hi, lo + 0.02), 0.01)
        r = np.array([max(rms(t + side * k) for k in np.arange(0, HOLD + 0.001, 0.02)) for t in ts])
        return float(ts[r.argmin()]), float(r.min())

    def snap(start, end, ws):
        """Move a span's start/end to the quietest point between words: (start, end, rms at start, rms at end), or None
        if no word is inside."""
        inside = [x for x in ws if start - 0.05 <= x["s"] < end - 0.05]
        if not inside:
            return None
        prev = [x for x in ws if x["e"] <= inside[0]["s"] + 0.01]
        nxt = [x for x in ws if x["s"] >= inside[-1]["e"] - 0.01 and x is not inside[-1]]
        lo = max(prev[-1]["e"] - 0.1, inside[0]["s"] - 0.35) if prev else inside[0]["s"] - 0.35
        s0, r0 = best(lo, inside[0]["s"] + 0.06, -1)
        # Whisper often ends a word early (long numbers, trailing consonants), so look up to 0.6 s past its end
        e0, r1 = best(inside[-1]["e"] - 0.06, min(inside[-1]["e"] + 0.6, nxt[0]["s"] + 0.1 if nxt else 1e9), +1)
        # never trade a quieter hand-placed cut for a louder one
        c0 = max(rms(start + 0.03 - k) for k in np.arange(0, HOLD + 0.001, 0.02))
        c1 = max(rms(end - 0.03 + k) for k in np.arange(0, HOLD + 0.001, 0.02))
        if c0 <= r0: s0, r0 = start + 0.03, c0
        if c1 <= r1: e0, r1 = end - 0.03, c1
        return round(s0 - 0.03, 3), round(e0 + 0.03, 3), r0, r1

    return rms, best, snap
