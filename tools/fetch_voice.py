#!/usr/bin/env python3
"""Download the Kokoro voice model files into the project root.

Kokoro is the local narration voice: CPU only, no GPU, no Kaggle job, no cost.
It is the production voice for Shorts, which render without a presenter.

    python tools/fetch_voice.py            # fetch what is missing
    python tools/fetch_voice.py --force    # re-fetch even if present
    python tools/fetch_voice.py --dir D:/models

The files are large and are checked by exact byte count. That is a check
against the download that actually goes wrong in practice -- a connection cut
part way, or a proxy error page saved under the model's name -- not a
cryptographic guarantee.
"""
from __future__ import annotations

import argparse
import shutil
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from studio import config  # noqa: E402

BASE = ("https://github.com/thewh1teagle/kokoro-onnx/releases/download/"
        "model-files-v1.0")
FILES = [
    (config.KOKORO_MODEL, f"{BASE}/{config.KOKORO_MODEL}", 325_532_387),
    (config.KOKORO_VOICES, f"{BASE}/{config.KOKORO_VOICES}", 28_214_398),
]
RELEASES = "https://github.com/thewh1teagle/kokoro-onnx/releases"


def human(n: int) -> str:
    return f"{n / 1e6:,.1f} MB"


def fetch(name: str, url: str, expect: int, dest_dir: Path, force: bool) -> bool:
    dest = dest_dir / name
    if dest.is_file() and not force:
        actual = dest.stat().st_size
        if actual == expect:
            print(f"  {name:<22} already present ({human(actual)})")
            return True
        print(f"  {name:<22} wrong size ({human(actual)}, expected "
              f"{human(expect)}) -- re-downloading")

    part = dest.with_suffix(dest.suffix + ".part")
    print(f"  {name:<22} downloading {human(expect)} ...", flush=True)
    try:
        with urllib.request.urlopen(url, timeout=60) as r, part.open("wb") as f:
            got, step = 0, max(1, expect // 20)
            nxt = step
            while chunk := r.read(1 << 16):
                f.write(chunk)
                got += len(chunk)
                if got >= nxt:
                    print(f"      {100 * got // expect:3d}%  {human(got)}", flush=True)
                    nxt += step
    except Exception as e:
        part.unlink(missing_ok=True)
        print(f"  {name:<22} FAILED: {e}\n"
              f"      Download it by hand from {RELEASES}\n"
              f"      and put it in {dest_dir}", file=sys.stderr)
        return False

    got = part.stat().st_size
    if got != expect:
        part.unlink(missing_ok=True)
        print(f"  {name:<22} FAILED: got {human(got)}, expected {human(expect)}.\n"
              f"      The download was cut short, or the release has changed.\n"
              f"      Check {RELEASES}", file=sys.stderr)
        return False

    part.replace(dest)          # only appears under its real name once complete
    print(f"  {name:<22} ok ({human(got)})")
    return True


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", type=Path, default=None,
                    help="where to put them (default: the project root)")
    ap.add_argument("--force", action="store_true", help="re-download even if present")
    args = ap.parse_args(argv)

    dest_dir = (args.dir or config.ROOT).expanduser().resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)

    need = sum(sz for n, _, sz in FILES
               if args.force or not (dest_dir / n).is_file()
               or (dest_dir / n).stat().st_size != sz)
    free = shutil.disk_usage(dest_dir).free
    if need and free < need * 1.1:
        print(f"Not enough free space in {dest_dir}: need about {human(need)}, "
              f"have {human(free)}.", file=sys.stderr)
        return 1

    print(f"\nKokoro voice files -> {dest_dir}")
    ok = all([fetch(n, u, sz, dest_dir, args.force) for n, u, sz in FILES])

    if ok:
        where = ("" if dest_dir == config.ROOT
                 else f"\nSet STUDIO_KOKORO_DIR={dest_dir} so the pipeline finds them.")
        print(f"\nBoth files ready.{where}\n"
              f"Check it:  python tools/setup_check.py\n")
        return 0
    print("\nSomething is missing -- see above.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
