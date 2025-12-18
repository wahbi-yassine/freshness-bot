import os
import requests
import base64
import json
import time
from datetime import datetime, timezone, timedelta

# =====================================================
# 1. الإعدادات
# =====================================================
WP_BASE = os.environ["WP_URL"].rstrip("/")
WP_API = f"{WP_BASE}/wp-json/wp/v2"
WP_USER = os.environ.get("WP_USER", "").strip()
WP_APP_PASSWORD = os.environ.get("WP_APP_PASSWORD", "").strip()
FOOTBALL_API_KEY = os.environ.get("FOOTBALL_API_KEY", "").strip()
FOOTBALL_API_URL = "https://v3.football.api-sports.io/fixtures"

# وسعنا القائمة لتشمل أهم البطولات العالمية والعربية
PRIORITY_LEAGUES = [39, 140, 135, 78, 61, 2, 3, 1, 4, 9, 200, 480, 529, 531, 202]

def get_wp_headers():
    token = base64.b64encode(f"{WP_USER}:{WP_APP_PASSWORD.replace(' ', '')}".encode()).decode()
    return {"Authorization": f"Basic {token}", "Content-Type": "application/json"}

# =====================================================
# 2. القالب المطور (Robust Template)
# =====================================================
HTML_TEMPLATE = r"""<div id="ys-match-app" class="ys-container" dir="rtl">
    <div class="ys-nav">
        <a href="/matches-yesterday/" class="ys-tab __ACT_YESTERDAY__">الأمس</a>
        <a href="/matches-today/" class="ys-tab __ACT_TODAY__">اليوم</a>
        <a href="/matches-tomorrow/" class="ys-tab __ACT_TOMORROW__">الغد</a>
    </div>

    <div class="ys-search">
        <input type="text" id="ys-search-input" placeholder="بحث عن فريق أو دوري...">
    </div>

    <textarea id="ys-raw-payload" style="display:none !important;">__B64_DATA__</textarea>

    <div id="ys-display-area">
        <div class="ys-message">جاري التحميل...</div>
    </div>
</div>

<script>
(function() {
    const display = document.getElementById('ys-display-area');
    const searchInput = document.getElementById('ys-search-input');
    const rawDataElement = document.getElementById('ys-raw-payload');
    
    let leagues = [];

    function init() {
        try {
            const b64 = rawDataElement.value.trim();
            if (!b64) {
                display.innerHTML = '<div class="ys-message">لا توجد بيانات متوفرة حالياً</div>';
                return;
            }

            // فك التشفير يدويًا لضمان دعم اللغة العربية في كل المتصفحات
            const binaryString = atob(b64);
            const bytes = new Uint8Array(binaryString.length);
            for (let i = 0; i < binaryString.length; i++) {
                bytes[i] = binaryString.charCodeAt(i);
            }
            const decodedText = new TextDecoder('utf-8').decode(bytes);
            leagues = JSON.parse(decodedText);
            
            render();
        } catch (err) {
            console.error(err);
            display.innerHTML = '<div class="ys-message">حدث خطأ أثناء معالجة البيانات. حاول تحديث الصفحة.</div>';
        }
    }

    function render(filter = "") {
        let html = '';
        let found = false;

        leagues.forEach(lg => {
            const filtered = lg.matches.filter(m => 
                m.home.includes(filter) || m.away.includes(filter) || lg.league.includes(filter)
            );

            if (filtered.length > 0) {
                found = true;
                html += `<div class="league-box">
                    <div class="league-title"><img src="${lg.logo}" width="18"> ${lg.league}</div>
                    ${filtered.map(m => `
                        <div class="match-card">
                            <div class="team h"><span>${m.home}</span><img src="${m.hLogo}" width="24"></div>
                            <div class="info">
                                <div class="score ${m.stat}">${m.stat==='scheduled' ? m.time : (m.score || '0-0')}</div>
                                <div class="badge ${m.stat}">${m.stat==='live'?'مباشر':(m.stat==='finished'?'انتهت':'قريباً')}</div>
                            </div>
                            <div class="team a"><img src="${m.aLogo}" width="24"><span>${m.away}</span></div>
                        </div>
                    `).join('')}
                </div>`;
            }
        });

        display.innerHTML = found ? html : '<div class="ys-message">لا توجد مباريات مطابقة للبحث</div>';
    }

    searchInput.addEventListener('input', e => render(e.target.value));
    init();
})();
</script>

<style>
.ys-container { max-width: 700px; margin: auto; font-family: sans-serif; background: #fff; border: 1px solid #eee; border-radius: 12px; padding: 10px; color: #333; }
.ys-nav { display: flex; gap: 5px; margin-bottom: 15px; }
.ys-tab { flex: 1; text-align: center; padding: 12px; background: #f8f9fa; border-radius: 8px; text-decoration: none; color: #555; font-weight: bold; font-size: 14px; border: 1px solid #eee; }
.ys-tab.active { background: #e60023; color: #fff; border-color: #e60023; }
.ys-search input { width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 8px; margin-bottom: 15px; box-sizing: border-box; }
.league-box { border: 1px solid #f0f0f0; border-radius: 10px; margin-bottom: 15px; overflow: hidden; }
.league-title { background: #f8f8f8; padding: 10px; font-size: 13px; font-weight: bold; display: flex; align-items: center; gap: 8px; border-bottom: 1px solid #f0f0f0; }
.match-card { display: flex; align-items: center; padding: 12px 8px; border-bottom: 1px solid #fafafa; }
.team { flex: 1; display: flex; align-items: center; gap: 8px; font-size: 13px; font-weight: bold; }
.team.h { justify-content: flex-end; }
.info { width: 80px; text-align: center; }
.score { font-size: 16px; font-weight: 900; }
.score.scheduled { font-size: 12px; color: #888; font-weight: normal; }
.badge { font-size: 9px; padding: 2px 6px; border-radius: 4px; display: inline-block; margin-top: 4px; }
.badge.live { background: #ff0000; color: #fff; }
.badge.finished { background: #eee; color: #888; }
.badge.scheduled { background: #e3f2fd; color: #1976d2; }
.ys-message { padding: 40px; text-align: center; color: #999; }
@media (max-width: 480px) { .team span { font-size: 11px; } .score { font-size: 14px; } }
</style>
"""

