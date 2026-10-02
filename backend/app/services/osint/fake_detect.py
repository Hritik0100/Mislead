"""Query A: Identify Fake News (scan & detect). PRD 7.5."""
from sqlalchemy.orm import Session
from app.models.db import Claim, Post

SUSPICIOUS = ["breaking", "shocking", "urgent", "share before deleted", "100% true", "secret", "exposed", "hoax", "alert"]

def run_fake_detect(db: Session, case_id: str):
    claims = db.query(Claim).filter(Claim.case_id == case_id).all()
    out = []
    for c in claims:
        t = (c.text or "").lower()
        hits = [w for w in SUSPICIOUS if w in t]
        score = min(0.9, 0.3 + 0.15 * len(hits) + (0.1 if len(c.text or "") > 200 else 0))
        out.append({"claim_id": c.id, "claim": c.text[:300], "signals": hits,
                    "suspicion": round(score, 2), "needs_review": True})
    return out
