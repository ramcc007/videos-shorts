#!/usr/bin/env python3
"""Run a notebook on Kaggle with no browser: push, poll, download.

    python tools/kaggle_run.py --job smoke
    python tools/kaggle_run.py --job voice --topic home-batteries
    python tools/kaggle_run.py --notebook nb.ipynb --slug my-job --inputs dir/ --out out/

Notes that cost real time to learn -- change these only with evidence:

* kernels_status() takes ONE "user/slug" string and returns an OBJECT, not a
  dict. Read .status; it is an enum, so str(x).split('.')[-1] gives
  "RUNNING" / "COMPLETE" / "ERROR".
* Kaggle publishes kernel output ONLY when the run finishes. Do not try to
  fetch the log mid-run -- on an empty file list it raises IndexError. Poll
  status and print elapsed minutes instead.
* PYTHONUTF8=1 / PYTHONIOENCODING=utf-8 keep the Kaggle CLI from mangling its
  log output on Windows.
* A batch "Save Version" run stops itself, so there is no session left open
  and no quota leak.
* The notebook push limit is about 1 MB, so inputs ride along as a private
  dataset instead of being embedded.

This script never reads, prints or copies your API token.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from studio import config, script  # noqa: E402

# Windows: keep our own stdout and any child CLI from mangling Kaggle's logs.
os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

POLL_SECONDS = 20
TERMINAL = {"COMPLETE", "ERROR", "CANCEL_REQUESTED", "CANCEL_ACKNOWLEDGED", "CANCELLED"}


def child_env() -> dict:
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def api():
    try:
        from kaggle.api.kaggle_api_extended import KaggleApi
    except ImportError:
        raise SystemExit("pip install kaggle")
    a = KaggleApi()
    try:
        a.authenticate()
    except Exception as e:                       # noqa: BLE001 -- surface the real cause
        raise SystemExit(
            f"Kaggle authentication failed: {e}\n"
            "Put your token at ~/.kaggle/kaggle.json (Settings -> API -> Create New Token).\n"
            "Never copy it into this project folder.")
    return a


def status_of(a, ref: str) -> tuple[str, str]:
    """kernels_status returns an object whose .status is an enum."""
    resp = a.kernels_status(ref)
    raw = getattr(resp, "status", resp)
    name = str(raw).split(".")[-1].upper()
    message = getattr(resp, "failure_message", "") or getattr(resp, "failureMessage", "") or ""
    return name, message


# --------------------------------------------------------------------------- #
def push_dataset(a, user: str, slug: str, src: Path, staging: Path) -> str:
    """Upload inputs as a PRIVATE dataset so the notebook can read them."""
    ref = f"{user}/{slug}"
    staging.mkdir(parents=True, exist_ok=True)
    for f in staging.iterdir():
        f.unlink() if f.is_file() else shutil.rmtree(f)
    for f in src.iterdir():
        if f.is_file():
            shutil.copy2(f, staging / f.name)

    (staging / "dataset-metadata.json").write_text(json.dumps({
        "title": slug.replace("-", " ")[:50],
        "id": ref,
        "licenses": [{"name": "CC0-1.0"}],
    }, indent=2), encoding="utf-8")

    exists = True
    try:
        a.dataset_status(ref)
    except Exception:                            # noqa: BLE001
        exists = False

    print(f"[kaggle] {'new version of' if exists else 'creating'} private dataset {ref}")
    if exists:
        a.dataset_create_version(str(staging), version_notes="pipeline update", quiet=True)
    else:
        a.dataset_create_new(str(staging), public=False, quiet=True)

    for _ in range(60):                          # datasets take a moment to become readable
        try:
            if str(a.dataset_status(ref)).lower() == "ready":
                print(f"[kaggle] dataset {ref} ready")
                return ref
        except Exception:                        # noqa: BLE001
            pass
        time.sleep(5)
    print(f"[kaggle] WARNING: dataset {ref} not confirmed ready; continuing anyway")
    return ref


def push_kernel(a, user: str, slug: str, notebook: Path, staging: Path,
                gpu: bool, internet: bool, dataset_refs: list[str]) -> str:
    ref = f"{user}/{slug}"
    staging.mkdir(parents=True, exist_ok=True)
    code_file = staging / notebook.name
    shutil.copy2(notebook, code_file)

    meta = {
        "id": ref,
        "title": slug.replace("-", " ")[:50],
        "code_file": notebook.name,
        "language": "python",
        "kernel_type": "notebook",
        "is_private": True,
        "enable_gpu": bool(gpu),
        "enable_tpu": False,
        "enable_internet": bool(internet),
        "dataset_sources": dataset_refs,
        "competition_sources": [],
        "kernel_sources": [],
        "model_sources": [],
    }
    (staging / "kernel-metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    size = code_file.stat().st_size
    if size > 900_000:
        raise SystemExit(f"{notebook.name} is {size/1e6:.1f} MB; the push limit is about 1 MB. "
                         "Make the notebook download its inputs instead of embedding them.")
    print(f"[kaggle] pushing {ref}  (gpu={gpu} internet={internet} "
          f"datasets={dataset_refs or 'none'}, {size/1024:.0f} KB)")
    a.kernels_push(str(staging))
    return ref


def wait(a, ref: str, timeout_min: int) -> str:
    print(f"[kaggle] running {ref} -- https://www.kaggle.com/code/{ref}")
    print("[kaggle] output is only published when the run finishes, so we poll status.")
    start = time.time()
    last = None
    while True:
        elapsed = (time.time() - start) / 60
        if elapsed > timeout_min:
            raise SystemExit(f"[kaggle] gave up after {timeout_min} min; the kernel may still "
                             f"be running: https://www.kaggle.com/code/{ref}")
        try:
            state, message = status_of(a, ref)
        except Exception as e:                   # noqa: BLE001 -- transient API hiccups
            print(f"  [{elapsed:5.1f} min] status unavailable ({e}); retrying")
            time.sleep(POLL_SECONDS)
            continue

        if state != last:
            print(f"  [{elapsed:5.1f} min] {state}")
            last = state
        elif int(elapsed * 60) % 60 < POLL_SECONDS:
            print(f"  [{elapsed:5.1f} min] still {state}")

        if state in TERMINAL:
            if state != "COMPLETE":
                raise SystemExit(f"[kaggle] kernel finished as {state}. {message}\n"
                                 f"Open the log: https://www.kaggle.com/code/{ref}")
            print(f"[kaggle] COMPLETE in {elapsed:.1f} min")
            return state
        time.sleep(POLL_SECONDS)


def download(a, ref: str, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"[kaggle] downloading output -> {out_dir}")
    a.kernels_output(ref, str(out_dir), force=True, quiet=False)
    got = sorted(p.name for p in out_dir.iterdir())
    print(f"[kaggle] got: {', '.join(got) if got else '(nothing)'}")
    if not got:
        raise SystemExit("[kaggle] the run produced no output files. Check the notebook's "
                         "final cell writes into /kaggle/working.")
    return out_dir


def run(notebook: Path, slug: str, out_dir: Path, inputs: Path | None,
        gpu: bool, internet: bool, timeout_min: int) -> Path:
    user = config.kaggle_username()
    a = api()
    staging = config.ROOT / "build" / "_staging" / slug
    dataset_refs = []
    if inputs is not None:
        dataset_refs.append(
            push_dataset(a, user, f"{slug}-inputs", inputs, staging.parent / f"{slug}-inputs"))
    ref = push_kernel(a, user, slug, notebook, staging, gpu, internet, dataset_refs)
    wait(a, ref, timeout_min)
    return download(a, ref, out_dir)


# --------------------------------------------------------------------------- #
def job_smoke(args) -> None:
    sys.path.insert(0, str(config.ROOT / "kaggle"))
    import make_smoke_nb
    nb_path = config.ROOT / "build" / "smoke.ipynb"
    make_smoke_nb.build(nb_path)
    out = run(nb_path, "studio-smoke", config.ROOT / "build" / "smoke_out",
              None, gpu=True, internet=True, timeout_min=args.timeout)
    smoke = out / "smoke.json"
    if smoke.exists():
        print("\nsmoke.json:", smoke.read_text().strip())
    print("\nSmoke test passed. kaggle_run.py works end to end.")


def job_voice(args) -> None:
    if not args.topic:
        raise SystemExit("--job voice needs --topic <name>")
    vdir = config.video_dir(args.topic)
    lines = script.lines(args.topic)             # imports build_body.py, renders nothing
    print(f"[voice] {len(lines)} lines from {vdir / 'body' / 'build_body.py'}")

    ref = vdir / "voice" / "ref.flac"
    if not ref.exists():
        raise SystemExit(f"No reference clip at {ref}.\n"
                         f"  Make one:  python tools/cut_voice_ref.py --topic {args.topic}")

    sys.path.insert(0, str(config.ROOT / "kaggle"))
    import make_voice_nb
    slug = f"voice-{args.topic}"[:48]
    nb_path = config.ROOT / "build" / f"{slug}.ipynb"
    make_voice_nb.build(nb_path, lines, f"{config.kaggle_username()}/{slug}-inputs")

    out = run(nb_path, slug, vdir / "body" / "kaggle_out", ref.parent,
              gpu=True, internet=True, timeout_min=args.timeout)
    print(f"\nVoice ready. Now run:\n"
          f"  python videos/{args.topic}/body/build_body.py --reuse-voice")
    print(f"(output in {out})")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--job", choices=("smoke", "voice"), help="a canned job")
    p.add_argument("--topic", help="video topic, for --job voice")
    p.add_argument("--notebook", type=Path, help="run an arbitrary notebook")
    p.add_argument("--slug", help="kernel slug for --notebook")
    p.add_argument("--inputs", type=Path, help="folder to upload as a private dataset")
    p.add_argument("--out", type=Path, help="where to put the output")
    p.add_argument("--no-gpu", action="store_true")
    p.add_argument("--no-internet", action="store_true")
    p.add_argument("--timeout", type=int, default=45, help="minutes before giving up")
    args = p.parse_args()

    if args.job == "smoke":
        return job_smoke(args)
    if args.job == "voice":
        return job_voice(args)
    if not (args.notebook and args.slug and args.out):
        p.error("give --job, or all of --notebook --slug --out")
    run(args.notebook, args.slug, args.out, args.inputs,
        gpu=not args.no_gpu, internet=not args.no_internet, timeout_min=args.timeout)


if __name__ == "__main__":
    main()
