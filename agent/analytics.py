"""Learning loop.
1) Pull metrics for posts that have had ~20h to accumulate engagement.
2) Convert each into a binary reward: engagement rate above the trailing
   median = success. (Binary + Beta posterior = Thompson sampling that's
   robust at tiny sample sizes, which is exactly the 0->100 follower regime.)
3) Sample the Beta posterior of each format to pick the next post's format —
   automatic explore/explore-less without hand-tuned epsilon."""
import random
import statistics

from .config import CFG
from .state import State
from .threads_client import ThreadsClient


def collect_metrics(state: State, tc: ThreadsClient):
    for row in state.unscored_posts(older_than_hours=20):
        try:
            m = tc.media_insights(row["media_id"])
        except Exception as e:
            print(f"[analytics] insights failed for {row['media_id']}: {e}")
            continue
        state.update_metrics(row["media_id"], m)
        views = max(m.get("views", 0), 1)
        rate = (m.get("likes", 0) + 2 * m.get("replies", 0) + 2 * m.get("reposts", 0)) / views
        history = state.engagement_rates()
        threshold = statistics.median(history) if len(history) >= 4 else 0.0
        success = rate > threshold
        state.update_arm(row["fmt"], success)
        state.mark_scored(row["media_id"])
        print(f"[analytics] {row['fmt']}: rate={rate:.4f} vs median={threshold:.4f} -> "
              f"{'success' if success else 'miss'}")

    try:
        n = tc.follower_count()
        state.log_followers(n)
        print(f"[analytics] followers: {n}/{CFG.follower_goal}")
    except Exception as e:
        print(f"[analytics] follower count failed: {e}")


def choose_format(state: State) -> tuple[str, str]:
    """Thompson sampling across format arms."""
    best, best_sample = None, -1.0
    for fmt_name, fmt_desc in CFG.formats:
        a, b = state.get_arm(fmt_name)
        sample = random.betavariate(a, b)
        if sample > best_sample:
            best, best_sample = (fmt_name, fmt_desc), sample
    print(f"[bandit] chose format {best[0]} (sampled {best_sample:.3f})")
    return best


def status_report(state: State) -> str:
    hist = state.follower_history()
    followers = hist[-1][1] if hist else "?"
    lines = [f"Followers: {followers}/{CFG.follower_goal}",
             f"Posts (last 7d): {state.posts_in_last(24 * 7)}",
             f"Replies (last 7d): {state.replies_in_last(24 * 7)}",
             "Format arms (alpha/beta -> est. win rate):"]
    for fmt, (a, b) in sorted(state.arm_table().items(), key=lambda x: -(x[1][0] / (x[1][0] + x[1][1]))):
        lines.append(f"  {fmt:<20} {a:.0f}/{b:.0f} -> {a / (a + b):.0%}")
    return "\n".join(lines)
