"""Telegram + ChirpWire/Matrix stubs.
Only official API / public channel / authorized access. No private-group bypass.
MVP: manual seed + public-channel placeholder that requires explicit analyst attestation.
"""
from .base import SourceRecord

SUPPORTED = ["telegram", "chirpwire", "matrix", "element", "facebook", "instagram", "x", "youtube"]

def collect_platform_stub(platform: str, handle_or_channel: str, note: str = ""):
    """Do NOT scrape. Record an analyst-attested placeholder requiring manual evidence upload.
    Returns SourceRecord with needs_review flag in engagement."""
    p = platform.lower()
    if p not in SUPPORTED:
        return [], f"unsupported platform: {platform}"
    rec = SourceRecord(
        platform=p,
        account_username=handle_or_channel,
        profile_url=f"{p}:{handle_or_channel}",
        source_url=f"{p}:{handle_or_channel}",
        text=note or f"[stub] {p} account {handle_or_channel} queued for authorized collection",
        engagement={"stub": True, "needs_manual_evidence": True},
    )
    return [rec], ""
