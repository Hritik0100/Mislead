"""UI-compat layer for the Next.js frontend (osint-nexus).
Serves exactly the endpoints + JSON shapes the UI expects, mapped from the
real collector/enrichment/OSINT data. No mock data: every row comes from the DB.
Conventions (from src/lib): single objects raw, lists wrapped as {data:[...]}.
"""
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.database import get_db
from app.models.db import (
    Case, CaseKeyword, Account, Post, Media, Evidence, Claim,
    ClaimEvidence, PostRelation, AnalysisRun, AnalysisFinding,
    Assessment, AuditEvent,
)
from app.services.osint.runner import run_full_analysis
from app.services.assessment.service import build_assessment
from app.services.reporting.service import build_report

router = APIRouter()

def _iso(dt):
    try:
        return dt.isoformat() if dt else datetime.now(timezone.utc).isoformat()
    except Exception:
        return datetime.now(timezone.utc).isoformat()

def _domain(url: str) -> str:
    try:
        return urlparse(url or "").netloc or (url or "")[:40]
    except Exception:
        return ""

# ---------- shared mappers ----------
def case_keywords(db: Session, case_id: str) -> list:
    """Search/claim keywords only.

    Workflow objectives (type='objective': "verify claim", "trace propagation")
    live in the same table but are NOT search terms. Returning them as keywords
    made the UI build a platform query out of them, so every search came back
    empty.
    """
    return [k.keyword for k in
            db.query(CaseKeyword).filter(CaseKeyword.case_id == case_id,
                                         CaseKeyword.type != "objective").all()]


def case_objectives(db: Session, case_id: str) -> list:
    return [k.keyword for k in
            db.query(CaseKeyword).filter(CaseKeyword.case_id == case_id,
                                         CaseKeyword.type == "objective").all()]


def ui_case(db: Session, c: Case) -> dict:
    kws = case_keywords(db, c.id)
    ev = db.query(func.count(Evidence.id)).filter(Evidence.case_id == c.id).scalar() or 0
    cl = db.query(func.count(Claim.id)).filter(Claim.case_id == c.id).scalar() or 0
    ac = db.query(func.count(func.distinct(Post.account_id))).filter(Post.case_id == c.id).scalar() or 0
    return {
        "id": c.id, "title": c.title, "description": c.objective or "",
        "objective": c.objective or "", "keywords": kws,
        "objectives": case_objectives(db, c.id),
        "status": c.status if c.status in ("open", "investigating", "closed", "archived") else "open",
        "priority": "medium", "created_by": "analyst", "assigned_to": [], "tags": kws[:8],
        "platforms": c.platforms or [],
        "created_at": _iso(c.created_at), "updated_at": _iso(c.updated_at),
        "metadata": {"evidenceCount": ev, "claimCount": cl, "accountCount": ac},
    }

def ui_post(p: Post, acc: Account | None = None) -> dict:
    eng = p.engagement or {}
    txt = p.clean_text or p.text or ""
    return {
        "id": p.id, "case_id": p.case_id, "account_id": p.account_id, "platform": p.platform,
        "author_username": (acc.username if acc else ""),
        "author_display": (acc.display_name if acc else ""),
        "author_profile": (acc.profile_url if acc else ""),
        "content": txt, "text": txt[:500], "post_url": p.source_url, "url": p.source_url,
        "media_urls": [], "likes": eng.get("likes", 0), "shares": eng.get("shares", 0),
        "comments": eng.get("comments", 0),
        "posted_at": _iso(p.published_at or p.collected_at), "collected_at": _iso(p.collected_at),
        "published_at": _iso(p.published_at or p.collected_at), "topics": [],
        "sentiment": eng.get("sentiment"), "sentiment_score": eng.get("sentiment_score", 0.0),
    }

def ui_account(db: Session, a: Account, case_id: str = "") -> dict:
    pc = db.query(func.count(Post.id)).filter(Post.account_id == a.id)
    if case_id:
        pc = pc.filter(Post.case_id == case_id)
    return {
        "id": a.id, "case_id": case_id, "platform": a.platform, "username": a.username,
        "display_name": a.display_name or a.username, "profile_url": a.profile_url or "",
        "followers": 0, "following": 0, "post_count": pc.scalar() or 0,
        "verified": False, "created_at": _iso(a.first_seen_at), "updated_at": _iso(a.first_seen_at),
    }

_EVTYPES = {"screenshot": "screenshot", "image": "image", "video": "video",
            "html_snapshot": "html", "html": "html", "text": "text",
            "authenticated_snapshot": "html"}

def _source_type(platform: str, url: str, evidence_type: str = "") -> tuple[str, bool]:
    """(source_type, is_analyst_seed). Provenance for report display (spec taxonomy):
    public_web | authenticated_browser | analyst_provided | analyst_derived | secondary_reporting."""
    u = url or ""
    p = (platform or "").lower()
    if u.startswith("http://example.invalid"):
        return "analyst_seed", True
    if (evidence_type or "") == "authenticated_snapshot":
        return "authenticated_browser", False
    if (evidence_type or "") == "screenshot" and p not in ("web", "rss", "manual", ""):
        # Only the authenticated browser captures real screenshot files;
        # stubs/manual never produce them.
        return "authenticated_browser", False
    if p == "rss":
        return "secondary_reporting", False
    if p == "web":
        return "public_web", False
    if p == "manual":
        return "analyst_provided", False
    return "social_stub", False

