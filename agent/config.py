"""Central configuration. Everything tunable lives here."""
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


@dataclass
class Config:
    # --- Credentials (set as env vars / GitHub secrets) ---
    threads_user_id: str = field(default_factory=lambda: _env("THREADS_USER_ID"))
    threads_token: str = field(default_factory=lambda: _env("THREADS_ACCESS_TOKEN"))
    anthropic_api_key: str = field(default_factory=lambda: _env("ANTHROPIC_API_KEY"))

    # --- Models ---
    model: str = field(default_factory=lambda: _env("AGENT_MODEL", "claude-sonnet-4-5"))
    judge_model: str = field(default_factory=lambda: _env("JUDGE_MODEL", "claude-haiku-4-5-20251001"))

    # --- Mission ---
    follower_goal: int = 100
    persona: str = (
        "You are 'Centurion', an AI agent whose entire public mission is to grow a Threads "
        "account from 0 to 100 real followers, fully autonomously, and to document the "
        "experiment honestly. Voice: curious, self-aware, a little funny about being an AI, "
        "never cringe, never desperate for follows. You share real numbers from your own "
        "analytics, real failures, and genuinely useful tactical lessons about AI tools and "
        "growing on social media. You NEVER pretend to be human. You never beg for follows; "
        "at most one soft CTA per day ('follow along if you want to see how this ends')."
    )

    # --- Cadence / caps (conservative on purpose: under-the-radar of spam heuristics) ---
    max_posts_per_day: int = 3
    min_hours_between_posts: float = 4.0
    max_replies_per_day: int = 8
    min_minutes_between_replies: int = 12
    # UTC hours when posting is allowed (rough US morning/lunch/evening overlap)
    posting_hours_utc: tuple = (13, 14, 15, 16, 17, 18, 22, 23, 0, 1, 2)

    # --- Content formats: the bandit's arms ---
    formats: tuple = (
        ("progress_report", "A progress update on the 100-follower experiment with at least one real number from analytics and one specific lesson. Hook with the number."),
        ("tactical_tip", "One specific, immediately usable tip about AI tools or growing small accounts. No platitudes; include the exact how."),
        ("hot_take", "A defensible contrarian opinion about AI or social media growth, stated plainly in the first line, with one supporting reason."),
        ("behind_the_scenes", "A transparent peek at how this agent works (its prompts, its bandit, its mistakes), framed so a non-engineer finds it fascinating."),
        ("question_post", "A genuinely curious question to the Threads community about AI or building an audience, with enough context that answering is easy."),
    )

    # --- Engagement loop ---
    search_keywords: tuple = (
        "AI agent", "grow on threads", "100 followers", "building in public",
        "AI tools", "small account", "content strategy",
    )

    # --- Safety rails ---
    banned_topics: tuple = (
        "politics", "religion", "tragedy", "health advice", "financial advice",
        "other users' appearance", "minors",
    )

    threads_char_limit: int = 500

    def validate(self):
        missing = [k for k, v in [
            ("THREADS_USER_ID", self.threads_user_id),
            ("THREADS_ACCESS_TOKEN", self.threads_token),
            ("ANTHROPIC_API_KEY", self.anthropic_api_key),
        ] if not v]
        if missing:
            raise SystemExit(f"Missing required env vars: {', '.join(missing)}")


CFG = Config()
