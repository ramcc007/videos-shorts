"""Generate the Kaggle notebook that produces body footage.

Two modes:
  samples  three clips for the quality gate -- run this FIRST
  batch    one clip per `clip` shot in a video

NO HUGGING FACE. This project does not depend on it. Weights are read from a
Kaggle dataset attached to the kernel, and the notebook sets HF_HUB_OFFLINE=1 /
TRANSFORMERS_OFFLINE=1 so that any accidental reach for the Hub raises instead
of silently downloading. If a load fails, the fix is to attach the right
weights dataset -- never to turn the offline flags off.

Getting weights onto Kaggle, in order of preference:
  1. An existing public Kaggle dataset of the model weights.
  2. Mirror them once into your OWN private Kaggle dataset, then depend only on
     that. Most durable, and removes the third-party fetch from every run.
  3. ModelScope (`pip install modelscope`) inside the notebook.

This notebook has NOT been run against a live Kaggle GPU -- the machine it was
written on had neither a GPU nor network access to Kaggle. Treat the first run
as a debugging session, not a production one.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nb  # noqa: E402

# 16:9 and divisible by 32, which LTX-Video requires. 1024x576 is exactly 16:9
# and only a 1.875x upscale to 1080p; drop to 704x384 if the T4 runs out of VRAM.
WIDTH, HEIGHT = 1024, 576
FALLBACK_W, FALLBACK_H = 704, 384
FPS_OUT = 24
# frames must be divisible by 8, plus 1
FRAMES = 193          # 193 = 24*8+1 -> ~8.0 s at 24 fps


def _preamble(weights_dir: str) -> str:
    return f'''
# --- environment -------------------------------------------------------------
# Hugging Face is deliberately disabled. Weights come from an attached Kaggle
# dataset. If a load fails here, attach the right dataset -- do not unset these.
import os
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["DIFFUSERS_OFFLINE"] = "1"
os.environ["HF_HOME"] = "/kaggle/tmp/hf"

import subprocess, sys, time, glob
t0 = time.time()

def sh(cmd):
    print("$", " ".join(cmd), flush=True)
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout[-3000:]); print(r.stderr[-3000:], file=sys.stderr)
        raise SystemExit("command failed: " + " ".join(cmd))
    return r.stdout

sh([sys.executable, "-m", "pip", "install", "-q", "diffusers", "transformers",
    "accelerate", "sentencepiece", "imageio-ffmpeg"])

import torch
print("torch", torch.__version__, "cuda", torch.cuda.is_available())
assert torch.cuda.is_available(), "No GPU. Set the accelerator to GPU on this kernel."
print("device:", torch.cuda.get_device_name(0),
      f"{{torch.cuda.get_device_properties(0).total_memory/1e9:.0f}} GB")

WEIGHTS = "{weights_dir}"
if not os.path.isdir(WEIGHTS):
    found = sorted(glob.glob("/kaggle/input/*/**/model_index.json", recursive=True))
    raise SystemExit(
        "Weights not found at " + WEIGHTS + ".\\n"
        "Attach the weights dataset to this kernel and set WEIGHTS_DIR to its path.\\n"
        "model_index.json files visible under /kaggle/input: " + repr(found[:10]))
print("weights:", WEIGHTS)
os.makedirs("/kaggle/tmp/out", exist_ok=True)
print(f"env ready in {{time.time()-t0:.0f}}s", flush=True)
'''


def _loader() -> str:
    return f'''
# --- load the pipeline (local weights only) ----------------------------------
from diffusers import LTXPipeline, LTXConditionPipeline
from diffusers.utils import export_to_video, load_image

W, H, FRAMES, FPS_OUT = {WIDTH}, {HEIGHT}, {FRAMES}, {FPS_OUT}

def load(kind):
    cls = LTXConditionPipeline if kind == "i2v" else LTXPipeline
    pipe = cls.from_pretrained(WEIGHTS, torch_dtype=torch.bfloat16,
                               local_files_only=True)
    pipe.to("cuda")
    pipe.enable_vae_tiling()          # keeps a T4 inside 16 GB at 1024x576
    return pipe

NEGATIVE = "worst quality, inconsistent motion, blurry, jittery, distorted, watermark, text"

def generate(pipe, prompt, out_path, image=None, steps=40, w=W, h=H, frames=FRAMES):
    kwargs = dict(prompt=prompt, negative_prompt=NEGATIVE, width=w, height=h,
                  num_frames=frames, num_inference_steps=steps)
    if image is not None:
        kwargs["image"] = load_image(image)
    t = time.time()
    video = pipe(**kwargs).frames[0]
    export_to_video(video, out_path, fps=FPS_OUT)
    print(f"  {{out_path}}  {{frames/FPS_OUT:.1f}}s  in {{time.time()-t:.0f}}s", flush=True)
'''


def build_samples(out_path: Path, weights_dir: str, prompts: list[str],
                  ref_image: str | None = None) -> Path:
    """The quality gate: three clips, then stop."""
    cells = [
        nb.md("""
