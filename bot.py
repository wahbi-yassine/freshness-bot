import os
import requests
import base64
import time
import json
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

# LEAGUE FILTERS
# 39=Premier League, 140=La Liga, 135=Serie A, 78=Bundesliga, 61=Ligue 1, 2=UCL, 200=Botola Pro
PRIORITY_LEAGUES = [39, 140, 135, 78, 61, 2, 200]

# SEO CONFIGURATION
# 1. Keywords for VISIBLE text rotation (Pick 1 per post based on Match ID)
VISIBLE_KEYWORDS = ["yacine tv", "yacines tv", "yasin tv", "ياسين تيفي"]

# 2. Keywords for SCHEMA (WebPage node only - Safe to include multiple variants)
SCHEMA_KEYWORDS = [
    "yacine tv", "yacines tv", "yasin tv", "ياسين تيفي", 
    "live score", "football match", "koora live", "match today"
]

# 3. Your Flagship Page Slug (Where you want to send traffic)
FLAGSHIP_SLUG = "yacine-tv-online"

# 4. The Slug for your "Matches Today" Hub Page
HUB_SLUG = "matches-today"

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "freshness-bot/8.0",
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
    clean_pw = WP_APP_PASSWORD.replace(" ", "")
    token = base64.b64encode(f"{WP_USER}:{clean_pw}".encode("utf-8")).decode("utf-8")
    return {
        "Authorization": f"Basic {token}",
        "Content-Type": "application/json",
    }

def wp_request(method, path, **kwargs):
    # Fix for /pages endpoint usage later
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
        print(f"Connected as: {data.get('name')}")

# =====================================================
# 3. CORE FUNCTIONS (FETCH & LOOKUP)
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

def get_post_id_by_slug(slug, post_type="posts"):
    # post_type can be 'posts' or 'pages'
    r = wp_request("GET", f"/{post_type}", params={"slug": slug})
    if r:
        data = r.json()
        return data[0]["id"] if data else None
    return None

