#!/usr/bin/env python3
"""Shift the body narration's tonal balance toward the Flow hook recording,
so the three parts sound like one take.

    python tools/match_eq.py --topic home-batteries

Measures seven octave bands in both recordings, subtracts the overall level
difference (loudnorm owns loudness; this owns tone), and applies the remaining
per-band difference as a gentle EQ. Every band is capped at +/-3 dB -- past
that you are no longer matching a voice, you are rebuilding it.

Needs no numpy: each band is measured with ffmpeg's own volumedetect.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from studio import config, render  # noqa: E402

BANDS = [(125, 90, 180), (250, 180, 355), (500, 355, 710), (1000, 710, 1400),
         (2000, 1400, 2800), (4000, 2800, 5600), (8000, 5600, 11000)]
CAP_DB = 3.0

_MEAN = re.compile(r"mean_volume:\s*(-?\d+(?:\.\d+)?)\s*dB")


def mean_db(path: Path, af: str = "") -> float:
    chain = f"{af},volumedetect" if af else "volumedetect"
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostdin", "-v", "info", "-i", str(path),
         "-af", chain, "-f", "null", "-"],
        capture_output=True, text=True)
    m = _MEAN.search(proc.stderr or "")
    if not m:
        raise SystemExit(f"[match_eq] could not measure {path}:\n"
                         + "\n".join((proc.stderr or "").splitlines()[-8:]))
    return float(m.group(1))


def profile(path: Path) -> tuple[float, list[float]]:
    overall = mean_db(path)
    bands = [mean_db(path, f"highpass=f={lo},highpass=f={lo},lowpass=f={hi},lowpass=f={hi}")
             for _, lo, hi in BANDS]
    return overall, bands


def gains(reference: Path, target: Path) -> list[float]:
    ref_all, ref_bands = profile(reference)
    tgt_all, tgt_bands = profile(target)
    out = []
    for (centre, _, _), r, t in zip(BANDS, ref_bands, tgt_bands):
        # remove the level offset so we correct tone, not volume
        raw = (r - ref_all) - (t - tgt_all)
        g = max(-CAP_DB, min(CAP_DB, raw))
        out.append(round(g, 2))
        flag = "  (capped)" if abs(raw) > CAP_DB else ""
        print(f"  {centre:>6} Hz   want {raw:+5.1f} dB -> apply {g:+5.2f} dB{flag}")
    return out


def apply(target: Path, out_path: Path, g: list[float]) -> Path:
    chain = ",".join(f"equalizer=f={c}:width_type=o:width=1:g={gain}"
                     for (c, _, _), gain in zip(BANDS, g) if abs(gain) >= 0.05)
    if not chain:
        print("[match_eq] nothing to correct; copying through")
        chain = "anull"
    render.ff(["-i", str(target), "-af", f"{chain},loudnorm=I=-16:TP=-1.5:LRA=11",
               "-c:a", "pcm_s16le", "-ar", "48000", str(out_path)],
              "applying tonal match")
    return out_path


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--topic")
    p.add_argument("--reference", type=Path, help="the hook clip (tone to match)")
    p.add_argument("--target", type=Path, help="the body narration to correct")
    p.add_argument("--output", type=Path)
    args = p.parse_args()

    render.require_ffmpeg()
    if args.topic:
        vdir = config.video_dir(args.topic)
        ref = args.reference or next(
            (q for q in (vdir / "flow" / "hook_fixed.mp4", vdir / "flow" / "hook.mp4")
             if q.exists()), None)
        tgt = args.target or (vdir / "body" / "_work" / "voice_unpacked" / "voice.wav")
        out = args.output or (vdir / "body" / "_work" / "voice_matched.wav")
    else:
        ref, tgt, out = args.reference, args.target, args.output
    if not (ref and tgt and out):
        p.error("give --topic, or all of --reference --target --output")
    for q in (ref, tgt):
        if not Path(q).exists():
            raise SystemExit(f"Missing {q}")

    print(f"[match_eq] reference {Path(ref).name}  ->  target {Path(tgt).name}")
    g = gains(Path(ref), Path(tgt))
    apply(Path(tgt), Path(out), g)
    print(f"[match_eq] wrote {out}")


if __name__ == "__main__":
    main()
