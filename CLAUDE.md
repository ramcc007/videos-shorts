# Second Studio — working notes for Claude Code

An automated faceless-video pipeline. Two output formats from one engine:

| | `long` (16:9) | `short` (9:16) |
|---|---|---|
| Canvas | 1920x1080 | 1080x1920 |
| Length | 90 s – 3 min | 15–60 s |
| Pace | ~8 s/shot | ~4 s/shot |
| Presenter | Flow hook + close | **none by default** |
| Marginal cost | ~40 Flow credits | **zero** |

Read `PLAN.md` before writing code, and keep it updated as you work. `README.md`
is the user-facing setup guide.

## Standing rules — never break these

1. **The presenter's face comes from Google Flow only.** SadTalker, Wav2Lip and
   every still-image talking-head model were tried and rejected as visibly
   fake. Do not re-propose them. Generated b-roll is fine; a generated talking
   head is not.
2. **No Hugging Face.** Weights come from Kaggle datasets/models, with
   `HF_HUB_OFFLINE` / `TRANSFORMERS_OFFLINE` / `DIFFUSERS_OFFLINE` set in every
   notebook. If a load fails, attach the right dataset — never unset the flags.
3. **Never upload a real person's photo or voice to Kaggle.** The voice
   reference is synthetic speech from Flow and nothing else.
4. **Only CC0, CC BY or public-domain assets**, and keep the credit lines.
5. **Never print or commit API keys.** The Kaggle token lives in `~/.kaggle/`
   and nowhere else. `config.json` holds a username and settings, no secrets.
6. **Flow: Veo 3.1 Fast only**, never Quality. Retry a bad clip once at most.
   Confirm-before-generating stays on "Always".
7. **Every YouTube upload gets the synthetic-content disclosure ticked.**
8. All on-screen text in English.

## Where things stand

Working and verified: the `studio/` render engine in both formats, per-frame
animation (`motion.py`), captions, music/mix, stitching, frame-count checks,
the resumable orchestrator, and `tools/kaggle_run.py` against a live account.

In progress: **setup-guide step 5**, the presenter portrait. The chain that
produces the cloned voice is:

```
SDXL portrait on Kaggle  -> --job portrait   [built, not yet succeeded]
  -> pick a face (permanent; back it up outside the project)   [human]
  -> register it as a Flow character                           [human]
  -> generate one clip of the presenter speaking               [human]
  -> cut a 15 s reference    tools/cut_voice_ref.py            [built]
  -> clone it                --job voice                       [built, never run]
```

Until that chain completes, narration is Kokoro: free, local, and flat.

**Immediate blocker:** Kaggle allocates a T4 (sm_75) or a P100 (sm_60) at
random, and its PyTorch is built for sm_70+. P100 runs cannot work at all. Find
an accelerator string Kaggle accepts that yields a T4, confirm it with the
smoke test (it prints `USABLE:`), then pin it:
`python tools/setup_check.py --set-accelerator <shape>`.

## Commands

```bash
python tools/setup_check.py                     # preflight
python tools/kaggle_run.py --job smoke          # ~40 s, prints GPU + USABLE
python tools/kaggle_run.py --job portrait       # 4 portrait options
python tools/make_video.py new --topic X --duration 30 --format short
python tools/make_video.py check --topic X      # enforces +/-10% duration
python tools/make_video.py run   --topic X      # renders; no Flow if no presenter
python tests/test_notebooks.py                  # MUST pass before any notebook change
```

## Traps already paid for — do not rediscover these

- **Notebook cells cannot contain `"""`** (it closes the literal carrying the
  cell) and **must not be f-strings** (every brace becomes a formatting site and
  is interpolated at build time). `nb.code()` enforces the first;
  `tests/test_notebooks.py` catches both. Run it after every notebook edit.
- **Read dimensions as `theme.OUT_W`**, never `from .theme import OUT_W` — the
  latter captures whichever format was active at import.
- **`state.json` is git-ignored**; the portable brief is `brief.json`. Read
  briefs through `make_video.py`'s `brief_of()`.
- **Kaggle models and datasets attach through different fields** —
  `model_sources` vs `dataset_sources`, routed by ref shape in `config.py`.
- **A single `.safetensors` cannot be loaded offline**: `from_single_file`
  fetches its config from the Hub. Use a diffusers-layout source.
- **Prefer the base pipeline over the refiner** — a refiner cannot generate from
  a prompt, and sorts first alphabetically in at least one dataset.
- **A failed kernel's log is published**; `kaggle_run.py` downloads and prints
  it. Read the traceback before theorising.
- Two frame-accuracy bugs are fixed and must not regress: `loudnorm` trimming
  the audio tail (fixed with `apad`) and the concat filter inserting a phantom
  frame per join (fixed by pinning both streams to `frames / FPS`).
  `tools/review.py` catches both.

## Known quality gaps (the owner's own words)

The videos currently read as "basic" — the motion pass helped, but these remain:

- **No music bed or SFX.** Drop a CC0/CC BY track into `assets/music/` and it is
  mixed and ducked automatically; SFX on cuts are not built yet.
- **Hooks and storytelling.** The first 2 seconds decide retention; current
  openings state a claim rather than opening a loop.
- **No b-roll.** Every shot is text on a navy gradient. Pexels/Pixabay have free
  API keys and would change this more than anything else.
- **Flat voice.** Kokoro is a model limitation, not a code one. Chatterbox (via
  the chain above) or ElevenLabs are the routes out.
