"""OPTIONAL authenticated browser collection adapter.

Goal (NOT a bypass): use an investigator-owned account to access content that
account is legitimately authorized to view, via a real browser automation layer.

Flow: credentials (env) -> browser -> login -> session -> search/navigate ->
collect visibly accessible content -> evidence snapshot.

HARD RESTRICTIONS (enforced, tested):
- No CAPTCHA/MFA/login-restriction bypass: on challenge -> *_REQUIRED status,
  no further interaction; investigator completes it manually.
- No private messages, no private groups without membership (adapter only visits
  explicit investigator-provided URLs / account-visible search pages).
- No auth-bug exploits, no rate-limit circumvention (429 -> RATE_LIMITED, no retry storm),
  no Cloudflare/Akamai bypass (-> BLOCKED).
- Only content actually visible to the authenticated account is collected.
- Passwords NEVER enter logs, reports, evidence rows, DB records, error text, or LLM prompts.
- LLM receives collected content + provenance only; it NEVER authenticates.
- Without credentials the adapter is DISABLED; the rest of the pipeline is untouched.

Statuses: SUCCESS | PARTIAL | AUTHENTICATION_REQUIRED | MFA_REQUIRED |
CAPTCHA_REQUIRED | ACCESS_DENIED | RATE_LIMITED | BLOCKED | ERROR
(AUTHENTICATION_ACTION_REQUIRED = manual-action pause alias.)
"""
import json
import os
import re
import stat
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Dict, List, Optional

from .base import SourceRecord

# ---------- statuses ----------
SUCCESS = "SUCCESS"
PARTIAL = "PARTIAL"
AUTHENTICATION_REQUIRED = "AUTHENTICATION_REQUIRED"
MFA_REQUIRED = "MFA_REQUIRED"
CAPTCHA_REQUIRED = "CAPTCHA_REQUIRED"
AUTHENTICATION_ACTION_REQUIRED = "AUTHENTICATION_ACTION_REQUIRED"
ACCESS_DENIED = "ACCESS_DENIED"
RATE_LIMITED = "RATE_LIMITED"
BLOCKED = "BLOCKED"
ERROR = "ERROR"

# ---------- secret hygiene ----------
_SECRET_HINTS = ("password", "passwd", "pwd", "secret", "token", "api_key", "apikey",
                 "auth", "credential", "sessionid", "cookie")


