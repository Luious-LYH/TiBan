"""V3.1 Knowledge lifecycle on the existing source/document/chunk graph."""

from __future__ import annotations

import os
import re
from pathlib import Path
from datetime import datetime
from uuid import uuid4

import fitz
from docx import Document
from sqlalchemy import func, select

from app.core.config import DEFAULT_DOMAIN_ID
from app.db.database import SessionLocal
from app.db.models import BackgroundJobModel, DocumentVersionModel, KnowledgeChunkModel, QuestionModel, SourceDocumentModel
from app.services.rag_service import MODEL_NAME, rag_service


KNOWLEDGE_UPLOAD_DIR = Path(os.getenv("ENDO_KNOWLEDGE_UPLOAD_DIR", Path(__file__).resolve().parents[2] / "runtime" / "knowledge"))
ALLOWED_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".md": "text/markdown",
    ".txt": "text/plain",
}
# Knowledge and Factory both use JSON + base64 at the current API boundary.
# Keep the raw payload below Nginx's 8 MiB request limit with room for base64
# expansion and JSON metadata. A future multipart contract can raise this
# independently; until then the UI must not promise 25 MiB.
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
PARSER_VERSION = "v31-section-aware-1"
LEGACY_PREFIXES = ("stage7-medical-", "stage7-general-")


