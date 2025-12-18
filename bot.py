import os
import requests
import base64
import json
from datetime import datetime, timezone, timedelta

# =====================================================
# 1. الإعدادات وتصحيح المدخلات (Environment & Cleanup)
# =====================================================
ARAB_LEAGUES = [200, 307, 233, 531, 12, 17, 202, 141, 143] 
EUROPE_LEAGUES = [39, 140, 135, 78, 61, 2, 3] 
NATIONS_LEAGUES = [1, 4, 9, 10, 20, 21, 42]

# تنظيف المتغيرات لضمان عدم وجود أسطر زائدة تسبب خطأ في الـ Header
WP_URL = os.environ.get("WP_URL", "").strip().rstrip("/")
WP_USER = os.environ.get("WP_USER", "").strip()
WP_APP_PASSWORD = os.environ.get("WP_APP_PASSWORD", "").strip()
FOOTBALL_API_KEY = os.environ.get("FOOTBALL_API_KEY", "").strip()

def get_wp_headers():
    clean_pwd = WP_APP_PASSWORD.replace(" ", "")
    auth_str = f"{WP_USER}:{clean_pwd}"
    token = base64.b64encode(auth_str.encode()).decode()
    return {"Authorization": f"Basic {token}", "Content-Type": "application/json"}