def redact_for_log(obj: Any) -> Any:
    """Deep-copy with secret values replaced by ***. Use for EVERY log/error path."""
    if isinstance(obj, dict):
        return {k: ("***" if any(h in str(k).lower() for h in _SECRET_HINTS) else redact_for_log(v))
                for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [redact_for_log(v) for v in obj]
    if isinstance(obj, str):
        return scrub_text(obj)
    return obj


_CRED_PAIR_RE = re.compile(
    r"(?i)(password|passwd|pwd|secret|token|api[_-]?key|auth)\s*[:=]\s*(\S+)")


def scrub_text(s: str) -> str:
    """Mask password=... style pairs accidentally embedded in free text."""
    return _CRED_PAIR_RE.sub(r"\1=***", s or "")


# ---------- challenge detection (no bypass: detect -> stop -> report) ----------
MFA_HINTS = ("two-factor", "two factor", "2fa", "verification code", "enter the code",
             "authenticator", "one-time passcode", "otp", "mfa")
CAPTCHA_HINTS = ("captcha", "recaptcha", "hcaptcha", "verify you are human",
                 "i am not a robot", "select all images", "checkbox challenge",
                 # Meta/Arkose puzzle interstitial: no literal "captcha" string.
                 "complete a challenge to verify", "solve a puzzle to continue",
                 "matchkey", "arkose", "funcaptcha", "press and hold",
                 "verify it's you",     "unusual activity")
# A platform can render a perfectly valid page that simply has zero results, or
# block a query as "sensitive". Neither is a DOM failure, so name it instead of
# reporting a generic "no post containers found".
NO_RESULTS_HINTS = (
    "no results for", "try searching for something else",
    "search settings to see if they", "potentially sensitive content",
    "your search does not match any", "no posts found", "0 results",
    "write a tweet", "nothing to see here",
)
BLOCK_HINTS = ("just a moment", "attention required", "verifying your browser",
               "challenge-platform", "cloudflare", "akamai", "perimeterx",
               "are you a robot", "unusual traffic")
DENIED_HINTS = ("access denied", "forbidden", "account suspended", "account locked",
                "permission denied", "not authorized", "unauthorized")
# Wrong credentials: login form persists WITH an error banner. Must NEVER
# classify as SUCCESS (proven live: Facebook "password incorrect" page).
BAD_CREDENTIAL_HINTS = ("password.*incorrect", "incorrect password", "wrong password",
                        "invalid username or password", "couldn't find an account",
                        "no account found", "account.*not found", "login.*failed",
                        "could not log you in", "input password is invalid")
RATE_HINTS = ("rate limit", "too many requests", "slow down", "try again later")


def classify_no_results(url: str, title: str, text: str) -> str:
    """Distinguish "the platform found nothing" from "our selector failed"."""
    blob = f"{title or ''}\n{text or ''}".lower()
    for h in NO_RESULTS_HINTS:
        if h in blob:
            return h
    return ""


def classify_page(url: str, title: str, text: str, status_code: int = 200) -> str:
    import re as _re
    blob = f"{title or ''}\n{text or ''}".lower()
    if status_code == 429 or any(h in blob for h in RATE_HINTS):
        return RATE_LIMITED
    if status_code in (401, 403) or any(h in blob for h in DENIED_HINTS):
        return ACCESS_DENIED
    if any(_re.search(p, blob) for p in BAD_CREDENTIAL_HINTS):
        return AUTHENTICATION_REQUIRED
    if any(h in blob for h in MFA_HINTS):
        return MFA_REQUIRED
    if any(h in blob for h in CAPTCHA_HINTS):
        return CAPTCHA_REQUIRED
    if any(h in blob for h in BLOCK_HINTS):
        return BLOCKED
    return SUCCESS


# ---------- config ----------
@dataclass
class AuthConfig:
    platform: str
    username: str = ""
    password: str = ""
    login_url: str = ""
    session_name: str = ""

    @classmethod
    def from_env(cls, prefix: str, platform: str = "", login_url: str = "") -> "AuthConfig":
        def _get(name: str, default: str = "") -> str:
            v = os.getenv(name, "")
            if not v:
                try:
                    from app.core.config import settings
                    v = getattr(settings, name, "") or ""
                except Exception:
                    v = ""
            return v or default
        p = (prefix or "").upper()
        return cls(platform=platform or prefix.lower(),
                   username=_get(f"{p}_USERNAME"),
                   password=_get(f"{p}_PASSWORD"),
                   login_url=login_url or _get(f"{p}_LOGIN_URL"),
                   session_name=f"auth-{prefix.lower()}")

    @property
    def is_configured(self) -> bool:
        return bool(self.username and self.password)


# ---------- session persistence (marker; cookies live in the browser profile) ----------
SESSION_TTL_DAYS = 30


def default_session_dir() -> str:
    try:
        from app.core.config import PROJECT_ROOT
        return os.path.join(PROJECT_ROOT, "data", "sessions")
    except Exception:
        return os.path.abspath("./data/sessions")


def session_path(session_dir: str, session_name: str) -> str:
    os.makedirs(session_dir, exist_ok=True)
    return os.path.join(session_dir, f"{session_name}.json")


def load_session_marker(session_dir: str, session_name: str) -> Optional[dict]:
    p = session_path(session_dir, session_name)
    if not os.path.isfile(p):
        return None
    try:
        m = json.load(open(p))
        ts = datetime.fromisoformat(m.get("saved_at", "1970-01-01"))
        if datetime.now(timezone.utc) - ts > timedelta(days=SESSION_TTL_DAYS):
            return None  # expired -> caller must re-login
        return m
    except Exception:
        return None


def save_session_marker(session_dir: str, session_name: str, extra: dict | None = None):
    p = session_path(session_dir, session_name)
    with open(p, "w") as f:
        json.dump({"saved_at": datetime.now(timezone.utc).isoformat(),
                   **(extra or {})}, f)
    os.chmod(p, stat.S_IRUSR | stat.S_IWUSR)  # 0600


def clear_session_marker(session_dir: str, session_name: str):
    try:
        os.remove(session_path(session_dir, session_name))
    except OSError:
        pass


# ---------- driver abstraction ----------
@dataclass
class PageData:
    url: str
    title: str = ""
    text: str = ""
    html: str = ""
    status_code: int = 200
    author: str = ""
    published_at: Any = None
    links: List[str] = field(default_factory=list)
    screenshot: Optional[bytes] = None


class BaseBrowserDriver:
    name = "base"

    def ensure_launched(self): pass  # launch on demand (Playwright); no-op elsewhere
    def open(self, url: str): raise NotImplementedError
    def snapshot(self) -> list: raise NotImplementedError  # [{ref,kind,name,placeholder}]
    def fill(self, ref: str, text: str): raise NotImplementedError
    def click(self, ref: str): raise NotImplementedError
    def press(self, key: str): raise NotImplementedError
    def eval(self, js: str) -> str: raise NotImplementedError
    def screenshot(self) -> Optional[bytes]: return None
    def close(self): pass


def _clean_eval_output(s: str) -> str:
    """Undo CLI JSON-quoting ("...\\n...") so text/links are real values."""
    t = (s or "").strip()
    if len(t) >= 2 and t.startswith('"') and t.endswith('"'):
        try:
            return json.loads(t)
        except Exception:
            t = t[1:-1]
    return t.replace("\\n", "\n").replace('\\"', '"')


class AgentBrowserCliDriver(BaseBrowserDriver):
    """REAL browser layer via the agent-browser CLI (Chrome CDP).
    Named --session persists the authenticated profile between runs.
    Credentials reach the vault via stdin only (never argv/logs)."""

    LOGIN_FIELD_HINTS = ("email", "username", "phone", "user")
    PASS_FIELD_HINTS = ("password", "passcode")

    def __init__(self, session: str = "osint-auth", runner: Callable = None):
        self.session = session
        self._run = runner or self._subprocess

    def _subprocess(self, *args: str, timeout: int = 60) -> str:
        out = subprocess.run(["agent-browser", "--session", self.session, *args],
                             capture_output=True, text=True, timeout=timeout)
        return out.stdout or ""

    def open(self, url: str): self._run("open", url)
    def snapshot(self) -> list: return []  # parsed by caller via eval/getters
    def snapshot_text(self) -> str: return self._run("snapshot", "-i")
    def fill(self, ref: str, text: str): self._run("fill", ref, text)
    def click(self, ref: str): self._run("click", ref)
    def press(self, key: str): self._run("press", key)
    def eval(self, js: str) -> str: return self._run("eval", js)

    def current_url(self) -> str:
        return self.eval("location.href").strip().strip('"')

    def ensure_profile(self, username: str, password: str, login_url: str) -> bool:
        """Save creds to the tool vault (stdin-only). Returns True on save."""
        try:
            out = subprocess.run(
                ["agent-browser", "auth", "save", self.session,
                 "--url", login_url, "--username", username, "--password-stdin"],
                input=password, capture_output=True, text=True, timeout=60)
            return out.returncode == 0
        except Exception:
            return False

    @staticmethod
    def parse_login_refs(snapshot: str) -> dict:
        """Find username/password/submit refs in a snapshot. No secrets involved."""
        user, pwd, submit = "", "", ""
        for line in (snapshot or "").splitlines():
            m = re.match(r"\s*-\s*textbox\s+\"([^\"]+)\"\s*\[ref=(e\d+)\]", line)
            if m:
                name = m.group(1).lower()
                if any(h in name for h in ("pass",)):
                    pwd = pwd or m.group(2)
                elif any(h in name for h in ("mail", "user", "phone", "login", "id")):
                    user = user or m.group(2)
            b = re.match(r"\s*-\s*button\s+\"([^\"]+)\"\s*\[ref=(e\d+)\]", line)
            if b and any(h in b.group(1).lower()
                         for h in ("log in", "login", "sign in", "submit", "continue")):
                submit = submit or b.group(2)
        if not user:  # fallback: first textbox
            m = re.search(r"-\s*textbox\s+\"[^\"]+\"\s*\[ref=(e\d+)\]", snapshot or "")
            if m:
                user = m.group(1)
        return {"user": user, "password": pwd, "submit": submit}

    def has_password_field(self) -> bool:
        try:
            return self.eval("!!document.querySelector('input[type=password]')").strip() == "true"
        except Exception:
            return False

    def login_flow(self, login_url: str = "") -> dict:
        """Vault fill (stdin-only secret) + explicit submit click + verify.
        A surviving password field ALWAYS means not-logged-in (never SUCCESS).
        Any challenge page is reported, not solved."""
        if login_url:
            self.open(login_url)
        try:
            self._run("auth", "login", self.session, timeout=45)
        except Exception:
            pass  # vault submit may not match custom forms; fall through to explicit click
        snap = ""
        try:
            snap = self.snapshot_text()
        except Exception:
            pass
        refs = self.parse_login_refs(snap)
        if refs["submit"] and self.has_password_field():
            try:
                self.click(refs["submit"])
                time.sleep(8)
            except Exception:
                pass
        url = self.current_url()
        title = self.eval("document.title").strip().strip('"')
        text = self.eval("document.body.innerText.slice(0,4000)")
        if self.has_password_field():
            return {"status": AUTHENTICATION_REQUIRED,
                    "reason": "login_form_present_not_authenticated",
                    "url": url, "title": title, "text": text}
        return {"status": classify_page(url, title, text),
                "url": url, "title": title, "text": text}

    @staticmethod
    def _clean(s: str) -> str:
        """Undo CLI JSON-quoting ("...\\n...") so text/links are real values."""
        return _clean_eval_output(s)

    _NAV_EXACT = ("/", "/friends", "/notifications", "/watch", "/messages",
                  "/marketplace", "/settings", "/help", "/privacy", "/policies",
                  "/reel", "/groups", "/events", "/saved", "/memories", "/feeds",
                  "/bookmarks", "/fundraisers", "/gaming", "/weather",
                  "/birthdays", "/login")

    def _settle(self, target: str = "", waits: int = 6):
        """Let SPA navigation finish + trigger lazy content (scrolls)."""
        import time as _t
        for _ in range(waits):
            try:
                cur = self.current_url()
            except Exception:
                cur = ""
            if target and cur.split("?")[0].rstrip("/") == target.split("?")[0].rstrip("/"):
                break
            _t.sleep(2)
        for _ in range(5):
            try:
                self.eval("window.scrollTo(0, document.body.scrollHeight)")
            except Exception:
                pass
            _t.sleep(2)

    _CONTENT_HINTS = ("/posts/", "/videos/", "/watch", "/reel/", "/photo",
                      "/story", "/permalink", "/share/")

    def extract(self, url: str) -> PageData:
        self.open(url)
        try:
            self.press("Escape")  # dismiss transient browser bubbles (save-password etc.)
        except Exception:
            pass
        self._settle(url)
        title = self._clean(self.eval("document.title"))
        text = self._clean(self.eval("document.body.innerText.slice(0,15000)"))
        html = self._clean(self.eval("document.documentElement.outerHTML.slice(0,800000)"))
        author = self._clean(self.eval(
            "(() => { const a = document.querySelector('[rel=author]'); "
            "if (a && a.innerText.trim()) return a.innerText.trim(); "
            "const t = document.title || ''; "
            "let m = t.match(/^(.+?)\\s+on\\s+X:/); "
            "if (m) return m[1].trim(); "
            "const bt = (document.body.innerText||''); "
            "let h = bt.match(/@([A-Za-z0-9_]{2,15})\\s*\\n?\\s*[·•]/); "
            "if (h) return h[1]; "
            "const b = bt.match(/@([A-Za-z0-9_]{2,15})/); "
            "return b ? b[1] : ''; })()"))
        pub = self._clean(self.eval(
            "document.querySelector('time')?.getAttribute('datetime')||''"))
        raw_links = self._clean(self.eval(
            "Array.from(document.querySelectorAll('a[href]')).map(a=>a.href).slice(0,150).join('\\n')"))
        links = []
        deferred = []
        for l in raw_links.splitlines():
            l = l.strip()
            if not l.startswith("http"):
                continue
            try:
                from urllib.parse import urlsplit
                parts = urlsplit(l)
                seg = (parts.path or "/").rstrip("/") or "/"
                if seg in self._NAV_EXACT:
                    continue
                if "notif_" in parts.query or "checkpoint" in seg or "/search/" in seg:
                    continue  # tabs/pings, not content
            except Exception:
                pass
            if l not in links:
                (links if any(h in l for h in self._CONTENT_HINTS) else deferred).append(l)
        links = links + [d for d in deferred if d not in links]
        return PageData(url=self.current_url() or url, title=title, text=text, html=html,
                        author=author, published_at=pub or None, links=links,
                        screenshot=self.screenshot())

    def screenshot(self) -> Optional[bytes]:
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            path = f.name
        try:
            self._run("screenshot", path)
            with open(path, "rb") as fh:
                return fh.read()
        except Exception:
            return None
        finally:
            try:
                os.remove(path)
            except OSError:
                pass


class PlaywrightDriver(BaseBrowserDriver):
    """REAL browser via Playwright + system Chrome (headed = visible).
    Cookie import for investigator-owned sessions; storage_state persistence.
    Same challenge rules: detect -> stop -> report, never bypass."""

    def __init__(self, session: str = "pw-auth", headless: bool = False,
                 session_dir: str | None = None, platform: str = ""):
        self.session = session
        self.headless = headless
        self.platform = (platform or "").lower()
        self.session_dir = session_dir or default_session_dir()
        self._pw = None
        self._browser = None
        self._ctx = None
        self._page = None
        self._last_eval_error = ""
        self.platform = platform or getattr(self, "platform", "")

    def _default_domain(self) -> str:
        """Cookie domain for this platform. Was hardcoded to .x.com, which
        silently sent Instagram/Facebook cookies to the wrong host."""
        return {
            "x": ".x.com", "twitter": ".x.com",
            "instagram": ".instagram.com",
            "facebook": ".facebook.com", "fb": ".facebook.com",
        }.get(self.platform, "")

    def _state_path(self) -> str:
        os.makedirs(self.session_dir, exist_ok=True)
        return os.path.join(self.session_dir, f"pw-{self.session}.json")

    def ensure_launched(self):
        if self._page is None:
            self.launch()

    def launch(self, storage_state: str | None = None):
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(channel="chrome", headless=self.headless)
        kw: dict = {"viewport": {"width": 1360, "height": 900}}
        if storage_state and os.path.isfile(storage_state):
            kw["storage_state"] = storage_state
        self._ctx = self._browser.new_context(**kw)
        self._page = self._ctx.new_page()

    def import_cookies(self, cookies: list) -> int:
        """Load investigator session cookies. Returns count accepted."""
        if self._ctx is None:
            self.launch()
        assert self._ctx is not None
        now = int(time.time())
        norm = []
        for c in cookies or []:
            try:
                exp = c.get("expirationDate") or c.get("expires")
                norm.append({"name": c["name"], "value": str(c["value"]),
                             "domain": c.get("domain") or self._default_domain() or ".x.com",
                             "path": c.get("path", "/"),
                             "secure": bool(c.get("secure", True)),
                             "httpOnly": bool(c.get("httpOnly", False)),
                             "sameSite": {"no_restriction": "None", "lax": "Lax",
                                          "strict": "Strict"}.get(
                                              str(c.get("sameSite") or "Lax"), "Lax"),
                             "expires": int(float(exp)) if exp else now + 86400 * 365})
            except Exception:
                continue
        if norm:
            self._ctx.add_cookies(norm)
        return len(norm)

    def save_storage(self):
        try:
            if self._ctx is not None:
                self._ctx.storage_state(path=self._state_path())
                os.chmod(self._state_path(), stat.S_IRUSR | stat.S_IWUSR)
        except Exception:
            pass

    def open(self, url: str):
        assert self._page is not None
        self._page.goto(url, wait_until="domcontentloaded", timeout=45000)

    def wait_for_selector(self, selector: str, timeout: int = 20000) -> bool:
        """Wait for real content instead of a blind sleep. Returns True if found."""
        assert self._page is not None
        try:
            self._page.wait_for_selector(selector, timeout=timeout, state="attached")
            return True
        except Exception:
            return False

    def fetch_bytes(self, url: str, timeout: int = 30000) -> Optional[bytes]:
        """Download a resource using this context's session (cookies + UA).

        Needed for off-page media such as fbcdn/cdninstagram images: a plain
        request without the session's headers is often rejected.
        """
        if self._ctx is None:
            return None
        try:
            r = self._ctx.request.get(url, timeout=timeout)
            if not r.ok:
                return None
            return r.body()
        except Exception:
            return None

    def scroll_settle(self, rounds: int = 4, pause: float = 1.6) -> None:
        """Trigger lazy-loaded feeds, then let the SPA paint."""
        import time as _t
        for _ in range(rounds):
            try:
                self._page.mouse.wheel(0, 2200)
            except Exception:
                try:
                    self.eval("window.scrollBy(0,2000)")
                except Exception:
                    break
            _t.sleep(pause)

    def snapshot(self) -> list:
        return []

    def fill(self, ref: str, text: str):
        assert self._page is not None
        self._page.fill(ref, text, timeout=15000)

    def click(self, ref: str):
        assert self._page is not None
        self._page.click(ref, timeout=15000)

    def press(self, key: str):
        assert self._page is not None
        self._page.keyboard.press(key)

    def eval(self, js: str) -> str:
        assert self._page is not None
        self._last_eval_error = ""
        try:
            v = self._page.evaluate(js)
            if isinstance(v, str):
                return v
            # Keep falsy scalars (0/false/empty array) meaningful instead of
            # collapsing them into an empty string.
            return json.dumps(v)
        except Exception as e:
            # A JS syntax/reference error used to be swallowed here, so a broken
            # extractor looked exactly like a page with no posts.
            self._last_eval_error = f"{type(e).__name__}: {str(e)[:200]}"
            return ""

    def current_url(self) -> str:
        try:
            return self._page.url if self._page else ""
        except Exception:
            return ""

    def screenshot(self) -> Optional[bytes]:
        try:
            return self._page.screenshot(timeout=20000) if self._page else None
        except Exception:
            return None

    def extract(self, url: str) -> PageData:
        nav_hints = AgentBrowserCliDriver._NAV_EXACT
        content_hints = AgentBrowserCliDriver._CONTENT_HINTS
        self.open(url)
        import time as _t
        for _ in range(6):
            try:
                cur = self.current_url()
            except Exception:
                cur = ""
            if cur.split("?")[0].rstrip("/") == url.split("?")[0].rstrip("/"):
                break
            _t.sleep(2)
        for _ in range(4):
            try:
                self.eval("window.scrollTo(0, document.body.scrollHeight)")
            except Exception:
                pass
            _t.sleep(2)
        title = _clean_eval_output(self.eval("document.title"))
        text = _clean_eval_output(self.eval("document.body.innerText.slice(0,15000)"))
        html = _clean_eval_output(self.eval("document.documentElement.outerHTML.slice(0,800000)"))
        author = _clean_eval_output(self.eval(
            "(() => { const a = document.querySelector('[rel=author]'); "
            "if (a && a.innerText.trim()) return a.innerText.trim(); "
            "const t = document.title || ''; "
            "let m = t.match(/^(.+?)\\s+on\\s+X:/); "
            "if (m) return m[1].trim(); "
            "const bt = document.body.innerText||''; "
            "let h = bt.match(/@([A-Za-z0-9_]{2,15})\\s*\\n?\\s*[·•]/); "
            "if (h) return h[1]; "
            "const b = bt.match(/@([A-Za-z0-9_]{2,15})/); "
            "return b ? b[1] : ''; })()"))
        pub = _clean_eval_output(self.eval(
            "document.querySelector('time')?.getAttribute('datetime')||''"))
        raw_links = _clean_eval_output(self.eval(
            "Array.from(document.querySelectorAll('a[href]')).map(a=>a.href).slice(0,150).join('\\n')"))
        links = []
        deferred = []
        for l in raw_links.splitlines():
            l = l.strip()
            if not l.startswith("http"):
                continue
            try:
                from urllib.parse import urlsplit
                parts = urlsplit(l)
                seg = (parts.path or "/").rstrip("/") or "/"
                if seg in AgentBrowserCliDriver._NAV_EXACT:
                    continue
                if "notif_" in parts.query or "checkpoint" in seg or "/search/" in seg:
                    continue
            except Exception:
                pass
            if l not in links:
                (links if any(h in l for h in AgentBrowserCliDriver._CONTENT_HINTS)
                 else deferred).append(l)
        links = links + [d for d in deferred if d not in links]
        links = links + [d for d in deferred if d not in links]
        return PageData(url=self.current_url() or url, title=title, text=text, html=html,
                        author=author, published_at=pub or None, links=links,
                        screenshot=self.screenshot())

    def extract_social(self, url: str, platform: str, listing: bool = True) -> dict:
        """Platform-aware capture. Returns posts + page-level capture artifacts.

        Unlike extract(), this NEVER uses document.body.innerText as post text.
        """
        from app.services.collectors import social_dom as S
        import time as _t
        self.ensure_launched()
        self.open(url)
        ready = self.wait_for_selector(S.CONTENT_READY.get(platform, "body"), 25000)
        _t.sleep(3)
        dismissed: list = []
        if platform == "x":
            try:
                dismissed = json.loads(self.eval(S.X_DISMISS_JS) or "[]")
            except Exception:
                dismissed = []
            _t.sleep(1)
        if listing:
            self.scroll_settle()
            _t.sleep(2)
        posts = [S.normalize_post(p) for p in
                 S.parse_extraction(self.eval(S.EXTRACTORS.get(platform, "[]")))]
        posts = [p for p in posts if p]
        # Dedupe by permalink so a single post captured twice is one record.
        uniq, seen = [], set()
        for p in posts:
            k = p["permalink"] or (p["handle"], p["text"][:80])
            if k in seen:
                continue
            seen.add(k)
            uniq.append(p)
        return {"posts": uniq, "ready": ready, "dismissed_overlays": dismissed,
                "eval_error": getattr(self, "_last_eval_error", ""),
                "url": self.current_url() or url, "title": _clean_eval_output(self.eval("document.title")),
                "text": _clean_eval_output(self.eval("document.body.innerText.slice(0,15000)")),
                "html": _clean_eval_output(
                    self.eval("document.documentElement.outerHTML.slice(0,800000)")),
                "screenshot": self.screenshot()}

    def close(self):
        try:
            if self._browser is not None:
                self._browser.close()
        except Exception:
            pass
        try:
            if self._pw is not None:
                self._pw.stop()
        except Exception:
            pass
        self._browser = self._ctx = self._page = self._pw = None


class FakeDriver(BaseBrowserDriver):
    """Scripted driver for tests. pages: {url: PageData|dict}. login_script: list of statuses."""
    name = "fake"

    def __init__(self, pages: dict | None = None, login_outcome: str = SUCCESS):
        self.pages = pages or {}
        self.login_outcome = login_outcome
        self.calls: list = []
        self.logged_in = False
        self.login_calls = 0
        self.current_url = ""

    def open(self, url: str):
        self.calls.append(("open", url))
        self.current_url = url

    def snapshot(self): return []
    def fill(self, ref: str, text: str): self.calls.append(("fill", ref, "***"))
    def click(self, ref: str): self.calls.append(("click", ref))
    def press(self, key: str): self.calls.append(("press", key))
    def eval(self, js: str) -> str: return ""

    def do_login(self, username: str, password: str) -> str:
        self.login_calls += 1
        if self.login_outcome == SUCCESS:
            self.logged_in = True
        return self.login_outcome

    def extract(self, url: str) -> PageData:
        self.calls.append(("extract", url))
        self.current_url = url
        p = self.pages.get(url, {})
        if isinstance(p, dict):
            return PageData(url=url, **p)
        return p

    def logout(self):
        self.calls.append(("logout",))
        self.logged_in = False


# ---------- session orchestration ----------
class BrowserSession:
    def __init__(self, driver: BaseBrowserDriver, config: AuthConfig,
                 session_dir: str | None = None):
        if session_dir is None:
            session_dir = default_session_dir()
        self.driver = driver
        self.config = config
        self.session_dir = session_dir
        self.session_reused = False

    def login(self) -> dict:
        """Returns {status, reason}. Password is passed to the driver ONLY, never logged."""
        if load_session_marker(self.session_dir, self.config.session_name):
            self.session_reused = True
            return {"status": SUCCESS, "reason": "session_reused"}
        if self.config.login_url:
            self.driver.ensure_launched()
            self.driver.open(self.config.login_url)
        if isinstance(self.driver, FakeDriver):
            st = self.driver.do_login(self.config.username, "***redacted***")
        else:
            st = self._interactive_login()
        if st == SUCCESS:
            save_session_marker(self.session_dir, self.config.session_name,
                                {"platform": self.config.platform})
            self.session_reused = False
        return {"status": st,
                "reason": "fresh_login" if st == SUCCESS else (
                    getattr(self.driver, "last_login_reason", "") or "login_failed")}

    def _interactive_login(self) -> str:
        """Vault-backed login for the real CLI driver; Playwright form login for
        the subprocess driver; otherwise pause for manual action."""
        drv = self.driver
        if isinstance(drv, AgentBrowserCliDriver) and self.config.username and self.config.login_url:
            if not drv.ensure_profile(self.config.username, self.config.password,
                                      self.config.login_url):
                return ERROR
            res = drv.login_flow(self.config.login_url)
            return res.get("status", ERROR)
        if isinstance(drv, PlaywrightDriver) and self.config.username and self.config.password \
                and self.config.login_url:
            st = _playwright_form_login(drv, self.config, self.session_dir)
            return st
        # Unknown driver or missing fields: do NOT guess — pause for the investigator.
        return AUTHENTICATION_ACTION_REQUIRED

    def logout(self) -> dict:
        try:
            self.driver.logout() if hasattr(self.driver, "logout") else None
        finally:
            clear_session_marker(self.session_dir, self.config.session_name)
        return {"status": SUCCESS, "reason": "logged_out"}


# ---------- collector ----------
def _env(name: str) -> str:
    """Read one env value (process env first, then app settings)."""
    v = os.getenv(name, "")
    if not v:
        try:
            from app.core.config import settings
            v = getattr(settings, name, "") or ""
        except Exception:
            v = ""
    return v or ""


def _cookies_from_env(var: str) -> list:
    raw = os.getenv(var, "")
    if not raw:
        try:
            from app.core.config import settings
            raw = getattr(settings, var, "") or ""
        except Exception:
            raw = ""
    try:
        data = json.loads(raw or "[]")
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _verify_persisted_session(task: dict, payload: dict, platform: str) -> bool:
    """Re-open the saved storage_state in a fresh worker and require a real
    signed-in page. Guards against a handoff that looked complete but wasn't."""
    worker = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "playwright_worker.py")
    check = {
        "platform": platform,
        "env_prefix": task.get("env_prefix", platform),
        "session": task.get("session"),
        "mode": "session_probe",
        "headless": True,
        "verify_url": task.get("verify_url") or task.get("login_url", ""),
        "session_dir": payload.get("session_dir", default_session_dir()),
    }
    try:
        proc = subprocess.run([sys.executable, worker], input=json.dumps(check),
                              capture_output=True, text=True, timeout=180)
    except Exception:
        return False
    for ln in reversed((proc.stdout or "").splitlines()):
        if ln.strip().startswith("{"):
            try:
                return json.loads(ln).get("status") == SUCCESS
            except Exception:
                return False
    return False


