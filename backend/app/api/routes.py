"""REST API - TRD Sec 14."""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.db import Case, CaseKeyword, Post, Evidence, Claim, AnalysisRun, AnalysisFinding, Assessment, AuditEvent
from app.schemas.api import CaseCreate, CollectRequest, AssessmentPatch
from app.services.collectors.manager import run_collection
from app.services.osint.runner import run_full_analysis
from app.services.assessment.service import build_assessment, VALID
from app.services.reporting.service import build_report, report_to_html
from fastapi.responses import HTMLResponse

router = APIRouter()

def _parse_dt(s):
    if not s:
        return None
    try:
        from dateutil import parser
        return parser.parse(s)
    except Exception:
        return None

@router.post("/cases")
def create_case(body: dict, db: Session = Depends(get_db)):
    """Accepts both legacy {title,objective,keywords,platforms} and UI
    {title,description,metadata:{target,targetType,objectives,platforms,dateRange}}."""
    meta = body.get("metadata") or {}
    title = body.get("title", "Untitled case")
    objective = body.get("objective", body.get("description", ""))
    kws = body.get("keywords", []) or []
    objs = meta.get("objectives", []) or []
    if isinstance(objs, str):
        objs = [objs]
    # Objectives are workflow steps ("verify claim", "trace propagation"), NOT
    # search terms. Merging them into keywords made every case query a platform
    # with junk and return nothing, so they are stored with their own type.
    kws = list(dict.fromkeys(kws))
    objs = list(dict.fromkeys(objs))
    plats = body.get("platforms", []) or meta.get("platforms", []) or ["rss", "web"]
    if not kws:
        # UI-created cases often carry no keywords: derive from title+objective
        import re as _re
        from collections import Counter as _Counter
        stop = {"with", "from", "that", "this", "have", "has", "are", "was", "were",
                "will", "would", "there", "their", "about", "into", "over", "under",
                "claim", "case", "check", "verify", "investigation", "against",
                "identify", "source", "earliest", "trace", "propagation", "analyze",
                "relationships", "detect", "coordination", "media", "generate",
                "report", "account", "grab", "info", "find"}
        words = _re.findall(r"[A-Za-z]{5,}", f"{title} {objective}")
        freq = _Counter(w.lower() for w in words if w.lower() not in stop)
        kws = [w for w, _ in freq.most_common(10)]
    cid = str(uuid.uuid4())
    c = Case(id=cid, title=title, objective=objective, status="open",
             platforms=plats, time_from=_parse_dt(body.get("time_from")),
             time_to=_parse_dt(body.get("time_to")))
    db.add(c)
    for kw in kws:
        db.add(CaseKeyword(id=str(uuid.uuid4()), case_id=cid, keyword=kw,
                           normalized_keyword=str(kw).lower().strip(), type="keyword"))
    for ob in objs:
        db.add(CaseKeyword(id=str(uuid.uuid4()), case_id=cid, keyword=ob,
                           normalized_keyword=str(ob).lower().strip(), type="objective"))
    db.commit()
    from app.api.ui import ui_case as _ui_case
    return _ui_case(db, c)

@router.get("/cases")
def list_cases(limit: int = 50, db: Session = Depends(get_db)):
    from app.api.ui import ui_case as _ui_case
    rows = db.query(Case).order_by(Case.created_at.desc()).limit(min(limit, 200)).all()
    items = [_ui_case(db, c) for c in rows]
    return {"data": items, "total": len(items), "page": 1, "per_page": limit, "total_pages": 1}

@router.get("/cases/{cid}")
def case_detail(cid: str, db: Session = Depends(get_db)):
    c = db.query(Case).filter(Case.id == cid).first()
    if not c:
        raise HTTPException(404, "case not found")
    from app.api.ui import ui_case as _ui_case, case_keywords as _kws
    out = _ui_case(db, c)
    out["keywords"] = _kws(db, cid)  # legacy field, real search terms only
    return out