class KnowledgeService:
    def list_sources(self, scope: str | None = None) -> list[dict[str, object]]:
        """Return the knowledge-library projection without touching retrieval runtime.

        Listing sources is a learner-facing read operation. It must continue to
        work when Qdrant is down, so corpus retirement and vector maintenance
        never belong on this request path.
        """
        with SessionLocal() as session:
            statement = select(SourceDocumentModel).where(SourceDocumentModel.business_usage == "knowledge_base")
            if scope:
                statement = statement.where(SourceDocumentModel.source_scope == scope)
            rows = list(session.scalars(statement.order_by(SourceDocumentModel.created_at.desc())))
            if not rows:
                return []
            latest_versions = self._latest_versions(session, [row.document_id for row in rows])
            counts = dict(session.execute(
                select(KnowledgeChunkModel.document_id, func.count(KnowledgeChunkModel.chunk_id))
                .join(latest_versions, KnowledgeChunkModel.version_id == latest_versions.c.version_id)
                .where(latest_versions.c.version_rank == 1)
                .group_by(KnowledgeChunkModel.document_id)
            ).all())
            return [self._public(row, int(counts.get(row.document_id, 0))) for row in rows]

    def detail(self, document_id: str) -> dict[str, object]:
        with SessionLocal() as session:
            row = self._document(session, document_id)
            latest_versions = self._latest_versions(session, [document_id])
            latest_version_ids = select(latest_versions.c.version_id).where(latest_versions.c.version_rank == 1)
            chunks = list(session.scalars(select(KnowledgeChunkModel).where(
                KnowledgeChunkModel.document_id == document_id,
                KnowledgeChunkModel.version_id.in_(latest_version_ids),
            ).order_by(KnowledgeChunkModel.ordinal).limit(6)))
            chunk_count = session.scalar(
                select(func.count(KnowledgeChunkModel.chunk_id))
                .join(latest_versions, KnowledgeChunkModel.version_id == latest_versions.c.version_id)
                .where(
                    latest_versions.c.version_rank == 1,
                    KnowledgeChunkModel.document_id == document_id,
                )
            )
            payload = self._public(row, int(chunk_count or 0))
            payload["preview"] = [{"section": item.parent_section, "page": item.page, "text": item.content[:700]} for item in chunks]
            return payload

    def upload(self, *, filename: str, content: bytes, content_type: str | None, domain_id: str = DEFAULT_DOMAIN_ID) -> dict[str, object]:
        suffix = Path(filename).suffix.lower()
        if suffix not in ALLOWED_TYPES:
            raise ValueError("仅支持 PDF、DOCX、Markdown 和 TXT 文件。")
        if not content or len(content) > MAX_UPLOAD_BYTES:
            raise ValueError("资料大小需在 1 B 到 5 MiB 之间。")
        if content_type and content_type not in {ALLOWED_TYPES[suffix], "application/octet-stream", "text/plain"}:
            raise ValueError("文件类型与扩展名不一致。")
        document_id = f"knowledge_{uuid4().hex[:12]}"
        safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", Path(filename).name)
        KNOWLEDGE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        source_path = KNOWLEDGE_UPLOAD_DIR / f"{document_id}_{safe_name}"
        source_path.write_bytes(content)
        with SessionLocal() as session:
            session.add(SourceDocumentModel(
                document_id=document_id, domain_id=domain_id, bank_id=None, name=Path(filename).name,
                media_type=ALLOWED_TYPES[suffix], content_hash="pending", status="queued", source_id=document_id,
                business_usage="knowledge_base", license_gate_status="allow", ai_ingestion_allowed=True,
                source_uri=str(source_path.resolve()), namespace="user", source_scope="user", file_name=Path(filename).name,
                size_bytes=len(content), enabled=False, parser_version=None, index_stage="uploaded", index_progress=5,
            ))
            session.add(DocumentVersionModel(
                version_id=f"{document_id}-pending", document_id=document_id, version_label="pending",
                source_path=str(source_path.resolve()), content_hash="pending", parser="pending", status="queued",
            ))
            session.commit()
        return self._enqueue_index(document_id, reason="upload")

    def set_enabled(self, document_id: str, enabled: bool) -> dict[str, object]:
        with SessionLocal() as session:
            row = self._document(session, document_id)
            row.enabled = enabled
            row.status = "ready" if enabled else "disabled"
            session.commit()
        return self.detail(document_id)

    def reindex(self, document_id: str) -> dict[str, object]:
        with SessionLocal() as session:
            row = self._document(session, document_id)
            version = session.scalar(select(DocumentVersionModel).where(DocumentVersionModel.document_id == document_id).order_by(DocumentVersionModel.created_at.desc()))
            if version is None or not Path(version.source_path).is_file():
                raise ValueError("原始资料文件已不可用，无法重新索引。")
        return self._enqueue_index(document_id, reason="reindex")

    def delete(self, document_id: str) -> None:
        with SessionLocal() as session:
            row = self._document(session, document_id)
            versions = list(session.scalars(select(DocumentVersionModel).where(DocumentVersionModel.document_id == document_id)))
            paths = [Path(item.source_path) for item in versions]
        try:
            self._purge(document_id, remove_document=True)
        except Exception:
            # Deleting canonical source metadata must remain possible while the
            # derived vector service is offline; next rebuild drops old points.
            with SessionLocal() as session:
                session.query(KnowledgeChunkModel).filter_by(document_id=document_id).delete(synchronize_session=False)
                session.query(DocumentVersionModel).filter_by(document_id=document_id).delete(synchronize_session=False)
                row = session.get(SourceDocumentModel, document_id)
                if row:
                    session.delete(row)
                session.commit()
        for path in paths:
            if KNOWLEDGE_UPLOAD_DIR in path.parents:
                path.unlink(missing_ok=True)
                path.with_suffix(".parsed.md").unlink(missing_ok=True)

    def ensure_cmexam_explanations(self, limit: int = 180) -> dict[str, object]:
        document_id = "source-cmexam-explanations-v31"
        with SessionLocal() as session:
            existing = session.get(SourceDocumentModel, document_id)
            if existing and existing.status == "ready":
                return self.detail(document_id)
            rows = list(session.scalars(select(QuestionModel).where(
                QuestionModel.bank_id == "bank-cmexam-real", QuestionModel.official_explanation_available.is_(True)
            ).order_by(QuestionModel.question_id).limit(limit)))
        if not rows:
            raise ValueError("CMExam 尚未导入，无法建立解析知识库。")
        KNOWLEDGE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        source_path = KNOWLEDGE_UPLOAD_DIR / "system_cmexam_explanations_v31.md"
        sections = ["# CMExam 官方解析（只读）", "来自当前 CMExam 学习题库的原始题目解析，用于学习解释与来源检索。"]
        sections += [f"## {row.question_id}\n题目：{row.stem}\n解析：{row.explanation}" for row in rows]
        source_path.write_text("\n\n".join(sections), encoding="utf-8")
        return self._index(document_id=document_id, source_path=source_path, title="CMExam 官方解析库", file_name="CMExam 官方解析（当前题库子集）.md",
                           media_type="text/markdown", scope="qbank_explanations", namespace="qbank_explanations", domain_id=DEFAULT_DOMAIN_ID,
                           attribution="CMExam · 当前学习题库中的上游题目与官方解析", source_uri="https://github.com/williamliujl/CMExam")

    def import_openrn_heart_failure_excerpt(self, pdf_path: Path) -> dict[str, object]:
        if not pdf_path.is_file():
            raise ValueError("Open RN PDF 文件不存在。")
        document_id = "source-openrn-health-alterations-heart-failure-v31"
        pdf = fitz.open(pdf_path)
        try:
            # The book's table of contents also mentions this heading. The
            # chapter itself begins in the cardiovascular pages, so choose the
            # first later heading instead of indexing the contents.
            start = next((index for index, page in enumerate(pdf) if index > 300 and "5.8 Heart Failure" in page.get_text("text")), None)
            if start is None:
                raise ValueError("未在 Open RN PDF 中定位到 Heart Failure 章节。")
            content = "\n\n".join(f"## 5.8 Heart Failure · PDF 第 {index + 1} 页\n{pdf[index].get_text('text')}" for index in range(start, min(start + 12, len(pdf))))
        finally:
            pdf.close()
        KNOWLEDGE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        source_path = KNOWLEDGE_UPLOAD_DIR / "system_openrn_health_alterations_heart_failure.md"
        source_path.write_text(content, encoding="utf-8")
        self._purge(document_id, remove_document=False)
        return self._index(document_id=document_id, source_path=source_path, title="Open RN Health Alterations · Heart Failure", file_name=pdf_path.name,
                           media_type="application/pdf", scope="system", namespace="system", domain_id="endoscopy",
                           attribution="Open RN Health Alterations by Chippewa Valley Technical College · CC BY 4.0", source_uri="https://www.ncbi.nlm.nih.gov/books/NBK613078/")

    def retire_legacy_system_corpus(self) -> int:
        """Logically retire pre-V3.1 generated corpora without requiring Qdrant.

        Derived vector points are deliberately left for explicit maintenance.
        Retrieval eligibility comes from the relational source record, so a
        stopped vector service cannot make the knowledge-library UI unavailable
        or reintroduce retired material.
        """
        with SessionLocal() as session:
            legacy = list(session.scalars(select(SourceDocumentModel).where(
                SourceDocumentModel.document_id.like("stage7-medical-%") | SourceDocumentModel.document_id.like("stage7-general-%")
            )))
            changed = False
            for row in legacy:
                if row.enabled or row.business_usage != "excluded" or row.status != "retired":
                    row.enabled = False
                    row.business_usage = "excluded"
                    row.status = "retired"
                    changed = True
            for document_id in ("source-seed-endoscopy-v1", "source-seed-general-science-v1"):
                row = session.get(SourceDocumentModel, document_id)
                if row and (row.enabled or row.business_usage != "excluded" or row.status != "retired"):
                    row.enabled = False
                    row.business_usage = "excluded"
                    row.status = "retired"
                    changed = True
            if changed:
                session.commit()
        return len(legacy)

    def _index(self, *, document_id: str, source_path: Path, title: str, file_name: str, media_type: str, scope: str, namespace: str, domain_id: str, attribution: str | None, source_uri: str | None) -> dict[str, object]:
        markdown, parser = self._parse(source_path)
        # Include this canonical source in the worker's global rebuild while
        # keeping its public status non-retrievable until the final commit.
        with SessionLocal() as session:
            pending = session.get(SourceDocumentModel, document_id)
            if pending is not None:
                # During a reindex, the previous canonical chunks and the
                # currently active Qdrant representation remain valid until a
                # complete replacement succeeds.  A new upload has no chunks
                # yet and therefore stays non-retrievable while it is built.
                has_existing_chunks = bool(session.scalar(select(func.count(KnowledgeChunkModel.chunk_id)).where(
                    KnowledgeChunkModel.document_id == document_id,
                )))
                pending.enabled = True
                pending.status = "ready" if has_existing_chunks else "indexing"
                pending.business_usage = "knowledge_base"
                pending.license_gate_status, pending.ai_ingestion_allowed = "allow", True
                session.commit()
        rag_service.index_markdown(markdown, document_id=document_id, document_name=title, domain_id=domain_id, child_size=700,
                                   namespace=namespace, source_id=document_id, source_uri=source_uri, business_usage="knowledge_base",
                                   license_gate_status="allow", ai_ingestion_allowed=True, version_label=f"{PARSER_VERSION}-700")
        with SessionLocal() as session:
            row = session.get(SourceDocumentModel, document_id)
            assert row is not None
            row.name, row.file_name, row.media_type = title, file_name, media_type
            row.source_scope, row.namespace, row.domain_id = scope, namespace, domain_id
            state = rag_service.index_state()
            row.status, row.enabled, row.business_usage = "ready", True, "knowledge_base"
            row.license_gate_status, row.ai_ingestion_allowed = "allow", True
            row.attribution, row.source_uri = attribution, source_uri or str(source_path.resolve())
            row.size_bytes, row.parser_version, row.embedding_model = source_path.stat().st_size, parser, str(state.get("model") or MODEL_NAME)
            row.embedding_provider = str(state.get("provider") or "") or None
            row.embedding_dimension = int(state["vector_dimension"]) if isinstance(state.get("vector_dimension"), int) else None
            row.index_version = int(state.get("index_version") or 0)
            row.index_stage, row.index_progress, row.index_error = "completed", 100, None
            session.commit()
        return self.detail(document_id)

    def _enqueue_index(self, document_id: str, *, reason: str) -> dict[str, object]:
        had_existing_chunks = False
        was_enabled = False
        with SessionLocal() as session:
            row = self._document(session, document_id)
            # A repeated click while an existing job is queued/running is
            # idempotent and returns the same truthful visible state.
            existing = session.scalar(select(BackgroundJobModel).where(
                BackgroundJobModel.target_id == document_id,
                BackgroundJobModel.job_type == "knowledge_index",
                BackgroundJobModel.status.in_(["queued", "running"]),
            ).order_by(BackgroundJobModel.created_at.desc()))
            if existing:
                return self.detail(document_id)
            job = BackgroundJobModel(
                job_id=f"knowledge_index_{uuid4().hex[:12]}", job_type="knowledge_index", target_id=document_id,
                status="queued", stage="queued", progress=0, idempotency_key=f"knowledge:{document_id}:{uuid4().hex[:10]}", detail={"reason": reason},
            )
            session.add(job)
            has_existing_chunks = bool(session.scalar(select(func.count(KnowledgeChunkModel.chunk_id)).where(
                KnowledgeChunkModel.document_id == document_id,
            )))
            had_existing_chunks = has_existing_chunks
            was_enabled = bool(row.enabled)
            # Reindexing is a read-safe replacement: keep a previously ready
            # source eligible while the worker prepares the new version.  A
            # first upload has no usable canonical chunks and remains hidden.
            if reason == "reindex" and has_existing_chunks and row.enabled:
                row.status, row.enabled = "ready", True
            else:
                row.status, row.enabled = ("rebuilding" if reason == "reindex" else "queued"), False
            row.index_job_id, row.index_stage, row.index_progress, row.index_error = job.job_id, "queued", 0, None
            session.commit()
        try:
            from app.workers.background_worker import process_knowledge_index_actor

            process_knowledge_index_actor.send(job.job_id)
        except Exception as exc:
            with SessionLocal() as session:
                failed_job = session.get(BackgroundJobModel, job.job_id)
                failed_row = session.get(SourceDocumentModel, document_id)
                if failed_job is not None:
                    failed_job.status, failed_job.stage = "failed", "dispatch_failed"
                    failed_job.error_message = type(exc).__name__
                    failed_job.completed_at = datetime.utcnow()
                if failed_row is not None:
                    if not (had_existing_chunks and was_enabled):
                        failed_row.status, failed_row.enabled = "failed", False
                    failed_row.index_stage, failed_row.index_progress, failed_row.index_error = "dispatch_failed", 0, type(exc).__name__
                session.commit()
        return self.detail(document_id)

    def process_index_job(self, job_id: str) -> dict[str, object]:
        previous_state: dict[str, object] = {}
        had_previous_chunks = False
        with SessionLocal() as session:
            job = session.get(BackgroundJobModel, job_id)
            if job is None or job.job_type != "knowledge_index":
                raise KeyError(job_id)
            if job.status == "completed":
                return {"job_id": job_id, "status": "completed"}
            row = self._document(session, job.target_id)
            version = session.scalar(select(DocumentVersionModel).where(DocumentVersionModel.document_id == row.document_id).order_by(DocumentVersionModel.created_at.desc()))
            if version is None or not Path(version.source_path).is_file():
                raise ValueError("原始资料文件已不可用，无法索引。")
            had_previous_chunks = bool(session.scalar(select(func.count(KnowledgeChunkModel.chunk_id)).where(
                KnowledgeChunkModel.document_id == row.document_id,
            )))
            previous_state = {
                name: getattr(row, name)
                for name in (
                    "status", "enabled", "index_stage", "index_progress", "index_error",
                    "embedding_model", "embedding_provider", "embedding_dimension", "index_version",
                )
            }
            args = dict(document_id=row.document_id, source_path=Path(version.source_path), title=row.name, file_name=row.file_name or row.name,
                        media_type=row.media_type, scope=row.source_scope, namespace=row.namespace, domain_id=row.domain_id,
                        attribution=row.attribution, source_uri=row.source_uri)
            job.status, job.stage, job.progress, job.started_at = "running", "解析文档", 15, datetime.utcnow()
            # A ready source continues to serve its old complete index during
            # replacement. New uploads with no chunks are hidden until ready.
            if not had_previous_chunks:
                row.status = "indexing"
                row.enabled = False
            row.index_stage, row.index_progress = "解析文档", 15
            session.commit()
        try:
            with SessionLocal() as session:
                job = session.get(BackgroundJobModel, job_id)
                row = self._document(session, job.target_id) if job else None
                assert job is not None and row is not None
                job.stage, job.progress = "文本切分", 35
                row.index_stage, row.index_progress = "文本切分", 35
                # Do not delete the previous canonical version here.  The
                # worker may still fail during parsing, embedding, or Qdrant
                # replacement; retaining old chunks makes retry and recovery
                # lossless.  The derived-index rebuild selects only the newest
                # successful version for retrieval.
                session.commit()
            with SessionLocal() as session:
                job = session.get(BackgroundJobModel, job_id)
                row = self._document(session, job.target_id) if job else None
                assert job is not None and row is not None
                job.stage, job.progress = "生成向量", 65
                row.index_stage, row.index_progress = "生成向量", 65
                session.commit()
            self._index(**args)
            with SessionLocal() as session:
                job = session.get(BackgroundJobModel, job_id)
                row = self._document(session, job.target_id) if job else None
                assert job is not None and row is not None
                job.status, job.stage, job.progress, job.completed_at = "completed", "完成", 100, datetime.utcnow()
                row.index_job_id, row.index_stage, row.index_progress, row.index_error = job_id, "完成", 100, None
                session.commit()
            return {"job_id": job_id, "status": "completed"}
        except Exception as exc:
            with SessionLocal() as session:
                job = session.get(BackgroundJobModel, job_id)
                row = self._document(session, job.target_id) if job else None
                if job:
                    job.status, job.stage, job.error_message, job.completed_at = "failed", "failed", type(exc).__name__, datetime.utcnow()
                if row:
                    if had_previous_chunks:
                        # The old source/index remains usable. Surface the
                        # failed replacement separately without downgrading a
                        # truthful ready state or hiding the old evidence.
                        for name, value in previous_state.items():
                            setattr(row, name, value)
                        row.index_stage, row.index_error = "failed", type(exc).__name__
                    else:
                        row.status, row.enabled, row.index_stage, row.index_error = "failed", False, "failed", type(exc).__name__
                session.commit()
            raise

    def _parse(self, source_path: Path) -> tuple[Path, str]:
        suffix = source_path.suffix.lower()
        target = source_path.with_suffix(".parsed.md")
        if suffix == ".pdf":
            pdf = fitz.open(source_path)
            try:
                text = "\n\n".join(f"## 第 {index + 1} 页\n{page.get_text('text')}" for index, page in enumerate(pdf))
            finally:
                pdf.close()
            parser = "pymupdf-page-aware"
        elif suffix == ".docx":
            text = "\n".join(paragraph.text for paragraph in Document(source_path).paragraphs if paragraph.text.strip())
            parser = "python-docx"
        else:
            text = source_path.read_text(encoding="utf-8", errors="replace")
            parser = "heading-aware-markdown" if suffix == ".md" else "utf8-text"
        if len(text.strip()) < 40:
            raise ValueError("未能从资料中解析出足够的可索引文本。")
        target.write_text(text, encoding="utf-8")
        return target, parser

    @staticmethod
    def _document(session: object, document_id: str) -> SourceDocumentModel:
        row = session.get(SourceDocumentModel, document_id)  # type: ignore[attr-defined]
        if row is None or row.business_usage != "knowledge_base":
            raise KeyError(document_id)
        return row

    @staticmethod
    def _latest_versions(session: object, document_ids: list[str]):
        """Return a ranked subquery selecting the newest version per source.

        Version rows are retained for rollback and audit.  Learner-facing
        counts/previews must describe the current canonical version only, so
        historical chunks cannot inflate the visible inventory.
        """

        return select(
            DocumentVersionModel.version_id,
            DocumentVersionModel.document_id,
            func.row_number().over(
                partition_by=DocumentVersionModel.document_id,
                order_by=(DocumentVersionModel.created_at.desc(), DocumentVersionModel.version_id.desc()),
            ).label("version_rank"),
        ).where(DocumentVersionModel.document_id.in_(document_ids)).subquery("latest_document_versions")

    @staticmethod
    def _public(row: SourceDocumentModel, chunk_count: int) -> dict[str, object]:
        return {"id": row.document_id, "title": row.name, "file_name": row.file_name or row.name, "media_type": row.media_type,
                "scope": row.source_scope, "status": row.status, "size_bytes": row.size_bytes, "chunk_count": chunk_count,
                "enabled": row.enabled, "parser_version": row.parser_version, "embedding_model": row.embedding_model,
                "embedding_provider": row.embedding_provider, "index_version": row.index_version, "index_job_id": row.index_job_id,
                "index_stage": row.index_stage, "index_progress": row.index_progress, "index_error": row.index_error,
                "attribution": row.attribution, "created_at": row.created_at, "updated_at": row.updated_at}

    @staticmethod
    def _purge(document_id: str, *, remove_document: bool) -> None:
        rag_service.delete_documents([document_id])
        with SessionLocal() as session:
            session.query(KnowledgeChunkModel).filter_by(document_id=document_id).delete(synchronize_session=False)
            session.query(DocumentVersionModel).filter_by(document_id=document_id).delete(synchronize_session=False)
            if remove_document:
                row = session.get(SourceDocumentModel, document_id)
                if row:
                    session.delete(row)
            session.commit()


knowledge_service = KnowledgeService()
