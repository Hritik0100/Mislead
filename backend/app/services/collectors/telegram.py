"""Telegram collector — REAL MTProto access via Telethon.

Scope: content the investigator's OWN account can legitimately see (public
channels, and groups that account is a member of). Nothing else.

HARD RESTRICTIONS (enforced, tested — same contract as auth_browser.py):
- No invite-link guessing, no join-spam, no private-channel bypass. A private
  entity is reported as ACCESS_DENIED and left alone.
- No MFA/code bypass. If the saved session is not authorized, collection stops
  with AUTHENTICATION_REQUIRED and the investigator is told to run the login
  command. The collector NEVER reads a login code or 2FA password itself.
- No rate-limit circumvention. FloodWait -> RATE_LIMITED with the server's wait
  time and no retry (retrying a FloodWait is exactly what gets an account
  rate-limited or banned).
- Failed fetches are NEVER converted into evidence. A record exists only if the
  server actually returned the message.
- api_id / api_hash / phone / session string / 2FA password never appear in
  logs, errors, records, evidence rows, DB rows or LLM prompts.

Authorization model (no prompt injection into a worker subprocess):
1. `python -m app.services.collectors.telegram login`  <- interactive, TTY only.
   Asks for the login code + 2FA password on the investigator's terminal and
   writes a 0600 session file. This is the ONLY place secrets are entered.
2. Collection reuses that file. `TELEGRAM_SESSION` (StringSession) is supported
   for CI/headless, but with no TTY there is no code entry, so an unauthorized
   session always reports AUTHENTICATION_REQUIRED.

Status vocabulary (shared with auth_browser):
  SUCCESS | PARTIAL | EMPTY | AUTHENTICATION_REQUIRED | ACCESS_DENIED |
  RATE_LIMITED | BLOCKED | ERROR
"""
import asyncio
import base64
import io
import json
import os
import stat
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .base import SourceRecord
from .auth_browser import (  # reuse the shared contract + helpers
    SUCCESS, PARTIAL, AUTHENTICATION_REQUIRED, MFA_REQUIRED, ACCESS_DENIED,
    RATE_LIMITED, BLOCKED, ERROR, redact_for_log, default_session_dir,
    save_session_marker, load_session_marker, clear_session_marker,
)

# An empty-but-successful run is distinct from a failure: "we looked, there was
# nothing" must not look like "collection broke".
EMPTY = "EMPTY"

# ---------- secret hygiene ----------
# auth_browser's redactor knows password/token/api_key/auth. Telegram adds
# api_hash (a real credential that does not match those words), the phone
# number, the StringSession blob and the login code.
#
# Two tiers on purpose. Distinctive names are matched as substrings
# ("phone_code_hash" should catch "phone_code_hash_b32"). Short, ambiguous ones
# are matched EXACTLY, because a substring rule on "code" also swallows
# `reason_code` and `status_code` and turns a diagnosis into "***".
_TG_SECRET_KEYS_EXACT = ("code", "session", "string_session", "phone", "password", "token")
_TG_SECRET_KEYS_SUBSTR = ("api_hash", "api_id", "phone_code_hash", "access_token",
                          "bot_token", "twofa", "2fa_password")


def _is_secret_key(key: str) -> bool:
    k = str(key).lower()
    return k in _TG_SECRET_KEYS_EXACT or any(h in k for h in _TG_SECRET_KEYS_SUBSTR)


def redact_tg(obj: Any, secrets: tuple = ()) -> Any:
    """redact_for_log + Telegram-specific keys + explicit secret values."""
    out = redact_for_log(obj)
    return _scrub(out, [s for s in secrets if s])


def _scrub(obj: Any, secrets: list) -> Any:
    if isinstance(obj, dict):
        return {k: ("***" if _is_secret_key(k) else _scrub(v, secrets))
                for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_scrub(v, secrets) for v in obj]
    if isinstance(obj, str):
        for s in secrets:
            if s and len(s) >= 6 and s in obj:
                obj = obj.replace(s, "***")
        return obj
    return obj