def ui_evidence(e: Evidence, published_at=None, platform: str = "") -> dict:
    stype, seed = _source_type(platform, e.source_url, e.evidence_type)
    snap = _EVTYPES.get((e.evidence_type or "").lower(), "html")
    if snap == "screenshot":
        snap_label = "screenshot"
    else:
        snap_label = f"{snap} snapshot (not a screenshot)"
    return {
        "id": e.id, "case_id": e.case_id,
        "type": _EVTYPES.get((e.evidence_type or "").lower(), "link"),
        "title": _domain(e.source_url) or e.evidence_type,
        "description": f"{e.evidence_type} captured {_iso(e.captured_at)[:19]}",
        "url": e.source_url, "file_path": e.object_uri, "hash": e.sha256,
        "sha256": e.sha256, "tags": [], "added_by": "collector",
        "created_at": _iso(e.captured_at), "captured_at": _iso(e.captured_at),
        "published_at": published_at,
        "source_type": stype, "is_analyst_seed": seed,
        "snapshot_type": snap_label,
        "verification": "unverified" if seed else "hash-stored",
    }

_STATUS_BADGE = {"Verified": "verified", "Contradicted": "debunked",
                 "Partially Verified": "contested", "Unverified": "pending",
                 "Irrelevant": "pending", "Rhetoric": "pending", "True": "verified",
                 "False": "debunked", "Misleading": "contested", "Context Missing": "contested"}

def ui_claim(db: Session, c: Claim, dmap: dict | None = None) -> dict:
    nec = db.query(func.count(ClaimEvidence.id)).filter(ClaimEvidence.claim_id == c.id).scalar() or 0
    v = (dmap or {}).get(c.id, {})
    status = v.get("status", "Unverified") if v else "Unverified"
    conf = v.get("confidence", 0.0) if v else 0.0
    supp = len(v.get("supporting_evidence_ids", [])) if v else 0
    contra = len(v.get("contradicting_evidence_ids", [])) if v else 0
    return {
        "id": c.id, "case_id": c.case_id, "text": c.text, "topic": c.topic or "",
        "category": "unverified", "confidence": conf, "evidence_count": supp + contra,
        "supporting_count": supp, "contradicting_count": contra,
        "status": _STATUS_BADGE.get(status, "pending"),
        "verification_status": status,
        "claim_type": v.get("claim_type", "factual"),
        "relevance": v.get("relevance", "relevant"),
        "created_at": _iso(c.created_at), "updated_at": _iso(c.created_at),
        "metadata": {"earliestSource": "", "cluster": (c.topic or "")},
    }

def _case_or_404(db: Session, cid: str) -> Case:
    c = db.query(Case).filter(Case.id == cid).first()
    if not c:
        raise HTTPException(404, "case not found")
    return c

# ---------- dashboard stats ----------
@router.get("/stats/dashboard")
def stats_dashboard(db: Session = Depends(get_db)):
    return {
        "totalCases": db.query(func.count(Case.id)).scalar() or 0,
        "activeInvestigations": db.query(func.count(Case.id)).filter(Case.status.in_(["open", "investigating"])).scalar() or 0,
        "accountsDiscovered": db.query(func.count(Account.id)).scalar() or 0,
        "postsCollected": db.query(func.count(Post.id)).scalar() or 0,
        "claimsAnalyzed": db.query(func.count(Claim.id)).scalar() or 0,
        "evidenceCollected": db.query(func.count(Evidence.id)).scalar() or 0,
    }

# ---------- dashboard stats ----------
@router.get("/cases/{cid}/posts")
def ui_posts(cid: str, db: Session = Depends(get_db)):
    _case_or_404(db, cid)
    posts = db.query(Post).filter(Post.case_id == cid).order_by(Post.collected_at.desc()).all()
    aids = {a.id for a in db.query(Account).filter(
        Account.id.in_([p.account_id for p in posts if p.account_id])).all()} if posts else set()
    accounts = {a.id: a for a in db.query(Account).filter(Account.id.in_(aids)).all()} if aids else {}
    return {"data": [ui_post(p, accounts.get(p.account_id)) for p in posts]}

@router.get("/cases/{cid}/accounts")
def ui_accounts(cid: str, db: Session = Depends(get_db)):
    _case_or_404(db, cid)
    aids = [r[0] for r in db.query(func.distinct(Post.account_id)).filter(Post.case_id == cid).all()]
    accs = db.query(Account).filter(Account.id.in_(aids)).all() if aids else []
    return {"data": [ui_account(db, a, cid) for a in accs]}

