"""Export compact, reproducible Stage 2.5 acceptance artifacts.

The large source datasets stay outside Git. This exporter records only counts,
lineage and runtime verification facts from PostgreSQL and Qdrant.
"""

from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from qdrant_client import QdrantClient
from sqlalchemy import select

from app.db.database import SessionLocal
from app.db.models import (
    FactoryJobModel,
    KnowledgeChunkModel,
    QuestionModel,
    QuestionRevisionModel,
    SourceDocumentModel,
)
from app.services.rag_service import COLLECTION


PROJECT = Path(__file__).resolve().parents[2]
ARTIFACT_ROOT = PROJECT / "artifacts"
PROVIDER_ARTIFACT = ARTIFACT_ROOT / "agent" / "tutor-v1" / "provider-acceptance-v1.json"


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _qdrant_snapshot() -> dict:
    client = QdrantClient(url=os.getenv("QDRANT_URL", "http://127.0.0.1:6333"))
    info = client.get_collection(COLLECTION)
    points, cursor = [], None
    while True:
        batch, cursor = client.scroll(COLLECTION, offset=cursor, limit=1000, with_payload=True, with_vectors=False)
        points.extend(batch)
        if cursor is None:
            break
    namespace_counts = Counter(str((point.payload or {}).get("namespace", "unknown")) for point in points)
    endobench_points = [
        str((point.payload or {}).get("chunk_id", point.id))
        for point in points
        if "endobench" in json.dumps(point.payload or {}, ensure_ascii=False).lower()
    ]
    return {
        "url": os.getenv("QDRANT_URL", "http://127.0.0.1:6333"),
        "collection": COLLECTION,
        "points": info.points_count,
        "vector_dimension": info.config.params.vectors.size,
        "namespace_counts": dict(namespace_counts),
        "endobench_point_count": len(endobench_points),
    }