# ---------- config ----------
@dataclass
class TelegramConfig:
    """Credentials for the investigator's own Telegram account.

    `api_id`/`api_hash` come from my.telegram.org (app identity, not user auth).
    `phone` is only needed for the interactive login command, not for collection
    once a session file exists.
    """
    api_id: int = 0
    api_hash: str = ""
    phone: str = ""
    session_string: str = ""
    twofa_password: str = ""
    session_name: str = "telegram"

    @classmethod
    def from_env(cls, session_name: str = "telegram") -> "TelegramConfig":
        def _get(name: str, default: str = "") -> str:
            v = os.getenv(name, "")
            if not v:
                try:
                    from app.core.config import settings
                    v = getattr(settings, name, "") or ""
                except Exception:
                    v = ""
            return v or default

        def _int(name: str) -> int:
            try:
                return int(_get(name, "0") or 0)
            except Exception:
                return 0

        return cls(
            api_id=_int("TELEGRAM_API_ID"),
            api_hash=_get("TELEGRAM_API_HASH"),
            phone=_get("TELEGRAM_PHONE"),
            session_string=_get("TELEGRAM_SESSION"),
            twofa_password=_get("TELEGRAM_2FA_PASSWORD"),
            session_name=session_name or "telegram",
        )

    @property
    def has_app_credentials(self) -> bool:
        return bool(self.api_id and self.api_hash)

    @property
    def is_configured(self) -> bool:
        """Enough to attempt an authorized read."""
        return self.has_app_credentials and bool(self.session_string or self.phone)

    def secret_values(self) -> tuple:
        return (self.api_hash, self.phone, self.session_string, self.twofa_password)

    def session_file(self) -> str:
        return os.path.join(default_session_dir(), f"{self.session_name}.session")


# ---------- normalization ----------
def _iso(dt: Any) -> str:
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    return ""


def _parse_dt(s: str):
    if not s:
        return None
    try:
        from dateutil import parser as dateparser
        d = dateparser.parse(str(s))
        return d.replace(tzinfo=timezone.utc) if d and not d.tzinfo else d
    except Exception:
        return None


def message_permalink(username: str, chat: Any, msg_id: int) -> str:
    """Stable public permalink.

    Public channel -> https://t.me/<username>/<id> (openable by anyone).
    Private group the account belongs to -> https://t.me/c/<internal>/<id>,
    which only resolves for members. That is intentional: it is the honest
    permalink for content that is not public, and the evidence row records the
    chat id too, so the analyst can find it inside the tool.
    """
    if username:
        return f"https://t.me/{username}/{msg_id}"
    try:
        raw = getattr(chat, "id", chat)
        # Telegram ids are -100XXXXXXXXXX for channels/supergroups.
        internal = str(raw)[4:] if str(raw).startswith("-100") else str(raw)
        return f"https://t.me/c/{internal}/{msg_id}"
    except Exception:
        return f"https://t.me/c/{msg_id}"


# ---------- driver abstraction ----------
@dataclass
class TelegramMessage:
    """One normalized message. Drivers produce these; the collector shapes them."""
    msg_id: int = 0
    text: str = ""
    caption: str = ""
    author_username: str = ""
    author_display: str = ""
    peer_username: str = ""
    peer_title: str = ""
    peer_id: int = 0
    peer_is_channel: bool = True
    published_at: Any = None
    views: Optional[int] = None
    forwards: Optional[int] = None
    replies: Optional[int] = None
    reply_to_msg_id: Optional[int] = None
    grouped_id: Optional[int] = None
    media_kind: str = ""          # photo | video | document | voice | sticker
    media_mime: str = ""
    media_bytes: Optional[bytes] = None
    post_author: str = ""         # channel signature on behalf of someone else
    raw: Dict[str, Any] = field(default_factory=dict)


class BaseTelegramDriver:
    """Async driver interface (Telethon is async; tests use the fake)."""
    name = "base"

    async def connect(self, cfg: TelegramConfig) -> str:
        """Return SUCCESS, or an *_REQUIRED / denied status."""
        raise NotImplementedError

    async def fetch(self, target: str, limit: int, search: str = "") -> list:
        raise NotImplementedError

    async def disconnect(self):
        pass

    def secret_values(self) -> tuple:
        return ()


