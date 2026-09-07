#!/usr/bin/env python3
"""Clean up a raw Flow clip: de-logo, force 1080p/25fps, patch artefacts.

    python tools/fix_clip.py --topic home-batteries --clip hook
    python tools/fix_clip.py --topic home-batteries --clip close \
        --patch 980,610,120,90        # a mouth or screen artefact to paint out

Output lands next to the input as <name>_fixed.mp4 and is normalised to
exactly the format the body renders in, so stitching cannot drift.

--patch takes x,y,w,h in 1080p coordinates and may be repeated. It uses the
same interpolate-from-the-edges trick as the watermark removal, which is
invisible on small regions and mushy on large ones -- keep patches tight.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from studio import config, render  # noqa: E402

# Flow burns its watermark into the bottom-right corner. Measured on a 1080p
# export; override with --logo if yours sits somewhere else.
DEFAULT_LOGO = (1620, 975, 270, 75)


def box(spec: str) -> tuple[int, int, int, int]:
    try:
        x, y, w, h = (int(v) for v in spec.split(","))
    except ValueError:
        raise argparse.ArgumentTypeError("expected x,y,w,h (e.g. 1620,975,270,75)")
    return x, y, w, h


def clamp(b: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    """delogo refuses boxes touching the frame edge; keep a 1px inset."""
    x, y, w, h = b
    x = max(1, min(x, 1918))
    y = max(1, min(y, 1078))
    w = max(4, min(w, 1919 - x))
    h = max(4, min(h, 1079 - y))
    return x, y, w, h


def build_filters(logo: tuple[int, int, int, int] | None,
                  patches: list[tuple[int, int, int, int]]) -> str:
    chain = [
        "scale=1920:1080:force_original_aspect_ratio=decrease",
        "pad=1920:1080:(ow-iw)/2:(oh-ih)/2",
        "setsar=1",
        "fps=25",
    ]
    for b in ([logo] if logo else []) + patches:
        x, y, w, h = clamp(b)
        chain.append(f"delogo=x={x}:y={y}:w={w}:h={h}")
    chain.append("format=yuv420p")
    return ",".join(chain)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--topic")
    p.add_argument("--clip", choices=("hook", "close"), help="with --topic")
    p.add_argument("--input", type=Path, help="an explicit file instead")
    p.add_argument("--output", type=Path)
    p.add_argument("--logo", type=box, default=DEFAULT_LOGO,
                   help=f"watermark box x,y,w,h (default {','.join(map(str, DEFAULT_LOGO))})")
    p.add_argument("--no-logo", action="store_true", help="leave the watermark alone")
    p.add_argument("--patch", type=box, action="append", default=[],
                   help="extra artefact box x,y,w,h; repeatable")
    args = p.parse_args()

    render.require_ffmpeg()
    if args.input:
        src = args.input
    elif args.topic and args.clip:
        src = config.video_dir(args.topic) / "flow" / f"{args.clip}.mp4"
    else:
        p.error("give --input, or --topic and --clip")

    if not src.exists():
        raise SystemExit(f"No such clip: {src}\nDownload it from Flow into that folder first.")

    dst = args.output or src.with_name(f"{src.stem}_fixed.mp4")
    vf = build_filters(None if args.no_logo else args.logo, args.patch)
    print(f"[fix_clip] {src.name} -> {dst.name}")
    print(f"[fix_clip] filters: {vf}")

    render.ff([
        "-i", str(src), "-vf", vf,
        "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p",
        "-r", "25", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
        "-movflags", "+faststart", str(dst),
    ], f"cleaning {src.name}")

    print(f"[fix_clip] {render.probe_duration(dst):.2f}s, "
          f"{render.probe_frames(dst)} frames -> {dst}")


if __name__ == "__main__":
    main()
