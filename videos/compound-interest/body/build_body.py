"""Compound interest, 30s Short. No presenter -- no Flow credits, no GPU.

Figures: $200/month at 7% a year, contributions at month end.
  Amy  $200/mo age 25-35 (pays in $24,000), then stops   -> $260,418 at 65
  Ben  $200/mo age 35-65 (pays in $72,000), never stops  -> $233,891 at 65
Amy ends $26,527 ahead having paid in a third as much. The 7% assumption is
shown on screen, not buried -- it is what the whole claim rests on.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from studio.body import build            # noqa: E402
TOPIC = Path(__file__).resolve().parents[1].name
HOOK = CLOSE = ""      # no presenter in this format

SHOTS = [
    {"kind": "card", "kicker": "two savers", "headline": "One of them wins. It is not who you think.",
     "say": "Two people save for retirement. One ends up richer."},

    {"kind": "number", "kicker": "Amy pays in", "value": "$24,000",
     "sub": "$200 a month, age 25 to 35 — then she stops forever",
     "say": "Amy saves two hundred a month for ten years, then stops."},

    {"kind": "number", "kicker": "Ben pays in", "value": "$72,000",
     "sub": "$200 a month, age 35 to 65 — he never stops",
     "say": "Ben starts ten years later, but he never stops."},

    {"kind": "card", "kicker": "so far", "headline": "Ben pays in three times more",
     "say": "Ben puts in three times as much money."},

    {"kind": "bars", "kicker": "value at 65, assuming 7% a year",
     "headline": "So who ends up ahead?", "unit": "k", "highlight": 0,
     "data": [("Amy", 260), ("Ben", 234)],
     "say": "But at sixty five, Amy is the one in front."},

    {"kind": "number", "kicker": "Amy's lead", "value": "$27,000",
     "sub": "while paying in a third as much",
     "say": "Twenty seven thousand ahead, on a third of the money."},

    {"kind": "card", "kicker": "how", "headline": "Her first $200 compounded for 40 years",
     "say": "Her earliest payments had forty years to grow."},

    {"kind": "card", "kicker": "the lesson", "headline": "Starting early beats saving more",
     "say": "Time in the market beats the size of the cheque."},
]
if __name__ == "__main__":
    build(TOPIC, SHOTS, fmt="short")
