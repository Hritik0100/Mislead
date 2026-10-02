<p align="center">
  <b>OSINT Misleading-News Platform</b><br>
  <i>Evidence-first investigation system for tracking, verifying and reporting on coordinated misinformation</i>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3670A0?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white" alt="PostgreSQL">
  <img src="https://img.shields.io/badge/SQLAlchemy-D71F00?style=for-the-badge&logo=sqlalchemy&logoColor=white" alt="SQLAlchemy">
  <img src="https://img.shields.io/badge/Redis-DC382D?style=for-the-badge&logo=redis&logoColor=white" alt="Redis">
  <img src="https://img.shields.io/badge/Groq-F55036?style=for-the-badge&logo=groq&logoColor=white" alt="Groq">
  <img src="https://img.shields.io/badge/Next.js-000000?style=for-the-badge&logo=next.js&logoColor=white" alt="Next.js">
  <img src="https://img.shields.io/badge/React-61DAFB?style=for-the-badge&logo=react&logoColor=black" alt="React">
  <img src="https://img.shields.io/badge/TypeScript-3178C6?style=for-the-badge&logo=typescript&logoColor=white" alt="TypeScript">
  <img src="https://img.shields.io/badge/Tailwind_CSS-06B6D4?style=for-the-badge&logo=tailwindcss&logoColor=white" alt="Tailwind CSS">
  <img src="https://img.shields.io/badge/Telethon-2AABEE?style=for-the-badge&logo=telegram&logoColor=white" alt="Telethon">
  <img src="https://img.shields.io/badge/Playwright-2EAD33?style=for-the-badge&logo=playwright&logoColor=white" alt="Playwright">
  <img src="https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker">
</p>

<p align="center">
  <a href="#-platforms--access">Platforms</a> •
  <a href="#-key-features">Features</a> •
  <a href="#-investigation-pipeline">Pipeline</a> •
  <a href="#-quick-start">Quick Start</a> •
  <a href="#-api-reference">API</a> •
  <a href="#-project-structure">Structure</a>
</p>

---

## 📐 Architecture

<details>
<summary><b>Click to expand full system diagram</b></summary>

<br>

<p align="center">
  <img src="architecture/architecture-diagram.png" alt="OSINT Misleading-News Platform — system architecture" width="420">
</p>

</details>

---

## 📖 Overview

**OSINT Misleading-News Platform** is an evidence-first investigation system for analysing public and authorized content across social media, news/RSS and messaging platforms.

Raw posts and media are turned into **hash-verified evidence**, run through a staged LLM-assisted analysis, traced for spread, screened for coordination signals, and compiled into a final report with source links, evidence IDs, assessment labels and risk indicators.

> 🔍 **Evidence first, verdict second.** Every material conclusion links back to a stored, SHA-256 verified artifact. The LLM is a reasoning assistant — never the source of truth.

---

## 📱 Platforms & Access

> 🔐 All social and messaging platforms require an **authenticated session and a valid login**. Only investigator-owned accounts are permitted. No credential sharing, no bypass of platform security controls.

| Platform | Auth required | Session type | Status |
| :--- | :---: | --- | :---: |
| 💬 **Telegram** | ✅ Login + session | MTProto (Telethon) | ✅ Live |
| 𝕏 **X (Twitter)** | ✅ Login + session | Cookie / auth token | ✅ Live |
| 📸 **Instagram** | ✅ Login + session | Cookie / auth token | ✅ Live |
| 📘 **Facebook** | ✅ Login + session | Cookie / auth token | ✅ Live |
| 🧩 **Element / Matrix** | ✅ Login + session | Access token + homeserver | 🚧 In progress |
| 📲 **WhatsApp** | ✅ Login + session | Linked-device session | 🚧 In progress |
| 📰 **RSS / News** | ➖ None | Public feed | ✅ Live |
| 🕸️ **Public web** | ➖ None | Public HTML | ✅ Live |
| 📝 **Manual upload** | ➖ Analyst | Analyst-supplied | ✅ Live |

**Legend:** ✅ Live · 🚧 In progress

<details>
<summary><b>⚠️ Which source spec to use — read this before adding a source</b></summary>

