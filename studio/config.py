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


def footage_weights() -> tuple[str, str]:
    """Where the video-model weights live on Kaggle.

    Deliberately NOT Hugging Face. Returns (dataset_ref, mount_path) where
    dataset_ref is "owner/slug" of a Kaggle dataset holding the weights, and
    mount_path is where the kernel will see them.

    Set both with:
      python tools/setup_check.py --set-weights owner/slug
    """
    cfg = load()
    ref = os.environ.get("STUDIO_WEIGHTS_DATASET") or cfg.get("footage_weights_dataset")
    if not ref:
        raise SystemExit(
            "No footage weights dataset configured.\n"
            "  Set it with:  python tools/setup_check.py --set-weights owner/slug\n"
            "It must be a KAGGLE dataset holding the model weights -- this project\n"
            "does not use Hugging Face. Mirror the weights into your own private\n"
            "Kaggle dataset if no public one exists.")
    mount = cfg.get("footage_weights_dir") or f"/kaggle/input/{ref.split('/')[-1]}"
    return ref, mount


def video_dir(topic: str) -> Path:
    return VIDEOS / topic
