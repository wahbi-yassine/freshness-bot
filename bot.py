import os
import requests
import base64
import time
from datetime import datetime, timezone

# =====================================================
# 1. CONFIGURATION
# =====================================================
WP_BASE = os.environ["WP_URL"].rstrip("/")
WP_API = WP_BASE + "/wp-json/wp/v2"
WP_USER = os.environ.get("WP_USER", "").strip()
WP_APP_PASSWORD = os.environ.get("WP_APP_PASSWORD", "").strip()
FOOTBALL_API_KEY = os.environ.get("FOOTBALL_API_KEY", "").strip()
FOOTBALL_API_URL = "https://v3.football.api-sports.io/fixtures"

# League IDs (Optional Filter)
PRIORITY_LEAGUES = [39, 140, 135, 78, 61, 2, 200]

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "freshness-bot/5.0",
    "Accept": "application/json",
})

# =====================================================
# 2. AUTH HELPERS
# =====================================================
def print_env_status():
    print("ENV CHECK:")
    print(" - WP_URL:", bool(WP_BASE))
    print(" - WP_USER:", bool(WP_USER))
    print(" - FOOTBALL_API_KEY:", bool(FOOTBALL_API_KEY))

def assert_auth_config():
    if not (WP_USER and WP_APP_PASSWORD):
        raise RuntimeError("Missing WordPress auth secrets.")

def wp_headers():
    # Remove spaces from app password if present
    clean_pw = WP_APP_PASSWORD.replace(" ", "")
    token = base64.b64encode(f"{WP_USER}:{clean_pw}".encode("utf-8")).decode("utf-8")
    return {
        "Authorization": f"Basic {token}",
        "Content-Type": "application/json",
    }

def wp_request(method, path, **kwargs):
    url = f"{WP_API}/{path.lstrip('/')}"
    for attempt in range(3):
        try:
            r = SESSION.request(method, url, headers=wp_headers(), **kwargs)
            if r.status_code in (401, 403):
                print(f"Auth Error ({r.status_code}): Check User Role is Administrator!")
            r.raise_for_status()
            return r
        except Exception as e:
            if attempt == 2: print(f"Request Failed: {e}")
            time.sleep(2)

def test_wp_auth():
    r = wp_request("GET", "/users/me")
    if r:
        data = r.json()
        print(f"Connected as: {data.get('name')} (Role: {data.get('roles', ['Unknown'])[0]})")

# =====================================================
# 3. CORE FUNCTIONS
# =====================================================
def get_fixtures():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    r = requests.get(
        FOOTBALL_API_URL, 
        headers={"x-apisports-key": FOOTBALL_API_KEY}, 
        params={"date": today}
    )
    r.raise_for_status()
    return r.json().get("response", [])

def get_post_id_by_slug(slug):
    r = wp_request("GET", "/posts", params={"slug": slug})
    if r:
        posts = r.json()
        return posts[0]["id"] if posts else None
    return None

def create_or_update_post(match):
    match_id = match["fixture"]["id"]
    slug = f"match-{match_id}"

    # DATA
    home = match["teams"]["home"]["name"]
    away = match["teams"]["away"]["name"]
    home_logo = match["teams"]["home"]["logo"]
    away_logo = match["teams"]["away"]["logo"]
    venue = match.get("fixture", {}).get("venue", {}).get("name") or "Stadium TBD"
    date = match["fixture"]["date"]
    status = match["fixture"]["status"]["long"]
    league = match["league"]["name"]

    # --- BLOCK 1: HIDDEN SEO SCHEMA ---
    # We minify it to one line to prevent formatting issues
    schema_json = (
        f'{{"@context":"https://schema.org","@type":"SportsEvent",'
        f'"name":"{home} vs {away}","startDate":"{date}",'
        f'"eventStatus":"https://schema.org/EventScheduled",'
        f'"competitor":[{{"@type":"SportsTeam","name":"{home}","logo":"{home_logo}"}},'
        f'{{"@type":"SportsTeam","name":"{away}","logo":"{away_logo}"}}],'
        f'"location":{{"@type":"Place","name":"{venue}"}}}}'
    )
    
    # HTML Block containing the script
    # IMPORTANT: The user MUST be Administrator for this <script> to work
    schema_block = f"""<script type="application/ld+json">{schema_json}</script>"""

    # --- BLOCK 2: VISUAL HEADER (NO CODE VISIBLE) ---
    visual_block = f"""
    <div class="wp-block-group has-cyan-bluish-gray-background-color has-background" style="padding-top:20px;padding-bottom:20px">
        <div class="wp-block-columns is-vertically-aligned-center">
            
            <div class="wp-block-column" style="flex-basis:40%;text-align:center;">
                <img src="{home_logo}" alt="{home}" width="80" height="80" style="display:block;margin:0 auto;"/>
                <p style="margin-top:10px;font-weight:bold;">{home}</p>
            </div>
            <div class="wp-block-column" style="flex-basis:20%;text-align:center;">
                <h2 style="margin:0;font-size:24px;color:#333;">VS</h2>
                <p style="font-size:12px;color:#d63638;">{status}</p>
            </div>
            <div class="wp-block-column" style="flex-basis:40%;text-align:center;">
                <img src="{away_logo}" alt="{away}" width="80" height="80" style="display:block;margin:0 auto;"/>
                <p style="margin-top:10px;font-weight:bold;">{away}</p>
            </div>
            </div>
        </div>
    <h3>Match Details</h3>
    <ul>
        <li><strong>🏆 Competition:</strong> {league}</li>
        <li><strong>📅 Date:</strong> {date}</li>
        <li><strong>🏟️ Venue:</strong> {venue}</li>
    </ul>
    """

    content = schema_block + visual_block

    payload = {
        "title": f"{home} vs {away} - Live Updates",
        "slug": slug,
        "status": "publish",
        "content": content,
        "meta": {"match_id": match_id}
    }

    # SEND
    existing_id = get_post_id_by_slug(slug)
    if existing_id:
        print(f"Updating: {home} vs {away}")
        wp_request("POST", f"/posts/{existing_id}", json=payload)
    else:
        print(f"Creating: {home} vs {away}")
        wp_request("POST", "/posts", json=payload)

# =====================================================
# 4. RUNNER
# =====================================================
def main():
    print("--- STARTING BOT ---")
    print_env_status()
    assert_auth_config()
    test_wp_auth()

    all_fixtures = get_fixtures()
    
    # Filter
    matches = [m for m in all_fixtures if m["league"]["id"] in PRIORITY_LEAGUES]
    if not matches: matches = all_fixtures[:5]

    print(f"Processing {min(5, len(matches))} matches...")
    for match in matches[:5]:
        try:
            create_or_update_post(match)
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    main()