X, Instagram and Facebook have **two** routes, and picking the wrong one silently
gives you a placeholder instead of real posts:

| Source spec | What you get |
| --- | --- |
| `{"type": "x", ...}` | 🚫 **Stub** — a placeholder post marked `needs_manual_evidence` |
| `{"type": "auth_browser", "platform": "x", ...}` | ✅ **Real** — logged-in Playwright + the platform's DOM extractor |

The same applies to `instagram` and `facebook`. **Always use `type: "auth_browser"`
with a `platform` field for these three.** Telegram is the exception: it uses
`type: "telegram"` because it is a MTProto client, not a browser.

A run that only ever produced `[stub]` records means the source was configured
with the wrong `type`.

</details>

<details>
<summary><b>💬 Setting up Telegram (real collector)</b></summary>

Telegram is collected over **MTProto with Telethon** — the official Telegram
client protocol, not scraping. It only ever reads what the investigator's own
account can legitimately see.

**1. Get app credentials** — <https://my.telegram.org> → *API development tools*.
You get an `api_id` and `api_hash`. This identifies your app, it is not user auth.

**2. Add them to `backend/.env`**

```bash
TELEGRAM_API_ID=123456
TELEGRAM_API_HASH=0123456789abcdef0123456789abcdef
TELEGRAM_PHONE=+919876543210        # E.164, only used by the login step
# TELEGRAM_2FA_PASSWORD=            # only if the account has 2FA enabled
```

**3. Create the session once, from your terminal**

```bash
cd backend
python -m app.services.collectors.telegram login
```

It asks for the login code (and 2FA password, if enabled) **on your TTY** and
writes a `0600` session file. That is the only place a secret is ever typed —
the collector itself never accepts a code or password.

**4. Collect**

Collections now reuse that session silently. Add the source to a case:

```json
{ "type": "telegram", "channel": "some_channel", "max_items": 50 }
{ "type": "telegram", "channel": "some_channel", "search": "election" }
```

Check status any time:

```bash
python -m app.services.collectors.telegram status
```

**What it will not do**

| Situation | Result |
| --- | --- |
| Private channel your account cannot see | `ACCESS_DENIED` — no invite guessing, no join |
| Rate limited (FloodWait) | `RATE_LIMITED` with the wait time — **no retry** |
| Session not authorized | `AUTHENTICATION_REQUIRED` + a pointer to `login` |
| No `api_id` / `api_hash` | adapter disabled, rest of the pipeline unaffected |
| Collection fails midway | recorded as an error — **never** as evidence |

Because it is async and writes a session file, collection runs in an isolated
subprocess, so it can never block or corrupt the API server's event loop.

</details>

<details>
<summary><b>🔐 Setting up X, Instagram and Facebook (real browser collector)</b></summary>

These three run through a **logged-in Playwright browser** using an
investigator-owned account, then extract posts with a per-platform DOM
extractor (`services/collectors/social_dom.py`). Nothing is scraped anonymously
and no access control is circumvented.

**1. Point Playwright at your real Chrome**

```bash
pip install playwright     # uses the system Chrome, no bundled download needed
```

**2. Provide a session** — either export cookies from your own browser, or let
the collector log in for you:

```bash
# backend/.env
X_COOKIES_JSON=         # JSON array exported from your own X session
INSTAGRAM_COOKIES_JSON=
FACEBOOK_COOKIES_JSON=

# ...or username/password login (one pair per platform prefix)
X_USERNAME=
X_PASSWORD=
X_LOGIN_URL=https://x.com/login
INSTAGRAM_USERNAME=
INSTAGRAM_PASSWORD=
```

**3. Add the source to a case**

```json
{ "type": "auth_browser", "platform": "x", "driver": "playwright",
  "cookies_env": "X_COOKIES_JSON", "mode": "search",
  "search_url": "https://x.com/search?q=election&f=live",
  "search_query": "election", "max_items": 20, "ocr": true }
```

```json
{ "type": "auth_browser", "platform": "instagram", "driver": "playwright",
  "cookies_env": "INSTAGRAM_COOKIES_JSON", "mode": "collect_urls",
  "urls": ["https://www.instagram.com/p/XXXX/"], "ocr": true }
```

