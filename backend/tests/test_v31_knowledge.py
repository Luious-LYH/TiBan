from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import fitz
import pytest
from docx import Document

from app.db.database import SessionLocal
from app.db.models import DocumentVersionModel, KnowledgeChunkModel, SourceDocumentModel
from app.services.knowledge_service import knowledge_service
from app.services.rag_service import rag_service


def test_retrieval_requires_real_lexical_relevance_dedupes_and_respects_disable() -> None:
    """A learner-facing citation must be relevant, unique and revocable.

    This deliberately uses sparse mode: it proves the policy on the canonical
    database graph without needing a running Qdrant service or an embedding
    download in the normal regression suite.
    """

    token = uuid4().hex[:10]
    document_id = f"v31-knowledge-{token}"
    version_id = f"v31-version-{token}"
    with SessionLocal() as session:
        session.add(SourceDocumentModel(
            document_id=document_id, domain_id="endoscopy", bank_id=None,
            name="真实心力衰竭学习资料", media_type="text/markdown", content_hash=token,
            status="ready", business_usage="knowledge_base", license_gate_status="allow",
            ai_ingestion_allowed=True, namespace="system", source_scope="system", enabled=True,
        ))
        session.add(DocumentVersionModel(
            version_id=version_id, document_id=document_id, version_label="test", source_path="test",
            content_hash=token, parser="test", status="indexed",
        ))
        for ordinal, content in enumerate((
            "心力衰竭患者需要结合症状、体征和检查结果进行学习复盘。",
            "心力衰竭复习要回到题干给出的证据，而不是猜测。",
        )):
            session.add(KnowledgeChunkModel(
                chunk_id=f"v31-chunk-{token}-{ordinal}", document_id=document_id, version_id=version_id,
                parent_section="心力衰竭", page=1, ordinal=ordinal, content=content,
                content_hash=f"{token}-{ordinal}", token_count=len(content), namespace="system",
            ))
        session.commit()
    try:
        citations = rag_service.retrieve("心力衰竭怎么复习", mode="sparse", document_ids=[document_id], limit=5)
        assert len(citations) == 1
        assert citations[0].document_name == "真实心力衰竭学习资料"
        assert citations[0].section == "心力衰竭"
        # Retrieval instructions and a current-question shell are not evidence
        # of a concept match.  The source does not discuss this CMExam item, so
        # learner-facing Citation must honestly stay empty.
        assert rag_service.retrieve(
            "根据资料解释当前题考点，并给出来源。\n当前题目：既补肝肾，又安胎的药是",
            mode="sparse",
            document_ids=[document_id],
            limit=5,
        ) == []
        assert rag_service.retrieve("marine biology octopus cephalopod", mode="sparse", document_ids=[document_id], limit=5) == []

        with SessionLocal() as session:
            source = session.get(SourceDocumentModel, document_id)
            assert source is not None
            source.enabled = False
            session.commit()
        assert rag_service.retrieve("心力衰竭怎么复习", mode="sparse", document_ids=[document_id], limit=5) == []
    finally:
        with SessionLocal() as session:
            session.query(KnowledgeChunkModel).filter_by(document_id=document_id).delete(synchronize_session=False)
            session.query(DocumentVersionModel).filter_by(document_id=document_id).delete(synchronize_session=False)
            source = session.get(SourceDocumentModel, document_id)
            if source is not None:
                session.delete(source)
            session.commit()


