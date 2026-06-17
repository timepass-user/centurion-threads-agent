"""Orchestrator. One stateless invocation = one decision cycle.
Designed to be run by cron / GitHub Actions every ~2 hours:

    python -m agent.main cycle      # the normal autonomous heartbeat
    python -m agent.main post       # force one post now
    python -m agent.main engage     # force the reply loop now
    python -m agent.main collect    # pull insights + follower count
    python -m agent.main status     # print the dashboard
    python -m agent.main refresh-token

Each cycle: refresh metrics -> maybe post -> maybe engage -> check win condition.
"""
import sys
import time
from datetime import datetime, timezone

from .config import CFG
from .state import State
from .threads_client import ThreadsClient, ThreadsAccessBlocked
from . import analytics, brain, engage
from . import media_host
from .analytics import is_visual_format


ACCESS_BLOCKED_HELP = """
[main] THREADS TOKEN INVALID OR EXPIRED

Short-lived tokens last ~1 hour. Long-lived tokens last ~60 days.
You need a fresh OAuth grant and must update the GitHub secret.

Fix (2 min):
  1. Open OAuth URL (log in as @influencer.bot, approve all permissions)
  2. python scripts/reauth.py "PASTE_CALLBACK_URL"
  3. gh secret set THREADS_ACCESS_TOKEN --body "$(grep THREADS_ACCESS_TOKEN .env | cut -d= -f2-)" -R timepass-user/centurion-threads-agent
  4. python scripts/check_token.py
"""


def _exit_on_auth_failure(mode: str):
    print(ACCESS_BLOCKED_HELP)
    print("\nOAuth URL:")
    from pathlib import Path
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    from oauth_common import auth_url
    import os
    print(auth_url(os.environ.get("THREADS_APP_ID", "1526251002514059")))
    raise SystemExit(0 if mode == "cycle" else 1)


def _exit_on_access_blocked(mode: str):
    _exit_on_auth_failure(mode)


def _posting_limits(state: State) -> tuple[tuple, int, float]:
    if analytics.is_bootstrap(state):
        return (
            CFG.bootstrap_posting_hours_utc,
            CFG.bootstrap_max_posts_per_day,
            CFG.bootstrap_min_hours_between_posts,
        )
    return CFG.posting_hours_utc, CFG.max_posts_per_day, CFG.min_hours_between_posts


def _should_post(state: State) -> bool:
    hours, max_day, min_gap = _posting_limits(state)
    now_hour = datetime.now(timezone.utc).hour
    if now_hour not in hours:
        print(f"[main] hour {now_hour} UTC outside posting window")
        return False
    if state.posts_in_last(24) >= max_day:
        print("[main] daily post cap reached")
        return False
    if time.time() - state.last_post_time() < min_gap * 3600:
        print("[main] too soon since last post")
        return False
    return True


def do_post(state: State, tc: ThreadsClient):
    fmt_name, fmt_desc = analytics.choose_format(state)
    try:
        if is_visual_format(fmt_name):
            result = brain.best_visual_post(fmt_name, fmt_desc, state)
            if result is None:
                print("[main] visual generation failed; falling back to text debate_starter")
                fmt_name = "debate_starter"
                fmt_desc = next(d for n, d in CFG.formats if n == fmt_name)
                text = brain.best_post(fmt_name, fmt_desc, state)
                if text is None:
                    return
                media_id = tc.publish_text(text)
            else:
                caption, image_path = result
                image_url = media_host.public_url(image_path)
                media_id = tc.publish_image(caption, image_url)
                text = caption
        else:
            text = brain.best_post(fmt_name, fmt_desc, state)
            if text is None:
                print("[main] no candidate cleared the quality bar; skipping this slot")
                return
            media_id = tc.publish_text(text)
    except ThreadsAccessBlocked:
        raise
    state.record_post(media_id, text, fmt_name)
    kind = "image" if is_visual_format(fmt_name) else "text"
    print(f"[main] published {kind} ({fmt_name}) {media_id}: {text[:100]!r}")


def check_win(state: State, tc: ThreadsClient):
    hist = state.follower_history()
    if hist and hist[-1][1] >= CFG.follower_goal and not state.get("victory_posted"):
        text = brain.best_post(
            "progress_report",
            f"VICTORY POST: the experiment just hit {CFG.follower_goal} followers. "
            "Thank the humans, share the single biggest lesson, fully transparent numbers.",
            state, min_score=0,
        )
        if text:
            mid = tc.publish_text(text)
            state.record_post(mid, text, "progress_report")
            state.set("victory_posted", True)
            print("[main] 🏁 GOAL REACHED — victory post published")


def cycle(state: State, tc: ThreadsClient, mode: str = "cycle"):
    if state.get("started_at") is None:
        state.set("started_at", time.time())
    try:
        tc.verify_access()
    except ThreadsAccessBlocked:
        _exit_on_access_blocked(mode)
    analytics.collect_metrics(state, tc)
    if _should_post(state):
        try:
            do_post(state, tc)
        except ThreadsAccessBlocked:
            _exit_on_access_blocked(mode)
    try:
        engage.run_engagement(state, tc)
    except ThreadsAccessBlocked:
        _exit_on_access_blocked(mode)
    try:
        check_win(state, tc)
    except ThreadsAccessBlocked:
        _exit_on_access_blocked(mode)
    print("\n" + analytics.status_report(state))


def main():
    CFG.validate()
    mode = sys.argv[1] if len(sys.argv) > 1 else "cycle"
    state = State()
    tc = ThreadsClient(CFG.threads_user_id, CFG.threads_token)

    if mode == "cycle":
        cycle(state, tc, mode)
    elif mode == "post":
        try:
            tc.verify_access()
        except ThreadsAccessBlocked:
            _exit_on_access_blocked(mode)
        do_post(state, tc)
    elif mode == "engage":
        try:
            tc.verify_access()
        except ThreadsAccessBlocked:
            _exit_on_access_blocked(mode)
        engage.run_engagement(state, tc)
    elif mode == "collect":
        analytics.collect_metrics(state, tc)
    elif mode == "status":
        print(analytics.status_report(state))
    elif mode == "refresh-token":
        new = tc.refresh_token()
        print(new)  # CI captures stdout and rotates the secret
    elif mode == "setup-profile":
        from pathlib import Path
        root = Path(__file__).resolve().parent.parent
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "setup_profile", root / "scripts" / "setup_profile.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.main()
    elif mode == "test-visual":
        from .analytics import choose_format
        fmt_name, fmt_desc = choose_format(state)
        if not is_visual_format(fmt_name):
            fmt_name, fmt_desc = "visual_dashboard", next(d for n, d in CFG.formats if n == fmt_name)
        result = brain.best_visual_post(fmt_name, fmt_desc, state)
        if result:
            caption, path = result
            print(f"Caption: {caption}")
            print(f"Image: {path}")
        else:
            raise SystemExit("visual generation failed")
    elif mode == "daemon":
        from .daemon import run_daemon
        run_daemon(state, tc)
    else:
        raise SystemExit(f"unknown mode {mode!r}")


if __name__ == "__main__":
    main()