class TelethonDriver(BaseTelegramDriver):
    """REAL MTProto driver. Only used inside telegram_worker (own event loop)."""
    name = "telethon"

    # Telethon raises these by class name; keep the match string-based so the
    # module imports fine even when telethon is not installed.
    _ERR = {
        "FloodWaitError": RATE_LIMITED,
        "FloodPremiumWaitError": RATE_LIMITED,
        "ChannelPrivateError": ACCESS_DENIED,
        "ChatAdminRequiredError": ACCESS_DENIED,
        "UserPrivacyRestrictedError": ACCESS_DENIED,
        "UsernameNotOccupiedError": ACCESS_DENIED,
        "UsernameInvalidError": ACCESS_DENIED,
        "InviteHashExpiredError": ACCESS_DENIED,
        "AuthKeyUnregisteredError": AUTHENTICATION_REQUIRED,
        "SessionPasswordNeededError": MFA_REQUIRED,
        "PhoneCodeInvalidError": AUTHENTICATION_REQUIRED,
        "PhoneCodeExpiredError": AUTHENTICATION_REQUIRED,
        "FloodError": RATE_LIMITED,
        "ForbiddenError": ACCESS_DENIED,
    }

    def __init__(self, cfg: TelegramConfig, session_dir: str | None = None):
        self.cfg = cfg
        self.session_dir = session_dir or default_session_dir()
        self.client = None
        self.authorized = False

    def secret_values(self) -> tuple:
        return self.cfg.secret_values()

    def _status_for(self, exc: Exception) -> str:
        for name, status in self._ERR.items():
            if type(exc).__name__ == name:
                return status
        return ""

    def _describe(self, exc: Exception) -> str:
        """Human-readable, secret-free reason."""
        for name in self._ERR:
            if type(exc).__name__ == name:
                extra = ""
                if name.startswith("FloodWait") or name == "FloodError":
                    # Telethon exposes the server's requested wait in seconds.
                    secs = getattr(exc, "seconds", None)
                    extra = f" (server asked to wait {secs}s)" if secs else ""
                if name == "ChannelPrivateError":
                    extra = " (entity exists but is private; this account cannot see it)"
                if name == "UsernameNotOccupiedError":
                    extra = " (no such public username)"
                return f"{name}{extra}"
        return type(exc).__name__

    async def connect(self, cfg: TelegramConfig) -> str:
        try:
            from telethon import TelegramClient
        except ImportError:
            return ERROR
        os.makedirs(self.session_dir, exist_ok=True)
        path = self.session_file()
        try:
            if cfg.session_string:
                # StringSession: no filesystem session, still no code entry here.
                from telethon.sessions import StringSession
                self.client = TelegramClient(StringSession(cfg.session_string),
                                            cfg.api_id, cfg.api_hash)
            else:
                self.client = TelegramClient(path, cfg.api_id, cfg.api_hash)
        except Exception:
            return ERROR
        try:
            await self.client.connect()
        except Exception as exc:
            st = self._status_for(exc)
            return st or ERROR
        try:
            self.authorized = bool(await self.client.is_user_authorized())
        except Exception:
            self.authorized = False
        if not self.authorized:
            # Telethon would happily prompt for a code here. We refuse: a
            # non-interactive worker must never accept a login secret, and
            # guessing/interpolating a code would be a bypass.
            return AUTHENTICATION_REQUIRED
        return SUCCESS

    def session_file(self) -> str:
        return self.cfg.session_file()

    async def fetch(self, target: str, limit: int, search: str = "") -> list:
        from telethon.tl.types import Channel, Chat
        out: List[TelegramMessage] = []
        entity = await self.client.get_entity(target)
        kwargs: Dict[str, Any] = {"limit": limit}
        if search:
            kwargs["search"] = search
        async for msg in self.client.iter_messages(entity, **kwargs):
            if not getattr(msg, "message", None) and not getattr(msg, "media"):
                continue  # pure reactions / service notice: not evidence
            peer_username, peer_title, peer_id, is_channel = "", "", 0, True
            if isinstance(entity, Channel):
                peer_username = entity.username or ""
                peer_title = entity.title or ""
                peer_id = entity.id
                is_channel = True
            elif isinstance(entity, Chat):
                peer_title = entity.title or ""
                peer_id = entity.id
                is_channel = False

            author_username, author_display = "", ""
            try:
                sender = await self.client.get_sender(msg)
            except Exception:
                sender = None
            if sender is not None:
                author_username = getattr(sender, "username", "") or ""
                author_display = (getattr(sender, "first_name", "") or "") or ""
                if not author_display:
                    author_display = getattr(sender, "title", "") or ""
                if not author_username:
                    # Private authors have no @handle. Keep a stable handle so
                    # the spread graph can still group their posts.
                    author_username = f"id{sender.id}"

            media_kind, media_mime, media_bytes = "", "", None
            media = getattr(msg, "media", None)
            if media is not None:
                media_kind = type(media).__name__.replace("MessageMedia", "").lower() or "media"
                doc = getattr(msg, "document", None)
                if doc is not None:
                    media_mime = getattr(doc, "mime_type", "") or ""
                else:
                    media_mime = "image/jpeg" if getattr(msg, "photo", None) else ""
                    media_kind = "photo" if getattr(msg, "photo", None) else media_kind
                if media_kind in ("photo", "document", "video"):
                    # Real bytes so OCR/meme analysis has something to read.
                    try:
                        buf = io.BytesIO()
                        got = await self.client.download_media(msg, file=buf)
                        if got and buf.tell():
                            media_bytes = buf.getvalue()
                    except Exception:
                        media_bytes = None

            replies = getattr(getattr(msg, "replies", None), "replies", None)
            out.append(TelegramMessage(
                msg_id=msg.id,
                text=msg.message or "",
                caption=getattr(msg, "media", None) and (getattr(msg, "message", "") or "") or "",
                author_username=author_username,
                author_display=author_display,
                peer_username=peer_username,
                peer_title=peer_title,
                peer_id=peer_id,
                peer_is_channel=is_channel,
                published_at=getattr(msg, "date", None),
                views=getattr(msg, "views", None),
                forwards=getattr(msg, "forwards", None),
                replies=replies,
                reply_to_msg_id=getattr(msg, "reply_to_msg_id", None),
                grouped_id=getattr(msg, "grouped_id", None),
                media_kind=media_kind,
                media_mime=media_mime,
                media_bytes=media_bytes,
                post_author=getattr(msg, "post_author", "") or "",
                raw={"out": getattr(msg, "out", None),
                     "via_bot": getattr(getattr(msg, "via_bot", None), "username", "") or ""},
            ))
        return out

    async def disconnect(self):
        try:
            if self.client is not None:
                await self.client.disconnect()
        except Exception:
            pass
        self.client = None


