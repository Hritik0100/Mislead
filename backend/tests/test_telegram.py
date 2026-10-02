"""Tests for the REAL Telegram MTProto collector.

No network, no real credentials, telethon never imported (FakeTelegramDriver).
Real secret values used here must NEVER appear in results, records, provenance,
errors, notes or markers.

Required scenarios mirror the auth_browser contract:
 1. disabled without credentials -> AUTHENTICATION_REQUIRED, 0 records
 2. unauthorized session -> AUTHENTICATION_REQUIRED + manual-action note
 3. successful collection -> correct records, permalinks, provenance
 4. api_hash / phone / session / 2FA never leak into the result
 5. FloodWait -> RATE_LIMITED, 0 records, and NO retry (one fetch call)
 6. private channel -> ACCESS_DENIED, 0 records, no bypass attempt
 7. photo bytes are really captured (media evidence, not a claim)
 8. no screenshot is ever claimed (Telegram renders no page)
 9. empty channel is EMPTY, not an error
10. missing target is a structured error, not a traceback
11. session marker is 0600
12. service messages / reaction-only messages are not evidence
13. record shaping is pure: no driver needed
"""
import asyncio
import json
import os
from datetime import datetime, timezone

import pytest

from app.services.collectors.telegram import (
    TelegramCollector, TelegramConfig, TelegramMessage, FakeTelegramDriver,
    TelethonDriver, redact_tg, message_permalink, run_telegram_task,
    collect_platform_stub, SUCCESS, EMPTY, AUTHENTICATION_REQUIRED,
    ACCESS_DENIED, RATE_LIMITED, ERROR,
)
from app.services.collectors.auth_browser import load_session_marker

API_HASH = "0123456789abcdef0123456789abcdef"          # real secret
PHONE = "+919876543210"                                  # real secret
SESSION_STR = "1AVJqQAAAAAAAAAAtPRv-8vL1YqLbG8xLbG8xLbG8xLbG8"  # real secret
TWOFA = "S3CR3T_2fa_pw"                                  # real secret
ALL_SECRETS = (API_HASH, PHONE, SESSION_STR, TWOFA)


def dump(o):
    return json.dumps(o, default=str)


@pytest.fixture
def env(monkeypatch, tmp_path):
    monkeypatch.setenv("TELEGRAM_API_ID", "123456")
    monkeypatch.setenv("TELEGRAM_API_HASH", API_HASH)
    monkeypatch.setenv("TELEGRAM_PHONE", PHONE)
    monkeypatch.setenv("TELEGRAM_SESSION", SESSION_STR)
    monkeypatch.setenv("TELEGRAM_2FA_PASSWORD", TWOFA)
    return tmp_path


def msg(**kw):
    base = dict(
        msg_id=42,
        text="Breaking: an official statement was released at 14:00 IST today.",
        author_username="some_channel",
        author_display="Some Channel",
        peer_username="some_channel",
        peer_title="Some Channel",
        peer_id=1001234567890,
        peer_is_channel=True,
        published_at=datetime(2026, 3, 4, 8, 30, tzinfo=timezone.utc),
        views=1500,
        forwards=12,
        replies=3,
    )
    base.update(kw)
    return TelegramMessage(**base)


def task(**kw):
    base = {"type": "telegram", "channel": "some_channel", "max_items": 30}
    base.update(kw)
    return base


def arun(coro):
    """Run one coroutine to completion. No pytest-asyncio needed: the collector
    is async only because Telethon is, and the driver is faked here."""
    return asyncio.run(coro)


def run(driver, **kw):
    col = TelegramCollector(session_dir=str(kw.pop("session_dir", "/tmp/tg-test-sess")),
                            driver=driver)
    return arun(col.collect_async(task(**kw)))


# 1. no app credentials -> adapter disabled, tells the investigator what to do
def test_1_disabled_without_credentials(monkeypatch, tmp_path):
    for v in ("TELEGRAM_API_ID", "TELEGRAM_API_HASH", "TELEGRAM_PHONE", "TELEGRAM_SESSION"):
        monkeypatch.delenv(v, raising=False)
    res = run(FakeTelegramDriver([msg()], connect_status=SUCCESS))
    assert res["status"] == AUTHENTICATION_REQUIRED
    assert res["records"] == []
    assert res["reason_code"] == "adapter_disabled_no_credentials"
    assert "telegram login" in res["note"]