@router.post("/cases/{cid}/collect")
def collect(cid: str, body: CollectRequest, db: Session = Depends(get_db)):
    if not db.query(Case).filter(Case.id == cid).first():
        raise HTTPException(404, "case not found")
    return run_collection(db, cid, body.sources, body.max_items)

@router.get("/cases/{cid}/evidence")
def list_evidence(cid: str, db: Session = Depends(get_db)):
    from app.api.ui import ui_evidence as _ue
    if not db.query(Case).filter(Case.id == cid).first():
        raise HTTPException(404, "case not found")
    pubs = {p.source_url: p.published_at.isoformat() if p.published_at else None
            for p in db.query(Post).filter(Post.case_id == cid).all()}
    plats = {p.source_url: p.platform
             for p in db.query(Post).filter(Post.case_id == cid).all()}
    return {"data": [_ue(e, pubs.get(e.source_url), plats.get(e.source_url, ""))
                     for e in db.query(Evidence).filter(Evidence.case_id == cid)
                     .order_by(Evidence.captured_at.desc()).all()]}


@router.get("/evidence/{eid}/view")
def view_evidence(eid: str, db: Session = Depends(get_db)):
    """Render the stored snapshot safely (item 8). HTML is sandboxed; never called a screenshot."""
    import os
    from fastapi.responses import Response, PlainTextResponse
    from app.core.config import settings
    e = db.query(Evidence).filter(Evidence.id == eid).first()
    if not e:
        raise HTTPException(404, "evidence not found")
    path = os.path.join(settings.EVIDENCE_DIR, e.object_uri or "")
    if not os.path.isfile(path):
        raise HTTPException(404, "snapshot file missing from storage")
    with open(path, "rb") as f:
        data = f.read()
    et = (e.evidence_type or "").lower()
    if et in ("html_snapshot", "html", "authenticated_snapshot"):
        # allow-scripts: React-style snapshots need their own JS to render.
        # No allow-same-origin: isolated opaque origin, cannot touch this app.
        return Response(content=data, media_type="text/html",
                        headers={"Content-Security-Policy": "sandbox allow-scripts",
                                 "X-Content-Type-Options": "nosniff"})
    if et in ("image", "screenshot"):
        mt = "image/png" if path.lower().endswith(".png") else "image/jpeg"
        return Response(content=data, media_type=mt)
    return PlainTextResponse(data.decode("utf-8", errors="replace"))


@router.get("/evidence/{eid}/verify")
def verify_evidence(eid: str, db: Session = Depends(get_db)):
    """Recompute SHA-256 over the stored artifact (item 8)."""
    import os
    import hashlib
    from app.core.config import settings
    e = db.query(Evidence).filter(Evidence.id == eid).first()
    if not e:
        raise HTTPException(404, "evidence not found")
    path = os.path.join(settings.EVIDENCE_DIR, e.object_uri or "")
    if not os.path.isfile(path):
        return {"evidence_id": eid, "status": "MISSING_FILE", "match": False,
                "stored_sha256": e.sha256, "computed_sha256": None}
    h = hashlib.sha256(open(path, "rb").read()).hexdigest()
    return {"evidence_id": eid, "status": "MATCH" if h == e.sha256 else "MISMATCH",
            "match": h == e.sha256, "stored_sha256": e.sha256, "computed_sha256": h}

@router.post("/cases/{cid}/keywords")
def add_keywords(cid: str, body: dict, db: Session = Depends(get_db)):
    """Attach real search terms to a case.

    Only type='keyword' rows are written. Workflow objectives live in the same
    table with type='objective' and must never become search terms - doing so
    made every platform search return nothing.
    """
    if not db.query(Case).filter(Case.id == cid).first():
        raise HTTPException(404, "case not found")
    kws = body.get("keywords") or []
    if isinstance(kws, str):
        kws = [kws]
    kws = [str(k).strip() for k in kws if str(k).strip()][:25]
    if not kws:
        raise HTTPException(400, "no keywords supplied")
    existing = {
        k.normalized_keyword
        for k in db.query(CaseKeyword).filter(CaseKeyword.case_id == cid,
                                              CaseKeyword.type != "objective").all()
    }
    added = []
    for kw in kws:
        nk = kw.lower()
        if nk in existing:
            continue
        existing.add(nk)
        db.add(CaseKeyword(id=str(uuid.uuid4()), case_id=cid, keyword=kw,
                           normalized_keyword=nk, type="keyword"))
        added.append(kw)
    db.commit()
    return {"added": added, "total": len(existing)}