def test_knowledge_parser_supports_pdf_docx_markdown_and_txt(tmp_path: Path) -> None:
    """Every learner-facing upload format yields real indexable text.

    This is deliberately a parser contract, so it does not hide a format
    failure behind a mocked embedding or Qdrant response.
    """
    # ASCII keeps this format contract independent of the Windows console
    # code page used by local test runners. Unicode extraction is covered by
    # the real Open RN / CMExam source lifecycle instead.
    content = "Knowledge parser format verification needs enough indexable text for the learning workflow."
    samples: list[Path] = []

    markdown = tmp_path / "note.md"
    markdown.write_text(f"# Study note\n\n{content}", encoding="utf-8")
    samples.append(markdown)

    text = tmp_path / "note.txt"
    text.write_text(content, encoding="utf-8")
    samples.append(text)

    docx_path = tmp_path / "note.docx"
    document = Document()
    document.add_paragraph(content)
    document.save(docx_path)
    samples.append(docx_path)

    pdf_path = tmp_path / "note.pdf"
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((72, 72), content)
    pdf.save(pdf_path)
    pdf.close()
    samples.append(pdf_path)

    parsers = []
    for source in samples:
        parsed, parser = knowledge_service._parse(source)
        assert parsed.is_file()
        assert len(parsed.read_text(encoding="utf-8").strip()) >= 40
        parsers.append(parser)

    assert parsers == ["heading-aware-markdown", "utf8-text", "python-docx", "pymupdf-page-aware"]


def test_system_knowledge_sources_are_not_deletable() -> None:
    token = uuid4().hex[:10]
    document_id = f"v31-system-delete-{token}"
    with SessionLocal() as session:
        session.add(SourceDocumentModel(
            document_id=document_id, domain_id="endoscopy", bank_id=None,
            name="只读系统资料", media_type="text/markdown", content_hash=token,
            status="ready", business_usage="knowledge_base", license_gate_status="allow",
            ai_ingestion_allowed=True, namespace="system", source_scope="system", enabled=True,
        ))
        session.commit()
    try:
        with pytest.raises(PermissionError):
            knowledge_service.delete(document_id)
        with SessionLocal() as session:
            source = session.get(SourceDocumentModel, document_id)
            assert source is not None
            assert source.enabled is True
    finally:
        with SessionLocal() as session:
            source = session.get(SourceDocumentModel, document_id)
            if source is not None:
                session.delete(source)
            session.commit()


def test_listing_sources_never_requires_qdrant_and_legacy_retirement_is_logical(monkeypatch) -> None:
    """The catalogue stays readable when the derived vector service is offline."""
    token = uuid4().hex[:10]
    document_id = f"stage7-medical-performance-{token}"
    calls: list[tuple[object, ...]] = []

    def forbidden_vector_delete(*args: object, **kwargs: object) -> None:
        calls.append(args)
        raise AssertionError("listing or retirement must not delete vectors")

    monkeypatch.setattr(rag_service, "delete_documents", forbidden_vector_delete)
    with SessionLocal() as session:
        session.add(SourceDocumentModel(
            document_id=document_id, domain_id="endoscopy", bank_id=None,
            name="已退役的旧系统资料", media_type="text/markdown", content_hash=token,
            status="ready", business_usage="knowledge_base", license_gate_status="allow",
            ai_ingestion_allowed=True, namespace="system", source_scope="system", enabled=True,
        ))
        session.commit()
    try:
        # ``list_sources`` is a pure relational read. It must not depend on a
        # reachable Qdrant instance or perform write-side retirement work.
        assert any(item["id"] == document_id for item in knowledge_service.list_sources())
        assert calls == []

        knowledge_service.retire_legacy_system_corpus()
        with SessionLocal() as session:
            retired = session.get(SourceDocumentModel, document_id)
            assert retired is not None
            assert retired.enabled is False
            assert retired.business_usage == "excluded"
            assert retired.status == "retired"
        assert all(item["id"] != document_id for item in knowledge_service.list_sources())
        assert calls == []
        # Sparse retrieval uses the same relational eligibility graph, proving
        # an old Qdrant point cannot become a learner-facing candidate.
        assert rag_service.retrieve("任何查询", mode="sparse", document_ids=[document_id], limit=5) == []
    finally:
        with SessionLocal() as session:
            source = session.get(SourceDocumentModel, document_id)
            if source is not None:
                session.delete(source)
            session.commit()
