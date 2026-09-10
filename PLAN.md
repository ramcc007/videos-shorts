# PLAN

Running notes for the explainer-video pipeline. Updated after every step.

## Standing rules — never break these

1. **The presenter comes from Google Flow only.** Veo 3.1 Fast, never Veo
   Quality. Retry a bad clip **once** at most.
2. **No open-weight talking heads.** SadTalker, Wav2Lip and every other
   still-image lip-sync model were tried and rejected as visibly fake, at both
   full-screen and corner size. An animated 2D mascot was rejected as
   cartoonish. This is settled — do not re-propose either.
3. **Flow's confirm-before-generating stays on "Always".** Click Approve each
   time. Never "Always approve".
4. **Never upload a real person's photo or voice to Kaggle.** The voice
   reference is synthetic speech from Flow, and nothing else.
5. **Only CC0, CC BY or public-domain assets**, and keep the credit lines.
   `out/CREDITS.md` is generated on every render — ship it.
6. **All on-screen text in English.**
7. **Every YouTube upload gets the synthetic-content disclosure ticked.**
8. **Never print API keys or tokens** into chat, a file in the project, or a
   commit. `config.json` holds a username and nothing else.

## Where things stand

| Piece | State | Proven by |
|---|---|---|
| `tools/kaggle_run.py` | built | CLI + auth/username guards exercised; **not yet run against a live Kaggle account** |
| `kaggle/make_smoke_nb.py` | built | generates a valid notebook; every cell compiles |
| `kaggle/make_voice_nb.py` | built | generates a valid notebook; every cell compiles |
| `studio/` render engine | **working** | 8-shot, 60 s body rendered end to end |
| all 7 shot kinds | **working** | rendered and inspected; caption safe-area verified |
| `tools/fix_clip.py` | **working** | 720p30 → 1080p25, de-logo, 200 frames exact |
| `tools/cut_voice_ref.py` | built | not yet run on real Flow clips |
| `tools/match_eq.py` | **working** | band mismatch 2.31 dB → 0.60 dB on a test pair, capped at 3 dB |
| `tools/stitch.py` | **working** | 200 + 1502 + 200 = 1902 frames, exact |
| `tools/review.py` | **working** | joins, per-segment EBU R128, frame count |
| Wikimedia photo fetch | built, **untested live** | licence filter unit-tested; Commons was blocked by the build sandbox's egress policy |

## Build order and what each step proved

1. **`studio/theme.py` + `draw.py`** — all seven shot kinds drawn with Pillow
   on a navy gradient, hand-placed coordinates, bar heights in true proportion.
   Rendered and eyeballed one of each.
2. **Caption safe area.** The first contact sheet showed the burned-in caption
   plate covering the bar labels and the line chart's x-axis. `BODY_BOTTOM` is
   now 858 with a further `LABEL_ROOM` of 74 for charts that hang labels below
   their baseline. Verified by overlaying the caption line on the stills.
3. **`voice.py`** — three interchangeable narration sources. Shot durations are
   derived so they tile the audio exactly; video and voice cannot drift.
4. **`render.py`** — Ken Burns via `zoompan` (alternating push-in, pull-back and
   two pan directions), concat, ducked music, loudnorm, contact sheet.
5. **Frame loss at the mux.** `loudnorm` trims ~70 ms off the audio tail and
   `-shortest` was then clipping the last video frame. Fixed with `apad`, so
   the video is the authority on length. 1502 frames expected, 1502 delivered.
6. **Phantom frame at the joins.** AAC quantises audio to 1024-sample frames,
   so each part's audio ends ~11 ms after its video; the concat filter offsets
   the next segment by the longer stream and the CFR encoder filled each gap
   with a duplicate. Fixed by pinning both streams of every segment to exactly
   `frames / 25` with `trim` / `apad`+`atrim`. 1902 = 1902.

## Second system (topic, duration, notes -> video)

`tools/make_video.py` orchestrates the whole run as a resumable state machine:
`new` -> `check` -> `flow` -> `watch`/`run` -> `status`. Verified end to end on
a 60 s test: predicted 58 s, rendered 57.52 s, frame counts exact at every join.

- **Flow stays manual, deliberately.** Flow has no public API. Veo 3.1 is
  available through the Gemini API and Vertex AI, but as a separate paid
  product that the AI Pro credits do not cover. `watch` polls the flow/ folder
  so the manual part is reduced to pasting two prompts and downloading two
  clips; everything after that is unattended. Automating the Flow UI with a
  headless browser was considered and rejected: it breaks Google's terms and
  risks the account.
- **`presenter.json`** defines the presenter once. Every video's Flow prompts
  are generated from it, so the room and character cannot drift between videos.
- **`studio/plan.py`** shares its pacing constants with `studio/voice.py`, so
  the duration estimate and the real render agree; `check` enforces +/-10%.
- **vidIQ for titles/keywords.** It is an MCP tool, so it runs in a Claude
  session, not in the pipeline: Claude writes `videos/<topic>/seo.json` and
  `make_video.py` renders `out/upload.md` from it. Measured cost: 10 credits
  per video against a 150/month free allowance.

## Generated footage (in progress)

A `clip` shot kind now sits alongside the drawn kinds. Its footage comes from a
video model on a GPU; everything downstream -- captions, music, mix, stitch,
frame-count verification -- is unchanged and still applies.

