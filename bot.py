import os
import requests
import base64
import time
from datetime import datetime, timezone

# =====================================================
# WORDPRESS CONFIG (APP PASSWORD ONLY)
# =====================================================
WP_BASE = os.environ["WP_URL"].rstrip("/")
WP_API = WP_BASE + "/wp-json/wp/v2"

WP_USER = os.environ.get("WP_USER", "").strip()
WP_APP_PASSWORD = os.environ.get("WP_APP_PASSWORD", "").strip()

# =====================================================
# API-FOOTBALL
# =====================================================
FOOTBALL_API_KEY = os.environ.get("FOOTBALL_API_KEY", "").strip()
FOOTBALL_API_URL = "https://v3.football.api-sports.io/fixtures"

# League IDs for filtering (Optional)
# 39=Premier League, 140=La Liga, 135=Serie A, 78=Bundesliga, 61=Ligue 1, 2=UCL
PRIORITY_LEAGUES = [39, 140, 135, 78, 61, 2] 

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "freshness-bot/4.0",
    "Accept": "application/json",
})

# =====================================================
# SAFE ENV CHECK & AUTH
# =====================================================
def print_env_status():
    print("ENV CHECK:")
    print(" - WP_URL:", bool(WP_BASE))
    print(" - WP_USER:", bool(WP_USER))
    print(" - WP_APP_PASSWORD:", bool(WP_APP_PASSWORD))
    print(" - FOOTBALL_API_KEY:", bool(FOOTBALL_API_KEY))

def assert_auth_config():
    if not (WP_USER and WP_APP_PASSWORD):
        raise RuntimeError(
            "Missing WordPress auth. Set WP_USER and WP_APP_PASSWORD."
        )

def basic_auth_header(user: str, app_pw: str) -> str:
    app_pw = app_pw.replace(" ", "")
    token = base64.b64encode(f"{user}:{app_pw}".encode("utf-8")).decode("utf-8")
    return f"Basic {token}"

def wp_headers():
    return {
        "Authorization": basic_auth_header(WP_USER, WP_APP_PASSWORD),
        "Content-Type": "application/json",
    }

def wp_request(method: str, path: str, *, params=None, json=None, timeout=30):
    url = f"{WP_API}/{path.lstrip('/')}"
    
    for attempt in range(3):
        try:
            r = SESSION.request(
                method=method.upper(),
                url=url,
                headers=wp_headers(),
                params=params,
                json=json,
                timeout=timeout,
            )
            
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(2)
                continue
                
            if r.status_code in (401, 403):
                print(f"Auth Error: {r.status_code} - {r.text[:200]}")
            
            r.raise_for_status()
            return r
            
        except requests.RequestException as e:
            if attempt == 2: raise
            time.sleep(2)

def test_wp_auth():
    r = wp_request("GET", "/users/me")
    print(f"WP Auth OK: {r.json().get('name')}")

# =====================================================
# FETCH FIXTURES
# =====================================================
def get_fixtures():
    if not FOOTBALL_API_KEY:
        raise RuntimeError("Missing FOOTBALL_API_KEY")

    headers = {"x-apisports-key": FOOTBALL_API_KEY}
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Fetch all matches for today
    r = requests.get(
        FOOTBALL_API_URL,
        headers=headers,
        params={"date": today},
        timeout=30,
    )
    r.raise_for_status()
    return r.json().get("response", [])

# =====================================================
# CREATE / UPDATE POST (PRO VERSION)
# =====================================================
def get_post_id_by_slug(slug: str):
    r = wp_request("GET", "/posts", params={"slug": slug})
    posts = r.json()
    return posts[0]["id"] if posts else None

def create_or_update_post(match):
    match_id = match["fixture"]["id"]
    slug = f"match-{match_id}"

    # 1. EXTRACT DATA
    home = match["teams"]["home"]["name"]
    away = match["teams"]["away"]["name"]
    home_logo = match["teams"]["home"]["logo"]
    away_logo = match["teams"]["away"]["logo"]
    
    venue = match.get("fixture", {}).get("venue", {}).get("name", "TBD")
    date_iso = match["fixture"]["date"]
    status_long = match["fixture"]["status"]["long"]
    league_name = match["league"]["name"]
    round_name = match["league"]["round"]

    # 2. GENERATE JSON-LD SCHEMA (SEO)
    schema_markup = f"""
    <script type="application/ld+json">
    {{
      "@context": "https://schema.org",
      "@type": "SportsEvent",
      "name": "{home} vs {away}",
      "startDate": "{date_iso}",
      "eventStatus": "https://schema.org/EventScheduled",
      "competitor": [
        {{ "@type": "SportsTeam", "name": "{home}", "logo": "{home_logo}" }},
        {{ "@type": "SportsTeam", "name": "{away}", "logo": "{away_logo}" }}
      ],
      "location": {{ "@type": "Place", "name": "{venue}" }}
    }}
    </script>
    """

    # 3. BUILD HTML (Visual Layout for Kadence)
    html_content = f"""
    {schema_markup}
    <div class="wp-block-group" style="text-align:center; padding:20px; background:#f5f5f5; border-radius:8px;">
        <div class="wp-block-columns">
            <div class="wp-block-column">
                <img src="{home_logo}" alt="{home}" width="80" height="80"/>
                <h3>{home}</h3>
            </div>
            <div class="wp-block-column is-vertically-aligned-center">
                <h2 style="color:#444;">VS</h2>
                <p><strong>{status_long}</strong></p>
            </div>
            <div class="wp-block-column">
                <img src="{away_logo}" alt="{away}" width="80" height="80"/>
                <h3>{away}</h3>
            </div>
            </div>
        </div>
    <h3>Match Info</h3>
    <ul>
        <li><strong>League:</strong> {league_name} - {round_name}</li>
        <li><strong>Date:</strong> {date_iso}</li>
        <li><strong>Venue:</strong> {venue}</li>
    </ul>
    """

    # 4. PREPARE PAYLOAD
    payload = {
        "title": f"{home} vs {away} - Live Updates",
        "slug": slug,
        "status": "publish",
        "comment_status": "closed",
        "content": html_content,
        "meta": {
            "match_id": match_id,
        }
    }

    # 5. PUSH TO WORDPRESS
    existing_id = get_post_id_by_slug(slug)
    if existing_id:
        print(f"Updating: {home} vs {away} (ID: {existing_id})")
        wp_request("POST", f"/posts/{existing_id}", json=payload)
    else:
        print(f"Creating: {home} vs {away}")
        wp_request("POST", "/posts", json=payload)

# =====================================================
# MAIN LOOP
# =====================================================
def main():
    print("Starting freshness run...")
    print_env_status()
    assert_auth_config()
    test_wp_auth()

    fixtures = get_fixtures()
    print(f"Fetched {len(fixtures)} total fixtures.")

    processed_count = 0
    
    # Filter Logic: Prioritize Top Leagues
    # 1. First, try to find matches in Priority Leagues
    priority_matches = [m for m in fixtures if m["league"]["id"] in PRIORITY_LEAGUES]
    
    # 2. If we have priority matches, use them. If not, fallback to the first 5 of any list.
    target_matches = priority_matches if priority_matches else fixtures

    print(f"Processing {min(5, len(target_matches))} matches...")

    for match in target_matches[:5]:
        try:
            create_or_update_post(match)
            processed_count += 1
        except Exception as e:
            print(f"Error processing match: {e}")

    print(f"Run complete. Processed {processed_count} posts.")

if __name__ == "__main__":
    main()
