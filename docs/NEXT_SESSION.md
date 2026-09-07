# Brief for the local session

You are picking up a working pipeline. **Read `PLAN.md` and `README.md` before
writing any code**, and keep `PLAN.md` updated as you go.

## The objective

Today the body of each video is charts, cards and stock photographs. The owner
wants the **core body to be generated footage** — actual moving video for the
stated duration — produced on a **free Kaggle GPU** with open-weight models.

The split of labour:

- **Flow (manual, by the owner):** the 8 s hook, the 8 s close, and occasional
  character-building clips. Veo 3.1 Fast. Flow has no public API, so this stays
  manual — see below.
- **Kaggle (automated, by you):** the core footage for the body, plus the
  existing voice clone.
- **Local (automated, by you):** captions, music, mixing, stitching, checks.

## What already exists — do not rebuild it

A full pipeline is already built, tested and committed:

| Piece | State |
|---|---|
| `studio/` render engine, 7 shot kinds | working, verified |
| `tools/make_video.py` orchestrator (new/check/flow/watch/run/status) | working, resumable |
| `tools/kaggle_run.py` headless notebook runner | built, **never run live** |
| `kaggle/make_voice_nb.py` Chatterbox voice clone | built, **never run live** |
| `tools/fix_clip.py`, `cut_voice_ref.py`, `match_eq.py`, `stitch.py`, `review.py` | working |
| `studio/plan.py` duration → shot/word budget | working |
| `presenter.json` → Flow prompt generation | working |

The captions, music ducking, loudness normalisation, stitching and frame-count
verification all still apply to generated footage. **Reuse them.** The new work
is a second body renderer, not a new pipeline.

## Step 0 — where can the footage actually be generated?

Answer this before anything else, because it decides the whole design.

