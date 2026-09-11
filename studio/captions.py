"""Burned-in captions as ASS, timed straight off the narration.

Because one shot == one narration line, caption timing needs no forced
alignment: each line shows for exactly as long as it is spoken.
"""
from __future__ import annotations

from pathlib import Path

from . import theme

MAX_LINES = 2
WORDS_PER_GROUP = 3   # Shorts: how many words pop at once

# libass override: start at 78% and snap to 100% over 90ms, fading in over 60ms.
POP = r"{\fscx78\fscy78\alpha&HFF&\t(0,60,\alpha&H00&)\t(0,90,\fscx100\fscy100)}"


def _ass_colour(rgb: tuple[int, int, int], alpha: int = 0) -> str:
    r, g, b = rgb
    return f"&H{alpha:02X}{b:02X}{g:02X}{r:02X}"


def _ts(seconds: float) -> str:
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _groups(text: str, per: int = WORDS_PER_GROUP) -> list[str]:
    """Split a line into small word groups for punchy Shorts captions."""
    words = text.split()
    return [" ".join(words[i:i + per]) for i in range(0, len(words), per)] or [text]


def _split_by_length(text: str, start: float, end: float,
                     per: int = WORDS_PER_GROUP) -> list[tuple[float, float, str]]:
    """Time each word group within a line, in proportion to its length.

    We already know exactly when each narration line starts and ends, so word
    timing needs no forced-alignment model: distributing the line's duration by
    character count is accurate to a few hundredths of a second at speech pace,
    and costs nothing to compute.
    """
    groups = _groups(text, per)
    weights = [max(1, len(g)) for g in groups]
    total = sum(weights)
    span = max(0.05, end - start)
    out, t = [], start
    for g, w in zip(groups, weights):
        dur = span * w / total
        out.append((t, t + dur, g))
        t += dur
    out[-1] = (out[-1][0], end, out[-1][2])      # absorb rounding into the last
    return out


def _wrap(text: str, max_chars: int) -> str:
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 <= max_chars or not cur:
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
    fmt = theme.ACTIVE
    family = theme.caption_font_family()
    primary = _ass_colour(theme.INK)
    if fmt.caption_boxed:
        # long-form: a soft navy plate keeps text legible over charts
        border_style, box = 3, _ass_colour(theme.NAVY_LO, alpha=0x55)
        outline_w, shadow_w = 14, 0
        outline = _ass_colour((0, 0, 0), alpha=0x30)
    else:
        # Shorts: outlined text with a drop shadow floats over moving footage
        # far better than a hard slab, and is what the format's viewers expect.
        border_style, box = 1, _ass_colour((0, 0, 0), alpha=0x00)
        outline_w, shadow_w = 6, 3
        outline = _ass_colour((0, 0, 0), alpha=0x00)

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {theme.LOGICAL_W}
PlayResY: {theme.LOGICAL_H}
WrapStyle: 2
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Body,{family},{fmt.caption_size},{primary},{primary},{outline},{box},-1,0,0,0,100,100,0.4,0,{border_style},{outline_w},{shadow_w},{fmt.caption_align},{fmt.margin},{fmt.margin},{fmt.caption_margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    rows = []
    for t in times:
        text = _escape(t.get("text", "")).strip()
        if not text:
            continue
        if fmt.name == "short":
            # A few words at a time, timed within the line we already know, each
            # landing with a scale punch. A caption that simply appears reads as
            # a subtitle; one that arrives reads as part of the edit.
            for a, b, group in _split_by_length(text, t["start"], t["end"]):
                rows.append(f"Dialogue: 0,{_ts(a)},{_ts(b)},Body,,0,0,0,,"
                            f"{POP}{_wrap(group, fmt.caption_max_chars)}")
        else:
            rows.append(f"Dialogue: 0,{_ts(t['start'])},{_ts(t['end'])},Body,,0,0,0,,"
                        f"{_wrap(text, fmt.caption_max_chars)}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(header + "\n".join(rows) + "\n", encoding="utf-8")
    return out_path
