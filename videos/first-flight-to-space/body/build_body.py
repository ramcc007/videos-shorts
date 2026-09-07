"""A girl travelling into space for the first time -- 60 seconds.

Written in the second person on purpose. The pipeline renders charts, cards
and stock photography, not generated character footage, so following a named
fictional girl would leave her invisible for the whole body. "You" puts the
viewer in the seat instead, and Maya carries the framing in the hook and close.

Every figure here is a well-established constant, not an estimate:
  ~8 min 45 s      pad to orbital insertion (Falcon 9 / Soyuz / Shuttle all sit near this)
  ~28,000 km/h     orbital velocity at low Earth orbit (7.7 km/s)
  100 km           the Karman line
  ~400 km          space station altitude
  ~90 min          one orbit, hence 16 sunrises a day
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from studio.body import build            # noqa: E402

TOPIC = Path(__file__).resolve().parents[1].name

HOOK = ("The first time you go to space, the whole trip up takes about eight minutes. "
        "Here is what those eight minutes actually feel like.")
CLOSE = ("Nobody comes back quite the same. That is the part no amount of training "
         "prepares you for. Subscribe if you would go.")

SHOTS = [
    {"kind": "card", "kicker": "the wait", "headline": "Hours of nothing, then everything",
     "bullets": ["Strapped in, flat on your back, for hours.",
                 "Then the countdown ends.",
                 "And it all happens at once."],
     "say": "You are strapped in flat on your back for hours before anything happens. "
            "Then the countdown ends, and everything happens at once."},

    {"kind": "number", "kicker": "kilometres per hour", "value": "28,000",
     "sub": "Getting to space is easy. Staying there is a question of speed.",
     "say": "To stay up there you do not just go up. You have to get fast. "
            "Faster than anything you have ever felt."},

    {"kind": "bars", "kicker": "how far up", "headline": "Space is closer than you think",
     "unit": " km", "highlight": 3,
     "data": [("Everest", 8.8), ("Airliner", 11), ("Edge of space", 100), ("Space station", 400)],
     "say": "The edge of space is only a hundred kilometres away. "
            "Straight up, that is an hour in the car."},

    {"kind": "photo", "headline": "Then the engines stop",
     "query": "Earth from International Space Station cupola",
     "sub": "Four hundred kilometres up, eight kilometres every second",
     "say": "The engines cut. Your arms drift up on their own. "
            "And you finally turn and look out of the window."},

    {"kind": "number", "kicker": "sunrises every day", "value": "16",
     "sub": "One full orbit of the planet every ninety minutes",
     "say": "You go around the entire planet every ninety minutes. "
            "Sixteen sunrises a day, and every one of them completely silent."},

    {"kind": "card", "kicker": "the part that stays", "headline": "Everyone says the same thing",
     "bullets": ["The atmosphere is thinner than you imagined.",
                 "The borders you were taught to see are not there.",
                 "It is very quiet."],
     "say": "Almost everyone says the same thing afterwards. "
            "The borders you were taught to see simply are not there."},
]

if __name__ == "__main__":
    build(TOPIC, SHOTS)
