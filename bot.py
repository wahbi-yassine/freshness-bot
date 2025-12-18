import os
import requests
import base64
import json
from datetime import datetime, timezone, timedelta

# =====================================================
# 1. إعدادات الدوريات (Arab, Europe, Nations)
# =====================================================
# قمت بتنظيم المعرفات لضمان ظهور ما تهتم به أولاً
ARAB_LEAGUES = [200, 307, 233, 202, 531, 12, 17] # المغرب، السعودية، مصر، الإمارات، أبطال العرب، أبطال أفريقيا، أبطال آسيا
EUROPE_LEAGUES = [39, 140, 135, 78, 61, 2, 3]    # إنجلترا، إسبانيا، إيطاليا، ألمانيا، فرنسا، أبطال أوروبا، الدوري الأوروبي
NATIONS_LEAGUES = [1, 4, 9, 34, 10, 20, 21]      # كأس العالم، اليورو، كوبا أمريكا، أمم أفريقيا، وديات دولية، تصفيات

ALL_INTERESTED_LEAGUES = ARAB_LEAGUES + EUROPE_LEAGUES + NATIONS_LEAGUES

# إعدادات WP و API
WP_BASE = os.environ["WP_URL"].rstrip("/")
WP_API = f"{WP_BASE}/wp-json/wp/v2"
WP_USER = os.environ.get("WP_USER", "").strip()
WP_APP_PASSWORD = os.environ.get("WP_APP_PASSWORD", "").strip()
FOOTBALL_API_KEY = os.environ.get("FOOTBALL_API_KEY", "").strip()

def get_wp_headers():
    token = base64.b64encode(f"{WP_USER}:{WP_APP_PASSWORD.replace(' ', '')}".encode()).decode()
    return {"Authorization": f"Basic {token}", "Content-Type": "application/json"}

