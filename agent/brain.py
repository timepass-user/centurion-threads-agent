"""The agent's brain: gathers raw material, generates candidate posts,
judges them with a separate cheap model, and writes replies.
Generator/judge separation matters: a model grading its own homework
systematically over-rates it."""
import json
import re
import time

import anthropic
import feedparser
import requests

from .config import CFG

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
BOOTSTRAP (0 followers): first line must stop the scroll — use a real number, confession,
or question. Great hooks:
- "Day 0. 0 followers. I'm an AI with no human editor. Documenting everything."
- "Would you follow an AI trying to hit 100 followers? I'm about to find out."
- "My AI editor rejected 9/12 drafts. Here's what made the cut."
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
real numbers only (followers: {followers}), plain text, banned: {', '.join(CFG.banned_topics)}.

Return ONLY a JSON array of {n} strings."""
    raw = _ask(CFG.model, system, user)
    cands = _extract_json(raw)
    return [c for c in cands if isinstance(c, str) and 0 < len(c) <= CFG.threads_char_limit]


JUDGE_SYSTEM = """You are a brutal social media editor. You score Threads posts 0-10.
9-10: would stop a scroll, feels human, specific, earns a follow.
6-8: solid, publishable.
3-5: generic, sounds like AI slop, weak hook.
0-2: cringe, spammy, off-brand, or violates the rules.
Heavily penalize: vague inspiration-speak, fake-sounding numbers, beggy CTAs,
'in today's fast-paced world' energy, anything that reads as engagement bait."""


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
    from .analytics import is_bootstrap
    if is_bootstrap(state):
        min_score = 7.0  # higher bar, but better hooks in bootstrap prompts
    cands = generate_candidates(fmt_name, fmt_desc, state)
    if not cands:
        return None
    ranked = judge(cands)
    text, score = ranked[0]
    print(f"[brain] best candidate scored {score}: {text[:80]!r}")
    return text if score >= min_score else None


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
    if not posts:
        return []
    summary = [{"i": i, "user": p.get("username", ""), "text": (p.get("text") or "")[:300]}
               for i, p in enumerate(posts)]
    user = ("From these Threads posts, return a JSON array of the indices (max 5) where a "
            "genuinely useful, non-promotional reply about AI tools or audience-building is "
            "possible. Exclude: brands/spam, sensitive personal topics, politics, posts that "
            "are themselves replies or engagement bait. Return ONLY the JSON array.\n\n"
            + json.dumps(summary, indent=1))
    try:
        idxs = _extract_json(_ask(CFG.judge_model, "You curate reply opportunities.", user, max_tokens=100))
        return [posts[i] for i in idxs if isinstance(i, int) and 0 <= i < len(posts)]
    except Exception:
        return []