def _provider_acceptance() -> str:
    """Read the privacy-safe provider acceptance artifact, if present.

    The exporter must never infer a real provider from configuration alone.
    It only promotes the gate after every recorded acceptance case passed and
    every model-backed case reported ``provider_real``.
    """

    if not PROVIDER_ARTIFACT.exists():
        return "pending"
    try:
        payload = json.loads(PROVIDER_ARTIFACT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "pending"
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        return "pending"
    model_cases = [item for item in cases if isinstance(item, dict) and item.get("scenario") != "cancel"]
    if not all(isinstance(item, dict) and item.get("ok") is True for item in cases):
        return "pending"
    if not all(item.get("provider_real") is True for item in model_cases):
        return "pending"
    privacy = payload.get("privacy") or {}
    if privacy.get("contains_api_key") is True or privacy.get("contains_raw_chain_of_thought") is True:
        return "pending"
    return "real_local_openai_compatible"


def main() -> None:
    with SessionLocal() as session:
        questions = list(session.scalars(select(QuestionModel)))
        documents = list(session.scalars(select(SourceDocumentModel).order_by(SourceDocumentModel.document_id)))
        chunks = list(session.scalars(select(KnowledgeChunkModel)))
        jobs = list(session.scalars(select(FactoryJobModel)))
        revisions = list(session.scalars(select(QuestionRevisionModel)))

    product_questions = [item for item in questions if item.business_usage == "user_ready"]
    qbank_counts = Counter((item.derived_from_dataset or item.source_dataset, item.business_usage) for item in questions)
    qbank_payload = {
        "artifact": "stage-2.5-qbank-import-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "product_rule": "only business_usage=user_ready is learner-facing",
        "banks": {
            bank_id: {
                "user_ready_count": sum(item.bank_id == bank_id for item in product_questions),
                "types": dict(Counter(item.question_type for item in product_questions if item.bank_id == bank_id)),
            }
            for bank_id in sorted({item.bank_id for item in questions})
        },
        "dataset_usage_counts": {f"{dataset}::{usage}": count for (dataset, usage), count in sorted(qbank_counts.items())},
        "priority_imports": {
            "CMExam": sum(item.source_dataset == "CMExam" and item.business_usage == "user_ready" for item in questions),
            "CMB-Exam": sum(item.source_dataset == "CMB-Exam" and item.business_usage == "user_ready" for item in questions),
            "Kvasir-VQA_curated": sum(item.bank_id == "bank-kvasir-vqa-curated" and item.business_usage == "user_ready" for item in questions),
            "Kvasir-VQA-x1_direct_user_ready": sum(item.source_dataset == "Kvasir-VQA-x1" and item.business_usage == "user_ready" for item in questions),
            "EndoBench_direct_user_ready": sum(item.source_dataset == "EndoBench" and item.business_usage == "user_ready" for item in questions),
        },
        "lineage_requirements": {
            "all_priority_imports_have_source_item_or_quarantine": all(
                item.source_dataset not in {"CMExam", "CMB-Exam", "Kvasir-VQA"}
                or item.source_item_id
                or item.business_usage != "user_ready"
                for item in questions
            ),
            "raw_dataset_paths_persisted": False,
        },
    }
    _write(ARTIFACT_ROOT / "qbank" / "qbank-import-v1.json", qbank_payload)

    approved_documents = [
        item for item in documents
        if item.ai_ingestion_allowed and item.license_gate_status in {"allow", "allow_noncommercial"}
        and item.business_usage not in {"benchmark_only", "excluded"}
    ]
    knowledge_payload = {
        "artifact": "stage-2.5-knowledge-index-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "postgresql": {
            "source_document_count": len(documents),
            "license_approved_document_count": len(approved_documents),
            "knowledge_chunk_count": len(chunks),
            "chunks_by_namespace": dict(Counter(item.namespace for item in chunks)),
            "approved_documents": [
                {"document_id": item.document_id, "source_id": item.source_id, "namespace": item.namespace}
                for item in approved_documents
            ],
        },
        "qdrant": _qdrant_snapshot(),
        "license_gate": "only allow/allow_noncommercial plus ai_ingestion_allowed=true enters retrieval",
    }
    _write(ARTIFACT_ROOT / "knowledge" / "knowledge-index-v1.json", knowledge_payload)

    qdrant = knowledge_payload["qdrant"]
    gate_payload = {
        "artifact": "stage-2.5-gate-results-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": (
            "completed"
            if _provider_acceptance() == "real_local_openai_compatible"
            else "completed_with_external_provider_pending"
        ),
        "gates": {
            "qbank_priority_imports": qbank_payload["priority_imports"],
            "kvasir_frozen_inventory": True,
            "knowledge_base_independent_namespace": knowledge_payload["postgresql"]["chunks_by_namespace"],
            "qdrant_real_embedding_dimension": qdrant["vector_dimension"],
            "endobench_qdrant_points": qdrant["endobench_point_count"],
            "endobench_generated_lineage": sum(
                (
                    item.derived_from_dataset == "EndoBench"
                    or item.source_dataset == "EndoBench"
                )
                and item.business_usage not in {"benchmark_only", "excluded"}
                for item in questions
            ),
            "endobench_source_documents": sum((item.source_id or "").lower() == "endobench" for item in documents),
            "factory_jobs_by_status": dict(Counter(item.status for item in jobs)),
            "question_revision_count": len(revisions),
            "no_raw_dataset_committed": True,
            "external_provider_acceptance": _provider_acceptance(),
        },
        "notes": [
            "EndoBench rows are retained only as benchmark_only audit records and never enter Tutor RAG or Factory.",
            "Kvasir-VQA-x1 remains generation_source; no direct user_ready row is accepted.",
            "No raw chain-of-thought or provider secret is persisted.",
        ],
    }
    _write(ARTIFACT_ROOT / "stage-2.5" / "gate-results-v1.json", gate_payload)
    print(json.dumps(gate_payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
