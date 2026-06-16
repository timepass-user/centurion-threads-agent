#!/usr/bin/env python3
"""Diagnose Threads API credentials. Run after any 'API access blocked' error."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.config import CFG
from agent.threads_client import ThreadsClient, ThreadsAccessBlocked, ThreadsError


def main():
    CFG.validate()
    tc = ThreadsClient(CFG.threads_user_id, CFG.threads_token)
    print("Checking Threads API access...\n")

    checks = [
        ("profile", lambda: tc.profile()),
        ("follower_count", lambda: {"followers": tc.follower_count()}),
        ("recent_posts", lambda: {"count": len(tc.my_recent_posts(limit=3))}),
    ]

    ok = 0
    for name, fn in checks:
        try:
            result = fn()
            print(f"  OK  {name}: {result}")
            ok += 1
        except ThreadsAccessBlocked as e:
            print(f"  FAIL {name}: ACCESS BLOCKED — re-OAuth required")
            print(f"       {e}")
        except ThreadsError as e:
            print(f"  FAIL {name}: {e}")

    print()
    if ok == len(checks):
        print("All checks passed. Token is healthy.")
        return

    print("TOKEN IS DEAD. Recovery steps:")
    print("  1. https://developers.facebook.com/ → your app → Home → Alerts")
    print("  2. python scripts/bootstrap_oauth.py THREADS_APP_ID THREADS_APP_SECRET")
    print("  3. gh secret set THREADS_ACCESS_TOKEN --body 'NEW_TOKEN' -R timepass-user/centurion-threads-agent")
    sys.exit(1)


if __name__ == "__main__":
    main()