class FakeTelegramDriver(BaseTelegramDriver):
    """Scripted driver for tests. No network, no credentials, no telethon."""
    name = "fake"

    def __init__(self, messages: list | None = None, connect_status: str = SUCCESS,
                 fetch_exc: Exception | None = None, cfg: TelegramConfig | None = None):
        self.messages = messages or []
        self.connect_status = connect_status
        self.fetch_exc = fetch_exc
        self.cfg = cfg or TelegramConfig()
        self.calls: list = []
        self.connected = False
        self.targets: list = []

    async def connect(self, cfg: TelegramConfig) -> str:
        self.calls.append(("connect",))
        self.connected = self.connect_status == SUCCESS
        return self.connect_status

    async def fetch(self, target: str, limit: int, search: str = "") -> list:
        self.calls.append(("fetch", target, limit, search))
        self.targets.append(target)
        if self.fetch_exc is not None:
            raise self.fetch_exc
        return self.messages[:limit]

    async def disconnect(self):
        self.calls.append(("disconnect",))
        self.connected = False


# ---------- OCR helper (same contract as the browser worker) ----------
def _maybe_ocr(data: bytes, base_text: str) -> tuple:
    """Read text baked into a channel image (memes, posters, screenshots).

    Returns (text_to_store, ocr_block). OCR text is never silently promoted
    over the author's words unless the DOM/message text is thin.
    """
    try:
        from app.services.ocr import service as ocr_svc
    except Exception:
        return base_text, {}
    try:
        res = ocr_svc.ocr_image(data)
    except Exception:
        return base_text, {}
    block = {"attempted": True, "available": res.get("available"),
             "engine": res.get("engine"), "confidence": res.get("confidence"),
             "line_count": res.get("line_count"), "error": res.get("error")}
    ocr_text = res.get("text") or ""
    if not ocr_text:
        return base_text, block
    block["text"] = ocr_text[:4000]
    try:
        promote = ocr_svc.should_promote_ocr(base_text, ocr_text, res.get("confidence"))
    except Exception:
        promote = False
    block["ocr_promoted"] = bool(promote)
    if promote:
        return ocr_text[:20000], block
    return ((base_text or "") + "\n\n[image text]\n" + ocr_text)[:20000], block


