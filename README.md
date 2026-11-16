# DOAC Podcast Trailer

A Claude skill that turns a full podcast episode into a 60-95 second trailer in the style of *The Diary of a CEO*: a cold open on the guest's boldest claim, a quick back-and-forth, the guest introduced by name and credential, one useful idea given away, and a cliffhanger that cuts to black.

Give Claude an episode (a file, a YouTube link or a Google Drive link) and ask for a trailer. You get:

- `trailer.mp4`, 16:9 with the full two-shot, bold captions with coloured key words, and boom / whoosh / riser sound effects on the turns
- a [HyperFrames](https://github.com/heygen-com/hyperframes) project you can open and tweak yourself (captions, sound effects, timing)
- a short note listing every bite: its role, who speaks, the source timestamp and the line

Claude makes the editing choices (which lines, in what order). The scripts handle the mechanics: transcription, clean cuts on real pauses, sound levels, captions that stay off faces, rendering, and a final review.

## Install

### Claude Code (as a plugin)

```
/plugin marketplace add thiernoyunus/doac-podcast-trailer
/plugin install doac-podcast-trailer@doac-podcast-trailer
```

### Claude Code (copy the folder)

```bash
git clone https://github.com/thiernoyunus/doac-podcast-trailer
cp -r doac-podcast-trailer/skills/doac-podcast-trailer ~/.claude/skills/
```

Use `.claude/skills/` inside a project instead of `~/.claude/skills/` to install it for that project only.

### Claude.ai / Claude desktop app

1. Download [`dist/doac-podcast-trailer.zip`](dist/doac-podcast-trailer.zip).
2. Go to **Settings > Capabilities > Skills** and upload the zip.

Code execution needs to be turned on, since the skill runs Python and Node.

## Use

Ask something like:

> Make a trailer from this episode: https://youtube.com/watch?v=...

The first run installs what it needs (faster-whisper, OpenCV, ffmpeg, Node 22, HyperFrames, a headless Chrome) without asking. Transcription takes about a quarter of the episode's length, and rendering takes a few minutes.

To change the result, just say what you want: "too long", "open on a different line", "colour the word *money* red", "move the boom". Claude edits the plan and re-renders.

## Requirements

- Python 3.10+ and `pip`
- Internet access to download the episode and the tools on first run
- Optional: a HeyGen sign-in (`npx hyperframes auth login`) for HeyGen's full sound library. Without it the skill uses HyperFrames' free built-in effects.

## What's inside

```
skills/doac-podcast-trailer/
  SKILL.md                  the steps Claude follows
  reference/editorial.md    story rules: hook, guest sell, arc, cliffhanger, sound
  reference/examples.md     two approved trailers, bite by bite
  reference/plan-format.md  the plan.json format every script reads
  scripts/                  transcribe, snap cuts, audio, sound effects, captions,
                            HyperFrames build, fallback renderer, review
```

## Note

This is an independent fan-made tool that imitates an editing style. It isn't affiliated with or endorsed by *The Diary of a CEO* or Steven Bartlett. Only cut trailers from episodes you have the right to use.

## License

MIT
