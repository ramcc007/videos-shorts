"""The trivial notebook that proves kaggle_run.py works end to end.

Prints nvidia-smi and writes a file to /kaggle/working so the download path is
exercised too. Run this BEFORE trusting the voice job with 8 GPU minutes.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nb  # noqa: E402


def build(out_path: Path) -> Path:
    cells = [
        nb.md("# Smoke test\nProves: GPU attached, notebook runs headless, output comes back."),
        nb.code("""
import subprocess, json, sys, platform, datetime

print("python:", sys.version)
print("platform:", platform.platform())
print("utc:", datetime.datetime.utcnow().isoformat())

try:
    smi = subprocess.run(["nvidia-smi"], capture_output=True, text=True, timeout=60)
    print(smi.stdout or smi.stderr)
    gpu_ok = smi.returncode == 0
except Exception as e:
    print("nvidia-smi failed:", e)
    gpu_ok = False

try:
    import torch
    print("torch:", torch.__version__, "cuda:", torch.cuda.is_available())
    if torch.cuda.is_available():
        print("device:", torch.cuda.get_device_name(0))
except Exception as e:
    print("torch not importable:", e)

with open("/kaggle/working/smoke.json", "w") as f:
    json.dump({"gpu_ok": gpu_ok, "python": sys.version}, f, indent=2)
print("\\nWROTE /kaggle/working/smoke.json")
print("SMOKE TEST OK" if gpu_ok else "SMOKE TEST RAN, BUT NO GPU -- check the accelerator setting")
"""),
    ]
    return nb.write(cells, out_path)


if __name__ == "__main__":
    dest = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("build/smoke.ipynb")
    print(build(dest))
