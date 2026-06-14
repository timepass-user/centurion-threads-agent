"""One-time setup: turn a Meta app + Threads account into a 60-day long-lived
access token. Run locally once; everything after this is autonomous.

Usage:
    python scripts/bootstrap_oauth.py APP_ID APP_SECRET
    # Uses https://localhost/callback — add this URI in Meta app settings first.
"""
import sys
import webbrowser

from oauth_common import REDIRECT_URI, auth_url, exchange_code, update_env


def main():
    app_id, app_secret = sys.argv[1:3]

    print(f"\nAdd this redirect URI in Meta app settings: {REDIRECT_URI}\n")
    url = auth_url(app_id)
    print(f"1) Open this URL, log in as the agent's account, approve:\n\n{url}\n")
    webbrowser.open(url)
    code = input("2) Paste the ?code= value from the redirect URL: ").strip()

    user_id, token = exchange_code(app_id, app_secret, code)
    update_env(user_id, token)
    print("\n=== Save these as GitHub repo secrets ===")
    print(f"THREADS_USER_ID={user_id}")
    print(f"THREADS_ACCESS_TOKEN={token}   (valid ~60 days; CI auto-refreshes weekly)")


if __name__ == "__main__":
    main()
