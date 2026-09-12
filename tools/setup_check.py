#!/usr/bin/env python3
"""Preflight: does this machine have everything the pipeline needs?

    python tools/setup_check.py
    python tools/setup_check.py --set-kaggle-user yourname

Checks only. It never reads or prints the contents of your API token -- it
reports whether a credential file exists, nothing more.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from studio import config  # noqa: E402

OK, WARN, BAD = "  ok  ", " warn ", " MISS "


def line(state: str, name: str, detail: str = "") -> None:
    print(f"[{state}] {name:<26} {detail}")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--set-kaggle-user", metavar="NAME",
                   help="store your Kaggle username in config.json (git-ignored)")
    p.add_argument("--set-portrait-weights", metavar="OWNER/SLUG",
                   help="Kaggle dataset holding the SDXL portrait checkpoint")
    p.add_argument("--set-weights", metavar="OWNER/SLUG",
                   help="Kaggle dataset holding the video-model weights "
                        "(this project does not use Hugging Face)")
    args = p.parse_args()

    if args.set_portrait_weights:
        cfg = config.load()
        ref = config.validate_ref(args.set_portrait_weights, "portrait weights ref")
        cfg["portrait_weights_dataset"] = ref
        cfg["portrait_weights_dir"] = config.mount_for(ref)
        config.save(cfg)
        kind = "model" if config.is_model_ref(ref) else "dataset"
        print(f"Portrait weights {kind}: {ref}")
        print(f"Mounts at:            {cfg['portrait_weights_dir']}")
        return 0

    if args.set_weights:
        cfg = config.load()
        ref = config.validate_ref(args.set_weights, "footage weights ref")
        cfg["footage_weights_dataset"] = ref
        cfg["footage_weights_dir"] = config.mount_for(ref)
        config.save(cfg)
        print(f"Weights source:  {cfg['footage_weights_dataset']}")
        print(f"Mounts at:       {cfg['footage_weights_dir']}")
        return 0

    if args.set_kaggle_user:
        cfg = config.load()
        cfg["kaggle_username"] = args.set_kaggle_user.strip()
        config.save(cfg)
        print(f"Wrote kaggle_username={cfg['kaggle_username']} to {config.CONFIG_FILE}")
        print("(config.json is git-ignored -- it holds no secrets, only your username.)")
        return 0

    problems = 0
    print("\n--- preflight " + "-" * 50)

    v = sys.version_info
    if (v.major, v.minor) >= (3, 11):
        line(OK, "python", f"{v.major}.{v.minor}.{v.micro}")
    else:
        line(BAD, "python", f"{v.major}.{v.minor} -- need 3.11+"); problems += 1

    for exe in ("ffmpeg", "ffprobe"):
        path = shutil.which(exe)
        if path:
            ver = subprocess.run([exe, "-version"], capture_output=True, text=True
                                 ).stdout.splitlines()[0].split(" version ")[-1].split()[0]
            line(OK, exe, f"{ver}")
        else:
            line(BAD, exe, "not on PATH"); problems += 1

    for mod, why in (("PIL", "charts and cards"), ("requests", "Wikimedia photos"),
                     ("numpy", "kokoro narration"), ("soundfile", "narration wavs"),
                     ("kaggle", "GPU voice job")):
        try:
            # the kaggle package prints a wall of auth help on import when it
            # has no credentials yet; we only want to know it is installed
            with contextlib.redirect_stdout(io.StringIO()), \
                 contextlib.redirect_stderr(io.StringIO()):
                __import__(mod)
            line(OK, mod, why)
        except ImportError:
            line(BAD, mod, f"missing -- see the install hint below ({why})"); problems += 1

    try:
        import kokoro_onnx  # noqa: F401
        model, voices, searched = config.kokoro_files()
        if model and voices:
            line(OK, "kokoro-onnx", f"local voice ready ({model.parent})")
        else:
            missing = [n for n, f in ((config.KOKORO_MODEL, model),
                                      (config.KOKORO_VOICES, voices)) if f is None]
            line(WARN, "kokoro-onnx",
                 f"package installed but {' and '.join(missing)} missing -- "
                 f"run: python tools/fetch_voice.py")
    except ImportError:
        line(WARN, "kokoro-onnx", "not installed -- drafts fall back to --voice silent")

    # credentials: existence only, never contents
    legacy = config.LEGACY_KAGGLE_JSON
    token = legacy.parent / "access_token"
    if legacy.exists() or token.exists():
        which = "kaggle.json" if legacy.exists() else "access_token"
        line(OK, "kaggle credentials", f"{which} present in ~/.kaggle (contents not read)")
    else:
        line(BAD, "kaggle credentials",
             "no ~/.kaggle/kaggle.json -- Kaggle Settings > API > Create New Token"); problems += 1

    try:
        line(OK, "kaggle username", config.kaggle_username())
    except SystemExit:
        line(BAD, "kaggle username",
             "not set -- python tools/setup_check.py --set-kaggle-user <name>"); problems += 1

    music = sorted((config.ASSETS / "music").glob("*"))
    beds = [m for m in music if m.suffix.lower() in (".mp3", ".m4a", ".wav", ".flac", ".ogg")]
    if beds:
        line(OK, "music bed", beds[0].name)
    else:
        line(WARN, "music bed", "none in assets/music -- renders will have no bed")

    try:
        from studio import theme
        if theme.font_path("bold"):
            line(OK, "fonts", Path(theme.font_path("bold")).name)
        else:
            line(BAD, "fonts", "no usable TTF found"); problems += 1
    except ImportError as e:
        # Pillow missing is already reported above; don't crash the report that
        # is meant to tell you what to install.
        line(BAD, "fonts", f"cannot check ({e.name} missing)"); problems += 1

    print("-" * 64)
    if problems:
        print(f"{problems} thing(s) to fix before the pipeline will run.")
        # Always spell out the interpreter: installing with a bare `pip` when
        # several Pythons are on PATH is the usual reason a package reads as
        # missing right after a successful install.
        exe = Path(sys.executable).name
        print(f'\nInstall into THIS interpreter ({sys.executable}):\n'
              f'  "{sys.executable}" -m pip install -r requirements.txt\n'
              f'  "{sys.executable}" -m pip install kokoro-onnx soundfile\n'
              f'\nA bare `pip` may belong to a different Python. '
              f'`{exe} -m pip` never does.')
        return 1
    print("All good. Next:  python tools/kaggle_run.py --job smoke")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
