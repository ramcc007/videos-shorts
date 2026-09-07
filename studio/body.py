"""Turn a SHOTS list into videos/<topic>/out/body.mp4.

videos/<topic>/body/build_body.py holds the script and calls straight into
here, so a fix to the renderer reaches every video instead of the one you
happen to be editing.
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

from . import captions, config, photos, render, shots as shotlib, voice


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Render the body of one explainer video.")
    p.add_argument("--reuse-voice", action="store_true",
                   help="use the cloned Chatterbox narration from Kaggle (the real take)")
    p.add_argument("--voice", choices=("chatterbox", "kokoro", "silent"),
                   help="override the narration source (default: kokoro draft)")
    p.add_argument("--music", type=Path, help="path to a CC0/CC BY music bed")
    p.add_argument("--no-photos", action="store_true",
                   help="skip Commons downloads; photo shots become text cards")
    p.add_argument("--stills-only", action="store_true",
                   help="draw the stills and stop -- fastest way to check a script")
    p.add_argument("--force-stills", action="store_true",
                   help="redraw stills even if they already exist")
    return p.parse_args(argv)


def _default_music(explicit: Path | None) -> Path | None:
    if explicit:
        return explicit
    for ext in ("*.mp3", "*.m4a", "*.wav", "*.flac", "*.ogg"):
        found = sorted((config.ASSETS / "music").glob(ext))
        if found:
            return found[0]
    return None


def build(topic: str, SHOTS: list[dict], argv=None) -> Path | None:
    args = parse_args(argv)
    render.require_ffmpeg()
    shotlib.validate(SHOTS)

    vdir = config.video_dir(topic)
    bdir = vdir / "body"
    out_dir = vdir / "out"
    work = bdir / "_work"
    for d in (out_dir, work):
        d.mkdir(parents=True, exist_ok=True)

    print(f"\n=== {topic} ===")
    print(shotlib.summary(SHOTS))

    # 1. narration ---------------------------------------------------------
    source = args.voice or ("chatterbox" if args.reuse_voice else "kokoro")
    lines = shotlib.narration(SHOTS)
    print(f"\n[1/6] narration: {source}")
    narration = voice.load(source, lines, work, kaggle_out=bdir / "kaggle_out")
    durations = narration.durations()
    print(f"      {len(lines)} lines, {narration.total:.1f}s total "
          f"({narration.total/60:.1f} min), source={narration.source}")

    # 2. stills ------------------------------------------------------------
    print(f"[2/6] drawing {len(SHOTS)} stills")
    stills_dir = bdir / "stills"
    existing = sorted(stills_dir.glob("*.png"))
    if len(existing) == len(SHOTS) and not args.force_stills:
        print("      reusing existing stills (--force-stills to redraw)")
        stills = existing
    else:
        stills = render.render_stills(SHOTS, stills_dir, bdir / "photos",
                                      fetch_photos=not args.no_photos)
    photos.write_credits_md(bdir / "photos", out_dir / "CREDITS.md", topic)

    if args.stills_only:
        print(f"\nStills only. See {stills_dir}")
        return None

    # 3. motion ------------------------------------------------------------
    print(f"[3/6] shot clips (generated footage where present, Ken Burns otherwise)")
    t0 = time.time()
    clips = render.make_shot_clips(SHOTS, stills, durations, bdir / "clips",
                                   bdir / "footage")
    silent_video = render.concat_clips(clips, work / "silent.mp4")
    print(f"      {len(clips)} clips in {time.time()-t0:.0f}s")

    # 4. captions ----------------------------------------------------------
    print("[4/6] captions")
    ass = captions.write_ass(narration.times, work / "captions.ass")

    # 5. audio -------------------------------------------------------------
    music = _default_music(args.music)
    print(f"[5/6] audio mix ({'music: ' + music.name if music else 'no music bed'})")
    mixed = render.mix_audio(narration.wav, music, work / "mixed.wav", narration.total)

    # 6. final -------------------------------------------------------------
    print("[6/6] burn captions + mux")
    body = render.burn_and_mux(silent_video, mixed, ass, out_dir / "body.mp4")

    # verification ---------------------------------------------------------
    dur = render.probe_duration(body)
    frames = render.probe_frames(body)
    expected = sum(max(2, round(d * 25)) for d in durations)
    drift = dur - narration.total
    print("\n--- checks " + "-" * 52)
    print(f"  duration      {dur:7.2f}s   (narration {narration.total:.2f}s, drift {drift:+.2f}s)")
    print(f"  frames        {frames:7d}    (expected {expected})")
    ok = True
    if abs(drift) > 0.5:
        print("  WARNING: audio/video drift over 0.5s -- check the narration source.")
        ok = False
    if frames != expected:
        print(f"  WARNING: frame count {frames} != sum of shot clips {expected}.")
        ok = False
    print(f"  status        {'PASS' if ok else 'CHECK THE WARNINGS ABOVE'}")

    sheet = render.contact_sheet(body, narration.times, SHOTS, out_dir / "contact_sheet.png")
    print(f"  contact sheet {sheet}")
    print(f"\nBody ready: {body}")
    if narration.source != "chatterbox":
        print("NOTE: this is a DRAFT voice. Re-run with --reuse-voice before stitching.")
    return body
