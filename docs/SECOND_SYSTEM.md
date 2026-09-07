# The second system: topic → finished video

You give three things — **topic, duration, notes** — and everything except the
Flow clicks happens on its own.

```bash
python tools/make_video.py new --topic solar-payback --duration 120 \
    --notes "UK angle, sceptical tone, mention time-of-use tariffs"
```

That prints your budget: for 120 s it's 13 shots, ~272 words, ~8 s per shot.

## The six commands

| Command | Does |
|---|---|
| `new` | scaffolds the video, computes the shot and word budget from your duration |
| `check` | validates the script *against that budget* and says how many words to add or cut |
| `flow` | prints the two Flow prompts, generated from `presenter.json` |
| `watch` | waits for `hook.mp4` / `close.mp4` to appear, then runs everything after |
| `run` | same as `watch` but doesn't wait — use it when the clips are already there |
| `status` | which steps are done |

Every step records itself in `state.json`, so a failure resumes where it
stopped rather than starting over. `--force` redoes completed steps.

## What "automated" actually means here

Flow has **no public API**. Veo 3.1 is available programmatically through the
Gemini API and Vertex AI, but that's a separate paid product — your Google AI
Pro credits don't apply to it. So the honest split is:

- **Manual (~10 min):** paste two prompts into Flow, click Approve, download
  two clips into `videos/<topic>/flow/`.
- **Automatic (everything else):** clip cleanup, voice reference, GPU voice
  clone, tonal match, body render, stitch, verification, upload notes.

`watch` sits on the folder, so the moment you save the second clip the rest
runs unattended. In practice you paste, click, and walk away.

## Duration targeting

The planner uses the same pacing maths as the renderer, so its estimate and the
real render agree to within a fraction of a second. `check` refuses to bless a
script that lands outside ±10% of your target and tells you exactly how many
words to move:

```
  target        60s
  estimated     58s  (-2s, -4%)
  shots         6 (budget 6)
  words         108 (budget 115)
  status        ON TARGET
```

## The presenter

`presenter.json` at the repo root defines Maya once — appearance, wardrobe,
room, camera, lighting, delivery. Every video's Flow prompts are generated from
it, which is what stops the room drifting between videos. Edit it once; attach
your own Flow character so the face stays stable.

## Titles and keywords (vidIQ)

vidIQ is an MCP tool available to Claude in a session — a local Python script
can't call it. So the SEO step works like this:

1. Ask Claude in a session to run the vidIQ step for a topic.
2. Claude writes `videos/<topic>/seo.json`.
3. `make_video.py` renders `out/upload.md` from it — scored titles, keywords,
   description, tags, plus the asset credits and the pre-publish checklist.

**Budget:** the free plan gives 150 credits a month. Title generation costs 5
and keyword research costs 5, so about **10 credits per video → ~15 videos a
month**. Ask for keyword research *before* the script is written: on the demo
topic it showed "home battery payback" had almost no search volume while
"solar payback" scored 66.8, which is the kind of thing worth knowing before
spending 40 Flow credits.

Note: no YouTube channel is currently authorized in vidIQ (it reports zero
channels for `onlinemoneyrcc@gmail.com`). Authorizing one makes title scoring
channel-aware and unlocks the analytics tools.

## seo.json format

```json
{
  "titles":   [{"title": "...", "score": 90}],
  "keywords": [{"keyword": "...", "overall": 66.8, "volume": 55.4, "competition": 16.2}],
  "description": "...",
  "tags": ["..."]
}
```

## A full run

```bash
python tools/make_video.py new   --topic solar-payback --duration 120 --notes "..."
# Claude writes the script into videos/solar-payback/body/build_body.py
python tools/make_video.py check --topic solar-payback
python tools/make_video.py flow  --topic solar-payback     # paste into Flow
python tools/make_video.py watch --topic solar-payback     # walk away
```

About 30 minutes wall-clock, ~40 Flow credits, ~8 GPU-minutes of your free
Kaggle quota, and ~10 vidIQ credits.
