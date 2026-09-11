"""Animated shot rendering: one frame at a time, not one still per shot.

`draw.py` composes a finished still. This module composes the same shot at an
arbitrary progress 0.0 -> 1.0 through its own duration, so a shot becomes a
frame sequence: numbers count up, bars grow, text arrives in staggered slides.

Kinds it does not animate fall back to the still from draw.py, so adding a
shot kind never breaks the render -- it just does not move yet.
"""
from __future__ import annotations

import functools
import re

from PIL import Image, ImageDraw

from . import anim, draw, theme
from .theme import AMBER, BLUE, GREEN, INK, INK_2, INK_3, RED, SERIES

ANIMATED = {"card", "number", "bars"}


@functools.lru_cache(maxsize=4)
def _bg(w: int, h: int) -> Image.Image:
    """The gradient is identical every frame and costs ~40ms, so build once."""
    return draw.background().convert("RGBA")


def _rgba(colour, alpha: float):
    a = int(255 * anim.clamp(alpha))
    return (colour[0], colour[1], colour[2], a)


def _text(d, xy, s, fnt, colour, alpha=1.0, anchor="la"):
    if alpha <= 0.004 or not s:
        return
    d.text(xy, s, font=fnt, fill=_rgba(colour, alpha), anchor=anchor)


# --- counters --------------------------------------------------------------
_NUM = re.compile(r"^(?P<pre>[^\d\-]*)(?P<num>-?[\d,]*\.?\d+)(?P<post>.*)$", re.S)


def count_value(value: str, t: float) -> str:
    """Interpolate the numeric part of a value toward its final text.

    "$24,000" counts up through "$9,431"; "8:45" and "3.5x" keep their shape.
    Anything with no number in it is returned unchanged, so a value like "N/A"
    is safe.
    """
    m = _NUM.match(str(value).strip())
    if not m or t >= 1:
        return str(value)
    pre, raw, post = m.group("pre"), m.group("num"), m.group("post")
    try:
        target = float(raw.replace(",", ""))
    except ValueError:
        return str(value)
    cur = target * anim.out_quint(anim.clamp(t))
    if "." in raw:
        dec = len(raw.split(".")[1])
        body = f"{cur:,.{dec}f}" if "," in raw else f"{cur:.{dec}f}"
    else:
        body = f"{int(round(cur)):,}" if "," in raw else str(int(round(cur)))
    return f"{pre}{body}{post}"


# --- shot renderers --------------------------------------------------------
def _card(shot: dict, p: float, img: Image.Image) -> Image.Image:
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    W, H = theme.LOGICAL_W, theme.LOGICAL_H
    M = theme.ACTIVE.margin
    bullets = shot.get("bullets") or []

    if not bullets and not shot.get("body"):
        head = shot.get("headline", "")
        size, lines = 76, []
        while size >= 44:
            fnt = theme.font(size, "bold")
            lines = draw.wrap(head, fnt, W - 2 * M)
            if len(lines) <= 4:
                break
            size -= 8
        line_h = size * 1.26
        kicker = shot.get("kicker")
        block = len(lines) * line_h + (58 if kicker else 0)
        y = (theme.ACTIVE.body_top - 120) + max(
            0, (theme.ACTIVE.body_bottom - (theme.ACTIVE.body_top - 120) - block) / 2)

        if kicker:
            _text(d, (W / 2, y + anim.rise(p, 0.0, 0.22, 26)), kicker.upper(),
                  theme.font(22, "bold"), BLUE, anim.fade(p, 0.0, 0.18), "ma")
            y += 58
        # lines stagger, so the headline reads as it lands rather than all at once
        for i, ln in enumerate(lines):
            s0 = 0.08 + i * 0.09
            _text(d, (W / 2, y + anim.rise(p, s0, s0 + 0.3, 40)), ln, fnt, INK,
                  anim.fade(p, s0, s0 + 0.26), "ma")
            y += line_h
        rule = min(120, W * 0.12) * anim.out_cubic(anim.seg(p, 0.34, 0.6))
        if rule > 1:
            d.line([(W / 2 - rule, y + 26), (W / 2 + rule, y + 26)],
                   fill=_rgba(BLUE, 1.0), width=4)
        return Image.alpha_composite(img, layer)

    # cards with bullets: header, then bullets one by one
    y = _header(d, shot, p)
    bf = theme.font(34)
    wrapped = [draw.wrap(b, bf, W - 2 * M - 60)[:2] for b in bullets[:5]]
    block_h = sum(48 * len(w) + 22 for w in wrapped) - 22
    y = max(y, y + (theme.ACTIVE.body_bottom - y - block_h) / 2)
    for i, w in enumerate(wrapped):
        s0 = 0.22 + i * 0.12
        a = anim.fade(p, s0, s0 + 0.25)
        dx = anim.rise(p, s0, s0 + 0.3, 50)
        if a > 0.004:
            d.rounded_rectangle((M + dx, y + 8, M + dx + 14, y + 22), 7,
                                fill=_rgba(BLUE, a))
        for j, ln in enumerate(w):
            _text(d, (M + 44 + dx, y), ln, bf, INK_2 if j else INK, a)
            y += 48
        y += 22
    return Image.alpha_composite(img, layer)


