"""Caption logic shared by both finishing paths (render.py draws it with PIL, hyperframes.py writes it as HTML).

- place_bites(bites)            output timeline: [(out_start, bite)], total seconds; sets bite["dur"]
- build_blocks(timeline, words) transcript words -> caption blocks (the on-screen groups), in output seconds
- roles(block)                  per word: "lead" (small), "big" (the hero word), "tail" (medium); "serif" for a soft hero word
- place(blocks, plan)           where each block goes, from the faces in shot: beside the head, between two people, or bottom
- style numbers (sizes, colours, timing) used by both renderers
usage: captions.py plan.json    prints every block with its place (no render);  captions.py --selftest
"""
import json, os, re, sys, zipfile
import numpy as np
from PIL import ImageFont
from common import spans, bite_time, src_time, punches, probe, grab, FONTS, CACHE

# ---- style (both renderers read these) ----
FPS = 30
# accent colours: DOAC colours one key word in most guest blocks, picked by what the word means
COLORS = {"red": (237, 41, 57), "yellow": (255, 208, 1), "green": (46, 204, 113), "pink": (255, 79, 163), "gold": (255, 196, 64)}
HOST_RGB = (255, 208, 1)      # every word the host says is yellow (#FFD001); everyone else is white
BOX_RGB = (226, 35, 45)       # "box": a white word on a red box, for the two or three strongest words
BOX_PAD = 0.10                # box padding left, right and above the capitals, as a fraction of the word's font size
BOX_DROP = {"big": 0.10, "serif": 0.26, "lead": 0.26, "tail": 0.26, "sub": 0.26}   # how far the box reaches below the baseline
# font per role: (file, weight). A wide heavy sans for everything; an italic serif for a soft hero word
FONT = {"lead": ("Montserrat.ttf", "ExtraBold"), "tail": ("Montserrat.ttf", "ExtraBold"), "big": ("Montserrat.ttf", "Black"),
        "serif": ("PlayfairDisplay-Italic.ttf", "SemiBold Italic"), "sub": ("Montserrat.ttf", "Bold")}
SIZE = {"lead": 0.55, "tail": 0.65, "big": 1.0, "serif": 1.05, "sub": 0.25}   # font size = BASE * this (BASE = 15 % of a 16:9 frame)
HERO = ("big", "serif")
HERO_MIN, HERO_MAX = 0.45, 1.3   # a hero word grows or shrinks to fill its place's width, within these shares of BASE
                                 # (below HERO_MIN the place doesn't fit); under 0.8 the other words shrink with it
GAP_EM = 0.26                 # space between words, in em of the line's font
LINE_WORDS = 3                # a lead or tail line holds at most this many words (DOAC stacks short lines)
LINE_BIG, LINE_OTHER = 0.86, 1.0   # line height = font ascent+descent * this
WEIGHT = {"Bold": 700, "ExtraBold": 800, "Black": 900, "SemiBold Italic": 600}
SHADOW = ((4, .35, 2), (16, .55, 3))   # soft drop shadow, no outline: (blur px, opacity, drop px)
SHADOW_LOW = ((4, 1.0, 0), (10, .8, 1), (26, .6, 3))   # on a light background (low contrast): a tight dark halo round the letters
LOW_CONTRAST = 2.0            # contrast ratio (WCAG) of the text colour against the background under the block, below which
                              # the block gets SHADOW_LOW (yellow on a cream wall ~1.0, white on a light curtain ~2.5)
READABLE = 3.0                # review.py flags a rendered block whose letters reach less than this against what's around them
BUSY = 0.12                   # share of strong-edge pixels (a mic, a shelf, a plant) under a block that review.py calls busy
SPLIT_BUSY = 0.22             # a beside-head block with a patch this busy (a mic head) in its lower half, under a calm top, is
                              # split in two so each half can sit higher, clear of it
SPLIT_MIN_S = 0.6             # ...if each half stays on screen at least this long
MOVE_COST = 0.15              # a block beside a head may rise out of a busy patch: cost per frame height moved (in edge share)
TOP_FRAC = {True: 0.64, False: 0.60}    # bottom placement: block top, fraction of frame height (wide, tall)
LIMIT_FRAC = {True: 0.94, False: 0.90}  # ...and the block never goes below this
ENTER_S, HERO_ENTER_S, EXIT_S = 0.12, 0.25, 0.14   # a word blurs in over ENTER_S (hero words HERO_ENTER_S); the block exits
ENTER_SCALE = 1.06            # words enter at this scale and settle to 1
ENTER_BLUR = 16               # px (render.py kernel size; Gaussian sigma = half of it)
EXIT_BLUR = 10
# placement (fractions of the frame width, or of the face height)
EDGE = 0.04                   # keep this far from the frame's sides
PAD = 0.2                     # keep this many face heights between a caption and a face, sideways
BESIDE_W, WIDE_W = 0.46, 0.68 # widest block beside a head / between two people or at the bottom
MIN_FACE = 0.03               # faces smaller than this share of the frame height are ignored (someone far away, a poster)
FACE_SCORE = 0.7              # YuNet confidence for a face (real faces ~0.9, turned away ~0.6-0.8, hands and the back
                              # of a head ~0.5-0.65). A face seen in any of a block's 5 frames counts for the whole block


