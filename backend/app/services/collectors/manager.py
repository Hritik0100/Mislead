"""Collection orchestrator: normalize -> evidence -> dedup -> enrich. TRD Sec 3."""
import uuid, hashlib
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.db import Account, Post, Evidence, CaseKeyword, CollectionJob
from app.services.evidence.service import store_text_evidence, store_binary_evidence
from app.services.collectors.auth_browser import redact_for_log
from app.services.enrichment.prefilter import content_hash
from app.services.enrichment.pipeline import run_enrichment_for_post
from app.services.collectors import rss as rss_c, public_web as web_c, telegram as tg_c, manual as man_c

def _get_account(db: Session, platform: str, username: str, display="", profile=""):
    a = db.query(Account).filter(Account.platform == platform, Account.username == username).first()
    if not a:
        a = Account(id=str(uuid.uuid4()), platform=platform, username=username,
                    display_name=display, profile_url=profile)
        db.add(a)
        db.commit()
    return a

def ingest_records(db: Session, case_id: str, records: list, keywords: list):
    from app.models.db import PostRelation as _PR
    stats = {"received": len(records), "stored": 0, "deduped": 0, "reposts": 0, "claims": 0}
    for rec in records:
        h = content_hash(rec.text or "")
        canon = db.query(Post).filter(Post.case_id == case_id, Post.raw_hash == h).first()
        if canon is not None:
            # Exact-copy REPOST: no duplicate analysis, but the reposter + edge are recorded.
            acc = _get_account(db, rec.platform, rec.account_username, rec.account_display, rec.profile_url)
            rp = Post(id=str(uuid.uuid4()), case_id=case_id, platform_post_id=rec.source_url[:200],
                      account_id=acc.id, source_url=rec.source_url, text=(rec.text or "")[:20000],
                      clean_text=(rec.text or "")[:20000],
                      published_at=rec.published_at if hasattr(rec.published_at, "year") else None,
                      collected_at=datetime.now(timezone.utc), raw_hash=h,
                      engagement={"repost_of": canon.id, "repost": True}, platform=rec.platform)
            db.add(rp)
            canon_ev = db.query(Evidence).filter(Evidence.source_url == canon.source_url).first()
            db.add(_PR(id=str(uuid.uuid4()), case_id=case_id,
                       source_post_id=canon.id, target_post_id=rp.id,
                       relation_type="repost", similarity=1.0,
                       evidence_ids=[canon_ev.id] if canon_ev else []))
            db.commit()
            stats["deduped"] += 1
            stats["reposts"] += 1
            continue
        acc = _get_account(db, rec.platform, rec.account_username, rec.account_display, rec.profile_url)
        # evidence snapshot (provenance decides the type; secrets never stored)
        method = (getattr(rec, "provenance", {}) or {}).get("collection_method", "public_web")
        ev_type = "authenticated_snapshot" if method == "authenticated_browser" else "html_snapshot"
        ev = store_text_evidence(case_id, rec.source_url, (rec.raw_html or rec.text or "")[:800000],
                                 evidence_type=ev_type)
        ev_row = Evidence(id=ev["id"], case_id=case_id, evidence_type=ev["evidence_type"],
                          object_uri=ev["object_uri"], source_url=rec.source_url,
                          sha256=ev["sha256"], captured_at=ev["captured_at"])
        db.add(ev_row)
        if getattr(rec, "screenshot_bytes", None):
            shot = store_binary_evidence(case_id, rec.source_url, rec.screenshot_bytes,
                                         "screenshot.png", evidence_type="screenshot")
            db.add(Evidence(id=shot["id"], case_id=case_id, evidence_type=shot["evidence_type"],
                            object_uri=shot["object_uri"], source_url=rec.source_url,
                            sha256=shot["sha256"], captured_at=shot["captured_at"]))
        if getattr(rec, "image_bytes", None):
            # The post image itself: the artifact OCR read, stored so the reading
            # is verifiable rather than taken on trust.
            img = store_binary_evidence(case_id, rec.source_url, rec.image_bytes,
                                        "post-image.jpg", evidence_type="post_image")
            db.add(Evidence(id=img["id"], case_id=case_id, evidence_type=img["evidence_type"],
                            object_uri=img["object_uri"], source_url=rec.source_url,
                            sha256=img["sha256"], captured_at=img["captured_at"]))
        post = Post(id=str(uuid.uuid4()), case_id=case_id, platform_post_id=rec.source_url[:200],
                    account_id=acc.id, source_url=rec.source_url, text=(rec.text or "")[:20000],
                    clean_text=(rec.text or "")[:20000], published_at=rec.published_at if hasattr(rec.published_at, "year") else None,
                    collected_at=datetime.now(timezone.utc), raw_hash=h,
                    engagement=rec.engagement or {}, platform=rec.platform)
        db.add(post)
        db.commit()
        stats["stored"] += 1
        r = run_enrichment_for_post(db, post, keywords)
        stats["claims"] += r.get("claims", 0)
    return stats

