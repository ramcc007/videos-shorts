#!/usr/bin/env python3
"""Step 7: everything you should look at before uploading.

    python tools/review.py --topic home-batteries

Writes review/ next to the final cut containing the frames either side of both
joins, and prints EBU R128 loudness per segment plus the frame-count check.
The contact sheet catches most problems; the joins need your eye.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from studio import config, render  # noqa: E402

FPS = 25
_SUMMARY = re.compile(r"I:\s*(-?\d+(?:\.\d+)?)\s*LUFS.*?LRA:\s*(-?\d+(?:\.\d+)?)\s*LU",
                      re.S)
_PEAK = re.compile(r"Peak:\s*(-?\d+(?:\.\d+)?)\s*dBFS")


def loudness(path: Path, start: float | None = None, dur: float | None = None) -> str:
    args = ["ffmpeg", "-hide_banner", "-nostdin", "-v", "info"]
    if start is not None:
        args += ["-ss", f"{start:.2f}"]
    if dur is not None:
        args += ["-t", f"{dur:.2f}"]
    args += ["-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-"]
    err = subprocess.run(args, capture_output=True, text=True).stderr or ""
    tail = err[err.rfind("Summary"):] if "Summary" in err else err
    m = _SUMMARY.search(tail)
    pk = _PEAK.findall(tail)
    if not m:
        return "unmeasurable"
    return f"{float(m.group(1)):6.1f} LUFS   LRA {float(m.group(2)):4.1f} LU   " \
           f"peak {float(pk[-1]) if pk else float('nan'):5.1f} dBFS"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--topic", required=True)
    p.add_argument("--final", type=Path)
    args = p.parse_args()

    render.require_ffmpeg()
    vdir = config.video_dir(args.topic)
    final = args.final or (vdir / "out" / f"{args.topic}_final.mp4")
    if not final.exists():
        raise SystemExit(f"No {final}\n  Run:  python tools/stitch.py --topic {args.topic}")

    hook = next((q for q in (vdir / "flow" / "hook_fixed.mp4", vdir / "flow" / "hook.mp4")
                 if q.exists()), None)
    body = vdir / "out" / "body.mp4"
    close = next((q for q in (vdir / "flow" / "close_fixed.mp4", vdir / "flow" / "close.mp4")
                  if q.exists()), None)

    rdir = vdir / "out" / "review"
    rdir.mkdir(parents=True, exist_ok=True)

    print(f"\n=== review: {final.name} ===")
    total_frames = render.probe_frames(final)
    total_dur = render.probe_duration(final)
    print(f"  {total_dur:.2f}s  ({total_dur/60:.2f} min)  {total_frames} frames  "
          f"{total_frames/FPS:.2f}s at {FPS} fps")

    # --- frame count against the parts ------------------------------------
    parts = [(q, render.probe_frames(q)) for q in (hook, body, close) if q and q.exists()]
    expected = sum(n for _, n in parts)
    print("\n  parts:")
    for q, n in parts:
        print(f"    {q.name:<28} {n:>5} frames  {n/FPS:7.2f}s")
    verdict = "PASS" if expected == total_frames else f"MISMATCH ({expected} vs {total_frames})"
    print(f"    {'sum':<28} {expected:>5} frames   -> {verdict}")

    # --- the two joins ----------------------------------------------------
    if len(parts) == 3:
        j1 = parts[0][1] / FPS
        j2 = (parts[0][1] + parts[1][1]) / FPS
        print("\n  joins (check these by eye -- the contact sheet will not show them):")
        for label, t in (("hook-body", j1), ("body-close", j2)):
            for tag, at in (("before", t - 1.5 / FPS), ("after", t + 1.5 / FPS)):
                out = rdir / f"join_{label}_{tag}.png"
                render.ff(["-ss", f"{max(0, at):.3f}", "-i", str(final), "-frames:v", "1",
                           "-vf", "scale=960:-1", str(out)], f"grabbing {out.name}")
            print(f"    {label:<12} at {t:6.2f}s  -> {rdir / f'join_{label}_before.png'} / _after.png")

    # --- loudness per segment --------------------------------------------
    print("\n  loudness (EBU R128) -- the three parts should be within ~1 LU:")
    print(f"    {'whole cut':<14} {loudness(final)}")
    if len(parts) == 3:
        offs = [0.0, parts[0][1] / FPS, (parts[0][1] + parts[1][1]) / FPS]
        for (q, n), off in zip(parts, offs):
            print(f"    {q.stem[:14]:<14} {loudness(final, off, n / FPS)}")

    sheet = vdir / "out" / "contact_sheet.png"
    print(f"\n  contact sheet   {sheet if sheet.exists() else 'not rendered'}")
    credits = vdir / "out" / "CREDITS.md"
    print(f"  credits         {credits if credits.exists() else 'none (no photo shots)'}")
    print("\n  Before uploading: tick YouTube's synthetic-content disclosure.")
    if verdict != "PASS":
        raise SystemExit("\nFrame count does not match the parts -- do not upload this cut.")


if __name__ == "__main__":
    main()
