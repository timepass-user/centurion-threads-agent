"""Growth loop #2: join existing conversations.
A 0-follower account's posts are shown to almost nobody; replies are shown to
the poster and their audience. Keyword search -> curate targets -> write a
reply that's useful on its own merits. Hard caps keep this unmistakably
non-spammy (and inside platform policy)."""
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

    keywords = random.sample(CFG.search_keywords, k=min(2, len(CFG.search_keywords)))
    found: list[dict] = []
    for kw in keywords:
        try:
            found.extend(tc.keyword_search(kw, search_type="RECENT", limit=15))
        except Exception as e:
            print(f"[engage] search failed for {kw!r}: {e}")

    # basic filters before spending LLM tokens
    fresh: list[dict] = []
    for p in found:
        if p.get("is_reply"):
            continue
        if not p.get("text") or len(p["text"]) < 40:
            continue
        if state.replied_to(p["id"]):
            continue
        if state.replied_to_user_recently(p.get("username", "")):
            continue  # never reply to the same person twice in 72h
        fresh.append(p)
    print(f"[engage] {len(found)} found, {len(fresh)} after filters")

    targets = brain.pick_reply_targets(fresh)[:max_new_replies]
    sent = 0
    for t in targets:
        if state.replies_in_last(24) >= CFG.max_replies_per_day:
            break
        reply = brain.write_reply(t["text"], t.get("username", ""))
        if not reply:
            print(f"[engage] brain skipped @{t.get('username')}")
            continue
        try:
            mid = tc.publish_text(reply, reply_to_id=t["id"])
        except Exception as e:
            print(f"[engage] publish failed: {e}")
            continue
        state.record_reply(mid, t["id"], t.get("username", ""), reply)
        sent += 1
        print(f"[engage] replied to @{t.get('username')}: {reply[:80]!r}")
        time.sleep(random.uniform(45, 120))  # human-ish pacing between replies
    print(f"[engage] sent {sent} replies this cycle")