# ---------- per-case lists (claims/evidence live in routes.py, wrapped) ----------
@router.get("/cases/{cid}/timeline")
def ui_timeline(cid: str, db: Session = Depends(get_db)):
    _case_or_404(db, cid)
    evts = []
    for p in db.query(Post).filter(Post.case_id == cid).all():
        acc = db.query(Account).filter(Account.id == p.account_id).first()
        evts.append({"id": f"t-{p.id}", "case_id": cid, "type": "post_collected",
                     "title": f"Post collected from @{acc.username if acc else '?' } ({p.platform})",
                     "description": (p.clean_text or p.text or "")[:160],
                     "timestamp": _iso(p.published_at or p.collected_at),
                     "related_ids": {"account_id": p.account_id, "post_id": p.id}})
    for c in db.query(Claim).filter(Claim.case_id == cid).all():
        evts.append({"id": f"c-{c.id}", "case_id": cid, "type": "claim_made",
                     "title": "Claim extracted", "description": (c.text or "")[:160],
                     "timestamp": _iso(c.created_at),
                     "related_ids": {"claim_id": c.id}})
    for e in db.query(Evidence).filter(Evidence.case_id == cid).all():
        evts.append({"id": f"e-{e.id}", "case_id": cid, "type": "evidence_added",
                     "title": f"Evidence captured ({e.evidence_type})",
                     "description": e.source_url[:160], "timestamp": _iso(e.captured_at),
                     "related_ids": {"evidence_id": e.id}})
    for r in db.query(AnalysisRun).filter(AnalysisRun.case_id == cid).all():
        evts.append({"id": f"r-{r.id}", "case_id": cid, "type": "analysis_update",
                     "title": f"Analysis run: {r.analysis_type}", "description": f"model {r.model}",
                     "timestamp": _iso(r.finished_at), "related_ids": {}})
    evts.sort(key=lambda x: x["timestamp"], reverse=True)
    return {"data": evts}

@router.get("/cases/{cid}/graph")
def ui_graph(cid: str, db: Session = Depends(get_db)):
    import math
    _case_or_404(db, cid)
    nodes, edges = [], []
    accs = {}
    for p in db.query(Post).filter(Post.case_id == cid).all():
        a = db.query(Account).filter(Account.id == p.account_id).first()
        if a and a.id not in accs:
            accs[a.id] = True
            nodes.append({"id": a.id, "type": "account", "label": f"@{a.username}",
                          "data": {"platform": a.platform}})
        nodes.append({"id": p.id, "type": "post", "label": (p.clean_text or p.text or "")[:60] or p.id[:8],
                      "data": {"platform": p.platform, "url": p.source_url}})
        if a:
            edges.append({"id": f"e-pb-{p.id}", "source": a.id, "target": p.id,
                          "type": "posted_by", "weight": 1})
    for c in db.query(Claim).filter(Claim.case_id == cid).all():
        nodes.append({"id": c.id, "type": "claim", "label": (c.text or "")[:60], "data": {}})
    for r in db.query(PostRelation).filter(PostRelation.case_id == cid).all():
        et = "shares" if r.relation_type in ("repost", "copy", "shared_url", "shared_media") else "related_to"
        edges.append({"id": f"e-{r.id}", "source": r.source_post_id, "target": r.target_post_id,
                      "type": et, "weight": r.similarity or 0.5,
                      "metadata": {"relation": r.relation_type}})
    # spread initial positions on a circle so force layout doesn't stack nodes
    n = max(len(nodes), 1)
    for i, nd in enumerate(nodes):
        ang = 2 * math.pi * i / n
        nd["x"] = round(400 + 280 * math.cos(ang), 1)
        nd["y"] = round(300 + 240 * math.sin(ang), 1)
    return {"nodes": nodes, "edges": edges}

@router.get("/cases/{cid}/sources")
def ui_sources(cid: str, db: Session = Depends(get_db)):
    _case_or_404(db, cid)
    out = []
    for p in db.query(Post).filter(Post.case_id == cid).all():
        dom = _domain(p.source_url)
        out.append({"id": p.id, "platform": p.platform, "type": p.platform,
                    "title": dom or p.platform, "url": p.source_url,
                    "publishedDate": _iso(p.published_at or p.collected_at),
                    "retrievedDate": _iso(p.collected_at)})
    return {"data": out}

@router.get("/cases/{cid}/media")
def ui_media(cid: str, db: Session = Depends(get_db)):
    _case_or_404(db, cid)
    pids = [p.id for p in db.query(Post.id).filter(Post.case_id == cid).all()]
    rows = db.query(Media).filter(Media.post_id.in_(pids)).all() if pids else []
    return {"data": [{
        "id": m.id, "type": m.media_type or "link", "title": m.object_uri.split("/")[-1] or m.media_type,
        "description": "", "url": m.object_uri, "thumbnail": "", "hash": m.sha256,
        "postCount": 1, "firstObserved": "", "exifData": m.metadata_json or {},
    } for m in rows]}

