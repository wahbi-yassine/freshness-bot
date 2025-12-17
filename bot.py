import os
import requests
from datetime import datetime, timezone

# --- WordPress REST API ---
WP_API = os.environ["WP_URL"].rstrip("/") + "/wp-json/wp/v2"
WP_AUTH = (os.environ["WP_USER"], os.environ["WP_PASSWORD"])

# --- API-Football from dashboard.api-football.com ---
API_KEY = os.environ.get("FOOTBALL_API_KEY", "").strip()

HEADERS = {
    "x-apisports-key": API_KEY
}

def get_fixtures():
    # Today UTC
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if not API_KEY:
        raise RuntimeError("FOOTBALL_API_KEY is missing or empty.")

    # Current new API-Football endpoint (modern version)
    url = "https://v3.football.api-sports.io/fixtures"
    params = {"date": today}

    r = requests.get(url, headers=HEADERS, params=params, timeout=30)

    if r.status_code in (401, 403):
        raise RuntimeError(
            f"Football API auth failed {r.status_code}: {r.text}"
        )

    r.raise_for_status()
    data = r.json()

    # The new API returns fixtures under data["response"]
    return data.get("response", [])

def get_post_id_by_slug(slug):
    r = requests.get(f"{WP_API}/posts", params={"slug": slug}, auth=WP_AUTH, timeout=30)
    r.raise_for_status()
    results = r.json()
    return results[0]["id"] if results else None

def create_or_update_post(match):
    match_id = match["fixture"]["id"]
    slug = f"match-{match_id}"

    home = match["teams"]["home"]["name"]
    away = match["teams"]["away"]["name"]
    date = match["fixture"]["date"]
    status = match["fixture"]["status"]["long"]
    venue = match["fixture"].get("venue", {}).get("name", "TBD")

    title = f"{home} vs {away} Live Score & Updates"
    content = f"""
<h2>Match Details</h2>
<ul>
  <li><strong>Teams:</strong> {home} vs {away}</li>
  <li><strong>Date:</strong> {date}</li>
  <li><strong>Status:</strong> {status}</li>
  <li><strong>Stadium:</strong> {venue}</li>
</ul>
<p>Live score and update content automatically published.</p>
"""

    post_data = {
        "title": title,
        "slug": slug,
        "content": content,
        "status": "publish",
        "comment_status": "closed",
    }

    existing_id = get_post_id_by_slug(slug)
    if existing_id:
        print(f"Updating {slug} (post id {existing_id})")
        r = requests.post(f"{WP_API}/posts/{existing_id}", json=post_data, auth=WP_AUTH)
        r.raise_for_status()
    else:
        print(f"Creating {slug}")
        r = requests.post(f"{WP_API}/posts", json=post_data, auth=WP_AUTH)
        r.raise_for_status()

def main():
    print("Starting freshness run...")
    fixtures = get_fixtures()
    print(f"Fetched {len(fixtures)} fixtures for today.")

    for match in fixtures[:5]:
        create_or_update_post(match)

    print("Run complete.")

if __name__ == "__main__":
    main()
