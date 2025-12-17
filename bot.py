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

# Prefer an Application Password for WP REST (WP Admin → Users → Profile → Application Passwords)
WP_APP_PASSWORD = os.environ.get("WP_APP_PASSWORD", "").strip()

# Fallback (often blocked by hosts; do NOT rely on it)
WP_PASSWORD = os.environ.get("WP_PASSWORD", "").strip()

# If you use JWT plugin, set this to a valid token string: "eyJ0eXAiOiJKV1QiLCJhbGciOi..."
WP_JWT_TOKEN = os.environ.get("WP_JWT_TOKEN", "").strip()

# Optional: if your WordPress is behind aggressive WAF, you can set a referer
WP_REFERER = os.environ.get("WP_REFERER", WP_BASE).strip()

# =====================================================
# API-FOOTBALL (NEW DASHBOARD)
# =====================================================
FOOTBALL_API_KEY = os.environ.get("FOOTBALL_API_KEY", "").strip()
FOOTBALL_API_URL = "https://v3.football.api-sports.io/fixtures"

# =====================================================
# HTTP SESSION (reused connections)
# =====================================================
SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "freshness-bot/2.0",
    "Accept": "application/json",
})

# =====================================================
# WORDPRESS AUTH / REQUEST HELPERS
# =====================================================

def _basic_auth_header(user: str, pw: str) -> dict:
    token = base64.b64encode(f"{user}:{pw}".encode("utf-8")).decode("utf-8")
    return {"Authorization": f"Basic {token}"}

def wp_headers() -> dict:
    """
    Builds headers for WP REST calls.
    Priority:
      1) JWT token (Bearer)
      2) Application Password (Basic)
      3) Password (Basic - often blocked)
    """
    headers = {
        "Content-Type": "application/json",
        "Referer": WP_REFERER,
    }

    if WP_JWT_TOKEN:
        headers["Authorization"] = f"Bearer {WP_JWT_TOKEN}"
        return headers

    if WP_USER and WP_APP_PASSWORD:
        headers.update(_basic_auth_header(WP_USER, WP_APP_PASSWORD))
        return headers

    if WP_USER and WP_PASSWORD:
        headers.update(_basic_auth_header(WP_USER, WP_PASSWORD))
        return headers

    return headers

def wp_request(method: str, path: str, *, params=None, json=None, timeout=30, retries=2):
    """
    Single WP request function with retries + diagnostics.
    """
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

            # Retry on transient errors
            if r.status_code in (429, 500, 502, 503, 504) and attempt < retries:
                time.sleep(1.5 * (attempt + 1))
                continue

            # Helpful output on auth/permission problems
            if r.status_code in (401, 403):
                print("\n--- WORDPRESS AUTH ERROR DIAGNOSTICS ---")
                print("URL:", url)
                print("Status:", r.status_code)
                # WP usually returns JSON with code/message
                print("Body (first 600 chars):", r.text[:600])
                print("Auth mode:",
                      "JWT" if WP_JWT_TOKEN else
                      "APP_PASSWORD" if WP_APP_PASSWORD else
                      "PASSWORD" if WP_PASSWORD else
                      "NONE")
                print("User set:", bool(WP_USER))
                print("WP_BASE:", WP_BASE)
                print("WP_API:", WP_API)
                print("---------------------------------------\n")

            r.raise_for_status()
            return r

        except requests.RequestException as e:
            last_exc = e
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
            else:
                raise

    raise last_exc  # should never hit

def test_wp_auth():
    """
    Strong auth check: /users/me requires authentication.
    """
    r = wp_request("GET", "/users/me")
    me = r.json()
    print("WP auth OK. User:", me.get("name"), "| ID:", me.get("id"))

def ensure_can_create_posts():
    """
    Optional capability check: some users can auth but cannot publish.
    """
    # This tries to create a draft then deletes it (trash).
    payload = {"title": "auth-check", "status": "draft", "content": "auth-check"}
    r = wp_request("POST", "/posts", json=payload)
    post_id = r.json().get("id")
    print("Post create OK. Draft ID:", post_id)

    # Move to trash (cleanup)
    wp_request("DELETE", f"/posts/{post_id}", params={"force": True})
    print("Cleanup OK (deleted draft).")

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
    data = r.json()
    return data.get("response", [])

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
        # If your user cannot publish, switch to "draft" until permissions are fixed.
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

    # 1) Verify WordPress authentication FIRST
    test_wp_auth()

    # Optional: also confirm permissions to create posts
    # ensure_can_create_posts()

    # 2) Fetch fixtures
    fixtures = get_fixtures()
    print(f"Fetched {len(fixtures)} fixtures.")

    # 3) Publish (free-tier safe)
    for match in fixtures[:5]:
        created = create_or_update_post(match)
        print("OK:", created.get("slug"), "| status:", created.get("status"))

    print("Run complete.")

if __name__ == "__main__":
    main()
