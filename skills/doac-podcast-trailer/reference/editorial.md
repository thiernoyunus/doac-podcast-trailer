# Picking the story

This is the part that makes or breaks the trailer. The scripts only cut what you choose.
It is written from 25 real DOAC trailers traced line by line back to their full episodes (`research/`), from our best approved cut (a 91 s e-commerce episode, v3), from what went wrong in the cuts before it, and from DOAC's lead trailer editor.

## 1. Read the episode before choosing anything
Read all of `transcript.txt`, in chunks, start to finish. The last quarter matters: real trailers draw lines from it in nearly every case, and the closing lines often come from there. Then write these down, with timestamps:
- **The one topic.** What is this episode actually about? Say it in five words, as if it were the YouTube title. Every bite you pick will be about this. (In v3 it was "Is e-commerce a real asset class?", not "investing" or "business".)
- **What the audience argues about.** List the topics the show's viewers already debate in comment sections and at dinner (for a Muslim audience: a group or school of thought, mortgages, student loans, "is it really halal?"), and where the guest takes a side on them. These are the trailer, not the risk to steer around. A sensitive line is a reason to include it; make it honest instead of leaving it out: keep the guest's own softeners ("the majority", "so-called", "with all due respect"), and when a ruling comes with conditions, tease it (the question, the guest starting to answer, cut before the verdict) rather than play a shortened verdict. Open on what a general viewer cares about, not an insider line: "never call yourself a scholar" speaks to scholars; "say yes or no: can I mortgage my house?" speaks to everyone.
- **Who is who.** The host, the guest(s), any co-hosts, and what makes each worth listening to: exits, money managed, years, famous clients. The transcript has no speaker names. For each voice:
  1. Find a line where the transcript makes the speaker obvious ("Today I have brother X…", "Sam, you…").
  2. Run `frames.py original.mp4 who.jpg --burst MM:SS …` there, and see whose mouth and hands move across the three frames.
  3. Note what they look like (clothes, glasses, seat, camera) so you can recognise them at other timestamps.
  People are often never named, or two share a name. Label them by role ("the host", "the construction partner") and never guess a name.
- **What kind of episode it is.** This decides whose voice carries the trailer. Look at who the title or thumbnail names, who the host introduces as the guest ("Today I have…"), and who gets asked most of the questions.
  - **Guest episode:** one person is brought in as the expert, and the conversation is about what they know. The trailer is **guest-led** (see below). Co-hosts do the host's job.
  - **Guest plus panel:** one main guest, plus regulars or panelists who also talk. Still guest-led: the main guest has 50%+. Panelists are supporting voices. Keep one only if they add friction or a strong line, and introduce each one you keep.
  - **Panel:** a group discusses a topic and nobody is the main expert. No one has to have 50%. Share the trailer between the two to four strongest voices, and introduce each one.
  If you can't tell, it's a panel. Write down which it is, and each person's name as spoken (or a role label if never named), before listing candidates.
- **The style.** News, exposé or conspiracy (spying, war, AI danger) or personal growth (habits, emotions, relationships)? It sets the pace (section 2).
- **The premise** and **the central question** the episode keeps coming back to. The title's promise is usually both.
- **Specific numbers**, such as "$10,000 a month", "15 years in the CIA", "three exits". Specific numbers feel true.
- **Friction.** Pushback, disagreement, hard questions, the host challenging the guest.
- **Stakes and admissions.** Risks, failures, personal stories, anything said for the first time.
- **Open questions and reveals.** Lines that ask something important, or start to reveal something, where the answer comes later. These are your tease and ending candidates.
- **Objects.** A photo, a box, a letter, cards on the table: things you can mention without showing.
- **What to skip.** Sponsor reads and ads (often shot elsewhere, sometimes with their own burned-in captions), the intro/outro housekeeping, and quotes of other famous people's opinions.

Then list 40-60 candidate pieces in `candidates.md` (a trailer uses 25-45 separate source pieces), with timestamps, a role and the speaker for each. Include half-sentences you may stitch. In a guest episode, most candidates should be the guest's own lines. Use `words.py transcript.json --find "phrase"` to jump to a line.

## 2. Build the arc
**Size and pace.** 75-110 s, 17-30 bites. Real trailers run 67-124 s, most 90-110 s. A typical bite is 11-17 words, about 3.5-4 s. Guest bites run about 1.5-2 times as long as host bites. Speech runs at 3.2-4 words per second, and someone is speaking ~98% of the time: no air between lines. Length is the hard limit; the bite count follows from it.

**Rebuild the order.** Take lines from the whole episode, first 5% to the last quarter, and put them in the order the story needs. 37% of jumps between real trailer lines go backwards in the episode, and most jump more than 2 minutes. Keep late payoff moments (a letter, a confession, "the most remarkable thing of all") for the second half.

