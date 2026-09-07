"""The recurring presenter, and the Flow prompts generated from it.

Flow has no public API, so these prompts are meant to be pasted into the Flow
UI by hand. Generating them from one presenter.json is what stops the room and
the face drifting from video to video.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import config

SETTINGS = [
    "Model: Veo 3.1 Fast  (never Veo Quality)",
    "Outputs: x1",
    "Aspect: 16:9",
    "Your Maya character attached",
    "Confirm-before-generating: Always -- click Approve, never 'Always approve'",
    "Retry a bad clip ONCE at most",
]


def load() -> dict:
    path = config.ROOT / "presenter.json"
    if not path.exists():
        raise SystemExit(f"No {path}. Copy presenter.json from the repo and fill it in.")
    p = json.loads(path.read_text(encoding="utf-8"))
    missing = [k for k in ("name", "appearance", "room", "camera", "lighting")
               if not p.get(k)]
    if missing:
        raise SystemExit(f"presenter.json is missing: {', '.join(missing)}")
    return p


def prompt(kind: str, line: str, p: dict | None = None) -> str:
    """Build the Flow prompt for the hook or the close."""
    p = p or load()
    beat = ("She opens the video, hooking the viewer straight away."
            if kind == "hook" else
            "She closes the video, signing off warmly.")
    return (
        f"{p['appearance']}, wearing {p['wardrobe']}, sitting in {p['room']}. "
        f"{p['camera']}. {p['lighting']}. "
        f"She speaks directly to camera, {p['delivery']}. {beat} "
        f"She says: \"{line.strip()}\"\n\n"
        f"Audio: {p['audio']}. No on-screen text. No captions."
    )


def sheet(hook_line: str, close_line: str, topic: str) -> str:
    p = load()
    out = [
        f"=== Flow prompts: {topic} ===",
        f"Presenter: {p['name']}   (from presenter.json)",
        "",
        "Settings for BOTH clips:",
        *[f"  - {s}" for s in SETTINGS],
        "",
        "-" * 68,
        "HOOK  (save as videos/%s/flow/hook.mp4)" % topic,
        "-" * 68,
        prompt("hook", hook_line, p),
        "",
        "-" * 68,
        "CLOSE  (save as videos/%s/flow/close.mp4)" % topic,
        "-" * 68,
        prompt("close", close_line, p),
        "",
        "-" * 68,
        "Roughly 40 credits and 10 minutes. When both files are in place, the",
        "watcher picks them up and runs the rest on its own.",
    ]
    return "\n".join(out)


def write_sheet(topic: str, hook_line: str, close_line: str) -> Path:
    vdir = config.video_dir(topic)
    vdir.mkdir(parents=True, exist_ok=True)
    path = vdir / "flow_prompts.txt"
    path.write_text(sheet(hook_line, close_line, topic) + "\n", encoding="utf-8")
    return path