# ---------- collector ----------
class TelegramCollector:
    """Real Telegram collection. Async; run it via run_telegram_task()."""

    def __init__(self, driver_factory=None, session_dir: str | None = None,
                 driver: BaseTelegramDriver | None = None):
        self.driver_factory = driver_factory
        self.session_dir = session_dir or default_session_dir()
        self._driver = driver

    # ---- shaping ----
    def _shape(self, m: TelegramMessage, task: dict, session_reused: bool) -> dict:
        text = m.text or m.caption or ""
        img_b64 = ""
        ocr_block: dict = {}
        if m.media_bytes and task.get("ocr", True):
            text, ocr_block = _maybe_ocr(m.media_bytes, text)
            img_b64 = base64.b64encode(m.media_bytes).decode()
        elif m.media_bytes:
            img_b64 = base64.b64encode(m.media_bytes).decode()

        handle = m.author_username or m.peer_username or f"telegram_{m.peer_id or 'unknown'}"
        prov = {
            "collection_method": "telegram_mtproto",
            "access": "investigator_owned_account",
            "independent": True,
            "session_reused": session_reused,
            "collected_via": "telethon_mtproto",
            "entity": m.peer_username or task.get("channel") or task.get("handle") or task.get("url", ""),
            "entity_type": "channel" if m.peer_is_channel else "group",
            "entity_title": m.peer_title,
            "message_id": m.msg_id,
            "group_id": m.peer_id,
            "text_source": "message" if m.text else ("caption" if m.caption else ""),
            "media_kind": m.media_kind,
            "media_mime": m.media_mime,
            "media_bytes_captured": bool(m.media_bytes),
            "reply_to_msg_id": m.reply_to_msg_id,
            "grouped_id": m.grouped_id,
            "post_author": m.post_author,
            "views": m.views,
            "forwards": m.forwards,
            "replies": m.replies,
            "out": bool(m.raw.get("out")),
            "via_bot": m.raw.get("via_bot", ""),
        }
        if task.get("search"):
            prov["search_query"] = task["search"]
        if ocr_block:
            prov["ocr"] = ocr_block
        return {
            "platform": "telegram",
            "account_username": handle,
            "account_display": m.author_display or m.peer_title,
            "profile_url": f"https://t.me/{m.author_username}" if m.author_username else "",
            "source_url": message_permalink(m.peer_username, m.peer_id, m.msg_id),
            "text": text[:20000],
            "title": m.peer_title,
            "published_at": _iso(m.published_at),
            "engagement": {"views": m.views, "forwards": m.forwards, "replies": m.replies},
            "media_refs": ([{"kind": m.media_kind, "mime": m.media_mime,
                             "message_id": m.msg_id}] if m.media_kind else []),
            # Telegram has no rendered page, so there is no HTML snapshot. The
            # message text itself is the captured artifact.
            "raw_html": "",
            "image_b64": img_b64,
            "provenance": prov,
        }

    # ---- main ----
    async def collect_async(self, task: dict, case_keywords: list | None = None) -> dict:
        """case_keywords is accepted for parity with the other collectors.
        Relevance filtering happens in the enrichment pipeline (prefilter), not
        here, so a channel is always captured whole and never half-silently.
        """
        out = {"status": ERROR, "reason_code": "init", "records": [], "errors": [],
               "session_reused": False}
        cfg = TelegramConfig.from_env(task.get("session") or "telegram")
        secrets = cfg.secret_values()
        driver = self._driver
        if driver is None:
            try:
                driver = self.driver_factory(cfg) if self.driver_factory \
                    else TelethonDriver(cfg, self.session_dir)
            except Exception as exc:
                out.update(reason_code="driver_init_failed",
                           errors=[type(exc).__name__])
                return redact_tg(out, secrets)

        mode = task.get("mode", "collect_history")
        try:
            try:
                from telethon import __version__ as _tv  # noqa: F401
                telethon_present = True
            except Exception:
                telethon_present = driver.name != "telethon"

            if not telethon_present:
                out.update(status=AUTHENTICATION_REQUIRED, reason_code="telethon_not_installed",
                           errors=["install telethon: pip install telethon"])
                return redact_tg(out, secrets)

            if not cfg.has_app_credentials:
                # Adapter-off is a product decision, not a driver detail: without
                # app credentials there is no authorized read to make, so no
                # driver is even asked to connect.
                out.update(status=AUTHENTICATION_REQUIRED,
                           reason_code="adapter_disabled_no_credentials",
                           errors=["Telegram adapter disabled: no credentials configured"],
                           note="Set TELEGRAM_API_ID + TELEGRAM_API_HASH (my.telegram.org) "
                                "and run: python -m app.services.collectors.telegram login")
                return redact_tg(out, secrets)

            st = await driver.connect(cfg)
            out["session_reused"] = (st == SUCCESS and
                                     load_session_marker(self.session_dir,
                                                         f"{cfg.session_name}-tg") is not None)
            if st != SUCCESS:
                out.update(status=st, reason_code="not_authorized",
                           records=[], errors=["AUTHENTICATION_ACTION_REQUIRED"],
                           note="Telegram session is not authorized. Run: "
                                "python -m app.services.collectors.telegram login")
                return redact_tg(out, secrets)
            if not out["session_reused"]:
                save_session_marker(self.session_dir, f"{cfg.session_name}-tg",
                                    {"platform": "telegram"})

            if mode == "login_test":
                out.update(status=SUCCESS, reason_code="login_ok")
                return redact_tg(out, secrets)

            target = (task.get("channel") or task.get("handle") or
                      task.get("url") or task.get("target") or "")
            if not target:
                out.update(reason_code="missing_target",
                           errors=["collect needs channel/handle/url"])
                return redact_tg(out, secrets)

            limit = int(task.get("max_items", 30) or 30)
            try:
                msgs = await driver.fetch(target, limit, task.get("search", "") or "")
            except Exception as exc:
                # The real driver knows the Telegram error taxonomy; the fake
                # driver only ever raises something generic.
                status = driver._status_for(exc) if hasattr(driver, "_status_for") \
                    else RATE_LIMITED if type(exc).__name__.startswith("FloodWait") \
                    else ERROR
                desc = driver._describe(exc) if hasattr(driver, "_describe") \
                    else type(exc).__name__
                out.update(status=status or ERROR, reason_code="fetch_failed",
                           records=[], errors=[desc])
                return redact_tg(out, secrets)

            records = [self._shape(m, task, out["session_reused"]) for m in msgs]
            if not records:
                out.update(status=EMPTY, reason_code="no_messages",
                           note=f"'{target}' returned no messages (empty channel, "
                                f"or the search term matched nothing).")
                return redact_tg(out, secrets)
            out.update(status=SUCCESS, reason_code="ok", records=records, errors=[])
            return redact_tg(out, secrets)
        finally:
            try:
                await driver.disconnect()
            except Exception:
                pass


