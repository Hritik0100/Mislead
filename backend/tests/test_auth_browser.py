"""Tests for the OPTIONAL authenticated browser adapter (10 required scenarios).

Uses FakeDriver (no network, no real credentials). Real secret value: S3CR3T_pw_9
must NEVER appear in logs, records, DB rows, prompts, or errors.
"""
import hashlib
import json
import logging
import os
from datetime import datetime, timezone, timedelta

import pytest

from app.services.collectors.auth_browser import (
    AuthenticatedBrowserCollector, AuthConfig, BrowserSession, FakeDriver, PageData,
    redact_for_log, classify_page, load_session_marker,
    SUCCESS, PARTIAL, AUTHENTICATION_REQUIRED, MFA_REQUIRED, CAPTCHA_REQUIRED,
    ACCESS_DENIED, RATE_LIMITED, BLOCKED, ERROR,
)

SECRET = "S3CR3T_pw_9"
USER = "investigator@example.org"


@pytest.fixture
def env(monkeypatch, tmp_path):
    monkeypatch.setenv("OUTLET_USERNAME", USER)
    monkeypatch.setenv("OUTLET_PASSWORD", SECRET)
    return tmp_path


def dump(o):
    return json.dumps(o, default=str)


def collector(fake, tmp_path):
    return AuthenticatedBrowserCollector(driver_factory=lambda name: fake,
                                         session_dir=str(tmp_path / "sess"))


def task(**kw):
    base = {"type": "auth_browser", "platform": "outlet", "env_prefix": "OUTLET",
            "login_url": "https://outlet.example/login", "mode": "login_test"}
    base.update(kw)
    return base


# 1. successful login (+ session persisted 0600, no secret in result)
def test_1_login_success(env):
    fake = FakeDriver(login_outcome=SUCCESS)
    res = collector(fake, env).collect(task())
    assert res["status"] == SUCCESS
    assert SECRET not in dump(res)
    marker = list((env / "sess").glob("*.json"))[0]
    assert oct(marker.stat().st_mode & 0o777) == "0o600"
    assert fake.login_calls == 1


# 2. invalid credentials
def test_2_invalid_credentials(env):
    fake = FakeDriver(login_outcome=AUTHENTICATION_REQUIRED)
    res = collector(fake, env).collect(task())
    assert res["status"] == AUTHENTICATION_REQUIRED
    assert res["records"] == []
    assert SECRET not in dump(res)


# 3. MFA required -> stop, no further interaction
def test_3_mfa_required(env):
    fake = FakeDriver(login_outcome=MFA_REQUIRED)
    res = collector(fake, env).collect(task(mode="search", search_url="https://x"))
    assert res["status"] == MFA_REQUIRED
    assert AUTHENTICATION_REQUIRED in str(res.get("errors", [])) or "manual" in dump(res).lower()
    assert not [c for c in fake.calls if c[0] == "extract"]


# 4. CAPTCHA / manual action required
def test_4_captcha_required(env):
    fake = FakeDriver(login_outcome=CAPTCHA_REQUIRED)
    res = collector(fake, env).collect(task())
    assert res["status"] == CAPTCHA_REQUIRED
    assert classify_page("", "Verify you are human", "complete the captcha below") == CAPTCHA_REQUIRED
    assert classify_page("", "t", "enter your two-factor verification code") == MFA_REQUIRED
    assert classify_page("", "t", "just a moment, verifying browser cloudflare") == BLOCKED
    assert classify_page("", "t", "access denied forbidden", 403) == ACCESS_DENIED
    assert classify_page("", "t", "too many requests", 429) == RATE_LIMITED


# 4b. wrong-password page must NEVER classify as SUCCESS (proven live vs Facebook)
def test_4b_wrong_password_page():
    assert classify_page("https://www.facebook.com/login", "Facebook",
                         "Log in to Facebook. The password you've entered is incorrect. "
                         "Input Password is invalid.") == AUTHENTICATION_REQUIRED