def base(wide):
    return 160 if wide else 150


STOP = set("the a an and or but so to of in on at for with from by as is are was were be been being it its this that these those there their they them i you he she we me my your our his her not no do does did have has had just really very about into than then what when where which who how why can could would should will i'm it's don't that's you're".split())
NOBIG = set("question personal people everyone example something because customers gonna wanna right know mean thing things like yeah okay kind sort going".split())


def place_bites(bites):
    timeline, t = [], 0.0
    for b in bites:
        b["dur"] = sum(z - a for a, z in spans(b))   # a bite's pieces play back to back as one line
        timeline.append((t, b))
        t += b["dur"]
    return timeline, t


def clean(w):
    return w.strip()


def core(t):
    return re.sub(r"[^\w$%']", "", t)


PUNCT = ".,?!;:"


def bare(w):
    """A word without its punctuation, lower-cased: what `fix` keys and words are matched on."""
    return w.strip(PUNCT + '"').lower()


def fix_word(old, new):
    """`new` in place of `old`, keeping old's trailing punctuation once: new's own punctuation replaces it
    ("young," + "young." -> "young.", "fajr." + "al-Fajr" -> "al-Fajr.")."""
    core_ = new.rstrip(PUNCT)
    return core_ + (new[len(core_):] or old[len(old.rstrip(PUNCT)):])


END_SLACK = 0.15   # a word starting this close before a cut can't be heard there (no word is that short)


def heard(P, s, e):
    """False for a word clipped by a cut: it starts in the last END_SLACK s of a piece, ends after it, and doesn't run on
    into the next piece, so most of it was removed (the 12 hand fixes on the first real run were all this). Whisper's word ends and
    early starts stretch over pauses, so a word's midpoint or share can't tell: at a piece's start bite_time decides."""
    for j, (a, z) in enumerate(P):
        if z - END_SLACK <= s < z < e:
            return j + 1 < len(P) and e > P[j + 1][0]
    return True


def warn(msg):
    print(f"WARNING: {msg}", file=sys.stderr)


def build_blocks(timeline, words_all):
    blocks = []
    for out0, b in timeline:
        n0 = len(blocks)
        # a word may start just before the cut (cap_start earlier than start); it still appears at the cut, never on the previous bite
        # every time below is trailer time, so a pause removed between pieces never splits a block
        P, ws = spans(b), []
        lo, hi = b.get("cap_start"), b.get("cap_end")
        for x in words_all:
            at = clean(x["w"]) and bite_time(P, x["s"], x["e"], lo, hi)
            if at and heard(P, x["s"], x["e"]): ws.append(dict(w=clean(x["w"]), s=out0 + at[0], e=out0 + at[1], src=x["s"]))
        ws.sort(key=lambda w: w["s"])   # a stitch may play a later moment first
        merged = []
        for w in ws:
            if merged and (re.match(r"^[-,]\w", w["w"]) or re.match(r"^%[.,?!]?$", w["w"])):   # "e"+"-commerce", "195"+",000", "10"+"%"
                merged[-1]["w"] += w["w"]; merged[-1]["e"] = w["e"]
            else:
                merged.append(w)
        ws = merged
        dt_ = b.get("drop_times", []); dw_ = {re.sub(r"[^\w$%']", "", x).lower() for x in b.get("drop", [])}
        ws = [w for w in ws if not any(abs(w["src"] - t_) < 0.03 for t_ in dt_)
              and re.sub(r"[^\w$%']", "", w["w"]).lower() not in dw_]
        if ws: ws[0]["w"] = ws[0]["w"][0].upper() + ws[0]["w"][1:]
        for t_, v in b.get("fix_times", {}).items():  # fix one word: the one starting nearest that source time
            w = min(ws, key=lambda w: abs(w["src"] - float(t_)), default=None)
            if w and abs(w["src"] - float(t_)) < 0.03: w["w"] = fix_word(w["w"], v)
            else: warn(f"bite {b.get('id')}: fix_times {t_!r} matches no caption word (cut, dropped, or a wrong time): nothing changed")
        for k, v in b.get("fix", {}).items():  # transcript corrections, matched without punctuation
            hit = [w for w in ws if bare(w["w"]) == bare(k)]
            for w in hit: w["w"] = fix_word(w["w"], v)
            if not hit: warn(f"bite {b.get('id')}: fix {k!r} matches no caption word: nothing changed")
        cur = []
        for i, w in enumerate(ws):
            cur.append(w)
            text = " ".join(x["w"] for x in cur)
            nxt = ws[i + 1] if i + 1 < len(ws) else None
            # don't strand 1-2 words before a sentence end in their own block
            soon = any(re.search(r"[.?!,]$", x["w"]) for x in ws[i + 1:i + 3]) and len(cur) < 8
            brk = (nxt is None or ((len(cur) >= 6 or len(text) >= 34 or cur[-1]["e"] - cur[0]["s"] > 2.6) and not soon)
                   or re.search(r"[.?!]$", w["w"]) or (re.search(r",$", w["w"]) and len(cur) >= 3)
                   or (nxt and nxt["s"] - w["e"] > b.get("gap", 0.5)))
            if brk:
                end = min(nxt["s"] if nxt else out0 + b["dur"], cur[-1]["e"] + 0.6, out0 + b["dur"])
                blocks.append(dict(words=cur, s=cur[0]["s"], e=end, bite=b, t0=out0))
                cur = []
        mine = blocks[n0:]   # a lone small word ("you", "and") looks lost on its own: it joins the block before (or after)
        for i, bl in enumerate(mine):
            if len(bl["words"]) == 1 and core(bl["words"][0]["w"]).lower() in STOP and len(mine) > 1:
                other = mine[i - 1] if i else mine[i + 1]
                if i: other["words"] += bl["words"]; other["e"] = bl["e"]
                else: other["words"][:0] = bl["words"]; other["s"] = bl["s"]
                bl["words"] = []
        blocks[n0:] = [bl for bl in mine if bl["words"]]
    return blocks


