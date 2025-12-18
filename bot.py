import os
import requests
import base64
import json
import time
from datetime import datetime, timezone, timedelta

# =====================================================
# 1. الإعدادات الأساسية (CONFIGURATION)
# =====================================================
WP_BASE = os.environ["WP_URL"].rstrip("/")
WP_API = f"{WP_BASE}/wp-json/wp/v2"
WP_USER = os.environ.get("WP_USER", "").strip()
WP_APP_PASSWORD = os.environ.get("WP_APP_PASSWORD", "").strip()
FOOTBALL_API_KEY = os.environ.get("FOOTBALL_API_KEY", "").strip()
FOOTBALL_API_URL = "https://v3.football.api-sports.io/fixtures"

# البطولات المفضلة (يمكنك إضافة المزيد من IDs هنا)
PRIORITY_LEAGUES = [39, 140, 135, 78, 61, 2, 200, 1, 9, 3, 4, 480, 529]

SESSION = requests.Session()

def get_wp_headers():
    clean_pw = WP_APP_PASSWORD.replace(" ", "")
    token = base64.b64encode(f"{WP_USER}:{clean_pw}".encode("utf-8")).decode("utf-8")
    return {
        "Authorization": f"Basic {token}",
        "Content-Type": "application/json",
    }

# =====================================================
# 2. قالب العرض (HTML + CSS + JS)
# =====================================================
# ملاحظة: نستخدم Base64 لنقل البيانات لضمان عدم تلفها داخل ووردبريس
HTML_TEMPLATE = r"""<div id="ys-app" class="ys-container" dir="rtl">
    <div class="ys-nav">
        <a href="/matches-yesterday/" class="ys-btn __ACT_YESTERDAY__">الأمس</a>
        <a href="/matches-today/" class="ys-btn __ACT_TODAY__">اليوم</a>
        <a href="/matches-tomorrow/" class="ys-btn __ACT_TOMORROW__">الغد</a>
    </div>

    <div class="ys-search-box">
        <input type="text" id="ys-input" placeholder="بحث عن فريق أو دوري...">
    </div>

    <div id="ys-list" class="ys-matches-list">
        <div class="ys-wait">جاري معالجة البيانات...</div>
    </div>
</div>

<script>
(function() {
    const DATA_B64 = "__B64_PAYLOAD__";
    let allLeagues = [];

    try {
        const decoded = atob(DATA_B64);
        const bytes = new Uint8Array(decoded.length);
        for (let i = 0; i < decoded.length; i++) bytes[i] = decoded.charCodeAt(i);
        allLeagues = JSON.parse(new TextDecoder().decode(bytes));
    } catch (err) { console.error("Data Fail:", err); }

    const listDiv = document.getElementById('ys-list');
    const input = document.getElementById('ys-input');

    function draw(filter = "") {
        let html = '';
        allLeagues.forEach(lg => {
            const matches = lg.matches.filter(m => 
                m.home.includes(filter) || m.away.includes(filter) || lg.league.includes(filter)
            );
            
            if (matches.length > 0) {
                html += `<div class="ys-lg-card">
                    <div class="ys-lg-head"><img src="${lg.logo}" width="20"> ${lg.league}</div>
                    ${matches.map(m => `
                        <div class="ys-row">
                            <div class="ys-tm side-h"><span>${m.home}</span><img src="${m.hLogo}" width="25"></div>
                            <div class="ys-mid">
                                <div class="ys-sc ${m.stat}">${m.stat==='scheduled' ? m.time : (m.score || '0-0')}</div>
                                <div class="ys-st ${m.stat}">${m.stat==='live'?'مباشر':(m.stat==='finished'?'انتهت':'قريباً')}</div>
                            </div>
                            <div class="ys-tm side-a"><img src="${m.aLogo}" width="25"><span>${m.away}</span></div>
                        </div>
                    `).join('')}
                </div>`;
            }
        });
        listDiv.innerHTML = html || '<div class="ys-wait">لا توجد مباريات مطابقة</div>';
    }

    input.addEventListener('input', e => draw(e.target.value));
    draw();
})();
</script>

<style>
.ys-container { background: #fcfcfc; border: 1px solid #eee; border-radius: 12px; padding: 15px; font-family: system-ui; color: #333; max-width: 850px; margin: auto; }
.ys-nav { display: flex; gap: 8px; margin-bottom: 20px; }
.ys-btn { flex: 1; text-align: center; padding: 12px; background: #fff; border: 1px solid #ddd; border-radius: 8px; text-decoration: none; color: #555; font-weight: bold; font-size: 14px; }
.ys-btn.active { background: #e60023; color: #fff; border-color: #e60023; box-shadow: 0 4px 10px rgba(230,0,35,0.2); }
.ys-search-box input { width: 100%; padding: 14px; border: 1px solid #ddd; border-radius: 8px; margin-bottom: 15px; box-sizing: border-box; outline: none; transition: 0.3s; }
.ys-search-box input:focus { border-color: #e60023; box-shadow: 0 0 5px rgba(230,0,35,0.1); }
.ys-lg-card { background: #fff; border: 1px solid #eee; border-radius: 10px; margin-bottom: 15px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.02); }
.ys-lg-head { background: #f8f8f8; padding: 10px 15px; font-size: 13px; font-weight: 800; display: flex; align-items: center; gap: 10px; border-bottom: 1px solid #eee; color: #444; }
.ys-row { display: flex; align-items: center; padding: 15px 10px; border-bottom: 1px solid #f9f9f9; }
.ys-tm { flex: 1; display: flex; align-items: center; gap: 10px; font-size: 14px; font-weight: 600; }
.side-h { justify-content: flex-end; }
.side-a { justify-content: flex-start; }
.ys-mid { width: 90px; text-align: center; }
.ys-sc { font-size: 17px; font-weight: 900; color: #000; letter-spacing: -1px; }
.ys-sc.scheduled { font-size: 14px; color: #777; font-weight: normal; }
.ys-st { font-size: 10px; padding: 2px 8px; border-radius: 20px; display: inline-block; margin-top: 4px; font-weight: bold; }
.ys-st.live { background: #ff0000; color: #fff; animation: ys-blink 1s infinite; }
.ys-st.finished { background: #f0f0f0; color: #888; }
.ys-st.scheduled { background: #e3f2fd; color: #1976d2; }
.ys-wait { padding: 40px; text-align: center; color: #999; }
@keyframes ys-blink { 50% { opacity: 0.4; } }
@media (max-width: 500px) { .ys-tm span { font-size: 11px; } .ys-mid { width: 70px; } .ys-sc { font-size: 14px; } }
</style>
"""

