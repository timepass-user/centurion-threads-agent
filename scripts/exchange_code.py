#!/usr/bin/env python3
"""Exchange OAuth code for Threads token. Works with https://localhost/callback redirect.

Usage:
  # Step 1 — prints auth URL, paste code when prompted:
  python scripts/exchange_code.py APP_ID APP_SECRET

  # Step 2 — or pass code directly:
  python scripts/exchange_code.py APP_ID APP_SECRET "AQBx..."
"""
from __future__ import annotations

import sys
import webbrowser

from oauth_common import REDIRECT_URI, auth_url, exchange_code, update_env


def main():
    if len(sys.argv) < 3:
        print("Usage: python scripts/exchange_code.py APP_ID APP_SECRET [CODE]")
        sys.exit(1)

    app_id, app_secret = sys.argv[1], sys.argv[2]
    url = auth_url(app_id)

    print("\n=== BEFORE YOU START ===")
    print("Add this EXACT redirect URI in Meta Developer Console:")
    print(f"  App → Threads → Settings → Redirect Callback URLs")
    print(f"  → {REDIRECT_URI}\n")

    if len(sys.argv) >= 4:
        code = sys.argv[3]
    else:
        print("1) Open this URL, log in as @influencer.bot@threads.net, click Allow:\n")
        print(url)
        print("\n2) Browser will redirect to https://localhost/callback?code=...")
        print("   The page won't load — that's fine. Copy the FULL code value from the URL bar.\n")
        webbrowser.open(url)
        code = input("3) Paste the code here: ").strip()

    user_id, token = exchange_code(app_id, app_secret, code)
    update_env(user_id, token)
    print(f"\nSUCCESS — THREADS_USER_ID={user_id}")
    print(f"Token saved (starts with {token[:12]}...)")


if __name__ == "__main__":
    main()