@router.get("/cases/{cid}/coordination")
def ui_coordination(cid: str, db: Session = Depends(get_db)):
    """CoordinationCluster[] matching the UI contract, from real E findings.
    accounts/commonUrls/textSimilarity computed from member posts;
    mediaSimilarity reported 0 (not computed — stated, not invented)."""
    from app.services.osint.spread import sim as _sim
    _case_or_404(db, cid)
    f = db.query(AnalysisFinding).filter(
        AnalysisFinding.case_id == cid, AnalysisFinding.finding_type == "E_coordination"
    ).order_by(AnalysisFinding.id.desc()).first()
    posts = {p.id: p for p in db.query(Post).filter(Post.case_id == cid).all()}
    accs = {a.id: a for a in db.query(Account).all()}

    def members(ids):
        return [posts[i] for i in (ids or []) if i in posts]

    def usernames(m):
        out = []
        for p in m:
            a = accs.get(p.account_id)
            u = f"@{a.username}" if a else p.id[:8]
            if u not in out:
                out.append(u)
        return out

    def shared_urls(m):
        seen: dict[str, int] = {}
        for p in m:
            for tok in (p.text or "").split():
                if tok.startswith("http"):
                    seen[tok[:160]] = seen.get(tok[:160], 0) + 1
        return sorted([u for u, n in seen.items() if n >= 2])

    def avg_sim(m):
        if len(m) < 2:
            return 0.0
        ss = []
        for i in range(len(m)):
            for j in range(i + 1, len(m)):
                try:
                    ss.append(_sim(m[i].clean_text or m[i].text, m[j].clean_text or m[j].text))
                except Exception:
                    pass
        return round(sum(ss) / len(ss), 3) if ss else 0.0

    def proximity(m):
        ts = sorted([str(p.published_at or p.collected_at) for p in m])
        # same 10-min bucket burst => high proximity by construction
        return 0.9 if len(m) >= 2 else 0.0

    clusters = []
    if f:
        p = f.payload_json or {}
        for i, b in enumerate(p.get("temporal_bursts", [])):
            m = members(b.get("posts", []))
            clusters.append({
                "id": f"burst-{i}", "accounts": usernames(m),
                "commonUrls": shared_urls(m),
                "textSimilarity": avg_sim(m), "mediaSimilarity": 0.0,
                "temporalProximity": proximity(m),
                "patternDescription": (f"{b.get('count')} posts in window {b.get('window')} — "
                                       "synchronized posting (indicator only, no intent asserted)."),
                "confidence": 0.6})
        for i, u in enumerate(p.get("url_reuse", [])):
            m = members(u.get("posts", []))
            clusters.append({
                "id": f"url-{i}", "accounts": usernames(m),
                "commonUrls": [u.get("url", "")],
                "textSimilarity": avg_sim(m), "mediaSimilarity": 0.0,
                "temporalProximity": proximity(m),
                "patternDescription": (f"Same link shared by {len(m)} posts — "
                                       "URL reuse (indicator only, no intent asserted)."),
                "confidence": 0.7})
    return {"data": clusters}

# ---------- analysis workflow ----------
@router.get("/cases/{cid}/analysis")
def ui_analysis(cid: str, db: Session = Depends(get_db)):
    _case_or_404(db, cid)
    runs = db.query(AnalysisRun).filter(AnalysisRun.case_id == cid).order_by(AnalysisRun.started_at.desc()).all()
    findings = db.query(AnalysisFinding).filter(AnalysisFinding.case_id == cid).all()
    assess = db.query(Assessment).filter(Assessment.case_id == cid).order_by(Assessment.created_at.desc()).all()
    last = runs[0] if runs else None
    n_posts = db.query(func.count(Post.id)).filter(Post.case_id == cid).scalar() or 0
    plats = sorted({p.platform for p in db.query(Post.platform).filter(Post.case_id == cid).all()})
    by_type = {}
    for f in findings:
        by_type[f.finding_type] = f.payload_json or {}
    a_sec = by_type.get("A_fake_news", {})
    d_sec = by_type.get("D_verification", {})
    e_sec = by_type.get("E_coordination", {})
    c_sec = by_type.get("C_spread", {})
    a_items = a_sec.get("items", []) if isinstance(a_sec, dict) else []
    d_items = d_sec.get("items", []) if isinstance(d_sec, dict) else []
    labels: dict[str, int] = {}
    for v in d_items:
        labels[v.get("label_candidate", "?")] = labels.get(v.get("label_candidate", "?"), 0) + 1
    top_label = assess[0].label if assess else "pending"
    top_conf = assess[0].confidence if assess else 0.0
    reasoning = [
        f"Collected {n_posts} posts across platforms: {', '.join(plats) or 'none'}.",
        f"Query A flagged {len(a_items)} candidate claims for review.",
        "Query D verdicts: " + (", ".join(f"{k}×{v}" for k, v in labels.items()) or "none yet") + ".",
        f"Query C mapped {len(c_sec.get('edges', []))} spread edges; "
        f"Query E found {len(e_sec.get('temporal_bursts', []))} bursts, "
        f"{len(e_sec.get('url_reuse', []))} URL-reuse groups.",
    ]
    limitations = [
        "Social/Telegram collectors are authorized-only stubs; social posts here are analyst seeds.",
        "Verification is evidence-overlap based, not semantic proof — analyst review required.",
    ]
    if not any("contra" in str(v) for v in d_items):
        limitations.append("No contradicting sources retrieved yet for some claims.")
    alt = []
    if e_sec.get("temporal_bursts"):
        alt.append("Synchronized posting suggests possible coordinated amplification (indicator only).")
    if c_sec.get("edges"):
        alt.append("Copy-paste amplification across accounts explains the spread pattern.")
    alt.append("Insufficient evidence — claim remains Unverified until corroborated.")
    return {
        "id": last.id if last else None, "case_id": cid, "type": "network",
        "assessment": top_label, "confidence": top_conf,
        "reasoning": reasoning, "limitations": limitations,
        "alternativeExplanations": alt[:4],
        "results": {
            "runs": [{"id": r.id, "analysis_type": r.analysis_type, "model": r.model,
                      "status": r.status, "started_at": _iso(r.started_at)} for r in runs],
            "findings": [{"id": f.id, "type": f.finding_type, "confidence": f.confidence,
                          "payload": f.payload_json} for f in findings],
            "assessments": [{"id": a.id, "label": a.label, "confidence": a.confidence,
                             "rationale": a.rationale, "override": a.analyst_override} for a in assess],
        },
        "created_at": _iso(last.finished_at) if last else _iso(None),
    }

