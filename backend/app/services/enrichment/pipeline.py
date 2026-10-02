"""Enrichment pipeline orchestrator: prefilter -> clean -> LLM extract -> persist Claim rows."""
from sqlalchemy.orm import Session
from app.models.db import Post, Claim
from .prefilter import prefilter, content_hash
from .llm_extract import llm_extract
import uuid

def run_enrichment_for_post(db: Session, post: Post, keywords: list):
    keep, reason = prefilter(post.text, keywords)
    if not keep:
        return {"kept": False, "reason": reason}
    # sentiment over post text (visible comment text included when captured)
    from app.services.enrichment.sentiment import analyze as sentiment_analyze
    from app.services.enrichment.engagement import merge_engagement
    try:
        sent = sentiment_analyze(post.clean_text or post.text or "")
        eng = dict(post.engagement or {})
        eng["sentiment"] = sent["label"]
        eng["sentiment_score"] = sent["score"]
        eng["sentiment_pos"] = sent["pos"]
        eng["sentiment_neg"] = sent["neg"]
        post.engagement = merge_engagement(eng, post.clean_text or post.text or "")
    except Exception:
        pass
    data = llm_extract(post.clean_text or post.text, {"source_url": post.source_url, "platform": post.platform})
    # persist claims (item 12: drop clear boilerplate, keep count in debug return)
    from app.services.osint.relevance import is_boilerplate
    created, skipped_boilerplate = [], 0
    for c in data.get("claims", [])[:10]:
        txt = (c.get("text") if isinstance(c, dict) else str(c)) or ""
        if not txt.strip():
            continue
        if is_boilerplate(txt):
            skipped_boilerplate += 1
            continue
        claim = Claim(id=str(uuid.uuid4()), case_id=post.case_id, text=txt[:2000],
                      normalized_text=txt.lower().strip()[:2000],
                      topic=",".join(data.get("topics", [])[:5]))
        db.add(claim)
        created.append(claim)
    db.commit()
    return {"kept": True, "reason": reason, "claims": len(created),
            "skipped_boilerplate": skipped_boilerplate,
            "topics": data.get("topics", []),
            "mock": data.get("_meta", {}).get("mock", False)}
