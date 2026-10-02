<p align="center">
  <img src="architecture/architecture-diagram.png" alt="OSINT Misleading-News Platform Architecture" width="820">
</p>

<p align="center">
  <b>OSINT Misleading-News Platform</b><br>
  <i>Evidence-first investigation system for tracking, verifying and reporting on coordinated misinformation</i>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3670A0?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/SQLAlchemy-2C3E50?style=for-the-badge&logo=sqlalchemy&logoColor=white" alt="SQLAlchemy">
  <img src="https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white" alt="SQLite">
  <img src="https://img.shields.io/badge/Groq-F55036?style=for-the-badge&logo=groq&logoColor=white" alt="Groq">
  <img src="https://img.shields.io/badge/Next.js-000000?style=for-the-badge&logo=next.js&logoColor=white" alt="Next.js">
  <img src="https://img.shields.io/badge/React-61DAFB?style=for-the-badge&logo=react&logoColor=black" alt="React">
  <img src="https://img.shields.io/badge/TypeScript-3178C6?style=for-the-badge&logo=typescript&logoColor=white" alt="TypeScript">
  <img src="https://img.shields.io/badge/Tailwind_CSS-06B6D4?style=for-the-badge&logo=tailwindcss&logoColor=white" alt="Tailwind CSS">
  <img src="https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker">
  <img src="https://img.shields.io/badge/Playwright-2EAD33?style=for-the-badge&logo=playwright&logoColor=white" alt="Playwright">
  <img src="https://img.shields.io/badge/Markdown-000000?style=for-the-badge&logo=markdown&logoColor=white" alt="Markdown">
</p>

<p align="center">
  <a href="#-overview">Overview</a> •
  <a href="#-key-features">Features</a> •
  <a href="#-investigation-pipeline">Pipeline</a> •
  <a href="#-quick-start">Quick Start</a> •
  <a href="#-api-reference">API</a> •
  <a href="#-project-structure">Structure</a>
</p>

---

## 📖 Overview

**OSINT Misleading-News Platform** is an evidence-first investigation system for analysing public and authorized content across social media, news/RSS and communication platforms.

It takes raw posts and media, turns them into **hash-verified evidence**, runs a staged LLM-assisted analysis, traces how a claim spread, surfaces coordination signals, and produces a final report with source links, evidence IDs, assessment labels and risk indicators.

> 🔍 **Evidence first, verdict second.** Every material conclusion in a report links back to a stored evidence artifact. The LLM is a reasoning assistant, never the source of truth.

---

## ✨ Key Features

### 🗂️ Case & Evidence Management
- **📁 Case scoping** — define objective, keywords, platforms, time range and collection scope per investigation
- **🔐 Hash-verified store** — every artifact stored with SHA-256, verifiable via API (`GET /api/evidence/{id}/verify`)
- **🧾 Provenance capture** — account, username, platform, timestamp, post URL, source, media and engagement data
- **📸 Media retention** — screenshots and attachments preserved where permitted, with optional OCR

### 🌐 Multi-Source Collection
- **📰 RSS / news** — real ingestion via `feedparser`
- **🕸️ Public web** — real, robots-respecting article fetcher
- **✈️ Telegram** — public channel/signal ingestion
- **🖥️ Authorized browser** — investigator-owned accounts only, via Playwright
- **📝 Manual upload** — analyst-supplied evidence when a connector is unavailable
- **🚫 Hard limits** — no paywall bypass, no auth circumvention, no private-group access

### 🧠 Three-Layer Enrichment
- **Layer 1 — Pre-filter** — cheap keyword/regex gate drops obvious noise before any LLM cost
- **Layer 2 — Clean text** — BeautifulSoup + `lxml` strip boilerplate, nav and ads
- **Layer 3 — Groq JSON extraction** — structured, Pydantic-validated output with deterministic mock fallback

### 🎯 Five-Key OSINT Analysis
- **A. Identify Fake News** — scan for potentially misleading claims
- **B. Find Original Source** — earliest/candidate originating post via chronology + similarity
- **C. Trace Spread** — amplification graph with typed edges between accounts and platforms
- **D. Verify Claim** — compare claim against retrieved primary/secondary evidence
- **E. Check Coordination** — synchronized posting, repeated wording, shared URLs, temporal patterns

### ⚖️ Assessment & Reporting
- **🏷️ Five labels** — `True` · `False` · `Misleading` · `Context Missing` · `Unverified`
- **📊 Confidence separated** from the truth label, never conflated with it
- **↔️ Supporting vs contradicting** evidence shown side by side
- **🧑‍⚖️ Analyst override** — requires a mandatory written rationale, fully audited
- **📄 Exports** — human-readable report and machine-readable JSON

### 🛡️ Safety by Design
- **🚦 Indicators, not accusations** — coordination output is a set of explainable factors for human review, never a verdict against a person or org
- **🔑 Secrets never committed** — `.env`, session cookie jars, SQLite DBs and evidence artifacts are git-ignored
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

