# The plan file (plan.json)

The plan is the whole edit. Both finishing paths read it: `render.py` (Python) and `hyperframes.py` (HyperFrames).
Editorial choices live here and nowhere else, so changing the trailer means editing this file and re-rendering.

```jsonc
{
  "source": "original.mp4",          // relative to the plan file, or absolute
  "transcript": "transcript.json",   // from transcribe.py
  "aspect": "16:9",                  // "16:9" (full two-shot, default) or "9:16" (speaker crop, run track.py)
  "topic": "e-commerce as an asset class",   // the one thing this episode is about (for you, not the renderer)
  "genre": "interrogation / thriller",
  "host": "Steven",                 // optional: the host's speaker label; their caption lines are yellow, everyone else white
  "guest": "Jamal",                  // the main guest (guest episodes and guest plus panel): exactly the label used in the bites' "speaker"; review.py checks their share
  "names": {"Book buyer": "Abu Malik"},   // optional: the name as spoken, for a speaker label that isn't their name (review.py looks for it in the intro)
  "music": "track.mp3",              // optional licensed track, laid quietly under the dialogue; no key = no music
  "music_db": -24,
  "sounds": {"boom": {"heygen": "deep trailer boom"}},   // optional: what sfx.py searches for, or {"boom": "my-boom.wav"}
  "colors": {"red": [237, 41, 57]},   // optional: retune a highlight colour (red, yellow, green, pink, gold, box)
  "max_pause": 0.2,                  // optional: tighten.py shortens every silence longer than this to 0.1 s
  "punch_scale": 1.12,               // optional: how far a punch-in piece zooms (1.1-1.3)
  "bites": [ { ... }, ... ]          // in trailer order
}
```

## Bite keys

