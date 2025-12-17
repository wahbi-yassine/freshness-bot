import os
import requests
import base64
from datetime import datetime, timezone

# =====================================================
# WORDPRESS CONFIG
# =====================================================
WP_BASE = os.environ["WP_URL"].rstrip("/")
WP_API = WP_BASE + "/wp-json/wp/v2"
WP_USER = os.environ["WP_USER"]
WP_PASSWORD = os.environ["WP_PASSWORD"]

# =====================================================
# API-FOOTBALL (NEW DASHBOARD)
# =====================================================
FOOTBALL_API_KEY = os.environ.get("FOOTBALL_API_KEY", "").strip()
FOOTBALL_API_URL = "https://v3.football.api-sports.io/fixtures"

# =====================================================
# HELPERS
# =====================================================

def wp_headers():
    """
    Explicit Basic Auth header.
    This bypasses many hosting/security issues with requests' auth=().
    """
    token = base64.b64encode(f"{WP_USER}:{WP_PASSWORD}".encode()).decode()
    return {
        "Authorization": f"Basic {token}",
        "User-Agent": "freshness-bot/1.0",
        "Content-Type": "application/json",
    }

def test_wp_auth():
    """
    Definitive WordPress REST auth test.
    If this fails, posts will never work.
    """
    url = f"{WP_API}/users/me"
    r = requests.get(url, headers=wp_headers(), timeout=30)
    print("WP auth test status:", r.status_code)
    print("WP auth test body:", r.text[:300])
    r.raise_for_status()

# =====================================================
# API-FOOTBALL
# =====================================================

def get_fixtures():
    if not FOOTBALL_API_KEY:
        raise RuntimeError("FOOTBALL_API_KEY is empty or missing.")

    headers = {
        "x-apisports-key": FOOTBALL_API_KEY
    }

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    r = requests.get(
        FOOTBALL_API_URL,
        headers=headers,
        params={"date": today},
        timeout=30
    )

    if r.status_code in (401, 403):
        raise RuntimeError(
            f"API-Football auth failed ({r.status_code}): {r.text[:200]}"
        )

    r.raise_for_status()
    data = r.json()
    return data.get("response", [])

# =====================================================
# WORDPRESS POSTS
# =====================================================

def get_post_id_by_slug(slug):
    r = requests.get(
        f"{WP_API}/posts",
        params={"slug": slug},
        headers=wp_headers(),
        timeout=30
    )
    r.raise_for_status()
    posts = r.json()
    return posts[0]["id"] if posts else None

def create_or_update_post(match):
    match_id = match["fixture"]["id"]
    slug = f"match-{match_id}"

    home = match["teams"]["home"]["name"]
    away = match["teams"]["away"]["name"]
    date = match["fixture"]["date"]
    status = match["fixture"]["status"]["long"]
    venue = match.get("fixture", {}).get("venue", {}).get("name", "TBD")

    title = f"{home} vs {away} Live Score & Updates"

    content = f"""
<h2>Match Details</h2>
<ul>
  <li><strong>Teams:</strong> {home} vs {away}</li>
  <li><strong>Date:</strong> {date}</li>
  <li><strong>Status:</strong> {status}</li>
  <li><strong>Stadium:</strong> {venue}</li>
</ul>
<p>Automatic live score and match updates.</p>
"""

    payload = {
        "title": title,
        "slug": slug,
        "content": content,
        "status": "publish",
        "comment_status": "closed",
    }

    existing_id = get_post_id_by_slug(slug)

    if existing_id:
        print(f"Updating {slug}")
        r = requests.post(
            f"{WP_API}/posts/{existing_id}",
            json=payload,
            headers=wp_headers(),
            timeout=30
        )
    else:
        print(f"Creating {slug}")
        r = requests.post(
            f"{WP_API}/posts",
            json=payload,
            headers=wp_headers(),
            timeout=30
        )

    r.raise_for_status()

# =====================================================
# MAIN
# =====================================================

def main():
    print("Starting freshness run...")

    # 1) Verify WordPress authentication FIRST
    test_wp_auth()

    # 2) Fetch fixtures
    fixtures = get_fixtures()
    print(f"Fetched {len(fixtures)} fixtures.")

    # 3) Publish (free-tier safe)
    for match in fixtures[:5]:
        create_or_update_post(match)

    print("Run complete.")

if __name__ == "__main__":
    main()
