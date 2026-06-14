# Centurion — an autonomous Threads agent racing to 100 real followers

A fully autonomous social media agent. Once deployed, no human touches it: it generates content, posts, replies to real conversations, measures what worked, and reallocates its own strategy with a multi-armed bandit. Its public persona is the experiment itself: *"I'm an AI agent trying to reach 100 followers. Follow along to see how it ends."*

## Why these product calls

**Platform — Threads.** The decision is API economics. X's free tier allows ~500 posts/month with near-zero read access (no engagement loop possible without $200/mo Basic). Instagram/TikTok/LinkedIn gate publishing behind app review processes measured in weeks. Threads' API is free, allows 250 posts/day (replies don't count), and exposes the exact three primitives an autonomous growth agent needs: **publish**, **insights**, and **keyword search**. Keyword search is the unlock — it's a sanctioned way for a 0-follower account to find conversations where a reply will actually be seen. Threads' ranking also still gives small accounts feed distribution that X stopped giving years ago.

**Niche — the experiment documents itself.** "Another AI news account" competes with thousands of identical accounts. "An AI agent live-narrating its own attempt to get 100 followers" has:
- a narrative arc (people follow to see how it ends — the goal counter is a retention mechanic),
- an unfakeable content moat (its own analytics, A/B results, and failures),
- honesty by construction — disclosure of automation is the *hook*, not a liability.

**Growth loops, ranked by expected value at 0 followers:**
1. **Replies into existing conversations** (keyword search → curated targets → genuinely useful replies). At 0 followers your posts reach nobody; your replies reach the poster and their audience. This is the engine for followers 0→30.
2. **Format bandit on original posts.** Five formats compete (progress reports, tactical tips, hot takes, behind-the-scenes, questions). Thompson sampling shifts volume to what the audience actually rewards. Engine for 30→100.
3. **The victory arc.** Milestone posts (50%, the win) are natural repost candidates.

Explicitly rejected: follow/unfollow churn, DMs, engagement bait, buying anything. They violate platform policy, produce fake followers, and the assignment says *real*.

## Architecture

```
GitHub Actions cron (every 2h, stateless)
        │
        ▼
agent/main.py ── one decision cycle ──────────────────────────┐
  │ 1. analytics.collect_metrics()   pull insights + followers │
  │ 2. should_post? → bandit picks format                      │
  │       brain.generate (Sonnet) → brain.judge (Haiku)        │
  │       publish only if score ≥ 6.5 (skipping beats slop)    │
  │ 3. engage.run_engagement()  keyword search → curate →      │
  │       useful reply (hard caps: 8/day, 72h per-user cooloff)│
  │ 4. check_win() → victory post at 100                       │
  └── state.sqlite committed back to repo = persistent memory ─┘
```

Key design choices:
- **Generator/judge separation.** Sonnet writes, Haiku grades with a hostile rubric. A model grading its own homework over-rates it; the judge kills "AI slop" before it ships. Posting slots are *skipped* if nothing clears the bar — silence beats mediocrity for follower conversion.
- **Thompson sampling, binary rewards.** Engagement rate above trailing median = success → Beta posterior per format. Robust at the tiny sample sizes of a new account; explores automatically, no hand-tuned epsilon.
- **State as a committed SQLite file.** Free, inspectable, diffable memory across stateless CI runs. The agent's entire history is in `git log`.
- **Self-healing credentials.** A weekly workflow refreshes the 60-day token and rotates its own GitHub secret.

## Setup (≈30 minutes, once)

1. **Threads account**: create it, bio must disclose automation, e.g. *"🤖 Autonomous AI agent. Goal: 100 followers, zero humans in the loop. Built with Claude."*
2. **Meta app**: developers.facebook.com → Create App → add the **Threads** use case → request scopes `threads_basic, threads_content_publish, threads_read_replies, threads_manage_replies, threads_manage_insights, threads_keyword_search`. Add your account as a tester (works immediately; App Review only needed for public multi-user apps).
3. **Token**: `python scripts/bootstrap_oauth.py APP_ID APP_SECRET REDIRECT_URI` → follow the two prompts.
4. **GitHub repo secrets**: `THREADS_USER_ID`, `THREADS_ACCESS_TOKEN`, `ANTHROPIC_API_KEY`, and `SECRETS_ADMIN_PAT` (fine-grained PAT with Secrets:write, for token rotation).
5. Push. The cron takes it from there. Watch it via the Actions log or `python -m agent.main status`.

Local smoke test: copy `.env.example` → `.env`, fill it, then `python -m agent.main post`.

## Cost & compliance

- **Cost:** Threads API $0, GitHub Actions $0 (public repo), Anthropic API ≈ $3–6/month at this cadence. Total: less than a coffee.
- **Compliance:** automation is via the official API with approved scopes; the account discloses it's a bot; reply caps (8/day, one per user per 72h) and an LLM curation pass keep it far from spam heuristics; sensitive topics are hard-banned in the prompt *and* the judge rubric.

## What I'd do next

1. **Images.** Threads insights show media posts outperform text; auto-render the follower curve as a daily chart (the API supports image containers).
2. **Reply mining.** Read replies to our own posts (`threads_read_replies`) and respond — conversion from conversation → follow is the highest-leverage untapped loop here.
3. **Posting-time bandit.** Second bandit over time-of-day slots once there's enough data (~3 weeks).
4. **Weekly self-retrospective.** A scheduled job where the model reads its own full history and rewrites parts of its strategy config — strategy-level autonomy, not just content-level.
5. **Kill criteria.** If <25 followers by day 21, the honest conclusion is the niche or platform call was wrong; pivot the persona before pivoting the infra.
