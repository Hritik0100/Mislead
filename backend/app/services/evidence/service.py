"""Evidence service - S3-compatible local layout. TRD Sec 5, PRD Sec 7.3."""
import os, hashlib, uuid
from datetime import datetime, timezone
from app.core.config import settings

def _case_dir(case_id: str):
    d = os.path.join(settings.EVIDENCE_DIR, f"cases/{case_id}/evidence")
    os.makedirs(d, exist_ok=True)
    return d

def store_binary_evidence(case_id: str, source_url: str, data: bytes,
                          filename: str, evidence_type="screenshot"):
    """Store binary artifacts (e.g. real browser screenshots). Returns like text version."""
    import uuid as _uuid
    eid = str(_uuid.uuid4())
    safe = "".join(ch for ch in filename if ch.isalnum() or ch in "._-")[:80] or "file.bin"
    fname = f"{eid}-{safe}"
    path = os.path.join(_case_dir(case_id), fname)
    with open(path, "wb") as f:
        f.write(data)
    sha = hashlib.sha256(data).hexdigest()
    return {"id": eid, "object_uri": f"cases/{case_id}/evidence/{fname}", "abspath": path,
            "sha256": sha, "evidence_type": evidence_type, "source_url": source_url,
            "captured_at": datetime.now(timezone.utc)}


def store_text_evidence(case_id: str, source_url: str, content: str, evidence_type="html_snapshot"):
    eid = str(uuid.uuid4())
    fname = f"{eid}.txt"
    path = os.path.join(_case_dir(case_id), fname)
    data = content.encode("utf-8", errors="ignore")
    with open(path, "wb") as f:
        f.write(data)
    sha = hashlib.sha256(data).hexdigest()
    rel = f"cases/{case_id}/evidence/{fname}"
    return {"id": eid, "object_uri": rel, "abspath": path, "sha256": sha,
            "evidence_type": evidence_type, "source_url": source_url,
            "captured_at": datetime.now(timezone.utc)}
