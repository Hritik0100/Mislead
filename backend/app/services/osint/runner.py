"""OSINT runner: executes A-E + findings persistence. PRD 7.5."""
import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.db import AnalysisRun, AnalysisFinding
from app.core.config import settings
from .fake_detect import run_fake_detect
from .origin import run_origin
from .spread import run_spread
from .verification import run_verification
from .coordination import run_coordination

def run_full_analysis(db: Session, case_id: str, analysis_type="full"):
    run = AnalysisRun(id=str(uuid.uuid4()), case_id=case_id, analysis_type=analysis_type,
                      model=settings.GROQ_MODEL, status="succeeded",
                      started_at=datetime.now(timezone.utc), finished_at=datetime.now(timezone.utc))
    db.add(run)
    db.commit()
    out = {}
    if analysis_type in ("A", "full"):
        out["A_fake_news"] = run_fake_detect(db, case_id)
    if analysis_type in ("B", "full"):
        out["B_origin"] = run_origin(db, case_id)
    if analysis_type in ("C", "full"):
        out["C_spread"] = run_spread(db, case_id)
    if analysis_type in ("D", "full"):
        out["D_verification"] = run_verification(db, case_id)
    if analysis_type in ("E", "full"):
        out["E_coordination"] = run_coordination(db, case_id)
    for k, v in out.items():
        db.add(AnalysisFinding(id=str(uuid.uuid4()), run_id=run.id, case_id=case_id,
                               finding_type=k, payload_json=v if isinstance(v, dict) else {"items": v},
                               confidence=0.5, evidence_ids=[]))
    run.finished_at = datetime.now(timezone.utc)
    db.commit()
    return {"run_id": run.id, **out}
