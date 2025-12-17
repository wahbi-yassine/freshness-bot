import os
import requests
import base64
import time
from datetime import datetime, timezone

# =====================================================
# 1. CONFIGURATION & AUTHENTICATION
# =====================================================

# WordPress Config (From GitHub Secrets)
WP_BASE = os.environ["WP_URL"].rstrip("/")
WP_API = WP_BASE + "/wp-json/wp/v2"
WP_USER = os.environ.get("WP_USER", "").strip()
WP_APP_PASSWORD = os.environ.get("WP_APP_PASSWORD", "").strip()

# API-Football Config (From GitHub Secrets)
FOOTBALL_API_KEY = os.environ.get("FOOTBALL_API_KEY", "").strip()
FOOTBALL_API_URL = "https://v3.football.api-sports.io/fixtures"

# LEAGUE FILTERS: Add the IDs of leagues you want to publish.
# 39=Premier League, 140=La Liga, 135=Serie A, 78=Bundesliga, 61=Ligue 1, 2=UCL, 200=Botola Pro
PRIORITY_LEAGUES = [39, 140, 135, 78, 61, 2, 200]

# Setup Requests Session
SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "freshness-bot/5.0",
    "Accept": "application/json",
})

# =====================================================
# 2. HELPER FUNCTIONS (Auth & Checks)
# =====================================================

def print_env_status():
    """Prints status of secrets (True/False) without revealing them."""
    print("ENV CHECK:")
    print(" - WP_URL:", bool(WP_BASE))
    print(" - WP_USER:", bool(WP_USER))
    print(" - WP_APP_PASSWORD:", bool(WP_APP_PASSWORD))
    print(" - FOOTBALL_API_KEY:", bool(FOOTBALL_API_KEY))

def assert_auth_config():
    """Stops the script if secrets are missing."""
    if not (WP_USER and WP_APP_PASSWORD):
        raise RuntimeError("Missing WordPress auth. Check GitHub Secrets.")

def basic_auth_header(user: str, app_pw: str) -> str:
    """Generates the Basic Auth header for WordPress."""
    # Remove spaces that WordPress sometimes adds to app passwords
    app_pw = app_pw.replace(" ", "")
    token = base64.b64encode(f"{user}:{app_pw}".encode("utf-8")).decode("utf-8")
    return f"Basic {token}"

def wp_headers():
    return {
        "Authorization": basic_auth_header(WP_USER, WP_APP_PASSWORD),
        "Content-Type": "application/json",
    }

def wp_request(method: str, path: str, *, params=None, json=None, timeout=30):
    """Handles all requests to WordPress with retries and error checking."""
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
            
            # Retry on server errors
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(2)
                continue
                
            # Log Auth Errors specifically
            if r.status_code in (401, 403):
                print(f"Auth Error ({r.status_code}): {r.text[:200]}")
            
            r.raise_for_status()
            return r
            
        except requests.RequestException as e:
            if attempt == 2: raise
            time.sleep(2)

def test_wp_auth():
    """Verifies connection before doing real work."""
    r = wp_request("GET", "/users/me")
    print(f"WP Auth OK: Connected as '{r.json().get('name')}'")

# =====================================================
# 3. GET DATA (API-Football)
# =====================================================

def get_fixtures():
    """Fetches today's matches from API-Football."""
    if not FOOTBALL_API_KEY:
        raise RuntimeError("Missing FOOTBALL_API_KEY")

    headers = {"x-apisports-key": FOOTBALL_API_KEY}
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    r = requests.get(
        FOOTBALL_API_URL,
        headers=headers,
        params={"date": today},
        timeout=30,
    )
    r.raise_for_status()
    return r.json().get("response", [])

# =====================================================
# 4. CREATE / UPDATE POSTS
# =====================================================

def get_post_id_by_slug(slug: str):
    """Checks if a post already exists by slug."""
    r = wp_request("GET", "/posts", params={"slug": slug})
    posts = r.json()
    return posts[0]["id"] if posts else None

