"""Visual identity. One place for every colour, size and font decision."""
from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

from PIL import ImageFont

from . import formats

# --- canvas -----------------------------------------------------------------
# Stills are drawn larger than the output so the Ken Burns push never softens.
# These are module-level and MUTABLE: use_format() rebinds them. Read them as
# `theme.OUT_W`, never `from .theme import OUT_W`, or you will capture the
# format that happened to be active at import time.
FPS = 25

ACTIVE = formats.LONG
OUT_W, OUT_H = ACTIVE.out_w, ACTIVE.out_h
LOGICAL_W, LOGICAL_H = OUT_W, OUT_H          # layout units == output pixels
RENDER_W, RENDER_H = ACTIVE.render_w, ACTIVE.render_h
SCALE = RENDER_W / LOGICAL_W


def use_format(name: str | formats.Format) -> formats.Format:
    """Switch the whole render stack to another output format."""
    global ACTIVE, OUT_W, OUT_H, LOGICAL_W, LOGICAL_H, RENDER_W, RENDER_H, SCALE
    ACTIVE = name if isinstance(name, formats.Format) else formats.get(name)
    OUT_W, OUT_H = ACTIVE.out_w, ACTIVE.out_h
    LOGICAL_W, LOGICAL_H = OUT_W, OUT_H
    RENDER_W, RENDER_H = ACTIVE.render_w, ACTIVE.render_h
    SCALE = RENDER_W / LOGICAL_W
    font.cache_clear()        # cached sizes were scaled for the old format
    return ACTIVE

# --- palette ----------------------------------------------------------------
NAVY = (15, 27, 46)               # #0F1B2E  base background
NAVY_HI = (28, 46, 74)            # gradient top
NAVY_LO = (9, 17, 30)             # gradient bottom
PANEL = (24, 39, 62)              # card fill
PANEL_EDGE = (46, 68, 100)
RED = (192, 87, 76)               # #C0574C  "interest"
BLUE = (62, 144, 196)             # #3E90C4  "defense" / accent
INK = (233, 240, 248)             # primary text
INK_2 = (167, 186, 208)           # secondary text
INK_3 = (110, 132, 158)           # captions, credits
GREEN = (46, 125, 91)
AMBER = (214, 158, 74)

SERIES = [BLUE, RED, GREEN, AMBER, INK_2]   # categorical order for charts

# --- fonts ------------------------------------------------------------------
# Resolved against whatever the OS actually ships. Windows/macOS/Linux all hit
# one of these; PIL's bitmap default is a last resort and prints a warning.
_FONT_CANDIDATES = {
    "bold": [
        "C:/Windows/Fonts/segoeuib.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/SFNSDisplay-Bold.otf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ],
    "regular": [
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/SFNS.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ],
    "mono": [
        "C:/Windows/Fonts/consola.ttf",
        "/System/Library/Fonts/Menlo.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
    ],
}

_warned = set()


def font_path(weight: str = "regular") -> str | None:
    for p in _FONT_CANDIDATES[weight]:
        if Path(p).exists():
            return p
    if weight not in _warned:
        _warned.add(weight)
        print(f"[theme] WARNING: no '{weight}' TTF found; text will look wrong.",
              file=sys.stderr)
    return None


@lru_cache(maxsize=128)
def font(size: int, weight: str = "regular") -> ImageFont.FreeTypeFont:
    """Size is given in 1080p points and scaled to the render canvas."""
    p = font_path(weight)
    px = int(round(size * SCALE))
    if p is None:
        return ImageFont.load_default()
    return ImageFont.truetype(p, px)


def caption_font_family() -> str:
    """Family name libass should use for burned-in captions."""
    p = font_path("bold") or ""
    if "segoe" in p.lower():
        return "Segoe UI"
    if "arial" in p.lower():
        return "Arial"
    if "dejavu" in p.lower():
        return "DejaVu Sans"
    if "liberation" in p.lower():
        return "Liberation Sans"
    return "sans-serif"