**Guest episodes are guest-led.** The guest is why people click. DOAC weights the guest at about 50% of what makes an episode work.
- The guest's voice fills **at least half the running time** (real trailers: 69-87% of the words), spread across the whole trailer.
- **The host speaks little: 15-30% of the words** (13-31% measured). Host lines are only questions, challenges, reactions ("This is the stuff of movies.") and the introduction. Never the host's own opinion.
- The guest owns the big moments: the opening claim, the moment of value, the proof, the stakes.
- A good rhythm is host question or pushback (short), guest answer (longer), host reaction or challenge, guest again.
- Check with `review.py`, which prints each speaker's share. If the guest is under 50%, swap host lines for guest lines that make the same point.

Role names are free labels: `hook`, `challenge`, `premise`, `frame`, `sell-guest`, `question`, `value`, `proof`, `tease`, `pushback`, `stakes`, `admission`, `cliffhanger`. They describe the job the bite does.

| Part | Time | What it does |
|------|------|--------------|
| **Hook** | 0-15 s | The single strongest line in the episode, usually the title's promise said out loud (5 of 5 in one set). Two shapes: **(a)** the guest's boldest claim, stated as fact (19 of 25 trailers): "Billions of dollars are spent spying on Americans"; **(b)** the host's big-stakes question, with the guest's answer landing within a few seconds: "How long does it take someone to spot a psychopath?" / "About 5 seconds." Never a greeting, never the guest's background. Pick it for punch, not position: openers came from anywhere between 2% and 93% into the episode. Write down 5+ candidates, rank them on surprise, specificity and the topic word. |
| **Back-and-forth** | 10-25 s | A challenge or reaction from the other side ("Can they do that with devices?"), and the guest pushing further. |
| **Sell the guest** | 20-45% in | Name and credential together, never first. Often built from real lines: the host's question ("the Mark Cuban that we've all grown to love from the Shark Tank…") or the guest's own words ("I spent 15 years in the CIA."). Everyone who speaks twice or carries the conflict needs this. Start the bite on "we have [name]…", never after the name. If a person is never named, a credential alone is fine (never guess a name). If there's no intro line for someone, give their bites to someone else or cut them. Mark each intro bite with `introduces`. |
| **Frame / question** | by ~40 s | The premise and the central question, out loud, so a stranger knows what the conversation is. |
| **Body** | ~40-85 s | One of two shapes. *Rising danger*: claim, proof, escalation (news / exposé). *Takeaways*: one or two useful ideas given away free, a rule or a framework (personal growth). Put pushback in either: the trailer needs friction. Hold one answer back here (section 4). |
| **Hard question** | last third | The host asks something personal or controversial: "Have you forgiven her?", "Do you think Jeffrey Epstein was a spy?" (5 of 5 in one set). A run of 3-6 short host questions here is common in news trailers. |
| **Ending** | last 2-6 s | Unresolved, always (25 of 25). Strongest shape: the host asks the central or most personal question, the guest *starts* to answer, cut to black mid-sentence: "So, first," / "So, in my lab, what we found is that" / "which is". Look for the guest's first words after each big question. |

**Two styles, by kind of guest.** Treat each trailer as a genre and cut to it:
- **News / exposé / conspiracy** (CIA, AI danger, war): the fastest and densest. Short bites, rising danger, a run of host questions near the end, and an ending on a hard question.
- **Personal growth** (habits, emotions): calmer. Longer guest bites, practical takeaways, then a turn to emotion and vulnerability, and a slow last ~20 s ("I've been at some of my lowest points…" → "What happened?").

## 3. Stitch and tighten
About half of real trailer bites (40-60%) are stitched from two or more moments, sometimes an hour apart. Nearly every bite is tightened. This is what makes 3.5 words per second possible.
- **`tighten.py` does the small stuff.** It removes pauses, "um"s and "you know"s. You choose the stitches and the cuts.
- **Cut** (`cut`: source ranges removed from inside a bite): the lead-in ("Walk me through…", "And now,"), stumbles and restarts ("see, for someone to use"), repeated words or phrases ("over and over and over again"), hedging detours that don't change the claim ("to tell you the truth"), side jokes, and the middle of a list (keep the three strongest items).
- **Open on the bombshell itself.** Cut throat-clearing and hedging lead-ins before the claim, like "I don't want to criticize, but" or "Yeah, and for the record,": the first word heard is the claim. Dropping a lead-in is fine; dropping a qualifier inside the claim ("the majority", "so-called", "with all due respect") is not.
- **Stitch** (`parts`: source ranges played back to back as one line, in place of `start`/`end`): join two halves of one thought said minutes apart, or put a story's sentences in a stronger order. A short joining word ("And", "But", "which is why") can bridge only if that speaker says it in the episode; take it from their real audio.
- **`original`** is required on every bite with `parts` or `cut`: the sentence(s) exactly as said, with the source times. It is how the honesty test is checked.
- **`keep_pauses: true`** on the one bite whose pause is deliberate: 0.3-0.8 s just before the last line. DOAC uses 1-3 such pauses per trailer, before the last line or a big reveal; none anywhere else.
- You can only use what's in the episode. 7-16% of real trailer lines aren't in the published audio at all (likely pickups: "So, let's talk about that.", "And I'll tell you how we know."). Find a real line that does the same job.