def run_playwright_task(task: dict, timeout: int = 600) -> dict:
    """Run a Playwright collection in an isolated subprocess (no asyncio-loop
    conflicts). Returns collect()-shaped dict with SourceRecord objects."""
    import base64 as _b64
    from datetime import datetime as _dt
    platform = task.get("platform", "web")
    cfg = AuthConfig.from_env(task.get("env_prefix", platform),
                              platform=platform, login_url=task.get("login_url", ""))
    if task.get("session"):
        cfg.session_name = task["session"]
    has_session = load_session_marker(default_session_dir(), cfg.session_name) is not None
    if not cfg.is_configured and not (task.get("cookies_env") and _cookies_from_env(task["cookies_env"])) \
            and not has_session:
        return {"status": AUTHENTICATION_REQUIRED,
                "reason_code": "adapter_disabled_no_credentials",
                "records": [], "errors": ["authenticated adapter disabled: no credentials configured"]}
    worker = os.path.join(os.path.dirname(os.path.abspath(__file__)), "playwright_worker.py")
    payload = dict(task)
    payload["session_dir"] = default_session_dir()
    try:
        proc = subprocess.run([sys.executable, worker], input=json.dumps(payload),
                              capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"status": ERROR, "reason_code": "worker_timeout", "records": [],
                "errors": ["playwright worker timed out"]}
    except Exception as e:
        return {"status": ERROR, "reason_code": "worker_spawn_failed",
                "records": [], "errors": [redact_for_log(str(e))[:150]]}
    lines = [ln for ln in (proc.stdout or "").splitlines() if ln.strip().startswith("{")]
    if not lines:
        return {"status": ERROR, "reason_code": "worker_no_output", "records": [],
                "errors": [(proc.stderr or "")[-300:]]}
    try:
        res = json.loads(lines[-1])
    except Exception:
        return {"status": ERROR, "reason_code": "worker_bad_output", "records": [],
                "errors": ["unparseable worker output"]}
    # A handoff only counts if the SAVED state actually authenticates. Re-open it
    # in a fresh process and require a real signed-in page, otherwise drop the
    # marker so later runs do not trust a logged-out session.
    if res.get("reason_code") == "manual_login_ok" and not task.get("skip_verify"):
        if not _verify_persisted_session(task, payload, platform):
            try:
                clear_session_marker(default_session_dir(), cfg.session_name)
            except Exception:
                pass
            res["status"] = AUTHENTICATION_REQUIRED
            res["reason_code"] = "saved_session_did_not_authenticate"
            res["errors"] = ["The login was not completed. Re-run and finish every step "
                             "(captcha and any emailed/app code) before the window closes."]
            res["records"] = []
    recs = []
    for r in res.get("records", []):
        shot = None
        if r.get("screenshot_b64"):
            try:
                shot = _b64.b64decode(r["screenshot_b64"])
            except Exception:
                shot = None
        img = None
        if r.get("image_b64"):
            try:
                img = _b64.b64decode(r["image_b64"])
            except Exception:
                img = None
        pub = r.get("published_at") or None
        recs.append(SourceRecord(
            platform=r.get("platform", platform),
            account_username=r.get("account_username", "unknown"),
            account_display=r.get("account_display", ""),
            profile_url=r.get("profile_url", ""),
            source_url=r.get("source_url", ""), text=r.get("text", ""),
            title=r.get("title", ""), published_at=_parse_dt(pub),
            raw_html=r.get("raw_html", ""),
            engagement=r.get("engagement") or {},
            media_refs=r.get("media_refs") or [],
            screenshot_bytes=shot,
            image_bytes=img,
            provenance=r.get("provenance") or {
                "collection_method": "authenticated_browser",
                "access": "investigator_owned_account",
                "independent": True,
                "session_reused": res.get("session_reused", False)}))
        if r.get("provenance"):
            recs[-1].provenance["session_reused"] = res.get("session_reused", False)
    res["records"] = recs
    return res