- `studio/footage.py` conforms whatever the model returns to the exact frame
  count the narration needs. LTX-Video works in frames divisible by 8 plus 1,
  so a 193-frame clip is 8.04 s at 24 fps while a shot might want 8.4 s. Three
  modes: **trim** when the source is long enough, **speed** (setpts) within
  +/-15% where a retime is invisible, **boomerang** (forward + reversed, looped,
  trimmed) beyond that. Verified: all three land on the exact frame count.
- Missing footage degrades to a text card with a warning, the same policy as a
  failed Commons download. A model that drops one clip cannot kill a render.
- Optional lower-third headline overlay for clip shots.
- Generation resolution is **1024x576**: exactly 16:9 and divisible by 32, as
  LTX requires, and only a 1.875x upscale to 1080p. Fall back to 704x384 if a
  T4 runs out of VRAM. Generating at 4:3 and cropping to 16:9 loses a third of
  the frame -- do not.

**No Hugging Face.** Weights come from a Kaggle dataset named in `config.json`
(`python tools/setup_check.py --set-weights owner/slug`), and the notebook sets
`HF_HUB_OFFLINE` / `TRANSFORMERS_OFFLINE` / `DIFFUSERS_OFFLINE` so an accidental
reach for the Hub raises instead of silently downloading. If a load fails, the
fix is to attach the right dataset -- never to unset the flags.

`tools/gpu_probe.py` answers step 0: local GPU with 12 GB+ means generate
locally; otherwise Kaggle's free T4. CPU-only is not viable at hours per clip.

## Output formats and cost

`studio/formats.py` holds one profile per output shape. `theme.use_format()`
rebinds the canvas and every layout constant, so one `build_body.py` renders
either. Read dimensions as `theme.OUT_W`, never `from .theme import OUT_W` --
the latter captures whatever format was active at import.

| | `long` | `short` |
|---|---|---|
| canvas | 1920x1080 | 1080x1920 |
| pace | ~8 s/shot | ~4 s/shot |
| captions | navy plate, full lines | outlined text, 3-word groups |
| presenter | on by default | **off** by default |
| marginal cost | ~40 Flow credits | **zero** |

**Cost is the reason Shorts default to no presenter.** Flow credits come from a
monthly grant that does not roll over, so they -- not money -- are the binding
constraint on output. A hook and close also eat 16 s of a 60 s Short. Without
them a Short costs nothing at the margin and volume is capped only by the free
Kaggle GPU quota. Turn one on per video with `--presenter`.

Two more decisions made on cost grounds:

- **Kokoro is the production voice for Shorts**, not just a draft. It runs
  locally on CPU, needs no Kaggle job, and its weights come from the
  kokoro-onnx **GitHub releases** page, which satisfies the no-Hugging-Face
  rule. The Chatterbox clone still applies wherever there is a Flow presenter
  to clone from.
- **No Whisper for captions.** One shot is one narration line, so each line's
  start and end are already known exactly; word-group timings come from
  distributing that span by character count. Accurate to a few hundredths of a
  second at speech pace, and it costs nothing to compute. Adding a
  transcription model here would spend GPU time to recover timings we were
  handed for free.

Per-format outputs are suffixed (`body_short.mp4`, `contact_sheet_short.png`,
`stills_short/`) so one topic can hold both cuts without either clobbering the
other.

## Open items

- [ ] Run `python tools/kaggle_run.py --job smoke` against the real account.
  This is the one path that could not be exercised without live credentials.
- [ ] **Quality gate:** `python tools/kaggle_run.py --job footage-samples --ref <still>`
      then watch the three clips before any further footage work. The notebooks
      in `kaggle/make_footage_nb.py` have never run on a live GPU -- the build
      machine had neither a GPU nor network access to Kaggle. Treat the first
      run as a debugging session.
- [ ] Find or mirror LTX-Video weights as a Kaggle dataset, then
      `python tools/setup_check.py --set-weights owner/slug`.
- [ ] Check the model licence before publishing: some open-weight video models
      carry non-commercial terms that matter for a monetised channel.
- [ ] First real Flow hook/close, then `cut_voice_ref.py` and the voice job.
- [ ] Drop a CC0/CC BY music bed into `assets/music/`.
- [ ] Optional: install `kokoro-onnx` for local draft narration.
- [ ] Fill in `presenter.json` with the real Maya, once her Flow character exists.
- [ ] `pip install kokoro-onnx soundfile`, then `python tools/fetch_voice.py`.
      Until both are done every render falls back to silent narration.
- [ ] Authorize a YouTube channel in vidIQ (currently none), for channel-aware
      title scoring and the analytics tools.

## Deliberate deviations from the original brief

- **The renderer is shared, not copied per video.** The brief described
  copying `build_body.py` per video. Here the engine lives in `studio/` and
  the per-video file holds only `SHOTS`, `HOOK` and `CLOSE`. A rendering fix
  then reaches every video instead of the one you happen to be editing, and
  the part you actually edit stays about 60 lines.
- **The Kaggle username is resolved, not hard-coded.** The brief said to put
  it in a constant and ask rather than guess. It is read from
  `STUDIO_KAGGLE_USER`, then `config.json`, then the `username` field of
  `~/.kaggle/kaggle.json` — never guessed, and the token itself is never read.
- **Voice reference travels as a private Kaggle dataset**, not embedded in the
  notebook, which keeps the push under the ~1 MB limit with room to spare.