# =====================================================
# 3. وظائف الجلب والمعالجة (LOGIC)
# =====================================================

def fetch_data(date_str):
    print(f"📡 جلب بيانات: {date_str}...")
    params = {"date": date_str, "timezone": "Africa/Casablanca"}
    try:
        r = requests.get(FOOTBALL_API_URL, headers={"x-apisports-key": FOOTBALL_API_KEY}, params=params)
        return r.json().get("response", [])
    except Exception as e:
        print(f"❌ خطأ API: {e}")
        return []

def get_page_id(slug):
    r = requests.get(f"{WP_API}/pages", params={"slug": slug}, headers=get_wp_headers())
    return r.json()[0]["id"] if r.status_code == 200 and r.json() else None

def process_and_update(day_type, raw_data):
    # 1. التواريخ والعناوين
    config = {
        "yesterday": {"slug": "matches-yesterday", "title": "نتائج مباريات الأمس"},
        "today":     {"slug": "matches-today",     "title": "جدول مباريات اليوم مباشر"},
        "tomorrow":  {"slug": "matches-tomorrow",  "title": "جدول مباريات الغد"}
    }
    
    # 2. تصفية البيانات وترتيبها حسب الدوريات
    leagues = {}
    for item in raw_data:
        lname = item["league"]["name"]
        if lname not in leagues:
            leagues[lname] = {"league": lname, "logo": item["league"]["logo"], "matches": []}
        
        # تحويل حالة المباراة
        api_status = item["fixture"]["status"]["short"]
        stat = "scheduled"
        if api_status in ["FT", "AET", "PEN"]: stat = "finished"
        elif api_status in ["1H", "HT", "2H", "LIVE"]: stat = "live"
        
        # التوقيت
        dt = datetime.fromisoformat(item["fixture"]["date"].replace('Z', '+00:00'))
        time_str = dt.astimezone(timezone(timedelta(hours=1))).strftime("%H:%M")

        leagues[lname]["matches"].append({
            "home": item["teams"]["home"]["name"],
            "hLogo": item["teams"]["home"]["logo"],
            "away": item["teams"]["away"]["name"],
            "aLogo": item["teams"]["away"]["logo"],
            "time": time_str,
            "stat": stat,
            "score": f"{item['goals']['home']}-{item['goals']['away']}" if item["goals"]["home"] is not None else None
        })

    # 3. تشفير البيانات Base64 (هذا هو السر لعدم كسر الكود)
    json_bytes = json.dumps(list(leagues.values()), ensure_ascii=False).encode('utf-8')
    b64_str = base64.b64encode(json_bytes).decode('utf-8')

    # 4. دمج البيانات في القالب
    final_html = HTML_TEMPLATE.replace("__B64_PAYLOAD__", b64_str)
    for d in ["yesterday", "today", "tomorrow"]:
        final_html = final_html.replace(f"__ACT_{d.upper()}__", "active" if day_type == d else "")

    # 5. الإرسال لووردبريس
    slug = config[day_type]["slug"]
    payload = {"title": config[day_type]["title"], "content": final_html, "status": "publish"}
    
    pid = get_page_id(slug)
    if pid:
        print(f"🔄 تحديث صفحة {slug} (ID: {pid})")
        requests.post(f"{WP_API}/pages/{pid}", headers=get_wp_headers(), json=payload)
    else:
        print(f"🆕 إنشاء صفحة {slug}")
        payload["slug"] = slug
        requests.post(f"{WP_API}/pages", headers=get_wp_headers(), json=payload)

# =====================================================
# 4. التشغيل الرئيسي (MAIN)
# =====================================================
if __name__ == "__main__":
    now = datetime.now(timezone(timedelta(hours=1)))
    days_map = {
        "yesterday": (now - timedelta(days=1)).strftime("%Y-%m-%d"),
        "today":     now.strftime("%Y-%m-%d"),
        "tomorrow":  (now + timedelta(days=1)).strftime("%Y-%m-%d")
    }

    print("🚀 بدء تشغيل الألتيميت بوت...")
    for day_type, date_str in days_map.items():
        data = fetch_data(date_str)
        process_and_update(day_type, data)
    
    print("✅ تم تحديث جميع الصفحات بنجاح!")
