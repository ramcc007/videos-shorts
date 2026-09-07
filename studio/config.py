"""Project paths and credential-free configuration.

Rule: this module never reads, prints or copies a Kaggle API token. It only
resolves your *username*, which is not a secret.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VIDEOS = ROOT / "videos"
ASSETS = ROOT / "assets"
CONFIG_FILE = ROOT / "config.json"          # git-ignored
LEGACY_KAGGLE_JSON = Path.home() / ".kaggle" / "kaggle.json"


def load() -> dict:
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    return {}


def save(cfg: dict) -> None:
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")


def kaggle_username() -> str:
    """Resolve the Kaggle username. Never guessed -- only read from a place
    you put it.

    Order: STUDIO_KAGGLE_USER env -> config.json -> ~/.kaggle/kaggle.json.
    """
    env = os.environ.get("STUDIO_KAGGLE_USER") or os.environ.get("KAGGLE_USERNAME")
    if env:
        return env.strip()

    cfg = load()
    if cfg.get("kaggle_username"):
        return str(cfg["kaggle_username"]).strip()

    # The legacy token file carries the username alongside the key. We read the
    # username field only and never touch or echo "key".
    if LEGACY_KAGGLE_JSON.exists():
        try:
            data = json.loads(LEGACY_KAGGLE_JSON.read_text(encoding="utf-8"))
            if data.get("username"):
                return str(data["username"]).strip()
        except (json.JSONDecodeError, OSError):
            pass

    raise SystemExit(
        "Kaggle username not set.\n"
        "  Fix with:  python tools/setup_check.py --set-kaggle-user <your-username>\n"
        "  (or export STUDIO_KAGGLE_USER=<your-username>)\n"
        "It is read from config.json / ~/.kaggle/kaggle.json -- never guessed."
    )


def video_dir(topic: str) -> Path:
    return VIDEOS / topic
