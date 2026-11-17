---
name: doac-podcast-trailer
description: Cut a Diary of a CEO style trailer (75-110 s, 16:9 two-shot, DOAC captions) from any full podcast episode. Use when someone sends a podcast video or link and wants a trailer, teaser or intro cut from it.
---

# DOAC Podcast Trailer

Turns one full podcast episode into a 75-110 second trailer. The trailer is built around the episode's one topic: it sells the guest, gives away one useful idea, builds friction, and ends on an unanswered question.

The editing judgment is yours. The scripts do the mechanics.
Read `reference/editorial.md` before choosing anything. It holds the rules that made our best trailer, and the mistakes to avoid.
`reference/examples.md` shows three trailers bite by bite (two of our older cuts and a real DOAC trailer), and why they work.
`reference/plan-format.md` describes the plan file every step reads.

## Defaults (unless the person asks otherwise)
- 16:9, the full two-shot: no slow zoom, so both people are always in view. The only crop is the brief punch-in (1.12x, centred) that hides a jump cut inside a bite.
- 75-110 s, 17-30 bites (a stitched bite is still one bite), ending on 1.2 s of black.
- Fast pace: every bite is tightened (`tighten.py`): pauses over 0.2 s, stumbles and fillers out, so someone is talking ~98% of the time. One deliberate pause at most, before the last line (`keep_pauses`).
- DOAC captions: stacked blocks of 3-8 words with one huge hero word, beside the speaker's head (one face), in the gap between two people, or as a small subtitle at the bottom when there's no room. Never over a face. Host lines are yellow, everyone else white, with a coloured word (red, green, or a red box) in most guest blocks.
- Finishing: always HyperFrames. `setup.sh` installs it if it's missing, without asking. The person gets a project they can open and tweak themselves. The Python renderer is only a fallback for when HyperFrames can't run.
- No music. Sound effects (boom, whoosh, riser) come from HyperFrames' sound library, never synthesized.

## Steps

Work in a folder of its own, e.g. `trailer-<episode>/`. `S` is this skill's folder.

1. **Set up**: `bash $S/scripts/setup.sh`, then `source ~/.cache/doac-trailer/env.sh` (in every new shell).
   Setup installs everything, HyperFrames included (with Node 22, Chrome and ffprobe if missing), and skips what is already there. Don't ask the person first.
   If it prints `HYPERFRAMES NOT READY`, note the reason: you'll use the Python fallback in step 7 and tell the person why.
2. **Get the episode** as `original.mp4`:
   - Google Drive: `gdown <file-id> -O original.mp4`
   - YouTube: `yt-dlp`
   - Upload: copy the file in.
3. **Transcribe**: `python3 $S/scripts/transcribe.py original.mp4`. This writes `transcript.json`, `transcript.txt` and `audio.wav`, and takes about a quarter of the episode's length. `transcript.txt` fills in as it goes, so read it while it finishes.
   - **Non-English terms**: if the guest uses Arabic, Urdu, Malay or technical words (alim, jahl, madhhab, fiqh, Shafi'i...), pass them: `transcribe.py original.mp4 --terms "alim,jahl,madhhab,fiqh,Shafi'i"` (also on `edge.py`). Without it the English model hears "alim" as "island". Every word in `transcript.json` has a confidence `p` (0-1): in the delivery note, list the trailer's words under ~0.5 (especially the terms) so a person checks them by ear.
4. **Pick the story** following `reference/editorial.md`:
   - Name the one topic, and decide the kind of episode: a guest episode, a guest plus panel, or a panel (`reference/editorial.md`, section 1). With a main guest it's guest-led: it opens on the strongest line (the guest's boldest claim, or a host question the guest answers within a few seconds), starting on the claim itself: cut throat-clearing lead-ins like "I don't want to criticize, but" and the guest speaks for at least half of it. In a panel, share the trailer between the strongest voices.
   - Introduce everyone who speaks twice with their name and credential together (start the bite on "we have [name]…"), and mark those bites with `introduces`.
   - Find who is who: `python3 $S/scripts/frames.py original.mp4 who.jpg --burst MM:SS ...` shows three frames per time, so you can see whose mouth moves.
   - List candidate lines.
   - Build the arc.
   - Write `plan.json` with a `role`, `speaker` and `why` on every bite. Stitch with `parts`, remove stumbles and lead-ins with `cut`, and write `original` (exactly as said) on every bite that uses either (`reference/editorial.md`, section 3).
   - Use `python3 $S/scripts/words.py transcript.json START-END` to put each start and end on a sentence boundary.
