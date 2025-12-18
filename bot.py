import os
import requests
import base64
import json
import time
from datetime import datetime, timezone, timedelta

# =====================================================
# 1. الإعدادات المحسنة
# =====================================================
WP_BASE = os.environ["WP_URL"].rstrip("/")
WP_API = f"{WP_BASE}/wp-json/wp/v2"
WP_USER = os.environ.get("WP_USER", "").strip()
WP_APP_PASSWORD = os.environ.get("WP_APP_PASSWORD", "").strip()
FOOTBALL_API_KEY = os.environ.get("FOOTBALL_API_KEY", "").strip()
FOOTBALL_API_URL = "https://v3.football.api-sports.io/fixtures"

# إضافة معرفات الدوريات العربية والنهائيات (ضمان ظهور النهائي العربي)
# 531: Arab Club Champions Cup, 200: Morocco, 307: Saudi, 233: Egypt, 12: CAF Champions, 17: AFC Champions
PRIORITY_LEAGUES = [39, 140, 135, 78, 61, 2, 3, 1, 4, 9, 200, 480, 529, 531, 202, 307, 233, 12, 17, 141, 143]

def get_wp_headers():
    token = base64.b64encode(f"{WP_USER}:{WP_APP_PASSWORD.replace(' ', '')}".encode()).decode()
    return {"Authorization": f"Basic {token}", "Content-Type": "application/json"}

# =====================================================
# 2. القالب الفولاذي (Anti-Breakage Template)
# =====================================================
HTML_TEMPLATE = r"""<div id="ys-match-app" class="ys-container" dir="rtl" data-payload="__B64_DATA__">
    <div class="ys-nav">
        <a href="/matches-yesterday/" class="ys-tab __ACT_YESTERDAY__">الأمس</a>
        <a href="/matches-today/" class="ys-tab __ACT_TODAY__">اليوم</a>
        <a href="/matches-tomorrow/" class="ys-tab __ACT_TOMORROW__">الغد</a>
    </div>

    <div class="ys-search">
        <input type="text" id="ys-search-input" placeholder="بحث عن فريق أو دوري...">
    </div>

    <div id="ys-display-area">
        <div class="ys-message">جاري فحص البيانات...</div>
    </div>
</div>

<script>
(function() {
    const app = document.getElementById('ys-match-app');
    const display = document.getElementById('ys-display-area');
    const searchInput = document.getElementById('ys-search-input');
    
    function init() {
        try {
            const b64 = app.getAttribute('data-payload');
            if (!b64 || b64.length < 10) {
                display.innerHTML = '<div class="ys-message">⚠️ لم يتم استلام أي بيانات من البوت. تأكد من تشغيل bot.py بنجاح.</div>';
                return;
            }

            // فك التشفير مع دعم UTF-8
            const binaryString = atob(b64);
            const bytes = new Uint8Array(binaryString.length);
            for (let i = 0; i < binaryString.length; i++) bytes[i] = binaryString.charCodeAt(i);
            const decodedText = new TextDecoder('utf-8').decode(bytes);
            const leagues = JSON.parse(decodedText);
            
            if (leagues.length === 0) {
                display.innerHTML = '<div class="ys-message">لا توجد مباريات هامة مجدولة لهذا اليوم حسب القائمة المختارة.</div>';
                return;
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
                            <div class="league-title"><img src="${lg.logo}" width="18" loading="lazy"> ${lg.league}</div>
                            ${filtered.map(m => `
                                <div class="match-card">
                                    <div class="team h"><span>${m.home}</span><img src="${m.hLogo}" width="24" loading="lazy"></div>
                                    <div class="info">
                                        <div class="score ${m.stat}">${m.stat==='scheduled' ? m.time : (m.score || '0-0')}</div>
                                        <div class="badge ${m.stat}">${m.stat==='live'?'مباشر':(m.stat==='finished'?'انتهت':'قريباً')}</div>
                                    </div>
                                    <div class="team a"><img src="${m.aLogo}" width="24" loading="lazy"><span>${m.away}</span></div>
                                </div>
                            `).join('')}
                        </div>`;
                    }
                });
                display.innerHTML = found ? html : '<div class="ys-message">لا توجد نتائج مطابقة لبحثك</div>';
            }

            searchInput.addEventListener('input', e => render(e.target.value));
            render();

        } catch (err) {
            console.error("Critical JS Error:", err);
            display.innerHTML = '<div class="ys-message">❌ خطأ تقني: ووردبريس قام بتعطيل كود البيانات. حاول مسح الكاش.</div>';
        }
    }
    
    // تشغيل التطبيق
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
</script>

<style>
.ys-container { max-width: 700px; margin: 20px auto; font-family: -apple-system, sans-serif; background: #fff; border: 1px solid #eee; border-radius: 12px; padding: 15px; color: #333; box-shadow: 0 4px 15px rgba(0,0,0,0.05); }
.ys-nav { display: flex; gap: 8px; margin-bottom: 20px; }
.ys-tab { flex: 1; text-align: center; padding: 12px; background: #f8f9fa; border-radius: 8px; text-decoration: none; color: #555; font-weight: bold; font-size: 14px; border: 1px solid #eee; transition: 0.2s; }
.ys-tab.active { background: #e60023; color: #fff; border-color: #e60023; }
.ys-search input { width: 100%; padding: 14px; border: 1px solid #ddd; border-radius: 8px; margin-bottom: 20px; box-sizing: border-box; font-size: 15px; outline: none; }
.league-box { border: 1px solid #f0f0f0; border-radius: 10px; margin-bottom: 20px; overflow: hidden; }
.league-title { background: #f8f8f8; padding: 12px; font-size: 13px; font-weight: bold; display: flex; align-items: center; gap: 10px; border-bottom: 1px solid #f0f0f0; }
.match-card { display: flex; align-items: center; padding: 15px 10px; border-bottom: 1px solid #fafafa; }
.team { flex: 1; display: flex; align-items: center; gap: 10px; font-size: 13px; font-weight: bold; }
.team.h { justify-content: flex-end; text-align: left; }
.info { width: 90px; text-align: center; }
.score { font-size: 18px; font-weight: 900; color: #000; }
.score.scheduled { font-size: 14px; color: #777; font-weight: normal; }
.badge { font-size: 10px; padding: 2px 8px; border-radius: 4px; display: inline-block; margin-top: 5px; font-weight: bold; }
.badge.live { background: #ff0000; color: #fff; animation: ys-fade 1s infinite; }
.badge.finished { background: #eee; color: #888; }
.badge.scheduled { background: #e3f2fd; color: #1976d2; }
.ys-message { padding: 50px 20px; text-align: center; color: #666; font-size: 14px; line-height: 1.6; }
@keyframes ys-fade { 50% { opacity: 0.5; } }
@media (max-width: 480px) { .team span { font-size: 11px; } .score { font-size: 15px; } .info { width: 75px; } }
</style>
"""

