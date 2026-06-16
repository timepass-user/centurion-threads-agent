"""Growth loop: replies, self-threads, reposts, and quote-posts."""
import random
import time

from .config import CFG
from .state import State
from .threads_client import ThreadsClient
from . import brain


def run_engagement(state: State, tc: ThreadsClient, max_new_replies: int = 3):
    sent = _run_replies(state, tc, max_new_replies)
    sent += _self_thread(state, tc)
    sent += _repost_and_quote(state, tc)
    print(f"[engage] total {sent} engagement actions this cycle")


def _run_replies(state: State, tc: ThreadsClient, max_new_replies: int) -> int:
    if state.replies_in_last(24) >= CFG.max_replies_per_day:
        print("[engage] daily reply cap reached")
        return 0
    if time.time() - state.last_reply_time() < CFG.min_minutes_between_replies * 60:
        print("[engage] too soon since last reply")
        return 0

    sent = _reply_via_keyword_search(state, tc, max_new_replies)
    if sent < max_new_replies:
        sent += _reply_on_own_posts(state, tc, max_new_replies - sent)
    return sent


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


def _self_thread(state: State, tc: ThreadsClient) -> int:
    """Continue our own thread — boosts depth without keyword search."""
    if state.engagements_in_last("self_thread", 24) >= CFG.max_self_threads_per_day:
        return 0
    if time.time() - state.last_engagement_time("self_thread") < 3600:
        return 0

    try:
        posts = tc.my_recent_posts(limit=8)
    except Exception as e:
        print(f"[engage] self-thread fetch failed: {e}")
        return 0

    for post in posts:
        if state.engaged("self_thread", post["id"]):
            continue
        if not post.get("text") or len(post["text"]) < 30:
            continue
        continuation = brain.write_thread_continuation(post["text"], state)
        if not continuation:
            continue
        try:
            mid = tc.publish_text(continuation, reply_to_id=post["id"])
        except Exception as e:
            print(f"[engage] self-thread publish failed: {e}")
            continue
        state.record_engagement("self_thread", mid, post["id"], continuation)
        print(f"[engage] self-thread on {post['id']}: {continuation[:80]!r}")
        return 1
    return 0


def _discover_posts(state: State, tc: ThreadsClient) -> list[dict]:
    keywords = random.sample(CFG.search_keywords, k=min(2, len(CFG.search_keywords)))
    found: list[dict] = []
    for kw in keywords:
        try:
            found.extend(tc.keyword_search(kw, search_type="TOP", limit=12))
        except Exception as e:
            print(f"[engage] search failed for {kw!r}: {e}")

    fresh: list[dict] = []
    for p in found:
        if p.get("is_reply"):
            continue
        if not p.get("text") or len(p["text"]) < 50:
            continue
        if state.replied_to(p["id"]) or state.engaged("repost", p["id"]) or state.engaged("quote", p["id"]):
            continue
        if state.replied_to_user_recently(p.get("username", ""), hours=48):
            continue
        fresh.append(p)
    return fresh


def _repost_and_quote(state: State, tc: ThreadsClient) -> int:
    """Native reposts and quote-posts when keyword search is available."""
    sent = 0
    fresh = _discover_posts(state, tc)
    if not fresh:
        return 0

    if state.engagements_in_last("quote", 24) < CFG.max_quotes_per_day:
        for t in brain.pick_quote_targets(fresh)[:1]:
            commentary = brain.write_quote_commentary(t["text"], t.get("username", "user"))
            if not commentary:
                continue
            try:
                mid = tc.publish_text(commentary, quote_post_id=t["id"])
            except Exception as e:
                print(f"[engage] quote failed: {e}")
                continue
            state.record_engagement("quote", mid, t["id"], commentary)
            print(f"[engage] quoted @{t.get('username')}: {commentary[:80]!r}")
            sent += 1
            time.sleep(random.uniform(45, 90))
            break

    if state.engagements_in_last("repost", 24) < CFG.max_reposts_per_day:
        for t in brain.pick_repost_targets(fresh)[:1]:
            if state.engaged("repost", t["id"]):
                continue
            try:
                result = tc.repost(t["id"])
            except Exception as e:
                print(f"[engage] repost failed: {e}")
                continue
            state.record_engagement("repost", result, t["id"])
            print(f"[engage] reposted @{t.get('username')}: {t['text'][:60]!r}")
            sent += 1

    return sent
