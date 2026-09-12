"""Notebook that generates presenter portrait options on a Kaggle GPU.

Step 5 of the setup guide. The portrait it produces becomes the channel's
presenter: you pick one, register it as a Flow character, and every clip from
then on carries that face. So this generates several options in one run --
re-running costs another GPU slot, and comparing faces side by side beats
judging one in isolation.

The prompt is built from presenter.json, so the face matches the presenter the
rest of the pipeline already describes.

No Hugging Face: weights come from a Kaggle dataset or model attached to the
kernel, and HF_HUB_OFFLINE / TRANSFORMERS_OFFLINE / DIFFUSERS_OFFLINE are set so
an accidental reach for the Hub raises instead of silently downloading. If a
load fails, attach the right dataset -- never unset the flags.

Two rules about the cells below, both learned from failed GPU runs:
  * no cell source may contain a triple quote (it closes the literal carrying
    it) -- nb.code() enforces this;
  * no cell is an f-string, so a brace in notebook code cannot be interpolated
    at build time. CFG is injected by concatenation instead.
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
        "photorealistic head and shoulders portrait photograph of "
        + p["appearance"] + ", wearing " + p.get("wardrobe", "a plain jumper")
        + ", in " + p["room"] + ", " + p.get("lighting", "soft even lighting")
        + ", neutral friendly expression, looking directly into the camera, "
        "sharp focus on the eyes, 85mm portrait lens, shallow depth of field, "
        "natural skin texture with visible pores, documentary photography, "
        "colour photograph, centred composition"
    )


def build(out_path: Path, presenter: dict, weights_dir: str,
          seeds: list[int], steps: int = 34, guidance: float = 5.5) -> Path:
    cfg = json.dumps({"prompt": portrait_prompt(presenter), "negative": NEGATIVE,
                      "weights": weights_dir, "seeds": seeds, "steps": steps,
                      "guidance": guidance,
                      "name": presenter.get("name", "presenter")}, indent=2)
    q = chr(39) * 3          # a triple quote for the CFG literal, built not typed

    cells = [
        nb.md("# Presenter portraits\n"
              "Options for the channel's presenter. Pick one; it becomes permanent.\n\n"
              "Weights come from an attached **Kaggle source**, not Hugging Face."),

        nb.code("import json, os, sys, subprocess, time\n"
                "CFG = json.loads(r" + q + cfg + q + ")\n"
                "print('presenter:', CFG['name'])"),

        nb.code(r"""
# Offline by policy. A load failure here means the weights source is missing or
# laid out differently -- attach the right one, do NOT unset these.
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["DIFFUSERS_OFFLINE"] = "1"

# Pin the preinstalled torch while installing. Left free, the resolver can pull
# a newer build whose kernels no longer cover this machine's GPU, and that
# failure then surfaces deep inside a forward pass rather than here.
import torch
with open("/tmp/constraints.txt", "w") as f:
    f.write("torch==" + torch.__version__.split("+")[0] + "\n")
print("torch preinstalled:", torch.__version__)

subprocess.run([sys.executable, "-m", "pip", "install", "-q",
                "-c", "/tmp/constraints.txt",
                "diffusers", "transformers", "accelerate", "safetensors"], check=True)
"""),

        nb.code(r"""
# Check the GPU against what this torch was built for, BEFORE loading 7 GB of
# weights. A mismatch otherwise appears as "no kernel image is available for
# execution on the device" inside the first forward pass, which reads like a
# model bug rather than a build mismatch.
import torch
cap = torch.cuda.get_device_capability()
sm = "sm_" + str(cap[0]) + str(cap[1])
arches = torch.cuda.get_arch_list()
name = torch.cuda.get_device_name(0)
print("device:", name, " capability:", sm)
print("torch:", torch.__version__, " built for:", arches)
if sm not in arches:
    raise SystemExit(
        "This torch has no kernels for " + sm + " (" + name + ").\n"
        "It was built for: " + str(arches) + "\n"
        "Kaggle assigns either a P100 (sm_60) or a T4 (sm_75); this build does "
        "not cover the card allocated to this run.\n"
        "Fix: open the kernel on kaggle.com, set the accelerator to GPU T4 x2, "
        "save, and re-run -- or re-run to be assigned a different card.")