def split(bl):
    """A block cut in two (shorter blocks fit higher beside a head): at a comma near the middle, else the middle, never
    leaving a small word alone. Each half keeps its words' times."""
    ws = bl["words"]
    def cost(k):
        lone = any(len(h) == 1 and core(h[0]["w"]).lower() in STOP for h in (ws[:k], ws[k:]))
        return abs(k - len(ws) / 2) - (1.5 if re.search(r",$", ws[k - 1]["w"]) else 0) + (9 if lone else 0)
    k = min(range(1, len(ws)), key=cost)
    hero = [i for i, r in enumerate(bl.get("roles", [])) if r in HERO]   # the half without the block's hero word gets none
    return [dict(bl, words=ws[:k], e=ws[k]["s"], split=True, nobig=bool(hero) and hero[0] >= k),
            dict(bl, words=ws[k:], s=ws[k]["s"], split=True, nobig=bool(hero) and hero[0] < k)]


def roles(block):
    ws = block["words"]; b = block["bite"]
    bigset = {core(x).lower() for x in b.get("big", [])}
    big = [i for i, w in enumerate(ws) if core(w["w"]).lower() in bigset]
    if block.get("nobig"): big = []
    elif not big and b.get("auto_big", True):
        best, score = -1, 0
        for i, w in enumerate(ws):
            c = core(w["w"])
            sc = 100 if re.search(r"\d", c) else (len(c) if len(c) >= 4 and c.lower() not in STOP and c.lower() not in NOBIG and not c.lower().endswith("ly") else 0)
            if sc > score: best, score = i, sc
        if best >= 0: big = [best]
    if not big:
        return ["tail" if i == len(ws) - 1 else "lead" for i in range(len(ws))]
    first, last = big[0], big[-1]
    after = len(ws) - 1 - last
    r = []
    for i in range(len(ws)):
        if i in big: r.append("serif" if core(ws[i]["w"]).lower() in SOFT and i == first else "big")
        elif i > last: r.append("tail" if after <= 3 else "lead")
        else: r.append("lead" if i < first else "tail")
    return r


# a soft or abstract hero word is set in the italic serif instead of heavy caps (DOAC: "path", "humanity?", "important")
SOFT = set("""love loved life lives heart truth think believe feel feeling feelings meaning purpose soul hope dream dreams peace
happiness happy beautiful humanity emotions emotional important story stories wisdom silence family""".split())


def display_text(w, role):
    """What is shown for a word: hero words lose trailing punctuation, and sans hero words are upper-cased."""
    return w["w"].strip('.,;:!"').upper() if role == "big" else w["w"].strip('.,;:!"') if role == "serif" else w["w"]


# words whose meaning picks their colour
RED_WORDS = set("""not no never nothing nobody zero lose losing lost loss fail failed failing failure hate hated wrong worst
waste wasting wasted risk risky broke broken banned ban scam dead die dying death fear scared afraid stop quit lie lies fake
greed ego debt fired crash war danger dangerous problem problems less can't don't won't isn't aren't shouldn't bad hard
struggle pain poor burning burn replaced replace angry mistake mistakes""".split())
GREEN_WORDS = set("""money millionaire millionaires rich wealth wealthy profit profits profitable win winning won success
successful results growth grow grew more free best better sold selling sales revenue income paid earn earning earned yes
good great solution solutions help works worked working opportunity freedom invest investment asset asset-class""".split())
PINK_WORDS = set("love loved loving heart family wife husband kids children mother father mum mom dad beautiful".split())


def mood(word):
    c = core(word).lower()
    return "red" if c in RED_WORDS else "green" if c in GREEN_WORDS else "pink" if c in PINK_WORDS else None


