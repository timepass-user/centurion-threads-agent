"""Growth loop #2: join existing conversations.
Keyword search (when API allows) + reply to comments on our own posts."""
import random
import time

from .config import CFG
from .state import State
from .threads_client import ThreadsClient
from . import brain


def run_engagement(state: State, tc: ThreadsClient, max_new_replies: int = 3):
    if state.replies_in_last(24) >= CFG.max_replies_per_day:
        print("[engage] daily reply cap reached")
        return
    if time.time() - state.last_reply_time() < CFG.min_minutes_between_replies * 60:
        print("[engage] too soon since last reply")
        return

    sent = _reply_via_keyword_search(state, tc, max_new_replies)
    if sent < max_new_replies:
        sent += _reply_on_own_posts(state, tc, max_new_replies - sent)
    print(f"[engage] total {sent} replies this cycle")


def _send_replies(state: State, tc: ThreadsClient, targets: list[dict], max_n: int) -> int:
    sent = 0
    for t in targets[:max_n]:
        if state.replies_in_last(24) >= CFG.max_replies_per_day:
            break
        reply = brain.write_reply(t["text"], t.get("username", "user"))
        if not reply:
            continue
        try:
            mid = tc.publish_text(reply, reply_to_id=t["id"])
        except Exception as e:
            print(f"[engage] publish failed: {e}")
            continue
        state.record_reply(mid, t["id"], t.get("username", ""), reply)
        sent += 1
        print(f"[engage] replied to @{t.get('username')}: {reply[:80]!r}")
        time.sleep(random.uniform(30, 60))
    return sent


def _reply_via_keyword_search(state: State, tc: ThreadsClient, max_new_replies: int) -> int:
    keywords = random.sample(CFG.search_keywords, k=min(2, len(CFG.search_keywords)))
    found: list[dict] = []
    for kw in keywords:
        try:
            found.extend(tc.keyword_search(kw, search_type="RECENT", limit=15))
        except Exception as e:
            print(f"[engage] search failed for {kw!r}: {e}")

    fresh: list[dict] = []
    for p in found:
        if p.get("is_reply"):
            continue
        if not p.get("text") or len(p["text"]) < 40:
            continue
        if state.replied_to(p["id"]):
            continue
        if state.replied_to_user_recently(p.get("username", "")):
            continue
        fresh.append(p)
    print(f"[engage] keyword: {len(found)} found, {len(fresh)} after filters")
    targets = brain.pick_reply_targets(fresh)
    return _send_replies(state, tc, targets, max_new_replies)


def _reply_on_own_posts(state: State, tc: ThreadsClient, max_new_replies: int) -> int:
    """Reply to people who commented on our posts — no keyword search needed."""
    try:
        posts = tc.my_recent_posts(limit=5)
    except Exception as e:
        print(f"[engage] own-posts fetch failed: {e}")
        return 0

    candidates: list[dict] = []
    for post in posts:
        try:
            replies = tc.replies_to(post["id"])
        except Exception as e:
            print(f"[engage] replies_to failed: {e}")
            continue
        for r in replies:
            if state.replied_to(r["id"]):
                continue
            if state.replied_to_user_recently(r.get("username", "")):
                continue
            if not r.get("text") or len(r["text"]) < 10:
                continue
            candidates.append(r)

    print(f"[engage] own-posts: {len(candidates)} unreplied comments")
    return _send_replies(state, tc, candidates, max_new_replies)
