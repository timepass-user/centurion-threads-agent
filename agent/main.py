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
from .threads_client import ThreadsClient
from . import analytics, brain, engage


def _should_post(state: State) -> bool:
    now_hour = datetime.now(timezone.utc).hour
    if now_hour not in CFG.posting_hours_utc:
        print(f"[main] hour {now_hour} UTC outside posting window")
        return False
    if state.posts_in_last(24) >= CFG.max_posts_per_day:
        print("[main] daily post cap reached")
        return False
    if time.time() - state.last_post_time() < CFG.min_hours_between_posts * 3600:
        print("[main] too soon since last post")
        return False
    return True


def do_post(state: State, tc: ThreadsClient):
    fmt_name, fmt_desc = analytics.choose_format(state)
    text = brain.best_post(fmt_name, fmt_desc, state)
    if text is None:
        print("[main] no candidate cleared the quality bar; skipping this slot")
        return
    media_id = tc.publish_text(text)
    state.record_post(media_id, text, fmt_name)
    print(f"[main] published ({fmt_name}) {media_id}: {text[:100]!r}")


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


def cycle(state: State, tc: ThreadsClient):
    if state.get("started_at") is None:
        state.set("started_at", time.time())
    analytics.collect_metrics(state, tc)
    if _should_post(state):
        do_post(state, tc)
    engage.run_engagement(state, tc)
    check_win(state, tc)
    print("\n" + analytics.status_report(state))


def main():
    CFG.validate()
    mode = sys.argv[1] if len(sys.argv) > 1 else "cycle"
    state = State()
    tc = ThreadsClient(CFG.threads_user_id, CFG.threads_token)

    if mode == "cycle":
        cycle(state, tc)
    elif mode == "post":
        do_post(state, tc)
    elif mode == "engage":
        engage.run_engagement(state, tc)
    elif mode == "collect":
        analytics.collect_metrics(state, tc)
    elif mode == "status":
        print(analytics.status_report(state))
    elif mode == "refresh-token":
        new = tc.refresh_token()
        print(new)  # CI captures stdout and rotates the secret
    elif mode == "daemon":
        from .daemon import run_daemon
        run_daemon(state, tc)
    else:
        raise SystemExit(f"unknown mode {mode!r}")


if __name__ == "__main__":
    main()
