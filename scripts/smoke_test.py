"""
End-to-end smoke test against a running server. Exercises the whole auth/roles
flow: register -> login -> search (auth required) -> role-gated save -> admin
promotion -> admin-only endpoints denied/allowed.

Requires an existing owner account (create one first with scripts/seed_owner.py).

Usage:
    python scripts/smoke_test.py --owner-username admin --owner-password secret123
    python scripts/smoke_test.py --base-url http://localhost:8000 --owner-username admin --owner-password secret123
"""

import argparse
import sys
import uuid

import requests

FAILURES = []


def check(label, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}" + (f" — {detail}" if detail and not condition else ""))
    if not condition:
        FAILURES.append(label)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--owner-username", required=True)
    parser.add_argument("--owner-password", required=True)
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    reader_username = f"smoke_{uuid.uuid4().hex[:8]}"
    reader_password = "smoke_pw_123"

    print(f"Base URL: {base}")
    print(f"Test reader account: {reader_username}\n")

    # 1. Register a fresh reader
    r = requests.post(f"{base}/auth/register", json={"username": reader_username, "password": reader_password})
    check("register reader", r.status_code == 200, r.text)
    reader_token = r.json().get("access_token") if r.ok else None
    check("register returns reader role", r.ok and r.json().get("role") == "reader", r.text)

    reader_headers = {"Authorization": f"Bearer {reader_token}"}

    # 2. /me reflects the new user
    r = requests.get(f"{base}/me", headers=reader_headers)
    check("GET /me as reader", r.ok and r.json().get("username") == reader_username, r.text)

    # 3. Search requires auth
    r = requests.get(f"{base}/search", params={"q": "python"})
    check("GET /search without token is rejected", r.status_code == 401, r.text)

    r = requests.get(f"{base}/search", params={"q": "python"}, headers=reader_headers)
    check("GET /search with token succeeds", r.status_code == 200, r.text)

    # 3b. category filter endpoint + query param
    r = requests.get(f"{base}/categories", headers=reader_headers)
    check("GET /categories succeeds", r.status_code == 200, r.text)
    categories = r.json() if r.ok else []
    if categories:
        sample_category = categories[0]["category"]
        r = requests.get(
            f"{base}/search", params={"q": "a", "category": sample_category}, headers=reader_headers
        )
        check("GET /search with category filter succeeds", r.status_code == 200, r.text)
        check(
            "GET /search with category filter only returns that category",
            r.ok and all(sample_category in doc["categories"] for doc in r.json()["results"]),
            r.text,
        )
    else:
        print("  (skipped category-filter checks: index has no categories yet)")

    # 4. reader cannot save
    r = requests.post(
        f"{base}/saved",
        json={"article_url": "https://en.wikipedia.org/wiki/Python", "article_title": "Python"},
        headers=reader_headers,
    )
    check("reader is forbidden from POST /saved", r.status_code == 403, r.text)

    # 5. reader cannot see admin endpoints
    r = requests.get(f"{base}/admin/history", headers=reader_headers)
    check("reader is forbidden from GET /admin/history", r.status_code == 403, r.text)

    # 6. log in as owner and promote the reader to writer
    r = requests.post(f"{base}/auth/login", json={"username": args.owner_username, "password": args.owner_password})
    check("owner login", r.ok, r.text)
    owner_token = r.json().get("access_token") if r.ok else None
    owner_headers = {"Authorization": f"Bearer {owner_token}"}

    r = requests.get(f"{base}/admin/users", headers=owner_headers)
    check("owner can list users", r.ok, r.text)
    reader_id = next((u["id"] for u in r.json() if u["username"] == reader_username), None) if r.ok else None
    check("found test reader in user list", reader_id is not None)

    r = requests.patch(f"{base}/admin/users/{reader_id}/role", json={"role": "writer"}, headers=owner_headers)
    check("owner promotes reader to writer", r.ok and r.json().get("role") == "writer", r.text)

    # 7. same token now behaves as writer (role is re-checked from DB each request)
    r = requests.post(
        f"{base}/saved",
        json={"article_url": "https://en.wikipedia.org/wiki/Python", "article_title": "Python"},
        headers=reader_headers,
    )
    check("promoted user can now POST /saved", r.status_code == 201, r.text)
    saved_id = r.json().get("id") if r.ok else None

    r = requests.get(f"{base}/saved", headers=reader_headers)
    check("GET /saved returns the saved article", r.ok and any(s["id"] == saved_id for s in r.json()), r.text)

    # 8. admin-only endpoints work for the owner
    r = requests.get(f"{base}/admin/history", headers=owner_headers)
    check("owner can GET /admin/history", r.ok, r.text)

    r = requests.get(f"{base}/admin/stats", headers=owner_headers)
    check("owner can GET /admin/stats", r.ok, r.text)

    # 9. cleanup
    if saved_id is not None:
        r = requests.delete(f"{base}/saved/{saved_id}", headers=reader_headers)
        check("delete own saved article", r.status_code == 204, r.text)

    print()
    if FAILURES:
        print(f"{len(FAILURES)} check(s) FAILED: {', '.join(FAILURES)}")
        sys.exit(1)
    print("All checks passed.")


if __name__ == "__main__":
    main()
