PRODUCT REQUIREMENTS DOCUMENT (PRD)

OSINT Misleading-News Account Identification & Claim Verification Platform


Document purpose: Define the product behavior, user requirements, scope, workflows, outputs, acceptance criteria, and operational constraints for an OSINT platform that discovers potentially misleading claims, identifies and links originating/spreading accounts, verifies claims against evidence, and produces an evidence-backed analyst report. Groq-hosted LLM inference is the primary LLM layer.

## 1. Product Overview

The platform is an evidence-first OSINT investigation system for analyzing public or authorized content across social media, news/RSS sources, and communication platforms. It transforms collected posts and media into structured evidence, performs staged LLM-assisted analysis, traces the spread of a claim, checks coordination signals, and produces a final report with source links, evidence references, assessment labels, and risk indicators.

## 2. Problem Statement

Investigators currently need to manually collect posts, preserve screenshots/media, locate earlier versions of a claim, compare sources, trace amplification, and document conclusions. The proposed system reduces this fragmentation by providing one repeatable workflow from data collection to evidence-backed assessment.

## 3. Goals

- Identify potentially misleading or suspicious claims from monitored public/authorized sources.
- Capture provenance: account, username, platform, timestamp, post URL, source, media, and engagement data when available.
- Find candidate original/earliest sources for a claim and preserve the reasoning trail.
- Trace claim amplification across accounts, platforms, timestamps, and repeated content.
- Verify claims using retrieved evidence and classify them as True, False, Misleading, Context Missing, or Unverified.
- Detect coordination indicators such as synchronized posting, repeated wording, shared URLs, and temporal patterns.
- Use LLMs for extraction, classification, reasoning assistance, and report generation while retaining deterministic evidence links.
- Provide analysts with searchable, reviewable, exportable case reports.
## 4. Non-Goals

- The system is not an autonomous authority that declares truth without evidence.
- It does not bypass authentication, paywalls, access controls, private groups, or platform security controls.
- It does not guarantee that the earliest discovered post is the true origin.
- It does not infer a person's identity from protected/private information.
- It does not use an LLM as the sole source of factual evidence.
- It does not automatically accuse an account or organization of malicious coordination; it surfaces indicators for analyst review.
## 5. Target Users

| User | Needs | Primary Actions |
| --- | --- | --- |
| OSINT Analyst | Investigate claims and accounts | Search, review evidence, trace spread, verify, annotate, export |
| Researcher | Study misinformation patterns | Run cases, compare sources, inspect timelines/graphs |
| Editor / Fact Checker | Validate claims efficiently | Review evidence, source provenance, approve assessment |
| System Administrator | Operate monitored sources and jobs | Configure connectors, schedules, access, retention |

## 6. Core User Journey

1. Analyst defines investigation objective, topics/keywords, platforms, time range, and collection scope.
1. Collectors ingest public/authorized posts, RSS/news content, and permitted communication-platform data.
1. The system stores raw content and captures screenshots/media where permitted.
1. A three-layer enrichment pipeline filters noise, extracts clean text, and produces structured JSON.
1. The analysis engine runs key OSINT queries: fake-news detection, original-source discovery, spread tracing, claim verification, and coordination analysis.
1. The assessment engine combines evidence and model outputs into a conditional assessment with confidence/risk indicators.
1. The analyst reviews evidence, corrects/annotates findings, and exports the final OSINT report.
## 7. Functional Requirements

### 7.1 Investigation & Scope

- Create a case with case ID, title, objective, investigator, creation time, and status.
- Define keywords, aliases, entities, URLs, hashtags, account handles, and time windows.
- Select monitored platforms and source types.
- Support manual seed URLs/posts as investigation starting points.
- Allow scheduled or manually triggered collection.
### 7.2 Data Sources & Collection

- Social sources: public/authorized content from platforms such as Instagram, X, Facebook, YouTube, and other supported sources.
- News sources: multiple RSS feeds, publisher pages, and permitted APIs.
- Communication sources: Telegram or other platforms only through official APIs, public channels, or otherwise authorized access.
- Collector records source URL, platform, retrieval time, publication time when available, author/account metadata, text, links, media references, and engagement metrics.
- Collection failures must be logged without silently dropping the source.
### 7.3 Evidence Management

- Every collected item receives a stable evidence ID.
- Store screenshots, images, audio, video, HTML snapshots, and downloaded source artifacts where legally and technically permitted.
- Store cryptographic hashes for captured files to support integrity checking.
- Preserve source URL and retrieval timestamp.
- Maintain provenance from derived findings back to source evidence IDs.
### 7.4 Three-Layer Data Filtering & Enrichment

| Layer | Requirement | Output |
| --- | --- | --- |
| Layer 1: Pre-filter | Keyword/entity matching; remove irrelevant noise; basic deduplication | Relevant candidate records |
| Layer 2: Clean text | Parse HTML/XML; normalize text; extract visible content; preserve source metadata | Clean text + provenance |
| Layer 3: LLM JSON extraction | Groq LLM extracts claims, topics, entities, sentiment/context signals, source relationships, and structured fields | Validated structured JSON |

### 7.5 Key OSINT Queries

| Query | Expected Function | Required Evidence |
| --- | --- | --- |
| A. Identify Fake News | Scan/detect potentially misleading claims | Claim text, source context, supporting/contradicting sources |
| B. Find Original Source | Locate earliest/candidate originating post | Timestamps, URLs, text similarity, media similarity, source chronology |
| C. Trace Spread | Map amplification and repost/copy relationships | Account IDs, timestamps, shared text/URLs/media, graph edges |
| D. Verify Claim | Compare claim with retrieved evidence | Primary/secondary sources, source quality metadata, citations |
| E. Check Coordination | Surface synchronized or repeated behavior | Wording similarity, timestamps, shared links, network patterns |

