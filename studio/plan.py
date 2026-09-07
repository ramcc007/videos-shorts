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

from .voice import GAP, MIN_LINE, WPM

HOOK_S = 8.0
CLOSE_S = 8.0
SECONDS_PER_SHOT = 8.0        # a still held much longer than this goes stale
TOLERANCE = 0.10              # +/-10% of target is "on time"


@dataclass
class Budget:
    target_s: float
    body_s: float
    shots: int
    words_total: int
    words_per_shot: int
    seconds_per_shot: float

    def as_dict(self) -> dict:
        return asdict(self)


def budget(target_s: float) -> Budget:
    if target_s < 45:
        raise SystemExit("Target duration under 45s leaves no room for a body "
                         "after the 8s hook and 8s close.")
    body_s = target_s - HOOK_S - CLOSE_S
    shots = max(3, round(body_s / SECONDS_PER_SHOT))
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
    )


def estimate_body(lines: list[str]) -> float:
    """Same maths studio.voice uses, so the estimate and the render agree."""
    return sum(max(MIN_LINE, len(l.split()) / WPM * 60.0) + GAP for l in lines)


def check(lines: list[str], target_s: float) -> dict:
    b = budget(target_s)
    est_body = estimate_body(lines)
    est_total = est_body + HOOK_S + CLOSE_S
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
        "words": sum(len(l.split()) for l in lines),
        "words_budgeted": b.words_total,
    }


def report(lines: list[str], target_s: float) -> str:
    c = check(lines, target_s)
    verdict = "ON TARGET" if c["within_tolerance"] else "OFF TARGET"
    arrow = "too long -- cut" if c["drift_s"] > 0 else "too short -- add"
    out = [
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
