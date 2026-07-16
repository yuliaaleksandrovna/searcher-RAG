"""
Parses articles from Wikipedia API and saves them to data/articles.json.
Usage: python scripts/parser.py
"""

import json
import os
import time
import requests

TOPICS = [
    "Python_(programming_language)",
    "JavaScript",
    "Go_(programming_language)",
    "Rust_(programming_language)",
    "Machine_learning",
    "Deep_learning",
    "Neural_network",
    "Transformer_(machine_learning_model)",
    "Docker_(software)",
    "Kubernetes",
    "Representational_state_transfer",
    "GraphQL",
    "PostgreSQL",
    "MongoDB",
    "Redis",
    "Elasticsearch",
    "FastAPI",
    "Django_(web_framework)",
    "React_(software)",
    "Git",
    "Linux",
    "Microservices",
    "DevOps",
    "Algorithm",
    "Data_structure",
    "Artificial_intelligence",
    "Natural_language_processing",
    "Computer_vision",
    "Cloud_computing",
    "Application_programming_interface",
]


HEADERS = {
    "User-Agent": "SearcherMVP/1.0 (educational project; python-requests)"
}


def fetch_article(title: str) -> dict | None:
    url = "https://en.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "titles": title,
        "prop": "extracts|info",
        "explaintext": True,
        "inprop": "url",
        "format": "json",
        "redirects": 1,
    }
    for attempt in range(4):
        try:
            resp = requests.get(url, params=params, headers=HEADERS, timeout=15)
            if resp.status_code == 429:
                wait = 15 * (2 ** attempt)
                print(f"  Rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            pages = resp.json()["query"]["pages"]
            page = next(iter(pages.values()))
            if "missing" in page or "extract" not in page or not page["extract"].strip():
                return None
            return {
                "title": page.get("title", title),
                "url": page.get("fullurl", f"https://en.wikipedia.org/wiki/{title}"),
                "content": page["extract"].strip()[:8000],
                "source": "Wikipedia",
            }
        except Exception as e:
            print(f"  Error (attempt {attempt + 1}): {e}")
            time.sleep(5)
    return None


def main():
    os.makedirs("data", exist_ok=True)
    articles = []

    for i, topic in enumerate(TOPICS):
        print(f"[{i+1}/{len(TOPICS)}] {topic}")
        article = fetch_article(topic)
        if article:
            articles.append(article)
            print(f"  OK — {article['title']} ({len(article['content'])} chars)")
        else:
            print(f"  Skipped")
        time.sleep(2)

    output = "data/articles.json"
    with open(output, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)

    print(f"\nDone: {len(articles)} articles saved to {output}")


if __name__ == "__main__":
    main()