# ---------- subprocess isolation ----------
def run_telegram_task(task: dict, timeout: int = 300) -> dict:
    """Run a Telegram collection in an isolated subprocess.

    Why a subprocess: Telethon is asyncio-native and owns a sqlite session file.
    Running it in the ASGI worker would fight the server's event loop and risk
    two writers on one session file. Task JSON on stdin, result JSON on stdout;
    the last JSON line is the result.
    """
    worker = os.path.join(os.path.dirname(os.path.abspath(__file__)), "telegram_worker.py")
    payload = dict(task)
    payload["session_dir"] = default_session_dir()
    if not payload.get("session"):
        payload["session"] = "telegram"
    try:
        proc = subprocess.run([sys.executable, worker], input=json.dumps(payload),
                              capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"status": ERROR, "reason_code": "worker_timeout", "records": [],
                "errors": ["telegram worker timed out"]}
    except Exception as exc:
        return {"status": ERROR, "reason_code": "worker_spawn_failed", "records": [],
                "errors": [redact_tg(type(exc).__name__)]}
    lines = [ln for ln in (proc.stdout or "").splitlines() if ln.strip().startswith("{")]
    if not lines:
        return {"status": ERROR, "reason_code": "worker_no_output", "records": [],
                "errors": [scrub_stderr(proc.stderr)]}
    try:
        res = json.loads(lines[-1])
    except Exception:
        return {"status": ERROR, "reason_code": "worker_bad_output", "records": [],
                "errors": ["unparseable worker output"]}
    recs = []
    for r in res.get("records", []):
        img = None
        if r.get("image_b64"):
            try:
                img = base64.b64decode(r["image_b64"])
            except Exception:
                img = None
        recs.append(SourceRecord(
            platform=r.get("platform", "telegram"),
            account_username=r.get("account_username", "unknown"),
            account_display=r.get("account_display", ""),
            profile_url=r.get("profile_url", ""),
            source_url=r.get("source_url", ""),
            text=r.get("text", ""),
            title=r.get("title", ""),
            published_at=_parse_dt(r.get("published_at") or ""),
            raw_html=r.get("raw_html", ""),
            engagement=r.get("engagement") or {},
            media_refs=r.get("media_refs") or [],
            image_bytes=img,          # real bytes only; never a claimed screenshot
            screenshot_bytes=None,    # Telegram renders no page we can capture
            provenance=r.get("provenance") or {
                "collection_method": "telegram_mtproto",
                "access": "investigator_owned_account",
                "independent": True,
                "session_reused": res.get("session_reused", False)}))
    res["records"] = recs
    return res