# =====================================================
# 3. الوظائف البرمجية
# =====================================================

def fetch_matches(date_str):
    print(f"📡 Fetching: {date_str}")
    params = {"date": date_str, "timezone": "Africa/Casablanca"}
    r = requests.get(FOOTBALL_API_URL, headers={"x-apisports-key": FOOTBALL_API_KEY}, params=params)
    return r.json().get("response", [])

def update_wp_page(day_type, raw_data):
    slugs = {"yesterday": "matches-yesterday", "today": "matches-today", "tomorrow": "matches-tomorrow"}
    titles = {"yesterday": "مباريات الأمس", "today": "مباريات اليوم", "tomorrow": "مباريات الغد"}
    
    leagues = {}
    for m in raw_data:
        # تصفية البطولات (إذا كانت القائمة كبيرة نأخذ الكل، إذا أردت الاختصار فعل PRIORITY_LEAGUES)
        lname = m["league"]["name"]
        if lname not in leagues:
            leagues[lname] = {"league": lname, "logo": m["league"]["logo"], "matches": []}
        
        api_stat = m["fixture"]["status"]["short"]
        stat = "scheduled"
        if api_stat in ["FT", "AET", "PEN"]: stat = "finished"
        elif api_status in ["1H", "HT", "2H", "LIVE", "BT"]: stat = "live"
        
        dt = datetime.fromisoformat(m["fixture"]["date"].replace('Z', '+00:00'))
        time_str = dt.astimezone(timezone(timedelta(hours=1))).strftime("%H:%M")

        leagues[lname]["matches"].append({
            "home": m["teams"]["home"]["name"], "hLogo": m["teams"]["home"]["logo"],
            "away": m["teams"]["away"]["name"], "aLogo": m["teams"]["away"]["logo"],
            "time": time_str, "stat": stat,
            "score": f"{m['goals']['home']}-{m['goals']['away']}" if m["goals"]["home"] is not None else None
        })

    # تحويل البيانات لـ Base64
    json_str = json.dumps(list(leagues.values()), ensure_ascii=False)
    b64_data = base64.b64encode(json_str.encode('utf-8')).decode('utf-8')

    final_content = HTML_TEMPLATE.replace("__B64_DATA__", b64_data)
    for d in ["yesterday", "today", "tomorrow"]:
        final_content = final_content.replace(f"__ACT_{d.upper()}__", "active" if day_type == d else "")

    # تحديث ووردبريس
    slug = slugs[day_type]
    r = requests.get(f"{WP_API}/pages", params={"slug": slug}, headers=get_wp_headers())
    page_id = r.json()[0]["id"] if r.status_code == 200 and r.json() else None
    
    payload = {"title": titles[day_type], "content": final_content, "status": "publish"}
    if page_id:
        print(f"✅ Update Page: {slug}")
        requests.post(f"{WP_API}/pages/{page_id}", headers=get_wp_headers(), json=payload)
    else:
        print(f"🆕 Create Page: {slug}")
        payload["slug"] = slug
        requests.post(f"{WP_API}/pages", headers=get_wp_headers(), json=payload)

# =====================================================
# 4. RUN
# =====================================================
if __name__ == "__main__":
    now = datetime.now(timezone(timedelta(hours=1)))
    days = {
        "yesterday": (now - timedelta(days=1)).strftime("%Y-%m-%d"),
        "today": now.strftime("%Y-%m-%d"),
        "tomorrow": (now + timedelta(days=1)).strftime("%Y-%m-%d")
    }
    for d_type, d_str in days.items():
        data = fetch_matches(d_str)
        update_wp_page(d_type, data)
    print("🚀 All Done!")
