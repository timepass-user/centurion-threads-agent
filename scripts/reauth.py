#!/usr/bin/env python3
"""One-command OAuth recovery. Opens browser, exchanges code, prints GitHub secret command."""
from __future__ import annotations

import sys
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from oauth_common import REDIRECT_URI, auth_url, exchange_code, update_env

APP_ID = "1526251002514059"


def main():
    app_secret = sys.argv[1] if len(sys.argv) > 1 else ""
    if not app_secret:
        print("Usage: python scripts/reauth.py THREADS_APP_SECRET")
        print("\nGet secret from: Meta Developer → Threads API → Settings → Threads App Secret")
        sys.exit(1)

    url = auth_url(APP_ID)
    print("=" * 60)
    print("RE-AUTH @influencer.bot")
    print("=" * 60)
    print(f"\n1. Redirect URI must be set: {REDIRECT_URI}")
    print(f"\n2. Open this URL and approve ALL permissions:\n\n{url}\n")
    webbrowser.open(url)

    raw = input("3. Paste full callback URL (or just the code): ").strip()
    if "code=" in raw:
        import re
        m = re.search(r"[?&]code=([^&#]+)", raw)
        code = m.group(1) if m else raw
    else:
        code = raw

    user_id, token = exchange_code(APP_ID, app_secret, code)
    update_env(user_id, token)

    print("\n" + "=" * 60)
    print("SUCCESS — token saved to .env")
    print("=" * 60)
    print(f"\nTHREADS_USER_ID={user_id}")
    print(f"THREADS_ACCESS_TOKEN={token[:20]}...")
    print("\nUpdate GitHub secret:")
    print(f'  gh secret set THREADS_ACCESS_TOKEN --body "{token}" -R timepass-user/centurion-threads-agent')
    print("\nVerify:")
    print("  python scripts/check_token.py")
    print("  python -m agent.main post")


if __name__ == "__main__":
    main()
