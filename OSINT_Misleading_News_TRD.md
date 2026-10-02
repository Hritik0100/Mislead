TECHNICAL REQUIREMENTS DOCUMENT (TRD)

OSINT Misleading-News Account Identification & Claim Verification Platform


Technical design aligned with the supplied workflow: data sources → collection → evidence management → three-layer filtering/enrichment → database storage → OSINT analysis engine → final assessment/report. Groq is the LLM inference provider.

## 1. Architecture

Recommended architecture: modular backend with asynchronous workers. API services manage cases and queries; connector workers collect source data; evidence workers persist artifacts; enrichment workers perform filtering/parsing/LLM extraction; analysis workers execute OSINT jobs; PostgreSQL stores structured metadata and relationships; object storage stores evidence artifacts; the frontend provides analyst review.

- Frontend: Next.js/React + TypeScript.
- API: FastAPI + Python.
- Background jobs: Celery/RQ/Arq or an equivalent queue/worker system.
- Primary database: PostgreSQL.
- Optional vector retrieval: pgvector.
- Evidence/object storage: S3-compatible storage.
- Cache/queue: Redis.
- LLM: Groq API.
- Containerization: Docker; deployment may use managed PostgreSQL/object storage and containerized workers.
## 2. Logical Component Architecture

| Component | Responsibility | Interfaces |
| --- | --- | --- |
| API Gateway / Backend | Cases, search, evidence, analysis orchestration, auth | REST/JSON |
| Source Connectors | RSS, web/public sources, authorized platform APIs | HTTP/API/RSS |
| Collector Worker | Normalize and persist raw records | Queue + DB |
| Evidence Service | Screenshots/media/HTML object storage | S3 API |
| Pre-filter Worker | Keyword/entity filter, deduplication | DB + queue |
| Parser Worker | HTML/XML parsing and clean text extraction | DB |
| LLM Enrichment Worker | Groq structured extraction | Groq API |
| OSINT Analysis Worker | Origin, spread, verification, coordination | DB + retrieval |
| Assessment Service | Evidence aggregation and final label | DB + LLM where required |
| Reporting Service | Report JSON/HTML/PDF-ready output | API/object storage |
| Analyst UI | Search, graph, timeline, evidence review, export | REST/WebSocket/SSE |

## 3. End-to-End Data Flow

1. Case creation stores investigation objective, scope, keywords, platforms, and time range.
1. Scheduler or manual trigger creates collection jobs.
1. Collectors retrieve permitted source data and emit normalized SourceRecord objects.
1. Evidence service stores screenshots/media/HTML and returns immutable evidence references.
1. Pre-filter removes irrelevant records and performs deterministic deduplication.
1. Parser extracts clean text from HTML/XML while retaining original metadata.
1. Groq enrichment extracts claims, entities, topics, source relations, and analysis fields into schema-validated JSON.
1. Structured records are stored in PostgreSQL and linked to raw records and evidence artifacts.
1. OSINT analysis creates candidate-origin, spread, verification, and coordination findings.
1. Assessment combines findings and evidence into an uncertainty-aware result.
1. Report service produces analyst-facing output with traceable evidence links.
## 4. Recommended Database Schema

| Table | Key Structure |
| --- | --- |
| cases | id UUID PK; title; objective; status; created_at; updated_at |
| case_keywords | id; case_id FK; keyword; normalized_keyword; type |
| accounts | id UUID PK; platform; username; display_name; profile_url; first_seen_at |
| posts | id UUID PK; platform_post_id; account_id FK; source_url; text; published_at; collected_at; raw_hash |
| media | id UUID PK; post_id FK; object_uri; media_type; sha256; metadata_json |
| evidence | id UUID PK; case_id FK; evidence_type; object_uri; source_url; captured_at; sha256 |
| claims | id UUID PK; case_id FK; text; normalized_text; topic; status; created_at |
| claim_evidence | claim_id FK; evidence_id FK; relation; notes |
| post_relations | source_post_id; target_post_id; relation_type; similarity; evidence_ids |
| analysis_runs | id UUID PK; case_id; analysis_type; model; status; started_at; finished_at |
| analysis_findings | id UUID PK; run_id; finding_type; payload_json; confidence; evidence_ids |
| assessments | id UUID PK; case_id; label; confidence; factors_json; analyst_override; rationale |
| audit_events | id; actor; action; entity_type; entity_id; before_json; after_json; timestamp |

## 5. Evidence Storage Design

- Use S3-compatible object storage with case-scoped prefixes.
- Suggested object key: cases/{case_id}/evidence/{evidence_id}/{filename}.
- Store sha256 hash, MIME type, byte size, capture timestamp, source URL, and collector version.
- Prefer immutable/versioned object storage for investigation evidence.
- Do not store large binary artifacts directly in PostgreSQL.
- Generate signed, time-limited URLs for authorized analyst access.
## 6. Collector Design