```bash
nvidia-smi                     # NVIDIA GPU and how much VRAM?
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

| What you find | Where footage gets generated |
|---|---|
| NVIDIA GPU, >= 12 GB VRAM | **locally** — Kaggle is then only for the voice clone |
| NVIDIA GPU, 8-12 GB VRAM | locally, smaller models and shorter clips; Kaggle as overflow |
| No NVIDIA GPU (Apple Silicon, integrated, or CPU only) | **Kaggle's free T4** — the only free GPU available |

Apple Silicon: MPS works for image models but video generation support is
patchy. Test one clip before committing to it.

**CPU-only generation is not a fallback.** It is hours per five-second clip.
If there is no usable GPU locally, use Kaggle and do not pretend otherwise.

Report what you find and the plan that follows from it before building.

## Model weights: do NOT use Hugging Face

The owner has asked that this project not depend on Hugging Face. Nearly every
open-weight video model is distributed there, so source weights from these
instead, in order of preference:

1. **Kaggle Models / Kaggle Datasets.** Weights for LTX-Video and others are
   published as public Kaggle datasets. If the job runs on Kaggle anyway, this
   is the cleanest route: attach the weights dataset to the kernel and the
   notebook never reaches outside Kaggle at all. Search Kaggle first.
2. **ModelScope** (`modelscope` pip package) — Alibaba's own host, carries the
   Wan family.
3. **GitHub releases** from the model's own repository, where offered.
4. Mirror the weights once into the owner's **own private Kaggle dataset**, then
   depend only on that. This is the most durable option and removes the
   third-party fetch from every subsequent run.

Keep the weight source **pluggable** — a single constant or config entry naming
where weights come from, not a URL hard-coded through the notebook. Do not lock
the project to any one host, Kaggle included.

If a model turns out to be genuinely unobtainable outside Hugging Face, say so
and name the alternatives rather than quietly reaching for HF.

## Step 1 — de-risk. Do not skip this.

Before building anything, prove the quality clears the owner's bar. Produce
**three sample clips** and nothing else:

1. text-to-video, 5 s, from a prompt
2. **image-to-video, 5 s, from a supplied still** — this is the important one
3. one clip at the target shot length (~8 s)

Then stop and show them. Roughly 20 GPU-minutes on a T4, less locally.

**Why this gate exists:** the owner previously spent a full day on SadTalker
plus GFPGAN and rejected the result as visibly fake. Open-weight video on a
free T4 is the same category of risk. Find out from three clips, not from a
finished renderer.

Model guidance for a free T4 (16 GB) or a similar local card:

- **LTX-Video** (2B, ~8 GB VRAM) or **Wan 2.2 5B** — both viable
- **Not CogVideoX-5B**: ~30 min per clip on a T4. A 60 s video needs ~12 clips,
  so ~6 GPU-hours for one video against a 30 h/week quota. Too slow.
- Budget target: ~5 min per 5 s clip -> ~1 GPU-hour per 60 s video -> ~25 videos
  a week within the free Kaggle quota.

Two things that materially improve output:

- **Prefer image-to-video over text-to-video.** Generate or supply a consistent
  still, then animate it. Character consistency across shots is exactly where
  pure text-to-video falls apart.
- **Seed from the owner's Flow character clips.** Pull a frame from a Flow clip
  and use it as the i2v reference: Veo-quality character, animated free.

Ask about style before generating: **stylised or illustrated output hides
open-weight artefacts far better than photoreal** and is usually why channels
like this look intentional rather than broken.

Check each model's licence before use and record it in `PLAN.md`. Some
open-weight video models carry non-commercial or acceptable-use restrictions
that matter for a monetised channel.

## Step 2 — only if step 1 passes

Add a `footage` body renderer alongside the existing chart renderer:

shot list → per-shot clip prompts → one batched Kaggle job → downloaded clips →
assembled through the **existing** captions, music, mix, stitch and
verification path.

Keep both renderers. A data-heavy explainer is still better served by charts;
a narrative is better served by footage. The shot schema in `studio/shots.py`
should grow a kind, not be replaced.

## Standing rules — never break these

They are in `PLAN.md` in full. The ones most likely to be tripped here:

1. **The presenter's face comes from Flow only.** SadTalker, Wav2Lip and every
   still-image talking-head model were tried and rejected. Do not re-propose
   them. Generated b-roll is fine; a generated talking head is not.
2. **Never upload a real person's photo or voice to Kaggle.**
3. **Only CC0, CC BY or public-domain assets**, credits kept.
4. **Never print or commit API keys.** The Kaggle token lives in `~/.kaggle/`
   and nowhere else. `config.json` holds a username only.
5. **Every YouTube upload gets the synthetic-content disclosure ticked.**
6. Flow: Veo 3.1 Fast only, never Quality. Retry a bad clip once at most.

## Notes carried over from the build session

- Flow has **no public API**. Veo 3.1 is reachable through the Gemini API and
  Vertex AI, but as a separate paid product that AI Pro credits do not cover.
  Automating the Flow UI with a headless browser was considered and rejected:
  it breaks Google's terms and risks the account.
- `tools/make_video.py watch` polls the flow/ folder, so the manual Flow step is
  reduced to pasting two generated prompts and saving two files.
- Titles and keywords come from **vidIQ**, which is an MCP tool — it runs in a
  Claude session, not in the pipeline. It writes `videos/<topic>/seo.json` and
  `make_video.py` renders `out/upload.md` from it. Free plan: 150 credits a
  month, ~10 per video.
- Two frame-accuracy bugs are already fixed and must not regress: `loudnorm`
  trimming the audio tail (fixed with `apad`), and the concat filter inserting a
  phantom frame at each join (fixed by pinning both streams of every segment to
  `frames / 25`). `tools/review.py` catches both.
- The build ran in a cloud container with **no GPU** (4 CPU cores) whose egress
  policy blocked `kaggle.com`, `huggingface.co`, `modelscope.cn` and
  `commons.wikimedia.org`. That is why the Kaggle jobs and the Wikimedia photo
  fetch are marked untested in `PLAN.md`. **On a normal machine they should
  work** — verify them early rather than assuming they are broken.

## First actions

```bash
python tools/setup_check.py                    # every line should read ok
python tools/kaggle_run.py --job smoke         # proves the Kaggle path, ~1 min of quota
```

The smoke test is the first thing that has never been run for real. If it
passes, the plumbing works. If it fails, fix that before anything else.

Then build the step-1 sample notebook and show the owner the clips.
