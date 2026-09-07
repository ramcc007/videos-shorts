#!/usr/bin/env python3
"""Step 0: where can footage actually be generated?

    python tools/gpu_probe.py

Reports what this machine can do and recommends local generation or Kaggle.
Answer this before choosing a model -- it decides clip length, resolution and
how long each video takes.
"""
from __future__ import annotations

import platform
import shutil
import subprocess
import sys


def _smi() -> tuple[str, float] | None:
    if shutil.which("nvidia-smi") is None:
        return None
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=30).stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return None
    if not out:
        return None
    name, mem = out.splitlines()[0].split(",")
    return name.strip(), float(mem) / 1024.0


def main() -> int:
    print(f"\nplatform      {platform.platform()}")
    print(f"python        {sys.version.split()[0]}")

    gpu = _smi()
    torch_cuda = torch_mps = False
    try:
        import torch
        print(f"torch         {torch.__version__}")
        torch_cuda = torch.cuda.is_available()
        torch_mps = getattr(torch.backends, "mps", None) is not None \
            and torch.backends.mps.is_available()
    except ImportError:
        print("torch         not installed (pip install torch)")

    if gpu:
        name, vram = gpu
        print(f"gpu           {name}  ({vram:.0f} GB VRAM)")
        print(f"torch.cuda    {torch_cuda}")
        print()
        if vram >= 12:
            print("VERDICT: generate footage LOCALLY.")
            print("  Kaggle is then only needed for the voice clone.")
            print("  Target 1024x576 (16:9, divisible by 32), ~8 s clips.")
        elif vram >= 8:
            print("VERDICT: local generation is possible but tight.")
            print("  Use a smaller model and 704x384; push long jobs to Kaggle.")
        else:
            print(f"VERDICT: {vram:.0f} GB is not enough. Use Kaggle's free T4.")
        return 0

    if torch_mps:
        print("gpu           Apple Silicon (MPS)")
        print()
        print("VERDICT: test ONE clip before committing.")
        print("  MPS is solid for image models; video support is patchy and")
        print("  several video pipelines fall back to CPU silently. If a 5 s")
        print("  clip takes more than ~10 minutes, use Kaggle instead.")
        return 0

    print("gpu           none detected")
    print()
    print("VERDICT: use Kaggle's free T4. CPU-only generation is not viable")
    print("  -- it is hours per five-second clip, not minutes.")
    print("  Run: python tools/kaggle_run.py --job smoke")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