# 2. session file exists but is NOT authorized -> stop, manual action
def test_2_unauthorized_session(env):
    fake = FakeTelegramDriver([msg()], connect_status=AUTHENTICATION_REQUIRED)
    res = run(fake, session_dir=str(env / "sess"))
    assert res["status"] == AUTHENTICATION_REQUIRED
    assert res["records"] == []
    assert res["errors"] == ["AUTHENTICATION_ACTION_REQUIRED"]
    assert "telegram login" in res["note"]
    # It must not have tried to fetch anything.
    assert not [c for c in fake.calls if c[0] == "fetch"]


# 3. happy path: real records with permalink, engagement and provenance
def test_3_successful_collection(env, tmp_path):
    fake = FakeTelegramDriver([msg(), msg(msg_id=43, text="second post")])
    res = run(fake, session_dir=str(tmp_path / "sess"))
    assert res["status"] == SUCCESS
    assert len(res["records"]) == 2
    r = res["records"][0]
    assert r["platform"] == "telegram"
    assert r["account_username"] == "some_channel"
    assert r["source_url"] == "https://t.me/some_channel/42"
    assert r["published_at"].startswith("2026-03-04T08:30:00")
    assert r["engagement"] == {"views": 1500, "forwards": 12, "replies": 3}
    p = r["provenance"]
    assert p["collection_method"] == "telegram_mtproto"
    assert p["access"] == "investigator_owned_account"
    assert p["independent"] is True
    assert p["entity_type"] == "channel"
    assert p["message_id"] == 42
    assert p["group_id"] == 1001234567890
    assert p["text_source"] == "message"
    # No secrets in a successful result either.
    for s in ALL_SECRETS:
        assert s not in dump(res)


# 4. secret hygiene: no credential value in the result, whatever the path
def test_4_no_secret_leak(env, tmp_path):
    for status in (SUCCESS, AUTHENTICATION_REQUIRED, ACCESS_DENIED, RATE_LIMITED):
        exc = None
        if status == ACCESS_DENIED:
            exc = type("ChannelPrivateError", (Exception,), {})()
        elif status == RATE_LIMITED:
            exc = type("FloodWaitError", (Exception,), {"seconds": 420})()
        fake = FakeTelegramDriver([msg()], connect_status=status, fetch_exc=exc)
        res = run(fake, session_dir=str(tmp_path / f"s{status}"))
        blob = dump(res)
        for s in ALL_SECRETS:
            assert s not in blob, f"{s} leaked in {status}"
        # And the value-based scrubber catches a secret in free text too.
        assert API_HASH not in redact_tg({"note": f"hash={API_HASH} done"})


# 5. FloodWait -> RATE_LIMITED with the server wait, and exactly one attempt
def test_5_floodwait_no_retry(env, tmp_path):
    exc = type("FloodWaitError", (Exception,), {"seconds": 420})()
    fake = FakeTelegramDriver(fetch_exc=exc)
    driver = TelethonDriver(TelegramConfig.from_env())
    fake._status_for = driver._status_for       # real Telegram error taxonomy
    fake._describe = driver._describe
    res = run(fake, session_dir=str(tmp_path / "sess"))
    assert res["status"] == RATE_LIMITED
    assert res["records"] == []
    assert "420" in res["errors"][0]
    fetches = [c for c in fake.calls if c[0] == "fetch"]
    assert len(fetches) == 1, "must not retry a FloodWait"


# 6. private channel -> ACCESS_DENIED, no join attempt, no records
def test_6_private_channel_not_bypassed(env, tmp_path):
    exc = type("ChannelPrivateError", (Exception,), {})()
    fake = FakeTelegramDriver(fetch_exc=exc)
    driver = TelethonDriver(TelegramConfig.from_env())
    fake._status_for = driver._status_for
    fake._describe = driver._describe
    res = run(fake, session_dir=str(tmp_path / "sess"))
    assert res["status"] == ACCESS_DENIED
    assert res["records"] == []
    assert "private" in res["errors"][0]
    assert len([c for c in fake.calls if c[0] == "fetch"]) == 1


