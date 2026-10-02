"""Pydantic schemas for API + LLM validation. PRD Sec 8, TRD Sec 7.3."""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

# --- Cases ---
class CaseCreate(BaseModel):
    title: str
    objective: str = ""
    keywords: List[str] = []
    platforms: List[str] = ["rss", "web"]
    time_from: Optional[str] = None
    time_to: Optional[str] = None

class CaseOut(BaseModel):
    id: str
    title: str
    objective: str
    status: str
    platforms: List[str] = []

# --- Collection ---
class CollectRequest(BaseModel):
    sources: List[Dict[str, Any]] = []  # [{type: rss|web|telegram|manual, url/channel/text...}]
    max_items: int = 50

class ClaimOut(BaseModel):
    id: str
    text: str
    topic: str = ""
    status: str = ""

class AssessmentPatch(BaseModel):
    label: Optional[str] = None
    rationale: str = ""
    actor: str = "analyst"

# --- LLM structured output (TRD 7.3) ---
class LLMEntity(BaseModel):
    name: str
    type: str = "unknown"

class LLMExtraction(BaseModel):
    claims: List[Dict[str, Any]] = []
    topics: List[str] = []
    entities: List[LLMEntity] = []
    source_type: str = "unknown"
    stance_or_context: Dict[str, Any] = {}
    urls: List[str] = []
    temporal_expressions: List[str] = []
    evidence_spans: List[str] = []
    uncertainty: Dict[str, Any] = {"needs_review": False, "reasons": []}