# 4c. login-ref parser finds fields without touching secrets
def test_4c_parse_login_refs():
    from app.services.collectors.auth_browser import AgentBrowserCliDriver
    snap = ('- textbox "Email address or mobile number" [ref=e33]\n'
            '- textbox "Password" [ref=e34]\n'
            '- button "Log in" [ref=e36]\n')
    refs = AgentBrowserCliDriver.parse_login_refs(snap)
    assert refs == {"user": "e33", "password": "e34", "submit": "e36"}
    assert AgentBrowserCliDriver.parse_login_refs("nothing here")["submit"] == ""


# 4d. login_flow is fail-closed: fresh login form -> AUTHENTICATION_REQUIRED (never SUCCESS)
def test_4d_login_flow_fail_closed():
    from app.services.collectors.auth_browser import (
        AgentBrowserCliDriver, AUTHENTICATION_REQUIRED, SUCCESS)
    form_snap = ('- textbox "Email address or mobile number" [ref=e33]\n'
                 '- textbox "Password" [ref=e34]\n- button "Log in" [ref=e36]\n')
    feed_snap = '- heading "News Feed" [ref=e1]\n- article "post" [ref=e2]\n'

    def stub_factory(pwd_field):
        def run(*args, timeout=60):
            cmd = " ".join(args)
            if cmd.startswith("snapshot"):
                return form_snap if pwd_field else feed_snap
            if cmd.startswith("eval location"):
                return '"https://www.facebook.com/login"'
            if cmd.startswith("eval document.title"):
                return '"Facebook"'
            if cmd.startswith("eval document.body"):
                return '"Log in to Facebook"'
            if "input[type=password]" in cmd:
                return "true" if pwd_field else "false"
            if cmd.startswith("auth"):
                return ""
            return ""
        return run

    d1 = AgentBrowserCliDriver(session="t1", runner=stub_factory(True))
    r1 = d1.login_flow("https://www.facebook.com/login")
    assert r1["status"] == AUTHENTICATION_REQUIRED
    d2 = AgentBrowserCliDriver(session="t2", runner=stub_factory(False))
    r2 = d2.login_flow("")
    assert r2["status"] == SUCCESS


# 5. authenticated search (+ PARTIAL on 429, failed URL yields no record)
SEARCH = "https://outlet.example/search?q=protest"
PAGES = {
    SEARCH: {"title": "results", "text": "results page",
             "links": ["https://outlet.example/a/1", "https://outlet.example/a/2"]},
    "https://outlet.example/a/1": {"title": "Protest at Jantar Mantar", "text": "Reporters confirm a protest at Jantar Mantar over the commission row.",
                                   "author": "Staff Reporter", "published_at": "2026-09-25T10:00:00",
                                   "html": "<html>real article one</html>"},
    "https://outlet.example/a/2": {"title": "rate limited", "text": "too many requests, slow down", "status_code": 429},
}


def test_5_authenticated_search(env):
    fake = FakeDriver(pages=dict(PAGES), login_outcome=SUCCESS)
    res = collector(fake, env).collect(task(mode="search", search_url=SEARCH,
                                            search_query="protest", max_items=5))
    assert res["status"] == PARTIAL
    assert len(res["records"]) == 1  # 429 page produced NO record/claim input
    r = res["records"][0]
    assert r.source_url == "https://outlet.example/a/1"  # complete URL kept
    assert r.provenance["collection_method"] == "authenticated_browser"
    assert r.provenance["access"] == "investigator_owned_account"
    assert r.provenance["independent"] is True
    assert r.title and r.text and r.raw_html
    assert SECRET not in dump(res)


