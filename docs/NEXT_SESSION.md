# Brief for the local session

You are picking up a working pipeline. **Read `CLAUDE.md` and `PLAN.md` before
writing any code**, and keep `PLAN.md` updated as you go.

Everything below was built and verified in a cloud container with no GPU, whose
egress blocked `kaggle.com`, `huggingface.co` and `commons.wikimedia.org`. That
is why some paths are marked untested: they could not be exercised there, not
because they are known broken. On a normal machine they should work — verify
them early rather than assuming either way.

## First actions

```bash
python tools/setup_check.py          # every line ok; a music-bed warn is fine
python tests/test_notebooks.py       # all notebook cells parse
python tools/kaggle_run.py --job smoke
```

The smoke test prints the GPU, its compute capability, and `USABLE:`. That last
line is the gate for every other GPU job.

## The one live blocker

Kaggle hands out a T4 (sm_75) or a P100 (sm_60) at random and its PyTorch is
built for sm_70+, so **P100 runs cannot work at all**. `--accelerator` sets
`machine_shape` in the kernel metadata; Kaggle validates the string server-side
and the client has no enum for it, so the value has to be found empirically.

Try candidates against the 40-second smoke test until one reports a T4 and
`USABLE: True`, then pin it:

```bash
python tools/kaggle_run.py --job smoke --accelerator "gpu_t4x2"
python tools/setup_check.py --set-accelerator "<the one that worked>"
python tools/kaggle_run.py --job portrait
```

If no string is accepted, set the accelerator to GPU T4 x2 by hand in the
kernel's settings on kaggle.com and re-run — the kernel keeps that setting.

## Then: the presenter chain

`--job portrait` produces four faces and a contact sheet with a thumbnail strip.
Judge them at both sizes. The choice is permanent — it becomes the channel's
presenter — so back the chosen file up **outside** the project; it cannot be
regenerated identically. Then register it as a Flow character, record one clip
of her speaking, `tools/cut_voice_ref.py`, and `--job voice`.

Base SDXL renders faces somewhat plastic. If the four come back waxy that is the
model, not the prompt: `architkohli/sdxl` (dreamshaper-xl-turbo) is a photoreal
fine-tune, and Kaggle *models* now attach correctly via `model_sources`.

## After that

The owner's standing criticism is that the videos look basic. The motion pass
addressed movement; `CLAUDE.md` lists what remains, in rough order of impact:
sound design, hooks and storytelling, b-roll, voice. Sound design and b-roll are
free and mostly mechanical; hooks are writing; voice needs the chain above.
