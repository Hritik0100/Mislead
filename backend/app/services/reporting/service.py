"""Reporting service: JSON + HTML/PDF-ready. PRD 7.6, TRD Sec 14."""
import html
import re
from sqlalchemy.orm import Session
from app.models.db import Case, Post, Claim, Evidence, Assessment, Account, AnalysisFinding
from app.services.osint.relevance import is_boilerplate as _is_boilerplate

# --- Boilerplate filter: keeps nav-chrome / language-list / cookie-text out of reports ---
BOILERPLATE_PATTERNS = [
    r"^from wikipedia", r"free encyclopedia$", r"unlimited access", r"minimal ad experience",
    r"expertly crafted", r"news brief in summary", r"^skip to", r"^sign in", r"^log in$",
    r"^subscribe", r"^search$", r"cookie", r"all rights reserved", r"^home$", r"^menu$",
    r"edition$", r"download (the|our) app", r"follow us", r"share via",
]
_BOILER_RE = re.compile("|".join(BOILERPLATE_PATTERNS), re.IGNORECASE)

def is_boilerplate(text: str) -> bool:
    t = (text or "").strip()
    if len(t) < 30:
        return True
    if _BOILER_RE.search(t):
        return True
    words = t.split()
    # language-switcher rows: very few unique words, slashes, parens, non-latin only
    if len(words) <= 6 and ("/" in t or "(" in t):
        return True
    if len(words) <= 4:
        return True
    return False

LABEL_COLORS = {
    "True": "#14532d", "False": "#7f1d1d", "Misleading": "#713f12",
    "Context Missing": "#713f12", "Unverified": "#3f3f46",
}

def build_report(db: Session, case_id: str):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        return None
    posts = db.query(Post).filter(Post.case_id == case_id).all()
    claims = db.query(Claim).filter(Claim.case_id == case_id).all()
    evs = db.query(Evidence).filter(Evidence.case_id == case_id).all()
    assessments = sorted(
        db.query(Assessment).filter(Assessment.case_id == case_id).all(),
        key=lambda a: str(a.created_at), reverse=True)  # latest first; older runs = debug history
    findings = db.query(AnalysisFinding).filter(AnalysisFinding.case_id == case_id).all()
    accs = {a.id: a for a in db.query(Account).all()}

    def post_row(p):
        a = accs.get(p.account_id)
        eng = p.engagement or {}
        return {"post_id": p.id, "account": a.username if a else "", "platform": p.platform,
                "url": p.source_url, "published_at": str(p.published_at or p.collected_at),
                "engagement": eng, "sentiment": eng.get("sentiment"),
                "sentiment_score": eng.get("sentiment_score", 0.0),
                "text_prefix": (p.clean_text or p.text or "")[:500]}

    clean_claims = [c for c in claims if not is_boilerplate(c.text)]
    return {
        "case": {"id": case.id, "title": case.title, "objective": case.objective,
                 "platforms": case.platforms, "status": case.status, "created_at": str(case.created_at)},
        "counts": {"posts": len(posts), "claims": len(claims),
                   "claims_shown": len(clean_claims),
                   "claims_hidden_boilerplate": len(claims) - len(clean_claims),
                   "evidence": len(evs), "assessments": len(assessments)},
        "claims": [{"id": c.id, "text": c.text, "topic": c.topic, "status": c.status} for c in clean_claims],
        "posts": [post_row(p) for p in posts],
        "evidence": [{"id": e.id, "type": e.evidence_type, "uri": e.object_uri, "url": e.source_url,
                      "sha256": e.sha256, "captured_at": str(e.captured_at)} for e in evs],
        "assessments": [{"id": a.id, "label": a.label, "confidence": a.confidence,
                         "factors": a.factors_json, "evidence_refs": a.evidence_refs,
                         "override": a.analyst_override, "rationale": a.rationale} for a in assessments],
        "findings": [{"id": f.id, "type": f.finding_type, "confidence": f.confidence,
                      "payload": f.payload_json} for f in findings],
        "traceability": "Every conclusion links to evidence IDs + source URLs. Confidence != probability of truth.",
    }

def _esc(s) -> str:
    return html.escape(str(s or ""))

