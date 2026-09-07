"""Read a video's build_body.py without rendering it.

Importing the module is enough: the render only happens under its
`if __name__ == "__main__"` guard, so tools can read SHOTS, HOOK and CLOSE
without side effects.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

from . import config


def load(topic: str) -> ModuleType:
    path = config.video_dir(topic) / "body" / "build_body.py"
    if not path.exists():
        raise SystemExit(f"No {path}.\n  Create it with:  python tools/new_video.py {topic}")
    spec = importlib.util.spec_from_file_location(f"_script_{topic}", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"Could not load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if not hasattr(mod, "SHOTS"):
        raise SystemExit(f"{path} defines no SHOTS list")
    return mod


def lines(topic: str) -> list[str]:
    return [s["say"].strip() for s in load(topic).SHOTS]