def scrub_stderr(text: str) -> str:
    """Worker stderr can carry a traceback. Keep it short and secret-free."""
    t = (text or "").strip()
    if not t:
        return "no worker output"
    cfg = TelegramConfig.from_env()
    t = _scrub(t[-400:], list(cfg.secret_values()))
    return t.replace("\n", " | ")[:400]


# ---------- interactive login (the ONLY place secrets are entered) ----------
def _prompt(label: str, secret: bool = False) -> str:
    import getpass
    try:
        return (getpass.getpass(label) if secret else input(label)).strip()
    except (EOFError, KeyboardInterrupt):
        return ""


def login(session_dir: str | None = None, session_name: str = "telegram") -> int:
    """Create/repair a 0600 Telegram session from the investigator's terminal.

    Run once per account:
        python -m app.services.collectors.telegram login

    Reads the login code and 2FA password from a TTY. Neither is ever written to
    a log, a record, or the session marker. Needs TELEGRAM_API_ID and
    TELEGRAM_API_HASH in the environment (or entered here).
    """
    sdir = session_dir or default_session_dir()
    cfg = TelegramConfig.from_env(session_name)
    print("Telegram login — investigator's OWN account only.\n")
    if not cfg.has_app_credentials:
        print("TELEGRAM_API_ID / TELEGRAM_API_HASH are required.")
        print("Get them from https://my.telegram.org -> API development tools.\n")
        cfg.api_id = int(_prompt("API id: ") or 0)
        cfg.api_hash = _prompt("API hash: ", secret=True)
        if not (cfg.api_id and cfg.api_hash):
            print("Cannot continue without api_id and api_hash.")
            return 1
    if not cfg.phone:
        cfg.phone = _prompt("Phone (E.164, e.g. +919876543210): ")
    if not cfg.phone:
        print("Cannot continue without a phone number.")
        return 1
    if not cfg.twofa_password:
        cfg.twofa_password = os.getenv("TELEGRAM_2FA_PASSWORD", "")
    os.makedirs(sdir, exist_ok=True)
    try:
        from telethon import TelegramClient
        from telethon.errors import SessionPasswordNeededError
    except ImportError:
        print("telethon is not installed. Run: pip install telethon")
        return 1

    path = os.path.join(sdir, f"{session_name}.session")
    try:
        client = TelegramClient(path, cfg.api_id, cfg.api_hash)
    except Exception as exc:
        print(f"Could not open session: {type(exc).__name__}")
        return 1

    async def _run() -> int:
        await client.connect()
        if await client.is_user_authorized():
            print("Already authorized — nothing to do.")
            await client.disconnect()
            return 0
        try:
            await client.send_code_request(cfg.phone)
        except Exception as exc:
            print(f"Could not request a login code: {type(exc).__name__}.")
            print("Check the phone number, the api_id/api_hash pair, and your connection.")
            await client.disconnect()
            return 1
        code = _prompt("Login code (received in Telegram): ")
        if not code:
            print("No code entered. Aborted.")
            await client.disconnect()
            return 1
        try:
            await client.sign_in(phone=cfg.phone, code=code)
        except SessionPasswordNeededError:
            if not cfg.twofa_password:
                print("\nThis account has 2FA enabled.")
                print("Set TELEGRAM_2FA_PASSWORD and re-run, then re-enter the code.")
                await client.disconnect()
                return 1
            try:
                await client.sign_in(password=cfg.twofa_password)
            except Exception as exc:
                print(f"2FA rejected: {type(exc).__name__}. Aborted.")
                await client.disconnect()
                return 1
        except Exception as exc:
            print(f"Sign-in failed: {type(exc).__name__}. "
                  f"({_scrub(str(exc), list(cfg.secret_values()))[:120]})")
            await client.disconnect()
            return 1
        if not await client.is_user_authorized():
            print("Signed in but the session is still not authorized. Aborted.")
            await client.disconnect()
            return 1
        await client.disconnect()
        return 0

    try:
        rc = asyncio.run(_run())
    except KeyboardInterrupt:
        print("\nAborted.")
        return 1
    if rc == 0 and os.path.isfile(path):
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)  # 0600
        save_session_marker(sdir, f"{session_name}-tg", {"platform": "telegram"})
        print(f"\nSession saved (0600): {path}")
        print("Collections will reuse it silently from now on.")
    return rc


