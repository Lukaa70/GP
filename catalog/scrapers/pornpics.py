import re
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

SEARCH_URL = "https://www.pornpics.com/?q={query}"


def _playwright_photos(name, out, max_galleries=10, photos_per_gallery=5):
    query = name.replace(" ", "+")
    search_url = SEARCH_URL.format(query=query)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,  # must stay False — site detects headless
            args=[
                "--disable-blink-features=AutomationControlled",
                "--window-position=-2560,0",   # push off-screen so it won't steal focus
                "--window-size=1280,800",
            ]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()

        try:
            # ── Step 1: search ───────────────────────────────────────────
            page.goto(search_url)
            page.wait_for_timeout(4000)
            search_html = page.content()

            soup = BeautifulSoup(search_html, "html.parser")
            gallery_items = []
            for li in soup.select("li.thumbwook")[:max_galleries]:
                a = li.select_one("a.rel-link")
                if a and a.get("href"):
                    gallery_items.append({
                        "url":   a["href"],
                        "title": a.get("title", "").strip(),
                    })

            out["gallery_count"] = len(gallery_items)

            # ── Step 2: visit each gallery, collect photo URLs ────────────
            photos = []
            for gallery in gallery_items:
                try:
                    page.goto(gallery["url"])
                    page.wait_for_timeout(3000)
                    gallery_html = page.content()

                    gallery_soup = BeautifulSoup(gallery_html, "html.parser")

                    for a_tag in gallery_soup.select("a.rel-link")[:photos_per_gallery]:
                        url_1280 = a_tag.get("href", "")
                        img = a_tag.select_one("img")
                        if not img:
                            continue
                        url_460 = img.get("src") or img.get("data-src", "")

                        # Only keep real CDN image URLs
                        if not url_460 or not url_460.startswith("http"):
                            continue

                        photos.append({
                            "source_url_460":  url_460,
                            "source_url_1280": url_1280 if url_1280.startswith("http") else "",
                            "gallery_title":   gallery["title"],
                            "gallery_url":     gallery["url"],
                        })

                except Exception:
                    # Skip broken galleries silently — don't abort the whole scrape
                    continue

            out["photos"] = photos

        finally:
            browser.close()


def scrape_actress_photos(name, max_galleries=10, photos_per_gallery=5):
    """
    Search pornpics.com for `name`, visit up to `max_galleries` galleries,
    collect up to `photos_per_gallery` photos from each.

    Returns a list of dicts:
      {
        "source_url_460":  "https://cdni.pornpics.com/460/...",
        "source_url_1280": "https://cdni.pornpics.com/1280/...",
        "gallery_title":   "...",
        "gallery_url":     "https://www.pornpics.com/galleries/...",
      }
    """
    out = {}
    _playwright_photos(name, out, max_galleries, photos_per_gallery)
    return out.get("photos", [])


_LAUNCH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--window-position=-2560,0",
    "--window-size=1280,800",
]
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def get_gallery_urls(name, max_galleries=10):
    """
    Search pornpics.com for `name` and return a list of gallery dicts.
    Only visits the search page — no gallery pages.
    Fast: used as step 1 of the two-stage AJAX scrape.
    Returns: [{"url": ..., "title": ...}, ...]
    """
    query      = name.replace(" ", "+")
    search_url = SEARCH_URL.format(query=query)
    galleries  = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=_LAUNCH_ARGS)
        context = browser.new_context(user_agent=_USER_AGENT, viewport={"width": 1280, "height": 800})
        page    = context.new_page()
        try:
            page.goto(search_url)
            page.wait_for_timeout(4000)
            soup = BeautifulSoup(page.content(), "html.parser")
            for li in soup.select("li.thumbwook")[:max_galleries]:
                a = li.select_one("a.rel-link")
                if a and a.get("href"):
                    galleries.append({"url": a["href"], "title": a.get("title", "").strip()})
        finally:
            browser.close()

    return galleries


def scrape_gallery_photos(gallery_url, gallery_title="", max_photos=None):
    """
    Visit a single gallery page and return all photo dicts from it.
    Used as step 2 of the two-stage AJAX scrape, and for "Get all from album".
    Returns: [{"source_url_460": ..., "source_url_1280": ..., ...}, ...]
    """
    photos = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=_LAUNCH_ARGS)
        context = browser.new_context(user_agent=_USER_AGENT, viewport={"width": 1280, "height": 800})
        page    = context.new_page()
        try:
            page.goto(gallery_url)
            page.wait_for_timeout(3000)
            soup     = BeautifulSoup(page.content(), "html.parser")
            a_tags   = soup.select("a.rel-link")
            if max_photos:
                a_tags = a_tags[:max_photos]

            for a_tag in a_tags:
                url_1280 = a_tag.get("href", "")
                img      = a_tag.select_one("img")
                if not img:
                    continue
                url_460 = img.get("src") or img.get("data-src", "")
                if not url_460 or not url_460.startswith("http"):
                    continue
                photos.append({
                    "source_url_460":  url_460,
                    "source_url_1280": url_1280 if url_1280.startswith("http") else "",
                    "gallery_title":   gallery_title,
                    "gallery_url":     gallery_url,
                })
        finally:
            browser.close()

    return photos