def _parse_dt(s):
    if not s:
        return None
    try:
        from dateutil import parser
        return parser.parse(str(s))
    except Exception:
        return None


def _playwright_form_login(driver: "PlaywrightDriver", cfg: AuthConfig,
                            session_dir: str) -> str:
    """Fill the investigator's OWN login form. Detects challenge -> stop -> report.
    Never bypasses MFA/CAPTCHA and never logs the password."""
    import time as _t
    user_sel = ("#email, input[name='email'], input[name='username'], "
                "input[name='user'], input[type='text']")
    pass_sel = ("#pass, input[name='pass'], input[name='password'], "
                "input[type='password']")
    try:
        driver.ensure_launched()
        driver.open(cfg.login_url)
        # The login page is an SPA: wait for the actual form instead of sleeping.
        # A fixed sleep left Instagram rendering a blank page and every fill failed.
        if not driver.wait_for_selector(f"{user_sel}, {pass_sel}", 30000):
            driver.last_login_reason = "login_form_never_rendered"
            _login_debug_shot(driver, session_dir, cfg, "login_form_missing")
            return AUTHENTICATION_ACTION_REQUIRED
        _t.sleep(1)
        for sel, val in ((user_sel, cfg.username), (pass_sel, cfg.password)):
            if not val:
                continue
            try:
                driver.fill(sel, val)
            except Exception:
                try:
                    driver.eval(
                        "(() => { const e = document.querySelector('%s');"
                        "if (e) { e.focus(); e.value = %s; "
                        "e.dispatchEvent(new Event('input',{bubbles:true})); } })()"
                        % (sel.split(",")[0].strip(), json.dumps(val)))
                except Exception:
                    return ERROR
        for sel in ("button[type='submit']", "div[role='button']",
                    "input[type='submit']"):
            try:
                driver.click(sel)
                break
            except Exception:
                continue
        else:
            try:
                driver.press("Enter")
            except Exception:
                return ERROR
        _t.sleep(8)
        # One extra submit for FB/IG multi-step (e.g. "Log in" confirm page).
        try:
            driver.click("div[aria-label='Log in']")
        except Exception:
            pass
        _t.sleep(6)
        url = driver.current_url()
        title = driver.eval("document.title")
        text = driver.eval("document.body.innerText.slice(0,4000)")
        st = classify_page(url, title, text)
        _login_debug_shot(driver, session_dir, cfg, f"login_{st.lower()}")
        if st != SUCCESS:
            driver.last_login_reason = f"challenge_after_submit: {st}"
            return st
        logged_in = bool(driver.eval(
            "(() => { const q=(s)=>document.querySelector(s); "
            "return String(!!(q('[data-testid=\"SideNav_AccountSwitcher_Button\"]')"
            "|| q('[aria-label=\"Your profile\"]') || q('#email')===null"
            "|| q('[data-testid=\"facebook\"]') || q('#f0Mt')"
            "|| (document.body.innerText||'').length>0 && "
            "!/log in|log into|sign up/i.test((document.body.innerText||'').slice(0,600)))); })()"
        )) == "True"
        if not logged_in:
            driver.last_login_reason = (
                "credentials_not_accepted: form submitted but still on login screen "
                f"(url={redact_for_log(url)[:90]})")
            _login_debug_shot(driver, session_dir, cfg, "login_not_authenticated")
            return AUTHENTICATION_REQUIRED
        driver.save_storage()
        save_session_marker(session_dir, cfg.session_name, {"platform": cfg.platform})
        driver.last_login_reason = "form_login_ok"
        return SUCCESS
    except Exception:
        _login_debug_shot(driver, session_dir, cfg, "login_exception")
        return ERROR


