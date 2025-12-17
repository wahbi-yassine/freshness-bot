import os
import requests
import base64
import time
from datetime import datetime, timezone
from urllib.parse import urljoin

# =====================================================
# WORDPRESS CONFIG (APP PASSWORD ONLY)
# =====================================================
WP_BASE = os.environ["WP_URL"].rstrip("/")
WP_API = WP_BASE + "/wp-json/wp/v2"

WP_USER = os.environ.get("WP_USER", "").strip()
WP_APP_PASSWORD = os.environ.get("WP_APP_PASSWORD", "").strip()

# =====================================================
# API-FOOTBALL
# =====================================================
FOOTBALL_API_KEY = os.environ.get("FOOTBALL_API_KEY", "").strip()
FOOTBALL_API_URL = "https://v3.football.api-sports.io/fixtures"

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "freshness-bot/4.0",
    "Accept": "application/json",
})

# =====================================================
# SAFE ENV CHECK
# =====================================================
def print_env_status():
    print("ENV CHECK:")
    print(" - WP_URL:", bool(WP_BASE))
    print(" - WP_USER:", bool(WP_USER))
    print(" - WP_APP_PASSWORD:", bool(WP_APP_PASSWORD))
    print(" - FOOTBALL_API_KEY:", bool(FOOTBALL_API_KEY))

def assert_auth_config():
    if not (WP_USER and WP_APP_PASSWORD):
        raise RuntimeError(
            "Missing WordPress auth. Set WP_USER and WP_APP_PASSWORD (Application Password)."
        )

def basic_auth_header(user: str, app_pw: str) -> str:
    # WordPress shows application passwords with spaces; remove them safely.
    app_pw = app_pw.replace(" ", "")
    token = base64.b64encode(f"{user}:{app_pw}".encode("utf-8")).decode("utf-8")
    return f"Basic {token}"

def wp_headers():
    return {
        "Authorization": basic_auth_header(WP_USER, WP_APP_PASSWORD),
        "Content-Type": "application/json",
        "Referer": WP_BASE,
    }

def wp_request(method: str, path: str, *, params=None, json=None, timeout=30, retries=2):
    url = urljoin(WP_API + "/", path.lstrip("/"))
    last_exc = None

    for attempt in range(retries + 1):
        try:
            r = SESSION.request(
                method=method.upper(),
                url=url,
                headers=wp_headers(),
                params=params,
                json=json,
                timeout=timeout,
            )

            if r.status_code in (429, 500, 502, 503, 504) and attempt < retries:
                time.sleep(1.5 * (attempt + 1))
                continue

            if r.status_code in (401, 403):
                print("\n--- WORDPRESS AUTH ERROR ---")
                print("URL:", url)
                print("Status:", r.status_code)
                print("Body:", r.text[:500])
                print("----------------------------\n")

            r.raise_for_status()
            return r

        except requests.RequestException as e:
            last_exc = e
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
            else:
                raise

    raise last_exc  # should not happen

def test_wp_auth():
    r = wp_request("GET", "/users/me")
    me = r.json()
    print("WP auth OK →", me.get("name"), "| ID:", me.get("id"), "| username:", me.get("slug"))

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
        timeout=30,
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

    payload = {
        "title": f"{home} vs {away} Live Score & Updates",
        "slug": slug,
        "status": "publish",        # If author cannot publish on your site, change to "draft"
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
    print_env_status()
    assert_auth_config()

    # 1) Verify WordPress auth first
    test_wp_auth()

    # 2) Fetch fixtures
    fixtures = get_fixtures()
    print(f"Fetched {len(fixtures)} fixtures.")

    # 3) Publish a few
    for match in fixtures[:5]:
        post = create_or_update_post(match)
        print("OK:", post.get("slug"), "| status:", post.get("status"))

    print("Run complete.")

if __name__ == "__main__":
    main()