5. **Clean the cuts**: `python3 $S/scripts/snap.py plan.json`. Fix any cut it marks `<-- check` (its header says how), and put `"lock": true` on bites you place by hand. It's safe to re-run: it only touches bites whose times changed, and never makes a cut louder.
   Then **tighten**: `python3 $S/scripts/tighten.py plan.json`. It writes each bite's `pieces` (what actually plays): your `cut` ranges, silences over `max_pause` and isolated fillers removed, every edge on a quiet point. A `cut` edge only ever moves outward (by up to 70 ms), never into the cut, so put each edge on the outer boundary of the words to remove. A bite's end that is still in speech (even on a locked bite) is moved on to where the last word stops, plus 50 ms, when that's within 0.4 s; it prints `end X -> Y`, so check no next word came in. The same happens when the end sits in a pause just before the sentence's last word (Whisper's word runs on past the end: "a very simple ... reason."). Read what it prints per bite; veto a removal with `keep`, and fix any `<-- check`. Safe to re-run; run it again after any change to start/end, `parts` or `cut` (the other scripts stop until you do).
6. **Sound**:
   1. `python3 $S/scripts/audio.py plan.json` writes the dialogue track, `audio_mix.wav`.
   2. **Required loop: hear every stumble.** `python3 $S/scripts/check_audio.py plan.json` transcribes the trailer's own audio close to verbatim (the episode's transcript drops most "um"s, "uh"s and repeated words, so tighten.py can't see them) and prints what is heard in each bite (joins show as ` / `), then flags every `filler` (um, uh, a filler "like,"), `repeat` ("the the", "to, to", "and I, and I"), `extra` word (not in what the bite should play: a stray word from the other speaker) and `missing` word (a clipped first or last word), each with its trailer and source time. For each one you mean to remove, find its exact edges with `python3 $S/scripts/edge.py original.mp4 SOURCE_SECONDS` (it re-transcribes 2 s around that point with exact word times), add a `cut` over it, and re-run `tighten.py`, `audio.py` and `check_audio.py`. Repeat until nothing is flagged that you mean to remove; say in the delivery note which flags you left and why (a repeat that is emphasis, a name Whisper spells its own way). Removing a filler or a stumble never changes the meaning. Never leave a `missing` word on the last line.
   3. Put `boom`, `whoosh` and `riser` on the bites that turn the story (`reference/editorial.md`, Sound), then run `python3 $S/scripts/sfx.py plan.json`. It fetches each sound from HyperFrames' sound library (HeyGen's full library if the person is signed in, otherwise HyperFrames' free built-in effects), lines it up on the cut and sets its level so nothing clips.
7. **Finish in HyperFrames.** First check the captions without rendering: `python3 $S/scripts/captions.py plan.json`. Then:
   1. `python3 $S/scripts/hyperframes.py plan.json hf/` builds the project: one clip per bite, the dialogue, each sound effect as its own clip, and the captions.
   2. `cd hf && hyperframes check`
   3. `hyperframes render -w 4 -o ../trailer.mp4`
   The person can open it with `hyperframes preview` in `hf/`:
   - Caption look (fonts, sizes, colours, timing) and words: `compositions/captions.html`, `<style id="caption-style">`.
   - Sound effects: drag, swap or re-level them on the timeline.
   - Bite order or length: change `plan.json` and re-run `hyperframes.py`. Caption times don't follow a bite that's dragged in the Studio.
   `hyperframes doctor` says what's missing if a command fails.
   - **Fallback, only if setup printed `HYPERFRAMES NOT READY`:** `python3 $S/scripts/audio.py plan.json --sfx` (mixes the sound effects in), then `python3 $S/scripts/render.py plan.json trailer.mp4`. For 9:16, set `"aspect": "9:16"` and run `track.py plan.json` first. The picture is the same, but the person gets no project to edit, so tell them why HyperFrames didn't run.
8. **Review before sharing**: `python3 $S/scripts/review.py trailer.mp4 plan.json`. It makes a time-labelled sheet and prints the captions exactly as they appear on screen. Look at the sheet, and at 5+ full-size frames (the sheet catches words mid-animation). Check that:
   - it opens on the strongest line, and with a main guest the guest's share (printed by `review.py`) is at least 50%, spread through the trailer
   - everyone who speaks twice is introduced by name: `review.py` flags anyone without an intro bite, or whose name was cut out of it
   - captions never cover a face: `review.py` checks every caption block against the faces under it (punch-ins included) and saves any it flags as `trailer_faces.jpg`. This is very important; fix every one. On 9:16 or zoomed bites it can't check, so look yourself. Also keep captions off anything the viewer needs to see (a product, a screen, a sign).
   - where each block went: `review.py` prints `right`, `left`, `between`, `bottom`, `sub` (no face) or `bottom!` (nothing fit, shown as a small subtitle) per block and flags the bottom ones. A few is fine; many means the shots are tight close-ups (try `cap_pos`, fewer words, or other bites)
   - host lines are yellow (`host` is set) and nearly every guest block has a coloured word
   - the running order reads as one conversation
   - every bite starts and ends on a complete sentence, except the last and a tease cut before its reveal (`review.py` marks the rest `<-- ends mid-sentence?`)
   - every stitched or cut bite keeps its meaning: `review.py` prints `original` next to what plays, and flags any without one
   - the pace: `review.py` prints words per second (DOAC 3.2-4.1), how much of the time someone is speaking (~98%), and the 5 longest silences; fix any it flags over 0.35 s
   - the last line is left unanswered
   - the length is 75-110 s, with 17-30 bites
   Fix the plan and re-run steps 5-7 until it passes.
9. **Deliver**:
   - the mp4
   - `hf/` zipped, so the person can open and tweak it: unzip, then `npx hyperframes preview` inside it
   - a short note with a table: each bite's role, speaker, source timestamp and line. Also say what you left out and why, and list any words Whisper was unsure of (`p` under ~0.5) for the person to check by ear.
   If `sfx.py` said it used the built-in effects, end the note with: "Want more sound effects to pick from? Sign in to HeyGen with `npx hyperframes auth login` and I'll search its full sound library next time."

## When the person gives feedback
Change the plan, not the scripts.

| Feedback | Change |
|----------|--------|
| "Too long" | Cut the weakest bite that isn't the hook, the guest sell or the cliffhanger. |
| "Bad opening" | Pick a new hook from the candidate list. Never open with an answer that kills the tension. |
| "Stay on the topic" | Drop every bite that fails the on-topic test. |
| Caption wording | Use `fix`, `drop` or `big`. |
| Highlights / colours | Use `accent` with a colour per word (`{"not": "red"}`). Host lines yellow: set `host` to the host's speaker label. |
| Caption in the wrong place | `cap_pos` on that bite: `left`, `right`, `between` or `bottom`. |
| Framing | Use `aspect` or per-bite `zoom`. |
| Sound effects | Move `boom` / `whoosh` / `riser` to other bites, or change what's searched for with `sounds`. Re-run from step 6.3. |
| "Too slow" / pauses | Lower `max_pause` (e.g. 0.15), `cut` lead-ins and asides, stitch long answers down with `parts`. Re-run from step 5 (snap, then tighten). |
| "A stumble is still in" | Run `check_audio.py`: it flags fillers and repeats with their source times. Add a `cut` over each (`edge.py` for exact times), re-run `tighten.py`, `audio.py`, `check_audio.py`. |
| "Something important got cut" | Add a `keep` range over it (or `keep_pauses` for a deliberate pause), re-run `tighten.py`. |
| "The zoom jumps are distracting" | `punch: false` on that bite, or a smaller `punch_scale`. |
| Caption over a face | `cap_pos` to the other side or `bottom`, fewer words per block (`gap`, `drop`), or a different bite. |

Re-run from step 5 (snap, then tighten).
