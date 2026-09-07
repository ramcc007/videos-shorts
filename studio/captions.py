"""Burned-in captions as ASS, timed straight off the narration.

Because one shot == one narration line, caption timing needs no forced
alignment: each line shows for exactly as long as it is spoken.
"""
from __future__ import annotations

from pathlib import Path

from . import theme

MAX_CHARS = 44        # per line, before wrapping to a second row
MAX_LINES = 2


def _ass_colour(rgb: tuple[int, int, int], alpha: int = 0) -> str:
    r, g, b = rgb
    return f"&H{alpha:02X}{b:02X}{g:02X}{r:02X}"


def _ts(seconds: float) -> str:
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _wrap(text: str) -> str:
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 <= MAX_CHARS or not cur:
            cur = f"{cur} {w}".strip()
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    if len(lines) > MAX_LINES:                     # rebalance rather than clip
        joined = " ".join(lines)
        cut = len(joined) // 2
        space = joined.rfind(" ", 0, cut + 12)
        lines = [joined[:space], joined[space + 1:]] if space > 0 else [joined]
    return r"\N".join(lines)


def _escape(text: str) -> str:
    return text.replace("{", "(").replace("}", ")").replace("\n", " ")


def write_ass(times: list[dict], out_path: Path, style: str = "body") -> Path:
    family = theme.caption_font_family()
    primary = _ass_colour(theme.INK)
    box = _ass_colour(theme.NAVY_LO, alpha=0x55)      # semi-transparent navy plate
    outline = _ass_colour((0, 0, 0), alpha=0x30)

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Body,{family},50,{primary},{primary},{outline},{box},-1,0,0,0,100,100,0.4,0,3,14,0,2,220,220,64,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    rows = []
    for t in times:
        text = _escape(t.get("text", "")).strip()
        if not text:
            continue
        rows.append(
            f"Dialogue: 0,{_ts(t['start'])},{_ts(t['end'])},Body,,0,0,0,,{_wrap(text)}"
        )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(header + "\n".join(rows) + "\n", encoding="utf-8")
    return out_path
