"""Content quality gates — never publish follower-begging or engagement bait."""

BANNED_PHRASES = (
    "follow me", "follow along", "smash follow", "please follow",
    "would you follow", "hit follow", "follow if you", "follow for",
    "give me a follow", "need followers", "get me to 100",
    "help me reach", "follow back", "follow to see",
    "like and follow", "drop a follow", "follow this account",
)

BANNED_PATTERNS = (
    r"\bfollow\b.*\b(100|goal|journey|experiment)\b",
    r"\b(100|goal)\b.*\bfollowers?\b.*\b(follow|help|need)\b",
)


def is_begging(text: str) -> bool:
    lower = text.lower()
    if any(p in lower for p in BANNED_PHRASES):
        return True
    import re
    return any(re.search(pat, lower) for pat in BANNED_PATTERNS)


def scrub_begging(candidates: list[str]) -> list[str]:
    clean = [c for c in candidates if not is_begging(c)]
    dropped = len(candidates) - len(clean)
    if dropped:
        print(f"[quality] rejected {dropped} begging/bait candidates")
    return clean