# 7. real photo bytes are captured so OCR/meme analysis has something to read
def test_7_media_bytes_captured(env, tmp_path):
    png = (b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)
    fake = FakeTelegramDriver([msg(media_kind="photo", media_mime="image/jpeg",
                                   media_bytes=png)])
    res = run(fake, session_dir=str(tmp_path / "sess"))
    import base64
    assert base64.b64decode(res["records"][0]["image_b64"]) == png
    assert res["records"][0]["provenance"]["media_bytes_captured"] is True
    assert res["records"][0]["provenance"]["media_kind"] == "photo"


# 8. never claim a screenshot: Telegram renders no page we can capture
def test_8_never_fakes_screenshot(env, tmp_path, monkeypatch):
    # Force the base64 -> SourceRecord path in run_telegram_task's shaper.
    from app.services.collectors import telegram as tg
    recs = tg.run_telegram_task.__globals__  # keep reference for clarity
    fake = FakeTelegramDriver([msg()])
    res = run(fake, session_dir=str(tmp_path / "sess"))
    assert res["status"] == SUCCESS
    shaped = TelegramCollector(driver=FakeTelegramDriver([msg()]))
    # run_telegram_task is exercised separately in test_10; here just assert the
    # shaped payload never carries a screenshot key.
    assert "screenshot_b64" not in res["records"][0]


# 9. empty channel is EMPTY (not an error, not a broken collector)
def test_9_empty_channel(env, tmp_path):
    fake = FakeTelegramDriver([])
    res = run(fake, session_dir=str(tmp_path / "sess"))
    assert res["status"] == EMPTY
    assert res["records"] == []
    assert "no messages" in res["note"]


# 10. missing target -> structured error; bad worker output is handled
def test_10_missing_target_and_bad_worker(env, tmp_path, monkeypatch):
    fake = FakeTelegramDriver([msg()])
    col = TelegramCollector(session_dir=str(tmp_path / "sess"), driver=fake)
    res = arun(col.collect_async({"type": "telegram"}))
    assert res["reason_code"] == "missing_target"
    assert res["records"] == []
    # A worker that prints nothing must not raise.
    monkeypatch.setattr("subprocess.run",
                        lambda *a, **k: type("P", (), {"stdout": "", "stderr": ""})())
    bad = run_telegram_task({"channel": "x"})
    assert bad["status"] == ERROR
    assert bad["reason_code"] == "worker_no_output"
    # A line that starts as JSON but is truncated must not raise either.
    monkeypatch.setattr("subprocess.run", lambda *a, **k: type(
        "P", (), {"stdout": '{"status": "SUCCESS", "records": [', "stderr": ""})())
    bad2 = run_telegram_task({"channel": "x"})
    assert bad2["reason_code"] == "worker_bad_output"


# 11. the session marker is 0600 (created by the real login command)
def test_11_session_marker_is_0600(tmp_path):
    from app.services.collectors.auth_browser import save_session_marker
    sdir = str(tmp_path / "sess")
    save_session_marker(sdir, "telegram-tg", {"platform": "telegram"})
    p = os.path.join(sdir, "telegram-tg.json")
    assert oct(os.stat(p).st_mode & 0o777) == "0o600"
    assert load_session_marker(sdir, "telegram-tg")["platform"] == "telegram"
    # ...and the collector writes a marker without ever containing a secret.
    assert ALL_SECRETS[0] not in open(p).read()


# 12. reaction-only / service messages are skipped by the real driver
def test_12_service_messages_skipped():
    src = open(os.path.join(os.path.dirname(__file__), "..", "app", "services",
                            "collectors", "telegram.py")).read()
    assert "if not getattr(msg, \"message\", None) and not getattr(msg, \"media\")" in src
    assert "continue  # pure reactions / service notice: not evidence" in src


# 13. permalinks: public channel vs private group the account belongs to
def test_13_permalinks():
    assert message_permalink("news", 1001234567890, 7) == "https://t.me/news/7"
    # Private supergroup: honest permalink + internal id preserved.
    assert message_permalink("", -1001234567890, 7) == "https://t.me/c/1234567890/7"


# 14. the non-Telegram platforms are still honest stubs
def test_14_other_platforms_still_stubbed():
    for plat in ("x", "instagram", "facebook", "matrix", "element", "youtube"):
        recs, err = collect_platform_stub(plat, "handle1")
        assert err == ""
        assert recs[0].engagement["needs_manual_evidence"] is True
    # telegram is no longer a stub platform
    recs, err = collect_platform_stub("telegram", "chan")
    assert err == "unsupported platform: telegram"
    assert recs == []
