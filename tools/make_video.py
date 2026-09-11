#!/usr/bin/env python3
"""The orchestrator: topic + duration + notes in, finished video out.

    python tools/make_video.py new    --topic solar-payback --duration 120 \
                                      --notes "UK angle, sceptical tone"
    python tools/make_video.py check  --topic solar-payback     # script vs target
    python tools/make_video.py flow   --topic solar-payback     # the two Flow prompts
    python tools/make_video.py watch  --topic solar-payback     # wait, then finish it
    python tools/make_video.py run    --topic solar-payback     # finish it now
    python tools/make_video.py status --topic solar-payback

Flow is the one manual step: it has no public API, so `flow` prints the two
prompts to paste, and `watch` picks the clips up the moment you save them into
videos/<topic>/flow/ and runs everything after that unattended.

Every step records itself in state.json, so a failure resumes rather than
starting over.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from studio import config, formats, plan, presenter, script, state  # noqa: E402

ROOT = config.ROOT
POLL = 15          # seconds between checks while watching for the Flow clips


def run_step(argv: list[str], what: str) -> None:
    print(f"\n>>> {what}\n    $ {' '.join(argv)}")
    proc = subprocess.run([sys.executable, *argv], cwd=ROOT)
    if proc.returncode != 0:
        raise SystemExit(f"\n[make_video] step failed: {what}\n"
                         "Fix it and re-run; completed steps are skipped.")


# --------------------------------------------------------------------------- #
def brief_of(topic: str) -> dict:
    """The video's brief.

    brief.json is the committed record and travels with a clone. state.json is
    local progress and is git-ignored, so on a fresh clone it does not exist --
    reading the brief from there alone made every pulled video look unbriefed,
    silently falling back to long/presenter and demanding Flow clips.
    """
    path = config.video_dir(topic) / "brief.json"
    if path.is_file():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            print(f"  WARNING: {path} is unreadable ({e}); "
                  f"falling back to state.json", file=sys.stderr)
    return state.load(topic).get("brief", {})


def cmd_new(args) -> None:
    topic = args.topic
    vdir = config.video_dir(topic)
    if vdir.exists() and not args.force:
        raise SystemExit(f"{vdir} already exists (use --force).")

    run_step(["tools/new_video.py", topic] + (["--force"] if args.force else []),
             f"scaffolding videos/{topic}")

    fmt = formats.get(args.format)
    presenter_on = fmt.presenter_default if args.presenter is None else args.presenter
    b = plan.budget(args.duration, args.format, presenter_on)
    st = state.load(topic)
    st["brief"] = {"topic": topic, "duration_s": args.duration,
                   "format": args.format, "presenter": presenter_on,
                   "notes": args.notes or "", "budget": b.as_dict()}
    state.save(topic, st)
    state.mark(topic, "brief", f"{args.duration:.0f}s target")
    (vdir / "brief.json").write_text(json.dumps(st["brief"], indent=2) + "\n",
                                     encoding="utf-8")

    shape = (f"hook {b.hook_s:.0f}s + body {b.body_s:.0f}s + close {b.close_s:.0f}s"
             if presenter_on else f"body {b.body_s:.0f}s, no presenter")
    cost = ("~40 Flow credits" if presenter_on else
            "NO Flow credits -- free at the margin")
    print(f"""
=== brief: {topic} ===
  format        {fmt.name} ({fmt.aspect})
  duration      {b.target_s:.0f}s  ({shape})
  shot budget   {b.shots} shots, ~{b.seconds_per_shot:.1f}s each
  word budget   {b.words_total} words of narration (~{b.words_per_shot} per shot)
  presenter     {'yes' if presenter_on else 'no'}  ({cost})
  notes         {args.notes or '(none)'}

Next: the script goes in
  videos/{topic}/body/build_body.py
Fill in SHOTS{', HOOK and CLOSE' if presenter_on else ' (HOOK/CLOSE not needed)'}, then:
  python tools/make_video.py check --topic {topic}
