"""Per-video state, so a failed step resumes instead of restarting."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from . import config

STEPS = ["brief", "script", "flow_prompts", "flow_clips", "fix_clips",
         "voice_ref", "voice_clone", "match_eq", "body", "stitch", "review"]


def path(topic: str) -> Path:
    return config.video_dir(topic) / "state.json"


def load(topic: str) -> dict:
    p = path(topic)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"topic": topic, "done": {}, "brief": {}}


def save(topic: str, st: dict) -> None:
    p = path(topic)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(st, indent=2) + "\n", encoding="utf-8")


def mark(topic: str, step: str, detail: str = "") -> dict:
    st = load(topic)
    st["done"][step] = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                        "detail": detail}
    save(topic, st)
    return st


def is_done(topic: str, step: str) -> bool:
    return step in load(topic).get("done", {})


def summary(topic: str) -> str:
    st = load(topic)
    rows = []
    for s in STEPS:
        d = st["done"].get(s)
        rows.append(f"  [{'x' if d else ' '}] {s:<14}"
                    + (f"{d['at']}  {d['detail']}" if d else ""))
    return "\n".join(rows)
