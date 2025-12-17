import os
import requests
import base64
import time
from datetime import datetime, timezone
from urllib.parse import urljoin

# =====================================================
# WORDPRESS CONFIG
# =====================================================
WP_BASE = os.environ["WP_URL"].rstrip("/")
WP_API = WP_BASE + "/wp-json/wp/v2"

WP_USER = os.environ.get("WP_USER", "").strip()

# Prefer ONE of these:
WP_APP_PASSWORD = os.environ.get("WP_APP_PASSWORD", "").strip()   # recommended
WP_JWT_TOKEN = os.environ.get("WP_JWT_TOKEN", "").strip()         # if using JWT plugin

# Normal password is NOT reliable for WP REST; keep only as legacy fallback
WP_PASSWORD = os.environ.get("WP_PASSWORD", "").strip()

WP_REFERER = os.environ.get("WP_REFERER", WP_BASE).strip()

# =====================================================
# API-FOOTBALL (NEW DASHBOARD)
# =====================================================
FOOTBALL_API_KEY = os.environ.get("FOOTBALL_API_KEY", "").strip()
FOOTBALL_API_URL = "https://v3.football.api-sports.io/fixtures"

# =====================================================
# HTTP SESSION
# =====================================================
SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "freshness-bot/2.1",
    "Accept": "application/json",
})

# =====================================================
# AUTH HELPERS
# =====================================================

def _basic_auth_value(user: str, pw: str) -> str:
    token = base64.b64encode(f"{user}:{pw}".encode("utf-8")).decode("utf-8")
    return f"Basic {token}"

def _headers_with(auth_header_value: str | None) -> dict:
    h = {
        "Content-Type": "application/json",
        "Referer": WP_REFERER,
    }
    if auth_header_value:
        h["Authorization"] = auth_header_value
    return h

def available_auth_modes():
    """
    List of (name, Authorization header value) in priority order.
    """
    modes = []
    if WP_JWT_TOKEN:
        modes.append(("JWT", f"Bearer {WP_JWT_TOKEN}"))
    if WP_USER and WP_APP_PASSWORD:
        modes.append(("APP_PASSWORD", _basic_auth_value(WP_USER, WP_APP_PASSWORD)))
    # Legacy fallback (usually rejected). Keep only if you insist:
    if WP_USER and WP_PASSWORD:
        modes.append(("PASSWORD", _basic_auth_value(WP_USER, WP_PASSWORD)))
    return modes

def assert_auth_config():
    modes = available_auth_modes()
    if not modes:
        raise RuntimeError(
            "Missing WordPress auth. Set WP_JWT_TOKEN OR (WP_USER + WP_APP_PASSWORD). "
            "Avoid WP_PASSWORD for REST."
        )

# =====================================================
# WORDPRESS REQUEST WRAPPER
# =====================================================

def wp_request(method: str, path: str, *, params=None, json=None, timeout=30, retries=2):
    url = urljoin(WP_API + "/", path.lstrip("/"))
    modes = available_auth_modes()

    last_error = None

    for mode_name, auth_value in modes:
        for attempt in range(retries + 1):
            try:
                r = SESSION.request(
                    method=method.upper(),
                    url=url,
                    headers=_headers_with(auth_value),
                    params=params,
                    json=json,
                    timeout=timeout,
                )

                if r.status_code in (429, 500, 502, 503, 504) and attempt < retries:
                    time.sleep(1.5 * (attempt + 1))
                    continue

                if r.status_code in (401, 403):
                    print("\n--- WORDPRESS AUTH ERROR DIAGNOSTICS ---")
                    print("URL:", url)
                    print("Status:", r.status_code)
                    print("Auth mode attempted:", mode_name)
                    print("Body (first 400 chars):", r.text[:400])
                    print("---------------------------------------\n")
                    last_error = (mode_name, r)
                    break

                r.raise_for_status()
                return r

            except requests.RequestException as e:
                last_error = (mode_name, e)
                if attempt < retries:
                    time.sleep(1.5 * (attempt + 1))
                else:
                    break

    if isinstance(last_error, tuple) and len(last_error) == 2:
        mode, err = last_error
        if hasattr(err, "raise_for_status"):
            err.raise_for_status()
        raise RuntimeError(f"All WP auth modes failed. Last mode: {mode}. Error: {err}")

    raise RuntimeError("All WP auth modes failed.")

def test_wp_auth():
    r = wp_request("GET", "/users/me")
    me = r.json()
    print("WP auth OK. User:", me.get("name"), "| ID:", me.get("id"))

# =====================================================
# API-FOOTBALL
# =====================================================

def get_fixtures():
    if not FOOTBALL_API_KEY:
        raise RuntimeError("FOOTBALL_API_KEY is empty or missing.")

    headers = {"x-apisports-key": FOOTBALL_API_KEY}
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    r = requests.get(
        FOOTBALL_API_URL,
        headers=headers,
        params={"date": today},
        timeout=30
    )

    if r.status_code in (401, 403):
        raise RuntimeError(f"API-Football auth failed ({r.status_code}): {r.text[:300]}")

    r.raise_for_status()
    return r.json().get("response", [])

# =====================================================
# WORDPRESS POSTS
# =====================================================

def get_post_id_by_slug(slug: str):
    r = wp_request("GET", "/posts", params={"slug": slug})
    posts = r.json()
    return posts[0]["id"] if posts else None

def create_or_update_post(match):
    match_id = match["fixture"]["id"]
    slug = f"match-{match_id}"

    home = match["teams"]["home"]["name"]
    away = match["teams"]["away"]["name"]
    date = match["fixture"]["date"]
    status = match["fixture"]["status"]["long"]
    venue = match.get("fixture", {}).get("venue", {}).get("name", "TBD")

    title = f"{home} vs {away} Live Score & Updates"

    content = f"""
<h2>Match Details</h2>
<ul>
  <li><strong>Teams:</strong> {home} vs {away}</li>
  <li><strong>Date:</strong> {date}</li>
  <li><strong>Status:</strong> {status}</li>
  <li><strong>Stadium:</strong> {venue}</li>
</ul>
<p>Automatic live score and match updates.</p>
""".strip()

    payload = {
        "title": title,
        "slug": slug,
        "content": content,
        "status": "publish",
        "comment_status": "closed",
    }

    existing_id = get_post_id_by_slug(slug)

    if existing_id:
        print(f"Updating {slug} (ID {existing_id})")
        r = wp_request("POST", f"/posts/{existing_id}", json=payload)
    else:
        print(f"Creating {slug}")
        r = wp_request("POST", "/posts", json=payload)

    return r.json()

# =====================================================
# MAIN
# =====================================================

def main():
    print("Starting freshness run...")

    assert_auth_config()
    test_wp_auth()

    fixtures = get_fixtures()
    print(f"Fetched {len(fixtures)} fixtures.")

    for match in fixtures[:5]:
        created = create_or_update_post(match)
        print("OK:", created.get("slug"), "| status:", created.get("status"))

    print("Run complete.")

if __name__ == "__main__":
    main()