@router.post("/cases/{cid}/analysis/run")
def ui_analysis_run(cid: str, body: dict | None = None, db: Session = Depends(get_db)):
    _case_or_404(db, cid)
    atype = (body or {}).get("analysis_type", "full")
    res = run_full_analysis(db, cid, atype)
    if "D_verification" in res:
        build_assessment(db, cid, verify_results=res["D_verification"])
    out = ui_analysis(cid, db)  # same shape as GET: reasoning/limitations included
    out["id"] = res.get("run_id")
    return out

def _audit(db: Session, actor: str, action: str, cid: str, extra: dict):
    db.add(AuditEvent(id=str(uuid.uuid4()), actor=actor or "analyst", action=action,
                      entity_type="case", entity_id=cid, before_json={}, after_json=extra))
    db.commit()

@router.get("/cases/{cid}/analysis/notes")
def ui_notes_get(cid: str, db: Session = Depends(get_db)):
    _case_or_404(db, cid)
    ev = db.query(AuditEvent).filter(
        AuditEvent.entity_id == cid, AuditEvent.action == "analysis_notes"
    ).order_by(AuditEvent.timestamp.desc()).first()
    return {"notes": (ev.after_json or {}).get("notes", "") if ev else ""}

@router.put("/cases/{cid}/analysis/notes")
def ui_notes_put(cid: str, body: dict, db: Session = Depends(get_db)):
    _case_or_404(db, cid)
    _audit(db, body.get("actor", "analyst"), "analysis_notes", cid, {"notes": body.get("notes", "")})
    return {"ok": True}

@router.post("/cases/{cid}/analysis/approve")
def ui_approve(cid: str, body: dict | None = None, db: Session = Depends(get_db)):
    _case_or_404(db, cid)
    _audit(db, (body or {}).get("actor", "analyst"), "analysis_approved", cid, {})
    return {"ok": True}

@router.post("/cases/{cid}/analysis/finalize")
def ui_finalize(cid: str, body: dict | None = None, db: Session = Depends(get_db)):
    c = _case_or_404(db, cid)
    c.status = "closed"
    db.commit()
    _audit(db, (body or {}).get("actor", "analyst"), "analysis_finalized", cid, {"status": "closed"})
    return {"ok": True, "status": "closed"}

# ---------- report (item 15 structure; item 2: no truth-probability) ----------
def _d_items(db: Session, cid: str):
    """New-schema D items only (runs predating relevance/evidence-ID fields are debug history)."""
    out = []
    for f in db.query(AnalysisFinding).filter(
            AnalysisFinding.case_id == cid, AnalysisFinding.finding_type == "D_verification").all():
        for v in (f.payload_json or {}).get("items", []):
            if "relevance" in v and "supporting_evidence_ids" in v:
                out.append(v)
    # latest run wins per claim
    latest: dict[str, dict] = {}
    for v in out:
        latest[v.get("claim_id")] = v
    return list(latest.values())


def _norm_url(url: str) -> str:
    """Canonical URL for dedupe: lowercase, no fragment, no tracking params, no trailing slash."""
    from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
    try:
        p = urlsplit((url or "").strip())
        q = [(k, v) for k, v in parse_qsl(p.query)
             if not k.lower().startswith(("utm_", "fbclid", "gclid", "mc_eid"))]
        path = p.path.rstrip("/") or "/"
        return urlunsplit((p.scheme.lower(), p.netloc.lower(), path,
                           urlencode(sorted(q)), "")).rstrip("/")
    except Exception:
        return (url or "").strip().lower().rstrip("/")


def _dedupe_evidence(evidence_rows: list[dict]) -> list[dict]:
    """Group by (normalized_url + sha256). Main view counts each group once (item: dedupe)."""
    groups: dict[tuple[str, str], dict] = {}
    for e in evidence_rows:
        key = (_norm_url(e.get("url", "")), e.get("sha256", ""))
        g = groups.get(key)
        if g is None:
            groups[key] = {"item": e, "duplicate_record_ids": []}
        else:
            g["duplicate_record_ids"].append(e["id"])
    return [{"unique_id": g["item"]["id"], **g["item"],
             "duplicate_record_ids": g["duplicate_record_ids"],
             "duplicate_count": len(g["duplicate_record_ids"])} for g in groups.values()]


def _seed_ids(evidence_rows: list[dict]) -> set[str]:
    return {e["id"] for e in evidence_rows
            if (e.get("url") or "").startswith("http://example.invalid")}


def _domain_of(eid: str, rep: dict) -> str:
    for e in rep.get("evidence", []):
        if e["id"] == eid:
            return _domain(e.get("url", ""))
    return ""