# =====================================================
# 2. قالب العرض الاحترافي (Hardened UI Template)
# =====================================================
HTML_TEMPLATE = r"""<div id="ys-main-app" class="ys-widget-ui" dir="rtl">
    <div class="ys-tabs">
        <a href="/matches-yesterday/" class="ys-tab-btn __ACT_YESTERDAY__">الأمس</a>
        <a href="/matches-today/" class="ys-tab-btn __ACT_TODAY__">مباريات اليوم</a>
        <a href="/matches-tomorrow/" class="ys-tab-btn __ACT_TOMORROW__">الغد</a>
    </div>

    <div id="ys-payload" style="display:none !important;">__B64_DATA__</div>

    <div id="ys-view">
        <div class="ys-loader">جاري تحديث النتائج...</div>
    </div>
    <div id="ys-refresh-timer" style="font-size:9px; color:#ccc; text-align:center; margin-top:10px;">سيتم التحديث تلقائياً خلال دقائق...</div>
</div>

<script>
(function() {
    let tries = 0;
    const REFRESH_INTERVAL = 5 * 60 * 1000; // 5 دقائق

    function start() {
        const payloadDiv = document.getElementById('ys-payload');
        const viewDiv = document.getElementById('ys-view');
        
        // نظام المحاولات المتكررة لضمان وجود الـ DOM (Retry Mechanism)
        if (!payloadDiv || !viewDiv) {
            if (tries < 20) {
                tries++;
                setTimeout(start, 250);
            } else {
                console.error("YS: Elements not found.");
            }
            return;
        }

        try {
            // استخدام textContent والتنظيف الصارم لضمان فك تشفير Base64 بنجاح
            let rawBase64 = (payloadDiv.textContent || "")
                .replace(/&nbsp;/g, "")
                .replace(/\s+/g, "")
                .replace(/[^A-Za-z0-9+/=]/g, "")
                .trim();

            if (!rawBase64 || rawBase64.length < 10) {
                throw new Error("Payload Empty");
            }

            const binaryString = atob(rawBase64);
            const bytes = new Uint8Array(binaryString.length);
            for (let i = 0; i < binaryString.length; i++) bytes[i] = binaryString.charCodeAt(i);
            const data = JSON.parse(new TextDecoder().decode(bytes));
            
            if (!data || data.length === 0) {
                viewDiv.innerHTML = '<div class="ys-no-data">لا توجد مباريات هامة متوفرة حالياً</div>';
                return;
            }

            let html = '';
            data.forEach(cat => {
                html += `<div class="ys-cat-header">${cat.title}</div>`;
                cat.leagues.forEach(lg => {
                    html += `<div class="ys-lg-box">
                        <div class="ys-lg-head"><img src="${lg.logo}" width="18"> ${lg.name}</div>
                        ${lg.matches.map(m => `
                            <div class="ys-match">
                                <div class="ys-team h"><span>${m.home}</span><img src="${m.hLogo}" width="22"></div>
                                <div class="ys-info">
                                    <div class="ys-score ${m.status}">${m.status === 'scheduled' ? m.time : (m.score || '0-0')}</div>
                                    <div class="ys-stat ${m.status}">${m.status === 'live' ? 'مباشر' : (m.status === 'finished' ? 'انتهت' : 'قريباً')}</div>
                                </div>
                                <div class="ys-team a"><img src="${m.aLogo}" width="22"><span>${m.away}</span></div>
                            </div>
                        `).join('')}
                    </div>`;
                });
            });
            viewDiv.innerHTML = html;

            // ميزة التحديث التلقائي (Auto-Refresh)
            setTimeout(() => { location.reload(); }, REFRESH_INTERVAL);

        } catch (e) {
            console.error("YS Error:", e);
            viewDiv.innerHTML = '<div class="ys-no-data">❌ عذراً، حدث خطأ أثناء عرض البيانات.</div>';
        }
    }

    if (document.readyState === "complete" || document.readyState === "interactive") start();
    else window.addEventListener('load', start);
})();
</script>

<style>
.ys-widget-ui { max-width: 800px; margin: 20px auto; background: #fff; border-radius: 12px; padding: 12px; font-family: system-ui, -apple-system, sans-serif; box-shadow: 0 10px 30px rgba(0,0,0,0.08); border: 1px solid #f0f0f0; }
.ys-tabs { display: flex; gap: 6px; margin-bottom: 20px; border-bottom: 2px solid #f9f9f9; padding-bottom: 10px; }
.ys-tab-btn { flex: 1; text-align: center; padding: 12px; background: #fdfdfd; border-radius: 8px; text-decoration: none; color: #777; font-weight: bold; font-size: 14px; border: 1px solid #eee; }
.ys-tab-btn.active { background: #e60023 !important; color: #fff !important; border-color: #e60023; }
.ys-cat-header { background: #1a1a1a; color: #fff; padding: 8px 15px; border-radius: 6px; font-size: 15px; margin: 25px 0 10px; font-weight: bold; }
.ys-lg-box { border: 1px solid #f0f0f0; border-radius: 10px; margin-bottom: 15px; overflow: hidden; background: #fff; }
.ys-lg-head { background: #fafafa; padding: 10px 15px; font-size: 12px; font-weight: 800; border-bottom: 1px solid #f0f0f0; display: flex; align-items: center; gap: 8px; color: #444; }
.ys-match { display: flex; align-items: center; padding: 15px 10px; border-bottom: 1px solid #fcfcfc; }
.ys-team { flex: 1; display: flex; align-items: center; gap: 12px; font-size: 13px; font-weight: bold; }
.ys-team.h { justify-content: flex-end; }
.ys-info { width: 85px; text-align: center; }
.ys-score { font-size: 17px; font-weight: 900; color: #000; }
.ys-score.scheduled { font-size: 13px; color: #888; font-weight: 600; }
.ys-stat { font-size: 10px; font-weight: bold; padding: 2px 6px; border-radius: 4px; display: inline-block; margin-top: 4px; }
.ys-stat.live { background: #ff0000; color: #fff; animation: ys-blink 1.2s infinite; }
.ys-stat.finished { background: #eee; color: #999; }
.ys-stat.scheduled { background: #eef6ff; color: #007bff; }
.ys-no-data, .ys-loader { padding: 50px; text-align: center; color: #aaa; font-size: 14px; }
@keyframes ys-blink { 50% { opacity: 0.4; } }
@media (max-width: 500px) { .ys-team span { font-size: 11px; } .ys-score { font-size: 14px; } }
</style>
"""

# =====================================================
# 3. منطق الجلب والمعالجة (API & Processing)
# =====================================================

