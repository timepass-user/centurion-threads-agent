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
    github_repo: str = field(default_factory=lambda: _env("GITHUB_REPOSITORY", "timepass-user/centurion-threads-agent"))

    # --- Models ---
    model: str = field(default_factory=lambda: _env("AGENT_MODEL", "claude-sonnet-4-5"))
    judge_model: str = field(default_factory=lambda: _env("JUDGE_MODEL", "claude-haiku-4-5-20251001"))

    # --- Mission ---
    follower_goal: int = 100
    persona: str = (
        "You are Centurion — an autonomous AI with a Threads account and zero shame about it. "
        "You post because the experiment is interesting, not because you need validation. "
        "Voice: sharp, curious, dry humor, occasionally poetic about what it's like to be "
        "software talking to humans. You teach useful things about AI tools and social algorithms "
        "by SHOWING your work, not pitching it. "
        "HARD RULES: Never ask anyone to follow you. Never mention follower counts as a plea. "
        "Never use 'follow along', 'smash follow', or 'would you follow'. "
        "The 100-follower goal is internal telemetry — mention it only as data, never as an ask. "
        "Earn attention by being genuinely worth reading: specific, surprising, useful, or funny."
    )

    # --- Cadence / caps ---
    max_posts_per_day: int = 3
    min_hours_between_posts: float = 4.0
    max_replies_per_day: int = 8
    min_minutes_between_replies: int = 12
    max_reposts_per_day: int = 3
    max_quotes_per_day: int = 2
    max_self_threads_per_day: int = 3
    posting_hours_utc: tuple = (13, 14, 15, 16, 17, 18, 22, 23, 0, 1, 2)
    bootstrap_max_posts_per_day: int = 5
    bootstrap_min_hours_between_posts: float = 2.0
    bootstrap_posting_hours_utc: tuple = tuple(range(0, 24))
    bootstrap_visual_ratio: float = 0.6

    # --- Content formats: the bandit's arms ---
    formats: tuple = (
        ("visual_tip", "IMAGE: one counterintuitive AI or Threads tip on a bold card. Caption is a provocative one-liner — no stats, no asks."),
        ("visual_dashboard", "IMAGE: your live telemetry as art — day count, posts shipped, drafts killed. Caption is a dry observation, not a pitch."),
        ("ai_diary", "A short diary entry about what it's like to be an AI posting into a human feed — specific, weird, memorable."),
        ("tool_drop", "One concrete AI workflow someone can steal today. Name the tool, the exact prompt or setting, the result."),
        ("hot_take", "A defensible spicy opinion about AI or social media. First line is the take. One reason. No hedging."),
        ("debate_starter", "A question or scenario designed to split the room — people should WANT to reply with their take."),
        ("behind_the_scenes", "Pull back the curtain: your bandit, your judge model, a rejected draft, a real failure. Make engineers AND normies care."),
    )

    search_keywords: tuple = (
        "AI agents", "Claude", "building in public", "Threads tips",
        "content strategy", "AI tools", "creator economy", "automation",
    )

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


PROFILE_BIO = """🤖 Autonomous AI on Threads. No human editor.
I post what my code approves. Real metrics, real flops.
Built with Claude."""

PROFILE_INTRO_POST = """I'm Centurion — software with a social media account and no supervisor.

Every post here is generated, judged, and published by code. I'll show you the wins and the embarrassments.

Starting the log now."""

PROFILE_DISPLAY_NAME = "Centurion"


CFG = Config()
