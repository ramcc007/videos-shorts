#!/usr/bin/env python3
"""Run a notebook on Kaggle with no browser: push, poll, download.

    python tools/kaggle_run.py --job smoke
    python tools/kaggle_run.py --job portrait
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
        # Kaggle models and datasets attach through different fields. A model
        # ref carries framework/variation/version; a dataset is owner/name.
        "dataset_sources": [r for r in dataset_refs if not config.is_model_ref(r)],
        "competition_sources": [],
        "kernel_sources": [],
        "model_sources": [r for r in dataset_refs if config.is_model_ref(r)],
    }
    (staging / "kernel-metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    size = code_file.stat().st_size
    if size > 900_000:
        raise SystemExit(f"{notebook.name} is {size/1e6:.1f} MB; the push limit is about 1 MB. "
                         "Make the notebook download its inputs instead of embedding them.")
    print(f"[kaggle] pushing {ref}  (gpu={gpu} internet={internet} "
          f"datasets={meta['dataset_sources'] or 'none'} "
          f"models={meta['model_sources'] or 'none'}, {size/1024:.0f} KB)")
    a.kernels_push(str(staging))
    return ref


def wait(a, ref: str, timeout_min: int, log_dir: Path | None = None) -> str:
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
                # An ERROR is still a finished run, so the log IS published --
                # fetch it. Sending someone to a browser for the traceback is
                # the worst moment to make them leave the terminal.
                print(f"[kaggle] kernel finished as {state}. {message}")
                tail = fetch_log(a, ref, log_dir)
                raise SystemExit(
                    (f"\n{tail}\n" if tail else "")
                    + f"[kaggle] full log: https://www.kaggle.com/code/{ref}")
            print(f"[kaggle] COMPLETE in {elapsed:.1f} min")
            return state
        time.sleep(POLL_SECONDS)


def fetch_log(a, ref: str, out_dir: Path | None, lines: int = 40) -> str:
    """Pull a failed kernel's log and return its tail.

    Best effort: a kernel that died before producing any output can raise here,
    and losing the real failure behind a secondary one helps nobody.
    """
    dest = (out_dir or config.ROOT / "build") / "failed"
    try:
        dest.mkdir(parents=True, exist_ok=True)
        a.kernels_output(ref, str(dest), force=True, quiet=True)
    except Exception as e:                       # noqa: BLE001
        return f"[kaggle] could not download the log ({e})."

    logs = sorted(dest.glob("*.log"))
    if not logs:
        return f"[kaggle] no log file published; saved what there was to {dest}"

    text = logs[-1].read_text(encoding="utf-8", errors="replace")
    # Kaggle logs are JSON-ish per-line records; pull the message bodies out.
    out = []
    for ln in text.splitlines():
        try:
            rec = json.loads(ln)
            out.append(str(rec.get("data", rec.get("text", ln))).rstrip())
        except (json.JSONDecodeError, TypeError):
            out.append(ln.rstrip())
    body = [l for l in out if l.strip()]
    head = f"--- last {min(lines, len(body))} log lines ({logs[-1]}) ---"
    return "\n".join([head, *body[-lines:]])


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
        gpu: bool, internet: bool, timeout_min: int,
        extra_datasets: list[str] | None = None) -> Path:
    user = config.kaggle_username()
    a = api()
    staging = config.ROOT / "build" / "_staging" / slug
    dataset_refs = list(extra_datasets or [])
    if inputs is not None:
        dataset_refs.append(
            push_dataset(a, user, f"{slug}-inputs", inputs, staging.parent / f"{slug}-inputs"))
    ref = push_kernel(a, user, slug, notebook, staging, gpu, internet, dataset_refs)
    wait(a, ref, timeout_min, out_dir)
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


def job_portrait(args) -> None:
    """Step 5: presenter portrait options, for a human to choose between."""
    ref, mount = config.portrait_weights()
    sys.path.insert(0, str(config.ROOT / "kaggle"))
    import make_portrait_nb
    from studio import presenter as presmod

    pres = presmod.load()
    seeds = ([int(x) for x in args.seeds.split(",")] if args.seeds
             else [11, 22, 33, 44])
    nb_path = config.ROOT / "build" / "portrait.ipynb"
    make_portrait_nb.build(nb_path, pres, mount, seeds)
    print(f"[portrait] {pres.get('name', 'presenter')}, seeds {seeds}")

    out = run(nb_path, "portrait", config.ROOT / "build" / "portrait_out",
              None, gpu=True, internet=True, timeout_min=args.timeout,
              extra_datasets=[ref])
    print(f"""
Portraits are in {out}. Open contact_sheet.png.

Judge them at BOTH sizes -- the sheet has a thumbnail strip along the bottom,
because a face that works full-screen can still fail as a thumbnail.

