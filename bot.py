import os
import requests
import base64
import json
from datetime import datetime, timezone, timedelta

# =====================================================
# 1. إعدادات الدوريات (التركيز العربي + الأوروبي + المنتخبات)
# =====================================================
# أضفت لك كل البطولات العربية والنهائيات لضمان عدم ضياع أي مباراة كبرى
LEAGUES_CONFIG = {
    "🏆 بطولات عربية وقارية": [200, 307, 233, 531, 12, 17, 202, 301], 
    "🇪🇺 الدوريات الأوروبية الكبرى": [39, 140, 135, 78, 61, 2, 3],
    "🌍 المنتخبات والبطولات الدولية": [1, 4, 9, 10, 20, 21, 42]
}

WP_URL = os.environ.get("WP_URL", "").rstrip("/")
WP_API = f"{WP_URL}/wp-json/wp/v2"
WP_USER = os.environ.get("WP_USER", "")
WP_APP_PASSWORD = os.environ.get("WP_APP_PASSWORD", "")
FOOTBALL_API_KEY = os.environ.get("FOOTBALL_API_KEY", "")

def get_wp_headers():
    auth = f"{WP_USER}:{WP_APP_PASSWORD.replace(' ', '')}"
    token = base64.b64encode(auth.encode()).decode()
    return {"Authorization": f"Basic {token}", "Content-Type": "application/json"}

# =====================================================
# 2. القالب المستوحى من الـ Widget (تصميم عصري جداً)
# =====================================================
HTML_TEMPLATE = r"""<div id="ys-widget-container" class="ys-widget" dir="rtl">
    <div class="ys-header-tabs">
        <a href="/matches-yesterday/" class="ys-tab __ACT_YESTERDAY__">الأمس</a>
        <a href="/matches-today/" class="ys-tab __ACT_TODAY__">اليوم</a>
        <a href="/matches-tomorrow/" class="ys-tab __ACT_TOMORROW__">الغد</a>
    </div>

    <div id="ys-data-bridge" style="display:none !important;">__B64_DATA__</div>

    <div id="ys-render-target">
        <div class="ys-loading">جاري ترتيب جدول المباريات...</div>
    </div>
</div>

<script>
(function() {
    function decodeData(b64) {
        try {
            const bin = atob(b64);
            const bytes = new Uint8Array(bin.length);
            for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
            return JSON.parse(new TextDecoder().decode(bytes));
        } catch (e) { return null; }
    }

    function init() {
        const bridge = document.getElementById('ys-data-bridge');
        const target = document.getElementById('ys-render-target');
        if (!bridge) return;

        const data = decodeData(bridge.innerText.trim());
        if (!data || data.length === 0) {
            target.innerHTML = '<div class="ys-empty">لا توجد مباريات هامة مجدولة اليوم</div>';
            return;
        }

        let html = '';
        data.forEach(group => {
            html += `<div class="ys-group-title">${group.category}</div>`;
            group.leagues.forEach(lg => {
                html += `
                <div class="ys-league-card">
                    <div class="ys-league-info"><img src="${lg.logo}" width="18"> ${lg.name}</div>
                    ${lg.matches.map(m => `
                        <div class="ys-match-row">
                            <div class="ys-team ys-home"><span>${m.home}</span><img src="${m.hLogo}" width="22"></div>
                            <div class="ys-score-box">
                                <div class="ys-score ${m.status}">${m.status === 'scheduled' ? m.time : (m.score || '0-0')}</div>
                                <div class="ys-badge ${m.status}">${m.status === 'live' ? 'مباشر' : (m.status === 'finished' ? 'انتهت' : 'قريباً')}</div>
                            </div>
                            <div class="ys-team ys-away"><img src="${m.aLogo}" width="22"><span>${m.away}</span></div>
                        </div>
                    `).join('')}
                </div>`;
            });
        });
        target.innerHTML = html;
    }
    window.addEventListener('DOMContentLoaded', init);
    setTimeout(init, 500); // احتياطي في حال تأخر التحميل
})();
</script>

<style>
.ys-widget { max-width: 800px; margin: auto; background: #fff; border-radius: 12px; padding: 10px; font-family: sans-serif; box-shadow: 0 5px 20px rgba(0,0,0,0.05); }
.ys-header-tabs { display: flex; gap: 5px; margin-bottom: 20px; }
.ys-tab { flex: 1; text-align: center; padding: 12px; background: #f4f4f4; border-radius: 8px; text-decoration: none; color: #666; font-weight: bold; font-size: 14px; }
.ys-tab.active { background: #e60023; color: #fff; }
.ys-group-title { color: #e60023; font-weight: bold; padding: 10px; border-right: 4px solid #e60023; margin: 20px 0 10px; background: #fff5f5; }
.ys-league-card { border: 1px solid #eee; border-radius: 10px; margin-bottom: 15px; overflow: hidden; }
.ys-league-info { background: #f9f9f9; padding: 8px 12px; font-size: 12px; font-weight: bold; border-bottom: 1px solid #eee; display: flex; align-items: center; gap: 8px; }
.ys-match-row { display: flex; align-items: center; padding: 12px; border-bottom: 1px solid #fcfcfc; }
.ys-team { flex: 1; display: flex; align-items: center; gap: 10px; font-size: 13px; font-weight: bold; }
.ys-team.ys-home { justify-content: flex-end; }
.ys-score-box { width: 90px; text-align: center; }
.ys-score { font-size: 18px; font-weight: 900; }
.ys-score.scheduled { font-size: 13px; color: #888; font-weight: normal; }
.ys-badge { font-size: 10px; padding: 2px 6px; border-radius: 4px; display: inline-block; margin-top: 4px; }
.ys-badge.live { background: #ff0000; color: #fff; }
.ys-badge.finished { background: #f0f0f0; color: #999; }
.ys-empty, .ys-loading { padding: 40px; text-align: center; color: #bbb; }
@media (max-width: 480px) { .ys-team span { font-size: 11px; } .ys-score { font-size: 15px; } }
</style>
"""

