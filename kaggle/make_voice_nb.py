"""Generate the Chatterbox voice-clone notebook for one video.

The notebook clones the Flow presenter's voice from a 15-second reference and
narrates every line of the body, then zips voice.wav + times.json + one wav per
line back to /kaggle/working.

Why the notebook looks the way it does -- each of these cost someone a run:

* torch/torchaudio/torchvision are pinned and torchcodec is removed first. The
  stock Kaggle image ships a combination that breaks chatterbox on import.
* Everything heavy is built under /kaggle/tmp. Only the final zip lands in
  /kaggle/working, so the download stays small.
* Kaggle exports PYTHONPATH=/kaggle/lib/kagglegym:/kaggle/lib, which shadows a
  venv's numpy. If you ever need an isolated env here, create it with
  --system-site-packages --without-pip: the 3.12 image has no working ensurepip.
* The reference audio arrives as an attached private dataset, not embedded in
  the notebook -- the push limit is about 1 MB.
* This is a clone of a SYNTHETIC Flow voice. Never upload a real person's
  voice or photo to Kaggle.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nb  # noqa: E402

GAP = 0.38          # seconds of silence between lines; matches studio/voice.py


def build(out_path: Path, lines: list[str], dataset_slug: str,
          ref_name: str = "ref.flac", exaggeration: float = 0.5,
          cfg_weight: float = 0.5) -> Path:
    cells = [
        nb.md(f"""
# Voice clone -- {out_path.stem}

Clones the presenter's Flow voice from a 15 s reference and narrates
{len(lines)} lines. Expect roughly 8 minutes on a T4.

Output: `/kaggle/working/voice.zip` containing `voice.wav`, `times.json`
and one wav per line.
"""),
        nb.code(f"""
# --- 1. environment ---------------------------------------------------------
# Pin order matters. torchcodec must go first: the stock image ships a build
# that breaks chatterbox's audio loading on import.
import subprocess, sys, os, time
t0 = time.time()

def sh(cmd):
    print("$", " ".join(cmd), flush=True)
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout[-3000:]); print(r.stderr[-3000:], file=sys.stderr)
        raise SystemExit(f"command failed: {{' '.join(cmd)}}")
    return r.stdout

sh([sys.executable, "-m", "pip", "uninstall", "-y", "torchcodec"])
sh([sys.executable, "-m", "pip", "install", "-q",
    "torch==2.6.0", "torchaudio==2.6.0", "torchvision==0.21.0"])
sh([sys.executable, "-m", "pip", "install", "-q", "chatterbox-tts"])

# Build under /kaggle/tmp so the downloadable output stays small.
os.makedirs("/kaggle/tmp/out", exist_ok=True)
os.environ["HF_HOME"] = "/kaggle/tmp/hf"
print(f"env ready in {{time.time()-t0:.0f}}s", flush=True)
"""),
        nb.code(f"""
# --- 2. sanity: GPU + reference clip ----------------------------------------
import glob, torch
print("torch", torch.__version__, "cuda", torch.cuda.is_available())
assert torch.cuda.is_available(), "No GPU. Set the accelerator to GPU on this kernel."

REF_CANDIDATES = sorted(glob.glob("/kaggle/input/**/{ref_name}", recursive=True))
assert REF_CANDIDATES, (
    "Reference clip not found. The private dataset '{dataset_slug}' should be "
    "attached to this kernel and contain {ref_name}.")
REF = REF_CANDIDATES[0]
print("reference:", REF, os.path.getsize(REF), "bytes")
"""),
        nb.code("LINES = " + json.dumps(lines, indent=1, ensure_ascii=False)
                + f"\nprint(len(LINES), 'lines to narrate')"),
        nb.code(f"""
# --- 3. clone and narrate ---------------------------------------------------
import json, numpy as np, torchaudio as ta
from chatterbox.tts import ChatterboxTTS

model = ChatterboxTTS.from_pretrained(device="cuda")
SR = model.sr
GAP = {GAP}
gap = np.zeros(int(GAP * SR), dtype=np.float32)

pieces, times, t = [], [], 0.0
for i, line in enumerate(LINES):
    wav = model.generate(line, audio_prompt_path=REF,
                         exaggeration={exaggeration}, cfg_weight={cfg_weight})
    a = wav.squeeze(0).detach().cpu().numpy().astype("float32")
    ta.save(f"/kaggle/tmp/out/s{{i:03d}}.wav", wav.detach().cpu(), SR)
    dur = len(a) / SR
    times.append({{"i": i, "text": line, "start": round(t, 3), "end": round(t + dur, 3)}})
    pieces += [a, gap]
    t += dur + GAP
    print(f"  [{{i+1}}/{{len(LINES)}}] {{dur:5.2f}}s  {{line[:60]}}", flush=True)

full = np.concatenate(pieces)
total = len(full) / SR
import torch as _t
ta.save("/kaggle/tmp/out/voice.wav", _t.from_numpy(full).unsqueeze(0), SR)
with open("/kaggle/tmp/out/times.json", "w") as f:
    json.dump({{"sentences": times, "total": round(total, 3), "sr": SR}}, f, indent=2)
print(f"\\ntotal narration: {{total:.1f}}s ({{total/60:.1f}} min) at {{SR}} Hz")
"""),
        nb.code("""
# --- 4. hand it back --------------------------------------------------------
import shutil, os
zip_base = "/kaggle/working/voice"
shutil.make_archive(zip_base, "zip", "/kaggle/tmp/out")
size = os.path.getsize(zip_base + ".zip")
print(f"WROTE {zip_base}.zip  ({size/1e6:.1f} MB)")
print("VOICE JOB OK")
"""),
    ]
    return nb.write(cells, out_path)


if __name__ == "__main__":
    demo = ["This is the first line.", "And this is the second."]
    print(build(Path(sys.argv[1] if len(sys.argv) > 1 else "build/voice.ipynb"),
                demo, "someuser/demo-inputs"))
