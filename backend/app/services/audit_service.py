from datetime import datetime, timezone
from uuid import uuid4

from app.schemas import AuditLog
from app.services.data_store import read_json, write_json


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class AuditService:
    def list_logs(self) -> list[AuditLog]:
        return [AuditLog(**item) for item in read_json("audit_logs.json")]

    def log(
        self,
        event_type: str,
        user_id: str,
        summary: str,
        risk_level: str = "low",
        entity_id: str | None = None,
        doctor_review_required: bool = True,
        metadata: dict[str, object] | None = None,
    ) -> AuditLog:
        log = AuditLog(
            id=f"audit_{uuid4().hex[:12]}",
            event_type=event_type,
            user_id=user_id,
            entity_id=entity_id,
            summary=summary,
            risk_level=risk_level,
            doctor_review_required=doctor_review_required,
            metadata=metadata or {},
            created_at=now_iso(),
        )
        logs = read_json("audit_logs.json")
        logs.insert(0, log.model_dump())
        write_json("audit_logs.json", logs[:200])
        return log


audit_service = AuditService()
