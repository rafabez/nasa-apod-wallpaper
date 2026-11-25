from apod_wallpaper import source

HERO_IMAGE = """
<div class="media-detail-hero__media"><img src="x.jpg"></div>
<div class="media-detail-hero__content-row">
<p class="media-detail-hero__description"><strong>Explanation:</strong> Stars &amp; dust
 <a href="https://example.com/x.mp4">link</a> in   space.</p>
<table><tr><th>Image Credit &amp; Copyright:</th><td><a href="#">Jane Doe</a></td></tr></table>
</div>
"""

HERO_VIDEO = """
<div class="media-detail-hero__media"><video title="t"><source src="https://assets.example/v.mp4?a=1&amp;b=2" type="video/mp4"></video></div>
<div class="media-detail-hero__content-row"><p class="media-detail-hero__description">Explanation: Moving.</p></div>
"""


def post(slug, body, featured="https://assets.science.nasa.gov/dynamicimage/assets/science/cds/apod/a.jpg"):
    return {
        "slug": slug,
        "title": {"rendered": "APOD: 2026 November 24 &#8211; Galaxies &amp; Friends"},
        "content": {"rendered": body},
        "featured_image": {"file": featured} if featured else None,
    }


def test_date_from_slug():
    assert source.date_from_slug("apod-2026-november-5-x") == "2026-11-05"
    assert source.date_from_slug("apod-2026-smarch-5-x") is None
    assert source.date_from_slug("webb-2026-november-5-x") is None


def test_parse_image_post():
    a = source.parse_post(post("apod-2026-november-24-galaxies", HERO_IMAGE))
    assert a["date"] == "2026-11-24"
    assert a["title"] == "Galaxies & Friends"
    assert a["media_type"] == "image"
    assert a["explanation"] == "Stars & dust link in space."
    assert a["copyright"] == "Jane Doe"
    assert a["hdurl"] == "https://assets.science.nasa.gov/content/dam/science/cds/apod/a.jpg"


def test_parse_video_post_ignores_links_outside_hero():
    a = source.parse_post(post("apod-2026-november-25-v", HERO_VIDEO))
    assert a["media_type"] == "video"
    assert a["url"] == "https://assets.example/v.mp4?a=1&b=2"
    assert a["thumbnail_url"].endswith("a.jpg")


def test_image_post_without_image_is_skipped():
    assert source.parse_post(post("apod-2026-november-24-x", HERO_IMAGE, featured=None)) is None


def test_placeholder_guard():
    assert source.is_placeholder({"title": "NASA Science", "url": "x.png"})
    assert source.is_placeholder({"title": "X", "url": "https://x/nasa-logo@2x.png"})
    assert not source.is_placeholder({"title": "Galaxies", "url": "https://x/a.jpg"})


def test_fetch_from_site_picks_latest(monkeypatch):
    posts = [post("apod-2026-november-23-a", HERO_IMAGE), post("not-apod", HERO_IMAGE),
             post("apod-2026-november-24-b", HERO_IMAGE)]

    class Resp:
        def json(self):
            return posts

    monkeypatch.setattr(source, "_get", lambda url, **params: Resp())
    assert source.fetch_from_site()["date"] == "2026-11-24"
    assert source.fetch_from_site("2026-11-23")["date"] == "2026-11-23"