@router.get("/cases/{cid}/claims")
def list_claims(cid: str, db: Session = Depends(get_db)):
    from app.api.ui import ui_claim as _uc
    if not db.query(Case).filter(Case.id == cid).first():
        raise HTTPException(404, "case not found")
    dmap: dict = {}
    for f in db.query(AnalysisFinding).filter(
            AnalysisFinding.case_id == cid, AnalysisFinding.finding_type == "D_verification").all():
        for v in (f.payload_json or {}).get("items", []):
            dmap[v.get("claim_id")] = v  # latest run wins
    return {"data": [_uc(db, c, dmap) for c in db.query(Claim).filter(Claim.case_id == cid).order_by(Claim.created_at.desc()).all()]}

@router.post("/cases/{cid}/claims")
def add_claim(cid: str, body: dict, db: Session = Depends(get_db)):
    c = Claim(id=str(uuid.uuid4()), case_id=cid, text=body.get("text", "")[:2000],
              normalized_text=body.get("text", "").lower()[:2000], topic=body.get("topic", ""))
    db.add(c)
    db.commit()
    return {"id": c.id}

@router.post("/cases/{cid}/analysis")
def run_analysis(cid: str, body: dict | None = None, db: Session = Depends(get_db)):
    atype = (body or {}).get("analysis_type", "full")
    res = run_full_analysis(db, cid, atype)
    # auto-build assessment from D results
    if "D_verification" in res:
        build_assessment(db, cid, verify_results=res["D_verification"])
    return res

@router.get("/cases/{cid}/findings")
def findings(cid: str, db: Session = Depends(get_db)):
    return [{"id": f.id, "type": f.finding_type, "confidence": f.confidence, "payload": f.payload_json}
            for f in db.query(AnalysisFinding).filter(AnalysisFinding.case_id == cid).all()]

@router.get("/cases/{cid}/assessment")
def get_assessment(cid: str, db: Session = Depends(get_db)):
    return [{"id": a.id, "label": a.label, "confidence": a.confidence, "factors": a.factors_json,
             "evidence_refs": a.evidence_refs, "override": a.analyst_override, "rationale": a.rationale}
            for a in db.query(Assessment).filter(Assessment.case_id == cid).all()]

@router.patch("/cases/{cid}/assessment")
def patch_assessment(cid: str, body: AssessmentPatch, db: Session = Depends(get_db)):
    a = db.query(Assessment).filter(Assessment.case_id == cid).order_by(Assessment.created_at.desc()).first()
    if not a:
        raise HTTPException(404, "no assessment yet - run analysis first")
    before = {"label": a.label}
    if body.label:
        if body.label not in VALID:
            raise HTTPException(400, f"label must be one of {VALID}")
        a.label = body.label
        a.analyst_override = body.label
    a.rationale = (a.rationale or "") + f"\n[override by {body.actor}]: {body.rationale}"
    db.add(AuditEvent(id=str(uuid.uuid4()), actor=body.actor, action="assessment_override",
                      entity_type="assessment", entity_id=a.id,
                      before_json=before, after_json={"label": a.label}))
    db.commit()
    return {"id": a.id, "label": a.label, "override": a.analyst_override}

@router.get("/cases/{cid}/report")
def report(cid: str, format: str = "json", db: Session = Depends(get_db)):
    rep = build_report(db, cid)
    if not rep:
        raise HTTPException(404, "case not found")
    if format == "html":
        return HTMLResponse(report_to_html(rep))
    return rep
