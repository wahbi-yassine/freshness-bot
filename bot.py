# bot.py  (Elite+++ Stable-by-Design)
import os
import json
import base64
import requests
from datetime import datetime, timedelta

try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except ImportError:
    from backports.zoneinfo import ZoneInfo  # if you ever need it locally


# =====================================================
# 1) CONFIG
# =====================================================
ARAB_LEAGUES = [200, 307, 233, 531, 12, 17, 202, 141, 143]
EUROPE_LEAGUES = [39, 140, 135, 78, 61, 2, 3]
NATIONS_LEAGUES = [1, 4, 9, 10, 20, 21, 42]

WP_URL = os.environ.get("WP_URL", "").strip().rstrip("/")
WP_USER = os.environ.get("WP_USER", "").strip()
WP_APP_PASSWORD = os.environ.get("WP_APP_PASSWORD", "").strip()
FOOTBALL_API_KEY = os.environ.get("FOOTBALL_API_KEY", "").strip()

MA_TZ = ZoneInfo("Africa/Casablanca")
API_URL = "https://v3.football.api-sports.io/fixtures"


def require_env():
    missing = []
    for k, v in {
        "WP_URL": WP_URL,
        "WP_USER": WP_USER,
        "WP_APP_PASSWORD": WP_APP_PASSWORD,
        "FOOTBALL_API_KEY": FOOTBALL_API_KEY,
    }.items():
        if not v:
            missing.append(k)
    if missing:
        raise SystemExit(f"Missing env vars: {', '.join(missing)}")


def get_wp_headers():
    # Remove spaces that sometimes get introduced in GitHub secrets copy/paste
    clean_pwd = WP_APP_PASSWORD.replace(" ", "")
    auth_str = f"{WP_USER}:{clean_pwd}"
    token = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")
    return {
        "Authorization": f"Basic {token}",
        "Content-Type": "application/json; charset=utf-8",
        "Accept": "application/json",
        "User-Agent": "ys-football-bot/elite+++",
    }


