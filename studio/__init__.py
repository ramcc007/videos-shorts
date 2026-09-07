"""Shared rendering engine for the explainer-video pipeline.

Per-video scripts live in videos/<topic>/body/build_body.py and hold only the
SHOTS list; everything reusable lives here so a bug is fixed once, not once
per video.
"""
__all__ = ["theme", "shots", "draw", "photos", "voice", "captions", "render", "config"]
