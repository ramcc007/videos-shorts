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

## Open items

- [ ] Run `python tools/kaggle_run.py --job smoke` against the real account.
  This is the one path that could not be exercised without live credentials.
- [ ] First real Flow hook/close, then `cut_voice_ref.py` and the voice job.
- [ ] Drop a CC0/CC BY music bed into `assets/music/`.
- [ ] Optional: install `kokoro-onnx` for local draft narration.
- [ ] Fill in `presenter.json` with the real Maya, once her Flow character exists.
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
