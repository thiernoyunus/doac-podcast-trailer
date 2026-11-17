"""Transcribe an episode with word timestamps.  usage: transcribe.py original.mp4 [transcript.json] [--terms "alim,jahl,fiqh"]
Writes transcript.json ([{start,end,text,words:[{w,s,e,p}]}], p = Whisper's confidence in the word, 0-1),
transcript.txt (one line per segment, [mm:ss], written as it goes so you can read it while it runs), and audio.wav
(16 kHz mono, reused by snap.py). --terms: words the guest uses that an English model mishears (Arabic, Urdu, technical
names), passed to Whisper as hotwords. Takes roughly a quarter of the episode's length on 4 CPUs."""
import json, os, subprocess, sys, time
from faster_whisper import WhisperModel

args = sys.argv[1:]
terms = args.pop(args.index("--terms") + 1).replace(",", ", ") if "--terms" in args else None
args = [a for a in args if a != "--terms"]
src = args[0]
out = args[1] if len(args) > 1 else "transcript.json"
wav = os.path.join(os.path.dirname(os.path.abspath(out)), "audio.wav")
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", wav], check=True)
t = time.time()
m = WhisperModel(os.environ.get("WHISPER_MODEL", "small.en"), device="cpu", compute_type="int8", cpu_threads=os.cpu_count())
segs, _ = m.transcribe(wav, beam_size=1, word_timestamps=True, vad_filter=True, condition_on_previous_text=False, hotwords=terms)
res = []
with open(out.replace(".json", ".txt"), "w") as f:
    for s in segs:
        res.append({"start": s.start, "end": s.end, "text": s.text.strip(),
                    "words": [{"w": w.word, "s": w.start, "e": w.end, "p": round(w.probability, 3)} for w in s.words]})
        f.write(f"[{int(s.start // 60):02d}:{s.start % 60:05.2f}] {s.text.strip()}\n"); f.flush()
        if len(res) % 20 == 0: print(f"{s.end / 60:.1f} min", flush=True)
json.dump(res, open(out, "w"))
print(f"done in {time.time() - t:.0f}s, {len(res)} segments")
