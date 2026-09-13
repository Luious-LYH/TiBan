from __future__ import annotations

from uuid import uuid4

import pytest

from app.db.database import SessionLocal
from app.db.models import KnowledgeFolderModel, SourceDocumentModel
from app.services.knowledge_service import knowledge_service
from app.services.rag_service import rag_service


def test_knowledge_folder_lifecycle_and_document_move() -> None:
    token = uuid4().hex[:10]
    folder_name = f"面试资料-{token}"
    document_id = f"folder-source-{token}"
    folder = knowledge_service.create_folder(name=folder_name, description="测试目录")
    folder_id = str(folder["id"])
    try:
        with SessionLocal() as session:
            session.add(SourceDocumentModel(
                document_id=document_id,
                domain_id="endoscopy",
                name="目录移动测试资料",
                media_type="text/markdown",
                content_hash=token,
                status="ready",
                business_usage="knowledge_base",
                license_gate_status="allow",
                ai_ingestion_allowed=True,
                namespace="user",
                source_scope="user",
                folder_id=folder_id,
                enabled=True,
            ))
            session.commit()

        assert any(item["id"] == folder_id and item["source_count"] == 1 for item in knowledge_service.list_folders())
        with pytest.raises(ValueError, match="先将资料移到其他目录"):
            knowledge_service.delete_folder(folder_id)

        moved = knowledge_service.update_source(document_id, folder_id="folder-my-materials")
        assert moved["folder_id"] == "folder-my-materials"
        knowledge_service.delete_folder(folder_id)
        assert all(item["id"] != folder_id for item in knowledge_service.list_folders())
    finally:
        with SessionLocal() as session:
            source = session.get(SourceDocumentModel, document_id)
            if source is not None:
                source.folder_id = "folder-my-materials"
                session.delete(source)
            folder_row = session.get(KnowledgeFolderModel, folder_id)
            if folder_row is not None:
                session.delete(folder_row)
            session.commit()


def test_system_knowledge_folder_cannot_be_deleted() -> None:
    with pytest.raises(PermissionError):
        knowledge_service.delete_folder("folder-system")


def test_retrieval_cache_is_bounded_runtime_only_and_clearable() -> None:
    rag_service.clear_retrieval_cache()
    rag_service._store_retrieval("unit-test-key", ("citation-metadata",))
    assert rag_service._cached_retrieval("unit-test-key") == ("citation-metadata",)
    rag_service.clear_retrieval_cache()
    assert rag_service._cached_retrieval("unit-test-key") is None


def test_legacy_clinical_guideline_index_is_withheld_until_structured_processing() -> None:
    document_id = f"legacy-guideline-{uuid4().hex[:10]}"
    try:
        with SessionLocal() as session:
            session.add(SourceDocumentModel(
                document_id=document_id,
                domain_id="endoscopy",
                name="旧版临床资料",
                media_type="application/pdf",
                content_hash="legacy",
                status="ready",
                business_usage="knowledge_base",
                license_gate_status="allow",
                ai_ingestion_allowed=True,
                namespace="system",
                source_scope="system",
                folder_id="folder-clinical-guidelines",
                enabled=True,
                parser_version="pymupdf-page-aware",
                parse_stats={},
                index_stage="完成",
                index_progress=100,
            ))
            session.commit()

        assert knowledge_service.quarantine_legacy_guideline_indexes() >= 1
        with SessionLocal() as session:
            row = session.get(SourceDocumentModel, document_id)
            assert row is not None
            assert row.enabled is False
            assert row.status == "queued"
            assert row.index_stage == "待处理"
    finally:
        with SessionLocal() as session:
            row = session.get(SourceDocumentModel, document_id)
            if row is not None:
                session.delete(row)
                session.commit()
