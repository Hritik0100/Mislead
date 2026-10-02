"""Engagement-metrics extraction from captured text (Phase 4: Engagement Metrics).

Parses counts like "2.6K likes", "1.1M views", "152.3K reposts", "15 comments".
Rules (conservative, no invention):
- number (with optional K/M/B suffix) within 3 tokens BEFORE a metric keyword
  (like/likes, comment/comments, share/shares, repost/reposts, retweet(s),
   view/views, reply/replies, follower(s), following, repost)
- only fills keys that are missing/zero; never overwrites API-provided values.
- X-style bare icon counts ("1.1M 1.5K 152.3K" without labels) are NOT guessed.
"""
import re

_SUFFIX = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}
_METRICS = {
    "like": "likes", "likes": "likes",
    "comment": "comments", "comments": "comments",
    "share": "shares", "shares": "shares",
    "repost": "shares", "reposts": "shares", "retweet": "shares", "retweets": "shares",
    "view": "views", "views": "views",
    "repl": "comments", "reply": "comments", "replies": "comments",
}
_PAT = re.compile(
    r"(\d[\d,]*(?:\.\d+)?)\s*([KkMmBb])?\s+(likes?|comments?|shares?|reposts?|"
    r"retweets?|views?|repl(?:y|ies)?)\b", re.IGNORECASE)


def _num(n: str, suf: str) -> int:
    try:
        v = float(n.replace(",", ""))
    except ValueError:
        return 0
    return int(v * _SUFFIX.get((suf or "").lower(), 1))


def parse_engagement(text: str) -> dict:
    out: dict[str, int] = {}
    for m in _PAT.finditer(text or ""):
        key = _METRICS.get(m.group(3).lower(), "")
        if not key:
            continue
        v = _num(m.group(1), m.group(2))
        if v > 0:
            out[key] = max(out.get(key, 0), v)  # max: repeated chrome, keep peak
    return out


def merge_engagement(existing: dict | None, text: str) -> dict:
    """Fill only missing/zero metric keys; preserves sentiment + API values."""
    eng = dict(existing or {})
    for k, v in parse_engagement(text).items():
        if not eng.get(k):
            eng[k] = v
    return eng