print("GPU and torch build are compatible.")
"""),

        nb.code(r"""
from pathlib import Path

W = Path(CFG["weights"])
if not W.exists():
    raise SystemExit(str(W) + " does not exist. Attach the SDXL weights source "
                     "to this kernel and re-run.")

# Kaggle models mount several levels deep (name/framework/variation/version), so
# search at any depth rather than assuming a layout.
single = sorted(W.rglob("*.safetensors"))
is_diffusers = (W / "model_index.json").exists()

# Prefer the base pipeline. A refiner is img2img-only and cannot start from a
# prompt, but it ships beside the base model in several datasets and sorts first
# alphabetically.
def _rank(p):
    n = p.name.lower()
    return (0 if "base" in n else 2 if "refiner" in n else 1, len(str(p)))

sub = sorted((q.parent for q in W.rglob("model_index.json")), key=_rank) if not is_diffusers else []
print("layout:", "diffusers" if is_diffusers else ("nested: " + str(sub[:2]) if sub
      else str(len(single)) + " safetensors file(s)"))
if not is_diffusers and not sub and not single:
    print("TREE:", [str(q.relative_to(W)) for q in list(W.rglob("*"))[:40]])
"""),

        nb.code(r"""
from diffusers import StableDiffusionXLPipeline

# T4 and P100 are both pre-Ampere: no bfloat16. float16 throughout.
if is_diffusers:
    src = str(W)
elif sub:
    if "refiner" in sub[0].name.lower():
        raise SystemExit("Only a refiner pipeline was found (" + sub[0].name +
                         "). A refiner cannot generate from a prompt on its own. "
                         "Attach a source containing the BASE model.")
    src = str(sub[0])
else:
    # from_single_file reads its pipeline config from the Hub, which the offline
    # flags block on purpose. The fix is a diffusers-layout source, never
    # unsetting the flags.
    raise SystemExit("Only a single-file checkpoint was found, and loading one "
                     "needs a config from huggingface.co, blocked here by policy. "
                     "Use a source in diffusers layout (model_index.json beside "
                     "unet/, vae/, text_encoder/).")

t0 = time.time()
pipe = StableDiffusionXLPipeline.from_pretrained(
    src, torch_dtype=torch.float16, use_safetensors=True, local_files_only=True)
pipe = pipe.to("cuda")
pipe.enable_attention_slicing()
pipe.set_progress_bar_config(disable=True)
print("loaded in", round(time.time() - t0), "s from", src)
"""),

        nb.code(r"""
OUT = Path("/kaggle/working")
made = []
for seed in CFG["seeds"]:
    g = torch.Generator("cuda").manual_seed(int(seed))
    t0 = time.time()
    img = pipe(prompt=CFG["prompt"], negative_prompt=CFG["negative"],
               width=1024, height=1024,
               num_inference_steps=CFG["steps"],
               guidance_scale=CFG["guidance"], generator=g).images[0]
    f = OUT / ("portrait_seed" + str(seed) + ".png")
    img.save(f)
    made.append((seed, f))
    print("seed", seed, ":", round(time.time() - t0), "s ->", f.name)
"""),

        nb.code(r"""
# One contact sheet so the options can be judged side by side, plus a thumbnail
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
    json.dump({"prompt": CFG["prompt"], "seeds": [s for s, _ in made],
               "steps": CFG["steps"], "guidance": CFG["guidance"],
               "files": [f.name for _, f in made]}, fh, indent=2)
print("done:", [f.name for _, f in made])
"""),
    ]
    return nb.write(cells, out_path)


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from studio import config, presenter as presmod
    ref, mount = config.portrait_weights()
    out = build(Path("/tmp/portrait.ipynb"), presmod.load(), mount, [11, 22, 33, 44])
    print("wrote " + str(out))
