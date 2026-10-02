"""Query B: Find Original Source (items 9, 10).

Separates three clocks that must never be confused:
  first_observed_at — when OUR system first saw it (collection time)
  published_at      — original publication time, ONLY if the source states it
  captured_at       — when the evidence snapshot was taken
Result is labeled 'Candidate Earliest Observed Source' unless provenance
independently establishes the true origin.
"""
from sqlalchemy.orm import Session
from app.models.db import Post, Evidence

def _iso(dt):
    try:
        return dt.isoformat() if dt else None
    except Exception:
        return None

def run_origin(db: Session, case_id: str):
    posts = db.query(Post).filter(Post.case_id == case_id).order_by(
        Post.published_at.asc().nullslast(), Post.collected_at.asc()).all()
    ev_by_url = {}
    for e in db.query(Evidence).filter(Evidence.case_id == case_id).all():
        ev_by_url.setdefault(e.source_url or "", e)
    cands = []
    for p in posts[:20]:
        ev = ev_by_url.get(p.source_url or "")
        cands.append({
            "post_id": p.id, "url": p.source_url, "platform": p.platform,
            "first_observed_at": _iso(p.collected_at),
            "published_at": _iso(p.published_at),          # None => unknown, never invented
            "published_known": p.published_at is not None,
            "captured_at": _iso(ev.captured_at) if ev else _iso(p.collected_at),
            "evidence_id": ev.id if ev else None,
            "text_prefix": (p.clean_text or p.text or "")[:200],
        })
    return {"label": "Candidate Earliest Observed Source (not proven true origin)",
            "note": "first_observed_at = system observation; published_at = source-stated only; "
                    "collection time must not be presented as publication time.",
            "candidates": cands}