def _logged_in_probe(driver: "PlaywrightDriver", platform: str = "") -> bool:
    """True only on positive evidence of a signed-in surface.

    Checking merely for the absence of a password field is not enough: a wrong
    one-time code or a rejected login shows an error on a non-login URL with no
    password box, which previously read as a captured session.
    """
    plat = (platform or getattr(driver, "platform", "") or "").lower()
    marker = {
        "facebook": ('!!(document.querySelector(\'[aria-label="Your profile"]\''
                     ', [aria-label="Account controls and settings"]'
                     ', [aria-label="Create a post"], [role="feed"]\''
                     ', [data-testid="SideNav_AccountSwitcher_Button"]))'),
        "instagram": ('!!(document.querySelector(\'svg[aria-label="Home"]\''
                      ', svg[aria-label="Settings"], svg[aria-label="Messages"]\''
                      ', nav a[href$="/account/"]))'),
    }.get(plat, "")
    try:
        return driver.eval(
            "(() => { const u = (location.pathname + location.href).toLowerCase();"
            "if (/\\/login|\\/accounts\\/login|\\/checkpoint|\\/signin/.test(u)) return 'False';"
            "const b = (document.body.innerText || '').slice(0, 2000).toLowerCase();"
            "if (/enter the code|verification code|complete a challenge to verify|"
            "solve a puzzle|log in to continue|your password|captcha|incorrect|"
            "try again|isn.t right|wasn.t right|code you entered/.test(b)) return 'False';"
            "if (document.querySelector('#email, input[name=\"password\"]')) return 'False';"
            + (f"if (!{marker}) return 'False';" if marker else "") +
            "return 'True'; })()"
        ) == "True"
    except Exception:
        return False


