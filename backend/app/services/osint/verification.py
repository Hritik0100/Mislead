"""Query D: Verify Claim vs retrieved evidence (items 1,3,4,5,6,7,9,13,14).

- Every claim classified (type + relevance); irrelevant/rhetoric/boilerplate are
  marked and EXCLUDED from factual scoring (kept in output for audit, never in counts).
- Supporting/contradicting reference EVIDENCE IDs (mapped from posts via source_url),
  not bare post IDs.
- Source independence: distinct registrable domains = independent; same-domain
  extras = derivative/duplicate. Analyst seeds corroborate only weakly and are
  never counted as independent.
- Confidence is computed from evidence quality (documented formula below),
  never a fixed constant.
- Statuses: Verified | Partially Verified | Contradicted | Unverified |
  Irrelevant | Rhetoric. Partially Verified always explains what is missing.

Confidence formula (0.05–0.95):
  start 0.30
  + 0.12 per independent supporting source (cap +0.36)
  + 0.08 if >=1 supporting source has a known publication time (temporal consistency)
  + 0.05 if supporting evidence spans >1 platform
  - 0.15 per contradicting source (cap -0.30)
  seeds-only support caps the result at 0.35
"""
from urllib.parse import urlparse
from sqlalchemy.orm import Session
from app.models.db import Claim, Post, Evidence, Case, CaseKeyword
from app.services.osint.relevance import classify

_CONTRADICT_WORDS = ("false", "debunk", "untrue", "no evidence", "fake", "scam", "hoax")


def _domain(url: str) -> str:
    try:
        host = (urlparse(url or "").netloc or "").lower()
        if host.startswith("www."):
            host = host[4:]
        parts = host.split(".")
        return ".".join(parts[-2:]) if len(parts) >= 2 else host
    except Exception:
        return ""


def _is_seed_post(p: Post) -> bool:
    url = p.source_url or ""
    return url.startswith("http://example.invalid") or bool((p.engagement or {}).get("stub"))


def _is_seed_evidence(e: Evidence) -> bool:
    return (e.source_url or "").startswith("http://example.invalid")


def _post_evidence_map(db: Session, case_id: str) -> dict[str, str]:
    """post_id -> evidence_id via shared source_url (no schema change)."""
    m: dict[str, str] = {}
    evs = db.query(Evidence).filter(Evidence.case_id == case_id).all()
    by_url: dict[str, str] = {}
    for e in evs:
        by_url.setdefault(e.source_url or "", e.id)
    for p in db.query(Post).filter(Post.case_id == case_id).all():
        if (p.source_url or "") in by_url:
            m[p.id] = by_url[p.source_url or ""]
    return m


def _case_context(db: Session, case_id: str):
    case = db.query(Case).filter(Case.id == case_id).first()
    kws = [k.normalized_keyword for k in
           db.query(CaseKeyword).filter(CaseKeyword.case_id == case_id).all()]
    text = ""
    if case:
        text = f"{case.title} {case.objective}"
    return kws, text