# Footage samples — the quality gate

Three clips only. Look at them before any renderer is built.

1. text-to-video, ~8 s
2. **image-to-video from a reference still** — the important one for character
   consistency across shots
3. a second text-to-video at a different prompt, to judge consistency

No Hugging Face: weights are read from an attached Kaggle dataset with the
offline flags set.
"""),
        nb.code(_preamble(weights_dir)),
        nb.code(_loader()),
        nb.code("PROMPTS = " + json.dumps(prompts, indent=1, ensure_ascii=False)
                + f"\nREF = {json.dumps(ref_image)}\nprint(len(PROMPTS), 'prompts')"),
        nb.code('''
# --- 1 & 3: text to video ----------------------------------------------------
pipe = load("t2v")
for i, p in enumerate(PROMPTS[:2]):
    generate(pipe, p, f"/kaggle/tmp/out/t2v_{i:02d}.mp4")
del pipe; torch.cuda.empty_cache()
'''),
        nb.code('''
# --- 2: image to video from the reference still ------------------------------
import glob
if REF:
    hits = sorted(glob.glob(f"/kaggle/input/**/{REF}", recursive=True))
    if not hits:
        print(f"WARNING: reference image {REF} not found under /kaggle/input; "
              "skipping the image-to-video sample. This is the sample that "
              "matters most -- attach it and re-run.")
    else:
        pipe = load("i2v")
        generate(pipe, PROMPTS[-1], "/kaggle/tmp/out/i2v_00.mp4", image=hits[0])
        del pipe; torch.cuda.empty_cache()
else:
    print("No reference image supplied; skipping image-to-video.")
'''),
        nb.code('''
# --- hand back ---------------------------------------------------------------
import shutil, os
shutil.make_archive("/kaggle/working/samples", "zip", "/kaggle/tmp/out")
print("WROTE /kaggle/working/samples.zip",
      f"({os.path.getsize('/kaggle/working/samples.zip')/1e6:.1f} MB)")
print("SAMPLES OK")
'''),
    ]
    return nb.write(cells, out_path)


def build_batch(out_path: Path, weights_dir: str, shots: list[dict],
                ref_image: str | None = None) -> Path:
    """One clip per `clip` shot, indexed to match the SHOTS list."""
    jobs = [{"index": i, "prompt": s["prompt"], "ref": s.get("ref")}
            for i, s in enumerate(shots) if s["kind"] == "clip"]
    cells = [
        nb.md(f"""
# Body footage — {out_path.stem}

{len(jobs)} clips, named by shot index so `studio/footage.py` can pair them up.
Output: `/kaggle/working/footage.zip` containing `000.mp4`, `001.mp4`, ...
"""),
        nb.code(_preamble(weights_dir)),
        nb.code(_loader()),
        nb.code("JOBS = " + json.dumps(jobs, indent=1, ensure_ascii=False)
                + f"\nREF = {json.dumps(ref_image)}\nprint(len(JOBS), 'clips to generate')"),
        nb.code('''
# --- generate ----------------------------------------------------------------
import glob, traceback

ref_hits = sorted(glob.glob(f"/kaggle/input/**/{REF}", recursive=True)) if REF else []
use_i2v = bool(ref_hits)
print("mode:", "image-to-video" if use_i2v else "text-to-video")

pipe = load("i2v" if use_i2v else "t2v")
failed = []
for j in JOBS:
    out = f"/kaggle/tmp/out/{j['index']:03d}.mp4"
    try:
        img = None
        if use_i2v:
            own = sorted(glob.glob(f"/kaggle/input/**/{j['ref']}", recursive=True)) \\
                  if j.get("ref") else []
            img = own[0] if own else ref_hits[0]
        generate(pipe, j["prompt"], out, image=img)
    except Exception:
        # one bad clip must not cost the whole batch -- the renderer falls back
        # to a text card for anything missing
        traceback.print_exc()
        failed.append(j["index"])
        torch.cuda.empty_cache()

print("\\nfailed shots:", failed or "none")
'''),
        nb.code('''
# --- hand back ---------------------------------------------------------------
import shutil, os, glob
made = sorted(glob.glob("/kaggle/tmp/out/*.mp4"))
print(f"{len(made)} clips generated")
shutil.make_archive("/kaggle/working/footage", "zip", "/kaggle/tmp/out")
print("WROTE /kaggle/working/footage.zip",
      f"({os.path.getsize('/kaggle/working/footage.zip')/1e6:.1f} MB)")
print("FOOTAGE JOB OK")
'''),
    ]
    return nb.write(cells, out_path)


if __name__ == "__main__":
    dest = Path(sys.argv[1] if len(sys.argv) > 1 else "build/footage_samples.ipynb")
    print(build_samples(dest, "/kaggle/input/ltx-video-weights",
                        ["a rocket rising through low cloud at dawn, slow push in",
                         "the curved edge of the earth from orbit, sunlight creeping across",
                         "a woman looking out of a spacecraft window, quiet, cinematic"],
                        ref_image="maya_ref.png"))