# =====================================================
# 2) STABLE UI TEMPLATE (JSON in <script type="application/json">)
# =====================================================
HTML_TEMPLATE = r"""<div id="ys-main-app" class="ys-widget-ui" dir="rtl">
  <div class="ys-tabs">
    <a href="/matches-yesterday/" class="ys-tab-btn __ACT_YESTERDAY__">الأمس</a>
    <a href="/matches-today/" class="ys-tab-btn __ACT_TODAY__">مباريات اليوم</a>
    <a href="/matches-tomorrow/" class="ys-tab-btn __ACT_TOMORROW__">الغد</a>
  </div>

  <!-- Stable storage: REAL JSON (no Base64) -->
  <script id="ys-payload" type="application/json">__JSON_DATA__</script>

  <div id="ys-view"><div class="ys-loader">جاري تحديث النتائج...</div></div>
</div>

<script>
(function(){
  let tries = 0;
  const REFRESH_INTERVAL = 10 * 60 * 1000; // 10 minutes

  // Escape text nodes to prevent HTML injection
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({
    "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"
  }[c]));

  // Allow only http/https URLs in src
  const safeUrl = u => {
    u = String(u ?? "").trim();
    return (/^https?:\/\/[^ "]+$/i).test(u) ? u : "";
  };

  function start(){
    const payload = document.getElementById("ys-payload");
    const view = document.getElementById("ys-view");

    if (!payload || !view) {
      if (tries++ < 20) return setTimeout(start, 250);
      console.error("YS: DOM elements missing (#ys-payload/#ys-view)");
      return;
    }

    try {
      const raw = (payload.textContent || "").trim();
      if (raw.length < 5) throw new Error("Payload empty/too short");

      const data = JSON.parse(raw);
      if (!Array.isArray(data) || data.length === 0) {
        view.innerHTML = '<div class="ys-no-data">لا توجد مباريات هامة متوفرة حالياً</div>';
        return;
      }

      let html = "";
      for (const cat of data) {
        html += `<div class="ys-cat-header">${esc(cat.title)}</div>`;

        for (const lg of (cat.leagues || [])) {
          const lgLogo = safeUrl(lg.logo);
          html += `<div class="ys-lg-box">
            <div class="ys-lg-head">
              ${lgLogo ? `<img src="${lgLogo}" width="18" loading="lazy" referrerpolicy="no-referrer">` : ""}
              ${esc(lg.name)}
            </div>
          `;

          const matches = Array.isArray(lg.matches) ? lg.matches : [];
          html += matches.map(m => {
            const hLogo = safeUrl(m.hLogo);
            const aLogo = safeUrl(m.aLogo);
            const status = String(m.status || "scheduled");
            const scoreText = (status === "scheduled") ? (m.time || "") : (m.score || "0-0");
            const statText = (status === "live") ? "مباشر" : (status === "finished" ? "انتهت" : "قريباً");

            return `<div class="ys-match">
              <div class="ys-team h">
                <span>${esc(m.home)}</span>
                ${hLogo ? `<img src="${hLogo}" width="22" loading="lazy" referrerpolicy="no-referrer">` : ""}
              </div>

              <div class="ys-info">
                <div class="ys-score ${esc(status)}">${esc(scoreText)}</div>
                <div class="ys-stat ${esc(status)}">${esc(statText)}</div>
              </div>

              <div class="ys-team a">
                ${aLogo ? `<img src="${aLogo}" width="22" loading="lazy" referrerpolicy="no-referrer">` : ""}
                <span>${esc(m.away)}</span>
              </div>
            </div>`;
          }).join("");

          html += `</div>`;
        }
      }

      view.innerHTML = html;

      // Cache-busting refresh (optional; reduce pressure vs 5-min)
      setTimeout(() => {
        const url = new URL(location.href);
        url.searchParams.set("cache_bust", Date.now().toString());
        location.href = url.toString();
      }, REFRESH_INTERVAL);

    } catch (e) {
      console.error("YS: render error", e);
      view.innerHTML = '<div class="ys-no-data">❌ تعذر عرض البيانات.</div>';
    }
  }

  if (document.readyState === "complete" || document.readyState === "interactive") start();
  else document.addEventListener("DOMContentLoaded", start);
})();
</script>

<style>
.ys-widget-ui { max-width: 800px; margin: 20px auto; background: #fff; border-radius: 12px; padding: 12px; font-family: system-ui, sans-serif; box-shadow: 0 10px 30px rgba(0,0,0,0.05); border: 1px solid #f0f0f0; }
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
</style>
"""


# =====================================================
# 3) API + PROCESSING
# =====================================================
def fetch_data(date_str: str):
    print(f"📡 API Fetch: {date_str}")
    headers = {"x-apisports-key": FOOTBALL_API_KEY, "Accept": "application/json"}
    try:
        r = requests.get(
            API_URL,
            headers=headers,
            params={"date": date_str, "timezone": "Africa/Casablanca"},
            timeout=25,
        )
        r.raise_for_status()
        data = r.json().get("response", [])
        print(f"📦 fixtures={len(data)}")
        return data
    except requests.HTTPError as e:
        # Show useful context if possible
        status = getattr(e.response, "status_code", None)
        text = getattr(e.response, "text", "")[:400]
        print(f"❌ API HTTP Error: {status} {text}")
        return []
    except Exception as e:
        print(f"❌ API Error: {e}")
        return []


def classify_league(l_id: int):
    if l_id in ARAB_LEAGUES:
        return "arab"
    if l_id in EUROPE_LEAGUES:
        return "euro"
    if l_id in NATIONS_LEAGUES:
        return "intl"
    return None


