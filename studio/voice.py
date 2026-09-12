"""Narration: where the body's voice comes from, and when each line lands.

Three sources, all producing the same Narration shape:
  chatterbox  the real thing -- a clone of the Flow presenter, rendered on a
              Kaggle GPU and downloaded as a zip
  kokoro      a local ONNX voice, for drafts, so you don't burn GPU quota
              while you're still editing the script
  silent      timed silence, for pure layout checks -- no model needed
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import wave
import zipfile
from dataclasses import dataclass
from pathlib import Path

from . import config

WPM = 165          # measured pace of the Chatterbox output; used for estimates
GAP = 0.38         # breath between lines
MIN_LINE = 1.9     # a three-word line still needs time to read


@dataclass
class Narration:
    wav: Path
    times: list[dict]      # [{i, text, start, end}]
    total: float
    source: str

    def starts(self) -> list[float]:
        return [t["start"] for t in self.times]

    def durations(self) -> list[float]:
        """Shot durations that exactly tile the audio -- video and voice can
        never drift apart because each shot ends where the next one starts."""
        s = self.starts()
        return [(s[i + 1] if i + 1 < len(s) else self.total) - s[i]
                for i in range(len(s))]


def _wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / float(w.getframerate())


def estimate(lines: list[str]) -> tuple[list[dict], float]:
    times, t = [], 0.0
    for i, line in enumerate(lines):
        dur = max(MIN_LINE, len(line.split()) / WPM * 60.0)
        times.append({"i": i, "text": line, "start": round(t, 3),
                      "end": round(t + dur, 3)})
        t += dur + GAP
    return times, round(t, 3)


# --------------------------------------------------------------------------- #
def from_kaggle(zip_or_dir: Path, work: Path) -> Narration:
    """Unpack what kaggle_run.py brought back: voice.wav + times.json."""
    work.mkdir(parents=True, exist_ok=True)
    src = Path(zip_or_dir)

    if src.is_dir():
        cand = list(src.glob("*.zip"))
        if (src / "voice.wav").exists() and (src / "times.json").exists():
            for f in ("voice.wav", "times.json"):
                shutil.copy2(src / f, work / f)
        elif cand:
            with zipfile.ZipFile(cand[0]) as z:
                z.extractall(work)
        else:
            raise SystemExit(f"No voice.wav/times.json or zip found in {src}")
    else:
        with zipfile.ZipFile(src) as z:
            z.extractall(work)

    # the notebook may nest everything one level down
    wav = next(iter(sorted(work.rglob("voice.wav"))), None)
    tj = next(iter(sorted(work.rglob("times.json"))), None)
    if wav is None or tj is None:
        raise SystemExit(f"Kaggle output in {work} has no voice.wav / times.json")

    data = json.loads(tj.read_text(encoding="utf-8"))
    times = data["sentences"] if isinstance(data, dict) else data
    total = float(data.get("total")) if isinstance(data, dict) and data.get("total") \
        else _wav_duration(wav)
    return Narration(wav=wav, times=times, total=total, source="chatterbox")


def kokoro(lines: list[str], out_dir: Path, voice: str = "af_heart") -> Narration:
    """Local draft voice. Needs `pip install kokoro-onnx soundfile` plus the
    model files; falls back to silence with a clear message if absent."""
    try:
        import numpy as np
        import soundfile as sf
        from kokoro_onnx import Kokoro
    except ImportError as e:
        # Name the module that actually failed: kokoro pulls in numpy and
        # soundfile, and blaming kokoro for their absence sends you to the
        # wrong fix.
        print(f"[voice] cannot use kokoro -- {e.name!r} is not installed.\n"
              f"        pip install -r requirements.txt kokoro-onnx\n"
              f"        then: python tools/fetch_voice.py\n"
              f"        -- falling back to --voice silent.", file=sys.stderr)
        return silent(lines, out_dir)

    model, voices, searched = config.kokoro_files()
    if model is None or voices is None:
        missing = [n for n, f in ((config.KOKORO_MODEL, model),
                                  (config.KOKORO_VOICES, voices)) if f is None]
        print(f"[voice] Kokoro model file(s) missing: {', '.join(missing)}\n"
              f"        Looked in: {', '.join(str(d) for d in searched)}\n"
              f"        Get them with:  python tools/fetch_voice.py\n"
              f"        -- falling back to --voice silent.", file=sys.stderr)
        return silent(lines, out_dir)

    out_dir.mkdir(parents=True, exist_ok=True)
    k = Kokoro(str(model), str(voices))
    chunks, times, t, sr = [], [], 0.0, 24000
    for i, line in enumerate(lines):
        samples, sr = k.create(line, voice=voice, speed=1.0, lang="en-us")
        sf.write(out_dir / f"s{i:03d}.wav", samples, sr)
        dur = len(samples) / sr
        times.append({"i": i, "text": line, "start": round(t, 3), "end": round(t + dur, 3)})
        chunks.append(samples)
        chunks.append(np.zeros(int(GAP * sr), dtype=samples.dtype))
        t += dur + GAP

    full = np.concatenate(chunks)
    wav = out_dir / "voice.wav"
    sf.write(wav, full, sr)
    (out_dir / "times.json").write_text(
        json.dumps({"sentences": times, "total": round(len(full) / sr, 3)}, indent=2),
        encoding="utf-8")
    return Narration(wav=wav, times=times, total=len(full) / sr, source="kokoro")


def silent(lines: list[str], out_dir: Path) -> Narration:
    """Timed silence: lets you check layout, pacing and caption timing without
    any model at all."""
    out_dir.mkdir(parents=True, exist_ok=True)
    times, total = estimate(lines)
    wav = out_dir / "voice.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
         "-i", f"anullsrc=r=24000:cl=mono", "-t", f"{total:.3f}",
         "-c:a", "pcm_s16le", str(wav)],
        check=True)
    (out_dir / "times.json").write_text(
        json.dumps({"sentences": times, "total": total}, indent=2), encoding="utf-8")
    return Narration(wav=wav, times=times, total=total, source="silent")


def load(source: str, lines: list[str], work: Path,
         kaggle_out: Path | None = None) -> Narration:
    if source == "chatterbox":
        if kaggle_out is None or not Path(kaggle_out).exists():
            raise SystemExit(
                "--voice chatterbox needs the Kaggle output.\n"
                "  Run:  python tools/kaggle_run.py --topic <topic> --job voice")
        n = from_kaggle(Path(kaggle_out), work / "voice_unpacked")
        if len(n.times) != len(lines):
            raise SystemExit(
                f"Kaggle narration has {len(n.times)} lines but SHOTS has {len(lines)}.\n"
                "The script changed after the voice was rendered -- re-run the voice job.")
        return n
    if source == "kokoro":
        return kokoro(lines, work / "voice_kokoro")
    return silent(lines, work / "voice_silent")
