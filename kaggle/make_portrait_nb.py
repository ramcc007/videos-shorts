"""Notebook that generates presenter portrait options on a Kaggle GPU.

Step 5 of the setup guide. The portrait it produces becomes the channel's
presenter: you pick one, register it as a Flow character, and every clip from
then on carries that face. So this generates several options in one run --
re-running costs another GPU slot, and comparing four faces side by side beats
judging one in isolation.

The prompt is built from presenter.json, so the face matches the presenter the
rest of the pipeline already describes.

No Hugging Face: weights come from a Kaggle dataset attached to the kernel, and
HF_HUB_OFFLINE / DIFFUSERS_OFFLINE are set so an accidental reach for the Hub
raises instead of silently downloading. If a load fails, attach the right
dataset -- never unset the flags.

Kaggle's free GPUs (T4, P100) are pre-Ampere and have no bfloat16, so this uses
float16 throughout.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nb  # noqa: E402

NEGATIVE = ("cartoon, anime, illustration, painting, 3d render, cgi, plastic skin, "
            "waxy, airbrushed, distorted face, asymmetric eyes, extra fingers, "
            "deformed hands, watermark, text, logo, signature, blurry, low quality, "
            "oversaturated, harsh shadows, fisheye, wide angle distortion")


def portrait_prompt(p: dict) -> str:
    """A head-and-shoulders portrait prompt from the presenter definition."""
    return (
        f"photorealistic head and shoulders portrait photograph of {p['appearance']}, "
        f"wearing {p.get('wardrobe', 'a plain jumper')}, "
        f"in {p['room']}, "
        f"{p.get('lighting', 'soft even lighting')}, "
        "neutral friendly expression, looking directly into the camera, "
        "sharp focus on the eyes, 85mm portrait lens, shallow depth of field, "
        "natural skin texture with visible pores, documentary photography, "
        "colour photograph, centred composition"
    )


def build(out_path: Path, presenter: dict, weights_dir: str,
          seeds: list[int], steps: int = 34, guidance: float = 5.5) -> Path:
    prompt = portrait_prompt(presenter)
    cfg = json.dumps({"prompt": prompt, "negative": NEGATIVE, "weights": weights_dir,
                      "seeds": seeds, "steps": steps, "guidance": guidance,
                      "name": presenter.get("name", "presenter")}, indent=2)

    cells = [
        nb.md("# Presenter portraits\n"
              "Four options for the channel's presenter. Pick one; it becomes "
              "permanent.\n\n"
              "Weights come from an attached **Kaggle dataset**, not Hugging Face."),

        nb.code(f"""
import json, os, sys, subprocess, time

CFG = json.loads(r'''{cfg}''')

# Offline by policy. A load failure here means the weights dataset is missing or
# laid out differently -- attach the right dataset, do NOT unset these.
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["DIFFUSERS_OFFLINE"] = "1"

subprocess.run([sys.executable, "-m", "pip", "install", "-q",
                "diffusers", "transformers", "accelerate", "safetensors"], check=True)
print(subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total",
                      "--format=csv,noheader"], capture_output=True,
                     text=True).stdout.strip())
"""),

        nb.code("""
from pathlib import Path

W = Path(CFG["weights"])
if not W.exists():
    raise SystemExit(
        f"{W} does not exist.\\n"
        "Attach the SDXL weights dataset to this kernel and re-run.\\n"
        "Set it locally with: python tools/setup_check.py --set-portrait-weights owner/slug")

# Accept either a diffusers directory or a single .safetensors checkpoint.
# Kaggle models mount several levels deep (name/framework/variation/version),
# so search at any depth rather than assuming a layout.
single = sorted(W.rglob("*.safetensors"))
is_diffusers = (W / "model_index.json").exists()
sub = sorted(p.parent for p in W.rglob("model_index.json")) if not is_diffusers else []
print("layout:", "diffusers" if is_diffusers else (f"nested diffusers: {sub[:2]}" if sub
      else f"{len(single)} safetensors file(s)"))
if not is_diffusers and not sub and not single:
    print("TREE:", [str(p.relative_to(W)) for p in list(W.rglob("*"))[:40]])
for f in single[:5]:
    print("  ", f.relative_to(W), f"{f.stat().st_size/1e9:.2f} GB")
"""),

        nb.code("""
import torch
from diffusers import StableDiffusionXLPipeline

# T4/P100 are pre-Ampere: no bfloat16. float16 throughout.
DTYPE = torch.float16

if is_diffusers:
    src, loader = str(W), StableDiffusionXLPipeline.from_pretrained
elif sub:
    src, loader = str(sub[0]), StableDiffusionXLPipeline.from_pretrained
elif single:
    src, loader = str(single[0]), StableDiffusionXLPipeline.from_single_file
else:
    raise SystemExit(f"No SDXL weights found under {W}")

t0 = time.time()
kw = dict(torch_dtype=DTYPE, use_safetensors=True)
if loader is StableDiffusionXLPipeline.from_pretrained:
    kw["local_files_only"] = True          # from_single_file has no such kwarg
pipe = loader(src, **kw)
pipe = pipe.to("cuda")
pipe.enable_attention_slicing()            # SDXL fp16 fits a 16GB T4 with this
pipe.set_progress_bar_config(disable=True)
print(f"loaded in {time.time()-t0:.0f}s from {src}")
"""),

        nb.code("""
OUT = Path("/kaggle/working")
made = []
for seed in CFG["seeds"]:
    g = torch.Generator("cuda").manual_seed(int(seed))
    t0 = time.time()
    img = pipe(prompt=CFG["prompt"], negative_prompt=CFG["negative"],
               width=1024, height=1024,
               num_inference_steps=CFG["steps"],
               guidance_scale=CFG["guidance"], generator=g).images[0]
    f = OUT / f"portrait_seed{seed}.png"
    img.save(f)
    made.append((seed, f))
    print(f"seed {seed}: {time.time()-t0:.0f}s -> {f.name}")
"""),

        nb.code("""
# One contact sheet so the four can be judged side by side, plus a thumbnail
# strip: a face that works full-screen can still fail at thumbnail size.
from PIL import Image

ims = [Image.open(f) for _, f in made]
if ims:
    n, w = len(ims), 512
    sheet = Image.new("RGB", (w * n, w + 128), (16, 20, 28))
    for i, im in enumerate(ims):
        sheet.paste(im.resize((w, w), Image.LANCZOS), (i * w, 0))
        sheet.paste(im.resize((112, 112), Image.LANCZOS), (i * w + 8, w + 8))
    sheet.save(OUT / "contact_sheet.png")
    print("contact_sheet.png", sheet.size)

with open(OUT / "portraits.json", "w") as fh:
    json.dump({"prompt": CFG["prompt"], "negative": CFG["negative"],
               "steps": CFG["steps"], "guidance": CFG["guidance"],
               "seeds": [s for s, _ in made],
               "files": [f.name for _, f in made]}, fh, indent=2)
print("done:", [f.name for _, f in made])
"""),
    ]
    return nb.write(cells, out_path)


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from studio import config, presenter as presmod
    ref, mount = config.portrait_weights()
    out = build(Path("/tmp/portrait.ipynb"), presmod.load(), mount,
                seeds=[11, 22, 33, 44])
    print(f"wrote {out}  ({out.stat().st_size/1024:.1f} KB, limit ~1 MB)")