def _link(url: str, label: str = "") -> str:
    u = (url or "").strip()
    if not u:
        return "<span class='meta'>—</span>"
    if not u.startswith("http"):
        return f"<span class='seed'>{_esc(label or u)} · demo seed, no live link</span>"
    if u.startswith("http://example.invalid"):
        return (f"<span class='seed'>demo seed post (test data, link never resolves by design — "
                f"RFC&#8209;2606 .invalid)</span><br><code>{_esc(u)}</code>")
    return f'<a href="{_esc(u)}">{_esc(label or (u[:70] + ("…" if len(u) > 70 else "")))}</a>'

def report_to_html(rep: dict) -> str:
    c = rep["case"]
    n = rep["counts"]
    # --- verdict card: LATEST automated assessment only (older runs = debug history) ---
    acards = ""
    _all_a = rep.get("assessments", [])
    for a in _all_a[:1]:
        color = LABEL_COLORS.get(a["label"], "#3f3f46")
        pct = int((a["confidence"] or 0) * 100)
        factors = " · ".join(f"{_esc(k)}: {_esc(v)}" for k, v in (a["factors"] or {}).items() if k in (
            "core_verdict", "evidence_confidence", "claim_coverage",
            "supporting_evidence", "contradicting_evidence", "independent_sources_total"))
        ovr = f"<div><b>Analyst override:</b> {_esc(a['override'])}</div>" if a.get("override") else ""
        refs = ", ".join(f"<code>{_esc(r[:8])}</code>" for r in (a["evidence_refs"] or [])[:12])
        acards += f"""<div class="verdict">
          <span class="pill" style="background:{color}">{_esc(a['label'])}</span>
          <div class="conf"><div style="width:{pct}%"></div></div><b>{pct}%</b>
          <span class="meta">(evidence-quality system metric, not probability of truth)</span>
          <p>{_esc(a['rationale'])}</p>{ovr}
          <div class="meta">Factors: {factors}</div>
          <div class="meta">Evidence refs: {refs}</div></div>"""
    if len(_all_a) > 1:
        acards += f"<p class='meta'>{len(_all_a) - 1} older automated run(s) kept in debug history.</p>"

    # --- claims (boilerplate already filtered) ---
    crows = "".join(
        f"<tr><td><code>{_esc(x['id'][:8])}</code></td><td>{_esc(x['text'])}</td>"
        f"<td>{_esc(x['topic'])}</td><td>{_esc(x['status'])}</td></tr>"
        for x in rep.get("claims", []))
    hidden = n.get("claims_hidden_boilerplate", 0)
    hnote = f"<p class='meta'>{hidden} boilerplate rows (nav chrome, language lists, cookie text) auto-hidden.</p>" if hidden else ""

    # --- posts with links ---
    prows = "".join(
        f"<tr><td>{_esc(p['account'])}</td><td>{_esc(p['platform'])}</td>"
        f"<td>{_link(p['url'])}</td><td>{_esc(p['published_at'][:19])}</td>"
        f"<td>{_esc(p['text_prefix'][:300])}</td></tr>"
        for p in rep.get("posts", []))

    # --- evidence with links + hashes ---
    erows = "".join(
        f"<tr><td><code>{_esc(e['id'][:8])}</code></td><td>{_esc(e['type'])}</td>"
        f"<td>{_link(e['url'])}</td><td><code>{_esc((e['sha256'] or '')[:16])}…</code></td>"
        f"<td>{_esc(e['captured_at'][:19])}</td></tr>"
        for e in rep.get("evidence", []))

    # --- A–E findings summary ---
    fsec = ""
    for f in rep.get("findings", []):
        p = f.get("payload") or {}
        if f["type"] == "A_fake_news":
            items = [i for i in p.get("items", []) if not is_boilerplate(str(i.get("claim", "")))]
            lis = "".join(f"<li>suspicion <b>{_esc(i.get('suspicion'))}</b> {', '.join(map(_esc, i.get('signals', [])))} — {_esc(str(i.get('claim', ''))[:140])}</li>" for i in items[:8])
            fsec += f"<h3>A · Fake-news scan ({len(items)} claims)</h3><ul>{lis}</ul>"
        elif f["type"] == "B_origin":
            cs = p.get("candidates", [])[:5]
            lis = "".join(f"<li>{_esc((x.get('published_at') or 'unknown')[:19])} [{_esc(x.get('platform'))}] {_link(x.get('url'), (x.get('url', '')[:60]))}</li>" for x in cs)
            fsec += f"<h3>B · Earliest-observed origin (candidate, not proven)</h3><ul>{lis}</ul>"
        elif f["type"] == "C_spread":
            fsec += f"<h3>C · Spread graph</h3><p>{len(p.get('nodes', []))} accounts/posts, {len(p.get('edges', []))} typed copy/shared-URL edges.</p>"
        elif f["type"] == "D_verification":
            items = [v for v in p.get("items", []) if not is_boilerplate(str(v.get("claim", "")))]
            lis = "".join(f"<li><b>{_esc(v.get('label_candidate'))}</b> ({_esc(v.get('confidence'))}) — {_esc(str(v.get('claim', ''))[:140])}</li>" for v in items)
            fsec += f"<h3>D · Claim verification</h3><ul>{lis}</ul>"
        elif f["type"] == "E_coordination":
            fsec += (f"<h3>E · Coordination indicators (observable only)</h3>"
                     f"<p>Temporal bursts: {len(p.get('temporal_bursts', []))} · URL reuse groups: {len(p.get('url_reuse', []))}. No intent asserted.</p>")

    plats = ", ".join(map(_esc, c.get("platforms", [])))
    return f"""<html><head><title>OSINT Report - {_esc(c['title'])}</title>
<style>
body{{font-family:system-ui,sans-serif;margin:0;background:#fff;color:#111}}
.wrap{{max-width:1100px;margin:0 auto;padding:28px 22px 60px}}
table{{border-collapse:collapse;width:100%;font-size:14px;margin:10px 0}}
td,th{{border:1px solid #d4d4d8;padding:8px;vertical-align:top}}th{{background:#f4f4f5;text-align:left}}
code{{background:#f4f4f5;padding:1px 6px;border-radius:6px;font-size:12px}}
a{{color:#1d4ed8}}.meta{{color:#52525b;font-size:12px}}
.verdict{{border:1px solid #e4e4e7;border-left:6px solid #111;border-radius:10px;padding:16px;margin:12px 0}}
.verdict p{{white-space:pre-wrap;line-height:1.55}}
.pill{{display:inline-block;color:#fff;padding:3px 14px;border-radius:20px;font-weight:700}}
.seed{{display:inline-block;background:#fef3c7;border:1px solid #f59e0b;border-radius:6px;padding:2px 8px;font-size:12px;color:#713f12}}
.conf{{display:inline-block;width:220px;height:12px;background:#e4e4e7;border-radius:6px;overflow:hidden;vertical-align:middle;margin:0 8px}}
.conf>div{{height:100%;background:#111}}
h1{{font-size:26px}}h2{{font-size:20px;margin-top:30px}}
@media print{{.wrap{{max-width:100%}}}}
</style></head><body><div class="wrap">
<h1>OSINT Report: {_esc(c['title'])}</h1>
<p>Objective: {_esc(c['objective'])}<br>
<span class="meta">Platforms: {plats} · Posts: {n['posts']} · Claims: {n['claims']} (shown {n.get('claims_shown', n['claims'])}) · Evidence: {n['evidence']} · Status: {_esc(c['status'])}</span></p>
<h2>Assessment</h2>{acards or '<p>No assessment yet — run analysis first.</p>'}
<h2>Key OSINT findings (A–E)</h2>{fsec or '<p>No findings yet.</p>'}
<h2>Claims (evidence-linked)</h2>{hnote}
<table><tr><th>ID</th><th>Text</th><th>Topic</th><th>Status</th></tr>{crows}</table>
<h2>Accounts / Posts</h2>
<table><tr><th>Account</th><th>Platform</th><th>Post URL</th><th>Published</th><th>Text</th></tr>{prows}</table>
<h2>Evidence locker</h2>
<table><tr><th>ID</th><th>Type</th><th>Source URL</th><th>SHA-256</th><th>Captured</th></tr>{erows}</table>
<p><i>{_esc(rep['traceability'])}</i></p></div></body></html>"""