# =====================================================
# 3. المنطق البرمجي (The Logic)
# =====================================================

def fetch_all_fixtures(date_str):
    print(f"📡 جلب بيانات: {date_str}")
    headers = {"x-apisports-key": FOOTBALL_API_KEY}
    r = requests.get("https://v3.football.api-sports.io/fixtures", headers=headers, params={"date": date_str, "timezone": "Africa/Casablanca"})
    return r.json().get("response", [])

def process_data(fixtures):
    structured = []
    for cat_name, league_ids in LEAGUES_CONFIG.items():
        cat_leagues = {}
        for f in fixtures:
            if f["league"]["id"] in league_ids:
                lname = f["league"]["name"]
                if lname not in cat_leagues:
                    cat_leagues[lname] = {"name": lname, "logo": f["league"]["logo"], "matches": []}
                
                status = "scheduled"
                if f["fixture"]["status"]["short"] in ["FT", "AET", "PEN"]: status = "finished"
                elif f["fixture"]["status"]["short"] in ["1H", "HT", "2H", "LIVE"]: status = "live"
                
                dt = datetime.fromisoformat(f["fixture"]["date"].replace('Z', '+00:00'))
                time_str = dt.astimezone(timezone(timedelta(hours=1))).strftime("%H:%M")

                cat_leagues[lname]["matches"].append({
                    "home": f["teams"]["home"]["name"], "hLogo": f["teams"]["home"]["logo"],
                    "away": f["teams"]["away"]["name"], "aLogo": f["teams"]["away"]["logo"],
                    "time": time_str, "status": status,
                    "score": f"{f['goals']['home']}-{f['goals']['away']}" if f['goals']['home'] is not None else None
                })
        if cat_leagues:
            structured.append({"category": cat_name, "leagues": list(cat_leagues.values())})
    return structured

def update_wp(day_type, data):
    slugs = {"yesterday": "matches-yesterday", "today": "matches-today", "tomorrow": "matches-tomorrow"}
    
    # تحويل البيانات لـ Base64 (هذا هو السر!)
    b64_json = base64.b64encode(json.dumps(data, ensure_ascii=False).encode('utf-8')).decode('utf-8')
    
    content = HTML_TEMPLATE.replace("__B64_DATA__", b64_json)
    for d in ["yesterday", "today", "tomorrow"]:
        content = content.replace(f"__ACT_{d.upper()}__", "active" if day_type == d else "")

    headers = get_wp_headers()
    r = requests.get(f"{WP_API}/pages", params={"slug": slugs[day_type]}, headers=headers)
    if r.status_code == 200 and r.json():
        pid = r.json()[0]["id"]
        requests.post(f"{WP_API}/pages/{pid}", headers=headers, json={"content": content})
        print(f"✅ تم تحديث صفحة: {slugs[day_type]}")

if __name__ == "__main__":
    now = datetime.now(timezone(timedelta(hours=1)))
    for d_name, offset in {"yesterday": -1, "today": 0, "tomorrow": 1}.items():
        date_str = (now + timedelta(days=offset)).strftime("%Y-%m-%d")
        raw_data = fetch_all_fixtures(date_str)
        final_data = process_data(raw_data)
        update_wp(d_name, final_data)
