"""Demo video: "Do home batteries actually pay for themselves?"

This ships as a WORKING EXAMPLE so you can render something on day one and see
the whole pipeline move. The figures below are illustrative placeholders -- 
replace them with sourced numbers before you publish anything.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from studio.body import build            # noqa: E402

TOPIC = Path(__file__).resolve().parents[1].name

HOOK = ("Everyone says a home battery pays for itself. "
        "I ran the numbers, and the answer depends on one thing nobody mentions.")
CLOSE = ("So: worth it if you're on a time-of-use tariff, marginal if you're not. "
         "Subscribe if you want the spreadsheet.")

SHOTS = [
    {"kind": "card", "kicker": "the claim", "headline": "\"It pays for itself in five years\"",
     "bullets": ["That number comes from the installer's own calculator.",
                 "It assumes you charge cheap and discharge expensive, every day.",
                 "Miss that assumption and the maths falls apart."],
     "say": "Every installer quotes the same line. It pays for itself in about five years. "
            "That number comes from their own calculator."},

    {"kind": "number", "kicker": "what people actually pay", "value": "9.4 yrs",
     "sub": "Median payback across a hundred real installs on a flat tariff",
     "say": "Across a hundred real installs on a flat tariff, the median payback was closer to nine and a half years."},

    {"kind": "bars", "kicker": "hardware", "headline": "Installed cost per usable kilowatt-hour",
     "unit": " GBP", "highlight": 3,
     "data": [("Tesla PW3", 640), ("BYD HVS", 710), ("GivEnergy", 520), ("Self-build", 295)],
     "say": "The hardware spread is wider than most people expect. "
            "A self-build rack costs less than half what a branded unit does."},

    {"kind": "line", "kicker": "the tailwind", "headline": "Cell prices have fallen almost every year",
     "sub": "USD per kilowatt-hour, LFP prismatic cells",
     "data": [("2019", 156), ("2020", 132), ("2021", 118), ("2022", 138),
              ("2023", 95), ("2024", 61), ("2025", 53)],
     "say": "And cells keep getting cheaper. One bad year aside, the price has fallen by two thirds since twenty nineteen."},

    {"kind": "pie", "headline": "Where the money in an install actually goes",
     "data": [("Battery cells", 52), ("Inverter", 21), ("Labour", 17), ("Scaffold and parts", 10)],
     "say": "But cells are only half the bill. The inverter, the labour and the scaffolding make up the rest."},

    {"kind": "photo", "headline": "The bit that decides everything",
     "query": "electricity smart meter",
     "sub": "Your tariff, not your battery",
     "say": "Which brings us to the thing that actually decides whether any of this works: your tariff."},

    {"kind": "rating", "headline": "How the four options scored overall", "max": 5,
     "data": [("Tesla Powerwall 3", 4.6), ("BYD Battery-Box", 4.1),
              ("GivEnergy All-in-One", 3.9), ("Self-build rack", 3.2)],
     "say": "Scored on cost, warranty, and how much of your evening they can actually cover, "
            "the branded units still win on everything except price."},

    {"kind": "card", "kicker": "the answer", "headline": "So does it pay for itself?",
     "bullets": ["On a time-of-use tariff: yes, comfortably inside the warranty.",
                 "On a flat tariff: it is close, and it depends on your usage.",
                 "Either way, size it to your evening load, not your roof."],
     "say": "So. On a time of use tariff, yes, comfortably. On a flat tariff it is a much closer call."},
]

if __name__ == "__main__":
    build(TOPIC, SHOTS)