| Collector Type | Technical Approach | Constraints |
| --- | --- | --- |
| RSS/News | Feed parser + HTTP client + HTML parser | Respect publisher/feed terms and rate limits |
| Public Web | HTTP fetch + parser; browser automation only where permitted | Robots/terms/access controls |
| Telegram | Official API / authorized public channel access | API limits and authorization |
| Social APIs | Official/authorized APIs where available | API quotas, permissions, platform policy |
| Manual Evidence | Analyst URL/upload + screenshot capture | Analyst must attest to source/context |

## 7. Three-Layer Enrichment Pipeline

### 7.1 Layer 1 — Pre-filter

- Normalize Unicode, whitespace, URLs, and case for matching.
- Keyword/alias/entity matching.
- Remove exact duplicates using content hash.
- Use near-duplicate similarity only as a candidate filter; retain original records.
- Reject records outside configured time/scope unless explicitly retained.
### 7.2 Layer 2 — Clean Text

- Parse HTML/XML using BeautifulSoup/lxml or equivalent.
- Extract title, visible text, canonical URL, author, publication time, and links.
- Preserve raw HTML reference for auditability.
- Normalize boilerplate while keeping the original text available.
### 7.3 Layer 3 — Groq LLM JSON Extraction

Send only the required cleaned content and provenance metadata to Groq. The response must conform to a versioned JSON schema and must be validated before persistence.

| Field | Type | Purpose |
| --- | --- | --- |
| claims | array | Atomic factual claims extracted from content |
| topics | array | Normalized topics/themes |
| entities | array | People, organizations, places, products, events |
| source_type | string | News/social/blog/official/etc. |
| stance_or_context | object | Contextual characterization without unsupported intent |
| urls | array | URLs explicitly present in source content |
| temporal_expressions | array | Dates/times expressed in content |
| evidence_spans | array | Text spans supporting extracted fields |
| uncertainty | object | Fields requiring review or ambiguous extraction |

## 8. Groq Integration

- Backend-only API access; never expose GROQ_API_KEY to the browser.
- Use environment/secret manager configuration: GROQ_API_KEY, GROQ_MODEL, request timeout, retry policy.
- Implement exponential backoff for transient failures and bounded retries.
- Use structured output / JSON schema enforcement when supported by the selected Groq model/API.
- Validate JSON with Pydantic before database writes.
- Persist model/version metadata with every LLM-derived result.
- Use deterministic temperature/settings where supported for extraction/classification tasks.
- Separate extraction prompts from investigative reasoning prompts.
- Set maximum input size and chunk large source documents before inference.
## 9. LLM Prompt Contracts

### 9.1 Extraction Contract

Input: clean text + source metadata. Output: schema-valid JSON only. The model must not invent URLs, entities, dates, quotations, or evidence. Unknown values must be null/empty and marked uncertain.

### 9.2 Claim Verification Contract

Input: normalized claim + retrieved source excerpts + source metadata. Output: label candidate, confidence, supporting evidence IDs, contradicting evidence IDs, missing information, and concise rationale. The model must distinguish source-reported claims from independently established facts.

### 9.3 Coordination Contract

Input: account/post graph features. Output: observable coordination indicators, temporal clusters, text/link similarity, and uncertainty. Do not output intent as a fact.

## 10. Source Verification & Retrieval

- Use deterministic source retrieval first; LLMs interpret retrieved evidence rather than inventing it.
- Rank sources using configurable metadata such as source type, directness, publication time, and corroboration.
- Store each retrieved source URL, retrieval timestamp, content hash, and evidence reference.
- For conflicting sources, preserve both sides and require an uncertainty state when the evidence is insufficient.
- The 'original source' result must be labeled as 'earliest observed/candidate origin' unless independently proven.
## 11. Spread Analysis

- Represent accounts and posts as graph nodes.
- Represent repost/copy/shared URL/shared media/semantic similarity/temporal proximity as typed edges.
- Calculate graph features such as in-degree, out-degree, connected components, temporal clusters, and repeated-content counts.
- Keep each edge explainable through one or more evidence IDs.
- Use configurable similarity thresholds and log the algorithm/version.
## 12. Coordination Analysis

| Signal | Implementation |
| --- | --- |
| Temporal synchronization | Bucket timestamps; calculate unusually close posting intervals |
| Text reuse | Normalized exact match + embedding/semantic similarity |
| URL reuse | Canonicalize URLs and compare shared destinations |
| Media reuse | SHA/perceptual hash where appropriate |
| Network overlap | Compare shared accounts, links, and interaction patterns |
| Burst detection | Time-series count anomaly against historical baseline |

## 13. Assessment Engine

Use a rule/evidence aggregation layer before final LLM narrative generation. Example internal representation:

| Factor | Example |
| --- | --- |
| Evidence coverage | Number/quality of directly relevant evidence items |
| Source agreement | Agreement across independent sources |
| Source contradiction | Directly conflicting evidence |
| Chronology confidence | Strength of temporal/origin evidence |
| Propagation strength | Observed amplification relationships |
| Coordination indicators | Observable synchronized behavior |
| Analyst override | Human decision and rationale |

