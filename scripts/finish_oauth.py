#!/usr/bin/env python3
"""Exchange OAuth code from full redirect URL or raw code.

Usage:
  python scripts/finish_oauth.py "https://localhost/callback?code=AQBx..."
  python scripts/finish_oauth.py "AQBx..."
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from oauth_common import exchange_code, update_env

APP_ID = "1526251002514059"
APP_SECRET = "2991758208e8f2b1335e9daa2ac8bf1e"


def extract_code(raw: str) -> str:
    raw = raw.strip()
    if "code=" in raw:
        m = re.search(r"[?&]code=([^&#]+)", raw)
        if m:
            return m.group(1)
    return raw.rstrip("#_")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("\nWhen you see 'localhost refused to connect', copy the ENTIRE URL")
        print("from the address bar and run this script with it.")
        sys.exit(1)

    code = extract_code(sys.argv[1])
    print(f"Exchanging code ({len(code)} chars)...")
    user_id, token = exchange_code(APP_ID, APP_SECRET, code)
    update_env(user_id, token)
    print(f"\nSUCCESS! THREADS_USER_ID={user_id}")
    print("Run: python -m agent.main post")


if __name__ == "__main__":
    main()