def run_collection(db: Session, case_id: str, sources: list, max_items=50):
    from app.models.db import Case
    case = db.query(Case).filter(Case.id == case_id).first()
    # Objectives are workflow steps, not claim terms. Feeding them to the
    # prefilter made every post look off-topic (or every claim look relevant)
    # depending on the step names.
    kws = [k.normalized_keyword for k in db.query(CaseKeyword)
           .filter(CaseKeyword.case_id == case_id,
                   CaseKeyword.type != "objective").all()]
    job = CollectionJob(id=str(uuid.uuid4()), case_id=case_id, status="running", source="mixed")
    db.add(job)
    db.commit()
    all_recs = []
    errors = []
    try:
        for s in sources:
            t = (s.get("type") or "").lower()
            try:
                if t == "rss":
                    all_recs += rss_c.collect_rss(s.get("url", ""), max_items)
                elif t == "web":
                    recs, err = web_c.collect_web(s.get("url", ""))
                    all_recs += recs
                    if err:
                        errors.append(err)
                elif t == "telegram":
                    # REAL MTProto collector (Telethon, isolated subprocess).
                    # Only the investigator's own authorized view; a private
                    # entity is reported ACCESS_DENIED, never worked around.
                    res = tg_c.run_telegram_task(dict(s))
                    all_recs += res.get("records", [])
                    for e in res.get("errors", []):
                        errors.append(f"telegram [{res.get('status')}]: {e}")
                    if res.get("status") not in ("SUCCESS", "PARTIAL", "EMPTY"):
                        errors.append(f"telegram status={res.get('status')} "
                                      f"reason={res.get('reason_code', '')}")
                elif t in ("chirpwire", "matrix", "element", "facebook", "instagram", "x", "youtube", "social"):
                    recs, err = tg_c.collect_platform_stub(t, s.get("channel") or s.get("handle") or s.get("url", ""), s.get("note", ""))
                    for r in recs:
                        r.provenance = {"collection_method": "analyst_provided",
                                        "access": "stub_pending_manual_evidence", "independent": False}
                    all_recs += recs
                elif t == "manual":
                    recs, err = man_c.collect_manual(s.get("platform", "manual"), s.get("username", "analyst"), s.get("text", ""), s.get("url", ""))
                    for r in recs:
                        r.provenance = {"collection_method": "analyst_provided",
                                        "access": "investigator_submitted", "independent": False}
                    all_recs += recs
                    if err:
                        errors.append(err)
                elif t in ("auth_browser", "authenticated_browser"):
                    # OPTIONAL adapter: disabled without credentials; never logs secrets.
                    # Playwright runs in an isolated subprocess (asyncio-loop safe).
                    from app.services.collectors import auth_browser as _ab
                    if (s.get("driver") or "").lower() == "playwright":
                        res = _ab.run_playwright_task(dict(s))
                    else:
                        res = _ab.AuthenticatedBrowserCollector().collect(dict(s), kws)
                    all_recs += res.get("records", [])
                    for e in res.get("errors", []):
                        errors.append(f"auth_browser [{res.get('status')}]: {e}")
                    if res.get("status") not in ("SUCCESS", "PARTIAL", "EMPTY"):
                        errors.append(f"auth_browser status={res.get('status')} "
                                      f"reason={res.get('reason_code', '')}")
                else:
                    errors.append(f"unknown source type: {t}")
            except Exception as e:
                errors.append(f"{t}: {redact_for_log(str(e))}")
        stats = ingest_records(db, case_id, all_recs[:max_items * 5], kws)
        stats["errors"] = errors
        job.status = "succeeded"
        job.stats_json = stats
    except Exception as e:
        job.status = "failed"
        job.error = str(e)
        stats = {"error": str(e)}
    job.finished_at = datetime.now(timezone.utc)
    db.commit()
    return {"job_id": job.id, "status": job.status, **stats}
