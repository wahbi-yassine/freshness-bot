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

# LEAGUE FILTERS (IDs work regardless of language)
# 39=Premier League, 140=La Liga, 135=Serie A, 78=Bundesliga, 61=Ligue 1, 2=UCL, 200=Botola Pro
PRIORITY_LEAGUES = [39, 140, 135, 78, 61, 2, 200]

# SEO & PAGE CONFIG
VISIBLE_KEYWORDS = ["yacine tv", "yacines tv", "yasin tv", "ياسين تيفي"]
FLAGSHIP_SLUG = "yacine-tv-online"
HUB_SLUG = "matches-today" # This will contain your new App Component

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "freshness-bot/9.0",
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
# 3. CORE FUNCTIONS (Now Fetching in ARABIC)
# =====================================================
def get_fixtures():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    # We add lang="ar" to get Arabic names for your UI
    params = {
        "date": today,
        "timezone": "Africa/Casablanca", # Match your UI default
        "lang": "ar" 
    }
    r = requests.get(
        FOOTBALL_API_URL, 
        headers={"x-apisports-key": FOOTBALL_API_KEY}, 
        params=params
    )
    r.raise_for_status()
    return r.json().get("response", [])

def get_post_id_by_slug(slug, post_type="posts"):
    r = wp_request("GET", f"/{post_type}", params={"slug": slug})
    if r:
        data = r.json()
        return data[0]["id"] if data else None
    return None

# =====================================================
# 4. MATCH POST CREATION (Individual Pages)
# =====================================================
def create_or_update_post(match):
    match_id = match["fixture"]["id"]
    slug = f"match-{match_id}"
    post_url = f"{WP_BASE}/{slug}/"

    home = match["teams"]["home"]["name"]
    away = match["teams"]["away"]["name"]
    home_logo = match["teams"]["home"]["logo"]
    away_logo = match["teams"]["away"]["logo"]
    venue = match.get("fixture", {}).get("venue", {}).get("name") or "ملعب غير محدد"
    
    date_iso = match["fixture"]["date"]
    # Time is already in Casablanca/Morocco time because of API param
    status = match["fixture"]["status"]["long"]
    league = match["league"]["name"]

    # SEO Rotation
    kw_index = match_id % len(VISIBLE_KEYWORDS)
    target_keyword = VISIBLE_KEYWORDS[kw_index]
    flagship_url = f"{WP_BASE}/{FLAGSHIP_SLUG}/"

    # Schema (@graph)
    webpage_node = {
        "@type": "WebPage",
        "@id": f"{post_url}#webpage",
        "url": post_url,
        "name": f"{home} ضد {away} - نتيجة مباشرة",
        "inLanguage": "ar",
        "keywords": ["yacine tv", "koora live", "مباريات اليوم", target_keyword]
    }

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

    graph_data = {"@context": "https://schema.org", "@graph": [webpage_node, event_node]}
    schema_str = json.dumps(graph_data)
    schema_block = f'<script type="application/ld+json">{schema_str}</script>'

    # Visual Card (Arabic Optimized)
    visual_block = f"""
    <div class="wp-block-group has-white-background-color has-background" style="border-radius:12px;box-shadow:0px 10px 30px rgba(0,0,0,0.08);padding:0;" dir="rtl">
        <div style="padding:40px 20px; text-align:center;">
            <div style="display:flex; align-items:center; justify-content:space-between;">
                <div style="width:35%;">
                    <img src="{home_logo}" width="80" height="80" style="display:block;margin:0 auto 10px;"/>
                    <h3 style="margin:0;font-size:16px;">{home}</h3>
                </div>
                <div style="width:30%;">
                    <span style="background:#d63638;color:#fff;padding:5px 15px;border-radius:20px;font-size:12px;">{status}</span>
                </div>
                <div style="width:35%;">
                    <img src="{away_logo}" width="80" height="80" style="display:block;margin:0 auto 10px;"/>
                    <h3 style="margin:0;font-size:16px;">{away}</h3>
                </div>
            </div>
        </div>
    </div>
    """
    
    # SEO Text
    seo_snippet = f"""
    <p style="text-align:center; margin-top:20px;">
        هل تبحث عن <strong>{target_keyword}</strong> لمشاهدة المباراة؟ 
        شاهد الدليل الرسمي <a href="{flagship_url}">من هنا</a>.
    </p>
    """

    payload = {
        "title": f"{home} ضد {away}",
        "slug": slug,
        "status": "publish",
        "content": schema_block + visual_block + seo_snippet,
        "meta": {"match_id": match_id}
    }

    if existing_id := get_post_id_by_slug(slug, "posts"):
        print(f"Updating Match: {home} vs {away}")
        wp_request("POST", f"/posts/{existing_id}", json=payload)
    else:
        print(f"Creating Match: {home} vs {away}")
        wp_request("POST", "/posts", json=payload)

