"""Assessment engine: core-claim verdict + explainable metrics (items 2, 14).

Outputs (stored in factors_json + returned):
  core_verdict: TRUE | FALSE | PARTIALLY VERIFIED | UNVERIFIED
  evidence_confidence: LOW | MEDIUM | HIGH   (NOT a probability of truth)
  claim_coverage: % of relevant factual claims with >=1 supporting evidence
  supporting_evidence / contradicting_evidence counts (evidence IDs, deduped)
  truth_score_system: internal mean-label metric, explicitly labeled as such —
    NEVER presented as probability.

Core claim = relevant factual/numerical/attribution claim with the highest
relevance_score (tie: earliest created). Secondary details reported separately;
an unverified side-detail never downgrades a verified core event.
"""
from sqlalchemy.orm import Session
from app.models.db import Assessment, Claim, Case
import uuid

VALID = ["True", "False", "Misleading", "Context Missing", "Unverified"]
_SCORE = {"Verified": 100, "Partially Verified": 55, "Unverified": 30,
          "Contradicted": 0, "Misleading": 15, "False": 0, "True": 100,
          "Context Missing": 55, "Rhetoric": 0, "Irrelevant": 0}


def _core_item(verify_results, db: Session, case_id: str, case_text: str = ""):
    """Core = the claim that best answers the investigation OBJECTIVE (item: fix core claim).

    NOT by confidence, evidence count, claim order, or claim type.
    Score = 2x objective bigram overlap + objective unigram overlap + relevance.
    Only relevant factual/numerical/attribution claims are eligible.
    """
    from app.services.osint.relevance import _toks, _bigrams
    obj_toks = _toks(case_text or "")
    obj_bi = _bigrams(obj_toks)
    obj_set = set(obj_toks)
    eligible = [v for v in (verify_results or [])
                if not v.get("excluded_from_scoring")
                and v.get("relevance") == "relevant"
                and v.get("claim_type") in ("factual", "numerical", "attribution")]
    if not eligible:
        eligible = [v for v in (verify_results or [])
                    if not v.get("excluded_from_scoring")
                    and v.get("claim_type") in ("factual", "numerical", "attribution")]
    if not eligible:
        return None
    order = {c.id: c.created_at for c in db.query(Claim).filter(Claim.case_id == case_id).all()}

    def objective_score(v):
        ct = _toks(v.get("claim") or "")
        bi = len(_bigrams(ct) & obj_bi) * 2.0
        uni = len(set(ct) & obj_set) * 0.5
        return bi + uni + v.get("relevance_score", 0)

    return sorted(eligible,
                  key=lambda v: (-objective_score(v),
                                 str(order.get(v.get("claim_id"), ""))))[0]


def build_assessment(db: Session, case_id: str, claim_id=None, verify_results=None):
    verify_results = verify_results or []
    case = db.query(Case).filter(Case.id == case_id).first()
    case_text = f"{case.title} {case.objective}" if case else ""
    # new-schema items only: old runs predate relevance/evidence-ID fields
    verify_results = [v for v in verify_results if "relevance" in v]
    factual = [v for v in verify_results if not v.get("excluded_from_scoring")]
    core = _core_item(verify_results, db, case_id, case_text)

    supp_ids = sorted({e for v in factual for e in v.get("supporting_evidence_ids", [])})
    contra_ids = sorted({e for v in factual for e in v.get("contradicting_evidence_ids", [])})
    covered = sum(1 for v in factual if v.get("supporting_evidence_ids"))
    coverage = round(100 * covered / len(factual)) if factual else 0
    indep_total = sum(v.get("independent_sources", 0) for v in factual)

    if core is None:
        core_verdict, label, conf = "UNVERIFIED", "Unverified", 0.30
    else:
        st = core.get("status")
        if st == "Verified":
            core_verdict, label = "TRUE", "True"
        elif st == "Contradicted":
            core_verdict, label = "FALSE", "False"
        elif st == "Partially Verified":
            core_verdict, label = "PARTIALLY VERIFIED", "Misleading"
        else:
            core_verdict, label = "UNVERIFIED", "Unverified"
        conf = core.get("confidence", 0.3)

    if core_verdict == "TRUE" and indep_total >= 2 and not contra_ids:
        ev_conf = "HIGH"
    elif core_verdict == "FALSE" and contra_ids:
        ev_conf = "HIGH"
    elif indep_total >= 1 or supp_ids:
        ev_conf = "MEDIUM"
    else:
        ev_conf = "LOW"

    mean_score = (round(sum(_SCORE.get(v.get("status"), 30) for v in factual) / len(factual))
                  if factual else 0)
    secondary = [{"claim_id": v.get("claim_id"), "claim": (v.get("claim") or "")[:160],
                  "status": v.get("status"),
                  "missing": v.get("missing_details", [])}
                 for v in factual if v is not core][:8]
    factors = {
        "core_verdict": core_verdict,
        "core_claim_id": (core or {}).get("claim_id"),
        "claim_roles": {v.get("claim_id"): ("core" if core and v.get("claim_id") == core.get("claim_id") else "supporting")
                        for v in factual if v.get("claim_type") in ("factual", "numerical", "attribution")},
        "evidence_confidence": ev_conf,
        "claim_coverage": coverage,
        "supporting_evidence": len(supp_ids),
        "contradicting_evidence": len(contra_ids),
        "truth_score_system": mean_score,
        "truth_score_note": ("Internal mean-label metric over relevant factual claims only; "
                             "NOT a probability of truth."),
        "independent_sources_total": indep_total,
        "secondary_details": secondary,
        "evidence_coverage": len(supp_ids) + len(contra_ids),
        "source_agreement": len(supp_ids),
        "source_contradiction": len(contra_ids),
    }
    a = Assessment(id=str(uuid.uuid4()), case_id=case_id,
                   claim_id=claim_id or (core or {}).get("claim_id"),
                   label=label, confidence=conf, factors_json=factors,
                   evidence_refs=(supp_ids + contra_ids)[:50],
                   rationale=(f"Core verdict {core_verdict} from core claim "
                              f"{((core or {}).get('claim') or '')[:160]}. "
                              f"Coverage {coverage}% over {len(factual)} relevant factual claims; "
                              f"{len(supp_ids)} supporting / {len(contra_ids)} contradicting evidence. "
                              f"Confidence is NOT probability of truth."))
    db.add(a)
    db.commit()
    return a