""")


def cmd_check(args) -> None:
    topic = args.topic
    st = state.load(topic)
    brief = brief_of(topic)
    target = args.duration or brief.get("duration_s")
    fmt = args.format or brief.get("format", "long")
    presenter_on = brief.get("presenter", formats.get(fmt).presenter_default)
    if not target:
        raise SystemExit("No target duration. Pass --duration or run `new` first.")

    mod = script.load(topic)
    from studio import shots as shotlib
    shotlib.validate(mod.SHOTS)
    lines = [s["say"].strip() for s in mod.SHOTS]

    print(f"\n=== script check: {topic} ===")
    print(shotlib.summary(mod.SHOTS))
    print()
    print(plan.report(lines, target, fmt, presenter_on))

    if presenter_on:
        for name in ("HOOK", "CLOSE"):
            val = getattr(mod, name, "")
            if not val or val.startswith("Write the"):
                print(f"  WARNING: {name} is still the placeholder.")

    c = plan.check(lines, target, fmt, presenter_on)
    if c["within_tolerance"]:
        state.mark(topic, "script", f"{c['estimated_total_s']:.0f}s est, "
                                    f"{len(lines)} shots, {fmt}")
        nxt = "flow" if presenter_on else "run"
        print(f"\nNext:  python tools/make_video.py {nxt} --topic {topic}")
    else:
        print("\nAdjust the narration, then run check again.")


def cmd_flow(args) -> None:
    topic = args.topic
    brief = brief_of(topic)
    if brief and not brief.get("presenter", True):
        raise SystemExit(
            f"{topic} is set up without a presenter, so there are no Flow prompts.\n"
            f"  Render it:  python tools/make_video.py run --topic {topic}\n"
            f"  Or re-brief with --presenter to add a hook and close.")
    mod = script.load(topic)
    path = presenter.write_sheet(topic, mod.HOOK, mod.CLOSE)
    print(presenter.sheet(mod.HOOK, mod.CLOSE, topic))
    print(f"\n(also saved to {path})")
    state.mark(topic, "flow_prompts", str(path))
    print(f"\nThen:  python tools/make_video.py watch --topic {topic}")


def _clips_ready(topic: str) -> bool:
    flow = config.video_dir(topic) / "flow"
    return (flow / "hook.mp4").exists() and (flow / "close.mp4").exists()


def _stable(topic: str) -> bool:
    """Both files present and not still being written."""
    flow = config.video_dir(topic) / "flow"
    sizes = [(flow / f"{n}.mp4").stat().st_size for n in ("hook", "close")]
    time.sleep(3)
    return sizes == [(flow / f"{n}.mp4").stat().st_size for n in ("hook", "close")] \
        and all(s > 10_000 for s in sizes)


def cmd_watch(args) -> None:
    topic = args.topic
    flow = config.video_dir(topic) / "flow"
    flow.mkdir(parents=True, exist_ok=True)
    print(f"[watch] waiting for {flow / 'hook.mp4'} and close.mp4")
    print("[watch] generate them in Flow and save them there; Ctrl-C to stop.")
    waited = 0
    while not (_clips_ready(topic) and _stable(topic)):
        time.sleep(POLL)
        waited += POLL
        if waited % 300 == 0:
            missing = [n for n in ("hook", "close")
                       if not (flow / f"{n}.mp4").exists()]
            print(f"  [{waited//60} min] still waiting for: {', '.join(missing) or 'files to settle'}")
    print("[watch] both clips present -- continuing")
    state.mark(topic, "flow_clips", "detected by watcher")
    cmd_run(args)


def cmd_run(args) -> None:
    topic = args.topic
    vdir = config.video_dir(topic)
    brief = brief_of(topic)
    fmt = args.format or brief.get("format", "long")
    presenter_on = brief.get("presenter", formats.get(fmt).presenter_default)

    _warn_if_off_target(topic, fmt, presenter_on)

    if not presenter_on:
        # No Flow clips, so no clip cleanup, no voice reference to clone from,
        # and nothing to stitch: the body IS the video. Narration comes from
        # the local Kokoro voice, which costs nothing.
        suffix = "" if fmt == "long" else f"_{fmt}"
        voice = ["--voice", args.voice] if args.voice else ["--voice", "kokoro"]
        run_step([f"videos/{topic}/body/build_body.py", "--format", fmt, *voice],
                 f"rendering the {fmt} body (no presenter)")
        state.mark(topic, "body")
        final = vdir / "out" / f"body{suffix}.mp4"
        _write_upload_notes(topic)
        print(f"""