def _manual_login_handoff(driver: "PlaywrightDriver", cfg: AuthConfig, session_dir: str,
                          task: dict) -> str:
    """Open a VISIBLE browser and let the investigator finish the login themselves.

    This exists for challenges that must never be automated: an image/Arkose
    puzzle, an emailed one-time code, an authenticator prompt, MFA approval. The
    tool never solves or guesses any of them -- it just holds the window open,
    detects that the investigator finished, and persists the resulting session so
    later collections reuse it silently.

    An investigator-supplied one-time code may be pre-filled when the platform
    asks for it ({P}_VERIFICATION_CODE). The code is never logged or stored.
    """
    import time as _t
    code = (task.get("verification_code")
            or _env(f"{(cfg.platform or '').upper()}_VERIFICATION_CODE"))
    try:
        driver.ensure_launched()
        driver.open(cfg.login_url or task.get("verify_url", ""))
        sys.stderr.write(
            f"[{cfg.platform}] Complete the login in the visible Chrome window "
            f"(captcha / emailed code / 2FA). Waiting up to "
            f"{int(task.get('manual_timeout', 420))}s...\n")
        sys.stderr.flush()
        timeout = min(int(task.get("manual_timeout", 420)), 1800)
        deadline = _t.time() + timeout
        code_used = False
        while _t.time() < deadline:
            _t.sleep(4)
            if _logged_in_probe(driver, cfg.platform):
                driver.save_storage()
                save_session_marker(session_dir, cfg.session_name,
                                    {"platform": cfg.platform, "method": "manual_handoff"})
                sys.stderr.write(f"[{cfg.platform}] Login captured.\n")
                return SUCCESS
            # Pre-fill an emailed/app code exactly once, only if the code field
            # is actually on screen. Never guessed, never retried blindly.
            if code and not code_used:
                try:
                    if driver.eval(
                        "(() => { const e = document.querySelector("
                        "'input[name=\"security_code\"], input[name=\"otp\"], "
                        "input[autocomplete=\"one-time-code\"]');"
                        "return e ? 'True' : 'False'; })()"
                    ) == "True":
                        driver.fill('input[name="security_code"], input[name="otp"], '
                                    'input[autocomplete="one-time-code"]', code)
                        for sel in ("button[type='submit']", "div[role='button']"):
                            try:
                                driver.click(sel)
                                break
                            except Exception:
                                continue
                        code_used = True
                        sys.stderr.write(f"[{cfg.platform}] One-time code entered.\n")
                except Exception:
                    pass
        sys.stderr.write(f"[{cfg.platform}] Timed out waiting for manual login.\n")
        return AUTHENTICATION_REQUIRED
    except Exception:
        return ERROR


