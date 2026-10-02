"""DB models - PRD Sec 8, TRD Sec 4."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, Float, ForeignKey, Integer, JSON
from app.core.database import Base

def _uuid():
    return str(uuid.uuid4())

def _now():
    return datetime.now(timezone.utc)

class Case(Base):
    __tablename__ = "cases"
    id = Column(String, primary_key=True, default=_uuid)
    title = Column(String, nullable=False)
    objective = Column(Text, default="")
    status = Column(String, default="open")
    platforms = Column(JSON, default=list)  # monitored platforms Phase 2
    time_from = Column(DateTime, nullable=True)
    time_to = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

class CaseKeyword(Base):
    __tablename__ = "case_keywords"
    id = Column(String, primary_key=True, default=_uuid)
    case_id = Column(String, ForeignKey("cases.id"), index=True)
    keyword = Column(String)
    normalized_keyword = Column(String, index=True)
    type = Column(String, default="keyword")  # keyword|alias|entity|url|hashtag|handle

class Account(Base):
    __tablename__ = "accounts"
    id = Column(String, primary_key=True, default=_uuid)
    platform = Column(String, index=True)
    username = Column(String, index=True)
    display_name = Column(String, default="")
    profile_url = Column(String, default="")
    first_seen_at = Column(DateTime, default=_now)

class Post(Base):
    __tablename__ = "posts"
    id = Column(String, primary_key=True, default=_uuid)
    case_id = Column(String, ForeignKey("cases.id"), index=True)
    platform_post_id = Column(String, default="")
    account_id = Column(String, ForeignKey("accounts.id"), index=True)
    source_url = Column(Text, default="")
    text = Column(Text, default="")
    clean_text = Column(Text, default="")
    published_at = Column(DateTime, nullable=True)
    collected_at = Column(DateTime, default=_now)
    raw_hash = Column(String, index=True, default="")
    engagement = Column(JSON, default=dict)
    platform = Column(String, default="")

class Media(Base):
    __tablename__ = "media"
    id = Column(String, primary_key=True, default=_uuid)
    post_id = Column(String, ForeignKey("posts.id"))
    object_uri = Column(String, default="")
    media_type = Column(String, default="")
    sha256 = Column(String, default="")
    metadata_json = Column(JSON, default=dict)

class Evidence(Base):
    __tablename__ = "evidence"
    id = Column(String, primary_key=True, default=_uuid)
    case_id = Column(String, ForeignKey("cases.id"), index=True)
    evidence_type = Column(String, default="html_snapshot")  # screenshot|html|image|video|text
    object_uri = Column(String, default="")
    source_url = Column(Text, default="")
    captured_at = Column(DateTime, default=_now)
    sha256 = Column(String, default="")

class Claim(Base):
    __tablename__ = "claims"
    id = Column(String, primary_key=True, default=_uuid)
    case_id = Column(String, ForeignKey("cases.id"), index=True)
    text = Column(Text)
    normalized_text = Column(Text, default="")
    topic = Column(String, default="")
    status = Column(String, default="candidate")
    created_at = Column(DateTime, default=_now)

class ClaimEvidence(Base):
    __tablename__ = "claim_evidence"
    id = Column(String, primary_key=True, default=_uuid)
    claim_id = Column(String, ForeignKey("claims.id"), index=True)
    evidence_id = Column(String, ForeignKey("evidence.id"), index=True)
    post_id = Column(String, ForeignKey("posts.id"), index=True, nullable=True)
    relation = Column(String, default="supports")  # supports|contradicts|context|origin|cites
    notes = Column(Text, default="")

class PostRelation(Base):
    __tablename__ = "post_relations"
    id = Column(String, primary_key=True, default=_uuid)
    case_id = Column(String, ForeignKey("cases.id"), index=True)
    source_post_id = Column(String, index=True)
    target_post_id = Column(String, index=True)
    relation_type = Column(String)  # repost|copy|shared_url|shared_media|semantic|temporal
    similarity = Column(Float, default=0.0)
    evidence_ids = Column(JSON, default=list)

class AnalysisRun(Base):
    __tablename__ = "analysis_runs"
    id = Column(String, primary_key=True, default=_uuid)
    case_id = Column(String, ForeignKey("cases.id"), index=True)
    analysis_type = Column(String, index=True)  # A|B|C|D|E|full
    model = Column(String, default="")
    status = Column(String, default="succeeded")
    prompt_version = Column(String, default="v1")
    started_at = Column(DateTime, default=_now)
    finished_at = Column(DateTime, default=_now)

class AnalysisFinding(Base):
    __tablename__ = "analysis_findings"
    id = Column(String, primary_key=True, default=_uuid)
    run_id = Column(String, ForeignKey("analysis_runs.id"), index=True)
    case_id = Column(String, ForeignKey("cases.id"), index=True)
    finding_type = Column(String, index=True)
    payload_json = Column(JSON, default=dict)
    confidence = Column(Float, default=0.0)
    evidence_ids = Column(JSON, default=list)

class Assessment(Base):
    __tablename__ = "assessments"
    id = Column(String, primary_key=True, default=_uuid)
    case_id = Column(String, ForeignKey("cases.id"), index=True)
    claim_id = Column(String, ForeignKey("claims.id"), nullable=True)
    label = Column(String, default="Unverified")  # True|False|Misleading|Context Missing|Unverified
    confidence = Column(Float, default=0.0)
    factors_json = Column(JSON, default=dict)
    evidence_refs = Column(JSON, default=list)
    analyst_override = Column(String, nullable=True)
    rationale = Column(Text, default="")
    created_at = Column(DateTime, default=_now)

class AuditEvent(Base):
    __tablename__ = "audit_events"
    id = Column(String, primary_key=True, default=_uuid)
    actor = Column(String, default="system")
    action = Column(String)
    entity_type = Column(String)
    entity_id = Column(String)
    before_json = Column(JSON, default=dict)
    after_json = Column(JSON, default=dict)
    timestamp = Column(DateTime, default=_now)

class CollectionJob(Base):
    __tablename__ = "collection_jobs"
    id = Column(String, primary_key=True, default=_uuid)
    case_id = Column(String, ForeignKey("cases.id"), index=True)
    status = Column(String, default="queued")  # queued|running|succeeded|failed|cancelled
    source = Column(String, default="rss")
    stats_json = Column(JSON, default=dict)
    error = Column(Text, default="")
    created_at = Column(DateTime, default=_now)
    finished_at = Column(DateTime, nullable=True)