=== done: {topic} ===
  cut           {final}
  contact sheet {vdir / 'out' / f'contact_sheet{suffix}.png'}
  upload notes  {vdir / 'out' / 'upload.md'}

No Flow credits were spent on this one.
Tick the synthetic-content disclosure on upload.
""")
        return

    if not _clips_ready(topic):
        raise SystemExit(
            f"No hook.mp4 / close.mp4 in {vdir / 'flow'}.\n"
            f"  Get the prompts:  python tools/make_video.py flow --topic {topic}\n"
            f"  Or wait for them: python tools/make_video.py watch --topic {topic}")
    state.mark(topic, "flow_clips", "present")

    if args.force or not state.is_done(topic, "fix_clips"):
        for clip in ("hook", "close"):
            run_step(["tools/fix_clip.py", "--topic", topic, "--clip", clip],
                     f"cleaning {clip}.mp4")
        state.mark(topic, "fix_clips")

    if args.force or not state.is_done(topic, "voice_ref"):
        run_step(["tools/cut_voice_ref.py", "--topic", topic], "cutting the voice reference")
        state.mark(topic, "voice_ref")

    if args.skip_voice:
        print("\n[make_video] --skip-voice: rendering with a draft voice, not the clone.")
    else:
        if args.force or not state.is_done(topic, "voice_clone"):
            run_step(["tools/kaggle_run.py", "--job", "voice", "--topic", topic],
                     "cloning the voice on a Kaggle GPU (~8 min)")
            state.mark(topic, "voice_clone")
        if args.force or not state.is_done(topic, "match_eq"):
            run_step(["tools/match_eq.py", "--topic", topic],
                     "matching the body's tone to the hook")
            state.mark(topic, "match_eq")

    body_args = ["--voice", "silent"] if args.skip_voice else ["--reuse-voice"]
    run_step([f"videos/{topic}/body/build_body.py", "--format", fmt, *body_args],
             "rendering the body")
    state.mark(topic, "body")

    run_step(["tools/stitch.py", "--topic", topic], "stitching the three parts")
    state.mark(topic, "stitch")

    run_step(["tools/review.py", "--topic", topic], "review checks")
    state.mark(topic, "review")

    _write_upload_notes(topic)
    print(f"""
=== done: {topic} ===
  cut           {vdir / 'out' / f'{topic}_final.mp4'}
  contact sheet {vdir / 'out' / 'contact_sheet.png'}
  upload notes  {vdir / 'out' / 'upload.md'}

