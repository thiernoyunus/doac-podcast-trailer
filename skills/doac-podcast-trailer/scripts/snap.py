"""Move every bite's start/end to the quietest point between words, so no cut clips a syllable.
usage: snap.py plan.json [--force]   (edits the plan in place; prints the before/after and the loudness at each cut)
Safe to re-run: bites already snapped (or marked "lock": true after a hand fix) are left alone unless their
start/end changed since. --force re-snaps everything except locked bites.
A cut is clean when its rms is under ~0.01. The printed rms is the loudest moment in the 0.12 s just outside the cut,
so a fast speaker who barely pauses shows high numbers on clean cuts. Only an edge that is loud right at the cut
(rms over 0.03 there: mid-word) gets <-- check. Then:
  - look for a nearby sentence start/end with a real pause and move the bite there, or
  - if Whisper's word times look stretched at that edge (a word lasting >0.6 s), re-transcribe a 2 s clip
    around it to find the true boundary, set start/end by hand, and add "lock": true."""
import json, sys
from common import load_plan, words, quiet, LOUD

path = sys.argv[1]
force = "--force" in sys.argv
raw = json.load(open(path))
plan = load_plan(path)
rms, best, snap = quiet(plan)
ws = words(plan["transcript"])



bites = raw["bites"] if isinstance(raw, dict) else raw
for b in bites:
    if b.get("lock"):
        print(f"{b.get('id')}: locked, left as is"); continue
    if "parts" in b:
        print(f"{b.get('id')}: parts, tighten.py snaps every part's edges"); continue
    if not force and b.get("_snapped") == [b["start"], b["end"]]:
        print(f"{b.get('id')}: already snapped"); continue
    r = snap(b["start"], b["end"], ws)
    if not r:
        print(b.get("id"), "no words inside, skipped"); continue
    s, e, r0, r1 = r
    flag = "  <-- check" if max(rms(s), rms(e)) > LOUD else ""
    print(f"{b.get('id')}: start {b['start']:.2f}->{s:.2f} (rms {r0:.4f})  end {b['end']:.2f}->{e:.2f} (rms {r1:.4f}){flag}")
    b["start"], b["end"] = s, e
    b["_snapped"] = [b["start"], b["end"]]
json.dump(raw, open(path, "w"), indent=1)