def _header(d, shot: dict, p: float) -> float:
    """Kicker + headline + rule, arriving in sequence. Returns the y below it."""
    W, M = theme.LOGICAL_W, theme.ACTIVE.margin
    y = theme.ACTIVE.head_y
    if shot.get("kicker"):
        _text(d, (M, y + anim.rise(p, 0.0, 0.2, 18)), shot["kicker"].upper(),
              theme.font(20, "bold"), BLUE, anim.fade(p, 0.0, 0.16))
        y += 42
    fnt = theme.font(56, "bold")
    for i, ln in enumerate(draw.wrap(shot.get("headline", ""), fnt, W - 2 * M)[:3]):
        s0 = 0.05 + i * 0.07
        _text(d, (M + anim.rise(p, s0, s0 + 0.28, 36), y), ln, fnt, INK,
              anim.fade(p, s0, s0 + 0.24))
        y += 70
    y += 6
    if shot.get("sub"):
        sf = theme.font(30)
        for ln in draw.wrap(shot["sub"], sf, W - 2 * M - 260)[:2]:
            _text(d, (M, y), ln, sf, INK_2, anim.fade(p, 0.18, 0.4))
            y += 42
    w = 120 * anim.out_cubic(anim.seg(p, 0.16, 0.42))
    if w > 1:
        d.line([(M, y + 18), (M + w, y + 18)], fill=_rgba(BLUE, 1.0), width=4)
    return max(y + 60, theme.ACTIVE.body_top)


def _number(shot: dict, p: float, img: Image.Image) -> Image.Image:
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    W, M = theme.LOGICAL_W, theme.ACTIVE.margin
    top = theme.ACTIVE.body_top

    kicker = shot.get("kicker") or shot.get("headline", "")
    if kicker:
        _text(d, (W / 2, top - 30 + anim.rise(p, 0.0, 0.2, 22)), kicker.upper(),
              theme.font(26, "bold"), BLUE, anim.fade(p, 0.0, 0.16), "ma")

    rule = min(200, W * 0.19) * anim.out_cubic(anim.seg(p, 0.06, 0.3))
    if rule > 1:
        d.line([(W / 2 - rule, top + 15), (W / 2 + rule, top + 15)],
               fill=_rgba(RED, 1.0), width=5)

    # size on the FINAL text so the counter never reflows as digits appear
    final = str(shot["value"])
    start = 300 if len(final) <= 4 else (230 if len(final) <= 7 else 170)
    base = draw.fit(final, start, W - 2 * M)
    ct = anim.seg(p, 0.08, 0.62)
    shown = count_value(final, ct)
    scale = anim.pop(ct)
    vf = theme.font(max(12, int(round(base.size / theme.SCALE * scale))), "bold")
    _text(d, (W / 2, top + 50), shown, vf, INK, anim.fade(p, 0.05, 0.16), "ma")

    if shot.get("sub") or shot.get("caption"):
        sf = theme.font(38)
        yy = top + 50 + round(base.size / theme.SCALE) + 60
        for ln in draw.wrap(shot.get("sub") or shot["caption"], sf, W - 4 * M)[:3]:
            _text(d, (W / 2, yy + anim.rise(p, 0.55, 0.78, 24)), ln, sf, INK_2,
                  anim.fade(p, 0.55, 0.74), "ma")
            yy += 54
    return Image.alpha_composite(img, layer)