Watch the two joins before you publish, and tick the synthetic-content
disclosure on upload.
""")


def _warn_if_off_target(topic: str, fmt: str, presenter_on: bool) -> None:
    """Rendering an off-target script wastes a render; say so before it starts."""
    brief = brief_of(topic)
    target = brief.get("duration_s")
    if not target:
        return
    try:
        c = plan.check(script.lines(topic), target, fmt, presenter_on)
    except SystemExit:
        return
    if not c["within_tolerance"]:
        print(f"\n  WARNING: script is {c['drift_s']:+.0f}s off a {target:.0f}s target "
              f"({c['drift_pct']:+.0f}%). Rendering anyway.\n"
              f"           Fix it with: python tools/make_video.py check --topic {topic}\n")


def _write_upload_notes(topic: str) -> None:
    """Render out/upload.md from seo.json when it exists.

    seo.json is written by the vidIQ step, which runs in a Claude session --
    vidIQ is an MCP tool, not something a local script can call.
    """
    vdir = config.video_dir(topic)
    seo_path = vdir / "seo.json"
    out = vdir / "out" / "upload.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    brief = brief_of(topic)

    lines = [f"# Upload notes — {topic}", ""]
    if seo_path.exists():
        seo = json.loads(seo_path.read_text(encoding="utf-8"))
        lines += ["## Title options (vidIQ, highest score first)", ""]
        for t in seo.get("titles", []):
            lines.append(f"- **{t['score']}** — {t['title']}")
        if seo.get("keywords"):
            lines += ["", "## Keywords", ""]
            for k in seo["keywords"]:
                lines.append(f"- `{k['keyword']}` — overall {k.get('overall', '?')}, "
                             f"volume {k.get('volume', '?')}, comp {k.get('competition', '?')}")
        if seo.get("description"):
            lines += ["", "## Description", "", seo["description"]]
        if seo.get("tags"):
            lines += ["", "## Tags", "", ", ".join(seo["tags"])]
    else:
        lines += ["_No seo.json yet._ Ask Claude in a session to run the vidIQ",
                  "title and keyword step for this topic; it writes seo.json and",
                  "this file is regenerated from it.", ""]
        if brief.get("notes"):
            lines += [f"Brief notes: {brief['notes']}", ""]

    credits = vdir / "out" / "CREDITS.md"
    if credits.exists():
        lines += ["", "## Asset credits (paste into the description)", "",
                  credits.read_text(encoding="utf-8")]

    lines += ["", "## Before publishing", "",
              "- [ ] Watch both joins", "- [ ] Check the contact sheet",
              "- [ ] Tick YouTube's synthetic-content disclosure",
              "- [ ] Paste the asset credits into the description"]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def cmd_status(args) -> None:
    topic = args.topic
    brief = brief_of(topic)
    print(f"\n=== {topic} ===")
    if brief:
        print(f"  target {brief.get('duration_s')}s   notes: {brief.get('notes') or '(none)'}")
    print(state.summary(topic))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp):
        sp.add_argument("--topic", required=True)
        return sp

    n = common(sub.add_parser("new", help="start a video from topic/duration/notes"))
    n.add_argument("--duration", type=float, required=True, help="target seconds")
    n.add_argument("--format", choices=("long", "short"), default="long",
                   help="long = 16:9 1080p, short = 9:16 1080x1920")
    n.add_argument("--presenter", action=argparse.BooleanOptionalAction, default=None,
                   help="Flow hook and close (default: on for long, off for short)")
    n.add_argument("--notes", help="angle, audience, tone, must-mentions")
    n.add_argument("--force", action="store_true")
    n.set_defaults(func=cmd_new)

    c = common(sub.add_parser("check", help="does the script hit the target duration?"))
    c.add_argument("--duration", type=float)
    c.add_argument("--format", choices=("long", "short"))
    c.set_defaults(func=cmd_check)

    common(sub.add_parser("flow", help="print the Flow prompts")).set_defaults(func=cmd_flow)

    for name, fn, helptext in (("watch", cmd_watch, "wait for the Flow clips, then finish"),
                               ("run", cmd_run, "run everything after Flow, now")):
        s = common(sub.add_parser(name, help=helptext))
        s.add_argument("--skip-voice", action="store_true",
                       help="draft voice instead of the Kaggle clone")
        s.add_argument("--format", choices=("long", "short"))
        s.add_argument("--voice", choices=("chatterbox", "kokoro", "silent"))
        s.add_argument("--force", action="store_true", help="redo completed steps")
        s.set_defaults(func=fn)

    common(sub.add_parser("status", help="what is done so far")).set_defaults(func=cmd_status)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
