"""Find the true word boundary near a cut when Whisper's word times look stretched.
usage: edge.py original.mp4 SECONDS [WINDOW=2.0] [--terms "alim,jahl"]
Re-transcribes WINDOW seconds centred on SECONDS and prints each word with its exact source time and Whisper's
confidence (0-1; under ~0.5 means check it by ear). --terms as in transcribe.py."""
import os, subprocess, sys, tempfile
from faster_whisper import WhisperModel
from check_audio import PROMPT   # keeps fillers and repeated words, so a stumble's edges show

args = sys.argv[1:]
terms = args.pop(args.index("--terms") + 1).replace(",", ", ") if "--terms" in args else None
args = [a for a in args if a != "--terms"]
src, t = args[0], float(args[1])
win = float(args[2]) if len(args) > 2 else 2.0
a = max(0, t - win / 2)
wav = os.path.join(tempfile.mkdtemp(), "edge.wav")
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{a:.3f}", "-i", src, "-t", f"{win:.3f}", "-ac", "1", "-ar", "16000", wav], check=True)
m = WhisperModel(os.environ.get("WHISPER_MODEL", "small.en"), device="cpu", compute_type="int8")
segs, _ = m.transcribe(wav, beam_size=5, word_timestamps=True, condition_on_previous_text=False, hotwords=terms, initial_prompt=PROMPT)
for s in segs:
    for w in s.words:
        print(f"{a + w.start:9.2f} - {a + w.end:9.2f}  {w.word.strip():<16} {w.probability:.2f}")
