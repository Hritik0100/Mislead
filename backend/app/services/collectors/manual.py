"""Manual seed collector - analyst URL/upload with attestation. TRD Sec 6."""
from .base import SourceRecord

def collect_manual(platform: str, username: str, text: str, url: str = "", published_at=None):
    return [SourceRecord(platform=platform or "manual", account_username=username or "analyst-seed",
                         source_url=url or "manual://seed", text=text)], ""
