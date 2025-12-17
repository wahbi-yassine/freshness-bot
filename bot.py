import os
import requests
from datetime import datetime

WP_API = os.environ["WP_URL"].rstrip("/") + "/wp-json/wp/v2"
WP_AUTH = (os.environ["WP_USER"], os.environ["WP_PASSWORD"])

API_KEY = os.environ["FOOTBALL_API_KEY"]
HEADERS = {
    "x-rapidapi-host": "api-football-v1.p.rapidapi.com",
    "x-rapidapi-key": API_KEY,
}

def get_fixtures():
    today = datetime.utcnow().strftime("%Y-%m-%d")
    url = "https://api-football-v1.p.rapidapi.com/v3/fixtures"
    r = requests.get(url, headers=HEADERS, params={"date": today}, timeout=30)
    r.raise_for_status()
    return r.json().get("response", [])

def get_post_id_by_slug(slug):
    r = requests.get(f"{WP_API}/posts", params={"slug": slug}, auth=WP_AUTH, timeout=30)
    r.raise_for_status()
    data = r.json()
    return data[0]["id"] if data else None

def create_or_update_post(match):
    match_id = match["fixture"]["id"]
    slug = f"match-{match_id}"

    home = match["teams"]["home"]["name"]
    away = match["teams"]["away"]["name"]
    date = match["fixture"]["date"]
    status = match["fixture"]["status"]["long"]
    venue = match.get("fixture", {}).get("venue", {}).get("name") or "TBD"

    title = f"{home} vs {away} Live Score & Updates"
    content = f"""
<h2>Match Details</h2>
<ul>
  <li><strong>Teams:</strong> {home} vs {away}</li>
  <li><strong>Date:</strong> {date}</li>
  <li><strong>Status:</strong> {status}</li>
  <li><strong>Stadium:</strong> {venue}</li>
</ul>
<p>Live updates for the {home} vs {away} match. Check back for confirmed lineups and live scores.</p>
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
        r = requests.post(f"{WP_API}/posts/{existing_id}", json=post_data, auth=WP_AUTH, timeout=30)
        r.raise_for_status()
    else:
        print(f"Creating {slug}")
        r = requests.post(f"{WP_API}/posts", json=post_data, auth=WP_AUTH, timeout=30)
        r.raise_for_status()

def main():
    print("Starting freshness run...")
    fixtures = get_fixtures()

    for match in fixtures[:5]:
        create_or_update_post(match)

    print("Run complete.")

if __name__ == "__main__":
    main()
