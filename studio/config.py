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
    ref = validate_ref(ref, "footage weights ref")
    return ref, cfg.get("footage_weights_dir") or mount_for(ref)


PLACEHOLDERS = {"owner/slug", "owner/name", "user/slug", "your/dataset"}


def validate_ref(ref: str, what: str) -> str:
    """Reject a ref that was never really set.

    The docs have to show the shape somewhere, and "owner/slug" is what gets
    pasted. Kaggle then accepts the push and the kernel dies attaching a
    dataset that does not exist, which costs a run to discover.
    """
    ref = (ref or "").strip().strip("/")
    if ref.lower() in PLACEHOLDERS:
        raise SystemExit(
            f"{ref!r} is the placeholder from the docs, not a real {what}.\n"
            f"Find one:  kaggle models list -s sdxl\n"
            f"           kaggle datasets list -s 'stable diffusion xl'\n"
            f"then pass the ref exactly as the 'ref' column prints it.")
    parts = ref.split("/")
    if len(parts) < 2 or not all(parts):
        raise SystemExit(
            f"{ref!r} is not a valid {what}. Expected 'owner/name' for a Kaggle "
            f"dataset, or 'owner/model/framework/variation/version' for a Kaggle "
            f"model.")
    return ref


def is_model_ref(ref: str) -> bool:
    """Kaggle models carry framework/variation/version; datasets are owner/name."""
    return len(ref.strip("/").split("/")) >= 3


def mount_for(ref: str) -> str:
    """Where Kaggle mounts an attached source inside the kernel."""
    parts = ref.strip("/").split("/")
    # datasets land under their slug; models keep their whole path below the name
    return "/kaggle/input/" + ("/".join(parts[1:]) if is_model_ref(ref) else parts[-1])


def portrait_weights() -> tuple[str, str]:
    """Where the SDXL portrait weights live on Kaggle.

    Same policy as footage_weights: a Kaggle dataset, never Hugging Face. A
    photoreal SDXL checkpoint in diffusers layout, or a single-file .safetensors
    the notebook loads with from_single_file.

    Set it with:
      python tools/setup_check.py --set-portrait-weights owner/slug
    """
    cfg = load()
    ref = (os.environ.get("STUDIO_PORTRAIT_DATASET")
           or cfg.get("portrait_weights_dataset"))
    if not ref:
        raise SystemExit(
            "No portrait weights dataset configured.\n"
            "  Set it with:  python tools/setup_check.py --set-portrait-weights owner/slug\n"
            "It must be a KAGGLE dataset holding an SDXL checkpoint -- this project\n"
            "does not use Hugging Face. Search Kaggle Models for 'stable diffusion xl',\n"
            "or mirror a checkpoint into your own private Kaggle dataset.")
    ref = validate_ref(ref, "portrait weights ref")
    return ref, cfg.get("portrait_weights_dir") or mount_for(ref)


KOKORO_MODEL = "kokoro-v1.0.onnx"
KOKORO_VOICES = "voices-v1.0.bin"


def kokoro_files() -> tuple[Path | None, Path | None, list[Path]]:
    """Find the Kokoro ONNX model and voices file.

    They are ~310 MB and ~26 MB and are shared by every video, so they live
    once at the project root -- never per video. STUDIO_KOKORO_DIR overrides,
    for a shared drive or a cache outside the repo.

    Returns (model, voices, searched) with None for anything missing, so the
    caller can name the exact directories it looked in.
    """
    searched = []
    env = os.environ.get("STUDIO_KOKORO_DIR")
    if env:
        searched.append(Path(env).expanduser())
    searched += [ROOT, ROOT / "assets" / "kokoro"]

    model = voices = None
    for d in searched:
        if model is None and (d / KOKORO_MODEL).is_file():
            model = d / KOKORO_MODEL
        if voices is None and (d / KOKORO_VOICES).is_file():
            voices = d / KOKORO_VOICES
    return model, voices, searched


def video_dir(topic: str) -> Path:
    return VIDEOS / topic