# =====================================================
# 4. MATCH POST CREATION (LEAF PAGES)
# =====================================================
def create_or_update_post(match):
    match_id = match["fixture"]["id"]
    slug = f"match-{match_id}"
    post_url = f"{WP_BASE}/{slug}/" # Canonical URL for Schema

    # --- A. DATA EXTRACTION ---
    home = match["teams"]["home"]["name"]
    away = match["teams"]["away"]["name"]
    home_logo = match["teams"]["home"]["logo"]
    away_logo = match["teams"]["away"]["logo"]
    venue = match.get("fixture", {}).get("venue", {}).get("name") or "Stadium TBD"
    
    date_iso = match["fixture"]["date"]
    try:
        dt_obj = datetime.fromisoformat(date_iso.replace("Z", "+00:00"))
        date_human = dt_obj.strftime("%d %b %Y") 
        time_human = dt_obj.strftime("%H:%M")     
    except:
        date_human = date_iso
        time_human = ""

    status = match["fixture"]["status"]["long"]
    league = match["league"]["name"]

    # --- B. SEO KEYWORD SELECTION (Deterministic) ---
    kw_index = match_id % len(VISIBLE_KEYWORDS)
    target_keyword = VISIBLE_KEYWORDS[kw_index]
    flagship_url = f"{WP_BASE}/{FLAGSHIP_SLUG}/"

    # --- C. SCHEMA: THE KNOWLEDGE GRAPH (@graph) ---
    # Node 1: WebPage
    webpage_node = {
        "@type": "WebPage",
        "@id": f"{post_url}#webpage",
        "url": post_url,
        "name": f"{home} vs {away} - Live Score & Updates",
        "inLanguage": "en-US",
        "keywords": SCHEMA_KEYWORDS
    }

    # Node 2: SportsEvent
    event_node = {
        "@type": "SportsEvent",
        "@id": f"{post_url}#event",
        "mainEntityOfPage": {"@id": f"{post_url}#webpage"},
        "name": f"{home} vs {away}",
        "startDate": date_iso,
        "eventStatus": "https://schema.org/EventScheduled",
        "competitor": [
            {"@type": "SportsTeam", "name": home, "logo": home_logo},
            {"@type": "SportsTeam", "name": away, "logo": away_logo}
        ],
        "location": {"@type": "Place", "name": venue}
    }

    graph_data = {
        "@context": "https://schema.org",
        "@graph": [webpage_node, event_node]
    }
    
    schema_str = json.dumps(graph_data)
    schema_block = f'<script type="application/ld+json">{schema_str}</script>'

    # --- D. VISUAL CARD (Premium Design) ---
    visual_block = f"""
    <div class="wp-block-group has-white-background-color has-background" style="border-radius:12px;box-shadow:0px 10px 30px rgba(0,0,0,0.08);padding-top:0;padding-right:0;padding-bottom:0;padding-left:0">
        
        <div class="wp-block-group has-white-background-color has-background" style="padding-top:40px;padding-right:20px;padding-bottom:40px;padding-left:20px">
            <div class="wp-block-columns is-vertically-aligned-center">
                
                <div class="wp-block-column" style="flex-basis:35%;text-align:center;">
                    <img src="{home_logo}" alt="{home}" width="90" height="90" style="display:block;margin:0 auto 15px auto;filter:drop-shadow(0 4px 6px rgba(0,0,0,0.1));"/>
                    <p style="margin:0;font-weight:800;font-size:16px;line-height:1.2;color:#222;">{home}</p>
                </div>
                <div class="wp-block-column" style="flex-basis:30%;text-align:center;">
                    <p style="font-size:13px;color:#888;margin-bottom:8px;font-weight:600;">{date_human}</p>
                    <h2 style="margin:0 0 10px 0;font-size:36px;font-weight:900;color:#111;line-height:1;">VS</h2>
                    <div style="display:inline-block;background:#d63638;color:#fff;padding:6px 16px;border-radius:50px;font-size:12px;font-weight:bold;text-transform:uppercase;letter-spacing:0.5px;box-shadow:0 4px 10px rgba(214, 54, 56, 0.3);">
                        {status}
                    </div>
                </div>
                <div class="wp-block-column" style="flex-basis:35%;text-align:center;">
                    <img src="{away_logo}" alt="{away}" width="90" height="90" style="display:block;margin:0 auto 15px auto;filter:drop-shadow(0 4px 6px rgba(0,0,0,0.1));"/>
                    <p style="margin:0;font-weight:800;font-size:16px;line-height:1.2;color:#222;">{away}</p>
                </div>
                </div>
            </div>
        <hr class="wp-block-separator alignwide is-style-wide" style="margin:0;border-bottom:1px solid #f1f1f1;"/>
        <div class="wp-block-group has-luminous-vivid-amber-background-color has-background" style="background-color:#fafafa;padding-top:25px;padding-right:20px;padding-bottom:25px;padding-left:20px">
            <div class="wp-block-columns">
                <div class="wp-block-column" style="text-align:center;margin-bottom:10px;">
                    <p style="font-size:11px;color:#999;margin-bottom:5px;font-weight:700;">LEAGUE</p>
                    <p style="font-size:14px;color:#333;margin:0;font-weight:600;">🏆 {league}</p>
                </div>
                <div class="wp-block-column" style="text-align:center;margin-bottom:10px;">
                    <p style="font-size:11px;color:#999;margin-bottom:5px;font-weight:700;">TIME</p>
                    <p style="font-size:14px;color:#333;margin:0;font-weight:600;">⏰ {time_human} UTC</p>
                </div>
                <div class="wp-block-column" style="text-align:center;margin-bottom:10px;">
                     <p style="font-size:11px;color:#999;margin-bottom:5px;font-weight:700;">VENUE</p>
                     <p style="font-size:14px;color:#333;margin:0;font-weight:600;">🏟️ {venue}</p>
                </div>
            </div>
        </div>
        </div>
    """

    # --- E. SEO SNIPPET (Visible - "How to Watch") ---
    seo_snippet = f"""
    <div style="height:30px" aria-hidden="true" class="wp-block-spacer"></div>
    <div class="wp-block-group has-white-background-color has-background" style="border:1px solid #e0e0e0;border-radius:8px;padding-top:20px;padding-right:20px;padding-bottom:20px;padding-left:20px">
        <h4 class="wp-block-heading" style="margin-top:0;">📺 Official Viewing Guide</h4>
        <p class="has-small-font-size" style="color:#555;">
            Searching for <strong>{target_keyword}</strong> to watch the match? 
            We support legal streaming options in Morocco. 
            View our full guide on <a href="{flagship_url}" style="color:#d63638;text-decoration:underline;font-weight:bold;">how to watch officially</a>.
        </p>
        </div>
    """

    # Combine All
    full_content = schema_block + visual_block + seo_snippet

    payload = {
        "title": f"{home} vs {away} - Live Updates",
        "slug": slug,
        "status": "publish",
        "content": full_content,
        "meta": {"match_id": match_id}
    }

    # SEND
    existing_id = get_post_id_by_slug(slug, "posts")
    if existing_id:
        print(f"Updating Match: {home} vs {away}")
        wp_request("POST", f"/posts/{existing_id}", json=payload)
    else:
        print(f"Creating Match: {home} vs {away}")
        wp_request("POST", "/posts", json=payload)

