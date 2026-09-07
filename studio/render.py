"""The ffmpeg half of the body: motion, captions, music, mix, contact sheet."""
from __future__ import annotations

import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image

from . import draw, photos, theme
from .theme import FPS, OUT_H, OUT_W

ZOOM_MAX = 1.13          # Ken Burns push-in end zoom
ZOOM_PAN = 1.10          # zoom held while panning
MUSIC_LEVEL = 0.18       # "about 18 percent under the voice"


# --------------------------------------------------------------------------- #
def ff(args: list[str], what: str) -> None:
    """Run ffmpeg, and on failure show the tail of stderr rather than a bare
    exit code -- ffmpeg's real error is always in the last few lines."""
    proc = subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-y", "-v", "warning", *args],
                          capture_output=True, text=True)
    if proc.returncode != 0:
        tail = "\n".join((proc.stderr or "").strip().splitlines()[-14:])
        raise SystemExit(f"[render] ffmpeg failed while {what}:\n{tail}")


def probe_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, check=True).stdout.strip()
    return float(out)


def probe_frames(path: Path) -> int:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
         "-show_entries", "stream=nb_read_frames", "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, check=True).stdout.strip()
    return int(out) if out.isdigit() else 0


def require_ffmpeg() -> None:
    for exe in ("ffmpeg", "ffprobe"):
        if shutil.which(exe) is None:
            raise SystemExit(
                f"{exe} is not on PATH. Install it and reopen your terminal:\n"
                "  Windows: winget install Gyan.FFmpeg\n"
                "  macOS:   brew install ffmpeg\n"
                "  Linux:   sudo apt install ffmpeg")


# --------------------------------------------------------------------------- #
def render_stills(shots: list[dict], stills_dir: Path, photos_dir: Path,
                  fetch_photos: bool = True) -> list[Path]:
    stills_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for i, shot in enumerate(shots):
        img_path, credit = (None, None)
        if shot["kind"] == "photo" and fetch_photos:
            img_path, credit = photos.fetch(shot, photos_dir, i)
        img = draw.render_shot(shot, img_path, credit)
        out = stills_dir / f"{i:03d}.png"
        img.save(out)
        paths.append(out)
        print(f"  [{i:>2}/{len(shots)-1}] {shot['kind']:<6} {shot.get('headline', shot.get('value',''))[:46]}")
    return paths


def _kenburns(index: int, frames: int) -> tuple[str, str, str]:
    """Alternate push-in and pan so a long body never feels mechanical."""
    last = max(1, frames - 1)
    mode = index % 4
    if mode in (0, 2):                      # push in / pull back
        if mode == 0:
            z = f"min(1.0005+{ZOOM_MAX - 1:.4f}*on/{last},{ZOOM_MAX})"
        else:
            z = f"max({ZOOM_MAX}-{ZOOM_MAX - 1:.4f}*on/{last},1.0005)"
        return z, "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    # pan across, alternating direction
    z = f"{ZOOM_PAN}"
    travel = f"on/{last}" if mode == 1 else f"(1-on/{last})"
    return z, f"(iw-iw/zoom)*{travel}", "ih/2-(ih/zoom/2)"


def make_clips(stills: list[Path], durations: list[float], clips_dir: Path) -> list[Path]:
    clips_dir.mkdir(parents=True, exist_ok=True)
    out = []
    for i, (still, dur) in enumerate(zip(stills, durations)):
        frames = max(2, int(round(dur * FPS)))
        z, x, y = _kenburns(i, frames)
        clip = clips_dir / f"{i:03d}.mp4"
        vf = (f"zoompan=z='{z}':x='{x}':y='{y}':d=1:s={OUT_W}x{OUT_H}:fps={FPS},"
              f"format=yuv420p")
        ff(["-loop", "1", "-framerate", str(FPS), "-t", f"{frames/FPS:.4f}",
            "-i", str(still), "-vf", vf, "-frames:v", str(frames),
            "-c:v", "libx264", "-crf", "18", "-preset", "medium",
            "-pix_fmt", "yuv420p", "-an", str(clip)],
           f"animating shot {i}")
        out.append(clip)
    return out


def make_shot_clips(shots: list[dict], stills: list[Path], durations: list[float],
                    clips_dir: Path, footage_dir: Path) -> list[Path]:
    """One clip per shot: generated footage where we have it, Ken Burns otherwise.

    A clip shot whose footage never arrived falls back to its drawn card rather
    than killing the render -- same policy as a failed photo download.
    """
    from . import footage as footagemod

    clips_dir.mkdir(parents=True, exist_ok=True)
    out: list[Path] = []
    for i, (shot, still, dur) in enumerate(zip(shots, stills, durations)):
        clip = clips_dir / f"{i:03d}.mp4"
        src = footagemod.source_for(i, footage_dir) if shot["kind"] == "clip" else None

        if shot["kind"] == "clip" and src is None:
            print(f"  [{i:>2}] WARNING: no footage for clip shot; using the text card. "
                  f"Expected {footage_dir / f'{i:03d}.mp4'}")

        if src is not None:
            raw = clips_dir / f"{i:03d}_raw.mp4"
            footagemod.conform(src, raw, dur)
            overlay = footagemod.headline_overlay(shot, clips_dir / f"{i:03d}_ovl.png")
            if overlay is not None:
                footagemod.apply_overlay(raw, overlay, clip)
                raw.unlink(missing_ok=True)
            else:
                raw.replace(clip)
            print(f"  [{i:>2}] footage  {src.name} -> {dur:.2f}s")
        else:
            _kenburns_clip(still, dur, i, clip)
            print(f"  [{i:>2}] {shot['kind']:<7} {dur:.2f}s")
        out.append(clip)
    return out


