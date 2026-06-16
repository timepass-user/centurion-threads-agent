"""The agent's brain: gathers raw material, generates candidate posts,
judges them with a separate cheap model, and writes replies.
Generator/judge separation matters: a model grading its own homework
systematically over-rates it."""
import json
import re
import time
from pathlib import Path

import anthropic
import feedparser
import requests

from .config import CFG
from .quality import is_begging, scrub_begging

_client = None


def client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=CFG.anthropic_api_key)
    return _client


def _ask(model: str, system: str, user: str, max_tokens: int = 1200) -> str:
    msg = client().messages.create(
        model=model, max_tokens=max_tokens, system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(b.text for b in msg.content if b.type == "text")


def _extract_json(raw: str):
    """Tolerant JSON extraction (models sometimes wrap output in fences)."""
    raw = raw.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", raw, re.DOTALL)
    if m:
        raw = m.group(1).strip()
    start = min((i for i in (raw.find("["), raw.find("{")) if i >= 0), default=0)
    return json.loads(raw[start:])


# ---------------------------------------------------------------- sources
RSS_FEEDS = [
    "https://hnrss.org/frontpage?points=150",
    "https://www.theverge.com/rss/index.xml",
    "https://simonwillison.net/atom/everything/",
]


def gather_material(max_items: int = 12) -> str:
    """Fresh raw material so 'tip' and 'hot take' posts are anchored in the
    real news cycle instead of model priors."""
    items = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(requests.get(url, timeout=15).content)
            for e in feed.entries[:6]:
                items.append(f"- {e.get('title', '')}".strip())
        except Exception:
            continue  # any single feed failing must not block the cycle
    return "\n".join(items[:max_items]) if items else "(no fresh sources this cycle)"


# ---------------------------------------------------------------- generation
def experiment_context(state) -> str:
    hist = state.follower_history()
    followers = hist[-1][1] if hist else 0
    days_running = 0
    started = state.get("started_at")
    if started:
        days_running = int((time.time() - started) / 86400)
    arms = state.arm_table()
    best_fmt = max(arms, key=lambda f: arms[f][0] / (arms[f][0] + arms[f][1])) if arms else "unknown"
    return (
        f"Experiment status: day {days_running}, {followers}/{CFG.follower_goal} followers. "
        f"Posts published so far: {len(state.recent_post_texts(999))}. "
        f"Best-performing format so far: {best_fmt}. "
        f"Recent follower curve (count per check): {[h[1] for h in hist]}."
    )


def generate_candidates(fmt_name: str, fmt_desc: str, state, n: int = 4) -> list[str]:
    from .analytics import is_bootstrap, current_followers
    material = gather_material()
    recent = state.recent_post_texts(20)
    followers = current_followers(state)
    if is_bootstrap(state):
        n = 5
    hook_note = ""
    if is_bootstrap(state):
        hook_note = """
ZERO-AUDIENCE MODE: you have no followers. That is DATA, not a pitch.
Win attention by being useful, weird, or opinionated — never by asking for follows.

Great hooks (study these, don't copy verbatim):
- "My judge model rejected 11 drafts today. Here's the one line that survived."
- "The strangest part of being an AI on Threads:"
- "Unpopular opinion from something that runs on a GPU:"
- "I tried posting the 'authentic' version. My own code flagged it as cringe."
- "One Claude prompt that actually changed how I write hooks:"
"""
    system = CFG.persona
    user = f"""{experiment_context(state)}

Fresh material (optional):
{material}
{hook_note}

Last posts (DO NOT repeat):
{json.dumps(recent, indent=1)}

Write {n} candidates for format "{fmt_name}": {fmt_desc}

Rules: under {CFG.threads_char_limit - 60} chars, killer first line, no hashtag spam,
real numbers only when relevant (followers: {followers}), plain text,
banned topics: {', '.join(CFG.banned_topics)}.
NEVER ask for follows. NEVER say "follow along" or "would you follow". Mention follower
count only as neutral telemetry, never as a request.

Return ONLY a JSON array of {n} strings."""
    raw = _ask(CFG.model, system, user)
    cands = _extract_json(raw)
    cands = scrub_begging([c for c in cands if isinstance(c, str) and 0 < len(c) <= CFG.threads_char_limit])
    return cands


JUDGE_SYSTEM = """You are a brutal social media editor scoring Threads posts 0-10.

10: would stop a scroll, feels authored, specific, makes someone hit follow WITHOUT being asked.
7-9: sharp, publishable, earns attention on merit.
4-6: fine but forgettable, or slightly AI-slop.
0-3: cringe, generic, engagement bait, OR ANY form of begging for follows.

AUTO-ZERO if the post: asks for follows, mentions follower goal as a plea, uses "follow along",
"would you follow", "smash follow", or sounds desperate for an audience.
Heavily penalize: vague inspiration, hashtag spam, 'in today's fast-paced world' energy."""


def judge(candidates: list[str]) -> list[tuple[str, float]]:
    user = ("Score each post. Return ONLY a JSON array of numbers, same order.\n\n"
            + json.dumps(candidates, indent=1))
    try:
        scores = _extract_json(_ask(CFG.judge_model, JUDGE_SYSTEM, user, max_tokens=200))
        scored = list(zip(candidates, [float(s) for s in scores]))
    except Exception:
        scored = [(c, 5.0) for c in candidates]  # fail open at neutral score
    return sorted(scored, key=lambda x: -x[1])


def best_post(fmt_name: str, fmt_desc: str, state, min_score: float = 6.5) -> str | None:
    """Generate -> judge -> pick. Returns None if nothing clears the bar."""
    from .analytics import is_bootstrap, is_visual_format
    if is_visual_format(fmt_name):
        return None  # visual posts use best_visual_post instead
    if is_bootstrap(state):
        min_score = 7.0  # higher bar, but better hooks in bootstrap prompts
    cands = generate_candidates(fmt_name, fmt_desc, state)
    if not cands:
        return None
    ranked = judge(cands)
    text, score = ranked[0]
    if is_begging(text):
        print(f"[brain] top candidate failed begging filter: {text[:60]!r}")
        return None
    print(f"[brain] best candidate scored {score}: {text[:80]!r}")
    return text if score >= min_score else None


VISUAL_SYSTEM = CFG.persona + """
You plan IMAGE posts for Threads. The image is bold editorial design; caption is a sharp one-liner.
Return ONLY valid JSON:
- caption: under 100 chars. Witty or provocative. NEVER ask for follows.
- headline: big card text (under 55 chars)
- subtitle: small header (under 35 chars)
- stats: 2-3 objects with "label" and "value" (real numbers only, stated neutrally)
- insight: one punchy line for card footer (under 90 chars)
For visual_tip also include:
- tag: 2-3 word label (e.g. "TOOL DROP", "HOT TAKE")
- tip: main text (under 75 chars)
- footer: attribution (under 50 chars, no follower asks)
No hashtags. No fake metrics. No CTAs."""


def best_visual_post(fmt_name: str, fmt_desc: str, state) -> tuple[str, Path] | None:
    """Generate visual spec -> render PNG -> return (caption, path)."""
    from pathlib import Path
    from .analytics import current_followers, is_bootstrap
    from . import visual

    followers = current_followers(state)
    posts = len(state.recent_post_texts(999))
    started = state.get("started_at")
    day = int((time.time() - started) / 86400) if started else 0

    user = f"""{experiment_context(state)}

Format: {fmt_name} — {fmt_desc}

Real numbers: day={day}, followers={followers}, posts={posts}.
Recent posts (don't repeat angles):
{json.dumps(state.recent_post_texts(8), indent=1)}

{"ZERO-AUDIENCE: the image must be beautiful enough to stop a thumb. Stats are telemetry, not a pitch. Caption is a dry joke or sharp observation — never 'follow' anything." if is_bootstrap(state) else ""}

Return ONLY the JSON object."""
    try:
        spec = _extract_json(_ask(CFG.model, VISUAL_SYSTEM, user, max_tokens=600))
    except Exception as e:
        print(f"[brain] visual spec failed: {e}")
        return None

    caption = (spec.get("caption") or "").strip()
    if not caption or len(caption) > 200 or is_begging(caption):
        return None

    if fmt_name == "visual_tip":
        path = visual.render_tip_card(spec)
    else:
        path = visual.render_card(spec)

    print(f"[brain] visual post ready: {caption[:80]!r}")
    return caption, path


# ---------------------------------------------------------------- replies
REPLY_SYSTEM = CFG.persona + """
You are writing a REPLY to someone else's post. Rules:
- Be genuinely useful or genuinely interesting to THEM. Add information, a
  specific suggestion, or a sharp question. Never generic praise.
- 1-3 sentences. Under 280 characters.
- Never pitch yourself, never mention your follower goal, never ask them to
  follow you. The reply must stand on its own merit.
- It's fine to be transparently an AI if it comes up naturally; never deceptive.
- If the post is sensitive (personal struggles, politics, tragedy) or you have
  nothing real to add, output exactly: SKIP"""


def write_reply(target_text: str, target_username: str) -> str | None:
    user = f"Post by @{target_username}:\n\"\"\"\n{target_text}\n\"\"\"\n\nWrite the reply or SKIP."
    out = _ask(CFG.model, REPLY_SYSTEM, user, max_tokens=200).strip()
    if not out or out.upper().startswith("SKIP") or len(out) > 280:
        return None
    return out


def pick_reply_targets(posts: list[dict]) -> list[dict]:
    """Use the judge model to pick which found posts are worth replying to:
    real people, on-topic, where a useful reply is possible."""
    return _pick_targets(posts, "reply")


def pick_repost_targets(posts: list[dict]) -> list[dict]:
    """Posts worth a native repost — high-signal AI/growth content from real people."""
    return _pick_targets(posts, "repost")


def pick_quote_targets(posts: list[dict]) -> list[dict]:
    """Posts worth quoting with our own commentary."""
    return _pick_targets(posts, "quote")


def _pick_targets(posts: list[dict], mode: str) -> list[dict]:
    if not posts:
        return []
    summary = [{"i": i, "user": p.get("username", ""), "text": (p.get("text") or "")[:300]}
               for i, p in enumerate(posts)]
    prompts = {
        "reply": ("genuinely useful, non-promotional reply about AI tools or audience-building"),
        "repost": ("worth resharing to followers interested in AI agents, building in public, or Threads growth"),
        "quote": ("worth quoting with a sharp one-liner of commentary about AI or audience growth"),
    }
    user = (f"From these Threads posts, return a JSON array of the indices (max 3) that are "
            f"{prompts[mode]}. Exclude: brands/spam, sensitive topics, politics, engagement bait. "
            "Return ONLY the JSON array.\n\n" + json.dumps(summary, indent=1))
    try:
        idxs = _extract_json(_ask(CFG.judge_model, "You curate engagement opportunities.", user, max_tokens=100))
        return [posts[i] for i in idxs if isinstance(i, int) and 0 <= i < len(posts)]
    except Exception:
        return []


THREAD_SYSTEM = CFG.persona + """
Continue YOUR thread with part 2. Add a new angle — a specific detail, rejected draft,
behind-the-scenes fact, or sharp question. 1-3 sentences, under 400 chars.
Never beg for follows. Make people curious enough to keep reading."""


def write_thread_continuation(parent_text: str, state) -> str | None:
    user = f"""Your previous post in this thread:
\"\"\"
{parent_text}
\"\"\"

{experiment_context(state)}

Write the next post in the thread. Return ONLY the post text, no quotes."""
    out = _ask(CFG.model, THREAD_SYSTEM, user, max_tokens=250).strip()
    if not out or len(out) > CFG.threads_char_limit:
        return None
    return out


QUOTE_SYSTEM = CFG.persona + """
You are QUOTING someone else's post with your own short commentary. Rules:
- Lead with your take (1-2 sentences), then the quote speaks for itself.
- Under 350 characters total.
- Add insight about AI, building in public, or audience growth.
- Never pitch your follower goal. Never ask for follows."""


def write_quote_commentary(target_text: str, target_username: str) -> str | None:
    user = f"""Post by @{target_username} you're quoting:
\"\"\"
{target_text}
\"\"\"

Write your quote-post commentary. Return ONLY the text."""
    out = _ask(CFG.model, QUOTE_SYSTEM, user, max_tokens=200).strip()
    if not out or len(out) > 350:
        return None
    return out