This choice is permanent: the face you pick becomes the channel's presenter and
appears in every video. If none is right, re-run with different seeds:
  python tools/kaggle_run.py --job portrait --seeds 7,101,202,303

When one is right, copy it somewhere OUTSIDE the project as a backup -- it
cannot be regenerated identically later -- then register it as a Flow character.""")


def job_footage_samples(args) -> None:
    """The quality gate: three clips, then a human looks at them."""
    ref, mount = config.footage_weights()
    sys.path.insert(0, str(config.ROOT / "kaggle"))
    import make_footage_nb

    prompts = [args.prompt] * 2 if args.prompt else [
        "a rocket rising through low cloud at dawn, slow push in, cinematic",
        "the curved edge of the earth from orbit, sunlight creeping across the terminator",
    ]
    prompts.append(args.prompt or
                   "a woman looking out of a spacecraft window, quiet, cinematic")

    nb_path = config.ROOT / "build" / "footage_samples.ipynb"
    make_footage_nb.build_samples(nb_path, mount, prompts,
                                  ref_image=Path(args.ref).name if args.ref else None)

    inputs = None
    if args.ref:
        staged = config.ROOT / "build" / "footage_ref"
        staged.mkdir(parents=True, exist_ok=True)
        import shutil as _sh
        _sh.copy2(args.ref, staged / Path(args.ref).name)
        inputs = staged

    out = run(nb_path, "footage-samples", config.ROOT / "build" / "footage_samples_out",
              inputs, gpu=True, internet=True, timeout_min=args.timeout,
              extra_datasets=[ref])
    print(f"""
Samples are in {out}.
Unzip samples.zip and WATCH THEM before anything else is built.

The question is only: is this good enough to publish? If it is not, say so --
switching model, resolution or style is cheap now and expensive later.""")


def job_footage(args) -> None:
    if not args.topic:
        raise SystemExit("--job footage needs --topic <name>")
    ref, mount = config.footage_weights()
    mod = script.load(args.topic)
    clips = [s for s in mod.SHOTS if s["kind"] == "clip"]
    if not clips:
        raise SystemExit(f"{args.topic} has no 'clip' shots; nothing to generate.")
    print(f"[footage] {len(clips)} clip shots of {len(mod.SHOTS)}")

    sys.path.insert(0, str(config.ROOT / "kaggle"))
    import make_footage_nb
    slug = f"footage-{args.topic}"[:48]
    nb_path = config.ROOT / "build" / f"{slug}.ipynb"
    make_footage_nb.build_batch(nb_path, mount, mod.SHOTS,
                                ref_image=Path(args.ref).name if args.ref else None)

    inputs = None
    if args.ref:
        staged = config.ROOT / "build" / f"{slug}_ref"
        staged.mkdir(parents=True, exist_ok=True)
        import shutil as _sh
        _sh.copy2(args.ref, staged / Path(args.ref).name)
        inputs = staged

    vdir = config.video_dir(args.topic)
    out = run(nb_path, slug, vdir / "body" / "footage_zip", inputs,
              gpu=True, internet=True, timeout_min=args.timeout,
              extra_datasets=[ref])

    # unpack next to the renderer, which pairs clips to shots by index
    import zipfile
    dest = vdir / "body" / "footage"
    dest.mkdir(parents=True, exist_ok=True)
    for z in Path(out).glob("*.zip"):
        with zipfile.ZipFile(z) as zf:
            zf.extractall(dest)
    got = sorted(p.name for p in dest.glob("*.mp4"))
    print(f"[footage] {len(got)} clips -> {dest}: {', '.join(got) or '(none)'}")
    print(f"\nNow render:\n  python videos/{args.topic}/body/build_body.py --reuse-voice")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--job", choices=("smoke", "portrait", "voice",
                                    "footage-samples", "footage"),
                   help="a canned job")
    p.add_argument("--ref", help="reference still for image-to-video "
                                 "(e.g. a frame from a Flow character clip)")
    p.add_argument("--prompt", help="override the sample prompts")
    p.add_argument("--topic", help="video topic, for --job voice")
    p.add_argument("--seeds", help="comma-separated seeds for --job portrait")
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
    if args.job == "portrait":
        return job_portrait(args)
    if args.job == "voice":
        return job_voice(args)
    if args.job == "footage-samples":
        return job_footage_samples(args)
    if args.job == "footage":
        return job_footage(args)
    if not (args.notebook and args.slug and args.out):
        p.error("give --job, or all of --notebook --slug --out")
    run(args.notebook, args.slug, args.out, args.inputs,
        gpu=not args.no_gpu, internet=not args.no_internet, timeout_min=args.timeout)


if __name__ == "__main__":
    main()