```json
{"role": "proof", "speaker": "Guest", "start": 1034.2, "end": 1056.4,
 "cut": [[1035.4, 1036.3], [1037.4, 1038.2], [1039.7, 1042.7], [1044.2, 1051.6]],
 "original": "because my colleagues, my superiors at the CIA kept repeating this lie over and over and over again that torture worked. And that torture got us information that saved American lives. And that was just simply not true. It was a lie. Besides being illegal, immoral, unethical. It just wasn't true.",
 "why": "Why he blew the whistle: 22 s of speech down to about 8"}
```
Plays: "because my superiors kept repeating that torture worked. Besides being illegal, immoral, unethical. It just wasn't true." Shorter, same meaning. (Times here are caption word starts, about ±0.3 s; in a real plan place every edge with `words.py`.)

## 4. Teases
- **Hold an answer back mid-trailer.** Cut right before the reveal: "It had to do with—", "the worst question in the history of conversations is". 4 of 5 trailers do it in two separate sets.
- **Mention an object without showing it**: "I've got some wonderful photos here", the box, six handwritten cards.
- At most two or three per trailer, and the episode must pay off every one (check the timestamp where it does). A bet or object that's never resolved is clickbait.

## 5. Tests every bite must pass
- **Honest.** Read `original` against what plays. A stitch may shorten a line, never change its meaning. Real trailers break this; we don't (the owner is explicit: no clickbait). Fail it if:
  - **A question gets someone else's answer.** "So you're saying aliens are real?" was played over "I think it would be insane that there is no one visiting", from 4 minutes later. The real answer was "No." A question keeps its real answer.
  - **A line moves to another subject.** "decided to get into a recreational war" was said about the last tsar, and the trailer put it after "Donald Trump". The host's "This is the stuff of movies" was about the pager operation, and was placed after a disease-experiment claim.
  - **A content word is swapped or inserted.** "Protocol number one is hydrate" became "protocol number one, you want to get sunlight". "I'm not optimistic about the present" became "…about the next year".
  - **A hedge that changes the claim is deleted.** "may become the eight most dangerous weeks" → "the eight most dangerous weeks"; "something approaching 100%" → "100%"; a story "reported to him" played as the guest's own claim. Fillers and "to tell you the truth" can go; "may", "potentially", "I don't think", names and numbers stay.
  - **List structure is invented.** "First", "Second thing" or "Number one" that wasn't said about these items (one trailer turned "Second, non-verbal cues" into "So, first thing is non-verbal cues").
- **On topic.** Is it about the one topic? A great line about something else still gets cut. v2 lost points because it drifted into general investing talk.
- **Complete sentence.** Every bite except the last starts where a sentence starts ("And…" or "But…" is fine) and ends after its last word. For a stitched bite this applies to what plays, not to each part. Two exceptions: the last bite, which may stop mid-sentence, and a tease cut right before its reveal.
- **Stands alone from its first word.** Cut lead-ins that point back to something the viewer never heard: "What I mean by that is…", "Like I said…", "So basically…". Start on the claim itself ("AI is not going to…"). Check each edge with `words.py transcript.json START-END`.
- **Justified.** You can write its `why` in one line. If you can't, cut it.
- **Bridges.** Read the running order out loud as a script. Each line should follow from the one before, like one conversation. If it jumps, reorder, or add a short real bridge line (a question, a "but").
- **Guest share.** In a guest episode, is the guest speaking for at least half the running time, in more than one place?
- **Doesn't answer its own cliffhanger.** No later bite may resolve the last question.

