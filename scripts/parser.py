"""
Parses articles from Wikipedia via the MediaWiki API and saves them to
data/articles.json.

Collects a broad set of articles (not a fixed hand-picked topic list) using
list=allpages for title discovery + batched prop=extracts fetches, so the
collection meets the required size (>=5000 documents) instead of the ~30
topic-based articles used in the earlier draft. Each article also carries
its non-hidden Wikipedia categories (fetched in the same batched request,
no extra round-trips) for the /search?category=... filter, and exact
content duplicates (e.g. near-identical stub pages) are skipped.

Usage: python scripts/parser.py
"""

import hashlib
import json
import os
import time
import requests

API_URL = "https://en.wikipedia.org/w/api.php"
HEADERS = {
    "User-Agent": "SearcherMVP/1.0 (educational project; python-requests)"
}

# Discover more titles than the 5000 target, since some fraction of pages
# (stubs, list pages, disambiguation-like pages, exact-content duplicates)
# get filtered out below.
DISCOVER_TARGET = 7000
MIN_FINAL_DOCS = 5000

TITLE_BATCH = 500     # max page titles per list=allpages request
EXTRACT_BATCH = 20    # max titles per prop=extracts request for anonymous API access
MIN_CONTENT_LENGTH = 200
MAX_CONTENT_LENGTH = 4000
MAX_CATEGORIES = 5    # categories stored per article, for search filtering

SAVE_EVERY_N_BATCHES = 25  # checkpoint to disk periodically (~500 titles) so an
                           # interruption doesn't lose everything collected so far
OUTPUT_PATH = "data/articles.json"


def _get(params: dict, max_retries: int = 4) -> dict | None:
    params = {**params, "format": "json"}
    for attempt in range(max_retries):
        try:
            resp = requests.get(API_URL, params=params, headers=HEADERS, timeout=20)
            if resp.status_code == 429:
                wait = 15 * (2 ** attempt)
                print(f"  Rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            print(f"  Error (attempt {attempt + 1}): {e}")
            time.sleep(5)
    return None


def discover_titles(target: int) -> list[str]:
    """Page through list=allpages to gather non-redirect article titles."""
    titles = []
    apcontinue = None

    while len(titles) < target:
        params = {
            "action": "query",
            "list": "allpages",
            "apnamespace": 0,
            "apfilterredir": "nonredirects",
            "aplimit": TITLE_BATCH,
        }
        if apcontinue:
            params["apcontinue"] = apcontinue

        data = _get(params)
        if data is None:
            print("  Could not fetch a page of titles, stopping discovery early.")
            break

        pages = data.get("query", {}).get("allpages", [])
        titles.extend(p["title"] for p in pages)
        print(f"  Discovered {len(titles)} candidate titles so far...")

        apcontinue = data.get("continue", {}).get("apcontinue")
        if not apcontinue:
            break
        time.sleep(0.3)

    return titles[:target]


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def fetch_batch(titles: list[str]) -> list[dict]:
    """Fetch extracts + URLs + categories for up to EXTRACT_BATCH titles at once."""
    params = {
        "action": "query",
        "titles": "|".join(titles),
        "prop": "extracts|info|categories",
        "explaintext": True,
        "inprop": "url",
        "redirects": 1,
        "cllimit": "max",
        "clshow": "!hidden",  # skip maintenance/tracking categories (e.g. "CS1 errors")
    }
    data = _get(params)
    if data is None:
        return []

    pages = data.get("query", {}).get("pages", {})
    docs = []
    for page in pages.values():
        if "missing" in page or "extract" not in page:
            continue
        content = page["extract"].strip()
        if len(content) < MIN_CONTENT_LENGTH:
            continue
        title = page.get("title", "")
        categories = [
            c["title"].split(":", 1)[-1] for c in page.get("categories", [])
        ][:MAX_CATEGORIES]
        docs.append({
            "title": title,
            "url": page.get("fullurl", f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"),
            "content": content[:MAX_CONTENT_LENGTH],
            "source": "Wikipedia",
            "categories": categories,
        })
    return docs


def save(articles: list[dict]) -> None:
    os.makedirs("data", exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)


def main():
    print(f"Discovering at least {DISCOVER_TARGET} candidate titles...")
    titles = discover_titles(DISCOVER_TARGET)
    print(f"Discovered {len(titles)} titles. Fetching extracts in batches of {EXTRACT_BATCH}...\n")

    articles = []
    seen_hashes = set()
    duplicates_skipped = 0
    batch_num = 0
    for i in range(0, len(titles), EXTRACT_BATCH):
        batch_num += 1
        batch = titles[i:i + EXTRACT_BATCH]
        for doc in fetch_batch(batch):
            content_hash = _content_hash(doc["content"])
            if content_hash in seen_hashes:
                duplicates_skipped += 1
                continue
            seen_hashes.add(content_hash)
            articles.append(doc)

        done = i + len(batch)
        print(f"[{done}/{len(titles)} titles processed] collected {len(articles)} documents "
              f"({duplicates_skipped} duplicates skipped)")

        if batch_num % SAVE_EVERY_N_BATCHES == 0:
            save(articles)

        time.sleep(0.4)

    save(articles)
    print(f"\nDone: {len(articles)} articles saved to {OUTPUT_PATH} "
          f"({duplicates_skipped} exact-content duplicates skipped)")

    if len(articles) < MIN_FINAL_DOCS:
        print(
            f"WARNING: only {len(articles)} documents collected, below the "
            f"required {MIN_FINAL_DOCS}. Increase DISCOVER_TARGET in this "
            f"script and rerun."
        )


if __name__ == "__main__":
    main()
