# OSINT Misleading-News Platform — MVP Build (PRD + TRD)

Evidence-first workflow: **P1 Objective → P2 Platforms → P3 Search → P4 Account ID → P5 A-E queries → P6 Report**. Groq LLM.

## Architecture

![Architecture diagram](architecture/architecture-diagram.png)

## Quickstart (local, no Postgres/Redis needed)
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add GROQ_API_KEY for real LLM, else deterministic mock is used
uvicorn app.main:app --reload --port 8000
```
Open:
- Dashboard: http://localhost:8000/dashboard
- API docs: http://localhost:8000/docs
- Health: http://localhost:8000/health

## API (TRD Sec 14)
POST/GET /api/cases | GET/PATCH /api/cases/{id} | POST /api/cases/{id}/collect |
GET /api/cases/{id}/evidence | GET/POST /api/cases/{id}/claims | POST /api/cases/{id}/analysis |
GET /api/cases/{id}/findings | GET/PATCH /api/cases/{id}/assessment | GET /api/cases/{id}/report

## MVP notes vs PRD/TRD
- Collectors: RSS (real), public web (real, robots-respecting), Telegram/ChirpWire/Matrix/Facebook/Instagram/X/YouTube via **authorized-only stub** — analyst must upload manual evidence. No paywall/auth bypass (PRD Sec 4 non-goals).
- Evidence: local S3-layout `data/evidence/cases/{case}/evidence/{id}.txt` + sha256 (TRD Sec 5). Swap to S3 by replacing `evidence/service.py`.
- 3-layer enrichment: prefilter → BeautifulSoup clean → Groq JSON extract (mock fallback, Pydantic-validated).
- A-E analysis: fake-detect, earliest-observed origin, spread graph (typed edges), verification (uncertainty-aware), coordination (indicators only).
- Assessment labels: True/False/Misleading/Context Missing/Unverified + separate confidence + analyst override (audited).
- DB: SQLite locally, Postgres-ready via `DATABASE_URL` (SQLAlchemy). `docker-compose up` runs API.

## Test
```bash
cd backend && pytest tests/test_pipeline.py tests/test_auth_browser.py -v
```

## Optional: authenticated browser collection (investigator-owned accounts only)
- Disabled unless `<PREFIX>_USERNAME` / `<PREFIX>_PASSWORD` are set (see `backend/.env.example`). Passwords never logged, stored, or sent to the LLM.
- Source spec: `{"type":"auth_browser","platform":"outlet","env_prefix":"OUTLET","login_url":"…","mode":"login_test|search|collect_urls", ...}`. Real-browser driver = agent-browser CLI session; FakeDriver for tests.
- Restrictions enforced: MFA/CAPTCHA → `*_REQUIRED` + manual pause (no bypass), 429 → `RATE_LIMITED`, bot-walls → `BLOCKED`, failures never become contradictory evidence. Provenance recorded as `authenticated_browser` + `investigator_owned_account`.
- SearXNG is not deployed; the pipeline continues on RSS / public web / manual when auth is absent.

## Env (TRD Sec 21)
DATABASE_URL, GROQ_API_KEY (server-only), GROQ_MODEL, EVIDENCE_DIR, APP_SECRET_KEY. Never expose GROQ key to frontend.