| Key | Required | Meaning |
|-----|----------|---------|
| `id` | no | Label shown in logs (defaults to 1, 2, 3...) |
| `role` | yes | Its job in the story: `hook`, `challenge`, `premise`, `sell-guest`, `value`, `pushback`, `stakes`, `admission`, `cliffhanger`... |
| `speaker` | yes | Who is talking. Use one short label per person, identical on every bite, so `review.py` can add up each person's share. Use their name when it's said ("Murad"), else a role ("Host", "Book buyer"). Put descriptions in `notes`, not here |
| `start`, `end` | yes, or `parts` | Source seconds. Start at a sentence start, end after its last word (except the last bite and a tease, which may stop mid-sentence). `snap.py` refines both |
| `parts` | no | `[[start, end], ...]` instead of `start`/`end`: source ranges from anywhere in the episode, in any order, played back to back as one line (a stitch). `tighten.py` snaps each edge. Still one bite |
| `cut` | no | `[[start, end], ...]` source ranges removed from inside the bite: a stumble, a repeated word, a filler, a lead-in, an aside. `tighten.py` may move each edge up to 70 ms outward to a quieter point, never inward, so every word inside the range stays removed. Put the edges on the outer boundaries of the words to remove (`words.py`, or `edge.py` for exact times) |
| `original` | with `parts` or `cut` | The sentence(s) exactly as said in the episode. `review.py` prints it next to what plays and flags a stitched or cut bite without one. A stitch may shorten a line, never change its meaning |
| `keep_pauses` | no | `true`: `tighten.py` leaves this bite's pauses alone. For the one deliberate pause before the last line |
| `keep` | no | `[[start, end], ...]` source ranges `tighten.py` must not remove from (veto a filler or pause it printed) |
| `punch` | no | `false`: no punch-in on this bite's joins |
| `pieces` | written by `tighten.py` | The kept source spans, played back to back. Never write it by hand: change `start`/`end`, `parts`, `cut`, `keep` or the plan's `max_pause` and re-run `tighten.py`. The other scripts stop if it is stale |
| `why` | yes | One line: what this bite does for the viewer. If you can't write it, cut the bite |
| `cap_start`, `cap_end` | no | Only caption words spoken inside this window (default: the bite). Use to drop a stray word from the other speaker at an edge |
| `drop` | no | Words to leave out of the captions (e.g. a greeting, a name the transcript mangles) |
| `drop_times` | no | Leave out the word starting at these source times (for one repeated word, "I I"). Not needed for a word clipped at a cut: one that starts in the last 0.15 s before a cut and ends after it is left out automatically |
| `fix` | no | `{"heard": "correct"}` whole-word caption fixes. Keys match with punctuation ignored (`"fajr."`, `"Fajr"` and `"fajr"` all match "fajr,"). The word keeps its own ending punctuation unless the fix brings its own, which replaces it: `{"that": "that?"}` on "that." gives "that?", never "that?.". Changes every copy of that word in the bite. A key that matches no caption word prints a `WARNING` (often: the word was cut, dropped, or is spelled differently in the transcript) |
| `introduces` | no | On an intro bite: the `speaker` label of the person it introduces (`"Murad"`). `review.py` checks that everyone who speaks twice has one, and that their name is in it |
| `fix_times` | no | `{"1085.42": "helped"}` replaces just the one word that starts nearest that source time (within 0.03 s; only that word, even when Whisper's words are closer together). Punctuation works as in `fix`. The value may be several words (`"It became"`); they show as one caption word. No word that close prints a `WARNING` |
| `auto_big` | no | `false`: blocks in this bite with none of your `big` words get no huge word (instead of an automatic pick) |
| `lock` | no | `true`: `snap.py` leaves this bite's start/end alone, and `tighten.py` uses `parts`/`cut` edges exactly as written (use after placing a cut by hand). Pauses and fillers are still removed, and a final end that lands inside the last word still moves on to the next quiet point within 0.4 s, plus 0.05 s (that tail can catch the start of the next word: listen). With no quiet point in 0.4 s the end stays as written and is printed with `<-- check`. An end in a pause just before the sentence's last word moves on to play that word too (printed, so you can check) |
| `big` | no | The hero word of a block, shown huge (heavy caps; a soft word like "love" or "purpose" gets italic serif instead). One per block: a number, the topic word, the emotional word. If missing, the first 4+ letter non-filler word is picked |
| `cap_pos` | no | Where this bite's captions go: `left` / `right` (beside the head), `between` (gap between two people), `bottom`. Default: picked from the faces in shot. Ignored on 9:16 (always the bottom) |
| `accent` | no | Coloured words, any role: `{"not": "red", "money": "box"}`. Colours: `red`, `yellow`, `green`, `pink`, `gold`, `box` (white word on a red box). A list (`["money"]`) picks each colour by meaning (yellow if none fits). Works on host lines too (see editorial.md, Captions) |
| `auto_accent` | no | `false`: guest blocks with no `accent` word stay white (otherwise a red, green or pink word by meaning is coloured, if there is one). Host blocks never get an automatic colour |
| `gap` | no | Pause (seconds) that starts a new caption block (default 0.5). Raise it if a slow speaker's lines get split |
| `fade_in`, `fade_out` | no | Edge fade in seconds (default 0.025). Use 0.08-0.12 when another voice starts right on top of the last word |
| `boom` | no | `true`: a deep impact that hits on the bite's first frame. Use on 2-4 turns (the hook, the guest reveal, the stakes) |
| `whoosh` | no | `true`: a whoosh that peaks on the cut into this bite. For a change of scene or mood, one or two per trailer |
| `riser` | no | Seconds (or `true` = 2.5): a build that starts that long before this bite and peaks on its first frame. At most one, into the biggest turn |
| `focus_pull` | no | Seconds of blur-to-sharp at the bite start ("perfect imperfection"). 0.4-0.6 on one or two bites |
| `zoom` | no | `[1.0, 1.06]` slow push-in on this bite. Off by default. Don't use unless asked: people want both faces in shot |
| `cx`, `cy` | 9:16 only | Where the speaker sits (0-1). `track.py` fills in `track` from this |

Preview the captions without rendering: `python3 scripts/captions.py plan.json` prints every block, with BIG words in caps and each coloured word followed by its colour, like `[MONEY]<box>`.

Sounds come from HyperFrames' sound library (`sfx.py`): HeyGen's library when signed in, otherwise HyperFrames' bundled free effects. `sounds` changes what is searched for per kind (`heygen` search words, `bundled` file name), or points a kind at your own file.

## Stitched and tightened bites

```jsonc
{"id": "7", "role": "value", "speaker": "Guest",
 "parts": [[1312.40, 1315.10], [1388.05, 1391.60]],   // the start of one answer + its point, 73 s later
 "cut": [[1313.20, 1313.65]],                         // "I I": a stumble
 "original": "So what I tell people is, I I always say start with the customer. [...] Start with the customer, and the product comes after.",
 "why": "the one rule, in one breath"}
```
`tighten.py` turns that into `pieces` (the stumble, pauses over `max_pause` and isolated fillers gone) and prints what it
removed. Everything after it plays the pieces back to back as one line: one dialogue stretch with 10 ms fades at each join,
one clip per piece, captions that flow across the joins, sound effects and speaker share once per bite.
Where a join removed more than 0.15 s or jumps elsewhere in the episode, the picture alternates between the full frame
and a centred punch-in (`punch_scale`), the way DOAC hides a jump cut. A caption block stays where it is across a punch-in unless the bigger face would cover it.

## Rules the scripts enforce for you
- Each caption block is placed once, from the faces in the frame as shown (punch-in included): one face → beside the head on the side with more room; two or more → the gap between them if it's wide enough, else a small subtitle at the bottom; no face → a small subtitle. 9:16 always goes at the bottom. `review.py` flags any caption that covers a face, except on 9:16 and `zoom` bites: it skips those, so check them by eye.
- `tighten.py` keeps someone talking: no silence inside a bite over `max_pause`, and `review.py` flags any silence over 0.35 s outside a `keep_pauses` bite.
- Every cut gets 25 ms fades (10 ms where two pieces of one bite meet), the dialogue is normalised to -14 LUFS, and each sound effect is levelled so dialogue plus effects never go above -1 dB.
- Music (only if you set `music`) drops out just before the last bite, and the video holds on black for 1.2 s after it.