| Stage | What happens | Key artifact |
| --- | --- | --- |
| **P1** Objective | Analyst sets objective, keywords, platforms, time window | Case record |
| **P2** Platforms | Connector registry resolves which sources are permitted | Source spec |
| **P3** Search | Collectors ingest posts, articles, channels, manual uploads | Raw content |
| **P4** Account ID | Accounts are identified, deduplicated and linked to provenance | Account set |
| **P5** A–E | Fake-detect, origin, spread, verification, coordination run | Findings |
| **P6** Report | Assessment engine merges evidence + model output | Final report |

---

## 🚀 Quick Start

### Prerequisites
- **Python 3.11+**
- **Node.js 18+** (only if you want the Next.js dashboard)
- **A Groq API key** — optional; without it a deterministic mock is used

### 1️⃣ Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                     # add GROQ_API_KEY for real LLM
uvicorn app.main:app --reload --port 8000
```

No Postgres or Redis required locally — SQLite + in-process jobs out of the box.

### 2️⃣ Open the app

| Surface | URL |
| --- | --- |
| 🖥️ Dashboard | http://localhost:8000/dashboard |
| 📚 API docs (Swagger) | http://localhost:8000/docs |
| 💚 Health check | http://localhost:8000/health |

### 3️⃣ Frontend dashboard (optional)

```bash
cd frontend
npm install
npm run dev            # http://localhost:3000
```

### 4️⃣ Docker (optional)

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
├── architecture/          # Architecture diagram
├── backend/               # FastAPI + SQLAlchemy service
│   ├── app/
│   │   ├── api/           # Routes + dashboard UI
│   │   ├── core/          # Config, database, Groq client
│   │   ├── models/        # SQLAlchemy models
│   │   ├── prompts/       # LLM prompt contracts
│   │   ├── schemas/       # Pydantic contracts
│   │   ├── services/
│   │   │   ├── assessment/    # Label + confidence engine
│   │   │   ├── collectors/    # RSS, web, Telegram, browser, manual
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
│                         # timeline, propagation,
│                         # coordination, report
├── infra/docker/          # Backend Dockerfile
├── docker-compose.yml
└── .env.example
```

---

## ⚙️ Environment Variables

| Variable | Required | Description |
| --- | --- | --- |
| `DATABASE_URL` | yes | SQLAlchemy URL. Local default `sqlite:///./data/osint.db` |
| `GROQ_API_KEY` | no | Groq key. Absent ⇒ deterministic mock enrichment |
| `GROQ_MODEL` | no | Defaults to `llama-3.3-70b-versatile` |
| `EVIDENCE_DIR` | no | Local S3-layout evidence root |
| `APP_SECRET_KEY` | yes | App signing secret. Change for any real deployment |
| `REDIS_URL` | no | Reserved for queue-backed job mode |
| `S3_ENDPOINT` / `S3_BUCKET` | no | Swap local evidence store for S3-compatible storage |

<details>
<summary><b>🔐 Optional: authorized browser collection (investigator-owned accounts only)</b></summary>

Disabled unless credentials are present. Passwords are never logged, never stored, and never sent to the LLM.

```bash
# One pair per platform prefix, e.g. OUTLET_USERNAME / OUTLET_PASSWORD
# PLATFORM_USERNAME=
# PLATFORM_PASSWORD=
# PLATFORM_LOGIN_URL=
# X_COOKIES_JSON=        # session cookies exported from your OWN browser
```

Source spec:
```json
{
  "type": "auth_browser",
  "platform": "outlet",
  "env_prefix": "OUTLET",
  "login_url": "https://…",
  "mode": "login_test | search | collect_urls"
}
```

Enforced restrictions — MFA/CAPTCHA ⇒ `*_REQUIRED` + manual pause (**no bypass**), 429 ⇒ `RATE_LIMITED`, bot-walls ⇒ `BLOCKED`. Failures are never converted into contradictory evidence. Provenance is always recorded as `authenticated_browser` + `investigator_owned_account`.

</details>

---

## 🧪 Testing

```bash
cd backend
source .venv/bin/activate
pytest -v
```

---

## 🔐 Security Notes

- ✅ `.env`, session cookie jars, `data/`, `*.db` and evidence artifacts are git-ignored
- ✅ `GROQ_API_KEY` is server-only and never exposed to the frontend
- ✅ Evidence integrity is verifiable end-to-end via SHA-256
- ✅ Analyst overrides require a rationale and are audited
- ⚠️ Change `APP_SECRET_KEY` before any non-local deployment
- ⚠️ Use authorized, investigator-owned accounts only — never third-party credentials

---

## 📄 License

Released under the MIT License.

---

## 🤝 Contributing

Issues and pull requests are welcome. Please keep changes evidence-first: if a claim in a report cannot be traced to a stored artifact, it does not belong in the report.

---

<p align="center">
  Made with 🕵️ for evidence-first OSINT investigation
</p>