def _bars(shot: dict, p: float, img: Image.Image) -> Image.Image:
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    W, M = theme.LOGICAL_W, theme.ACTIVE.margin
    top = _header(d, shot, p)

    data = list(shot["data"])
    unit = shot.get("unit", "")
    hi = shot.get("highlight")
    base = theme.ACTIVE.body_bottom - theme.ACTIVE.label_room
    chart_top = top + 40
    peak = max(v for _, v in data) or 1

    n = len(data)
    span = W - 2 * M
    slot = span / n
    bw = min(slot * 0.56, 190)

    axis_w = span * anim.out_cubic(anim.seg(p, 0.2, 0.5))
    if axis_w > 1:
        d.line([(M, base + 3), (M + axis_w, base + 3)], fill=_rgba(INK_3, 0.6), width=3)

    for i, (label, v) in enumerate(data):
        s0 = 0.3 + i * 0.11                   # each bar grows after the one before
        g = anim.out_back(anim.seg(p, s0, s0 + 0.42), 0.9)
        full = (base - chart_top) * (v / peak)
        h = max(0, full * g)
        cx = M + slot * (i + 0.5)
        colour = (RED if i == hi else SERIES[i % len(SERIES)])
        if h > 2:
            d.rounded_rectangle((cx - bw / 2, base - h, cx + bw / 2, base), 12,
                                fill=_rgba(colour, 1.0))
        # the value lands only once its bar has arrived
        _text(d, (cx, base - max(0, full) - 58), draw.fmt(v, unit),
              theme.font(30, "bold"), INK, anim.fade(p, s0 + 0.3, s0 + 0.5), "ma")
        _text(d, (cx, base + 18), str(label)[:16], theme.font(26), INK_2,
              anim.fade(p, s0 + 0.1, s0 + 0.32), "ma")
    return Image.alpha_composite(img, layer)


_KINDS = {"card": _card, "number": _number, "bars": _bars}


PUNCH = 0.035          # how far a cut pushes in, as a fraction of the frame
PUNCH_FOR = 0.18       # ... and over what share of the shot it settles


def _punch(img: Image.Image, p: float) -> Image.Image:
    """Scale-down-to-rest at the top of a shot, so a cut has some force.

    A hard cut between two static frames reads as a slideshow. Easing out of a
    slight over-scale gives the cut a push without moving anything the viewer
    is trying to read.
    """
    t = anim.seg(p, 0.0, PUNCH_FOR)
    if t >= 1:
        return img
    z = 1 + PUNCH * (1 - anim.out_cubic(t))
    w, h = img.size
    zw, zh = int(w * z), int(h * z)
    big = img.resize((zw, zh), Image.LANCZOS)
    return big.crop(((zw - w) // 2, (zh - h) // 2,
                     (zw - w) // 2 + w, (zh - h) // 2 + h))


def frame(shot: dict, p: float) -> Image.Image:
    """One frame of `shot` at progress p (0..1). Caller must hold native_scale."""
    kind = shot.get("kind")
    p = anim.clamp(p)
    if kind not in _KINDS:
        return draw.render_shot(shot).convert("RGB")
    img = _bg(theme.OUT_W, theme.OUT_H).copy()
    return _punch(_KINDS[kind](shot, p, img).convert("RGB"), p)
