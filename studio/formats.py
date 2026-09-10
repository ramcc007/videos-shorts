"""Output format profiles.

One place for everything that differs between a 16:9 long-form video and a
9:16 Short: canvas, layout, pacing, caption size, and whether a Flow presenter
is used at all.

Cost note: `short` defaults to presenter=False. A hook and close cost ~40 Flow
credits from a monthly grant that does not roll over, and eat 16s of a 60s
Short. Without them a Short costs nothing at the margin and output is limited
only by the free Kaggle GPU quota. Turn it on per video with --presenter.
"""
from __future__ import annotations

from dataclasses import dataclass

OVERSAMPLE = 1.3333        # stills drawn larger so the Ken Burns push stays sharp


@dataclass(frozen=True)
class Format:
    name: str
    out_w: int
    out_h: int

    # layout, in logical points (== output pixels)
    margin: int
    head_y: int
    body_top: int
    body_bottom: int          # nothing is drawn below this: captions own it
    label_room: int           # extra room for chart labels hung below a baseline

    # captions
    caption_size: int
    caption_margin_v: int
    caption_max_chars: int
    caption_align: int        # libass alignment: 2 = bottom centre
    caption_boxed: bool       # True = opaque plate behind text; False = outlined text

    # pacing
    seconds_per_shot: float
    presenter_default: bool
    hook_s: float
    close_s: float

    @property
    def render_w(self) -> int:
        return int(round(self.out_w * OVERSAMPLE))

    @property
    def render_h(self) -> int:
        return int(round(self.out_h * OVERSAMPLE))

    @property
    def aspect(self) -> str:
        return f"{self.out_w}x{self.out_h}"


LONG = Format(
    name="long", out_w=1920, out_h=1080,
    margin=110, head_y=108, body_top=330, body_bottom=858, label_room=74,
    caption_size=50, caption_margin_v=64, caption_max_chars=44, caption_align=2,
    caption_boxed=True,
    seconds_per_shot=8.0, presenter_default=True, hook_s=8.0, close_s=8.0,
)

# 9:16. The bottom ~15% of a Short is covered by YouTube's own UI (title,
# channel, action rail), so captions sit high of it and nothing is drawn below
# body_bottom. Cuts are much faster than long-form.
SHORT = Format(
    name="short", out_w=1080, out_h=1920,
    margin=72, head_y=180, body_top=430, body_bottom=1300, label_room=74,
    caption_size=70, caption_margin_v=380, caption_max_chars=20, caption_align=2,
    caption_boxed=False,
    seconds_per_shot=4.0, presenter_default=False, hook_s=5.0, close_s=4.0,
)

FORMATS = {"long": LONG, "short": SHORT}


def get(name: str) -> Format:
    if name not in FORMATS:
        raise SystemExit(f"Unknown format {name!r}. Choose from: {', '.join(FORMATS)}")
    return FORMATS[name]
