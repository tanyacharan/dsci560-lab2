import csv
import time
from datetime import datetime, timezone, timedelta
import requests


SUBREDDIT = "wallstreetbets"
DAYS = 180
BASE = "https://old.reddit.com"   
OUT_CSV = "wsb_last_30d_old.csv"

HEADERS = {
    "User-Agent": "Nirali-WSB-json-scraper/1.0 (contact: you@example.com)"
}
REQUEST_SLEEP = 2.0   
MAX_REQ = 1000       

def fetch_json(path, params=None):
    if params is None:
        params = {}
    params.setdefault("raw_json", 1)

    url = f"{BASE}{path}"
    for attempt in range(3):
        r = requests.get(url, headers=HEADERS, params=params, timeout=30)
        if r.status_code == 429:
            time.sleep(10 * (attempt + 1))
            continue
        r.raise_for_status()
        time.sleep(REQUEST_SLEEP)
        return r.json()
    raise RuntimeError("Too many 429s / failed attempts")

def get_subreddit_meta(sub):
    data = fetch_json(f"/r/{sub}/about.json")["data"]
    return {
        "display_name": data.get("display_name_prefixed", f"r/{sub}"),
        "title": data.get("title", ""),
        "public_description": data.get("public_description", ""),
        "subscribers": data.get("subscribers", 0),
        "created_utc": data.get("created_utc", 0),
    }

def iter_new_posts_since(sub, cutoff_ts):
    """Yield posts from /new.json until older than cutoff_ts (UTC epoch)."""
    after = None
    reqs = 0
    while reqs < MAX_REQ:
        params = {"limit": 100}
        if after:
            params["after"] = after

        payload = fetch_json(f"/r/{sub}/new.json", params=params)
        reqs += 1

        children = payload.get("data", {}).get("children", [])
        if not children:
            break

        for child in children:
            d = child.get("data", {})
            created_utc = d.get("created_utc")
            if not isinstance(created_utc, (int, float)):
                continue

            if created_utc < cutoff_ts:
                return

            yield {
                "id": d.get("id"),
                "fullname": d.get("name"),
                "title": (d.get("title") or "").strip(),
                "permalink": "https://www.reddit.com" + d.get("permalink", ""),  
                "author": d.get("author", ""),
                "score": d.get("score", 0),
                "num_comments": d.get("num_comments", 0),
                "created_utc": int(created_utc),
            }

        after = payload.get("data", {}).get("after")
        if not after:
            break

def main():
    cutoff = datetime.now(timezone.utc) - timedelta(days=DAYS)
    cutoff_ts = int(cutoff.timestamp())

    meta = get_subreddit_meta(SUBREDDIT)

    rows = []
    for p in iter_new_posts_since(SUBREDDIT, cutoff_ts):
        created_iso = datetime.fromtimestamp(p["created_utc"], tz=timezone.utc).isoformat()
        rows.append({
            "subreddit": SUBREDDIT,
            "tagline": meta["title"],
            "description": meta["public_description"],
            "title": p["title"],
            "url": p["permalink"],
            "author": p["author"],
            "score": p["score"],
            "notes(num_comments)": p["num_comments"],
            "created_utc": p["created_utc"],
            "created_iso": created_iso,
        })

    rows.sort(key=lambda r: r["created_utc"], reverse=True)

    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "subreddit", "tagline", "description",
                "title", "url", "author", "score",
                "notes(num_comments)", "created_utc", "created_iso"
            ]
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Collected {len(rows)} posts from r/{SUBREDDIT} (last {DAYS} days) → {OUT_CSV}")

if __name__ == "__main__":
    main()
