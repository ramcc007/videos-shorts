"""Every still frame in the body, drawn with Pillow.

Deterministic, crisp, free. No matplotlib -- coordinates are hand-placed so the
charts sit in the same optical grid as the cards.

All coordinates in this module are written in 1080p logical points and scaled
up to the 1440p render canvas by px(). That keeps the numbers readable while
the output stays oversampled for the Ken Burns move.
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from . import theme
from .theme import (AMBER, BLUE, GREEN, INK, INK_2, INK_3, NAVY, NAVY_HI,
                    NAVY_LO, PANEL, PANEL_EDGE, RED, RENDER_H, RENDER_W, SERIES)

MARGIN = 110          # logical px
HEAD_Y = 108
BODY_TOP = 330
# Nothing may be drawn below BODY_BOTTOM: the burned-in caption plate owns the
# bottom of the frame (two 50px lines + padding + a 64px margin ~= y 876 up).
# Charts that hang labels *below* their baseline subtract further, see LABEL_ROOM.
BODY_BOTTOM = 858
LABEL_ROOM = 74
CONTENT_W = 1920 - 2 * MARGIN


def px(v: float) -> int:
    return int(round(v * theme.SCALE))


def _f(size: int, weight: str = "regular"):
    return theme.font(size, weight)


# --------------------------------------------------------------------------- #
# primitives
# --------------------------------------------------------------------------- #
def background() -> Image.Image:
    """Dark navy vertical gradient with a soft corner glow."""
    img = Image.new("RGB", (RENDER_W, RENDER_H), NAVY)
    d = ImageDraw.Draw(img)
    for y in range(RENDER_H):
        t = y / max(1, RENDER_H - 1)
        # ease-out so the top third stays lighter, like the reference deck
        t = t ** 0.85
        c = tuple(int(NAVY_HI[i] + (NAVY_LO[i] - NAVY_HI[i]) * t) for i in range(3))
        d.line([(0, y), (RENDER_W, y)], fill=c)

    glow = Image.new("RGB", (RENDER_W, RENDER_H), (0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([px(1250), px(-420), px(2400), px(560)], fill=(26, 52, 84))
    glow = glow.filter(ImageFilter.GaussianBlur(px(150)))
    return Image.blend(img, Image.blend(img, glow, 0.55), 0.45)


def rounded(d: ImageDraw.ImageDraw, box, radius: int, fill=None, outline=None,
            width: int = 2) -> None:
    d.rounded_rectangle(
        [px(box[0]), px(box[1]), px(box[2]), px(box[3])],
        radius=px(radius), fill=fill, outline=outline,
        width=px(width) if outline else 0,
    )


def wrap(text: str, fnt, max_logical_w: int) -> list[str]:
    max_w = px(max_logical_w)
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if fnt.getlength(trial) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def text(d, xy, s, fnt, fill=INK, anchor="la") -> None:
    d.text((px(xy[0]), px(xy[1])), s, font=fnt, fill=fill, anchor=anchor)


def header(d, shot: dict, max_lines: int = 2) -> float:
    """Draw the kicker + headline. Returns the logical y where content may start."""
    y = HEAD_Y
    kicker = shot.get("kicker")
    if kicker:
        text(d, (MARGIN, y), kicker.upper(), _f(20, "bold"), BLUE)
        y += 42

    fnt = _f(56, "bold")
    lines = wrap(shot.get("headline", ""), fnt, CONTENT_W)[:max_lines]
    for ln in lines:
        text(d, (MARGIN, y), ln, fnt, INK)
        y += 70
    y += 6

    sub = shot.get("sub")
    if sub:
        sfnt = _f(30)
        for ln in wrap(sub, sfnt, CONTENT_W - 260)[:2]:
            text(d, (MARGIN, y), ln, sfnt, INK_2)
            y += 42

    d.line([px(MARGIN), px(y + 18), px(MARGIN + 120), px(y + 18)],
           fill=BLUE, width=px(4))
    return max(y + 60, BODY_TOP)


def _nice_bounds(lo: float, hi: float) -> tuple[float, float]:
    """Round an axis out to human numbers so ticks read 0/50/100, not 34.5."""
    span = hi - lo or 1
    mag = 10 ** math.floor(math.log10(span / 4))
    for mult in (1, 2, 2.5, 5, 10):
        step = mag * mult
        if step * 4 >= span:
            break
    lo2 = math.floor(lo / step) * step
    return lo2, lo2 + step * 4


def fmt(v: float, unit: str = "") -> str:
    if abs(v - round(v)) < 1e-9:
        s = f"{int(round(v)):,}"
    elif abs(v) < 10:
        s = f"{v:.1f}"
    else:
        s = f"{v:,.1f}"
    return f"{s}{unit}"


# --------------------------------------------------------------------------- #
# shot renderers -- each returns a full-canvas RGB image
# --------------------------------------------------------------------------- #
def top_of(y: float) -> float:
    """The top of the free content area, given where the header ended."""
    return y


def card(shot: dict) -> Image.Image:
    img = background()
    d = ImageDraw.Draw(img)
    y = header(d, shot, max_lines=3)

    bullets = shot.get("bullets") or []
    if bullets:
        bf = _f(34)
        wrapped = [wrap(b, bf, CONTENT_W - 60)[:2] for b in bullets[:5]]
        block_h = sum(48 * len(w) + 22 for w in wrapped) - 22
        y = max(y, top_of(y) + (BODY_BOTTOM - top_of(y) - block_h) / 2)
        for w in wrapped:
            rounded(d, (MARGIN, y + 8, MARGIN + 14, y + 22), 7, fill=BLUE)
            for j, ln in enumerate(w):
                text(d, (MARGIN + 44, y), ln, bf, INK_2 if j else INK)
                y += 48
            y += 22
    elif shot.get("body"):
        bf = _f(38)
        lines = wrap(shot["body"], bf, CONTENT_W - 200)[:6]
        y = max(y, top_of(y) + (BODY_BOTTOM - top_of(y) - 56 * len(lines)) / 2)
        for ln in lines:
            text(d, (MARGIN, y), ln, bf, INK_2)
            y += 56
    return img


def number(shot: dict) -> Image.Image:
    img = background()
    d = ImageDraw.Draw(img)
    kicker = shot.get("kicker") or shot.get("headline", "")
    if kicker:
        text(d, (960, 300), kicker.upper(), _f(26, "bold"), BLUE, anchor="ma")

    value = str(shot["value"])
    size = 300 if len(value) <= 4 else (230 if len(value) <= 7 else 170)
    text(d, (960, 380), value, _f(size, "bold"), INK, anchor="ma")

    sub = shot.get("sub") or shot.get("caption")
    if sub:
        sf = _f(38)
        yy = 380 + size + 60
        for ln in wrap(sub, sf, 1300)[:3]:
            text(d, (960, yy), ln, sf, INK_2, anchor="ma")
            yy += 54

    d.line([px(760), px(345), px(1160), px(345)], fill=RED, width=px(5))
    return img


def bars(shot: dict) -> Image.Image:
    img = background()
    d = ImageDraw.Draw(img)
    top = header(d, shot)
    data = list(shot["data"])
    unit = shot.get("unit", "")

    base = BODY_BOTTOM - LABEL_ROOM
    avail_h = base - top - 70
    peak = max(v for _, v in data)
    floor = min(0, min(v for _, v in data))
    span = peak - floor or 1

    n = len(data)
    gap = 46 if n <= 5 else 28
    bw = min(210, (CONTENT_W - gap * (n - 1)) / n)
    total_w = bw * n + gap * (n - 1)
    x = MARGIN + (CONTENT_W - total_w) / 2

    highlight = shot.get("highlight")
    for i, (label, v) in enumerate(data):
        h = avail_h * (v - floor) / span
        colour = RED if (highlight is not None and i == highlight) else BLUE
        rounded(d, (x, base - h, x + bw, base), 10, fill=colour)
        text(d, (x + bw / 2, base - h - 48), fmt(v, unit), _f(32, "bold"),
             INK, anchor="ma")
        lf = _f(26)
        yy = base + 18
        for ln in wrap(str(label), lf, bw + gap - 6)[:2]:
            text(d, (x + bw / 2, yy), ln, lf, INK_2, anchor="ma")
            yy += 34
        x += bw + gap

    d.line([px(MARGIN), px(base + 3), px(1920 - MARGIN), px(base + 3)],
           fill=PANEL_EDGE, width=px(2))
    return img


def line(shot: dict) -> Image.Image:
    img = background()
    d = ImageDraw.Draw(img)
    top = header(d, shot)
    data = list(shot["data"])
    unit = shot.get("unit", "")

    base, left = BODY_BOTTOM - LABEL_ROOM + 20, MARGIN + 40
    right, chart_top = 1920 - MARGIN, top + 40
    peak = max(v for _, v in data)
    floor = min(v for _, v in data)
    span = (peak - floor) or 1
    pad = span * 0.18
    lo, hi = floor - pad, peak + pad

    lo, hi = _nice_bounds(lo, hi)
    step = (hi - lo) / 4
    for k in range(5):
        val = lo + step * k
        gy = base - (base - chart_top) * ((val - lo) / (hi - lo))
        d.line([px(left), px(gy), px(right), px(gy)], fill=PANEL_EDGE, width=px(1))
        text(d, (left - 16, gy - 14), fmt(val, unit), _f(22), INK_3, anchor="ra")

    n = len(data)
    step = (right - left) / max(1, n - 1)
    pts = []
    for i, (label, v) in enumerate(data):
        x = left + step * i
        y = base - (base - chart_top) * ((v - lo) / (hi - lo))
        pts.append((x, y))
        text(d, (x, base + 18), str(label), _f(24), INK_2, anchor="ma")

    fill_poly = [(px(x), px(y)) for x, y in pts] + [(px(right), px(base)), (px(left), px(base))]
    shade = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(shade).polygon(fill_poly, fill=(62, 144, 196, 46))
    img = Image.alpha_composite(img.convert("RGBA"), shade).convert("RGB")
    d = ImageDraw.Draw(img)

    d.line([(px(x), px(y)) for x, y in pts], fill=BLUE, width=px(6), joint="curve")
    for i, (x, y) in enumerate(pts):
        last = i == len(pts) - 1
        r = 12 if last else 8
        d.ellipse([px(x - r), px(y - r), px(x + r), px(y + r)],
                  fill=RED if last else NAVY, outline=RED if last else BLUE,
                  width=px(4))
    lx, ly = pts[-1]
    lx = min(lx, right - 60)
    text(d, (lx, ly - 62), fmt(data[-1][1], unit), _f(32, "bold"), INK, anchor="ma")
    return img


def rating(shot: dict) -> Image.Image:
    img = background()
    d = ImageDraw.Draw(img)
    top = header(d, shot)
    data = list(shot["data"])
    top_v = float(shot.get("max", 5))

    rows = len(data)
    row_h = min(120, (BODY_BOTTOM - top) / max(1, rows))
    bar_x0, bar_x1 = MARGIN + 470, 1920 - MARGIN - 150
    y = top + (BODY_BOTTOM - top - row_h * rows) / 2

    for i, (label, v) in enumerate(data):
        cy = y + row_h / 2
        lf = _f(32)
        text(d, (MARGIN, cy), str(label)[:34], lf, INK, anchor="lm")
        rounded(d, (bar_x0, cy - 17, bar_x1, cy + 17), 17, fill=PANEL)
        frac = max(0.0, min(1.0, v / top_v if top_v else 0))
        if frac > 0:
            end = bar_x0 + (bar_x1 - bar_x0) * frac
            rounded(d, (bar_x0, cy - 17, max(end, bar_x0 + 34), cy + 17), 17,
                    fill=SERIES[i % len(SERIES)])
        text(d, (bar_x1 + 26, cy), f"{v:g}", _f(30, "bold"), INK, anchor="lm")
        y += row_h
    return img


def pie(shot: dict) -> Image.Image:
    img = background()
    d = ImageDraw.Draw(img)
    top = header(d, shot)
    data = list(shot["data"])
    total = sum(v for _, v in data)

    cx, cy = 660, (top + BODY_BOTTOM) / 2
    r = min(230, (BODY_BOTTOM - top) / 2 - 10)
    box = [px(cx - r), px(cy - r), px(cx + r), px(cy + r)]

    start = -90.0
    for i, (_, v) in enumerate(data):
        sweep = 360.0 * v / total
        d.pieslice(box, start, start + sweep, fill=SERIES[i % len(SERIES)])
        start += sweep
    # donut hole keeps it from reading as a 90s clipart pie
    hr = r * 0.56
    d.ellipse([px(cx - hr), px(cy - hr), px(cx + hr), px(cy + hr)], fill=NAVY_LO)

    biggest = max(range(len(data)), key=lambda i: data[i][1])
    text(d, (cx, cy - 40), f"{100*data[biggest][1]/total:.0f}%",
         _f(58, "bold"), INK, anchor="ma")
    text(d, (cx, cy + 26), str(data[biggest][0])[:16].upper(), _f(22, "bold"),
         INK_2, anchor="ma")

    ly = cy - (len(data) * 62) / 2
    for i, (label, v) in enumerate(data):
        rounded(d, (1080, ly + 12, 1080 + 26, ly + 38), 7,
                fill=SERIES[i % len(SERIES)])
        text(d, (1128, ly + 6), str(label)[:28], _f(30), INK)
        text(d, (1920 - MARGIN, ly + 6), f"{100*v/total:.0f}%", _f(30, "bold"),
             INK_2, anchor="ra")
        ly += 62
    return img


def photo(shot: dict, image_path: Path | None, credit: str | None = None) -> Image.Image:
    """Full-bleed photograph with a scrim and the headline over it.

    A missing image is not fatal: we fall back to a text card so one dead
    Commons URL cannot kill a render.
    """
    if image_path is None or not Path(image_path).exists():
        fallback = dict(shot)
        fallback.setdefault("sub", "")
        return card(fallback)

    src = Image.open(image_path).convert("RGB")
    # cover-fit
    sw, sh = src.size
    scale = max(RENDER_W / sw, RENDER_H / sh)
    src = src.resize((max(1, int(sw * scale)), max(1, int(sh * scale))), Image.LANCZOS)
    ox = (src.width - RENDER_W) // 2
    oy = int((src.height - RENDER_H) * 0.38)      # bias up: faces/horizons sit high
    img = src.crop((ox, oy, ox + RENDER_W, oy + RENDER_H))

    # navy tint + bottom scrim so white text always clears WCAG on any photo
    tint = Image.new("RGB", img.size, NAVY)
    img = Image.blend(img, tint, 0.28)
    scrim = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(scrim)
    for i in range(px(560)):
        y = img.height - i
        a = int(215 * (i / px(560)) ** 1.4)
        sd.line([(0, y), (img.width, y)], fill=(9, 17, 30, a))
    img = Image.alpha_composite(img.convert("RGBA"), scrim).convert("RGB")

    d = ImageDraw.Draw(img)
    fnt = _f(58, "bold")
    lines = wrap(shot.get("headline", ""), fnt, CONTENT_W - 200)[:3]
    y = 1080 - 190 - (len(lines) - 1) * 72
    d.line([px(MARGIN), px(y - 34), px(MARGIN + 120), px(y - 34)], fill=RED, width=px(5))
    for ln in lines:
        text(d, (MARGIN, y), ln, fnt, INK)
        y += 72
    if shot.get("sub"):
        text(d, (MARGIN, y + 4), shot["sub"], _f(30), INK_2)
    if credit:
        text(d, (1920 - MARGIN, 1080 - 46), credit[:110], _f(19), INK_3, anchor="ra")
    return img


RENDERERS = {
    "card": card, "number": number, "bars": bars,
    "line": line, "rating": rating, "pie": pie,
}


def render_shot(shot: dict, image_path: Path | None = None,
                credit: str | None = None) -> Image.Image:
    if shot["kind"] == "photo":
        return photo(shot, image_path, credit)
    return RENDERERS[shot["kind"]](shot)