```json
{ "type": "auth_browser", "platform": "facebook", "driver": "playwright",
  "cookies_env": "FACEBOOK_COOKIES_JSON", "mode": "collect_urls",
  "urls": ["https://www.facebook.com/page/posts/12345"], "ocr": true }
```

**Modes**

| `mode` | Does |
| --- | --- |
| `login_test` | Verifies the session only, collects nothing |
| `manual_login` | Opens a visible window; **you** finish the captcha / emailed code / MFA |
| `search` | Reads posts from a search or listing page you supply |
| `collect_urls` | Opens each URL in `urls` and reads that post |

Use `manual_login` when the platform challenges you — the tool will never solve
a captcha or guess a one-time code itself.

**OCR** — when a post is a poster, meme or screenshot, the claim lives in the
pixels. With `ocr: true` the image is read locally, the text is attached for
search, and the image itself is stored as evidence so you can verify exactly
what was read.

</details>

<details>
<summary><b>🔐 How browser sessions are provided (X / IG / FB / and others)</b></summary>

Sessions are exported from **your own** logged-in browser and supplied via
environment variables — never committed, never logged, never sent to the LLM.

```bash
# .env — one block per platform

# ── Cookies (JSON array exported from your own browser) ──
X_COOKIES_JSON=
INSTAGRAM_COOKIES_JSON=
FACEBOOK_COOKIES_JSON=

# ── Login credentials for authorized browser collection ──
# One pair per platform prefix, e.g. OUTLET_USERNAME / OUTLET_PASSWORD
PLATFORM_USERNAME=
PLATFORM_PASSWORD=
PLATFORM_LOGIN_URL=
```

Enforced restrictions — MFA/CAPTCHA ⇒ manual pause (**no bypass**) · rate limit
⇒ `RATE_LIMITED` · bot-wall ⇒ `BLOCKED`. A failed collection is **never**
recorded as evidence. Provenance is always tagged `authenticated_browser` +
`investigator_owned_account`.

</details>

---

## ✨ Key Features

### 🗂️ Case & Evidence Management
- **📁 Case scoping** — objective, keywords, platforms, time range per investigation
- **🔐 Hash-verified store** — every artifact stored with SHA-256, verifiable via `GET /api/evidence/{id}/verify`
- **🧾 Provenance** — account, username, platform, timestamp, post URL, source, media, engagement
- **📸 Media retention** — screenshots and attachments preserved where permitted, with optional OCR

### 🌐 Multi-Source Collection
- **📰 RSS / news** — live ingestion via `feedparser`
- **🕸️ Public web** — live, robots-respecting article fetcher
- **💬 Telegram** — **real MTProto client** (Telethon), session reuse, media download + OCR
- **𝕏 / 📸 / 📘 X, Instagram, Facebook** — **real logged-in Playwright** + per-platform DOM extractors, local OCR for memes and screenshots
- **📝 Manual upload** — analyst-supplied evidence when a connector is unavailable

### 🧠 Three-Layer Enrichment
- **Layer 1 — Pre-filter** — keyword/regex gate drops noise before any LLM spend
- **Layer 2 — Clean text** — BeautifulSoup + `lxml` strip boilerplate, nav and ads
- **Layer 3 — Groq JSON extraction** — structured, Pydantic-validated, deterministic mock fallback

### 🎯 Five-Key OSINT Analysis
| | Query | Purpose |
| :---: | --- | --- |
| **A** | Identify Fake News | scan for potentially misleading claims |
| **B** | Find Original Source | earliest post via chronology + similarity |
| **C** | Trace Spread | amplification graph with typed edges |
| **D** | Verify Claim | compare against primary/secondary evidence |
| **E** | Check Coordination | synchronized timing, repeated wording, shared URLs |

### ⚖️ Assessment & Reporting
- **🏷️ Five labels** — `True` · `False` · `Misleading` · `Context Missing` · `Unverified`
- **📊 Confidence separate** from the truth label, never conflated
- **↔️ Supporting vs contradicting** evidence shown side by side
- **🧑‍⚖️ Analyst override** — mandatory written rationale, fully audited
- **📄 Exports** — human-readable report + machine-readable JSON