## 6. Mistakes we've already made
- **Opening with an answer that kills the tension.** An earlier cut opened with "No, your investment can't go to zero". The same question worked as the last line, left unanswered. (A host question answered in seconds is fine when the answer makes you want more: "About 5 seconds.")
- **Topic drift.** Twelve great lines on five topics feel like a highlight reel, not a trailer.
- **No context.** Without the premise, viewers don't know why the argument matters.
- **Playing it safe.** An Islamic-finance cut opened on "Do not ever call yourself a scholar" and left out the guest's remarks on Salafis, the student-loan ruling and "say yes or no" on mortgages. The owner's verdict: it missed the point of a trailer. The debated topics are the trailer.
- **Two speakers in one bite.** The transcript has no speaker labels, and a host question often runs straight into the guest's answer in one transcript line. Check each bite's first and last words against `frames.py --burst`, and split it where the voice changes.
- **Unknown guests.** If nobody says who they are, their claims carry no weight.
- **A name cut off the intro.** A panel test introduced three people but only one by name: two intro bites started a line after the host said the name ("And Hormozi was impressed…" instead of "Across me we have Murad, who…"). Keep the name in the bite and fix its spelling.
- **The guest barely speaks.** One test cut gave the guest one moment and the host seven bites. In a guest episode the guest's ideas are the product.
- **Too slow and too few bites.** Our old cuts used 12-16 whole sentences with their pauses kept. DOAC trailers use 17-30 tightened, often stitched bites at 3.5 words per second.
- **Zoom and crop on a two-shot podcast.** People want both faces in view. Keep the full frame in 16:9, exactly as each camera shot it.
- **Trusting Whisper's word times at an edge.** Filler words are sometimes stretched over a second, so a cut placed from `words.py` can clip the next word. `check_audio.py` catches this. Re-transcribe a 2 s clip around the cut with `edge.py`, place the edge by hand, and add `"lock": true`.
- **A setup the episode never resolves.** A bet or challenge that is never settled ("let's make a bet, your system against my team") is clickbait as a cliffhanger.
- **Cuts in the middle of speech.** Run `snap.py` and fix any cut it flags.
- **Stray words from the other speaker** at a bite's edge showing up in captions. Use `cap_start`/`cap_end` or `drop`.

## 7. Captions
- **Where:** a block sits beside the speaker's head, at head-to-shoulder height, on the side with more room, never over the face. Two people in shot: in the gap between them. No room or no face: a small subtitle at the bottom. The scripts pick this; override per bite with `cap_pos`.
- **Who:** host lines are yellow, guest lines white (set `host`). That's how DOAC shows who's asking.
- **Shape:** 3-8 words, stacked, with one huge hero word: the number, the topic word, or the emotional word (`big`). Soft words ("love", "purpose") come out in italic serif.
- **Colour a word in most guest blocks.** DOAC trailers do: red "HATE", green "RESULTS", a red box behind "replaced". Pick the colour by what the word means:
  - **red**: danger, loss, negatives, pushback ("not", "wasting", "lose", "never")
  - **green**: money, results, wins, the positive answer ("money", "selling", "80%", "solutions")
  - **pink**: love, family, heart
  - **box** (white on a red box): the two or three strongest words in the whole trailer, usually the hook, the guest's credential and the stakes
  - **yellow** is the host's colour, so use it on a guest word only for a name or number that needs it.
- The coloured word can be any word, not only the hero: a small "not" in red is very DOAC. One colour per block; leave a quiet setup line white so colour keeps meaning something.
- Set colours with `accent`, e.g. `{"not": "red", "money": "box"}`. Guest blocks you don't set get red, green or pink on a word whose meaning fits, else stay white. Choose them yourself.
- Fix the transcript's mistakes with `fix`: names, brand words, and missing question marks.

## 8. Sound
- Sound effects come from HyperFrames' sound library (HeyGen's full library when signed in), never synthesized. Less is more: each one marks a turn.
- `boom` on 2-4 turning points (the hook, the guest reveal, the stakes).
- `whoosh` on a cut that changes scene or mood (one or two per trailer).
- `riser` into the one biggest turn, usually the stakes or the cliffhanger. At most one.
- No music by default: the dialogue carries the trailer. Only set `music` if the person gives you a licensed track.

## From DOAC's lead trailer editor
- Every element must be justified. If it's only there to look cool, cut it.
- Respect the audience: the episode must pay off the hook. No clickbait.
- The hook can be slow and long (20-40 s including the back-and-forth), but the strongest line still comes first and the introduction follows it.
- Treat each trailer as a genre (thriller, rom-com, conspiracy) and cut to it (section 2, two styles).
- Structure: A (rise) → B (conflict) → C (cliffhanger), cut just before C resolves.
- Reactions work like a laugh track: the host's shock gives the viewer permission to feel it.
- "Perfect imperfection": a focus pull (`focus_pull`) on one or two bites makes it feel raw.
- Specific numbers and exclusives ("I've never told anyone this") pull people in.
- Take the hook from the title or thumbnail that will get the click: the trailer opens by saying that same promise out loud.
- Open on the guest in the chair, never on b-roll. DOAC tested openings on b-roll and they lost viewers.
- With a famous guest, skip the fame and success talk: viewers switch off. Use what they know, not how big they are.
- The length is a guide, not a wall: a strong story may run past 110 s (DOAC has gone to 2:17). Never pad to reach 75 s.
- Credentials can be folded into the hook itself (the host's question names who the guest is) instead of a separate intro.
