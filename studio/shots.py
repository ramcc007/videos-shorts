"""Shot schema + validation.

A SHOTS list is the whole script of a video. One shot == one narration line ==
one still == one caption block. Keeping that 1:1 is what makes the captions
land on the voice without any alignment model.
"""
from __future__ import annotations

KINDS = {"card", "number", "bars", "line", "rating", "pie", "photo", "clip"}

# kind -> keys that must be present beyond the universal ones
_REQUIRED = {
    "card":   (),
    "number": ("value",),
    "bars":   ("data",),
    "line":   ("data",),
    "rating": ("data",),
    "pie":    ("data",),
    "photo":  (),
    "clip":   ("prompt",),
}


class ShotError(ValueError):
    pass


def validate(shots: list[dict]) -> list[dict]:
    """Fail loudly at the top of a render instead of 4 minutes in."""
    if not shots:
        raise ShotError("SHOTS is empty.")
    for i, s in enumerate(shots):
        where = f"SHOTS[{i}]"
        kind = s.get("kind")
        if kind not in KINDS:
            raise ShotError(f"{where}: kind={kind!r} is not one of {sorted(KINDS)}")
        if not s.get("say", "").strip():
            raise ShotError(f"{where}: missing 'say' (the narration line)")
        if not s.get("headline", "").strip() and kind not in ("number", "clip"):
            raise ShotError(f"{where}: missing 'headline'")
        for key in _REQUIRED[kind]:
            if key not in s:
                raise ShotError(f"{where}: kind={kind!r} needs a {key!r} key")
        if kind in ("bars", "line", "rating", "pie"):
            data = s["data"]
            if not data or not all(
                isinstance(d, (list, tuple)) and len(d) == 2 for d in data
            ):
                raise ShotError(f"{where}: 'data' must be [(label, number), ...]")
            for label, value in data:
                if not isinstance(value, (int, float)):
                    raise ShotError(f"{where}: value for {label!r} is not a number")
        if kind == "photo" and not (s.get("query") or s.get("file")):
            raise ShotError(f"{where}: photo needs 'query' or 'file' (a Commons File: page)")
        if kind == "clip":
            if not s.get("prompt", "").strip():
                raise ShotError(f"{where}: clip needs a 'prompt' for the video model")
            if s.get("ref") and not str(s["ref"]).strip():
                raise ShotError(f"{where}: clip 'ref' is empty; drop it or point it at a still")
        if kind == "pie" and sum(v for _, v in s["data"]) <= 0:
            raise ShotError(f"{where}: pie values sum to zero")
    return shots


def narration(shots: list[dict]) -> list[str]:
    return [s["say"].strip() for s in shots]


def summary(shots: list[dict]) -> str:
    lines = [f"{len(shots)} shots"]
    for i, s in enumerate(shots):
        head = s.get("headline") or s.get("value") or ""
        lines.append(f"  {i:>2}. {s['kind']:<6} {head[:52]}")
    return "\n".join(lines)
