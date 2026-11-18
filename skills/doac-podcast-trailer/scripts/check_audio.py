"""Listen to the mix the cheap way: transcribe audio_mix.wav close to verbatim and flag every stumble.
usage: check_audio.py plan.json [audio_mix.wav]      (after audio.py; also works on a final mp4)
       check_audio.py --selftest
Prints what is heard in each bite (joins between a bite's pieces show as " / ": no word clipped or doubled there),
then flags, with trailer time and source time:
  filler    um, uh, er, ah, hmm, and "like," / "you know," used as a filler
  repeat    a word or two said twice in a row ("the the", "to, to", "and I, and I")
  extra     a word that isn't in what the bite should play (a stray word from the other speaker at an edge)
  missing   a word the bite should play that isn't heard (a clipped first or last word)
  heard     a different word than the bite should play (often just Whisper's spelling of a name or term)
The episode's transcript drops most fillers and repeats, so tighten.py can't see them; this pass is told to keep them
(a prompt full of fillers). Cut each one ("cut" over its source time, edges from edge.py), re-run tighten.py, audio.py and
this, until nothing is flagged that you mean to remove. Removing a filler or a stumble never changes the meaning.
Whisper can mishear very short bites (under ~1.5 s); check those with edge.py before changing a cut."""
import difflib, os, re, sys

FILL = {"um", "uh", "erm", "er", "ah", "hmm", "mm", "uhm"}
PROMPT = "Um, uh, I- I mean, the the, you know, like, so, uh, we we, hmm, er, ah."   # makes Whisper keep fillers
norm = lambda w: re.sub(r"[^\w']", "", w.lower())


def flags(heard, want):
    """heard: [(word, ...)], want: [word] for one bite. Returns [(index into heard or None, kind, text)]."""
    h = [norm(w[0]) for w in heard]
    out, also = [], set()
    for i, w in enumerate(h):
        raw = heard[i][0].strip()
        prev = heard[i - 1][0].strip() if i else ""
        if w in FILL:
            out.append((i, "filler", raw))
        elif w == "like" and (raw.endswith(",") or prev.endswith(",")) or \
                w == "know" and i and h[i - 1] == "you" and raw.endswith(","):
            out.append((i, "filler", f"{prev} {raw}" if w == "know" else raw))
        elif i and w and w == h[i - 1] and not re.search(r"[.?!]$", prev):   # "...you and I. I do not" is fine
            out.append((i, "repeat", f"{prev} {raw}"))
        elif i >= 3 and h[i - 1:i + 1] == h[i - 3:i - 1] and h[i - 1] != h[i - 2]:
            out.append((i, "repeat", " ".join(x[0].strip() for x in heard[i - 3:i + 1]))); also.add(i - 1)
    flagged = {i for i, _, _ in out} | also
    toks = lambda w: re.findall(r"[\w']+", w.lower())   # "so-called" and "so -called" both become "so called"
    H = [(t, i) for i in range(len(h)) if i not in flagged for t in toks(heard[i][0])]
    Wt = [t for w in want for t in toks(w)]
    sm = difflib.SequenceMatcher(None, [t for t, _ in H], Wt, autojunk=False)
    words_of = lambda a0, a1: " ".join(heard[i][0].strip() for i in dict.fromkeys(i for _, i in H[a0:a1]))
    for op, a0, a1, b0, b1 in sm.get_opcodes():
        at = H[min(a0, len(H) - 1)][1] if H else None
        if op == "insert": out.append((at, "missing", " ".join(Wt[b0:b1])))
        elif op == "replace": out.append((at, "heard", f'"{words_of(a0, a1)}" for "{" ".join(Wt[b0:b1])}"'))
        elif op == "delete": out += [(i, "extra", heard[i][0].strip()) for i in dict.fromkeys(i for _, i in H[a0:a1])]
    return sorted(out, key=lambda f: -1 if f[0] is None else f[0])


def selftest():
    H = lambda s: [(w,) for w in s.split()]
    f = flags(H("I do not want to, to criticize, like, certain uh group"), "I do not want to criticize certain group".split())
    assert [(k, t) for _, k, t in f] == [("repeat", "to, to"), ("filler", "like,"), ("filler", "uh")], f
    f = flags(H("and I, and I concluded"), "and I concluded".split())
    assert [(k, t) for _, k, t in f] == [("repeat", "and I, and I")], f
    f = flags(H("because of a very simple"), "because of a very simple reason.".split())
    assert [(k, t) for _, k, t in f] == [("missing", "reason")], f
    f = flags(H("Yeah the majority"), "the majority".split())
    assert [(k, t) for _, k, t in f] == [("extra", "Yeah")], f
    assert flags(H("it is like a reference"), "it is like a reference".split()) == []   # "like" inside a sentence stays
    print("selftest ok")


if __name__ == "__main__":
    if sys.argv[1] == "--selftest":
        selftest(); sys.exit()
    import numpy as np
    from faster_whisper import WhisperModel
    from common import load_plan, spans, src_time, words
    from captions import place_bites, build_blocks
    plan = load_plan(sys.argv[1])
    mix = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(os.path.abspath(sys.argv[1])), "audio_mix.wav")
    m = WhisperModel(os.environ.get("WHISPER_MODEL", "small.en"), device="cpu", compute_type="int8", cpu_threads=os.cpu_count())
    # the prompt only carries past the first 30 s while each window is conditioned on the text before it
    segs, _ = m.transcribe(mix, beam_size=5, word_timestamps=True, initial_prompt=PROMPT)
    heard = [w for s in segs for w in s.words]
    timeline, _ = place_bites(plan["bites"])
    blocks = build_blocks(timeline, words(plan["transcript"]))   # what each bite should play: its caption words
    for t, b in timeline:
        joins = list(np.cumsum([z - a for a, z in spans(b)])[:-1] + t)   # where the bite's pieces meet, shown as " / "
        ws = ""
        for w in (w for w in heard if t - 0.05 <= w.start < t + b["dur"] - 0.05):
            while joins and w.start >= joins[0] - 0.05: ws += " /"; joins.pop(0)
            ws += " " + w.word.strip()
        print(f"{t:5.1f}s {b.get('id'):>3} {b.get('role', ''):<12} |{ws}")
    # one alignment over the whole trailer: a word Whisper hears a moment early or late across a bite edge isn't flagged twice
    want = [w["w"] for t, b in timeline for bl in blocks if bl["bite"] is b for w in bl["words"]]
    found = []
    for i, kind, text in flags([(w.word,) for w in heard], want):
        at = heard[i].start if i is not None else 0.0
        t, b = [(t, b) for t, b in timeline if t - 0.05 <= at][-1]
        found.append((at, b, kind, text, src_time(spans(b), at - t)[0]))
    print(f"\nstumbles and fillers heard ({len(found)}): cut each one you mean to remove, then re-run tighten.py, audio.py and this")
    for at, b, kind, text, src in found:
        print(f"  {at:6.2f}s  bite {b.get('id'):>3}  src {src:8.2f}  {kind:<8} {text}")
    if not found: print("  none")
