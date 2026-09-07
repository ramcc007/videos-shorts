# The seven steps

About 30 minutes and ~40 Flow credits per video. Steps 2 and 3 are the only
ones that need a browser.

## 1. Write the script

```bash
python tools/new_video.py my-topic
```

Edit `videos/my-topic/body/build_body.py`: fill in `SHOTS`, and write the
`HOOK` and `CLOSE` lines you will read into Flow. Check the layout without
rendering video:

```bash
python videos/my-topic/body/build_body.py --stills-only
```

Look at `videos/my-topic/body/stills/`. Iterate here — it takes seconds.

## 2 & 3. Generate the hook and close in Flow (by hand)

- Your own Maya character attached, so the face and room stay consistent
- **Veo 3.1 Fast** — never Veo Quality
- x1, 16:9
- Confirm-before-generating stays on **Always**; click Approve each time
- Retry a bad clip **once** at most

Save them as `videos/my-topic/flow/hook.mp4` and `close.mp4`.
About 10 minutes of clicking, ~40 credits.

## 4. Clean the Flow clips

```bash
python tools/fix_clip.py --topic my-topic --clip hook
python tools/fix_clip.py --topic my-topic --clip close
```

De-logos the watermark, forces 1080p/25fps, and normalises the codec so the
stitch cannot drift. If a mouth or a screen in the shot has an artefact, paint
it out with a tight box:

```bash
python tools/fix_clip.py --topic my-topic --clip hook --patch 980,610,120,90
```

If the watermark is not where the default expects, pass `--logo x,y,w,h`, or
`--no-logo` to leave it alone.

## 4b. Clone the voice

```bash
python tools/cut_voice_ref.py --topic my-topic
python tools/kaggle_run.py --job voice --topic my-topic
```

The first cuts a 15-second mono 24 kHz reference at −20 LUFS from the two Flow
clips. The second uploads it as a **private** Kaggle dataset, pushes a notebook
that clones the voice with Chatterbox and narrates every `say` line, waits, and
downloads `voice.zip` into `videos/my-topic/body/kaggle_out/`. About 8 minutes
on the GPU.

The reference is synthetic speech from Flow. Never point this at a real person.

Then match the body's tone to the hook recording:

```bash
python tools/match_eq.py --topic my-topic
```

## 5. Render the body

```bash
python videos/my-topic/body/build_body.py --reuse-voice
```

Six stages: narration → stills → Ken Burns clips → captions → audio mix →
burn and mux. It prints a duration/frame-count check and writes a contact
sheet at `videos/my-topic/out/contact_sheet.png`.

If the script changed after the voice was rendered, this stops and tells you —
the line counts must match.

## 6. Stitch

```bash
python tools/stitch.py --topic my-topic
```

Joins hook + body + close and **fails loudly** if the output frame count is not
exactly the sum of the parts.

## 7. Review

```bash
python tools/review.py --topic my-topic
```

Gives you:

- the contact sheet — one frame per shot
- the frames either side of both joins, in `out/review/`
- EBU R128 loudness for the whole cut and each part (they should sit within
  about 1 LU of each other)
- the frame-count check again

Then, on upload: **tick YouTube's synthetic-content disclosure**, and paste the
credit lines from `out/CREDITS.md` into the description.

---

## When something goes wrong

| Symptom | Cause | Fix |
|---|---|---|
| `kernels_status` raises `IndexError` | fetching the log mid-run | don't — poll status; output only exists when the run finishes |
| Kaggle push rejected, notebook too big | >~1 MB push limit | the notebook must download its inputs, not embed them |
| Kaggle logs full of mojibake on Windows | CLI encoding | `PYTHONUTF8=1`, `PYTHONIOENCODING=utf-8` (kaggle_run.py sets both) |
| `chatterbox` import fails on Kaggle | stock image's torch/torchcodec combo | the notebook already pins torch 2.6.0 and removes torchcodec first |
| venv on Kaggle picks up the wrong numpy | `PYTHONPATH=/kaggle/lib/kagglegym:/kaggle/lib` shadows it | build with `--system-site-packages --without-pip`; the 3.12 image has no working ensurepip |
| Kaggle output download is huge | built in `/kaggle/working` | build under `/kaggle/tmp`, copy only the zip out |
| Body voice and video drift apart | narration re-rendered after the script changed | re-run the voice job; the line counts must match |
| Final frame count ≠ sum of parts | a Flow clip is not 25 fps | re-run `fix_clip.py` on it |
| Chart labels hidden behind captions | drawing below `BODY_BOTTOM` | keep chart content above it; see `studio/draw.py` |
| A photo shot renders as a text card | no CC0/CC BY/PD image found, or the download failed | check the warning in the log; set `file="File:Something.jpg"` explicitly |