def create_or_update_post(match):
    """Generates HTML, Schema, and sends to WordPress."""
    match_id = match["fixture"]["id"]
    slug = f"match-{match_id}"

    # --- A. DATA EXTRACTION ---
    home = match["teams"]["home"]["name"]
    away = match["teams"]["away"]["name"]
    home_logo = match["teams"]["home"]["logo"]
    away_logo = match["teams"]["away"]["logo"]
    
    # Handle missing venue
    venue_data = match.get("fixture", {}).get("venue", {})
    venue = venue_data.get("name") if venue_data.get("name") else "Stadium TBD"
    
    date_iso = match["fixture"]["date"]
    status_long = match["fixture"]["status"]["long"]
    league_name = match["league"]["name"]
    round_name = match["league"]["round"]

    # --- B. SEO SCHEMA (HIDDEN) ---
    # This block uses to keep the JSON code invisible to visitors
    schema_block = f"""
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

    # --- C. VISUAL CONTENT (WordPress Blocks) ---
    visual_block = f"""
    <h2 class="wp-block-heading has-text-align-center">{home} vs {away}</h2>
    <div class="wp-block-columns is-vertically-aligned-center has-background" style="background-color:#f7f7f7;padding-top:20px;padding-bottom:20px">
        
        <div class="wp-block-column is-vertically-aligned-center" style="flex-basis:33%">
            <figure class="wp-block-image aligncenter size-full is-resized"><img src="{home_logo}" alt="{home} Logo" width="80" height="80"/></figure>
            <p class="has-text-align-center" style="font-style:normal;font-weight:700">{home}</p>
            </div>
        <div class="wp-block-column is-vertically-aligned-center" style="flex-basis:33%">
            <p class="has-text-align-center" style="font-size:24px;font-weight:800">VS</p>
            <p class="has-text-align-center has-vivid-red-color has-text-color">{status_long}</p>
            </div>
        <div class="wp-block-column is-vertically-aligned-center" style="flex-basis:33%">
            <figure class="wp-block-image aligncenter size-full is-resized"><img src="{away_logo}" alt="{away} Logo" width="80" height="80"/></figure>
            <p class="has-text-align-center" style="font-weight:700">{away}</p>
            </div>
        </div>
    <hr class="wp-block-separator has-alpha-channel-opacity"/>
    <div class="wp-block-group">
        <h3 class="wp-block-heading">Match Details</h3>
        <ul>
            <li><strong>🏆 League:</strong> {league_name} ({round_name})</li>
            <li><strong>📅 Date:</strong> {date_iso}</li>
            <li><strong>🏟️ Stadium:</strong> {venue}</li>
        </ul>
        </div>
    """

    # Combine blocks
    full_content = schema_block + visual_block

    payload = {
        "title": f"{home} vs {away} - Live Updates",
        "slug": slug,
        "status": "publish",
        "comment_status": "closed",
        "content": full_content,
        "meta": {
            "match_id": match_id,
        }
    }

    # --- D. API PUSH ---
    existing_id = get_post_id_by_slug(slug)
    if existing_id:
        print(f"Updating: {home} vs {away} (ID: {existing_id})")
        wp_request("POST", f"/posts/{existing_id}", json=payload)
    else:
        print(f"Creating: {home} vs {away}")
        wp_request("POST", "/posts", json=payload)

# =====================================================
# 5. MAIN EXECUTION FLOW
# =====================================================

def main():
    print("--- STARTING FRESHNESS BOT ---")
    print_env_status()
    assert_auth_config()
    test_wp_auth()

    # 1. Fetch
    fixtures = get_fixtures()
    print(f"Fetched {len(fixtures)} total fixtures for today.")

    # 2. Filter (Prioritize Leagues)
    priority_matches = [m for m in fixtures if m["league"]["id"] in PRIORITY_LEAGUES]
    
    # If no priority matches found, take top 5 of *anything* to keep site fresh
    if priority_matches:
        target_matches = priority_matches
        print(f"Found {len(target_matches)} priority matches.")
    else:
        target_matches = fixtures
        print("No priority matches found. Using general fixtures.")

    # 3. Publish (Limit to 5 to avoid timeouts/limits)
    limit = 5
    processed = 0
    
    print(f"Processing up to {limit} matches...")
    
    for match in target_matches[:limit]:
        try:
            create_or_update_post(match)
            processed += 1
        except Exception as e:
            print(f"Skipped match due to error: {e}")

    print(f"--- RUN COMPLETE: {processed} posts processed ---")

if __name__ == "__main__":
    main()