### 🛡️ Safety by Design
- **🚦 Indicators, not accusations** — coordination output is explainable evidence for human review
- **🔑 Secrets never committed** — `.env`, cookie jars, DBs and evidence are git-ignored
- **🔒 Server-only LLM key** — `GROQ_API_KEY` never reaches the frontend bundle

---

## 🎬 Investigation Pipeline

```
P1 Objective  →  P2 Platforms  →  P3 Search  →  P4 Account ID  →  P5 A–E Queries  →  P6 Report
     │               │              │               │                │                │
  case scope    connectors     collectors     account set     5 analyses     evidence-
                                          + provenance    (fake, origin,   backed report
                                                            spread, verify,
                                                            coordination)
```

| Stage | What happens | Artifact |
| --- | --- | --- |
| **P1** Objective | Analyst sets objective, keywords, platforms, time window | Case record |
| **P2** Platforms | Connector registry resolves permitted sources + sessions | Source spec |
| **P3** Search | Collectors ingest posts, articles, channels, manual uploads | Raw content |
| **P4** Account ID | Accounts identified, deduplicated, linked to provenance | Account set |
| **P5** A–E | Fake-detect, origin, spread, verification, coordination | Findings |
| **P6** Report | Assessment engine merges evidence + model output | Final report |

---

## 🚀 Quick Start

### Prerequisites
- **Python 3.11+**
- **Node.js 18+** — only for the Next.js dashboard
- **PostgreSQL 14+** — production · SQLite works for zero-dependency local dev
- **Groq API key** — optional; without it a deterministic mock is used
- **Telegram `api_id` / `api_hash`** — only for the Telegram collector
- **Playwright** — `pip install playwright` for the X / Instagram / Facebook collector

### 1️⃣ Database

```bash
# Production — PostgreSQL
createdb osint
psql osint
```

```bash
# Local dev — zero dependencies, file-based
# (default DATABASE_URL already points here)
```

### 2️⃣ Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

```bash
# .env
DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/osint
REDIS_URL=redis://localhost:6379/0
GROQ_API_KEY=your_key_here
GROQ_MODEL=llama-3.3-70b-versatile
APP_SECRET_KEY=change-me
EVIDENCE_DIR=./data/evidence
```

```bash
uvicorn app.main:app --reload --port 8000
```

### 3️⃣ Open the app

| Surface | URL |
| --- | --- |
| 🖥️ Dashboard | http://localhost:8000/dashboard |
| 📚 API docs | http://localhost:8000/docs |
| 💚 Health | http://localhost:8000/health |

### 4️⃣ Frontend dashboard *(optional)*

```bash
cd frontend
npm install
npm run dev            # http://localhost:3000
```

### 5️⃣ Docker *(optional)*

```bash
docker compose up --build
```

---