def accents(block, rs, host=False):
    """Colour name per word (None = the line's own colour: white, or yellow on a host line), for one block with roles rs.
    A bite's "accent" colours those words in any role: a list picks each colour by meaning (yellow when it has none), a dict
    {"word": "red"} sets it (red, yellow, green, pink, gold, box). A guest block with none of them gets one automatic accent,
    unless the bite has "auto_accent": false: its first hero word with a red/green/pink meaning, else its first such word.
    No meaning, no colour: a guest line stays white, so yellow keeps meaning "the host". Host lines get no automatic accent."""
    b = block["bite"]
    acc = b.get("accent") or {}
    if isinstance(acc, list): acc = {x: None for x in acc}
    acc = {core(k).lower(): v for k, v in acc.items()}
    out = [(acc[c] or mood(w["w"]) or "yellow") if (c := core(w["w"]).lower()) in acc else None for w in block["words"]]
    if any(out) or host or not b.get("auto_accent", True): return out
    order = [i for i, r in enumerate(rs) if r in HERO] + [i for i, r in enumerate(rs) if r not in HERO]
    i = next((i for i in order if mood(block["words"][i]["w"])), None)
    if i is not None: out[i] = mood(block["words"][i]["w"])
    return out


_fonts = {}
def font(role, px):
    """The PIL font for a role at px."""
    if (role, px) not in _fonts:
        f, var = FONT[role]
        _fonts[role, px] = ImageFont.truetype(f"{FONTS}/{f}", px); _fonts[role, px].set_variation_by_name(var)
    return _fonts[role, px]


def box_rows(font, role):
    """Where a "box" word's box sits, as (top, height) in px from the top of the word's line (PIL font, text drawn at the
    line top): from BOX_PAD above the capitals to BOX_DROP below the baseline."""
    asc, s = font.getmetrics()[0], font.size
    cap = -font.getbbox("H", anchor="ls")[1]
    return asc - cap - BOX_PAD * s, cap + (BOX_PAD + BOX_DROP[role]) * s


def flow_lines(items, maxw):
    """Greedy line flow. items need "r" (role), "iw" (ink width) and "g" (gap before them). Hero words own a line (several
    may share one if they fit); a role change starts a new line; long runs wrap at maxw."""
    lines, cur, curw = [], [], 0
    for it in items:
        iw, g = it["iw"], it["g"]
        if it["r"] in HERO:
            if cur and cur[-1]["r"] in HERO and curw + g + iw <= maxw:
                cur.append(it); curw += g + iw
                continue
            if cur: lines.append(cur)
            cur, curw = [it], iw
            continue
        if cur and cur[0]["r"] in HERO:
            lines.append(cur); cur, curw = [], 0
        if cur and (curw + g + iw > maxw or cur[-1]["r"] != it["r"] or (len(cur) >= LINE_WORDS and it["r"] != "sub")):
            lines.append(cur); cur, curw = [], 0
        cur.append(it); curw += (g if len(cur) > 1 else 0) + iw
    if cur: lines.append(cur)
    return lines


def layout(bl, maxw, base_px):
    """Lay a block out at most maxw px wide: each word's size and ink width, the lines, and the block's (w, h, hero fit).
    The hero word grows or shrinks to fill maxw (fit = its share of full size); the other words keep their size unless
    the hero shrinks a lot, so it always stays the biggest."""
    items = []
    for w, r, c in zip(bl["words"], bl["roles"], bl["colors"]):
        items.append(dict(w=w, r=r, c=c, t=display_text(w, r)))

    def ink(it, px):
        f = font(it["r"], px); l, _, r, _ = f.getbbox(it["t"])
        return r - l + (2 * round(px * BOX_PAD) if it["c"] == "box" else 0)
    hw = max([ink(it, int(base_px * SIZE[it["r"]])) for it in items if it["r"] in HERO] or [0])
    fit = min(HERO_MAX, maxw / hw) if hw else 1.0
    for it in items:
        px = int(base_px * SIZE[it["r"]] * (fit if it["r"] in HERO else min(1, fit / 0.8)))
        f = font(it["r"], px); asc, desc = f.getmetrics()
        it.update(px=px, iw=ink(it, px), asc=asc, lh=asc + desc, g=round(GAP_EM * px))
    lines = flow_lines(items, maxw)
    w = max(sum(i["iw"] + i["g"] for i in ln) - ln[0]["g"] for ln in lines)
    h = sum(max(i["lh"] for i in ln) * (LINE_BIG if ln[0]["r"] in HERO else LINE_OTHER) for ln in lines)
    return lines, w, h, fit


# ---------- where a block goes ----------
def people(boxes):
    """Face boxes (x0, y0, x1, y1) from several frames -> one box per person: boxes that overlap sideways are merged,
    so a head that moves during the block counts once and covers everywhere it went."""
    out = []
    for f in sorted(boxes):
        if out and f[0] <= out[-1][2]:
            o = out[-1]; out[-1] = (o[0], min(o[1], f[1]), max(o[2], f[2]), max(o[3], f[3]))
        else:
            out.append(tuple(f))
    return out