# ---------- still-stubbed platforms ----------
SUPPORTED = ["chirpwire", "matrix", "element", "facebook", "instagram", "x", "youtube"]


def collect_platform_stub(platform: str, handle_or_channel: str, note: str = ""):
    """Telegram is handled by the real collector above; the rest remain stubs.

    Do NOT scrape. Records an analyst-attested placeholder that requires manual
    evidence upload. These are queued for a real connector, not faked.

    IMPORTANT: x / instagram / facebook are NOT stub-only. They are collected
    for real by the auth_browser adapter (logged-in Playwright + the DOM
    extractors in social_dom.py). Reaching this function with one of those names
    means the source was declared as {"type": "x"} instead of
    {"type": "auth_browser", "platform": "x", ...}, so the analyst gets a
    placeholder rather than posts. Fix the source spec, not this collector.
    """
    p = platform.lower()
    if p not in SUPPORTED:
        return [], f"unsupported platform: {platform}"
    rec = SourceRecord(
        platform=p,
        account_username=handle_or_channel,
        profile_url=f"{p}:{handle_or_channel}",
        source_url=f"{p}:{handle_or_channel}",
        text=note or f"[stub] {p} account {handle_or_channel} queued for authorized collection",
        engagement={"stub": True, "needs_manual_evidence": True},
    )
    return [rec], ""


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Telegram MTProto collector")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("login", help="create/repair the session (interactive)")
    sub.add_parser("status", help="check whether the saved session is authorized")
    args = ap.parse_args()

    if args.cmd == "login":
        sys.exit(login())
    if args.cmd == "status":
        cfg = TelegramConfig.from_env()
        marker = load_session_marker(default_session_dir(), f"{cfg.session_name}-tg")
        path = cfg.session_file()
        print(f"session file : {path} ({'present' if os.path.isfile(path) else 'missing'})")
        print(f"marker       : {'present' if marker else 'missing'}")
        print(f"api_id/hash  : {'set' if cfg.has_app_credentials else 'MISSING'}")
        print(f"authorized   : {'unknown (run a collection or `login`)'}")
        sys.exit(0)
    ap.print_help()
