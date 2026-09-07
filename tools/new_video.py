#!/usr/bin/env python3
"""Scaffold videos/<topic>/ from the template.

    python tools/new_video.py battery-payback
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from studio import config  # noqa: E402

SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{1,48}$")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("topic", help="lower-case slug, e.g. battery-payback")
    p.add_argument("--force", action="store_true")
    args = p.parse_args()

    if not SLUG.match(args.topic):
        raise SystemExit("Topic must be a lower-case slug: letters, digits and hyphens.\n"
                         "It becomes a folder name and part of a Kaggle kernel slug.")

    dst = config.video_dir(args.topic)
    if dst.exists() and not args.force:
        raise SystemExit(f"{dst} already exists (use --force to overwrite the script).")

    src = config.VIDEOS / "_template"
    for sub in ("body", "flow", "voice"):
        (dst / sub).mkdir(parents=True, exist_ok=True)
    shutil.copy2(src / "body" / "build_body.py", dst / "body" / "build_body.py")

    print(f"Created {dst}")
    print(f"""
Next:
  1. Write the script in   {dst / 'body' / 'build_body.py'}
     - one SHOTS entry per beat, each with its own `say` line
     - HOOK and CLOSE are the lines you will read into Flow
  2. Check the layout      python videos/{args.topic}/body/build_body.py --stills-only
  3. Generate hook.mp4 and close.mp4 in Flow, save them into {dst / 'flow'}
  4. python tools/fix_clip.py --topic {args.topic} --clip hook
     python tools/fix_clip.py --topic {args.topic} --clip close
  4b. python tools/cut_voice_ref.py --topic {args.topic}
      python tools/kaggle_run.py --job voice --topic {args.topic}
  5. python videos/{args.topic}/body/build_body.py --reuse-voice
  6. python tools/stitch.py --topic {args.topic}
  7. python tools/review.py --topic {args.topic}
""")


if __name__ == "__main__":
    main()
