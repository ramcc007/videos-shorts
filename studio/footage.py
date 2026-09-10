"""Assemble generated footage into body shots.

The video model does not produce clips of the length we need: LTX-Video, for
instance, works in frames divisible by 8 plus 1, so 161 frames at 24 fps is
6.7 s while a shot might want 8.4 s. This module conforms whatever comes back
to the exact frame count the narration demands, so the "video is the authority
on length" rule that the rest of the pipeline relies on still holds.

It is deliberately model-agnostic: it takes an mp4 and a target duration. Which
model produced it, and where the weights came from, is not its problem.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from . import draw as drawmod
from . import render, theme
from .theme import FPS

MAX_SPEED_SHIFT = 0.15     # beyond +/-15% a speed change reads as slow motion


def _frames_needed(seconds: float) -> int:
    return max(2, int(round(seconds * FPS)))


def plan_fit(src_seconds: float, want_seconds: float) -> tuple[str, float]:
    """Decide how to turn src_seconds of footage into want_seconds.

    Returns (mode, factor). Modes:
      trim       source is long enough -- just cut it
      speed      within +/-15%, retime with setpts (invisible at these ratios)
      boomerang  too short -- play forward then reversed, then trim
    """
    if src_seconds >= want_seconds:
        return "trim", 1.0
    ratio = want_seconds / src_seconds
    if ratio - 1.0 <= MAX_SPEED_SHIFT:
        return "speed", ratio
    return "boomerang", ratio


def conform(src: Path, out: Path, want_seconds: float,
            sharpen: bool = True) -> Path:
    """Turn one generated clip into exactly the frames this shot needs, at 1080p.

    Generated footage is usually well below 1080p (704x480 is typical), so it is
    upscaled with lanczos and lightly sharpened. It will still be softer than the
    drawn shots -- that is a property of the source, not a bug here.
    """
    src_seconds = render.probe_duration(src)
    mode, factor = plan_fit(src_seconds, want_seconds)
    frames = _frames_needed(want_seconds)

    scale = (f"scale={theme.OUT_W}:{theme.OUT_H}:force_original_aspect_ratio=increase:flags=lanczos,"
             f"crop={theme.OUT_W}:{theme.OUT_H},setsar=1")
    if sharpen:
        scale += ",unsharp=5:5:0.8:3:3:0.4"

    if mode == "boomerang":
        # forward + reversed, looped until long enough, then trimmed
        graph = (f"[0:v]{scale},split=2[a][b];"
                 f"[b]reverse[r];"
                 f"[a][r]concat=n=2:v=1:a=0,loop=loop=-1:size=32767:start=0,"
                 f"trim=end_frame={frames},setpts=PTS-STARTPTS,fps={FPS}[v]")
        render.ff(["-i", str(src), "-filter_complex", graph, "-map", "[v]",
                   "-frames:v", str(frames), "-c:v", "libx264", "-crf", "18",
                   "-preset", "medium", "-pix_fmt", "yuv420p", "-an", str(out)],
                  f"boomeranging {src.name} to {want_seconds:.2f}s")
    else:
        vf = scale
        if mode == "speed":
            vf += f",setpts={factor:.4f}*PTS"
        vf += f",fps={FPS},trim=end_frame={frames},setpts=PTS-STARTPTS"
        render.ff(["-i", str(src), "-vf", vf, "-frames:v", str(frames),
                   "-c:v", "libx264", "-crf", "18", "-preset", "medium",
                   "-pix_fmt", "yuv420p", "-an", str(out)],
                  f"conforming {src.name} to {want_seconds:.2f}s ({mode})")

    got = render.probe_frames(out)
    if got != frames:
        raise SystemExit(f"[footage] {out.name}: got {got} frames, needed {frames}. "
                         "The conform step must be exact or the joins will drift.")
    return out


def headline_overlay(shot: dict, out_png: Path) -> Path | None:
    """Optional lower-third for a clip shot. Returns None when not wanted."""
    text = (shot.get("headline") or "").strip()
    if not text:
        return None
    img = Image.new("RGBA", (theme.RENDER_W, theme.RENDER_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    fnt = theme.font(46, "bold")
    lines = drawmod.wrap(text, fnt, 1200)[:2]

    top = 760
    pad = 26
    width = max(fnt.getlength(l) for l in lines) / theme.SCALE + pad * 2
    height = len(lines) * 62 + pad * 2
    d.rounded_rectangle(
        [drawmod.px(drawmod.MARGIN - pad), drawmod.px(top - pad),
         drawmod.px(drawmod.MARGIN + width - pad), drawmod.px(top + height - pad)],
        radius=drawmod.px(10), fill=(*theme.NAVY_LO, 205))
    d.rounded_rectangle(
        [drawmod.px(drawmod.MARGIN - pad), drawmod.px(top - pad),
         drawmod.px(drawmod.MARGIN - pad + 6), drawmod.px(top + height - pad)],
        radius=drawmod.px(3), fill=theme.RED)

    y = top
    for ln in lines:
        d.text((drawmod.px(drawmod.MARGIN), drawmod.px(y)), ln, font=fnt, fill=theme.INK)
        y += 62
    out_png.parent.mkdir(parents=True, exist_ok=True)
    img.resize((theme.OUT_W, theme.OUT_H), Image.LANCZOS).save(out_png)
    return out_png


def apply_overlay(clip: Path, overlay: Path, out: Path) -> Path:
    frames = render.probe_frames(clip)
    render.ff(["-i", str(clip), "-i", str(overlay),
               "-filter_complex", "[0:v][1:v]overlay=0:0:format=auto[v]",
               "-map", "[v]", "-frames:v", str(frames),
               "-c:v", "libx264", "-crf", "18", "-preset", "medium",
               "-pix_fmt", "yuv420p", "-an", str(out)],
              f"overlaying headline on {clip.name}")
    return out


def source_for(index: int, footage_dir: Path) -> Path | None:
    """Find the generated clip for shot `index`, whatever extension it has."""
    if not footage_dir.exists():
        return None
    for ext in (".mp4", ".webm", ".mov", ".mkv"):
        p = footage_dir / f"{index:03d}{ext}"
        if p.exists():
            return p
    return None