# =====================================================
# 3. الوظائف المنطقية
# =====================================================

def fetch_matches(date_str):
    print(f"📡 Fetching data for: {date_str}")
    params = {"date": date_str, "timezone": "Africa/Casablanca"}
    try:
        r = requests.get(FOOTBALL_API_URL, headers={"x-apisports-key": FOOTBALL_API_KEY}, params=params)
        r.raise_for_status()
        return r.json().get("response", [])
    except Exception as e:
        print(f"❌ API Error: {e}")
        return []

def update_wp_page(day_type, raw_data):
    slugs = {"yesterday": "matches-yesterday", "today": "matches-today", "tomorrow": "matches-tomorrow"}
    titles = {"yesterday": "مباريات الأمس", "today": "مباريات اليوم", "tomorrow": "مباريات الغد"}
    
    leagues_data = {}
    for m in raw_data:
        # إذا كنت تريد عرض كل المباريات دون استثناء، عطل الشرط التالي:
        if m["league"]["id"] not in PRIORITY_LEAGUES:
            continue
            
        lname = m["league"]["name"]
        if lname not in leagues_data:
            leagues_data[lname] = {"league": lname, "logo": m["league"]["logo"], "matches": []}
        
        api_status = m["fixture"]["status"]["short"]
        stat = "scheduled"
        if api_status in ["FT", "AET", "PEN"]: stat = "finished"
        elif api_status in ["1H", "HT", "2H", "LIVE", "BT"]: stat = "live"
        
        # تحويل التوقيت
        dt = datetime.fromisoformat(m["fixture"]["date"].replace('Z', '+00:00'))
        time_str = dt.astimezone(timezone(timedelta(hours=1))).strftime("%H:%M")

        leagues_data[lname]["matches"].append({
            "home": m["teams"]["home"]["name"], "hLogo": m["teams"]["home"]["logo"],
            "away": m["teams"]["away"]["name"], "aLogo": m["teams"]["away"]["logo"],
            "time": time_str, "stat": stat,
            "score": f"{m['goals']['home']}-{m['goals']['away']}" if m["goals"]["home"] is not None else None
        })

    # تحويل البيانات لـ Base64
    json_str = json.dumps(list(leagues_data.values()), ensure_ascii=False)
    b64_data = base64.b64encode(json_str.encode('utf-8')).decode('utf-8')

    # بناء المحتوى النهائي
    content = HTML_TEMPLATE.replace("__B64_DATA__", b64_data)
    for d in ["yesterday", "today", "tomorrow"]:
        content = content.replace(f"__ACT_{d.upper()}__", "active" if day_type == d else "")

    # تحديث ووردبريس
    slug = slugs[day_type]
    headers = get_wp_headers()
    
    r = requests.get(f"{WP_API}/pages", params={"slug": slug}, headers=headers)
    page_id = r.json()[0]["id"] if r.status_code == 200 and r.json() else None
    
    payload = {"title": titles[day_type], "content": content, "status": "publish"}
    
    if page_id:
        print(f"✅ Updating {slug} (Matches: {len(raw_data)})")
        requests.post(f"{WP_API}/pages/{page_id}", headers=headers, json=payload)
    else:
        print(f"🆕 Creating {slug}")
        payload["slug"] = slug
        requests.post(f"{WP_API}/pages", headers=headers, json=payload)

# =====================================================
# 4. التنفيذ
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
    print("🚀 Done! Please clear your LiteSpeed cache now.")
