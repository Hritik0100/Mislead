"""Subprocess worker: runs a full Playwright collection in isolation.

Why a subprocess: Playwright's sync API cannot run inside threads that already
run an asyncio loop (e.g. ASGI worker threads). A dedicated process guarantees
a clean interpreter with no running loop. Task JSON on stdin, result JSON on stdout.
One JSON object per line on stdout; the LAST line is the result.
"""
import base64
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))


def main():
    task = json.loads(sys.stdin.read() or "{}")
    from app.services.collectors.auth_browser import (
        PlaywrightDriver, AuthConfig, BrowserSession, _playwright_cookie_login,
        _playwright_form_login, _manual_login_handoff, _logged_in_probe,
        _parse_dt, classify_page, classify_no_results, SUCCESS,
        load_session_marker, default_session_dir, MFA_REQUIRED, CAPTCHA_REQUIRED,
    )
    from app.services.collectors.base import SourceRecord
    import time
    from datetime import datetime, timezone

    started = time.time()
    platform = task.get("platform", "web")
    cfg = AuthConfig.from_env(task.get("env_prefix", platform),
                              platform=platform, login_url=task.get("login_url", ""))
    if task.get("session"):
        cfg.session_name = task["session"]
    sdir = task.get("session_dir") or default_session_dir()
    out = {"status": "ERROR", "reason_code": "init", "records": [], "errors": [],
           "session_reused": False}
    driver = None
    try:
        driver = PlaywrightDriver(session=cfg.session_name,
                                  headless=bool(task.get("headless", False)),
                                  session_dir=sdir, platform=platform)
        mode = task.get("mode", "collect_urls")

        # Verify a previously saved storage_state really authenticates. Runs
        # headless and uses no credentials: it can only pass on a live session.
        if mode == "session_probe":
            _st = os.path.join(sdir, f"pw-{cfg.session_name}.json")
            if not os.path.isfile(_st):
                out.update(status="ERROR", reason_code="no_saved_state")
                print(json.dumps(out), flush=True)
                return
            try:
                driver.launch(storage_state=_st)
                vurl = task.get("verify_url") or ""
                if vurl:
                    driver.open(vurl)
                    import time as _t
                    _t.sleep(7)
                ok = _logged_in_probe(driver, platform)
                out.update(status=SUCCESS if ok else "AUTHENTICATION_REQUIRED",
                           reason_code="session_valid" if ok else "session_not_authenticated")
                print(json.dumps(out), flush=True)
                return
            except Exception as e:
                out.update(status="ERROR", reason_code=type(e).__name__)
                print(json.dumps(out), flush=True)
                return

        # Manual handoff: the investigator finishes the login in the visible
        # window (captcha / emailed code / MFA). Nothing is automated or guessed.
        if mode == "manual_login" or task.get("manual_login"):
            st = _manual_login_handoff(driver, cfg, sdir, task)
            if st != SUCCESS:
                out.update(status=st, reason_code="manual_login_not_completed",
                           errors=["AUTHENTICATION_ACTION_REQUIRED"]
                           if st in (MFA_REQUIRED, CAPTCHA_REQUIRED) else [st])
                print(json.dumps(out), flush=True)
                return
            out.update(status=SUCCESS, reason_code="manual_login_ok",
                       session_reused=False, records=[], errors=[])
            print(json.dumps(out), flush=True)
            return

        # Prefer the cookie/storage-state path, but only when it can actually work.
        # A leftover session marker with no state file and no cookies used to
        # dead-end at "no_cookies_configured" instead of trying a fresh login.
        _state = os.path.join(sdir, f"pw-{cfg.session_name}.json")
        _can_cookie = bool(task.get("cookies_env")) or os.path.isfile(_state)
        if _can_cookie or load_session_marker(sdir, cfg.session_name):
            login = _playwright_cookie_login(driver, cfg, task, sdir)
            if login["status"] == "AUTHENTICATION_REQUIRED" and \
                    login.get("reason") == "no_cookies_configured" and cfg.is_configured:
                login = BrowserSession(driver, cfg, sdir).login()
            # A captcha/2FA wall is escalated to the manual handoff rather than
            # being reported as a generic credential failure.
            if login["status"] in (MFA_REQUIRED, CAPTCHA_REQUIRED) and not task.get("headless"):
                out.update(status=login["status"],
                           reason_code=login.get("reason", "challenge"),
                           errors=["AUTHENTICATION_ACTION_REQUIRED"],
                           needs_manual_login=True)
                print(json.dumps(out), flush=True)
                return
        else:
            session = BrowserSession(driver, cfg, sdir)
            login = session.login()
            if login["status"] in (MFA_REQUIRED, CAPTCHA_REQUIRED) and not task.get("headless"):
                out.update(status=login["status"],
                           reason_code=login.get("reason", "challenge"),
                           errors=["AUTHENTICATION_ACTION_REQUIRED"],
                           needs_manual_login=True)
                print(json.dumps(out), flush=True)
                return
        if login["status"] != SUCCESS:
            out.update(status=login["status"], reason_code=login.get("reason", ""))
            if login["status"] in (MFA_REQUIRED, CAPTCHA_REQUIRED):
                out["errors"] = ["AUTHENTICATION_ACTION_REQUIRED"]
            else:
                out["errors"] = [login.get("reason", "login failed")]
            print(json.dumps(out), flush=True)
            return
        out["session_reused"] = bool(login.get("reason") == "session_reused")
        if mode == "login_test":
            out.update(status=SUCCESS, reason_code="login_ok")
            print(json.dumps(out), flush=True)
            return
        social = platform in ("x", "facebook", "instagram") and \
            isinstance(driver, PlaywrightDriver)

        def _maybe_ocr(p, cap, rec):
            """Read text baked into a post image when the DOM text is thin.

            Facebook/Instagram posts that are posters, memes or screenshots carry
            the claim only as pixels. OCR runs locally (macOS Vision); the image
            is stored as evidence so the analyst can see exactly what was read.
            """
            from app.services.ocr import service as ocr_svc
            if not p.get("media"):
                return
            try:
                data = driver.fetch_bytes(p["media"][0])
            except Exception:
                data = None
            if not data:
                return
            res = ocr_svc.ocr_image(data)
            prov = rec["provenance"]
            prov["ocr"] = {
                "attempted": True,
                "available": res.get("available"),
                "engine": res.get("engine"),
                "confidence": res.get("confidence"),
                "line_count": res.get("line_count"),
                "error": res.get("error"),
            }
            ocr_text = res.get("text") or ""
            if not ocr_text:
                return
            prov["ocr"]["text"] = ocr_text[:4000]
            if ocr_svc.should_promote_ocr(p.get("text"), ocr_text, res.get("confidence")):
                prov["text_source"] = "ocr"
                prov["dom_text"] = (p.get("text") or "")[:500]
                rec["text"] = ocr_text[:20000]
            else:
                # Keep the author's words as the post text but make the image
                # text searchable/attestable alongside it.
                prov["text_source"] = "dom"
                prov["ocr_promoted"] = False
                rec["text"] = ((p.get("text") or "") + "\n\n[image text]\n" +
                               ocr_text)[:20000]
            # The image itself is forensic evidence, not just a source for OCR.
            try:
                rec["image_b64"] = base64.b64encode(data).decode()
            except Exception:
                pass

        def _rec(p, capture, scope, query="", surl=""):
            """One record per real post. Content from the platform extractor only."""
            eng = dict(p.get("engagement") or {})
            handle = p.get("handle") or ""
            plat = p.get("platform") or platform
            return {
                "platform": plat,
                "account_username": handle or f"{plat}_account",
                "account_display": p.get("display_name") or "",
                "profile_url": p.get("profile_url") or (
                    f"https://x.com/{handle}" if plat == "x" and handle else ""),
                "source_url": p.get("permalink") or capture["url"],
                "text": (p.get("text") or "")[:20000],
                "title": capture["title"] or "",
                "published_at": p.get("published_at") or "",
                "engagement": eng,
                "media_refs": p.get("media") or [],
                "raw_html": capture["html"] or "",
                "screenshot_b64": base64.b64encode(capture["screenshot"]).decode()
                if capture.get("screenshot") else "",
                "provenance": {
                    "collection_method": "authenticated_browser",
                    "access": "investigator_owned_account",
                    "independent": True,
                    "extraction": "platform_dom_article",
                    "evidence_scope": scope,
                    "metrics_observed": sorted((p.get("engagement") or {}).keys()),
                    "caption_source": p.get("caption_source") or "",
                    "dismissed_overlays": capture.get("dismissed_overlays") or [],
                    **({"search_query": query, "search_url": surl,
                        "search_time": datetime.now(timezone.utc).isoformat()}
                       if query else {}),
                },
            }

        records, errors, partial = [], [], False
        if social and mode == "search":
            surl = task.get("search_url", "")
            if not surl:
                out.update(reason_code="missing_search_url",
                           errors=["search mode needs search_url"])
                print(json.dumps(out), flush=True)
                return
            cap = driver.extract_social(surl, platform, listing=True)
            st = classify_page(cap["url"], cap["title"], cap["text"], 200)
            if st != SUCCESS:
                out.update(status=st, reason_code="search_page_challenge",
                           errors=[f"search halted: {st}"])
                print(json.dumps(out), flush=True)
                return
            if not cap["posts"]:
                empty = classify_no_results(cap["url"], cap["title"], cap["text"])
                if empty:
                    out.update(status="EMPTY", reason_code="no_results_for_query",
                               errors=[f"{platform} returned no results (page says: '{empty}'). "
                                       "The search terms are too specific, or the platform "
                                       "flagged them as sensitive. Try broader keywords."])
                else:
                    out.update(status="ERROR", reason_code="no_posts_in_dom",
                               errors=["no post containers found on the search page"]
                               + ([f"extractor error -> {cap['eval_error']}"]
                                  if cap.get("eval_error") else []))
                print(json.dumps(out), flush=True)
                return
            q = task.get("search_query", "")
            for p in cap["posts"][:task.get("max_items", 10)]:
                rec = _rec(p, cap, "listing_page_capture", q, surl)
                if task.get("ocr", True):
                    _maybe_ocr(p, cap, rec)
                records.append(rec)
        elif social:
            for u in task.get("urls", [])[:task.get("max_items", 20)]:
                try:
                    cap = driver.extract_social(u, platform, listing=False)
                    st = classify_page(cap["url"], cap["title"], cap["text"], 200)
                    if st != SUCCESS:
                        errors.append(f"{u} -> {st}")
                        partial = True
                        continue
                    if not cap["posts"]:
                        errors.append(f"{u} -> no_posts_in_dom"
                                      + (f" ({cap['eval_error']})"
                                         if cap.get("eval_error") else ""))
                        partial = True
                        continue
                    rec = _rec(cap["posts"][0], cap, "post_page_capture")
                    if task.get("ocr", True):
                        _maybe_ocr(cap["posts"][0], cap, rec)
                    records.append(rec)
                except Exception as e:
                    errors.append(f"{u} -> {type(e).__name__}")
                    partial = True
        else:
            urls = []
            search_ctx = {}
            if mode == "search":
                surl = task.get("search_url", "")
                if not surl:
                    out.update(reason_code="missing_search_url",
                               errors=["search mode needs search_url"])
                    print(json.dumps(out), flush=True)
                    return
                page = driver.extract(surl)
                st = classify_page(page.url, page.title, page.text, page.status_code)
                if st != SUCCESS:
                    out.update(status=st, reason_code="search_page_challenge",
                               errors=[f"search halted: {st}"])
                    print(json.dumps(out), flush=True)
                    return
                urls = [u for u in (page.links or [])][:task.get("max_items", 10)]
                search_ctx = {"search_query": task.get("search_query", ""),
                              "search_url": surl,
                              "search_time": datetime.now(timezone.utc).isoformat()}
            else:
                urls = task.get("urls", [])[:task.get("max_items", 20)]
            for u in urls:
                try:
                    page = driver.extract(u)
                    st = classify_page(page.url, page.title, page.text, page.status_code)
                    if st != SUCCESS:
                        errors.append(f"{u} -> {st}")
                        partial = True
                        if st in ("ACCESS_DENIED", "RATE_LIMITED", "BLOCKED"):
                            break
                        continue
                    records.append({
                        "platform": platform,
                        "account_username": page.author or f"{platform}_account",
                        "source_url": page.url, "text": page.text or "",
                        "title": page.title or "",
                        "published_at": page.published_at.isoformat()
                        if hasattr(page.published_at, "isoformat") else (page.published_at or ""),
                        "raw_html": page.html or "",
                        "screenshot_b64": base64.b64encode(page.screenshot).decode()
                        if page.screenshot else "",
                        "provenance": {"collection_method": "authenticated_browser",
                                       "access": "investigator_owned_account",
                                       "independent": True, **search_ctx}})
                except Exception:
                    errors.append(f"{u} -> ERROR")
                    partial = True
        out.update(status="PARTIAL" if partial and records else (SUCCESS if records else "ERROR"),
                   reason_code="ok" if records else "no_records",
                   records=records, errors=errors)
        print(json.dumps(out), flush=True)
    except Exception as e:
        import traceback
        traceback.print_exc(file=sys.stderr)
        detail = f"{type(e).__name__}: {str(e)[:180]}" if str(e) else type(e).__name__
        out.update(reason_code="worker_failed", errors=[detail])
        try:
            print(json.dumps(out), flush=True)
        except Exception:
            pass
    finally:
        try:
            if driver is not None:
                driver.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
