import re
from datetime import date, datetime
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

BASE_URL = "https://www.iafd.com"

_LAUNCH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--window-position=-2560,0",   # push off-screen so it won't steal focus
    "--window-size=1280,800",
]
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _new_browser(p):
    browser = p.chromium.launch(
        headless=False,  # must stay False — iafd.com detects headless and blocks
        args=_LAUNCH_ARGS,
    )
    context = browser.new_context(
        user_agent=_USER_AGENT,
        viewport={"width": 1280, "height": 800},
    )
    return browser, context


def _playwright_full(name, out):
    query      = name.replace(" ", "+")
    search_url = f"{BASE_URL}/results.asp?searchtype=comprehensive&searchstring={query}"

    with sync_playwright() as p:
        browser, context = _new_browser(p)
        page = context.new_page()

        try:
            # Step 1: search
            page.goto(search_url, timeout=60000)
            page.wait_for_timeout(5000)
            search_html = page.content()

            # Step 2: parse ALL results
            soup    = BeautifulSoup(search_html, "html.parser")
            seen    = set()
            results = []
            for link in soup.find_all("a", href=True):
                if "/person.rme/" not in link["href"]:
                    continue
                url       = BASE_URL + link["href"]
                name_text = link.get_text(strip=True)
                if url not in seen and name_text:
                    seen.add(url)
                    results.append({"name": name_text, "url": url})

            out["results"] = results
            if not results:
                return

            # Step 3: visit first result's profile in same session
            page.goto(results[0]["url"], timeout=60000)
            page.wait_for_timeout(6000)
            out["profile_html"] = page.content()

        finally:
            browser.close()


def scrape_profile_by_url(profile_url):
    """
    Navigate directly to a specific IAFD profile URL and scrape it.
    Used when the user picks a different result from the stored search list.
    Returns a parsed data dict, or None on failure.
    """
    profile_html = ""

    with sync_playwright() as p:
        browser, context = _new_browser(p)
        page = context.new_page()
        try:
            page.goto(profile_url, timeout=60000)
            page.wait_for_timeout(6000)
            profile_html = page.content()
        finally:
            browser.close()

    if not profile_html:
        return None

    return scrape_actress(profile_url, profile_html)


def search_actress(name):
    """Return a list of search result dicts: [{"name": ..., "url": ...}]"""
    out = {}
    _playwright_full(name, out)
    return out.get("results", [])


def scrape_actress(profile_url, profile_html):
    """Parse a profile page and return a data dict ready to save to the DB."""
    soup = BeautifulSoup(profile_html, "html.parser")

    def clean_text(value):
        return re.sub(r"\s+", " ", value or "").strip()

    def parse_date_of_birth(text):
        m = re.search(r"\b([A-Z][a-z]+)\s+(\d{1,2}),\s+(\d{4})\b", text)
        if not m:
            return None
        try:
            return datetime.strptime(m.group(0), "%B %d, %Y").date()
        except ValueError:
            return None

    def parse_years_active(text):
        m = re.search(r"(\d{4})\s*[-–]\s*(\d{4}|present)", text, re.I)
        if not m:
            return None, None
        start = int(m.group(1))
        end   = m.group(2)
        end   = date.today().year if end.lower() == "present" else int(end)
        return start, end

    def parse_height_cm(text):
        m = re.search(r"(\d+)\s*cm", text)
        return int(m.group(1)) if m else None

    def parse_weight_kg(text):
        m = re.search(r"(\d+)\s*kg", text)
        return int(m.group(1)) if m else None

    def parse_country(text):
        if "," in text:
            return text.split(",")[-1].strip()
        return None

    # Nationalities as they appear on IAFD (single word, no commas)
    _NATIONALITIES = {
        "american", "british", "canadian", "australian", "french", "german",
        "italian", "spanish", "portuguese", "dutch", "belgian", "swiss",
        "austrian", "swedish", "norwegian", "danish", "finnish", "russian",
        "polish", "czech", "hungarian", "romanian", "bulgarian", "ukrainian",
        "greek", "turkish", "japanese", "korean", "chinese", "taiwanese",
        "thai", "vietnamese", "filipino", "indonesian", "indian", "brazilian",
        "argentinian", "colombian", "mexican", "venezuelan", "cuban",
        "puerto rican", "jamaican", "south african", "nigerian", "ghanaian",
        "egyptian", "moroccan", "iranian", "israeli", "lebanese",
    }

    def parse_nationality(text):
        t = text.lower().strip()
        if t in _NATIONALITIES:
            return text.strip()
        return None

    biodata_lines = [
        clean_text(p.get_text())
        for p in soup.select("p.biodata")
        if p.get_text(strip=True)
    ]

    data = {
        "profile_url":        profile_url,
        "name":               None,
        "date_of_birth":      None,
        "birth_country":      None,
        "nationality":        None,
        "height_cm":          None,
        "weight_kg":          None,
        "years_active_start": None,
        "years_active_end":   None,
    }

    h1 = soup.find("h1")
    if h1:
        data["name"] = clean_text(h1.get_text())

    for line in biodata_lines:
        if not data["date_of_birth"]:
            dob = parse_date_of_birth(line)
            if dob:
                data["date_of_birth"] = dob
                continue

        if not data["years_active_start"]:
            start, end = parse_years_active(line)
            if start:
                data["years_active_start"] = start
                data["years_active_end"]   = end
                continue

        if not data["height_cm"]:
            h = parse_height_cm(line)
            if h:
                data["height_cm"] = h
                continue

        if not data["weight_kg"]:
            w = parse_weight_kg(line)
            if w:
                data["weight_kg"] = w
                continue

        if not data["birth_country"]:
            country = parse_country(line)
            if country and not any(x in country.lower() for x in ["cm", "kg", "years"]):
                data["birth_country"] = country
                continue

        if not data["nationality"]:
            nat = parse_nationality(line)
            if nat:
                data["nationality"] = nat
                continue

    return data


def get_actress_data(name):
    """
    Search IAFD for `name`, scrape the top result's profile.

    Returns a tuple: (data_dict, search_results_list)
    - data_dict is None if no results found
    - search_results_list is always a list (may be empty)
    Storing all results allows the user to repick a different match later.
    """
    out = {}
    _playwright_full(name, out)

    results = out.get("results", [])
    if not results:
        return None, []

    data = scrape_actress(results[0]["url"], out.get("profile_html", ""))
    return data, results
