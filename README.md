# Second Studio

An automated explainer-video pipeline. Each video is a 90-second-to-3-minute
1080p/25fps cut in three parts:

| Part | Length | Made by |
|---|---|---|
| **Hook** | 8 s | Google Flow, by hand — a photoreal presenter talking to camera |
| **Body** | the bulk | local Python — charts, numbers, photos, captions, ducked music |
| **Close** | 8 s | Google Flow, by hand — same presenter, same room |

All three share one voice: the body narration is a zero-shot clone of the
presenter's Flow voice, rendered on a free Kaggle GPU.

Everything that is **not** the presenter's face is free. See `PLAN.md` for the
standing rules — the most important being that the presenter comes from Flow
only, and that open-weight talking-head models are not an option here.

---

## 1. Install (about 20 minutes)

### Windows

```powershell
winget install Python.Python.3.12
winget install Gyan.FFmpeg
# close and reopen the terminal so PATH updates

git clone <this repo> second-studio
cd second-studio
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### macOS

```bash
brew install python@3.12 ffmpeg
git clone <this repo> second-studio && cd second-studio
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### Linux

```bash
sudo apt install python3 python3-venv ffmpeg
git clone <this repo> second-studio && cd second-studio
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## 2. Accounts and credentials

Two things only you can do:

1. **Kaggle API token.** Kaggle → Settings → API → *Create New Token*. Save the
   downloaded `kaggle.json` to `~/.kaggle/kaggle.json`
   (`C:\Users\<you>\.kaggle\kaggle.json` on Windows) **and nowhere else**.
   Never paste it into a chat, a commit, or this project folder.
   Your account must be **phone-verified** or there is no GPU.

2. **Tell the project your Kaggle username** (not a secret, but never guessed):

   ```bash
   python tools/setup_check.py --set-kaggle-user yourname
   ```

   It goes in `config.json`, which is git-ignored.

Then check everything at once:

```bash
python tools/setup_check.py
```

Every line should read `ok`. Two `warn`s are fine: `kokoro-onnx` (optional
draft voice) and the music bed (see `assets/music/README.md`).

## 3. Prove the Kaggle path before trusting it with a real job

```bash
python tools/kaggle_run.py --job smoke
```

This pushes a tiny notebook that prints `nvidia-smi`, waits for it, and pulls
the output back. It costs about a minute of quota. If this works, the hard part
of the plumbing works.

## 4. Render the demo video

A working example ships in `videos/home-batteries/`. Without touching Flow or
Kaggle you can render its body right now:

```bash
python videos/home-batteries/body/build_body.py --voice silent
```

That produces `videos/home-batteries/out/body.mp4` and a contact sheet — one
frame per shot — which is the fastest way to see whether a script works.

Useful flags:

| Flag | Does |
|---|---|
| `--stills-only` | draw the frames and stop (seconds, not minutes) |
| `--voice silent` | timed silence — layout and pacing only, no model needed |
| `--voice kokoro` | local draft narration (needs `kokoro-onnx`) |
| `--reuse-voice` | the real cloned Chatterbox narration from Kaggle |
| `--no-photos` | skip Wikimedia downloads; photo shots become text cards |
| `--music path` | pick a specific bed |
| `--force-stills` | redraw stills that already exist |

## 5. Make your own video

```bash
python tools/new_video.py my-topic
```

Then edit `videos/my-topic/body/build_body.py`. That file holds the entire
script: a `SHOTS` list, plus the `HOOK` and `CLOSE` lines you will read into
Flow. Nothing else in it needs changing.

Shot kinds: `card`, `number`, `bars`, `line`, `rating`, `pie`, `photo`. Every
shot carries one `say` line — one shot, one narration line, one caption. That
1:1 rule is what keeps captions on the voice without any alignment model.

## 6. The seven steps

See `docs/WORKFLOW.md`. About 30 minutes and ~40 Flow credits per video.

---

## Project layout

```
PLAN.md                     running notes, standing rules, open items
config.json                 your Kaggle username (git-ignored)
studio/                     the shared render engine
  theme.py                  every colour, font and size decision
  draw.py                   all seven shot kinds, drawn with Pillow
  shots.py                  the SHOTS schema and its validation
  photos.py                 Wikimedia Commons, CC0/CC BY/PD only
  voice.py                  chatterbox | kokoro | silent narration
  captions.py               burned-in captions as ASS
  render.py                 ffmpeg: motion, mixing, contact sheet
  body.py                   the six-stage build, with checks
tools/
  setup_check.py            preflight
  new_video.py              scaffold a video
  kaggle_run.py             push a notebook to Kaggle, poll, download
  fix_clip.py               de-logo and normalise a Flow clip
  cut_voice_ref.py          cut the 15 s voice reference
  match_eq.py               match body narration tone to the hook
  stitch.py                 join the three parts, verify frame count
  review.py                 joins, loudness, frame count
kaggle/
  nb.py                     minimal .ipynb writer
  make_smoke_nb.py          the nvidia-smi proof notebook
  make_voice_nb.py          the Chatterbox voice-clone notebook
videos/<topic>/
  body/build_body.py        the script for one video — the only file you edit
  flow/                     hook.mp4, close.mp4 from Flow
  voice/ref.flac            15 s reference cut from those clips
  out/                      body.mp4, final cut, contact sheet, CREDITS.md
```

## Costs

| Item | Cost |
|---|---|
| Voice clone | ~8 GPU-minutes of Kaggle's free 30 h/week (resets Saturday 00:00 UTC) |
| Body render | free — CPU only, ~1 minute per minute of video |
| Charts, photos, captions, music | free |
| Presenter | ~40 Flow credits from the Google AI Pro grant; credits do not roll over |