# =====================================================
# 2. القالب المستوحى من الـ Widgets (HTML/CSS)
# =====================================================
HTML_TEMPLATE = r"""<div id="ultimate-match-center" class="match-center-wrapper" dir="rtl">
    <div class="center-nav">
        <a href="/matches-yesterday/" class="nav-item __ACT_YESTERDAY__">الأمس</a>
        <a href="/matches-today/" class="nav-item __ACT_TODAY__">مباريات اليوم</a>
        <a href="/matches-tomorrow/" class="nav-item __ACT_TOMORROW__">الغد</a>
    </div>

    <div class="search-container">
        <input type="text" id="match-search" placeholder="ابحث عن فريق، بطولة، أو دوري...">
    </div>

    <div id="matches-container">
        <div class="loading-state">جاري ترتيب المباريات...</div>
    </div>
</div>

<script>
(function() {
    const DATA = __JSON_DATA__;
    const container = document.getElementById('matches-container');
    const searchInput = document.getElementById('match-search');

    function renderMatches(filter = "") {
        if (!DATA || DATA.length === 0) {
            container.innerHTML = '<div class="no-matches">لا توجد مباريات هامة مجدولة حالياً</div>';
            return;
        }

        let html = '';
        DATA.forEach(group => {
            const filteredLeagues = group.leagues.filter(lg => {
                const matchesMatch = lg.matches.filter(m => 
                    m.home.toLowerCase().includes(filter.toLowerCase()) || 
                    m.away.toLowerCase().includes(filter.toLowerCase())
                );
                return lg.name.toLowerCase().includes(filter.toLowerCase()) || matchesMatch.length > 0;
            });

            if (filteredLeagues.length > 0) {
                html += `<div class="group-section">
                    <h2 class="group-title">${group.category}</h2>`;
                
                filteredLeagues.forEach(lg => {
                    html += `
                    <div class="league-card">
                        <div class="league-header">
                            <img src="${lg.logo}" width="22" height="22">
                            <span>${lg.name}</span>
                        </div>
                        <div class="match-list">
                            ${lg.matches.map(m => `
                                <div class="match-row">
                                    <div class="team home">
                                        <span class="team-name">${m.home}</span>
                                        <img src="${m.hLogo}" width="24" height="24">
                                    </div>
                                    <div class="match-meta">
                                        <div class="score-pill ${m.status}">
                                            ${m.status === 'scheduled' ? m.time : (m.score || '0 - 0')}
                                        </div>
                                        <div class="status-label ${m.status}">
                                            ${m.status === 'live' ? 'مباشر' : (m.status === 'finished' ? 'انتهت' : 'قريباً')}
                                        </div>
                                    </div>
                                    <div class="team away">
                                        <img src="${m.aLogo}" width="24" height="24">
                                        <span class="team-name">${m.away}</span>
                                    </div>
                                </div>
                            `).join('')}
                        </div>
                    </div>`;
                });
                html += `</div>`;
            }
        });
        container.innerHTML = html || '<div class="no-matches">لم يتم العثور على نتائج للبحث</div>';
    }

    searchInput.addEventListener('input', (e) => renderMatches(e.target.value));
    renderMatches();
})();
</script>

<style>
.match-center-wrapper { max-width: 800px; margin: auto; font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background: #fdfdfd; padding: 15px; border-radius: 15px; color: #222; }
.center-nav { display: flex; gap: 8px; margin-bottom: 20px; }
.nav-item { flex: 1; text-align: center; padding: 14px; background: #fff; border: 1px solid #eee; border-radius: 10px; text-decoration: none; color: #555; font-weight: bold; font-size: 14px; transition: 0.3s; }
.nav-item.active { background: #1a1a1a; color: #fff; border-color: #1a1a1a; }
.search-container input { width: 100%; padding: 15px; border: 2px solid #f0f0f0; border-radius: 12px; margin-bottom: 20px; box-sizing: border-box; outline: none; font-size: 15px; }
.search-container input:focus { border-color: #e60023; }
.group-title { font-size: 18px; color: #e60023; margin: 25px 0 15px; border-right: 4px solid #e60023; padding-right: 12px; }
.league-card { background: #fff; border: 1px solid #f0f0f0; border-radius: 12px; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.02); overflow: hidden; }
.league-header { background: #f8f9fa; padding: 12px 15px; display: flex; align-items: center; gap: 10px; font-weight: bold; font-size: 14px; border-bottom: 1px solid #f0f0f0; }
.match-row { display: flex; align-items: center; padding: 18px 10px; border-bottom: 1px solid #f9f9f9; transition: 0.2s; }
.match-row:hover { background: #fffcfc; }
.team { flex: 1; display: flex; align-items: center; gap: 12px; }
.team.home { justify-content: flex-end; text-align: left; }
.team.away { justify-content: flex-start; text-align: right; }
.team-name { font-weight: 700; font-size: 14px; }
.match-meta { width: 100px; text-align: center; }
.score-pill { font-size: 18px; font-weight: 900; color: #000; letter-spacing: -0.5px; }
.score-pill.scheduled { font-size: 14px; color: #666; font-weight: 600; }
.status-label { font-size: 10px; font-weight: bold; margin-top: 4px; padding: 2px 8px; border-radius: 20px; display: inline-block; }
.status-label.live { background: #ff0000; color: #fff; animation: blinker 1s linear infinite; }
.status-label.finished { background: #eee; color: #888; }
.status-label.scheduled { background: #e8f4ff; color: #007bff; }
@keyframes blinker { 50% { opacity: 0; } }
@media (max-width: 600px) { .team-name { font-size: 12px; } .score-pill { font-size: 15px; } .match-meta { width: 80px; } }
</style>
"""

# =====================================================
# 3. معالجة البيانات (Smart Logic)
# =====================================================

def fetch_data(date_str):
    print(f"📡 جلب بيانات {date_str}...")
    headers = {"x-apisports-key": FOOTBALL_API_KEY}
    r = requests.get("https://v3.football.api-sports.io/fixtures", headers=headers, params={"date": date_str, "timezone": "Africa/Casablanca"})
    return r.json().get("response", [])