# 6. evidence extraction + hashing (record -> stored snapshot hash MATCH)
def test_6_evidence_hashing(env, monkeypatch):
    from app.services.evidence import service as evs
    monkeypatch.setattr(evs.settings, "EVIDENCE_DIR", str(env / "ev"))
    fake = FakeDriver(pages={"https://outlet.example/a/1": PAGES["https://outlet.example/a/1"]},
                      login_outcome=SUCCESS)
    rec = collector(fake, env).collect(
        task(mode="collect_urls", urls=["https://outlet.example/a/1"]))["records"][0]
    stored = evs.store_text_evidence("case1", rec.source_url, rec.raw_html)
    assert stored["sha256"] == hashlib.sha256(rec.raw_html.encode()).hexdigest()
    assert stored["sha256"] == hashlib.sha256(
        open(stored["abspath"], "rb").read()).hexdigest()


# 7. credential leakage prevention (logs, records, DB rows, LLM prompts, errors)
def test_7_no_credential_leakage(env, caplog, monkeypatch):
    import app.services.collectors.manager as mgr
    from app.core.database import Base
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.services.enrichment import llm_extract as le

    prompts = []
    monkeypatch.setattr(le, "groq_client", type("NoGroq", (), {"available": False})())
    orig = le.mock_extract
    monkeypatch.setattr(le, "mock_extract", lambda *a, **k: (prompts.append(a), orig(*a, **k))[1])

    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    db = sessionmaker(bind=eng)()
    from app.models.db import Case
    import uuid
    cid = str(uuid.uuid4())
    db.add(Case(id=cid, title="t", objective="protest commission"))
    db.commit()

    fake = FakeDriver(pages={"https://outlet.example/a/1": PAGES["https://outlet.example/a/1"]},
                      login_outcome=SUCCESS)
    import app.services.collectors.auth_browser as ab
    monkeypatch.setattr(ab, "AuthenticatedBrowserCollector",
                        lambda: AuthenticatedBrowserCollector(
                            driver_factory=lambda n: fake,
                            session_dir=str(env / "sess")))
    with caplog.at_level(logging.INFO):
        out = mgr.run_collection(db, cid, [
            {"type": "auth_browser", "platform": "outlet", "env_prefix": "OUTLET",
             "login_url": "https://outlet.example/login", "mode": "collect_urls",
             "urls": ["https://outlet.example/a/1"]},
            {"type": "manual", "platform": "x", "username": "seed",
             "text": "protest at Jantar Mantar commission row", "url": "http://example.invalid/s1"},
        ])
    assert out["status"] == "succeeded" and out["stored"] >= 1  # rest of pipeline unaffected
    blob = dump(out) + caplog.text
    # every persisted row
    for tbl in ("posts", "accounts", "evidence", "claims"):
        for row in db.execute(__import__("sqlalchemy").text(f"SELECT * FROM {tbl}")).fetchall():
            blob += json.dumps([str(v) for v in row], default=str)
    for args in prompts:  # LLM inputs
        blob += json.dumps(args, default=str)
    assert SECRET not in blob
    assert USER in blob or True  # username is not a secret; allowed anywhere


# 8. session reuse (second run skips login)
def test_8_session_reuse(env):
    fake = FakeDriver(pages={"https://outlet.example/a/1": PAGES["https://outlet.example/a/1"]},
                      login_outcome=SUCCESS)
    col = collector(fake, env)
    t = task(mode="collect_urls", urls=["https://outlet.example/a/1"])
    assert col.collect(t)["session_reused"] is False
    assert col.collect(t)["session_reused"] is True
    assert fake.login_calls == 1


# 9. logout clears session
def test_9_logout(env):
    from app.services.collectors.auth_browser import save_session_marker
    fake = FakeDriver(login_outcome=SUCCESS)
    col = collector(fake, env)
    col.collect(task())
    sess = BrowserSession(fake, AuthConfig.from_env("OUTLET", platform="outlet"),
                          str(env / "sess"))
    assert load_session_marker(str(env / "sess"), "auth-outlet") is not None
    assert sess.logout()["status"] == SUCCESS
    assert load_session_marker(str(env / "sess"), "auth-outlet") is None
    assert fake.logged_in is False


