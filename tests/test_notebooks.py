"""Every generated notebook cell must be valid Python.

This exists because a cell whose source is built inside a non-raw triple-quoted
string can pick up a real newline from a "\n" that was meant to stay escaped,
which only shows up as a SyntaxError minutes into a GPU run. Parsing every cell
locally costs nothing and catches the whole class.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "kaggle"))


def cells_of(path: Path) -> list[str]:
    nb = json.loads(path.read_text(encoding="utf-8"))
    return ["".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"]


def check(path: Path) -> int:
    bad = 0
    for i, src in enumerate(cells_of(path)):
        try:
            ast.parse(src)
        except SyntaxError as e:
            bad += 1
            print(f"  FAIL {path.name} cell {i}: {e.msg} (line {e.lineno})")
            for n, ln in enumerate(src.splitlines()[max(0, (e.lineno or 1) - 3):
                                                    (e.lineno or 1) + 1],
                                   start=max(1, (e.lineno or 1) - 2)):
                print(f"       {n:>3} | {ln}")
    return bad


def main() -> int:
    out = ROOT / "build" / "_nbtest"
    out.mkdir(parents=True, exist_ok=True)
    from studio import presenter as presmod

    import make_portrait_nb
    import make_smoke_nb
    import make_voice_nb

    built = [
        make_smoke_nb.build(out / "smoke.ipynb"),
        make_portrait_nb.build(out / "portrait.ipynb", presmod.load(),
                               "/kaggle/input/sdxl", [1, 2]),
        make_voice_nb.build(out / "voice.ipynb", ["One line.", "Two."],
                            "someone/refs"),
    ]
    try:
        import make_footage_nb
        built.append(make_footage_nb.build_samples(
            out / "footage.ipynb", "/kaggle/input/ltx", ["a test prompt"]))
    except (ImportError, TypeError) as e:
        print(f"  (skipped make_footage_nb: {e})")

    bad = 0
    for p in built:
        n = check(p)
        print(f"  {'ok  ' if not n else 'FAIL'} {p.name}: {len(cells_of(p))} cells")
        bad += n
    print("all notebook cells parse" if not bad else f"{bad} bad cell(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
