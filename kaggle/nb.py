"""Minimal .ipynb writer. No nbformat dependency -- a notebook is just JSON."""
from __future__ import annotations

import json
from pathlib import Path


def code(src: str) -> dict:
    # Cell sources are carried in triple-quoted literals, so a triple quote
    # inside one closes it early -- and the damage surfaces minutes into a
    # GPU run, far from its cause. Use # comments in cell code, never
    # docstrings.
    if (chr(34) * 3) in src:
        raise ValueError(
            'notebook cell source contains a triple quote, which would '
            'terminate the literal carrying it. Use # comments instead of '
            'docstrings inside cells.')
    return {"cell_type": "code", "execution_count": None, "metadata": {},
            "outputs": [], "source": src.strip("\n").splitlines(keepends=True)}


def md(src: str) -> dict:
    return {"cell_type": "markdown", "metadata": {},
            "source": src.strip("\n").splitlines(keepends=True)}


def write(cells: list[dict], path: Path) -> Path:
    nb = {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.11"},
        },
        "nbformat": 4, "nbformat_minor": 5,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(nb, indent=1), encoding="utf-8")
    return path