def slots(P, W, H, many=False):
    """Places to try for a caption block, best first: (name, (x0, y0, x1, y1), align, cy). cy is the height the block is
    centred on (clamped inside the rectangle); 1e9 puts it at the bottom. many: two or more people were seen in one frame
    (even if their boxes touch and P merged them into one)."""
    e = EDGE * W
    if not P:   # no face: a small subtitle at the bottom centre
        return [("sub", (e, 0.70 * H, W - e, 0.92 * H), "center", 1e9)]
    fh = max(p[3] - p[1] for p in P); pad = PAD * fh
    top = max(0.05 * H, min(p[1] for p in P) - max(0.3 * fh, 0.1 * H))   # small faces (a wide shot) still leave room
    bot = min(0.95 * H, max(p[3] for p in P) + max(1.3 * fh, 0.2 * H))
    cy = sum(p[1] + 0.75 * (p[3] - p[1]) for p in P) / len(P)   # head to shoulder: centred between the nose and the chin
    if len(P) == 1 and many:   # two people too close to tell apart: no gap between them
        out = []
    elif len(P) == 1:
        x0, _, x1, _ = P[0]
        out = sorted([("left", (e, top, x0 - pad, bot), "right", cy), ("right", (x1 + pad, top, W - e, bot), "left", cy)],
                     key=lambda s: s[1][0] - s[1][2])   # the side with more room first
    else:
        k = max(range(len(P) - 1), key=lambda i: P[i + 1][0] - P[i][2])
        out = [("between", (P[k][2] + pad, top, P[k + 1][0] - pad, bot), "center", cy)]
    low = max(TOP_FRAC[True] * H, max(p[3] for p in P) + 0.25 * fh)   # low: under the chins, over the body or the table
    return out + [("bottom", (e, low, W - e, LIMIT_FRAC[True] * H), "center", 1e9)]


def choose(P, W, H, size, prev=None, force=None, many=False, busy=None):
    """Pick a block's place: (name, (x, y, w, h), align, slot). P = one face box per person, in frame px.
    size(maxw) -> (w, h, readable): the block laid out at most maxw wide. prev: the slot of the block before it in the same
    bite, tried first so the caption stays put; force: the bite's "cap_pos", tried before that (readable or not).
    busy(x, y, w, h) -> share of busy pixels under a rectangle: a block beside or between heads may then rise (never sink,
    toward the desk) to sit off a mic or a shelf, at MOVE_COST per frame height.
    A place is taken only if the block fits inside it and touches no face; if none does it goes to the bottom ("bottom!")."""
    cands = ([prev] if prev else []) + slots(P, W, H, many)
    if force: cands = [s for s in cands if s[0] == force] + cands
    m = 0.1 * max([p[3] - p[1] for p in P] or [0])
    for s in cands:
        name, (x0, y0, x1, y1), align, cy = s
        if x1 - x0 < 0.12 * W: continue
        w, h, ok = size(min(x1 - x0, (BESIDE_W if name in ("left", "right") else WIDE_W) * W))
        if not (ok or name == force) or w > x1 - x0 + 1 or h > y1 - y0: continue
        x = x0 if align == "left" else x1 - w if align == "right" else (x0 + x1 - w) / 2
        y = min(max(cy - h / 2, y0), y1 - h)
        ys = [y] + ([v for v in np.arange(y0, y, H / 54)] if busy and name in ("left", "right", "between") else [])
        ys = [v for v in ys if not any(x < p[2] + m and p[0] - m < x + w and v < p[3] + m and p[1] - m < v + h for p in P)]
        if not ys: continue
        if busy: y = min(ys, key=lambda v: busy(x, v, w, h) + MOVE_COST * (y - v) / H)
        else: y = ys[0]
        return name, (x, y, w, h), align, s
    w, h, _ = size(WIDE_W * W)
    return "bottom!", ((W - w) / 2, LIMIT_FRAC[True] * H - h, w, h), "center", None   # as low as it goes


