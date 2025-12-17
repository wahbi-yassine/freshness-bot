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
WP_APP_PASSWORD = os.environ.get("WP_APP_PASSWORD", "").strip()
WP_JWT_TOKEN = os.environ.get("WP_JWT_TOKEN", "").strip()

WP_REFERER = WP_BASE

# =====================================================
# API-FOOTBALL
# =====================================================
FOOTBALL_API_KEY = os.environ.get("FOOTBALL_API_KEY", "").strip()
FOOTBALL_API_URL = "https://v3.football.api-sports.io/fixtures"

# =====================================================
# HTTP SESSION
# =====================================================
SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "freshness-bot/3.0",
    "Accept": "application/json",
})

# =====================================================
# ENV CHECK (SAFE)
# =====================================================
def print_env_status():
    print("ENV CHECK:")
    print(" - WP_URL:", bool(WP_BASE))
    print(" - WP_USER:", bool(WP_USER))
    print(" - WP_APP_PASSWORD:", bool(WP_APP_PASSWORD))
    print(" - WP_JWT_TOKEN:", bool(WP_JWT_TOKEN))
    print(" - FOOTBALL_API_KEY:", bool(FOOTBALL_API_KEY))

def assert_auth_config():
    if WP_JWT_TOKEN:
        return
    if WP_USER and WP_APP_PASSWORD:
        return
    raise RuntimeError(
        "Missing WordPress auth. Set WP_APP_PASSWORD (recommended) "
        "or WP_JWT_TOKEN."
    )

# =====================================================
# AUTH HELPERS
# =====================================================
def basic_auth_header(user: str, pw: str) -> str:
    # IMPORTANT: remove spaces from application password
    pw = pw.replace(" ", "")
    token = base64.b64encode(f"{user}:{pw}".encode("utf-8")).decode("utf-8")
    return f"Basic {token}"

def auth_modes():
    modes = []
    if WP_JWT_TOKEN:
        modes.append(("JWT", f"Bearer {WP_JWT_TOKEN}"))
    if WP_USER and WP_APP_PASSWORD:
        modes.append(("APP_PASSWORD", basic_auth_header(WP_USER, WP_APP_PASSWORD)))
    return modes

def headers_with(auth_value: str):
    return {
        "Authorization": auth_value,
        "Content-Type": "application/json",
        "Referer": WP_REFERER,
    }

# =====================================================
# WORDPRESS REQUEST WRAPPER
# =====================================================
def wp_request(method: str, path: str, *, params=None, json=None, retries=2):
    url = urljoin(WP_API + "/", path.lstrip("/"))
    last_error = None

    for mode_name, auth_value in auth_modes():
        for attempt in range(retries + 1):
            try:
                r = SESSION.request(
                    method=method,
                    url=url,
                    headers=headers_with(auth_value),
                    params=params,
                    json=json,
                    timeout=30,
                )

                if r.status_code in (429, 500, 502, 503, 504) and attempt < retries:
                    time.sleep(1.5 * (attempt + 1))
                    continue

                if r.status_code in (401, 403):
                    print("\n--- WORDPRESS AUTH ERROR ---")
                    print("Auth mode:", mode_name)
                    print("Status:", r.status_code)
                    print("Body:", r.text[:400])
                    print("----------------------------\n")
                    last_error = r
                    break

                r.raise_for_status()
                return r

            except requests.RequestException as e:
                last_error = e
                break

    if hasattr(last_error, "raise_for_status"):
        last_error.raise_for_status()
    raise RuntimeError("All WordPress auth modes failed.")

def test_wp_auth():
    r = wp_request("GET", "/users/me")
    me = r.json()
    print("WP auth OK →", me.get("name"), "| ID:", me.get("id"))

# =====================================================
# API-FOOTBALL
# =====================================================
def get_fixtures():
    if not FOOTBALL_API_KEY:
        raise RuntimeError("FOOTBALL_API_KEY missing.")

    headers = {"x-apisports-key": FOOTBALL_API_KEY}
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    r = requests.get(
        FOOTBALL_API_URL,
        headers=headers,
        params={"date": today},
        timeout=30,
    )

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

    payload = {
        "title": f"{home} vs {away} Live Score & Updates",
        "slug": slug,
        "status": "publish",
        "comment_status": "closed",
        "content": f"""
<h2>Match Details</h2>
<ul>
  <li><strong>Teams:</strong> {home} vs {away}</li>
  <li><strong>Date:</strong> {date}</li>
  <li><strong>Status:</strong> {status}</li>
  <li><strong>Stadium:</strong> {venue}</li>
</ul>
<p>Automatic live score and match updates.</p>
""".strip(),
    }

    existing_id = get_post_id_by_slug(slug)

    if existing_id:
        print("Updating", slug)
        r = wp_request("POST", f"/posts/{existing_id}", json=payload)
    else:
        print("Creating", slug)
        r = wp_request("POST", "/posts", json=payload)

    return r.json()

# =====================================================
# MAIN
# =====================================================
def main():
    print("Starting freshness run...")
    print_env_status()
    assert_auth_config()
    test_wp_auth()

    fixtures = get_fixtures()
    print(f"Fetched {len(fixtures)} fixtures.")

    for match in fixtures[:5]:
        post = create_or_update_post(match)
        print("OK:", post.get("slug"))

    print("Run complete.")

if __name__ == "__main__":
    main()
