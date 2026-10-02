"""Query C: Trace Spread. Typed edges with evidence. TRD Sec 11."""
from sqlalchemy.orm import Session
from app.models.db import Post, PostRelation
from app.services.enrichment.prefilter import normalize
import uuid
from difflib import SequenceMatcher

def sim(a: str, b: str) -> float:
    a, b = normalize(a)[:2000], normalize(b)[:2000]
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()

def run_spread(db: Session, case_id: str, threshold: float = 0.55):
    posts = db.query(Post).filter(Post.case_id == case_id).all()
    # pre-existing edges (e.g. exact-copy reposts recorded at ingest) — include, don't duplicate
    seen = set()
    reposted_pairs = set()
    edges = []
    for r in db.query(PostRelation).filter(PostRelation.case_id == case_id).all():
        seen.add((r.source_post_id, r.target_post_id, r.relation_type))
        if r.relation_type == "repost":
            reposted_pairs.add(frozenset((r.source_post_id, r.target_post_id)))
        edges.append({"from": r.source_post_id, "to": r.target_post_id,
                      "type": r.relation_type, "similarity": r.similarity})
    for i in range(len(posts)):
        for j in range(i + 1, len(posts)):
            if frozenset((posts[i].id, posts[j].id)) in reposted_pairs:
                continue  # exact repost already linked at ingest; don't add a twin edge
            s = sim(posts[i].clean_text or posts[i].text, posts[j].clean_text or posts[j].text)
            shared_url = bool(set((posts[i].text or "").split()) & set((posts[j].text or "").split()) and "http" in (posts[i].text + posts[j].text))
            if s >= threshold or shared_url:
                key = (posts[i].id, posts[j].id, "copy" if s >= threshold else "shared_url")
                if key in seen:
                    continue
                seen.add(key)
                rel = PostRelation(id=str(uuid.uuid4()), case_id=case_id,
                                   source_post_id=posts[i].id, target_post_id=posts[j].id,
                                   relation_type=key[2],
                                   similarity=round(s, 3), evidence_ids=[])
                db.add(rel)
                edges.append({"from": posts[i].id, "to": posts[j].id, "type": rel.relation_type, "similarity": round(s, 3)})
    db.commit()
    nodes = [{"id": p.id, "platform": p.platform, "url": p.source_url,
              "ts": str(p.published_at or p.collected_at)} for p in posts]
    return {"nodes": nodes, "edges": edges,
            "note": "Observed similarity / temporal clustering only. "
                    "Intent not established — do not infer coordinated campaign, "
                    "malicious coordination, bot activity, or disinformation operation."}
