"""
Loads parsed articles into Elasticsearch.
Usage: python scripts/indexer.py
"""

import json
import os
import sys
from dotenv import load_dotenv
from elasticsearch import Elasticsearch, helpers

load_dotenv()

ES_URL = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
INDEX = "articles"

MAPPING = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
    },
    "mappings": {
        "properties": {
            "title":   {"type": "text"},
            "content": {"type": "text"},
            "url":     {"type": "keyword"},
            "source":  {"type": "keyword"},
        }
    },
}


def main():
    es = Elasticsearch(ES_URL)

    if not es.ping():
        print(f"ERROR: Cannot reach Elasticsearch at {ES_URL}")
        print("Start it first: docker-compose up -d")
        sys.exit(1)

    if es.indices.exists(index=INDEX):
        es.indices.delete(index=INDEX)
        print(f"Deleted existing index '{INDEX}'")

    es.indices.create(index=INDEX, body=MAPPING)
    print(f"Created index '{INDEX}'")

    try:
        with open("data/articles.json", encoding="utf-8") as f:
            articles = json.load(f)
    except FileNotFoundError:
        print("ERROR: data/articles.json not found. Run parser.py first.")
        sys.exit(1)

    actions = [
        {"_index": INDEX, "_id": str(i), "_source": doc}
        for i, doc in enumerate(articles)
    ]

    success, errors = helpers.bulk(es, actions, raise_on_error=False)
    print(f"Indexed {success} documents ({len(errors)} errors)")

    es.indices.refresh(index=INDEX)
    count = es.count(index=INDEX)["count"]
    print(f"Index now contains {count} documents")


if __name__ == "__main__":
    main()
