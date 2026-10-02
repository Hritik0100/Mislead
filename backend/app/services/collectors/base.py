"""Collector base types. TRD Sec 6. Only public/authorized sources. No auth bypass."""
from dataclasses import dataclass, field
from typing import Dict, Any
from datetime import datetime, timezone

@dataclass
class SourceRecord:
    platform: str
    account_username: str = "unknown"
    account_display: str = ""
    profile_url: str = ""
    source_url: str = ""
    text: str = ""
    title: str = ""
    published_at: Any = None
    engagement: Dict[str, Any] = field(default_factory=dict)
    media_refs: list = field(default_factory=list)
    raw_html: str = ""
    collected_at: Any = field(default_factory=lambda: datetime.now(timezone.utc))
    # Provenance (never carries secrets): e.g. {"collection_method": "public_web"|
    # "authenticated_browser"|"analyst_seed", "access": ..., "independent": bool}
    provenance: Dict[str, Any] = field(default_factory=dict)
    # Real screenshot bytes when the driver captured an actual file (else None;
    # never claim a screenshot without these bytes).
    screenshot_bytes: Any = None
    # Original post image bytes when OCR was run on it. Kept as evidence so the
    # analyst can verify what the OCR engine actually read.
    image_bytes: Any = None
