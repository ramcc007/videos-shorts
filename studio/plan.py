"""Turn "topic, duration, notes" into a shot budget, and check the finished
script actually hits the target.

Pacing maths, all in one place:
  body seconds = target - hook - close
  a line of n words takes n / WPM * 60 seconds, plus a GAP breath after it
  so total words = (body seconds - shots * GAP) * WPM / 60
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from . import formats
from .voice import GAP, MIN_LINE, WPM

TOLERANCE = 0.10              # +/-10% of target is "on time"


@dataclass
class Budget:
    target_s: float
    body_s: float
    shots: int
    words_total: int
    words_per_shot: int
    seconds_per_shot: float
    fmt: str
    presenter: bool
    hook_s: float
    close_s: float

    def as_dict(self) -> dict:
        return asdict(self)


def budget(target_s: float, fmt: str = "long", presenter: bool | None = None) -> Budget:
    f = formats.get(fmt)
    if presenter is None:
        presenter = f.presenter_default
    hook_s = f.hook_s if presenter else 0.0
    close_s = f.close_s if presenter else 0.0

    floor = (hook_s + close_s) + 3 * f.seconds_per_shot
    if target_s < floor:
        raise SystemExit(
            f"Target {target_s:.0f}s is too short for the {fmt} format: "
            f"{hook_s + close_s:.0f}s of presenter plus a minimum 3 shots "
            f"needs {floor:.0f}s.")
    body_s = target_s - hook_s - close_s
    shots = max(3, round(body_s / f.seconds_per_shot))
    speaking_s = body_s - shots * GAP
    if speaking_s <= 0:
        raise SystemExit("Too many shots for that duration.")
    words_total = int(round(speaking_s * WPM / 60))
    return Budget(
        target_s=round(target_s, 1),
        body_s=round(body_s, 1),
        shots=shots,
        words_total=words_total,
        words_per_shot=int(round(words_total / shots)),
        seconds_per_shot=round(body_s / shots, 2),
        fmt=fmt,
        presenter=presenter,
        hook_s=hook_s,
        close_s=close_s,
    )


def estimate_body(lines: list[str]) -> float:
    """Same maths studio.voice uses, so the estimate and the render agree."""
    return sum(max(MIN_LINE, len(l.split()) / WPM * 60.0) + GAP for l in lines)


def check(lines: list[str], target_s: float, fmt: str = "long",
          presenter: bool | None = None) -> dict:
    b = budget(target_s, fmt, presenter)
    est_body = estimate_body(lines)
    est_total = est_body + b.hook_s + b.close_s
    drift = est_total - target_s
    within = abs(drift) <= target_s * TOLERANCE
    return {
        "target_s": target_s,
        "estimated_total_s": round(est_total, 1),
        "estimated_body_s": round(est_body, 1),
        "drift_s": round(drift, 1),
        "drift_pct": round(100 * drift / target_s, 1),
        "within_tolerance": within,
        "shots": len(lines),
        "shots_budgeted": b.shots,
        "format": b.fmt,
        "aspect": formats.get(b.fmt).aspect,
        "presenter": b.presenter,
        "words": sum(len(l.split()) for l in lines),
        "words_budgeted": b.words_total,
    }


def report(lines: list[str], target_s: float, fmt: str = "long",
           presenter: bool | None = None) -> str:
    c = check(lines, target_s, fmt, presenter)
    verdict = "ON TARGET" if c["within_tolerance"] else "OFF TARGET"
    arrow = "too long -- cut" if c["drift_s"] > 0 else "too short -- add"
    out = [
        f"  format        {c['format']} ({c['aspect']})"
        + ("  + Flow presenter" if c["presenter"] else "  no presenter (free)"),
        f"  target        {c['target_s']:.0f}s",
        f"  estimated     {c['estimated_total_s']:.0f}s  "
        f"({c['drift_s']:+.0f}s, {c['drift_pct']:+.0f}%)",
        f"  shots         {c['shots']} (budget {c['shots_budgeted']})",
        f"  words         {c['words']} (budget {c['words_budgeted']})",
        f"  status        {verdict}",
    ]
    if not c["within_tolerance"]:
        need = abs(int(round(c["drift_s"] * WPM / 60)))
        out.append(f"  -> {arrow} about {need} words of narration")
    return "\n".join(out)


def save(path: Path, b: Budget) -> None:
    path.write_text(json.dumps(b.as_dict(), indent=2) + "\n", encoding="utf-8")
