#!/usr/bin/env python3
"""Join hook + body + close and prove nothing was lost.

    python tools/stitch.py --topic home-batteries

By default every part is re-encoded through the concat filter, which
guarantees one uniform stream even if Flow hands you something odd. --copy is
faster and lossless but only works when all three parts already match exactly;
if it produces the wrong frame count, stitch falls back and says so.

The check that matters: output frames == hook + body + close frames.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from studio import config, render  # noqa: E402

FPS = 25


def resolve(vdir: Path) -> list[Path]:
    parts = []
    for name in ("hook", "body", "close"):
        if name == "body":
            cand = [vdir / "out" / "body.mp4"]
        else:
            cand = [vdir / "flow" / f"{name}_fixed.mp4", vdir / "flow" / f"{name}.mp4"]
        found = next((c for c in cand if c.exists()), None)
        if found is None:
            raise SystemExit(
                f"Missing {name}: looked for {', '.join(str(c) for c in cand)}\n"
                + ("  Render it:  python videos/<topic>/body/build_body.py --reuse-voice"
                   if name == "body" else
                   f"  Generate {name}.mp4 in Flow, then:  python tools/fix_clip.py "
                   f"--topic <topic> --clip {name}"))
        if found.name.endswith(f"{name}.mp4") and name != "body":
            print(f"[stitch] NOTE: using raw {found.name} -- fix_clip.py has not been run, "
                  "so the Flow watermark is still in it.")
        parts.append(found)
    return parts


def concat_filter(parts: list[Path], out: Path, counts: list[int]) -> None:
    """Concatenate, pinning every segment to exactly frames/FPS on BOTH streams.

    Without the trim/apad pair the joins drift: AAC quantises audio to 1024-
    sample frames, so each part's audio ends ~11 ms after its video, the concat
    filter offsets the next segment by the longer stream, and the CFR encoder
    fills each gap with a duplicated frame. Two joins, one phantom frame.
    """
    args: list[str] = []
    for p in parts:
        args += ["-i", str(p)]
    graph = "".join(
        f"[{i}:v]scale=1920:1080:force_original_aspect_ratio=decrease,"
        f"pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={FPS},format=yuv420p,"
        f"trim=end={counts[i]/FPS:.6f},setpts=PTS-STARTPTS[v{i}];"
        f"[{i}:a]aformat=sample_rates=48000:channel_layouts=stereo,"
        f"apad,atrim=end={counts[i]/FPS:.6f},asetpts=PTS-STARTPTS[a{i}];"
        for i in range(len(parts))
    ) + "".join(f"[v{i}][a{i}]" for i in range(len(parts))) \
      + f"concat=n={len(parts)}:v=1:a=1[v][a]"
    render.ff(args + ["-filter_complex", graph, "-map", "[v]", "-map", "[a]",
                      "-c:v", "libx264", "-crf", "18", "-preset", "medium",
                      "-pix_fmt", "yuv420p", "-r", str(FPS),
                      "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)],
              "concatenating parts")


def concat_copy(parts: list[Path], out: Path) -> None:
    listing = out.parent / "_stitch.txt"
    listing.write_text("".join(f"file '{p.resolve().as_posix()}'\n" for p in parts),
                       encoding="utf-8")
    render.ff(["-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy",
               "-movflags", "+faststart", str(out)], "concatenating parts (copy)")
    listing.unlink(missing_ok=True)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--topic", required=True)
    p.add_argument("--output", type=Path)
    p.add_argument("--copy", action="store_true", help="stream-copy instead of re-encoding")
    args = p.parse_args()

    render.require_ffmpeg()
    vdir = config.video_dir(args.topic)
    parts = resolve(vdir)
    out = args.output or (vdir / "out" / f"{args.topic}_final.mp4")
    out.parent.mkdir(parents=True, exist_ok=True)

    counts = []
    print("[stitch] parts:")
    for q in parts:
        f, d = render.probe_frames(q), render.probe_duration(q)
        counts.append(f)
        print(f"  {q.name:<28} {d:7.2f}s  {f:>5} frames")
    expected = sum(counts)

    if args.copy:
        concat_copy(parts, out)
        if render.probe_frames(out) != expected:
            print("[stitch] copy produced the wrong frame count; re-encoding instead.")
            concat_filter(parts, out, counts)
    else:
        concat_filter(parts, out, counts)

    got = render.probe_frames(out)
    dur = render.probe_duration(out)
    print(f"\n[stitch] {out}")
    print(f"  duration  {dur:7.2f}s  ({dur/60:.1f} min)")
    print(f"  frames    {got:>7}   expected {expected}")
    if got != expected:
        raise SystemExit(f"[stitch] FRAME COUNT MISMATCH: {got} != {expected}. "
                         "Do not upload this; re-run fix_clip.py on the Flow parts.")
    print("  status    PASS -- frame count equals the sum of the parts")
    print(f"\nReview before upload:\n"
          f"  - the two joins at {counts[0]/FPS:.1f}s and {(counts[0]+counts[1])/FPS:.1f}s\n"
          f"  - {vdir / 'out' / 'contact_sheet.png'}\n"
          f"  - loudness:  ffmpeg -i {out.name} -af ebur128 -f null -\n"
          f"  - tick the synthetic-content disclosure on upload")


if __name__ == "__main__":
    main()