def organize_matches(raw_fixtures):
    sections = {
        "arab": {"title": "🏆 البطولات العربية والقارية", "leagues": {}},
        "euro": {"title": "🇪🇺 الدوريات الأوروبية الكبرى", "leagues": {}},
        "intl": {"title": "🌍 المنتخبات والبطولات الدولية", "leagues": {}},
    }

    for f in raw_fixtures:
        try:
            l_id = f["league"]["id"]
            target = classify_league(l_id)
            if not target:
                continue

            lname = f["league"]["name"]
            leagues = sections[target]["leagues"]
            if lname not in leagues:
                leagues[lname] = {
                    "name": lname,
                    "logo": f["league"]["logo"],
                    "matches": [],
                }

            short = f["fixture"]["status"]["short"]
            status = "scheduled"
            if short in ["FT", "AET", "PEN"]:
                status = "finished"
            elif short in ["1H", "HT", "2H", "LIVE", "BT"]:
                status = "live"

            # Real timezone conversion to Africa/Casablanca
            dt = datetime.fromisoformat(f["fixture"]["date"].replace("Z", "+00:00")).astimezone(MA_TZ)
            time_str = dt.strftime("%H:%M")

            goals_home = f.get("goals", {}).get("home")
            goals_away = f.get("goals", {}).get("away")
            score = f"{goals_home}-{goals_away}" if goals_home is not None and goals_away is not None else None

            leagues[lname]["matches"].append(
                {
                    "home": f["teams"]["home"]["name"],
                    "hLogo": f["teams"]["home"]["logo"],
                    "away": f["teams"]["away"]["name"],
                    "aLogo": f["teams"]["away"]["logo"],
                    "time": time_str,
                    "status": status,
                    "score": score,
                }
            )
        except Exception:
            # Skip malformed fixture safely
            continue

    # Convert leagues dict -> list, and keep only non-empty sections
    out = []
    for key in ["arab", "euro", "intl"]:
        leagues_list = list(sections[key]["leagues"].values())
        if leagues_list:
            out.append({"title": sections[key]["title"], "leagues": leagues_list})
    return out


# =====================================================
# 4) WORDPRESS UPDATE
# =====================================================
def build_content(day_type: str, data):
    # Inject JSON directly into <script type="application/json">
    json_str = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    # Prevent rare </script> termination if it ever appeared in strings
    json_str = json_str.replace("</script", "<\\/script")

    content = HTML_TEMPLATE.replace("__JSON_DATA__", json_str)

    for d in ["yesterday", "today", "tomorrow"]:
        content = content.replace(f"__ACT_{d.upper()}__", "active" if day_type == d else "")
    return content


def update_wp(day_type: str, data):
    slugs = {"yesterday": "matches-yesterday", "today": "matches-today", "tomorrow": "matches-tomorrow"}
    slug = slugs[day_type]
    headers = get_wp_headers()

    # Find page ID by slug
    r = requests.get(f"{WP_URL}/wp-json/wp/v2/pages", params={"slug": slug}, headers=headers, timeout=20)
    if r.status_code != 200 or not r.json():
        print(f"❌ WP Page Missing/Unreachable: {slug} (status={r.status_code})")
        return False

    pid = r.json()[0]["id"]
    content = build_content(day_type, data)

    res = requests.post(
        f"{WP_URL}/wp-json/wp/v2/pages/{pid}",
        headers=headers,
        json={"content": content},
        timeout=30,
    )

    if res.status_code == 200:
        print(f"✅ WP Updated: {slug} (sections={len(data)})")
        return True

    print(f"❌ WP Update Error ({res.status_code}): {res.text[:500]}")
    return False


# =====================================================
# 5) MAIN
# =====================================================
def main():
    require_env()

    now = datetime.now(MA_TZ)
    plan = {"yesterday": -1, "today": 0, "tomorrow": 1}

    for d_name, offset in plan.items():
        date_str = (now + timedelta(days=offset)).strftime("%Y-%m-%d")
        raw = fetch_data(date_str)
        final = organize_matches(raw)
        print(f"🧩 date={date_str} day={d_name} sections={len(final)}")
        ok = update_wp(d_name, final)
        if not ok:
            # Fail fast so GitHub Actions run shows red (no silent success)
            raise SystemExit(1)


if __name__ == "__main__":
    main()