# 10. expired session forces re-login
def test_10_session_expiry(env):
    from app.services.collectors.auth_browser import save_session_marker, session_path
    import json as _json
    fake = FakeDriver(login_outcome=SUCCESS)
    col = collector(fake, env)
    col.collect(task())
    assert fake.login_calls == 1
    p = session_path(str(env / "sess"), "auth-outlet")
    m = _json.load(open(p))
    m["saved_at"] = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
    _json.dump(m, open(p, "w"))
    col.collect(task())
    assert fake.login_calls == 2


def test_arkose_puzzle_page_is_reported_as_captcha():
    """Meta's interstitial never says "captcha"; it used to be misreported as a
    plain credential failure, which sent the analyst to the wrong fix."""
    from app.services.collectors.auth_browser import classify_page, CAPTCHA_REQUIRED
    text = ("Complete a challenge to verify you're a human\n"
            "We just need to make sure there's a real human behind this login "
            "attempt. Solve a puzzle to continue.\n"
            "This helps us combat harmful conduct, detect and prevent spam, and "
            "maintain the integrity of our products. We've used Arkose Labs' "
            "MatchKey to provide this security check.")
    assert classify_page("https://www.facebook.com/login", "Facebook", text) == CAPTCHA_REQUIRED


def test_incorrect_password_is_authentication_required():
    from app.services.collectors.auth_browser import (
        classify_page, AUTHENTICATION_REQUIRED)
    text = "The password you've entered is incorrect."
    assert classify_page("https://www.facebook.com/login", "Facebook", text) == \
        AUTHENTICATION_REQUIRED


def test_email_code_page_is_mfa_required():
    from app.services.collectors.auth_browser import classify_page, MFA_REQUIRED
    text = "Check your email\nEnter the code that we sent to u***@gmail.com"
    assert classify_page("https://www.instagram.com/accounts/login/", "Instagram",
                         text) == MFA_REQUIRED


def test_manual_handoff_is_exposed_for_challenged_platforms():
    from app.services.collectors import auth_browser as ab
    assert callable(ab._manual_login_handoff)
    assert callable(ab._logged_in_probe)


def test_platform_no_results_is_not_reported_as_a_dom_failure():
    """X/Facebook render a valid page with zero results. That must not be
    reported as 'no post containers found', which reads like a broken selector
    and sends the analyst to debug the wrong thing."""
    from app.services.collectors.auth_browser import classify_no_results
    x_empty = ('No results for "identify-source verify-claim" '
               'Try searching for something else, or check your Search settings '
               'to see if they are protecting you from potentially sensitive content.')
    assert classify_no_results("https://x.com/search?q=x", "X", x_empty) == "no results for"


def test_a_real_page_is_not_misread_as_no_results():
    from app.services.collectors.auth_browser import classify_no_results
    body = ("Drinking lemon juice with turmeric cures cancer. "
            "These people won't tell you the truth. 5.1K likes.")
    assert classify_no_results("https://x.com/someuser", "X", body) == ""


def test_objectives_are_not_returned_as_search_keywords():
    """Workflow objectives share the CaseKeyword table. If they leak into the
    API's `keywords`, the UI builds a platform query out of them and every
    collection comes back empty."""
    import os as _os
    import tempfile
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.models.db import Base, CaseKeyword
    from app.api.ui import case_keywords, case_objectives
    import uuid as _uuid

    fd, path = tempfile.mkstemp(suffix=".db")
    _os.close(fd)
    eng = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(bind=eng)
    S = sessionmaker(bind=eng)()
    cid = str(_uuid.uuid4())
    S.add(CaseKeyword(id=str(_uuid.uuid4()), case_id=cid, keyword="cancer",
                      normalized_keyword="cancer", type="keyword"))
    S.add(CaseKeyword(id=str(_uuid.uuid4()), case_id=cid, keyword="verify-claim",
                      normalized_keyword="verify-claim", type="objective"))
    S.commit()
    try:
        assert case_keywords(S, cid) == ["cancer"]
        assert case_objectives(S, cid) == ["verify-claim"]
    finally:
        S.close()
        _os.unlink(path)
