"""Query E: Check Coordination. Observable indicators only, no intent assertion. TRD Sec 12."""
from sqlalchemy.orm import Session
from app.models.db import Post
from collections import defaultdict
from datetime import timedelta

def run_coordination(db: Session, case_id: str):
    posts = db.query(Post).filter(Post.case_id == case_id).order_by(Post.collected_at.asc()).all()
    # temporal buckets (10-min)
    buckets = defaultdict(list)
    for p in posts:
        ts = p.published_at or p.collected_at
        if ts:
            key = ts.strftime("%Y-%m-%d %H:%M")[:-1] + "0"
            buckets[key].append(p.id)
    bursts = [{ "window": k, "count": len(v), "posts": v[:10]} for k, v in buckets.items() if len(v) >= 2]
    # text reuse via shared URL tokens
    url_groups = defaultdict(list)
    for p in posts:
        for tok in (p.text or "").split():
            if tok.startswith("http"):
                url_groups[tok[:120]].append(p.id)
    shared = [{"url": u, "posts": v[:10], "count": len(v)} for u, v in url_groups.items() if len(v) >= 2]
    return {"temporal_bursts": bursts[:20], "url_reuse": shared[:20],
            "note": "Indicators only — do not infer malicious intent without analyst review."}