def build_data_structure(fixtures):
    # تقسيم البيانات لثلاث فئات
    categories = {
        "Arab": {"category": "🏆 البطولات العربية والدولية", "leagues": {}},
        "Europe": {"category": "🇪🇺 الدوريات الأوروبية الكبرى", "leagues": {}},
        "Nations": {"category": "🌍 المنتخبات والبطولات القارية", "leagues": {}}
    }

    for f in fixtures:
        l_id = f["league"]["id"]
        # تحديد الفئة
        cat_key = None
        if l_id in ARAB_LEAGUES: cat_key = "Arab"
        elif l_id in EUROPE_LEAGUES: cat_key = "Europe"
        elif l_id in NATIONS_LEAGUES: cat_key = "Nations"
        
        if not cat_key: continue

        lname = f["league"]["name"]
        if lname not in categories[cat_key]["leagues"]:
            categories[cat_key]["leagues"][lname] = {"name": lname, "logo": f["league"]["logo"], "matches": []}
        
        status = "scheduled"
        if f["fixture"]["status"]["short"] in ["FT", "AET", "PEN"]: status = "finished"
        elif f["fixture"]["status"]["short"] in ["1H", "HT", "2H", "LIVE", "BT"]: status = "live"

        dt = datetime.fromisoformat(f["fixture"]["date"].replace('Z', '+00:00'))
        time_str = dt.astimezone(timezone(timedelta(hours=1))).strftime("%H:%M")

        categories[cat_key]["leagues"][lname]["matches"].append({
            "home": f["teams"]["home"]["name"], "hLogo": f["teams"]["home"]["logo"],
            "away": f["teams"]["away"]["name"], "aLogo": f["teams"]["away"]["logo"],
            "time": time_str, "status": status,
            "score": f"{f['goals']['home']} - {f['goals']['away']}" if f["goals"]["home"] is not None else None
        })

    # تحويل القواميس إلى قوائم مرتبة
    final_data = []
    for key in ["Arab", "Europe", "Nations"]:
        if categories[key]["leagues"]:
            cat_node = {
                "category": categories[key]["category"],
                "leagues": list(categories[key]["leagues"].values())
            }
            final_data.append(cat_node)
    return final_data

def update_page(day_type, data_list):
    slugs = {"yesterday": "matches-yesterday", "today": "matches-today", "tomorrow": "matches-tomorrow"}
    titles = {"yesterday": "نتائج مباريات الأمس", "today": "مباريات اليوم مباشر", "tomorrow": "جدول مباريات الغد"}
    
    # تحويل البيانات لـ JSON وإدراجها في القالب
    json_payload = json.dumps(data_list, ensure_ascii=False)
    content = HTML_TEMPLATE.replace("__JSON_DATA__", json_payload)
    
    # تفعيل الزر المناسب
    for d in ["yesterday", "today", "tomorrow"]:
        content = content.replace(f"__ACT_{d.upper()}__", "active" if day_type == d else "")

    slug = slugs[day_type]
    headers = get_wp_headers()
    
    # البحث عن الصفحة أو إنشاؤها
    r = requests.get(f"{WP_API}/pages", params={"slug": slug}, headers=headers)
    page_id = r.json()[0]["id"] if r.status_code == 200 and r.json() else None
    
    payload = {"title": titles[day_type], "content": content, "status": "publish"}
    if page_id:
        print(f"✅ تحديث صفحة: {slug}")
        requests.post(f"{WP_API}/pages/{page_id}", headers=headers, json=payload)
    else:
        print(f"🆕 إنشاء صفحة: {slug}")
        payload["slug"] = slug
        requests.post(f"{WP_API}/pages", headers=headers, json=payload)

# =====================================================
# 4. التشغيل
# =====================================================
if __name__ == "__main__":
    now = datetime.now(timezone(timedelta(hours=1)))
    days = {
        "yesterday": (now - timedelta(days=1)).strftime("%Y-%m-%d"),
        "today": now.strftime("%Y-%m-%d"),
        "tomorrow": (now + timedelta(days=1)).strftime("%Y-%m-%d")
    }
    for d_type, d_date in days.items():
        raw = fetch_data(d_date)
        structured = build_data_structure(raw)
        update_page(d_type, structured)
    print("🚀 تم تحديث المركز الرياضي بنجاح!")
