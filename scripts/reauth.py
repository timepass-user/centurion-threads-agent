#!/usr/bin/env python3
"""One-command OAuth recovery. Reads app secret from .env automatically.

Usage:
  python scripts/reauth.py                    # opens browser, prompts for code
  python scripts/reauth.py "FULL_CALLBACK_URL_OR_CODE"   # non-interactive
"""
from __future__ import annotations

import os
import re
import sys
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from oauth_common import REDIRECT_URI, auth_url, exchange_code, update_env

APP_ID = os.environ.get("THREADS_APP_ID", "1526251002514059")


def extract_code(raw: str) -> str:
    raw = raw.strip()
    if "code=" in raw:
        m = re.search(r"[?&]code=([^&#]+)", raw)
        if m:
            return m.group(1)
    return raw.rstrip("#_")


def main():
    app_secret = os.environ.get("THREADS_APP_SECRET", "")
    if not app_secret:
        print("Set THREADS_APP_SECRET in .env first.")
        sys.exit(1)

    if len(sys.argv) > 1:
        code = extract_code(sys.argv[1])
    else:
        url = auth_url(APP_ID)
        print("=" * 60)
        print("RE-AUTH @influencer.bot")
        print("=" * 60)
        print(f"\n1. Redirect URI: {REDIRECT_URI}")
        print(f"\n2. Open & approve ALL permissions:\n\n{url}\n")
        webbrowser.open(url)
        code = input("3. Paste full callback URL (or just the code): ").strip()
        code = extract_code(code)

    print("Exchanging code...")
    user_id, token = exchange_code(APP_ID, app_secret, code)
    update_env(user_id, token)

    print("\nSUCCESS — token saved to .env")
    print(f"THREADS_USER_ID={user_id}")

    repo = os.environ.get("GITHUB_REPOSITORY", "timepass-user/centurion-threads-agent")
    print(f'\nUpdate GitHub secret:\n  gh secret set THREADS_ACCESS_TOKEN --body "{token}" -R {repo}')
    print("\nVerify:\n  python scripts/check_token.py\n  python -m agent.main post")


if __name__ == "__main__":
    main()