# =====================================================
# 5. HUB PAGE UPDATE (TRUNK PAGE)
# =====================================================
def update_hub_page(matches):
    """Updates a single 'Matches Today' page with a schedule table."""
    
    # 1. Build Table HTML
    list_html = """
    <h2 class="wp-block-heading has-text-align-center">📅 Today's Match Schedule</h2>
    <figure class="wp-block-table is-style-stripes has-small-font-size"><table>
    <thead><tr>
        <th>Time</th>
        <th>Match</th>
        <th>League</th>
        <th>Status</th>
    </tr></thead>
    <tbody>
    """
    
    count = 0
    for match in matches:
        match_id = match["fixture"]["id"]
        slug = f"match-{match_id}"
        post_link = f"{WP_BASE}/{slug}/"
        
        home = match["teams"]["home"]["name"]
        away = match["teams"]["away"]["name"]
        league = match["league"]["name"]
        status_short = match["fixture"]["status"]["short"]
        
        date_iso = match["fixture"]["date"]
        try:
            dt_obj = datetime.fromisoformat(date_iso.replace("Z", "+00:00"))
            time_str = dt_obj.strftime("%H:%M")
        except:
            time_str = "TBD"

        # Table Row
        list_html += f"""
        <tr>
            <td><strong>{time_str}</strong></td>
            <td><a href="{post_link}">{home} vs {away}</a></td>
            <td>{league}</td>
            <td>{status_short}</td>
        </tr>
        """
        count += 1
    
    list_html += "</tbody></table></figure>"

    # 2. Add Hub SEO Content
    seo_text = f"""
    <p>Watch all the top football matches for today. 
    We cover the Premier League, La Liga, and Botola Pro. 
    Follow <strong>Yacine TV</strong> live scores and updates for every game listed above. 
    Click any match in the table to see the full legal viewing guide and minute-by-minute updates.</p>
    """
    
    full_content = list_html + seo_text

    if count == 0:
        print("No matches to list on Hub.")
        return

    # 3. Update the Page
    payload = {
        "title": f"Matches Today ({datetime.now().strftime('%d %b')}) - Live Schedule",
        "slug": HUB_SLUG,
        "status": "publish",
        "content": full_content
    }

    # Check for PAGE (not post)
    existing_id = get_post_id_by_slug(HUB_SLUG, "pages")
    if existing_id:
        print(f"Updating Hub Page: {HUB_SLUG}")
        wp_request("POST", f"/pages/{existing_id}", json=payload)
    else:
        print(f"Creating Hub Page: {HUB_SLUG}")
        wp_request("POST", "/pages", json=payload)

# =====================================================
# 6. MAIN RUNNER
# =====================================================
def main():
    print("--- STARTING BOT (FINAL PHASE) ---")
    print_env_status()
    assert_auth_config()
    test_wp_auth()

    all_fixtures = get_fixtures()
    
    # Filter
    priority_matches = [m for m in all_fixtures if m["league"]["id"] in PRIORITY_LEAGUES]
    
    # 1. Update Matches
    if not priority_matches:
        print("No priority matches found. Updating Hub only.")
    else:
        print(f"Updating {len(priority_matches)} match pages...")
        for match in priority_matches:
            try:
                create_or_update_post(match)
            except Exception as e:
                print(f"Error on match {match['fixture']['id']}: {e}")

    # 2. Update Hub
    if priority_matches:
        update_hub_page(priority_matches)

    print("--- RUN COMPLETE ---")

if __name__ == "__main__":
    main()
