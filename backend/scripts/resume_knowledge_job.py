"""Resume one interrupted local knowledge indexing job."""

from __future__ import annotations

from datetime import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.database import SessionLocal
from app.db.models import BackgroundJobModel, SourceDocumentModel
from app.workers.background_worker import process_knowledge_index_actor


JOB_ID = "knowledge_index_3aa4572523df"


with SessionLocal() as session:
    job = session.get(BackgroundJobModel, JOB_ID)
    if job is None:
        raise SystemExit(f"job not found: {JOB_ID}")
    source = session.get(SourceDocumentModel, job.target_id)
    if source is None or source.business_usage != "knowledge_base":
        raise SystemExit("target source is missing or not a knowledge source")
    if job.status == "completed":
        print("already completed")
        raise SystemExit(0)
    job.status = "queued"
    job.stage = "queued"
    job.progress = 0
    job.error_message = None
    job.started_at = None
    job.completed_at = None
    source.status = "indexing"
    source.enabled = False
    source.index_stage = "queued"
    source.index_progress = 0
    source.index_error = None
    job.detail = {**dict(job.detail or {}), "resumed_at": datetime.utcnow().isoformat()}
    session.commit()

process_knowledge_index_actor.send(JOB_ID)
print(f"requeued {JOB_ID}")