### 7.6 Assessment & Reporting

- Generate assessment labels: True, False, Misleading, Context Missing, or Unverified.
- Present confidence separately from truth label.
- Show evidence supporting and contradicting the assessment.
- Show source URLs and evidence IDs for every material conclusion.
- Show spread timeline and account relationships where data is sufficient.
- Show risk indicators as explainable factors rather than opaque scores alone.
- Allow analyst override with mandatory rationale.
- Export a human-readable report and machine-readable JSON.
## 8. Data Model Requirements

| Entity | Key Fields |
| --- | --- |
| Case | case_id, title, objective, keywords, scope, status, created_at |
| Account | account_id, platform, username, display_name, profile_url, first_seen |
| Post | post_id, account_id, source_url, text, timestamp, engagement, media_refs |
| Evidence | evidence_id, case_id, type, object_uri, source_url, captured_at, sha256 |
| Claim | claim_id, text, normalized_text, entities, topic, status |
| Relation | source_id, target_id, relation_type, timestamp, similarity, evidence_refs |
| Assessment | assessment_id, label, confidence, factors, evidence_refs, analyst_review |

## 9. LLM Requirements — Groq

- Groq is the primary inference provider for LLM tasks.
- LLM tasks must use structured JSON outputs with schema validation.
- Prompts must require evidence-grounded reasoning and explicit uncertainty.
- The LLM must never fabricate a source URL, timestamp, account, quotation, or evidence ID.
- Source retrieval and deterministic metadata remain outside the LLM.
- Model name must be configurable so the system can change Groq-supported models without rewriting business logic.
- Store model name, prompt/version ID, request ID where available, timestamp, token usage where available, and output validation status.
- Sensitive/private data must not be sent to the model unless explicitly authorized by the deployment policy.
## 10. Non-Functional Requirements

| Area | Requirement |
| --- | --- |
| Reliability | Jobs are retryable and idempotent; failed sources are observable. |
| Traceability | Every conclusion links to evidence IDs and source URLs. |
| Security | Secrets stored server-side; RBAC; encrypted transport; least privilege. |
| Performance | Collection and enrichment are asynchronous; UI should remain responsive during long jobs. |
| Scalability | Collectors, workers, LLM calls, and graph analysis can scale independently. |
| Auditability | Record collector events, model versions, assessment changes, and analyst overrides. |
| Data Quality | Deduplicate records and validate structured LLM output before persistence. |
| Compliance | Respect platform terms, copyright, privacy, robots/API restrictions, and applicable law. |

## 11. Acceptance Criteria

- A case can be created with objectives, keywords, monitored platforms, and a time range.
- A supported collector can ingest a source item and persist provenance metadata.
- An evidence artifact can be linked to the exact post/source that produced it.
- The enrichment pipeline produces schema-valid JSON or records a validation failure.
- The system can create a claim and link it to multiple evidence items.
- The original-source workflow displays candidate sources with timestamps and evidence links.
- The spread workflow creates account/content relationships with explainable edge evidence.
- Claim verification displays supporting and contradicting sources and an uncertainty-aware label.
- Coordination analysis shows indicators without automatically asserting intent.
- A final report contains source links, evidence IDs, assessment, confidence, and risk indicators.
- An analyst can override an assessment and the override is audited.
## 12. Risks & Mitigations

| Risk | Mitigation |
| --- | --- |
| LLM hallucination | Strict JSON schema, evidence-only prompts, source citations, deterministic validation, analyst review. |
| Platform access changes | Connector abstraction, official APIs/RSS where available, graceful failure handling. |
| False positives | Multi-source verification, confidence/uncertainty, human review, configurable thresholds. |
| Incomplete chronology | Label earliest result as 'earliest observed' unless provenance proves otherwise. |
| Coordinated behavior misinterpretation | Present observable indicators; avoid inferring intent without evidence. |
| Evidence tampering/loss | Hash artifacts, immutable/object storage policy, timestamps, audit logs. |

## 13. MVP Scope

- Case management and keyword-based collection.
- RSS/news ingestion plus at least one authorized social/communication connector.
- Raw evidence store and PostgreSQL metadata store.
- Three-layer filtering/enrichment pipeline.
- Groq LLM JSON extraction.
- Claim verification workflow.
- Basic source chronology and spread graph.
- Analyst dashboard and JSON/PDF-ready report data.
## 14. Future Enhancements

- Multimodal image/video claim analysis.
- OCR and visual similarity for meme/image propagation.
- Advanced graph algorithms for communities and diffusion paths.
- Embedding-based semantic retrieval over historical cases.
- Human feedback loops for classifier/prompt evaluation.
- Case-to-case campaign and narrative clustering.
- Additional connectors and multilingual analysis.
## 15. Product Success Metrics

| Metric | Definition |
| --- | --- |
| Evidence Coverage | Percentage of material report claims with linked evidence IDs. |
| Structured Output Validity | Percentage of LLM extraction responses passing schema validation. |
| Analyst Review Rate | Percentage of cases reviewed before final report publication. |
| Source Traceability | Percentage of collected records with source URL and retrieval timestamp. |
| Investigation Cycle Time | Time from case creation to analyst-ready report. |
| False Positive Rate | Measured on a labeled evaluation set; track by platform/source type. |