def _kenburns_clip(still: Path, dur: float, index: int, clip: Path) -> Path:
    frames = max(2, int(round(dur * FPS)))
    z, x, y = _kenburns(index, frames)
    vf = (f"zoompan=z='{z}':x='{x}':y='{y}':d=1:s={OUT_W}x{OUT_H}:fps={FPS},"
          f"format=yuv420p")
    ff(["-loop", "1", "-framerate", str(FPS), "-t", f"{frames/FPS:.4f}",
        "-i", str(still), "-vf", vf, "-frames:v", str(frames),
        "-c:v", "libx264", "-crf", "18", "-preset", "medium",
        "-pix_fmt", "yuv420p", "-an", str(clip)],
       f"animating shot {index}")
    return clip


def concat_clips(clips: list[Path], out_path: Path) -> Path:
    listing = out_path.parent / "concat.txt"
    listing.write_text("".join(f"file '{c.resolve().as_posix()}'\n" for c in clips),
                       encoding="utf-8")
    ff(["-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(out_path)],
       "joining shot clips")
    return out_path


def mix_audio(voice_wav: Path, music: Path | None, out_path: Path,
              total: float) -> Path:
    """Voice + ducked, faded music, then EBU R128 loudness normalisation."""
    if music is None or not Path(music).exists():
        ff(["-i", str(voice_wav),
            "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
            "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2", str(out_path)],
           "normalising narration")
        return out_path

    fade_out_at = max(0.0, total - 3.0)
    graph = (
        f"[1:a]aformat=sample_rates=48000:channel_layouts=stereo,"
        f"volume={MUSIC_LEVEL},"
        f"afade=t=in:st=0:d=2,afade=t=out:st={fade_out_at:.2f}:d=3[music];"
        f"[0:a]aformat=sample_rates=48000:channel_layouts=stereo[voice];"
        f"[voice]asplit=2[v1][vkey];"
        # duck the bed further whenever the voice is actually speaking
        f"[music][vkey]sidechaincompress=threshold=0.02:ratio=6:attack=25:release=350[ducked];"
        f"[v1][ducked]amix=inputs=2:duration=first:normalize=0[mixed];"
        f"[mixed]loudnorm=I=-16:TP=-1.5:LRA=11[out]"
    )
    ff(["-i", str(voice_wav), "-stream_loop", "-1", "-i", str(music),
        "-filter_complex", graph, "-map", "[out]", "-t", f"{total:.3f}",
        "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2", str(out_path)],
       "mixing voice and music")
    return out_path


def burn_and_mux(video: Path, audio: Path, ass_file: Path, out_path: Path) -> Path:
    # libass needs a POSIX-ish path; on Windows the drive colon must be escaped
    ass_arg = ass_file.resolve().as_posix().replace(":", r"\:", 1) \
        if len(str(ass_file.resolve())) > 1 and str(ass_file.resolve())[1] == ":" \
        else ass_file.resolve().as_posix()
    # apad + shortest makes the *video* the authority on length: loudnorm trims
    # a few tens of ms off the audio tail, and without the pad that silently
    # cost us the final frame.
    ff(["-i", str(video), "-i", str(audio),
        "-vf", f"ass='{ass_arg}'", "-af", "apad",
        "-map", "0:v:0", "-map", "1:a:0", "-shortest",
        "-c:v", "libx264", "-crf", "19", "-preset", "medium",
        "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out_path)],
       "burning captions and muxing")
    return out_path


def contact_sheet(video: Path, times: list[dict], shots: list[dict],
                  out_path: Path, cols: int = 4) -> Path:
    """One frame per shot, tiled -- the fastest way to spot a broken render."""
    tmp = out_path.parent / "_sheet"
    tmp.mkdir(parents=True, exist_ok=True)
    thumbs = []
    for i, t in enumerate(times):
        mid = (t["start"] + t["end"]) / 2
        f = tmp / f"{i:03d}.png"
        ff(["-ss", f"{mid:.2f}", "-i", str(video), "-frames:v", "1",
            "-vf", "scale=640:-1", str(f)], f"grabbing frame for shot {i}")
        thumbs.append((i, f))

    if not thumbs:
        raise SystemExit("[render] contact sheet: no frames")
    tw, th = Image.open(thumbs[0][1]).size
    rows = math.ceil(len(thumbs) / cols)
    pad, label_h = 12, 30
    sheet = Image.new("RGB", (cols * tw + pad * (cols + 1),
                              rows * (th + label_h) + pad * (rows + 1)),
                      theme.NAVY_LO)
    from PIL import ImageDraw as _ID
    d = _ID.Draw(sheet)
    fnt = theme.font(16, "bold")
    for n, (i, f) in enumerate(thumbs):
        r, c = divmod(n, cols)
        x = pad + c * (tw + pad)
        y = pad + r * (th + label_h + pad)
        sheet.paste(Image.open(f), (x, y))
        d.text((x + 4, y + th + 6), f"{i:02d}  {shots[i]['kind']}  "
                                    f"{times[i]['start']:.1f}-{times[i]['end']:.1f}s",
               font=fnt, fill=theme.INK_2)
    sheet.save(out_path)
    shutil.rmtree(tmp, ignore_errors=True)
    return out_path