def _src_name(eid: str, rep: dict) -> str:
    """Human source name for an evidence ID (outlet domain, or seed account)."""
    for e in rep.get("evidence", []):
        if e["id"] == eid:
            if (e.get("url") or "").startswith("http://example.invalid"):
                for p in rep.get("posts", []):
                    if p.get("url") == e.get("url"):
                        return f"analyst seed @{p.get('account')} (unverified)"
                return "analyst seed (unverified)"
            return _domain(e.get("url", "")) or "web source"
    return eid[:8] if eid and not eid.startswith("post:") else "unlinked post"

def _latest_assessment(db: Session, cid: str):
    return db.query(Assessment).filter(Assessment.case_id == cid).order_by(
        Assessment.created_at.desc()).first()

def _analyst_override(db: Session, cid: str):
    """Latest assessment carrying a human override (actor parsed from rationale)."""
    import re as _re
    ov = db.query(Assessment).filter(
        Assessment.case_id == cid, Assessment.analyst_override.isnot(None)
    ).order_by(Assessment.created_at.desc()).first()
    if not ov:
        return None
    m = _re.search(r"\[override by ([^\]]+)\]:\s*(.*)", ov.rationale or "", _re.S)
    return {"label": ov.analyst_override,
            "reason": (m.group(2).strip()[:600] if m else (ov.rationale or "")[:600]),
            "actor": (m.group(1).strip() if m else "analyst"),
            "timestamp": ov.created_at.isoformat() if ov.created_at else None}