def faces(plan, blocks, W, H, detect=True):
    """Per block: (face boxes (x0, y0, x1, y1) in frame px on 5 frames across its life, the most faces seen in one of
    those frames with a sure score (0.8+)), as the viewer sees them (after
    the piece's punch-in or zoom: YuNet finds them on the source frame, then they go through the same crop render.py
    makes). Detections are cached per source second in faces.json next to the transcript. Also the block's middle frame
    as the viewer sees it (grey, 1/4 size), for contrast and clutter. detect=False (9:16): that frame only, no faces."""
    import cv2
    src = plan["source"]; sw0, sh0, _, _ = probe(src)
    SH = min(sh0, 1080); SW = SH * sw0 / sh0             # render.py's decode size
    dw, dh = 960, int(round(960 * sh0 / sw0 / 2)) * 2   # detection size
    path = os.path.join(os.path.dirname(plan["transcript"]), "faces.json")
    cache = json.load(open(path)) if os.path.exists(path) else {}
    tpath = os.path.join(os.path.dirname(plan["transcript"]), "thumbs.npz")   # small grey frames, for contrast and clutter
    try: thumbs = dict(np.load(tpath))
    except (OSError, ValueError, EOFError, zipfile.BadZipFile): thumbs = {}   # none yet, or half-written: rebuilt
    tw, th = dw // 2, dh // 2
    det, out = None, []
    for bl in blocks:
        b = bl["bite"]; P, zs = spans(b), punches(b, plan)
        z0, z1 = b.get("zoom", (1.0, 1.0)); boxes, many, view = [], 0, None
        for k in (0.05, 0.3, 0.55, 0.8, 0.97) if detect else (0.55,):
            t = bl["s"] + (bl["e"] - bl["s"]) * k - bl["t0"]
            st, j = src_time(P, t)
            key = f"{os.path.basename(src)}@{st:.2f}"
            fr = None
            if detect and key not in cache:
                det = det or cv2.FaceDetectorYN.create(os.path.join(CACHE, "yunet.onnx"), "", (dw, dh), 0.5)
                fr = grab(src, st, dw, dh)
                fa = det.detect(fr)[1] if fr is not None else None
                cache[key] = [[round(float(v) / d, 4) for v, d in zip(f[:4], (dw, dh, dw, dh))] + [round(float(f[-1]), 3)]
                              for f in (fa if fa is not None else [])]   # x, y, w, h (0-1), score
            zp = t / b["dur"]; zp = zp * zp * (3 - 2 * zp)
            z = (z0 + (z1 - z0) * zp) * zs[j]
            ch = SH / z; cw = ch * W / H; s = W / cw
            fx = float(np.interp(t, [q[0] for q in b["track"]], [q[1] for q in b["track"]])) if "track" in b else \
                [q[1] for q in (b.get("shots") or [[0, b.get("cx", 0.5)]]) if q[0] <= t][-1]   # render.py's crop centre
            cx = min(max(fx * SW - cw / 2, 0), SW - cw); cy = min(max(b.get("cy", 0.5) * SH - ch / 2, 0), SH - ch)
            if k == 0.55:   # the block's middle frame, as the viewer sees it, at a quarter of the frame size
                if key not in thumbs:
                    fr = fr if fr is not None else grab(src, st, dw, dh)
                    thumbs[key] = cv2.resize(cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY), (tw, th), interpolation=cv2.INTER_AREA) \
                        if fr is not None else np.zeros((th, tw), np.uint8)
                M = np.float32([[s * SW / tw / 4, 0, -cx * s / 4], [0, s * SH / th / 4, -cy * s / 4]])
                view = cv2.warpAffine(thumbs[key], M, (W // 4, H // 4), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
            many = max(many, sum(f[4] >= 0.8 for f in cache.get(key, [])))
            for u, v, fw, fh, score in (cache[key] if detect else []):
                if score < FACE_SCORE: continue
                x0, y0 = max((u * SW - cx) * s, 0), max((v * SH - cy) * s, 0)
                x1, y1 = min(((u + fw) * SW - cx) * s, W), min(((v + fh) * SH - cy) * s, H)
                if x1 > x0 and y1 - y0 >= MIN_FACE * H: boxes.append((x0, y0, x1, y1))
        out.append((boxes, many, view))
    json.dump(cache, open(path, "w"))
    with open(tpath + ".tmp", "wb") as f: np.savez_compressed(f, **thumbs)
    os.replace(tpath + ".tmp", tpath)   # whole or not at all, if two scripts run at once
    return out


def lum(rgb_or_grey):
    """Relative luminance (WCAG, 0-1) of 0-255 sRGB values: an (r, g, b) tuple, or an array of grey levels."""
    v = np.asarray(rgb_or_grey, np.float64) / 255
    v = np.where(v <= 0.04045, v / 12.92, ((v + 0.055) / 1.055) ** 2.4)
    return float(v @ (0.2126, 0.7152, 0.0722)) if v.shape == (3,) else v


def edges(view):
    """Strong edges of the grey frame view (a mic, a shelf, a plant; a plain wall or a soft curtain has few), 0/1."""
    import cv2
    return cv2.dilate(cv2.Canny(view, 100, 250), np.ones((3, 3), np.uint8)) > 0


def under(a, box):
    """The part of a 1/4-size frame array under box (x, y, w, h) in frame px."""
    x, y, w, h = (max(0, int(round(v / 4))) for v in box)
    return a[y:y + max(h, 1), x:x + max(w, 1)]


def cells(E, box):
    """Busy share of each cell of box (x, y, w, h) cut 4 x 4, top row first: a small busy thing (a mic head) shows up."""
    x, y, w, h = box
    return [[float(under(E, (x + w * c / 4, y + h * r / 4, w / 4, h / 4)).mean()) for c in range(4)] for r in range(4)]


def contrast(view, box, rgb):
    """WCAG contrast ratio of text colour rgb against the brighter part (75th percentile) of the background under box."""
    reg = under(view, box)
    return (lum(rgb) + 0.05) / (float(np.percentile(lum(reg), 75)) + 0.05) if reg.size else None


def frame_size(wide):
    return (1920, 1080) if wide else (1080, 1920)


def place(blocks, plan):
    """Decide every block's place, roles, colours and layout. Sets on each block: "place" (left, right, between, bottom,
    sub; "bottom!" = nothing fit, so it became a small subtitle at the bottom), "box" (x, y, w, h) in frame px, "align",
    "lines" (items with px, x, y), "fit", "host".
    16:9: from the faces in shot (see slots). 9:16: always the bottom."""
    wide = plan.get("aspect", "16:9") != "9:16"
    W, H = frame_size(wide); base_px = base(wide)
    F = faces(plan, blocks, W, H, detect=wide)
    prev = None
    for bl, (boxes, many, view) in zip(blocks, F):
        b = bl["bite"]
        bl["host"] = bool(plan.get("host")) and b.get("speaker") == plan.get("host")
        P = people(boxes)
        E = edges(view) if view is not None else None
        busy = (lambda *r: float(under(E, r).mean())) if E is not None else None
        rise = (lambda *r: busy(*r) + max(map(max, cells(E, r)))) if E is not None else None   # a small mic counts too
        bl["roles"] = ["sub"] * len(bl["words"]) if wide and not P else roles(bl)
        bl["colors"] = accents(bl, bl["roles"], bl["host"])
        memo, last = {}, []

        def size(maxw):   # choose() returns right after sizing the place it takes, so last[-1] is that layout
            maxw = int(maxw)
            if maxw not in memo: memo[maxw] = layout(bl, maxw, base_px)
            last.append(memo[maxw])
            return memo[maxw][1], memo[maxw][2], memo[maxw][3] >= HERO_MIN
        if wide:
            same = prev is not None and prev["bite"] is b and prev["slot"]
            name, (x, y, w, h), align, slot = choose(P, W, H, size, prev["slot"] if same else None, b.get("cap_pos"), many >= 2, rise)
            if name == "bottom!":   # nothing fit: a small subtitle under the faces rather than a big block over them
                bl["roles"] = ["sub"] * len(bl["words"]); memo.clear()
                w, h, _ = size(WIDE_W * W)
                x, y = (W - w) / 2, 0.92 * H - h
        else:   # 9:16: the lower third, as before
            w, h, _ = size(W - 2 * EDGE * W)
            name, (x, y, w, h), align, slot = "bottom", ((W - w) / 2, min(TOP_FRAC[False] * H, LIMIT_FRAC[False] * H - h), w, h), "center", None
        lines, _, _, fit = last[-1]
        bl.update(place=name, box=(x, y, w, h), align=align, lines=lines, fit=fit, slot=slot)
        # the background under the block: a low-contrast one gets the dark halo (SHADOW_LOW) in both renderers
        bl["contrast"] = contrast(view, bl["box"], HOST_RGB if bl["host"] else (255, 255, 255)) if view is not None else None
        bl["busy"] = busy(*bl["box"]) if busy else 0.0
        bl["low"] = bl["contrast"] is not None and bl["contrast"] < LOW_CONTRAST
        if name in ("left", "right") and len(bl["words"]) >= 3 and not bl.get("split") and E is not None:
            g = cells(E, bl["box"])
            bl["hot"] = max(map(max, g[2:])) >= SPLIT_BUSY and max(g[0]) < 0.13 and \
                min(h["e"] - h["s"] for h in split(bl)) >= SPLIT_MIN_S   # no half flashes by
        ly = y
        for ln in lines:   # word positions: the ink's left edge, and the line top + the line's baseline offset
            tw = sum(i["iw"] + i["g"] for i in ln) - ln[0]["g"]
            lx = x if align == "left" else x + w - tw if align == "right" else x + (w - tw) / 2
            maxasc = max(i["asc"] for i in ln)
            for i in ln:
                i["x"], i["y"] = lx, ly + maxasc - i["asc"]
                lx += i["iw"] + i["g"]
            ly += max(i["lh"] for i in ln) * (LINE_BIG if ln[0]["r"] in HERO else LINE_OTHER)
        prev = bl
    hot = [bl.pop("hot", False) for bl in blocks]
    if any(hot):   # split the blocks stuck on a mic, then place everything again (halves never split again)
        blocks[:] = [h for bl, t in zip(blocks, hot) for h in (split(bl) if t else [bl])]
        place(blocks, plan)


def selftest():
    W, H = 1920, 1080
    def block(bw, bh):
        return lambda maxw: (min(bw, maxw), bh, bw <= maxw)   # a hero word shrinks to fit; too small = not readable
    def hits(r, P):
        x, y, w, h = r
        return any(x < p[2] and p[0] < x + w and y < p[3] and p[1] < y + h for p in P)
    cases = [   # (face boxes, block size, expected place)
        ([(450, 250, 700, 560)], (600, 300), "right"),                    # guest on the left third: beside the head, right
        ([(1200, 230, 1430, 520)], (600, 300), "left"),                   # host on the right: beside the head, left
        ([(760, 150, 1160, 560)], (700, 260), "bottom"),                  # centred, block too wide for either side: under the chin
        ([(420, 300, 560, 420), (1300, 280, 1440, 400)], (500, 240), "between"),   # two people far apart
        ([(760, 300, 900, 420), (1010, 280, 1150, 400)], (500, 240), "bottom"),    # two people close together
        ([], (900, 90), "sub"),                                           # nobody in shot: a subtitle
        ([(760, 300, 1000, 560), (980, 280, 1200, 540)], (500, 240), "bottom"),    # two faces touching: no gap, bottom
        ([(300, 40, 1700, 1060)], (900, 300), "bottom!"),                 # a face fills the frame: nothing fits
    ]
    for boxes, (bw, bh), want in cases:
        P = people(boxes)
        name, r, align, _ = choose(P, W, H, block(bw, bh), many=len(boxes) >= 2)
        assert name == want, (boxes, name, want)
        assert name == "bottom!" or not hits(r, P), (boxes, name, r)
        assert 0 <= r[0] and r[0] + r[2] <= W and 0 <= r[1] and r[1] + r[3] <= H, r
        if name in ("left", "right"):   # text leans toward the face
            assert align == {"left": "right", "right": "left"}[name]
    assert people([(100, 0, 200, 50), (150, 10, 260, 60), (900, 0, 1000, 50)]) == [(100, 0, 260, 60), (900, 0, 1000, 50)]
    P = people([(450, 250, 700, 560)])   # the place stays put for the next block of the bite, if it still fits
    first = choose(P, W, H, block(600, 300))
    assert choose(P, W, H, block(500, 200), prev=first[3])[3] is first[3]
    assert choose(P, W, H, block(600, 300), force="left")[0] == "left"
    # a busy patch (a mic) beside the chin: the block rises off it, never sinks
    mic = lambda x, y, w, h: max(0, min(y + h, 700) - max(y, 560)) / h
    _, (x, y, w, h), _, _ = choose(P, W, H, block(600, 300), busy=mic)
    assert y + h <= 560 and y < first[1][1], (y, h, first)
    assert choose(P, W, H, block(600, 300), busy=lambda *r: 0)[1] == first[1]   # nothing busy: stays centred on the face
    # fix: punctuation-insensitive keys, punctuation kept once, the fix's own punctuation replaces the word's
    assert fix_word("young,", "young.") == "young." and fix_word("fajr.", "al-Fajr") == "al-Fajr."
    assert fix_word("committee.", "committee?") == "committee?" and fix_word("Prophet.", "Prophet ﷺ") == "Prophet ﷺ."
    assert fix_word("contrast,", "contracts") == "contracts," and fix_word("that", "that?") == "that?"
    assert bare("fajr.") == bare("Fajr") == "fajr"
    W_ = lambda w, s: dict(w=w, s=s, e=s + 0.2)
    b = dict(id="t", start=10.0, end=12.0, fix={"fajr.": "al-Fajr", "young": "young.", "nothere": "x"},
             fix_times={"10.41": "The", "11.90": "y"})
    ws = [W_("in", 10.0), W_("fajr.", 10.2), W_("easiest", 10.42), W_("thing", 10.38), W_("young,", 10.8), W_("gone", 11.9)]
    import io, contextlib
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        got = [w["w"] for bl in build_blocks(place_bites([b])[0], ws) for w in bl["words"]]
    assert got == ["In", "al-Fajr.", "thing", "The", "young."], got   # one fix_times word only (the nearest); no "young.,"
    assert "'nothere' matches no caption word" in err.getvalue() and "'11.90' matches no" in err.getvalue(), err.getvalue()
    # a word clipped at a cut edge (most of it in the removed part) isn't captioned; one mostly inside is
    P2 = [[10.0, 11.0], [12.0, 13.0]]
    assert heard(P2, 10.5, 10.84) and not heard(P2, 10.9, 11.3) and not heard(P2, 12.88, 13.2)   # cut off at an end
    assert heard(P2, 10.9, 12.3) and heard(P2, 11.5, 12.4)   # runs on into the next piece; an early Whisper start
    assert heard(P2, 10.86, 10.99)                          # short, and ends before the cut
    # a lone small word joins its neighbour block; a split never leaves one alone and prefers a comma
    b = dict(id="m", start=20.0, end=24.0, gap=0.3)
    ws = [W_("We", 20.0), W_("said", 20.25), W_("it.", 20.5), W_("And", 21.5)]
    assert [[w["w"] for w in bl["words"]] for bl in build_blocks(place_bites([b])[0], ws)] == [["We", "said", "it.", "And"]]
    words4 = [dict(w=w, s=i, e=i + .2) for i, w in enumerate(["Say", "yes,", "or", "no."])]
    a, z = split(dict(words=words4, s=0, e=4))
    assert [w["w"] for w in a["words"]] == ["Say", "yes,"] and a["e"] == 2 and z["s"] == 2 and z["e"] == 4
    assert [len(h["words"]) for h in split(dict(words=[dict(w=w, s=i, e=i) for i, w in enumerate(["the", "big", "idea"])], s=0, e=3))] == [2, 1]
    print("selftest ok")


if __name__ == "__main__":
    # dry run: print the caption blocks and where each goes, without rendering. usage: captions.py plan.json
    import sys
    if sys.argv[1] == "--selftest":
        selftest(); sys.exit()
    from common import load_plan, words
    plan = load_plan(sys.argv[1])
    timeline, total = place_bites(plan["bites"])
    blocks = build_blocks(timeline, words(plan["transcript"]))
    place(blocks, plan)
    for bl in blocks:
        print(f"{bl['s']:5.1f}s  bite {bl['bite'].get('id'):>3}  {bl['place']:<8}" + ("host " if bl["host"] else "") +
              " ".join((f"[{display_text(w, r)}]" if r in HERO else w["w"]) + (f"<{c}>" if c else "") for w, r, c in zip(bl["words"], bl["roles"], bl["colors"]))
              + (f"   (light background, contrast {bl['contrast']:.1f}: dark halo)" if bl["low"] else "")
              + (f"   (busy background {bl['busy']:.0%})" if bl["busy"] > BUSY else ""))
    print(f"total {total:.1f}s   ([WORD] = hero word, <red> = that word's colour, host = a yellow line; "
          "bottom! = nothing fit beside or between the faces)")