def run_verification(db: Session, case_id: str):
    claims = db.query(Claim).filter(Claim.case_id == case_id).all()
    posts = db.query(Post).filter(Post.case_id == case_id).all()
    kws, case_text = _case_context(db, case_id)
    ev_map = _post_evidence_map(db, case_id)
    ev_by_id = {e.id: e for e in db.query(Evidence).filter(Evidence.case_id == case_id).all()}
    results = []

    for c in claims:
        words = [w for w in (c.normalized_text or "").split() if len(w) > 4][:15]
        cls = classify(c.text or "", case_text, kws)
        ctype, rel = cls["claim_type"], cls["relevance"]

        # bucket posts by overlap
        supp_posts, contra_posts = [], []
        for p in posts:
            pt = (p.clean_text or p.text or "").lower()
            overlap = sum(1 for w in words if w in pt)
            hits_contra_word = any(n in pt for n in _CONTRADICT_WORDS)
            if hits_contra_word and overlap >= 2:
                contra_posts.append(p)
            elif overlap >= 3:
                supp_posts.append(p)

        def ev_ids(ps):
            out = []
            for p in ps:
                eid = ev_map.get(p.id)
                out.append(eid if eid else f"post:{p.id[:8]}")
            return out

        supp_ev = ev_ids(supp_posts)
        contra_ev = ev_ids(contra_posts)

        # independence (item 4): distinct real domains; seeds never independent
        real_domains = {_domain(ev_by_id[e].source_url) for e in supp_ev
                        if not e.startswith("post:") and e in ev_by_id
                        and not _is_seed_evidence(ev_by_id[e])}
        real_domains.discard("")
        seed_count = sum(1 for e in supp_ev
                         if (e in ev_by_id and _is_seed_evidence(ev_by_id[e])))
        independent = len(real_domains)
        derivative = max(0, len([e for e in supp_ev if not e.startswith("post:")])
                         - independent - seed_count)

        item = {
            "claim_id": c.id,
            "claim": (c.text or "")[:500],
            "claim_type": ctype,
            "type_reason": cls["type_reason"],
            "relevance": rel,
            "relevance_reason": cls["relevance_reason"],
            "relevance_score": cls["relevance_score"],
            "supporting_evidence_ids": supp_ev,
            "contradicting_evidence_ids": contra_ev,
            "supporting_sources": len(supp_ev),
            "contradicting_sources": len(contra_ev),
            "independent_sources": independent,
            "derivative_or_duplicate_sources": derivative,
            "analyst_seed_sources": seed_count,
            "excluded_from_scoring": False,
            "verification_status": "pending",
        }

        # non-factual / off-topic: classify, exclude from scoring (items 1,5,6,13)
        if ctype in ("boilerplate", "metadata"):
            item.update(status="Irrelevant", label_candidate="Unverified", confidence=0.05,
                        verification_status="not_applicable",
                        rationale="Boilerplate/page chrome — not an investigative claim.",
                        excluded_from_scoring=True)
        elif ctype == "rhetoric":
            item.update(status="Rhetoric", label_candidate="Unverified", confidence=0.05,
                        verification_status="not_applicable",
                        rationale="Rhetorical slogan without a verifiable proposition; excluded from factual score.",
                        excluded_from_scoring=True)
        elif ctype == "opinion":
            item.update(status="Unverified", label_candidate="Unverified", confidence=0.15,
                        verification_status="opinion — not fact-checkable as stated",
                        rationale="Opinion; no factual proposition to verify.",
                        excluded_from_scoring=True)
        elif rel == "irrelevant":
            item.update(status="Irrelevant", label_candidate="Unverified", confidence=0.05,
                        verification_status="not_applicable",
                        rationale=f"Off-topic for this investigation ({cls['relevance_reason']}); excluded from score.",
                        excluded_from_scoring=True)
        else:
            # factual scoring with variable confidence (items 3, 5)
            conf = 0.30 + min(0.36, 0.12 * independent)
            platforms = {p.platform for p in supp_posts}
            known_time = any(getattr(p, "published_at", None) for p in supp_posts)
            if known_time:
                conf += 0.08
            if len(platforms) > 1:
                conf += 0.05
            conf -= min(0.30, 0.15 * len(contra_posts))
            only_seeds = seed_count > 0 and independent == 0
            if only_seeds:
                conf = min(conf, 0.35)
            conf = round(max(0.05, min(0.95, conf)), 2)

            missing = []
            if independent == 0 and supp_posts:
                missing.append("no independent source — only analyst seeds" if only_seeds
                               else "single/derivative sourcing; needs independent corroboration")
            if ctype == "numerical" and independent < 2:
                missing.append("exact figure from fewer than two independent sources")
            if contra_posts:
                missing.append(f"contested by {len(contra_posts)} source(s)")

            if contra_posts and not supp_posts:
                status, label = "Contradicted", "False"
            elif contra_posts and supp_posts:
                status, label = "Partially Verified", "Misleading"
                missing.append("evidence conflicts across sources")
            elif independent >= 2 and len(supp_posts) >= 2:
                status, label = "Verified", "True"
            elif supp_posts:
                status, label = "Partially Verified", "Context Missing"
            else:
                status, label = "Unverified", "Unverified"
                missing.append("no supporting evidence retrieved")

            rationale = (f"{len(supp_posts)} supporting ({independent} independent, "
                         f"{derivative} derivative, {seed_count} seeds), "
                         f"{len(contra_posts)} contradicting. "
                         + ("Missing: " + "; ".join(missing) + "." if missing else
                            "Corroborated by multiple independent sources."))
            item.update(status=status, label_candidate=label, confidence=conf,
                        verification_status="verified" if status == "Verified" else "assessed",
                        rationale=rationale,
                        missing_details=missing)
        results.append(item)
    return results