@router.post("/cases/{cid}/report/generate")
def ui_report_generate(cid: str, body: dict, db: Session = Depends(get_db)):
    rep = build_report(db, cid)
    if not rep:
        raise HTTPException(404, "case not found")
    secs = set((body or {}).get("sections", []))
    want = lambda *names: (not secs) or any(n in secs for n in names)
    items = _d_items(db, cid)
    factual = [v for v in items if not v.get("excluded_from_scoring")]
    rel_factual = [v for v in factual
                   if v.get("relevance") == "relevant"
                   and v.get("claim_type") in ("factual", "numerical", "attribution")]
    latest = _latest_assessment(db, cid)
    override = _analyst_override(db, cid)
    if latest and override and latest.analyst_override:
        reason = latest.rationale or ""
        override = {"label": latest.analyst_override,
                    "reason": reason.split("[override by")[-1].strip(" ]:") if "[override by" in reason else reason,
                    "actor": "analyst",
                    "timestamp": latest.created_at.isoformat() if latest.created_at else None}
    factors = (latest.factors_json or {}) if latest else {}
    core_id = factors.get("core_claim_id")
    roles = factors.get("claim_roles", {})
    uniq = _dedupe_evidence(rep["evidence"])
    uniq_by_id = {u["unique_id"]: u for u in uniq}
    seeds = _seed_ids(rep["evidence"])
    # relevant-only, deduplicated evidence actually linked from relevant claims
    rel_supp = sorted({e for v in rel_factual for e in v.get("supporting_evidence_ids", [])
                       if e in uniq_by_id})
    rel_contra = sorted({e for v in rel_factual for e in v.get("contradicting_evidence_ids", [])
                         if e in uniq_by_id})
    indep_domains = sorted({_domain_of(e, rep) for e in rel_supp
                            if e not in seeds and _domain_of(e, rep)})
    seed_count = len({e for e in rel_supp + rel_contra if e in seeds})
    covered = [v for v in rel_factual if v.get("supporting_evidence_ids")]
    cov_txt = f"{len(covered)}/{len(rel_factual)} ({round(100*len(covered)/len(rel_factual))}%)" if rel_factual else "0/0"
    kws = case_keywords(db, cid)
    notes_ev = db.query(AuditEvent).filter(
        AuditEvent.entity_id == cid, AuditEvent.action == "analysis_notes"
    ).order_by(AuditEvent.timestamp.desc()).first()
    notes = (notes_ev.after_json or {}).get("notes", "") if notes_ev else ""
    findings = {f["type"]: f["payload"] for f in rep.get("findings", [])}
    md: list[str] = []

    if want("executive-summary"):
        md += ["# Executive Summary", "", f"Investigation: {rep['case']['objective'] or rep['case']['title']}", "",
               f"Core Verdict: **{factors.get('core_verdict', 'UNVERIFIED')}**",
               f"Overall Evidence Confidence: **{factors.get('evidence_confidence', 'LOW')}** "
               "(system metric — NOT a probability of truth)",
               f"Independent Sources: **{len(indep_domains)}**",
               f"Analyst Seeds: **{seed_count}** (test data, never independent)",
               f"Relevant Supporting Evidence: **{len(rel_supp)}** (deduplicated)",
               f"Relevant Contradicting Evidence: **{len(rel_contra)}** (deduplicated)",
               f"Relevant Factual Claims With Supporting Evidence: **{cov_txt}** (rhetoric, opinion, "
               "irrelevant, boilerplate and metadata excluded from denominator)", ""]
    if want("objective"):
        md += ["## Objective", "", rep["case"]["objective"] or "—", ""]
    if want("target"):
        md += ["## Target", "",
               f"Keywords: {', '.join(kws) or '—'}",
               f"Platforms: {', '.join(rep['case']['platforms'] or []) or '—'}", ""]
    if want("methodology"):
        md += ["## Methodology", "",
               "1. Collect (RSS / public web / authorized stubs / analyst seeds) → 2. Evidence snapshots (SHA-256) → "
               "3. Three-layer enrichment (keyword prefilter → clean text → Groq JSON extraction) → "
               "4. OSINT queries A–E → 5. Rule aggregation → 6. Analyst review & override. "
               "LLM never invents sources; every conclusion links to evidence IDs.", ""]
    if want("sources"):
        md += ["## Sources (relevant collection only)", ""]
        for p in rep["posts"]:
            sent = f" · sentiment: {p.get('sentiment')} ({p.get('sentiment_score')})" if p.get("sentiment") else ""
            md.append(f"- [{p['platform']}] {p['account']} — {p['url']} ({p['published_at'][:19]}){sent}")
        md.append("")
    if want("account-findings"):
        md += ["## Account Findings", ""]
        counts: dict[str, int] = {}
        for p in rep["posts"]:
            counts[p["account"]] = counts.get(p["account"], 0) + 1
        for acc, n in sorted(counts.items(), key=lambda x: -x[1]):
            a = db.query(Account).filter(Account.username == acc).first()
            md.append(f"- **@{acc}** ({a.platform if a else '?'}) — {n} post(s)"
                      + (f", profile: {a.profile_url}" if a and a.profile_url else ""))
        md.append("")
    if want("claim-analysis"):
        md += ["## Claim Analysis (relevant factual claims only)", ""]
        shown = 0
        for v in rel_factual:
            shown += 1
            role = roles.get(v.get("claim_id"), "supporting")
            header = "⭐ CORE CLAIM" if role == "core" else "Supporting"
            md.append(f"### [{v.get('status')}] {v.get('claim_id', '')[:8]} — {header}")
            md.append(f"{(v.get('claim') or '')[:400]}")
            md.append(f"- Claim type: {v.get('claim_type')} · Role: {role} · "
                      f"Confidence: {v.get('confidence')} (evidence-quality system metric, not probability of truth) "
                      f"(from {v.get('independent_sources', 0)} independent + "
                      f"{v.get('derivative_or_duplicate_sources', 0)} derivative + "
                      f"{v.get('analyst_seed_sources', 0)} seed sources)")
            md.append("- Supporting evidence: " + (", ".join(
                f"{_src_name(e, rep)} (`{e[:8]}`)" for e in v.get("supporting_evidence_ids", [])) or "None"))
            md.append("- Contradicting evidence: " + (", ".join(
                f"{_src_name(e, rep)} (`{e[:8]}`)" for e in v.get("contradicting_evidence_ids", [])) or "None"))
            md.append(f"- Reason: {(v.get('rationale') or '')[:400]}")
            if v.get("missing_details"):
                md.append(f"- Still missing: {'; '.join(v['missing_details'])}")
        skipped = [v for v in items if v.get("excluded_from_scoring")]
        if skipped:
            md.append(f"- *{len(skipped)} non-factual/off-topic/boilerplate items excluded from scoring "
                      f"(rhetoric, opinion, irrelevant, boilerplate) — kept in debug findings.*")
        if not shown:
            md.append("- No relevant factual claims retrieved.")
        md.append("")
    if want("earliest-source"):
        md += ["## Earliest Source — candidate earliest OBSERVED (not proven origin)", ""]
        b = findings.get("B_origin", {})
        for cnd in b.get("candidates", [])[:5]:
            pub = cnd.get("published_at")
            md.append(f"- First observed by system: {(cnd.get('first_observed_at') or '?')[:19]} · "
                      f"Original publication: {(pub[:19] if pub else 'unknown')} · "
                      f"Captured: {(cnd.get('captured_at') or '?')[:19]} · [{cnd.get('platform')}] {cnd.get('url')}")
        md.append("")
    if want("propagation"):
        md += ["## Propagation (observable indicators only — intent not established)", ""]
        c = findings.get("C_spread", {})
        md.append(f"Nodes: {len(c.get('nodes', []))}, typed edges: {len(c.get('edges', []))}.")
        for e in c.get("edges", [])[:15]:
            md.append(f"- {e.get('type')} (similarity {e.get('similarity')}) "
                      f"{str(e.get('from'))[:8]} → {str(e.get('to'))[:8]}")
        if c.get("note"):
            md.append(f"- {c['note']}")
        md.append("- Observed similarity / temporal clustering. Intent not established.")
        md.append("")
    if want("coordination"):
        md += ["## Coordination (observable indicators only — no intent asserted)", ""]
        e = findings.get("E_coordination", {})
        for bl in e.get("temporal_bursts", [])[:10]:
            md.append(f"- Burst: {bl.get('count')} posts in window {bl.get('window')}")
        for u in e.get("url_reuse", [])[:10]:
            md.append(f"- Shared link ×{u.get('count')}: {u.get('url')}")
        if e.get("note"):
            md.append(f"- {e['note']}")
        md.append("")
    if want("media"):
        md += ["## Media", ""]
        pids = [p.id for p in db.query(Post.id).filter(Post.case_id == cid).all()]
        media = db.query(Media).filter(Media.post_id.in_(pids)).all() if pids else []
        md.append("(none captured)" if not media else "")
        for m in media:
            md.append(f"- [{m.media_type}] {m.object_uri} (sha256 `{m.sha256[:16]}…`)")
        md.append("")
    if want("evidence"):
        md += ["## Evidence Locker (deduplicated main view)", ""]
        for u in uniq:
            e = u  # deduped row: unique evidence fields + duplicate_record_ids
            seed = (e["url"] or "").startswith("http://example.invalid")
            md.append(f"### {e['id'][:8]} ({'ANALYST SEED — unverified test data' if seed else 'collected evidence'})")
            md.append(f"- Source: {_src_name(e['id'], rep)}")
            md.append(f"- Original URL (complete, stored untruncated): {e['url']}")
            md.append(f"- Captured at: {e['captured_at'][:19]} · Snapshot type: {e['type']} "
                      f"(snapshot integrity fingerprint below — not a screenshot)")
            md.append(f"- SHA-256: `{e['sha256']}`")
            if u["duplicate_record_ids"]:
                md.append(f"- Duplicate records (same URL+hash, counted once): "
                          + ", ".join(f"`{d[:8]}`" for d in u["duplicate_record_ids"]))
            md.append(f"- Independent: {'false (seed)' if seed else 'true'} · "
                      f"Verification: {'unverified' if seed else 'hash-stored'}")
            md.append(f"- View snapshot: `/evidence/{e['id']}/view` · Verify hash: `/evidence/{e['id']}/verify` · Open original: {e['url'][:90]}")
        md.append("")
    if want("assessment"):
        md += ["## Assessment (automated — distinct from analyst override below)", ""]
        if latest:
            lat = {"label": latest.label, "confidence": latest.confidence,
                   "rationale": latest.rationale}
            md.append(f"- **{lat['label']}** ({lat['confidence']})")
            md.append(f"  - {(lat['rationale'] or '')[:500]}")
        else:
            md.append("- No automated assessment yet.")
        if len(rep["assessments"]) > 1:
            md.append(f"- *({len(rep['assessments']) - 1} older automated runs kept in debug history.)*")
        md.append("")
    if want("confidence"):
        md += ["## Confidence", "",
               f"Evidence confidence: **{(latest.factors_json or {}).get('evidence_confidence', 'LOW') if latest else 'LOW'}** "
               "(HIGH = core verified by ≥2 independent sources, no contradictions).",
               "Confidence values are system metrics from evidence quality — not probabilities of truth.", ""]
    if want("limitations"):
        md += ["## Limitations", "",
               "- Analyst seeds (example.invalid) are test data: never counted as independent sources.",
               "- Unavailable social content: Telegram/social APIs are authorized-only stubs.",
               "- Missing original timestamps: several sources lack published_at; collection time is not publication time.",
               "- Evidence-overlap verification, not semantic proof; analyst review required.",
               "- Snapshots are captures (HTML/text), not screenshots; bot-blocked pages may fail (logged, never silent).",
               "- Source-independence is domain-based; same-wire copies across domains can still slip through.", ""]
    if want("notes"):
        md += ["## Analyst Notes", "", notes or "—", ""]
    if want("appendix"):
        md += ["## Appendix", "",
               f"Case ID `{rep['case']['id']}` · Status {rep['case']['status']} · "
               f"Evidence refs: {', '.join(e['id'][:8] for e in rep['evidence'][:20])}",
               f"*{rep['traceability']}*", ""]
    md += ["## Analyst Assessment (human — separate from automation above)", ""]
    if override and override.get("label"):
        md += [f"- Override: **{override['label']}**",
               f"- Reason: {override.get('reason') or '—'}",
               f"- Analyst: {override.get('actor') or 'analyst'}",
               f"- Timestamp: {override.get('timestamp') or '—'}"]
    else:
        md += ["- No analyst override recorded — automated assessment stands pending review."]
    return {"content": "\n".join(md), "case_id": cid,
            "core_verdict": (latest.factors_json or {}).get("core_verdict", "UNVERIFIED") if latest else "UNVERIFIED",
            "evidence_confidence": (latest.factors_json or {}).get("evidence_confidence", "LOW") if latest else "LOW",
            "claim_coverage": (latest.factors_json or {}).get("claim_coverage", 0) if latest else 0,
            "supporting_evidence": (latest.factors_json or {}).get("supporting_evidence", 0) if latest else 0,
            "contradicting_evidence": (latest.factors_json or {}).get("contradicting_evidence", 0) if latest else 0,
            "truth_score": None,
            "verdict": (override or {}).get("label") or (latest.label if latest else "Unverified")}

@router.get("/cases/{cid}/report/export")
def ui_report_export(cid: str, format: str = "json", db: Session = Depends(get_db)):
    from fastapi.responses import PlainTextResponse
    import json as _json
    rep = build_report(db, cid)
    if not rep:
        raise HTTPException(404, "case not found")
    if format == "csv":
        lines = ["id,text,topic,status"]
        for ch in rep["claims"]:
            t = (ch["text"] or "").replace('"', '""')
            lines.append(f"{ch['id']},\"{t[:400]}\",{ch['topic']},{ch['status']}")
        return PlainTextResponse("\n".join(lines), media_type="text/csv",
                                 headers={"Content-Disposition": f"attachment; filename=report-{cid[:8]}.csv"})
    if format in ("pdf", "html"):
        from app.services.reporting.service import report_to_html
        return HTMLResponse(report_to_html(rep),
                            headers={"Content-Disposition": f"attachment; filename=report-{cid[:8]}.html"})
    return rep
