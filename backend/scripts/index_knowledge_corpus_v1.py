"""Index the license-gated Knowledge Corpus v1 into PostgreSQL and Qdrant.

This is deliberately an explicit operator command rather than import-time
application behaviour.  It only accepts documents whose source entry is
currently allowed for AI ingestion, records the stable corpus/version lineage
in PostgreSQL, and emits an artifact with no secrets or local absolute paths.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml


BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.db.database import SessionLocal
from app.db.models import DocumentVersionModel, KnowledgeChunkModel, SourceDocumentModel
from app.services.data_governance import source_can_enter_tutor, tutor_namespace_allowed
from app.services.rag_service import rag_service


CORPUS_ID = "knowledge-corpus-v1"
VERSION_LABEL = "knowledge-corpus-v1-child-180"
CHILD_SIZE = 180


def _source_registry() -> dict[str, dict[str, object]]:
    registry_path = PROJECT_ROOT / "knowledge" / "registry" / "sources.yaml"
    parsed = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict) or not isinstance(parsed.get("sources"), list):
        raise ValueError("knowledge source registry is malformed")
    return {
        str(item["source_id"]): item
        for item in parsed["sources"]
        if isinstance(item, dict) and item.get("source_id")
    }


def _load_manifest() -> dict[str, object]:
    path = PROJECT_ROOT / "knowledge" / "corpus-v1" / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("corpus_id") != CORPUS_ID or not isinstance(manifest.get("documents"), list):
        raise ValueError("knowledge corpus manifest is not corpus-v1")
    return manifest


def _gate_source(source: dict[str, object], namespace: str) -> None:
    status = str(source.get("status", "needs_review"))
    allowed = source_can_enter_tutor(
        business_usage="knowledge_base",
        license_gate_status=status,
        ai_ingestion_allowed=source.get("ai_ingestion_allowed") is True,
    )
    if not allowed:
        raise PermissionError(f"source registry blocks Tutor ingestion: {source.get('source_id')}")
    if not tutor_namespace_allowed(namespace):
        raise PermissionError(f"unapproved Tutor namespace: {namespace}")


def index_corpus(*, dry_run: bool = False) -> dict[str, object]:
    manifest = _load_manifest()
    source_id = str(dict(manifest["license_gate"])["source_id"])
    source = _source_registry().get(source_id)
    if source is None:
        raise KeyError(f"corpus source is missing from registry: {source_id}")

    documents = list(manifest["documents"])
    indexed: list[dict[str, object]] = []
    for item in documents:
        if not isinstance(item, dict):
            raise ValueError("manifest contains a non-object document")
        document_id = str(item["document_id"])
        namespace = str(item["namespace"])
        _gate_source(source, namespace)
        path = PROJECT_ROOT / str(item["path"])
        if not path.is_file():
            raise FileNotFoundError(path)
        if dry_run:
            indexed.append({"document_id": document_id, "namespace": namespace, "source_url": item["source_url"]})
            continue
        chunk_ids = rag_service.index_markdown(
            path,
            document_id=document_id,
            child_size=CHILD_SIZE,
            namespace=namespace,
            source_id=source_id,
            source_uri=str(item["source_url"]),
            business_usage="knowledge_base",
            license_gate_status=str(source["status"]),
            ai_ingestion_allowed=True,
            version_label=VERSION_LABEL,
        )
        indexed.append({
            "document_id": document_id,
            "namespace": namespace,
            "source_url": item["source_url"],
            "content_hash": item["content_hash"],
            "chunk_count": len(chunk_ids),
        })

    with SessionLocal() as session:
        document_ids = [str(item["document_id"]) for item in documents if isinstance(item, dict)]
        persisted = list(session.query(SourceDocumentModel).filter(SourceDocumentModel.document_id.in_(document_ids)))
        version_ids = list(session.query(DocumentVersionModel).filter(DocumentVersionModel.document_id.in_(document_ids)))
        chunk_count = session.query(KnowledgeChunkModel).filter(KnowledgeChunkModel.document_id.in_(document_ids)).count()
    result = {
        "artifact_version": "knowledge-corpus-v1-index-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "corpus_id": CORPUS_ID,
        "manifest_document_count": len(documents),
        "indexed_document_count": len(indexed),
        "persisted_document_count": len(persisted),
        "version_count": len(version_ids),
        "chunk_count": chunk_count,
        "namespace": "endoscopy",
        "source_id": source_id,
        "license_gate_status": str(source["status"]),
        "qdrant_collection": "endotutor_chunks_v1",
        "dry_run": dry_run,
        "documents": indexed,
    }
    if not dry_run:
        artifact_dir = PROJECT_ROOT / "artifacts" / "knowledge"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        (artifact_dir / "knowledge-corpus-v1-index.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="verify corpus and license gates without indexing")
    args = parser.parse_args()
    print(json.dumps(index_corpus(dry_run=args.dry_run), ensure_ascii=False, indent=2))
