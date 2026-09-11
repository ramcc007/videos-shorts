"""Easing and timing for animated shots.

Every shot renders as a sequence of frames rather than one still. A shot's
progress runs 0.0 -> 1.0 across its own duration, and each element inside it
claims a slice of that: `seg(p, 0.1, 0.4)` is 0 before 10%, ramps to 1 by 40%,
and stays there. Elements overlap deliberately -- staggering entrances is most
of what separates motion graphics from a slideshow.
"""
from __future__ import annotations


def clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return lo if v < lo else hi if v > hi else v


def seg(p: float, start: float, end: float) -> float:
    """Progress of one element's own window, as a 0..1 fraction."""
    if end <= start:
        return 1.0 if p >= end else 0.0
    return clamp((p - start) / (end - start))


# --- easings ---------------------------------------------------------------
def out_cubic(t: float) -> float:
    """Fast start, soft landing. The default for anything arriving."""
    return 1 - (1 - t) ** 3


def out_quint(t: float) -> float:
    """Sharper version, for counters that should settle decisively."""
    return 1 - (1 - t) ** 5


def out_back(t: float, overshoot: float = 1.5) -> float:
    """Overshoots then settles -- gives a bar or a title some weight."""
    c = overshoot + 1
    return 1 + c * (t - 1) ** 3 + overshoot * (t - 1) ** 2


def in_out(t: float) -> float:
    return 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def pop(t: float, peak: float = 0.14) -> float:
    """Scale multiplier that lands oversized and settles to 1.0.

    A counter that stops dead looks mechanical; one that arrives slightly big
    and relaxes reads as though it hit something.
    """
    return 1.0 + peak * (1 - out_cubic(clamp(t)))


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def fade(p: float, start: float, end: float, ease=out_cubic) -> float:
    """Opacity 0..1 for an element entering over [start, end]."""
    return ease(seg(p, start, end))


def rise(p: float, start: float, end: float, distance: float,
         ease=out_cubic) -> float:
    """Vertical offset that decays to 0 -- pair with fade() for a slide-up."""
    return distance * (1 - ease(seg(p, start, end)))