# =====================================================
# 5. HUB PAGE UPDATE (Your Custom HTML/JS App)
# =====================================================
def update_hub_page(matches):
    """
    Generates the 'Matches Today' page using YOUR custom HTML/JS/CSS.
    Injects real API data into the JSON block.
    """
    
    # 1. PROCESS MATCHES INTO APP FORMAT
    # We need to group matches by League to match your JSON structure
    leagues_map = {}
    
    for m in matches:
        league_name = m["league"]["name"]
        league_logo = m["league"]["logo"]
        
        if league_name not in leagues_map:
            leagues_map[league_name] = {
                "league": league_name,
                "leagueLogo": league_logo,
                "matches": []
            }
        
        # Map API status to your App's simple status
        # API: NS, FT, LIVE, HT -> App: scheduled, live, finished
        short_status = m["fixture"]["status"]["short"]
        app_status = "scheduled"
        if short_status in ["FT", "AET", "PEN"]: app_status = "finished"
        elif short_status in ["1H", "HT", "2H", "ET", "P", "LIVE"]: app_status = "live"
        
        score_display = None
        if m["goals"]["home"] is not None:
            score_display = f"{m['goals']['home']} - {m['goals']['away']}"

        leagues_map[league_name]["matches"].append({
            "home": m["teams"]["home"]["name"],
            "homeLogo": m["teams"]["home"]["logo"],
            "away": m["teams"]["away"]["name"],
            "awayLogo": m["teams"]["away"]["logo"],
            "time": m["fixture"]["date"], # ISO format works with your JS
            "status": app_status,
            "score": score_display
        })

    # Convert to list for JSON injection
    app_data_json = json.dumps(list(leagues_map.values()), ensure_ascii=False)

    # 2. THE HTML TEMPLATE (Split to allow injection)
    # We use raw strings r"""...""" to avoid escaping issues, but we must split
    # around the JSON block to inject our data safely.
    
    html_top = r"""<div id="ys-matches-app" class="ys-wrapper" dir="rtl">
  <div class="ys-controls">
    <div class="ys-tabs">
      <a href="/matches-yesterday/" class="ys-tab" data-day="yesterday">الأمس</a>
      <a href="#" class="ys-tab active" data-day="today">اليوم</a>
      <a href="/matches-tomorrow/" class="ys-tab" data-day="tomorrow">الغد</a>
    </div>
    <div class="ys-filters">
      <div class="ys-search-group">
        <input type="text" id="ysSearch" placeholder="ابحث عن فريق..." aria-label="بحث عن مباراة">
        <svg class="ys-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path>
        </svg>
      </div>
      <div class="ys-select-group">
        <select id="ysLeagueSelect" aria-label="اختر البطولة"><option value="all">كل البطولات</option></select>
      </div>
      <div class="ys-timezone-group">
        <select id="ysTimezone" aria-label="توقيت العرض">
          <option value="Africa/Casablanca">الدار البيضاء (GMT+1)</option>
          <option value="Africa/Cairo">القاهرة (GMT+2)</option>
          <option value="Asia/Riyadh">مكة المكرمة (GMT+3)</option>
          <option value="local">توقيت جهازي</option>
        </select>
      </div>
    </div>
  </div>

  <div id="ys-matches-container" class="ys-matches-list">
    <div class="ys-loading">جاري تحميل المباريات...</div>
  </div>

  <div class="ys-footer">
    <p>⚠️ <strong>تنويه:</strong> التوقيت الافتراضي هو توقيت المغرب.</p>
  </div>
</div>

<script type="application/json" id="ys-matches-data">
"""

    html_bottom = r"""
</script>

<style>
  :root { --ys-primary: #e60023; --ys-dark: #1a1a1a; --ys-gray: #f4f6f8; --ys-text: #333; --ys-border: #e1e4e8; --ys-radius: 12px; --ys-font: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; }
  .ys-wrapper { font-family: var(--ys-font); max-width: 100%; margin: 0 auto; color: var(--ys-text); }
  .ys-wrapper * { box-sizing: border-box; }
  .ys-tabs { display: flex; justify-content: center; gap: 1rem; margin-bottom: 1.5rem; background: #fff; padding: 0.5rem; border-radius: var(--ys-radius); box-shadow: 0 2px 8px rgba(0,0,0,0.05); }
  .ys-tab { text-decoration: none; padding: 0.5rem 1.5rem; border-radius: 8px; color: #666; font-weight: 600; }
  .ys-tab.active, .ys-tab:hover { background: var(--ys-primary); color: #fff; }
  .ys-filters { display: flex; flex-wrap: wrap; gap: 1rem; margin-bottom: 2rem; }
  .ys-search-group, .ys-select-group, .ys-timezone-group { flex: 1; min-width: 200px; position: relative; }
  .ys-search-group input, .ys-filters select { width: 100%; padding: 0.75rem 1rem; border: 1px solid var(--ys-border); border-radius: 8px; background: #fff; }
  .ys-wrapper[dir="rtl"] .ys-search-group input { padding-left: 1rem; padding-right: 2.5rem; }
  .ys-icon { position: absolute; top: 50%; transform: translateY(-50%); width: 1.2rem; height: 1.2rem; color: #999; right: 0.8rem; }
  .ys-league-block { background: #fff; border-radius: var(--ys-radius); margin-bottom: 1.5rem; border: 1px solid var(--ys-border); }
  .ys-league-header { background: #f8f9fa; padding: 0.8rem 1rem; display: flex; align-items: center; gap: 0.8rem; border-bottom: 1px solid var(--ys-border); }
  .ys-league-icon { width: 24px; height: 24px; object-fit: contain; }
  .ys-league-name { font-weight: 700; }
  .ys-match-row { display: flex; align-items: center; justify-content: space-between; padding: 1rem; border-bottom: 1px solid #eee; }
  .ys-team { flex: 1; display: flex; align-items: center; gap: 0.8rem; font-weight: 600; }
  .ys-team.home { justify-content: flex-end; }
  .ys-team.away { justify-content: flex-start; }
  .ys-match-center { flex: 0 0 100px; text-align: center; }
  .ys-score { font-size: 1.2rem; font-weight: 800; }
  .ys-time { font-size: 0.9rem; color: #666; direction: ltr; }
  .ys-status { font-size: 0.75rem; padding: 2px 8px; border-radius: 10px; margin-top: 4px; display: inline-block; }
  .ys-status.live { background: #ffebeb; color: #d90000; animation: pulse 2s infinite; }
  .ys-status.finished { background: #eee; }
  .ys-status.scheduled { background: #e6f4ea; color: #1a7f37; }
  @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.6; } 100% { opacity: 1; } }
  @media (max-width: 560px) { .ys-match-row { font-size: 0.9rem; } .ys-team-logo { width: 24px; height: 24px; } }
</style>

<script>
document.addEventListener('DOMContentLoaded', function () {
    const DEFAULT_TIMEZONE = "Africa/Casablanca";
    let allMatches = [];
    try { allMatches = JSON.parse(document.getElementById('ys-matches-data').textContent); } catch (e) {}

    const container = document.getElementById('ys-matches-container');
    const searchInput = document.getElementById('ysSearch');
    const leagueSelect = document.getElementById('ysLeagueSelect');
    const timezoneSelect = document.getElementById('ysTimezone');

    function formatTime(isoString, timeZone) {
        if (!isoString) return '';
        try {
            return new Intl.DateTimeFormat('ar-MA', {
                hour: '2-digit', minute: '2-digit', hour12: false,
                timeZone: timeZone === 'local' ? undefined : timeZone
            }).format(new Date(isoString));
        } catch (e) { return '--:--'; }
    }

    function render() {
        const q = searchInput.value.toLowerCase().trim();
        const sLeague = leagueSelect.value;
        const sTz = timezoneSelect.value || DEFAULT_TIMEZONE;
        let html = '';
        let hasMatches = false;

        allMatches.forEach(ld => {
            if (sLeague !== 'all' && ld.league !== sLeague) return;
            const filtered = ld.matches.filter(m => m.home.toLowerCase().includes(q) || m.away.toLowerCase().includes(q));
            
            if (filtered.length > 0) {
                hasMatches = true;
                html += `<div class="ys-league-block"><div class="ys-league-header"><img src="${ld.leagueLogo}" class="ys-league-icon"><span class="ys-league-name">${ld.league}</span></div><div>`;
                filtered.forEach(m => {
                    const time = formatTime(m.time, sTz);
                    const center = (m.status === 'scheduled') ? `<div class="ys-time">${time}</div>` : `<div class="ys-score">${m.score || '-'}</div>`;
                    const statusLbl = (m.status==='live')?'مباشر':(m.status==='finished')?'انتهت':'قريباً';
                    
                    html += `<div class="ys-match-row">
                        <div class="ys-team home"><span class="name">${m.home}</span><img src="${m.homeLogo}" width="32"></div>
                        <div class="ys-match-center">${center}<span class="ys-status ${m.status}">${statusLbl}</span></div>
                        <div class="ys-team away"><img src="${m.awayLogo}" width="32"><span class="name">${m.away}</span></div>
                    </div>`;
                });
                html += `</div></div>`;
            }
        });
        container.innerHTML = hasMatches ? html : '<div style="padding:2rem;text-align:center;">لا توجد مباريات</div>';
    }

    // Init Leagues
    const leagues = [...new Set(allMatches.map(l => l.league))];
    leagues.forEach(l => { const opt = document.createElement('option'); opt.value = l; opt.textContent = l; leagueSelect.appendChild(opt); });

    searchInput.addEventListener('input', render);
    leagueSelect.addEventListener('change', render);
    timezoneSelect.addEventListener('change', render);
    render();
});
</script>
"""

    # 3. SCHEMA INJECTION (Dynamic ItemList)
    # We update the ItemList part of your Schema to reflect real match count
    schema_str = f"""
    <script type="application/ld+json">
    {{
       "@context" : "https://schema.org",
       "@graph" : [
          {{
             "@type" : "CollectionPage",
             "@id" : "{WP_BASE}/{HUB_SLUG}/#webpage",
             "url" : "{WP_BASE}/{HUB_SLUG}/",
             "name" : "مباريات اليوم - Yacine TV",
             "description" : "جدول مباريات اليوم بتوقيت المغرب مع النتائج المباشرة.",
             "inLanguage" : "ar",
             "isPartOf" : {{ "@id" : "{WP_BASE}/#website" }}
          }},
          {{
             "@type" : "WebSite",
             "@id" : "{WP_BASE}/#website",
             "url" : "{WP_BASE}/",
             "name" : "Yassin TV App",
             "alternateName" : ["Yacine TV", "ياسين تيفي"]
          }}
       ]
    }}
    </script>
    """

    full_content = html_top + app_data_json + html_bottom + schema_str

    payload = {
        "title": "مباريات اليوم - النتائج المباشرة",
        "slug": HUB_SLUG,
        "status": "publish",
        "content": full_content
    }

    if existing_id := get_post_id_by_slug(HUB_SLUG, "pages"):
        print(f"Updating App Hub: {HUB_SLUG}")
        wp_request("POST", f"/pages/{existing_id}", json=payload)
    else:
        print(f"Creating App Hub: {HUB_SLUG}")
        wp_request("POST", "/pages", json=payload)

# =====================================================
# 6. MAIN RUNNER
# =====================================================
def main():
    print("--- STARTING BOT (ARABIC APP EDITION) ---")
    print_env_status()
    assert_auth_config()
    test_wp_auth()

    all_fixtures = get_fixtures() # Now fetches Arabic data
    
    priority_matches = [m for m in all_fixtures if m["league"]["id"] in PRIORITY_LEAGUES]
    if not priority_matches:
        print("No priority matches found. Fetching ALL for Hub.")
        priority_matches = all_fixtures[:20] # Limit if grabbing randoms

    # 1. Update Individual Match Pages
    print(f"Updating {len(priority_matches)} match pages...")
    for match in priority_matches:
        try:
            create_or_update_post(match)
        except Exception as e:
            print(f"Error on match: {e}")

    # 2. Update The App Hub
    if priority_matches:
        update_hub_page(priority_matches)

    print("--- RUN COMPLETE ---")

if __name__ == "__main__":
    main()