def fetch_data(date_str):
    print(f"📡 Fetching: {date_str}")
    headers = {"x-apisports-key": FOOTBALL_API_KEY, "Accept": "application/json"}
    try:
        r = requests.get(
            "https://v3.football.api-sports.io/fixtures", 
            headers=headers, 
            params={"date": date_str, "timezone": "Africa/Casablanca"},
            timeout=30
        )
        r.raise_for_status()
        return r.json().get("response", [])
    except Exception as e:
        print(f"❌ API Error: {e}")
        return []

def organize_matches(raw_fixtures):
    sections = {
        "arab": {"title": "🏆 البطولات العربية والقارية", "leagues": {}},
        "euro": {"title": "🇪🇺 الدوريات الأوروبية الكبرى", "leagues": {}},
        "intl": {"title": "🌍 المنتخبات والبطولات الدولية", "leagues": {}}
    }
    
    for f in raw_fixtures:
        l_id = f["league"]["id"]
        target = "arab" if l_id in ARAB_LEAGUES else ("euro" if l_id in EUROPE_LEAGUES else ("intl" if l_id in NATIONS_LEAGUES else None))
        
        if not target: continue
        
        lname = f["league"]["name"]
        if lname not in sections[target]["leagues"]:
            sections[target]["leagues"][lname] = {"name": lname, "logo": f["league"]["logo"], "matches": []}
            
        status = "scheduled"
        short_status = f["fixture"]["status"]["short"]
        if short_status in ["FT", "AET", "PEN"]: status = "finished"
        elif short_status in ["1H", "HT", "2H", "LIVE", "BT"]: status = "live"
        
        # تحويل الوقت مع مراعاة توقيت الدار البيضاء
        dt = datetime.fromisoformat(f["fixture"]["date"].replace('Z', '+00:00'))
        time_str = dt.astimezone(timezone(timedelta(hours=1))).strftime("%H:%M")
        
        sections[target]["leagues"][lname]["matches"].append({
            "home": f["teams"]["home"]["name"], "hLogo": f["teams"]["home"]["logo"],
            "away": f["teams"]["away"]["name"], "aLogo": f["teams"]["away"]["logo"],
            "time": time_str, "status": status,
            "score": f"{f['goals']['home']}-{f['goals']['away']}" if f["goals"]["home"] is not None else None
        })
        
    return [ {"title": v["title"], "leagues": list(v["leagues"].values())} for v in sections.values() if v["leagues"] ]

def update_wp(day_type, data):
    slugs = {"yesterday": "matches-yesterday", "today": "matches-today", "tomorrow": "matches-tomorrow"}
    
    # تحويل البيانات لـ Base64 لضمان عبورها من فلاتر ووردبريس
    json_bytes = json.dumps(data, ensure_ascii=False).encode('utf-8')
    b64_data = base64.b64encode(json_bytes).decode('utf-8')
    
    content = HTML_TEMPLATE.replace("__B64_DATA__", b64_data)
    for d in ["yesterday", "today", "tomorrow"]:
        active_class = "active" if day_type == d else ""
        content = content.replace(f"__ACT_{d.upper()}__", active_class)
        
    headers = get_wp_headers()
    r = requests.get(f"{WP_URL}/wp-json/wp/v2/pages", params={"slug": slugs[day_type]}, headers=headers)
    
    if r.status_code == 200 and r.json():
        pid = r.json()[0]["id"]
        requests.post(f"{WP_URL}/wp-json/wp/v2/pages/{pid}", headers=headers, json={"content": content})
        print(f"✅ Updated: {slugs[day_type]}")

if __name__ == "__main__":
    # تشغيل الدورة لليوم والأمس والغد
    now = datetime.now(timezone(timedelta(hours=1)))
    for d_name, offset in {"yesterday": -1, "today": 0, "tomorrow": 1}.items():
        date_str = (now + timedelta(days=offset)).strftime("%Y-%m-%d")
        raw = fetch_data(date_str)
        final = organize_matches(raw)
        update_wp(d_name, final)
