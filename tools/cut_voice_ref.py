#!/usr/bin/env python3
"""Cut the 15-second voice reference out of the Flow clips.

    python tools/cut_voice_ref.py --topic home-batteries

Takes the cleanest stretch of the hook (and the close, if the hook alone is
too short), makes it mono 24 kHz at -20 LUFS, and writes videos/<topic>/voice/
ref.flac -- exactly what the Chatterbox notebook expects.

This is a clone of a SYNTHETIC Flow voice. Never point this at a recording of
a real person.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from studio import config, render  # noqa: E402

TARGET = 15.0
SR = 24000


def pick(src: Path, start: float, want: float, out: Path) -> float:
    """Grab `want` seconds from `start`, or as much as the clip has."""
    have = render.probe_duration(src)
    take = min(want, max(0.0, have - start - 0.15))
    if take <= 0.2:
        return 0.0
    render.ff(["-ss", f"{start:.2f}", "-t", f"{take:.2f}", "-i", str(src),
               "-vn", "-ac", "1", "-ar", str(SR), "-c:a", "pcm_s16le", str(out)],
              f"cutting {src.name}")
    return take


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--topic", required=True)
    p.add_argument("--hook-start", type=float, default=0.6,
                   help="skip the first moments, which often start mid-breath")
    p.add_argument("--close-start", type=float, default=0.6)
    p.add_argument("--output", type=Path)
    args = p.parse_args()

    render.require_ffmpeg()
    vdir = config.video_dir(args.topic)
    flow = vdir / "flow"
    work = vdir / "voice" / "_work"
    work.mkdir(parents=True, exist_ok=True)

    # prefer the cleaned clips if fix_clip has been run
    sources = []
    for name, start in (("hook", args.hook_start), ("close", args.close_start)):
        for cand in (flow / f"{name}_fixed.mp4", flow / f"{name}.mp4"):
            if cand.exists():
                sources.append((cand, start))
                break
    if not sources:
        raise SystemExit(f"No hook.mp4 or close.mp4 in {flow}\n"
                         "Download them from Flow first (step 2 and 3).")

    parts, got = [], 0.0
    for src, start in sources:
        if got >= TARGET:
            break
        out = work / f"{src.stem}.wav"
        took = pick(src, start, TARGET - got, out)
        if took:
            parts.append(out)
            got += took
            print(f"[ref] {src.name}: {took:.1f}s")

    if got < 6:
        raise SystemExit(f"Only {got:.1f}s of usable audio; Chatterbox wants 10-15s. "
                         "Generate a longer hook in Flow.")
    if got < TARGET:
        print(f"[ref] WARNING: only {got:.1f}s (wanted {TARGET:.0f}s). "
              "The clone will still work but may be less stable.")

    dst = args.output or (vdir / "voice" / "ref.flac")
    dst.parent.mkdir(parents=True, exist_ok=True)
    if len(parts) == 1:
        render.ff(["-i", str(parts[0]),
                   "-af", "loudnorm=I=-20:TP=-2:LRA=7", "-ac", "1", "-ar", str(SR),
                   str(dst)], "normalising reference")
    else:
        listing = work / "concat.txt"
        listing.write_text("".join(f"file '{q.resolve().as_posix()}'\n" for q in parts),
                           encoding="utf-8")
        render.ff(["-f", "concat", "-safe", "0", "-i", str(listing),
                   "-af", "loudnorm=I=-20:TP=-2:LRA=7", "-ac", "1", "-ar", str(SR),
                   str(dst)], "normalising reference")

    print(f"[ref] {render.probe_duration(dst):.1f}s mono {SR} Hz -> {dst}")
    print(f"\nNext:  python tools/kaggle_run.py --job voice --topic {args.topic}")


if __name__ == "__main__":
    main()
