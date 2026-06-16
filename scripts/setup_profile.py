#!/usr/bin/env python3
"""One-time profile bootstrap: publish intro post + print manual profile steps.

Threads API cannot set bio or display name — those must be done in the app."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.config import CFG, PROFILE_BIO, PROFILE_DISPLAY_NAME, PROFILE_INTRO_POST
from agent.state import State
from agent.threads_client import ThreadsClient


def main():
    CFG.validate()
    state = State()
    tc = ThreadsClient(CFG.threads_user_id, CFG.threads_token)

    print("=" * 60)
    print("CENTURION PROFILE SETUP")
    print("=" * 60)

    # Show current profile
    try:
        prof = tc.profile()
        print(f"\nCurrent handle: @{prof.get('username', '?')}")
        print(f"Current bio: {prof.get('threads_biography') or '(empty)'}")
    except Exception as e:
        print(f"Could not fetch profile: {e}")

    # Publish intro post once
    if not state.get("profile_intro_posted"):
        print("\nPublishing intro post...")
        mid = tc.publish_text(PROFILE_INTRO_POST)
        state.record_post(mid, PROFILE_INTRO_POST, "profile_intro")
        state.set("profile_intro_posted", True)
        print(f"Intro post published: {mid}")
    else:
        print("\nIntro post already published — skipping.")

    print("\n" + "=" * 60)
    print("MANUAL STEPS (Threads app — API cannot do these)")
    print("=" * 60)
    print(f"""
1. DISPLAY NAME → Settings → Account → set to: {PROFILE_DISPLAY_NAME}

2. BIO → Edit profile → paste exactly:

{PROFILE_BIO}

3. PROFILE PHOTO → Use a simple bot/AI avatar (distinct, friendly, not generic).
   Suggestion: minimal robot face on dark background, or generate one with any AI image tool.

4. FOLLOW 10 PROFILES → Threads suggests this on new accounts.
   Follow creators in: AI tools, building in public, indie hackers, content strategy.
   This fills your feed and signals you're a real participant.

5. PIN INTRO → Long-press your intro post and pin it (if Threads supports pin on your account).
""")
    print("=" * 60)


if __name__ == "__main__":
    main()
