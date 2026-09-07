"""Stock photographs from Wikimedia Commons.

Standing rule: CC0, CC BY or public domain ONLY, and the credit line is cached
next to the file so CREDITS.md can be regenerated without a second API call.

A failed or unusable download is never fatal -- the caller falls back to a text
card and we print a warning so it gets noticed in the log.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import requests

API = "https://commons.wikimedia.org/w/api.php"
UA = "SecondStudio/1.0 (explainer-video pipeline; contact via repo)"
TIMEOUT = 25

# Licences we are allowed to ship. Deliberately strict: the standing rule says
# CC0 / CC BY / public domain, so ShareAlike and every NC/ND variant are out.
_ALLOW = (
    re.compile(r"^cc0", re.I),
    re.compile(r"^cc[ -]by([ -]\d(\.\d)?)?$", re.I),
    re.compile(r"public domain", re.I),
    re.compile(r"^pd([ -]|$)", re.I),
)
_DENY = re.compile(r"(\bnc\b|noncommercial|\bnd\b|noderiv|sa\b|share[ -]?alike|fair use)", re.I)


def _licence_ok(name: str) -> bool:
    if not name or _DENY.search(name):
        return False
    return any(p.search(name.strip()) for p in _ALLOW)


def _clean(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html or "")).strip()


def search(query: str, limit: int = 8) -> list[dict]:
    """Return candidate Commons images, licence-filtered, best first."""
    params = {
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": f"{query} filetype:bitmap", "gsrnamespace": "6",
        "gsrlimit": str(limit), "prop": "imageinfo",
        "iiprop": "url|extmetadata|size", "iiurlwidth": "2560",
    }
    try:
        r = requests.get(API, params=params, headers={"User-Agent": UA}, timeout=TIMEOUT)
        r.raise_for_status()
        pages = (r.json().get("query") or {}).get("pages") or {}
    except (requests.RequestException, ValueError) as e:
        print(f"[photos] WARNING: Commons search failed for {query!r}: {e}", file=sys.stderr)
        return []

    out = []
    for page in pages.values():
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata") or {}
        lic = _clean(meta.get("LicenseShortName", {}).get("value", ""))
        if not _licence_ok(lic):
            continue
        if (info.get("width") or 0) < 1280:
            continue
        author = _clean(meta.get("Artist", {}).get("value", "")) or "Unknown author"
        out.append({
            "title": page.get("title", ""),
            "url": info.get("thumburl") or info.get("url"),
            "descriptionurl": info.get("descriptionurl", ""),
            "licence": lic,
            "author": author[:80],
            "width": info.get("width"),
        })
    return out


def by_file(file_title: str) -> dict | None:
    """Look up one specific 'File:Something.jpg' page."""
    params = {
        "action": "query", "format": "json", "titles": file_title,
        "prop": "imageinfo", "iiprop": "url|extmetadata|size", "iiurlwidth": "2560",
    }
    try:
        r = requests.get(API, params=params, headers={"User-Agent": UA}, timeout=TIMEOUT)
        r.raise_for_status()
        pages = (r.json().get("query") or {}).get("pages") or {}
    except (requests.RequestException, ValueError) as e:
        print(f"[photos] WARNING: Commons lookup failed for {file_title!r}: {e}", file=sys.stderr)
        return None
    for page in pages.values():
        info = (page.get("imageinfo") or [{}])[0]
        if not info:
            continue
        meta = info.get("extmetadata") or {}
        lic = _clean(meta.get("LicenseShortName", {}).get("value", ""))
        if not _licence_ok(lic):
            print(f"[photos] WARNING: {file_title} is {lic!r} -- not CC0/CC BY/PD, skipping.",
                  file=sys.stderr)
            return None
        return {
            "title": page.get("title", ""),
            "url": info.get("thumburl") or info.get("url"),
            "descriptionurl": info.get("descriptionurl", ""),
            "licence": lic,
            "author": _clean(meta.get("Artist", {}).get("value", "")) or "Unknown author",
            "width": info.get("width"),
        }
    return None


def credit_line(hit: dict) -> str:
    return f"{hit['title'].removeprefix('File:')} - {hit['author']} - {hit['licence']} - Wikimedia Commons"


def fetch(shot: dict, dest_dir: Path, index: int) -> tuple[Path | None, str | None]:
    """Download the photo for one shot. Returns (path, credit) or (None, None).

    Results are cached: re-running a render never re-downloads.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    cache_file = dest_dir / "credits.json"
    cache = json.loads(cache_file.read_text(encoding="utf-8")) if cache_file.exists() else {}
    key = str(index)

    if key in cache and (dest_dir / cache[key]["filename"]).exists():
        c = cache[key]
        return dest_dir / c["filename"], c["credit"]

    hit = by_file(shot["file"]) if shot.get("file") else None
    if hit is None and shot.get("query"):
        hits = search(shot["query"])
        hit = hits[0] if hits else None

    if hit is None or not hit.get("url"):
        print(f"[photos] WARNING: no usable CC0/CC BY/PD image for shot {index} "
              f"({shot.get('query') or shot.get('file')!r}); falling back to a text card.",
              file=sys.stderr)
        return None, None

    ext = Path(hit["url"].split("?")[0]).suffix.lower() or ".jpg"
    if ext not in (".jpg", ".jpeg", ".png", ".webp"):
        ext = ".jpg"
    filename = f"{index:02d}{ext}"
    path = dest_dir / filename
    try:
        r = requests.get(hit["url"], headers={"User-Agent": UA}, timeout=60)
        r.raise_for_status()
        path.write_bytes(r.content)
    except requests.RequestException as e:
        print(f"[photos] WARNING: download failed for shot {index}: {e}", file=sys.stderr)
        return None, None

    credit = credit_line(hit)
    cache[key] = {"filename": filename, "credit": credit,
                  "source": hit.get("descriptionurl", ""), "licence": hit["licence"]}
    cache_file.write_text(json.dumps(cache, indent=2) + "\n", encoding="utf-8")
    return path, credit


def write_credits_md(dest_dir: Path, out_file: Path, topic: str) -> None:
    cache_file = dest_dir / "credits.json"
    if not cache_file.exists():
        return
    cache = json.loads(cache_file.read_text(encoding="utf-8"))
    lines = [f"# Credits - {topic}", "",
             "All imagery below is CC0, CC BY or public domain, per the project's standing rules.", ""]
    for k in sorted(cache, key=int):
        c = cache[k]
        lines.append(f"- **Shot {k}** - {c['credit']}" + (f"  \n  {c['source']}" if c.get("source") else ""))
    out_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