## 📡 API Reference

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/api/cases` | Create a case |
| `GET` | `/api/cases` | List cases |
| `GET` | `/api/cases/{id}` | Case detail |
| `POST` | `/api/cases/{id}/collect` | Trigger collection run |
| `GET` | `/api/cases/{id}/evidence` | List evidence for a case |
| `GET` | `/api/evidence/{id}/view` | Fetch evidence content |
| `GET` | `/api/evidence/{id}/verify` | Verify SHA-256 integrity |
| `POST` | `/api/cases/{id}/keywords` | Add scope keywords |
| `GET` | `/api/cases/{id}/claims` | List extracted claims |
| `POST` | `/api/cases/{id}/claims` | Add a claim manually |
| `POST` | `/api/cases/{id}/analysis` | Run A–E analysis |
| `GET` | `/api/cases/{id}/findings` | Analysis findings |
| `GET` | `/api/cases/{id}/assessment` | Current assessment |
| `PATCH` | `/api/cases/{id}/assessment` | Analyst override (audited) |
| `GET` | `/api/cases/{id}/report` | Final report (JSON) |

---

## 📁 Project Structure

```
.
├── architecture/          # System diagram
├── backend/               # FastAPI + SQLAlchemy service
│   ├── app/
│   │   ├── api/           # Routes + dashboard UI
│   │   ├── core/          # Config, database, Groq client
│   │   ├── models/        # SQLAlchemy models
│   │   ├── prompts/       # LLM prompt contracts
│   │   ├── schemas/       # Pydantic contracts
│   │   ├── services/
│   │   │   ├── assessment/    # Label + confidence engine
│   │   │   ├── collectors/    # RSS, web, telegram (MTProto), auth_browser
│   │   │   │                  # (Playwright), manual + social DOM extractors
│   │   │   ├── enrichment/    # prefilter → clean → LLM extract
│   │   │   ├── evidence/      # Hash-verified artifact store
│   │   │   ├── ocr/           # Image text extraction
│   │   │   ├── osint/         # A–E analysis modules
│   │   │   └── reporting/     # Report generation
│   │   └── workers/       # Async job execution
│   ├── static/            # Dashboard HTML
│   └── tests/             # pytest suite
├── frontend/              # Next.js 14 case dashboard
│   └── src/app/cases/[id] # overview, claims, evidence, media,
│                         # timeline, propagation, coordination, report
├── infra/docker/          # Backend Dockerfile
├── docker-compose.yml
└── .env.example
```

---

## ⚙️ Environment Variables

| Variable | Required | Description |
| --- | :---: | --- |
| `DATABASE_URL` | ✅ | SQLAlchemy URL — `postgresql+psycopg://…` in prod, `sqlite:///…` locally |
| `APP_SECRET_KEY` | ✅ | App signing secret — change for any real deployment |
| `GROQ_API_KEY` | ➖ | Absent ⇒ deterministic mock enrichment |
| `GROQ_MODEL` | ➖ | Defaults to `llama-3.3-70b-versatile` |
| `EVIDENCE_DIR` | ➖ | Local S3-layout evidence root |
| `REDIS_URL` | ➖ | Queue-backed job mode |
| `S3_ENDPOINT` / `S3_BUCKET` | ➖ | Swap local evidence store for S3-compatible storage |
| `X_COOKIES_JSON` / `INSTAGRAM_COOKIES_JSON` / `FACEBOOK_COOKIES_JSON` | ➖ | Per-platform session cookies — see [Platforms](#-platforms--access) |
| `*_USERNAME` / `*_PASSWORD` | ➖ | Authorized browser login — never logged or sent to LLM |
| `TELEGRAM_API_ID` / `TELEGRAM_API_HASH` | ➖ | Telegram app credentials from my.telegram.org |
| `TELEGRAM_PHONE` | ➖ | E.164 number, only used by the one-time `login` command |
| `TELEGRAM_2FA_PASSWORD` | ➖ | 2FA password for `login` — as sensitive as a password |
| `TELEGRAM_SESSION` | ➖ | StringSession for CI/headless (no code entry possible) |

---

## 🧪 Testing

```bash
cd backend
source .venv/bin/activate
pytest -v
```

The Telegram suite runs fully offline — `FakeTelegramDriver` stands in for
Telethon, and a fake `api_hash` / phone / session string are asserted to never
appear in results, records, provenance, errors or the session marker.

---

## 🔐 Security Notes

- ✅ `.env`, cookie jars, `data/`, `*.db` and evidence artifacts are git-ignored
- ✅ `GROQ_API_KEY` is server-only and never exposed to the frontend
- ✅ Evidence integrity is verifiable end-to-end via SHA-256
- ✅ Analyst overrides require a rationale and are audited
- ⚠️ Change `APP_SECRET_KEY` before any non-local deployment
- ⚠️ Use authorized, investigator-owned accounts only — never third-party credentials
- ⚠️ Sessions are as sensitive as passwords — never commit or share them

---

## 📄 License

Released under the MIT License.

---

## 🤝 Contributing

Issues and pull requests are welcome. Please keep changes evidence-first: if a claim in a report cannot be traced to a stored artifact, it does not belong in the report.

---

<p align="center">Made with 🕵️ for evidence-first OSINT investigation</p>