The final label must remain traceable to these factors. Confidence is not a probability of truth unless the system has been statistically calibrated on an evaluation dataset.

## 14. API Requirements

| Endpoint | Method | Purpose |
| --- | --- | --- |
| /api/cases | POST/GET | Create/list cases |
| /api/cases/{id} | GET/PATCH | Case details and scope |
| /api/cases/{id}/collect | POST | Start collection job |
| /api/cases/{id}/evidence | GET | List evidence |
| /api/evidence/{id} | GET | Evidence metadata/access |
| /api/cases/{id}/claims | GET/POST | Claims |
| /api/cases/{id}/analysis | POST | Run selected OSINT analysis |
| /api/cases/{id}/findings | GET | Analysis findings |
| /api/cases/{id}/assessment | GET/PATCH | Assessment and analyst review |
| /api/cases/{id}/report | GET | Final report/export |

## 15. Asynchronous Job Model

- Use job IDs for collection, enrichment, source verification, graph analysis, and report generation.
- Each job has queued/running/succeeded/failed/cancelled status.
- Jobs must be idempotent using source IDs/content hashes/case IDs.
- Use retry counts and dead-letter handling for persistent failures.
- Expose progress to UI through polling or WebSocket/SSE.
## 16. Security

- OAuth/OIDC or secure application authentication for analysts.
- Role-based authorization for case access and administrative actions.
- Secrets stored in environment/secret manager; never in source control.
- TLS for all external/internal network paths where applicable.
- Parameterized SQL/ORM to prevent injection.
- Validate uploaded file type and size; malware-scan uploads where feasible.
- Audit all evidence access, report exports, analyst overrides, and configuration changes.
- Apply data retention and deletion policies per deployment requirements.
## 17. Observability

| Area | Metrics / Logs |
| --- | --- |
| Collectors | requests, success rate, latency, rate-limit errors, parse failures |
| LLM | request count, latency, retries, token usage if available, schema failures |
| Pipeline | records per stage, drop counts, dedup counts, queue depth |
| Database | query latency, connections, storage growth |
| Evidence | artifact count, storage bytes, hash failures |
| Analysis | run duration, findings count, graph size |

## 18. Testing Strategy

- Unit tests for parsers, normalization, deduplication, schema validators, graph calculations, and assessment rules.
- Connector contract tests using mocked API/RSS responses.
- LLM evaluation set with labeled extraction and verification cases.
- Prompt regression tests across model/version changes.
- End-to-end tests from case creation through report generation.
- Security tests for authentication, authorization, injection, file uploads, and secret exposure.
- Load tests for concurrent collection and enrichment jobs.
## 19. Deployment

- Docker Compose for local development; Kubernetes or managed container platform for larger deployments.
- PostgreSQL with backups and point-in-time recovery for production.
- S3-compatible object storage with versioning where available.
- Redis for queue/cache.
- CI/CD pipeline with linting, tests, migration checks, container scanning, and staged deployment.
- Separate development, staging, and production credentials/configuration.
## 20. Suggested Project Structure

backend/
  app/
    api/
    core/
    models/
    schemas/
    services/
      collectors/
      evidence/
      enrichment/
      osint/
      assessment/
      reporting/
    workers/
    prompts/
    repositories/
  migrations/
frontend/
  app/
  components/
  lib/
infra/
  docker/
  deployment/

## 21. Environment Variables

| Variable | Purpose |
| --- | --- |
| DATABASE_URL | PostgreSQL connection string |
| REDIS_URL | Queue/cache connection |
| GROQ_API_KEY | Server-side Groq credential |
| GROQ_MODEL | Configurable Groq model identifier |
| S3_ENDPOINT | Object storage endpoint |
| S3_BUCKET | Evidence bucket |
| S3_ACCESS_KEY | Object storage credential |
| S3_SECRET_KEY | Object storage credential |
| APP_SECRET_KEY | Application signing/encryption secret |

## 22. Example Structured LLM Output

{
  "claims": [{"text": "…", "type": "factual", "evidence_spans": [1]}],
  "topics": ["…"],
  "entities": [{"name": "…", "type": "organization"}],
  "source_type": "social",
  "urls": ["https://example.invalid/source"],
  "uncertainty": {"needs_review": false, "reasons": []}
}

## 23. Technical Acceptance Criteria

- Every persisted post has source provenance and collection timestamp.
- Every evidence artifact has a stable ID and SHA-256 hash.
- Every LLM result is associated with model/version metadata and schema-validation status.
- No LLM-derived claim can enter final assessment without a case/evidence relationship.
- Graph edges expose their underlying evidence references.
- Assessment changes are audit logged.
- Collection and analysis jobs can be retried without creating duplicate canonical records.
- The application continues operating when one source connector or the Groq API is temporarily unavailable.
- All secrets remain server-side and are excluded from frontend bundles/logs.
- The system can export a complete case package containing structured findings and evidence references.
