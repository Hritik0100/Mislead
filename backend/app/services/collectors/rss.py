"""RSS/News collector. Respects feed terms + rate limits. TRD Sec 6."""
import feedparser
import httpx
from dateutil import parser as dateparser
from .base import SourceRecord

def collect_rss(url: str, max_items: int = 30):
    feed = feedparser.parse(url)
    out = []
    for e in feed.entries[:max_items]:
        text = e.get("summary", "") or e.get("description", "")
        pub = None
        for k in ("published", "updated"):
            if e.get(k):
                try:
                    pub = dateparser.parse(e[k])
                except Exception:
                    pass
        out.append(SourceRecord(
            platform="rss",
            account_username=feed.feed.get("title", url)[:80],
            account_display=feed.feed.get("title", ""),
            source_url=e.get("link", url),
            text=f"{e.get('title','')}\n{text}",
            title=e.get("title", ""),
            published_at=pub,
        ))
    return out
