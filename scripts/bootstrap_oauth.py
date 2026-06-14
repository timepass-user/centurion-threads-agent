"""One-time setup: turn a Meta app + Threads account into a 60-day long-lived
access token. Run locally once; everything after this is autonomous.

Usage:
    python scripts/bootstrap_oauth.py APP_ID APP_SECRET REDIRECT_URI
"""
import sys
import urllib.parse

import requests

SCOPES = ",".join([
    "threads_basic",
    "threads_content_publish",
    "threads_read_replies",
    "threads_manage_replies",
    "threads_manage_insights",
    "threads_keyword_search",
])


def main():
    app_id, app_secret, redirect_uri = sys.argv[1:4]

    auth_url = ("https://threads.net/oauth/authorize?" + urllib.parse.urlencode({
        "client_id": app_id, "redirect_uri": redirect_uri,
        "scope": SCOPES, "response_type": "code",
    }))
    print(f"\n1) Open this URL, log in as the agent's account, approve:\n\n{auth_url}\n")
    code = input("2) Paste the ?code= value from the redirect URL: ").strip().rstrip("#_")

    r = requests.post("https://graph.threads.net/oauth/access_token", data={
        "client_id": app_id, "client_secret": app_secret,
        "grant_type": "authorization_code", "redirect_uri": redirect_uri, "code": code,
    }, timeout=30).json()
    short_token, user_id = r["access_token"], r["user_id"]

    r = requests.get("https://graph.threads.net/access_token", params={
        "grant_type": "th_exchange_token", "client_secret": app_secret,
        "access_token": short_token,
    }, timeout=30).json()

    print("\n=== Save these as GitHub repo secrets ===")
    print(f"THREADS_USER_ID={user_id}")
    print(f"THREADS_ACCESS_TOKEN={r['access_token']}   (valid ~60 days; CI auto-refreshes weekly)")


if __name__ == "__main__":
    main()