def _login_debug_shot(driver: "PlaywrightDriver", session_dir: str, cfg: AuthConfig,
                      tag: str) -> None:
    """Local-only 0600 diagnostic for the investigator. No secrets, no case data."""
    try:
        d = os.path.join(session_dir, "login_debug")
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, f"{cfg.platform or 'web'}_{tag}.png")
        shot = driver.screenshot()
        if shot:
            with open(p, "wb") as f:
                f.write(shot)
            os.chmod(p, stat.S_IRUSR | stat.S_IWUSR)
    except Exception:
        pass


def _playwright_cookie_login(driver: "PlaywrightDriver", cfg: AuthConfig, task: dict,
                             session_dir: str) -> dict:
    """Cookie-session login: reuse storage_state, else import env cookies, verify.
    Any challenge -> *_REQUIRED. Never fabricates a session."""
    verify_url = task.get("verify_url", task.get("login_url", ""))
    state_path = driver._state_path()
    marker = load_session_marker(session_dir, cfg.session_name)
    if marker and os.path.isfile(state_path):
        try:
            driver.launch(storage_state=state_path)
            if verify_url:
                driver.open(verify_url)
                import time as _t
                _t.sleep(6)
            url = driver.current_url()
            title = driver.eval("document.title")
            text = driver.eval("document.body.innerText.slice(0,4000)")
            st = classify_page(url, title, text)
            if st == SUCCESS:
                driver.session_reused = True
                return {"status": SUCCESS, "reason": "session_reused"}
        except Exception as e:
            return {"status": ERROR, "reason": f"reuse_failed: {redact_for_log(str(e))[:100]}"}
        # reuse failed verification -> fall through to fresh import
    cookies = _cookies_from_env(task.get("cookies_env", ""))
    if not cookies:
        return {"status": AUTHENTICATION_REQUIRED,
                "reason": "no_cookies_configured",
                "note": "Set cookies env JSON or username/password."}
    try:
        driver.launch()
    except Exception as e:
        return {"status": ERROR, "reason": f"browser_launch_failed: {redact_for_log(str(e))[:100]}"}
    n = driver.import_cookies(cookies)
    if not n:
        return {"status": ERROR, "reason": "no_cookies_accepted"}
    try:
        if verify_url:
            driver.open(verify_url)
            import time as _t
            _t.sleep(8)
        url = driver.current_url()
        title = driver.eval("document.title")
        text = driver.eval("document.body.innerText.slice(0,4000)")
        st = classify_page(url, title, text)
        if st != SUCCESS:
            return {"status": st, "reason": "post_cookie_challenge",
                    "url": url, "title": title[:120]}
        driver.save_storage()
        save_session_marker(session_dir, cfg.session_name, {"platform": cfg.platform})
        driver.session_reused = False
        return {"status": SUCCESS, "reason": "cookie_login_ok"}
    except Exception as e:
        return {"status": ERROR, "reason": f"verify_failed: {redact_for_log(str(e))[:100]}"}


