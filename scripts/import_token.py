#!/usr/bin/env python3
"""Import a short-lived token from Meta Graph API Explorer (bypasses OAuth redirect issues).

Use when OAuth redirect fails with "Insecure Login Blocked":

1. Go to https://developers.facebook.com/tools/explorer/
2. Select your app (1526251002514059)
3. Add Permissions → search "threads" → add all threads_* permissions
4. Click "Generate Access Token" → log in as @influencer.bot@threads.net
5. Copy the token and run:

   python scripts/import_token.py APP_SECRET "TOKEN_FROM_EXPLORER"
"""
from __future__ import annotations

import sys

import requests

from oauth_common import update_env


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    app_secret, short_token = sys.argv[1], sys.argv[2]

    print("Exchanging for long-lived token...")
    r = requests.get("https://graph.threads.net/access_token", params={
        "grant_type": "th_exchange_token",
        "client_secret": app_secret,
        "access_token": short_token,
    }, timeout=30).json()

    if "access_token" not in r:
        print(f"ERROR: {r}")
        sys.exit(1)

    token = r["access_token"]

    print("Fetching user ID...")
    me = requests.get("https://graph.threads.net/v1.0/me", params={
        "access_token": token,
        "fields": "id,username",
    }, timeout=30).json()

    if "id" not in me:
        print(f"ERROR: {me}")
        sys.exit(1)

    user_id = str(me["id"])
    username = me.get("username", "?")
    update_env(user_id, token)
    print(f"\nSUCCESS")
    print(f"Account: @{username}")
    print(f"THREADS_USER_ID={user_id}")
    print(f"Token valid ~60 days. Run: python -m agent.main post")


if __name__ == "__main__":
    main()
