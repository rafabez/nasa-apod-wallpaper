"""Fetch the Astronomy Picture of the Day.

Primary source: science.nasa.gov's WordPress REST API. In late 2026 APOD moved
from apod.nasa.gov to science.nasa.gov/apod/, and api.nasa.gov/planetary/apod
started returning the NASA logo (title "NASA Science") for every date. Each APOD
day is now an `image-article` post whose slug encodes the date:
`apod-2026-november-25-some-title`.

Fallback: api.nasa.gov (DEMO_KEY, or the user's own key), with a guard that
rejects the logo placeholder.
"""
from __future__ import annotations

import html
import re
from datetime import date, timedelta

import requests

SITE_API = "https://science.nasa.gov/wp-json/wp/v2/image-article"
NASA_API = "https://api.nasa.gov/planetary/apod"
APOD_SITE_URL = "https://science.nasa.gov/apod/"
TIMEOUT = 30
USER_AGENT = "nasa-apod-wallpaper (+https://github.com/rafabez/nasa-apod-wallpaper)"

MONTHS = ["january", "february", "march", "april", "may", "june", "july",
          "august", "september", "october", "november", "december"]


class ApodError(Exception):
    pass


def date_from_slug(slug: str) -> str | None:
    """`apod-2026-october-1-some-title` -> `2026-10-01`; None if not an APOD slug."""
    m = re.match(r"^apod-(\d{4})-([a-z]+)-(\d{1,2})-", slug or "")
    if not m or m.group(2) not in MONTHS:
        return None
    return f"{m.group(1)}-{MONTHS.index(m.group(2)) + 1:02d}-{int(m.group(3)):02d}"


def _html_to_text(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]*>", "", fragment))).strip()


def _original_asset(url: str) -> str:
    """`dynamicimage/...` is a recompressed rendition; `content/dam/...` is the original."""
    return url.replace("assets.science.nasa.gov/dynamicimage/assets/",
                       "assets.science.nasa.gov/content/dam/")


def parse_post(post: dict) -> dict | None:
    """Map one image-article post to the api.nasa.gov shape; None if not a usable APOD."""
    apod_date = date_from_slug(post.get("slug", ""))
    if not apod_date:
        return None
    body = (post.get("content") or {}).get("rendered") or ""

    # "APOD: 2026 October 10 – Lunar Farside" -> "Lunar Farside"
    raw_title = html.unescape((post.get("title") or {}).get("rendered") or "")
    title = re.sub(r"^APOD:\s*\d{4}\s+\w+\s+\d{1,2}\s*[–—-]\s*", "", raw_title).strip()

    explanation = ""
    start = body.find("media-detail-hero__description")
    if start >= 0:
        end = body.find("</p>", start)
        frag = body[body.find(">", start) + 1: end if end >= 0 else None]
        explanation = re.sub(r"^Explanation:\s*", "", _html_to_text(frag))

    # Row label varies: "Credit:", "Credit &amp; Copyright:", "Image Credit & Copyright:" ...
    copyright_ = None
    m = re.search(r"<th[^>]*>[^<]*Credit[^<]*</th>\s*<td[^>]*>([\s\S]*?)</td>", body)
    if m:
        copyright_ = re.sub(r"^(Image|Video|Illustration)?\s*Credit[^:]*:\s*", "",
                            _html_to_text(m.group(1)), flags=re.I) or None

    # Only look inside the hero media block, so links in the explanation are ignored.
    hero_start = body.find("media-detail-hero__media")
    hero_end = body.find("media-detail-hero__content-row", hero_start)
    hero = body[hero_start: hero_end if hero_end >= 0 else None] if hero_start >= 0 else ""

    featured = ((post.get("featured_image") or {}).get("file")
                or (post.get("featured_image_url") or "").split("?")[0] or None)
    vm = (re.search(r'<video[\s\S]*?<source[^>]+src="([^"]+)"', hero)
          or re.search(r'<iframe[^>]+src="([^"]+)"', hero))

    common = {"date": apod_date, "title": title, "explanation": explanation,
              "copyright": copyright_}
    if vm:
        return {**common, "media_type": "video", "url": html.unescape(vm.group(1)),
                "thumbnail_url": featured}
    if not featured:
        return None
    return {**common, "media_type": "image", "url": featured, "hdurl": _original_asset(featured)}


def is_placeholder(data: dict | None) -> bool:
    """True for the broken api.nasa.gov response (NASA logo instead of the APOD)."""
    if not data:
        return True
    urls = f"{data.get('url') or ''} {data.get('hdurl') or ''}"
    return (data.get("title") or "").strip() == "NASA Science" or "nasa-logo" in urls


def _get(url: str, **params) -> requests.Response:
    r = requests.get(url, params=params, timeout=TIMEOUT, headers={"User-Agent": USER_AGENT})
    r.raise_for_status()
    return r


def fetch_from_site(day: str | None = None) -> dict:
    """Latest APOD, or the one for `day` (YYYY-MM-DD)."""
    params = {"per_page": 30, "orderby": "date", "order": "desc"}
    if day:
        d = date.fromisoformat(day)
        # Post timestamps don't always match the APOD date; the slug is the truth.
        params["after"] = f"{d - timedelta(days=1)}T00:00:00"
        params["before"] = f"{d + timedelta(days=2)}T00:00:00"
    apods = [a for a in map(parse_post, _get(SITE_API, **params).json()) if a]
    if day:
        apods = [a for a in apods if a["date"] == day]
    if not apods:
        raise ApodError(f"no APOD found on science.nasa.gov{' for ' + day if day else ''}")
    return max(apods, key=lambda a: a["date"])


def fetch_from_nasa_api(api_key: str, day: str | None = None) -> dict:
    params = {"api_key": api_key or "DEMO_KEY"}
    if day:
        params["date"] = day
    data = _get(NASA_API, **params).json()
    if is_placeholder(data):
        raise ApodError("api.nasa.gov returned the NASA logo placeholder")
    return data


def fetch_apod(api_key: str = "", day: str | None = None, log=None) -> dict:
    try:
        return fetch_from_site(day)
    except Exception as e:  # noqa: BLE001 - any failure falls back to the API
        if log:
            log.warning("science.nasa.gov failed (%s); trying api.nasa.gov", e)
    return fetch_from_nasa_api(api_key, day)