class AuthenticatedBrowserCollector:
    """Optional adapter. Disabled (AUTHENTICATION_REQUIRED/disabled) without credentials."""

    def __init__(self, driver_factory: Callable[[str], BaseBrowserDriver] | None = None,
                 session_dir: str | None = None):
        if session_dir is None:
            session_dir = default_session_dir()
        self.driver_factory = driver_factory
        self.session_dir = session_dir

    def collect(self, task: dict, case_keywords: list | None = None) -> dict:
        platform = task.get("platform", "web")
        cfg = AuthConfig.from_env(task.get("env_prefix", platform),
                                  platform=platform, login_url=task.get("login_url", ""))
        if task.get("session"):
            cfg.session_name = task["session"]
        # Saved authenticated session counts as authorization: reuse needs no creds.
        has_session = load_session_marker(self.session_dir, cfg.session_name) is not None
        cookie_mode = bool(task.get("cookies_env") and _cookies_from_env(task["cookies_env"]))
        if not cfg.is_configured and not cookie_mode and not has_session:
            return {"status": AUTHENTICATION_REQUIRED,
                    "reason_code": "adapter_disabled_no_credentials",
                    "records": [], "errors": ["authenticated adapter disabled: no credentials configured"],
                    "note": "Configure {P}_USERNAME/{P}_PASSWORD (or cookies env) or use public/RSS/manual sources.".format(
                        P=(task.get('env_prefix', platform) or '').upper())}
        factory = self.driver_factory or (lambda name: AgentBrowserCliDriver(session=name))
        driver = factory(cfg.session_name)
        session = BrowserSession(driver, cfg, self.session_dir)
        try:
            if isinstance(driver, PlaywrightDriver) and (
                    task.get("cookies_env") or
                    load_session_marker(self.session_dir, cfg.session_name)):
                login = _playwright_cookie_login(driver, cfg, task, self.session_dir)
                session.session_reused = (login.get("reason") == "session_reused")
            else:
                login = session.login()
            if login["status"] != SUCCESS:
                if login["status"] in (MFA_REQUIRED, CAPTCHA_REQUIRED):
                    return {"status": login["status"], "reason_code": "manual_action_pause",
                            "records": [], "errors": [AUTHENTICATION_ACTION_REQUIRED],
                            "note": "Investigator must complete the check manually, then re-run."}
                return {"status": login["status"], "reason_code": login.get("reason", ""),
                        "records": [], "errors": [login.get("reason", "login failed")]}
            mode = task.get("mode", "collect_urls")
            if mode == "login_test":
                return {"status": SUCCESS, "reason_code": "login_ok",
                        "records": [], "errors": [],
                        "session_reused": session.session_reused}
            urls: list[str] = []
            if mode == "search":
                surl = task.get("search_url", "")
                if not surl:
                    return {"status": ERROR, "reason_code": "missing_search_url",
                            "records": [], "errors": ["search mode needs search_url"]}
                page = driver.extract(surl) if hasattr(driver, "extract") else None
                if page is None:
                    return {"status": ERROR, "reason_code": "driver_no_extract",
                            "records": [], "errors": ["driver cannot extract"]}
                st = classify_page(page.url, page.title, page.text, page.status_code)
                if st != SUCCESS:
                    return {"status": st, "reason_code": "search_page_challenge",
                            "records": [], "errors": [f"search halted: {st}"]}
                urls = [l for l in (page.links or [])[:task.get("max_items", 10)]]
                search_ctx = {"search_query": task.get("search_query", ""),
                              "search_url": surl, "search_time": datetime.now(timezone.utc).isoformat()}
            else:
                urls = task.get("urls", [])[:task.get("max_items", 20)]
                search_ctx = {}
            records, errors, partial = [], [], False
            for u in urls:
                try:
                    page = driver.extract(u)
                    st = classify_page(page.url, page.title, page.text, page.status_code)
                    if st != SUCCESS:
                        # Structured failure only — NEVER becomes contradictory evidence (spec).
                        errors.append(f"{u} -> {st}")
                        if st in (ACCESS_DENIED, RATE_LIMITED, BLOCKED):
                            partial = True
                            break
                        partial = True
                        continue
                    records.append(SourceRecord(
                        platform=platform,
                        account_username=page.author or f"{platform}_account",
                        source_url=page.url,  # COMPLETE original URL, never truncated
                        text=page.text or "", title=page.title or "",
                        published_at=_parse_dt(page.published_at),
                        raw_html=page.html or "",
                        engagement={},
                        screenshot_bytes=page.screenshot,  # real file bytes or None (never faked)
                        provenance={"collection_method": "authenticated_browser",
                                    "access": "investigator_owned_account",
                                    "independent": True,
                                    "session_reused": session.session_reused,
                                    "snapshot_chars": len(page.html or ""),
                                    "snapshot_truncated": len(page.html or "") >= 799000,
                                    **search_ctx}))
                except Exception as e:
                    errors.append(f"{u} -> ERROR")
                    partial = True
            # attach screenshots collected by driver (real files, not claims of screenshots)
            return {"status": PARTIAL if partial and records else (SUCCESS if records else ERROR),
                    "reason_code": "ok" if records else "no_records",
                    "records": records, "errors": errors,
                    "session_reused": session.session_reused}
        finally:
            try:
                driver.close()
            except Exception:
                pass
