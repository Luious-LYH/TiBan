"""V3.1 Knowledge lifecycle on the existing source/document/chunk graph."""

from __future__ import annotations

import os
import re
import hashlib
import shutil
from dataclasses import asdict
from pathlib import Path
from typing import Callable
from datetime import datetime, timedelta
from uuid import uuid4

import fitz
from docx import Document
from sqlalchemy import func, select

from app.core.config import (
    DEFAULT_DOMAIN_ID,
    DEFAULT_MULTIMODAL_KNOWLEDGE_SAMPLE_PATH,
    DEFAULT_MULTIMODAL_KNOWLEDGE_SOURCE_ID,
    KNOWLEDGE_EXTERNAL_GUIDES_DIR,
)
from app.db.database import SessionLocal
from app.db.models import BackgroundJobModel, DocumentVersionModel, KnowledgeChunkModel, KnowledgeFolderModel, KnowledgeMediaAssetModel, QuestionBankModel, QuestionModel, SourceDocumentModel
from app.services.rag_service import MODEL_NAME, rag_service
from app.services.knowledge_multimodal_service import knowledge_multimodal_service, pdf_has_usable_text
from app.services.document_parser import ParsedDocument, parse_document


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
DEFAULT_MULTIMODAL_KNOWLEDGE_TITLE = "消化道内镜图像记录建议"
DEFAULT_MULTIMODAL_KNOWLEDGE_FILE_NAME = "Image Documentation in Gastrointestinal Endoscopy - Review of Recommendations.pdf"
DEFAULT_MULTIMODAL_KNOWLEDGE_ATTRIBUTION = "Image Documentation in Gastrointestinal Endoscopy: Review of Recommendations；Susana Marques 等；CC BY-NC-ND 4.0"
DEFAULT_MULTIMODAL_KNOWLEDGE_URI = "https://doi.org/10.1159/000477739"
KNOWLEDGE_CLINICAL_GUIDELINES_FOLDER_ID = "folder-clinical-guidelines"
KNOWLEDGE_USER_FOLDER_ID = "folder-my-materials"
KNOWLEDGE_QBANK_FOLDER_ID = "folder-qbank-explanations"
CLINICAL_GUIDELINE_KEEP_NAMES = {
    "临床诊疗指南_消化系统疾病分册2004中华医学会",
    "临床诊疗指南_肠外肠内营养分册",
    "临床诊疗指南_内科学分册",
    "临床诊疗指南_外科学分册",
    "临床诊疗指南-急诊医学分册2009中华医学会",
    "临床诊疗指南_呼吸病学分册",
    "临床诊疗指南_传染病学分册",
    "临床诊疗指南_心血管分册",
    "临床诊疗指南_神经病学分册",
    "临床诊疗指南-血液学分册2006中华医学会",
    "临床诊疗指南_免疫学分册",
    "临床诊疗指南_风湿病分册",
}
_UNSET = object()


def _public_vector_error(exc: Exception) -> str:
    """Return a learner-safe reason while retaining the real retry boundary.

    The raw exception can include implementation-specific transport details.
    The product needs a useful next action instead of a misleading completed
    state or an opaque exception class.
    """

    detail = str(exc).lower()
    if "embedding_" in detail or "connection" in detail or "timeout" in detail or "responsehandling" in detail:
        return "正文已解析，资料搜索索引暂时未完成；可稍后重新索引资料。"
    return "正文已解析，资料搜索索引暂时未完成；可稍后重新索引资料。"


def _public_index_error(exc: Exception) -> str:
    """Keep the actual learner-actionable failure without leaking internals."""
    detail = " ".join(str(exc).split()).strip()
    if isinstance(exc, ValueError) and detail:
        return detail[:320]
    if any(token in detail.lower() for token in ("api_key", "authorization", "secret", "password")):
        return "处理失败：服务配置未完成，请检查后重试。"
    return detail[:320] or type(exc).__name__


class KnowledgeService:
    def search(self, *, query: str, domain_id: str | None, limit: int) -> dict[str, object]:
        result = rag_service.retrieve_multimodal(query, limit=limit, domain_id=domain_id, include_images=True, include_graph=True)
        citations = []
        for item in result.get("citations", []):
            payload = asdict(item) if hasattr(item, "__dataclass_fields__") else dict(item)
            payload["media_asset_ids"] = list(payload.get("media_asset_ids") or [])
            payload["image_urls"] = list(payload.get("image_urls") or [])
            citations.append(payload)
        return {**result, "citations": citations}

    @staticmethod
    def resolve_media_path(asset_id: str) -> Path:
        return knowledge_multimodal_service.resolve_path(asset_id)

    @staticmethod
    def media_asset(asset_id: str) -> dict[str, object]:
        return knowledge_multimodal_service.public_asset(asset_id)

    def list_sources(self, scope: str | None = None) -> list[dict[str, object]]:
        """Return the knowledge-library projection without touching retrieval runtime.

        Listing sources is a learner-facing read operation. It must continue to
        work when Qdrant is down, so corpus retirement and vector maintenance
        never belong on this request path.
        """
        with SessionLocal() as session:
            statement = select(SourceDocumentModel).where(
                SourceDocumentModel.business_usage == "knowledge_base",
                SourceDocumentModel.status != "deleted",
            )
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
            folders = {
                item.folder_id: item
                for item in session.scalars(select(KnowledgeFolderModel).where(
                    KnowledgeFolderModel.folder_id.in_({row.folder_id for row in rows if row.folder_id})
                ))
            }
            return [self._public(row, int(counts.get(row.document_id, 0)), folders.get(row.folder_id)) for row in rows]

    def list_folders(self) -> list[dict[str, object]]:
        """Return the durable folder catalog without touching vector services."""

        with SessionLocal() as session:
            folders = list(session.scalars(select(KnowledgeFolderModel).order_by(
                KnowledgeFolderModel.display_order,
                KnowledgeFolderModel.created_at,
                KnowledgeFolderModel.folder_id,
            )))
            counts = dict(session.execute(
                select(SourceDocumentModel.folder_id, func.count(SourceDocumentModel.document_id))
                .where(
                    SourceDocumentModel.business_usage == "knowledge_base",
                    SourceDocumentModel.status != "deleted",
                )
                .group_by(SourceDocumentModel.folder_id)
            ).all())
            return [self._folder_public(row, int(counts.get(row.folder_id, 0))) for row in folders]

    def create_folder(self, *, name: str, description: str = "", scope: str = "user") -> dict[str, object]:
        clean_name = self._validate_folder_name(name)
        if scope not in {"user", "qbank_explanations"}:
            raise ValueError("资料目录范围不受支持。")
        with SessionLocal() as session:
            if session.scalar(select(KnowledgeFolderModel).where(KnowledgeFolderModel.name == clean_name)) is not None:
                raise ValueError("已存在同名资料目录，请换一个名称。")
            last_order = session.scalar(select(func.max(KnowledgeFolderModel.display_order))) or 0
            row = KnowledgeFolderModel(
                folder_id=f"folder_{uuid4().hex[:16]}",
                name=clean_name,
                description=description.strip()[:500],
                scope=scope,
                is_system=False,
                display_order=int(last_order) + 10,
            )
            session.add(row)
            session.commit()
            return self._folder_public(row, 0)

    def update_folder(self, folder_id: str, *, name: str | None = None, description: str | None = None) -> dict[str, object]:
        with SessionLocal() as session:
            row = session.get(KnowledgeFolderModel, folder_id)
            if row is None:
                raise KeyError(folder_id)
            if name is not None:
                clean_name = self._validate_folder_name(name)
                duplicate = session.scalar(select(KnowledgeFolderModel).where(
                    KnowledgeFolderModel.name == clean_name,
                    KnowledgeFolderModel.folder_id != folder_id,
                ))
                if duplicate is not None:
                    raise ValueError("已存在同名资料目录，请换一个名称。")
                row.name = clean_name
            if description is not None:
                row.description = description.strip()[:500]
            session.commit()
            count = session.scalar(select(func.count(SourceDocumentModel.document_id)).where(
                SourceDocumentModel.folder_id == folder_id,
                SourceDocumentModel.business_usage == "knowledge_base",
            )) or 0
            return self._folder_public(row, int(count))

    def delete_folder(self, folder_id: str) -> None:
        with SessionLocal() as session:
            row = session.get(KnowledgeFolderModel, folder_id)
            if row is None:
                raise KeyError(folder_id)
            if row.is_system:
                raise PermissionError(folder_id)
            count = session.scalar(select(func.count(SourceDocumentModel.document_id)).where(
                SourceDocumentModel.folder_id == folder_id,
                SourceDocumentModel.business_usage == "knowledge_base",
            )) or 0
            if count:
                raise ValueError("目录中仍有资料，请先将资料移到其他目录后再删除。")
            session.delete(row)
            session.commit()

    def update_source(self, document_id: str, *, enabled: bool | None = None, folder_id: object = _UNSET) -> dict[str, object]:
        with SessionLocal() as session:
            row = self._document(session, document_id)
            if enabled is not None:
                if enabled:
                    latest_versions = self._latest_versions(session, [document_id])
                    usable_chunks = int(session.scalar(
                        select(func.count(KnowledgeChunkModel.chunk_id))
                        .join(latest_versions, KnowledgeChunkModel.version_id == latest_versions.c.version_id)
                        .where(
                            latest_versions.c.version_rank == 1,
                            KnowledgeChunkModel.document_id == document_id,
                            KnowledgeChunkModel.content.is_not(None),
                        )
                    ) or 0)
                    if usable_chunks <= 0:
                        raise ValueError("资料尚未完成正文索引，完成后才能启用。")
                    row.enabled, row.status = True, "ready"
                else:
                    row.enabled, row.status = False, "disabled"
            if folder_id is not _UNSET:
                if folder_id is None:
                    row.folder_id = None
                else:
                    folder = session.get(KnowledgeFolderModel, str(folder_id))
                    if folder is None:
                        raise ValueError("目标资料目录不存在。")
                    if folder.scope != row.source_scope:
                        raise ValueError("资料只能移动到同一资料范围的目录。")
                    row.folder_id = folder.folder_id
            session.commit()
        rag_service.clear_retrieval_cache()
        return self.detail(document_id)

    def sync_local_guidelines(self, directory: Path | None = None, *, enqueue: bool = False) -> dict[str, object]:
        """Register every supported file in the local clinical-guideline folder.

        The source directory is deliberately local-only.  This method creates
        one durable source per file, keeps unchanged sources idempotent, and
        sends new/changed files through the same knowledge-index worker used by
        normal uploads.  Unsupported legacy formats are reported to the caller
        instead of being silently mislabeled as indexed content.
        """

        root = (directory or KNOWLEDGE_EXTERNAL_GUIDES_DIR).expanduser().resolve()
        if not root.is_dir():
            return {"folder_id": KNOWLEDGE_CLINICAL_GUIDELINES_FOLDER_ID, "directory_found": False, "created": 0, "queued": 0, "unchanged": 0, "ignored": [], "errors": []}
        with SessionLocal() as session:
            folder = session.get(KnowledgeFolderModel, KNOWLEDGE_CLINICAL_GUIDELINES_FOLDER_ID)
            if folder is None:
                folder = KnowledgeFolderModel(
                    folder_id=KNOWLEDGE_CLINICAL_GUIDELINES_FOLDER_ID,
                    name="临床诊疗指南",
                    description="本机导入的临床诊疗与教学参考资料。",
                    scope="user",
                    is_system=False,
                    display_order=10,
                )
                session.add(folder)
                session.commit()

        created = queued = unchanged = 0
        ignored: list[str] = []
        errors: list[dict[str, str]] = []
        supported = set(ALLOWED_TYPES)
        # Older versions wrote normalized projections beside the original
        # guide.  They look like ordinary Markdown files on the next startup,
        # so remove only those known derived records before scanning the
        # directory.  Real source files are never deleted here.
        with SessionLocal() as session:
            derived_ids = list(session.scalars(select(SourceDocumentModel.document_id).where(
                SourceDocumentModel.folder_id == KNOWLEDGE_CLINICAL_GUIDELINES_FOLDER_ID,
                SourceDocumentModel.file_name.like("%.parsed.md"),
                SourceDocumentModel.source_uri.like("local://临床诊疗指南/%"),
            )))
        for derived_id in derived_ids:
            self._purge(derived_id, remove_document=True)

        # Keep the curated local catalog small while retaining every original
        # file on disk.  These rows become durable tombstones, so a later
        # startup cannot silently put removed references back into retrieval.
        with SessionLocal() as session:
            retired_ids = list(session.scalars(select(SourceDocumentModel.document_id).where(
                SourceDocumentModel.folder_id == KNOWLEDGE_CLINICAL_GUIDELINES_FOLDER_ID,
                SourceDocumentModel.status != "deleted",
                SourceDocumentModel.name.not_in(CLINICAL_GUIDELINE_KEEP_NAMES),
            )))
        for retired_id in retired_ids:
            self._retire_source(retired_id)

        for path in sorted((item for item in root.iterdir() if item.is_file()), key=lambda item: item.name.casefold()):
            # A normalized projection is an implementation artifact, not a
            # second user document.  Keep it out of the system library even if
            # an older run left the file beside its source.
            if path.name.lower().endswith(".parsed.md"):
                ignored.append(path.name)
                continue
            suffix = path.suffix.lower()
            if suffix not in supported:
                ignored.append(path.name)
                continue
            if path.stem not in CLINICAL_GUIDELINE_KEEP_NAMES:
                ignored.append(path.name)
                continue
            try:
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                stable_key = hashlib.sha256(path.name.casefold().encode("utf-8")).hexdigest()[:16]
                document_id = f"knowledge-clinical-{stable_key}"
                needs_index = False
                with SessionLocal() as session:
                    row = session.get(SourceDocumentModel, document_id)
                    if row is None:
                        row = SourceDocumentModel(
                            document_id=document_id,
                            domain_id=DEFAULT_DOMAIN_ID,
                            bank_id=None,
                            folder_id=KNOWLEDGE_CLINICAL_GUIDELINES_FOLDER_ID,
                            name=path.stem,
                            media_type=ALLOWED_TYPES[suffix],
                            content_hash=digest,
                            status="queued",
                            source_id=document_id,
                            business_usage="knowledge_base",
                            license_gate_status="allow",
                            ai_ingestion_allowed=True,
                            source_uri=f"local://临床诊疗指南/{path.name}",
                            namespace="system",
                            attribution="本机导入资料 · 临床诊疗指南",
                            source_scope="system",
                            file_name=path.name,
                            size_bytes=path.stat().st_size,
                            enabled=False,
                            index_stage="等待处理",
                            index_progress=0,
                        )
                        session.add(row)
                        created += 1
                        needs_index = True
                    elif row.status == "deleted":
                        # A learner may intentionally remove a system source
                        # from the library.  Startup sync must not resurrect
                        # it merely because the original local file remains.
                        unchanged += 1
                    else:
                        chunk_count = int(session.scalar(select(func.count(KnowledgeChunkModel.chunk_id)).where(
                            KnowledgeChunkModel.document_id == document_id,
                        )) or 0)
                        needs_repair = (
                            row.status in {"queued", "failed"}
                            or (row.status == "ready" and chunk_count == 0)
                            or (row.image_count > 0 and row.image_index_status == "empty")
                            or not isinstance(row.parse_stats, dict)
                            or int((row.parse_stats or {}).get("page_count") or 0) == 0
                        )
                        if row.content_hash != digest or row.folder_id != KNOWLEDGE_CLINICAL_GUIDELINES_FOLDER_ID or needs_repair:
                            row.folder_id = KNOWLEDGE_CLINICAL_GUIDELINES_FOLDER_ID
                            row.namespace = "user"
                            row.source_scope = "user"
                            row.content_hash = digest
                            row.file_name = path.name
                            row.media_type = ALLOWED_TYPES[suffix]
                            row.size_bytes = path.stat().st_size
                            row.source_uri = f"local://临床诊疗指南/{path.name}"
                            row.status = "queued"
                            row.business_usage = "knowledge_base"
                            row.enabled = False
                            row.index_stage = "等待处理"
                            row.index_progress = 0
                            row.index_error = None
                            needs_index = True
                        else:
                            row.folder_id = KNOWLEDGE_CLINICAL_GUIDELINES_FOLDER_ID
                            row.namespace = "user"
                            row.source_scope = "user"
                            unchanged += 1
                    if needs_index:
                        version_id = f"{document_id}-{digest[:12]}"
                        if session.get(DocumentVersionModel, version_id) is None:
                            session.add(DocumentVersionModel(
                                version_id=version_id,
                                document_id=document_id,
                                version_label=f"{PARSER_VERSION}-{digest[:8]}",
                                source_path=str(path),
                                content_hash=digest,
                                parser="pending",
                                status="queued",
                            ))
                    session.commit()
                if needs_index:
                    queued += 1
                    if enqueue:
                        self._enqueue_index(document_id, reason="clinical_guidelines_sync")
            except Exception as exc:
                errors.append({"file_name": path.name, "error": type(exc).__name__})
        return {
            "folder_id": KNOWLEDGE_CLINICAL_GUIDELINES_FOLDER_ID,
            "directory_found": True,
            "directory_name": root.name,
            "created": created,
            "queued": queued,
            "unchanged": unchanged,
            "ignored": ignored,
            "errors": errors,
        }

    def register_local_source(
        self,
        source_path: Path,
        *,
        title: str | None = None,
        folder_id: str | None = KNOWLEDGE_USER_FOLDER_ID,
        attribution: str = "本机导入资料",
        enqueue: bool = False,
    ) -> dict[str, object] | None:
        """Register one controlled local source without scanning its folder.

        This is used for a deliberately selected teaching reference such as the
        local medical-imaging textbook.  Registration is idempotent and does not
        copy or mutate the original file.  Index execution remains explicit so
        a large PDF cannot unexpectedly block service startup.
        """

        path = source_path.expanduser().resolve()
        if not path.is_file():
            return None
        suffix = path.suffix.lower()
        if suffix not in ALLOWED_TYPES:
            raise ValueError("仅支持 PDF、DOCX、Markdown 和 TXT 文件；旧版 DOC 请先转换。")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        stable_key = hashlib.sha256(f"{path.name.casefold()}:{digest}".encode("utf-8")).hexdigest()[:18]
        document_id = f"knowledge-local-{stable_key}"
        clean_title = (title or path.stem).strip()[:300]
        with SessionLocal() as session:
            folder = session.get(KnowledgeFolderModel, folder_id) if folder_id else None
            if folder_id and folder is None:
                raise ValueError("目标资料目录不存在。")
            row = session.get(SourceDocumentModel, document_id)
            changed = row is None or row.content_hash != digest
            if row is None:
                row = SourceDocumentModel(
                    document_id=document_id, domain_id=DEFAULT_DOMAIN_ID, bank_id=None,
                    folder_id=folder_id, name=clean_title, media_type=ALLOWED_TYPES[suffix],
                    content_hash=digest, status="queued", source_id=document_id,
                    business_usage="knowledge_base", license_gate_status="allow",
                    ai_ingestion_allowed=True, source_uri=f"local://{folder.name if folder else '我的资料'}/{path.name}",
                    namespace="user", attribution=attribution, source_scope="user",
                    file_name=path.name, size_bytes=path.stat().st_size, enabled=False,
                    index_stage="待处理", index_progress=0,
                )
                session.add(row)
            else:
                # Registration is also the durable catalog placement step, so
                # a pre-existing unchanged source still follows the caller's
                # explicit root/folder choice.
                row.folder_id = folder_id
                row.name, row.file_name = clean_title, path.name
                row.namespace, row.source_scope = "user", "user"
            if changed and row is not None and row.document_id == document_id and row.content_hash != digest:
                row.media_type, row.content_hash, row.size_bytes = ALLOWED_TYPES[suffix], digest, path.stat().st_size
                row.source_uri = f"local://{folder.name if folder else '我的资料'}/{path.name}"
                row.namespace, row.source_scope = "user", "user"
                row.status, row.enabled = "queued", False
                row.index_stage, row.index_progress, row.index_error = "待处理", 0, None
            version_id = f"{document_id}-{digest[:12]}"
            if session.get(DocumentVersionModel, version_id) is None:
                session.add(DocumentVersionModel(
                    version_id=version_id, document_id=document_id,
                    version_label=f"{PARSER_VERSION}-{digest[:8]}", source_path=str(path),
                    content_hash=digest, parser="pending", status="queued",
                ))
            session.commit()
        if enqueue:
            return self._enqueue_index(document_id, reason="selected_local_source")
        return self.detail(document_id)

    def queue_selected_sources(self, document_ids: list[str]) -> list[dict[str, object]]:
        """Queue at most five user-selected external sources for indexing."""

        unique_ids = list(dict.fromkeys(str(value) for value in document_ids if str(value).strip()))
        if not unique_ids:
            raise ValueError("请至少选择一份资料。")
        if len(unique_ids) > 5:
            raise ValueError("一次最多处理 5 份资料。")
        with SessionLocal() as session:
            rows = list(session.scalars(select(SourceDocumentModel).where(
                SourceDocumentModel.document_id.in_(unique_ids),
                SourceDocumentModel.business_usage == "knowledge_base",
                SourceDocumentModel.status != "deleted",
            )))
            found = {row.document_id for row in rows}
        if found != set(unique_ids):
            raise ValueError("请选择知识库中的有效资料后再开始索引。")
        return [self._enqueue_index(document_id, reason="selected_sources") for document_id in unique_ids]

    def requeue_pending_index_jobs(self) -> int:
        """Re-dispatch durable queued knowledge jobs after a worker restart.

        Queue messages are intentionally not the source of truth.  A previous
        worker may have been stopped after the database commit, or an old
        checkout may have placed the message in Dramatiq's dead-letter queue.
        Re-sending queued job IDs lets the current worker recover those durable
        records without creating duplicate database jobs.
        """

        now = datetime.utcnow()
        job_ids: list[str] = []
        with SessionLocal() as session:
            jobs = list(session.scalars(select(BackgroundJobModel).where(
                BackgroundJobModel.job_type == "knowledge_index",
                BackgroundJobModel.status == "queued",
            )))
            for job in jobs:
                source = session.get(SourceDocumentModel, job.target_id)
                if source is None or source.business_usage != "knowledge_base":
                    # A deleted source may still have a broker message from
                    # an older process.  Retire the durable job here so a
                    # restart does not keep presenting it to the worker.
                    job.status, job.stage = "failed", "source_missing"
                    job.error_message = "source_not_found"
                    job.completed_at = now
                    continue
                # External guideline registration is intentionally separate
                # from execution.  Never resurrect a whole directory of old
                # queued jobs on startup; the user chooses the files to process
                # explicitly from the knowledge workspace.
                if source is not None and source.folder_id == KNOWLEDGE_CLINICAL_GUIDELINES_FOLDER_ID:
                    continue
                detail = dict(job.detail or {})
                last_dispatched = detail.get("_last_dispatched_at")
                if last_dispatched:
                    try:
                        dispatched_at = datetime.fromisoformat(str(last_dispatched))
                    except ValueError:
                        dispatched_at = None
                    if dispatched_at and now - dispatched_at < timedelta(seconds=90):
                        continue
                detail["_last_dispatched_at"] = now.isoformat()
                job.detail = detail
                job_ids.append(job.job_id)
            if job_ids:
                session.commit()
        if not job_ids:
            return 0
        try:
            from app.workers.background_worker import process_knowledge_index_actor
        except Exception:
            return 0
        dispatched = 0
        for job_id in job_ids:
            try:
                process_knowledge_index_actor.send(job_id)
                dispatched += 1
            except Exception:
                # Keep the durable job queued so the next start or an explicit
                # retry can recover it; do not report a false failure here.
                continue
        return dispatched

    def quarantine_legacy_guideline_indexes(self) -> int:
        """Hide pre-structured clinical-guide indexes until they are rebuilt.

        Early local runs used a page-text parser without durable coverage
        metadata. Some large PDFs were consequently marked ready with only a
        handful of fragments. Those rows must not influence Mentor or Tutor
        retrieval while the learner chooses a small, explicit rebuild batch.
        Original files, version records and previous derived data remain in
        place for traceability; this only removes them from eligible search.
        """

        quarantined = 0
        with SessionLocal() as session:
            rows = list(session.scalars(select(SourceDocumentModel).where(
                SourceDocumentModel.folder_id == KNOWLEDGE_CLINICAL_GUIDELINES_FOLDER_ID,
                SourceDocumentModel.status == "ready",
                SourceDocumentModel.enabled.is_(True),
            )))
            for row in rows:
                stats = row.parse_stats if isinstance(row.parse_stats, dict) else {}
                if int(stats.get("page_count") or 0) > 0 and int(stats.get("chunk_count") or 0) > 0:
                    continue
                row.status = "queued"
                row.enabled = False
                row.index_stage = "待处理"
                row.index_progress = 0
                row.index_error = None
                quarantined += 1
            if quarantined:
                session.commit()
        if quarantined:
            rag_service.clear_retrieval_cache()
        return quarantined

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
            folder = session.get(KnowledgeFolderModel, row.folder_id) if row.folder_id else None
            payload = self._public(row, int(chunk_count or 0), folder)
            payload["preview"] = [{"section": item.parent_section, "page": item.page, "text": item.content[:700]} for item in chunks]
            media = list(session.scalars(select(KnowledgeMediaAssetModel).where(
                KnowledgeMediaAssetModel.document_id == document_id,
                KnowledgeMediaAssetModel.version_id.in_(latest_version_ids),
                KnowledgeMediaAssetModel.asset_type == "figure",
                KnowledgeMediaAssetModel.status == "ready",
            ).order_by(KnowledgeMediaAssetModel.ordinal).limit(6)))
            payload["media_preview"] = [
                {
                    "asset_id": item.asset_id,
                    "url": f"/api/v3/knowledge/media/{item.asset_id}",
                    "mime_type": item.mime_type,
                    "width": item.width,
                    "height": item.height,
                     "page": item.page,
                     "alt_text": item.alt_text or "资料中的教学图片",
                     "asset_type": item.asset_type,
                     "bbox": item.bbox,
                     "section_path": item.section_path,
                 }
                for item in media
            ]
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
                source_uri=str(source_path.resolve()), namespace="user", source_scope="user", folder_id=KNOWLEDGE_USER_FOLDER_ID, file_name=Path(filename).name,
                size_bytes=len(content), enabled=False, parser_version=None, index_stage="uploaded", index_progress=5,
            ))
            session.add(DocumentVersionModel(
                version_id=f"{document_id}-pending", document_id=document_id, version_label="pending",
                source_path=str(source_path.resolve()), content_hash="pending", parser="pending", status="queued",
            ))
            session.commit()
        return self._enqueue_index(document_id, reason="upload")

    def ensure_default_multimodal_guide(self, *, index: bool = True) -> dict[str, object] | None:
        """Make the bundled, attributed endoscopy guide available on a clean run.

        The source PDF is kept unchanged in the public sample directory.  It is
        copied into the ignored runtime knowledge directory before parsing so
        startup never writes beside an installed/read-only application file.
        Repeated starts reuse the indexed source and do not rebuild it unless
        the bundled file has changed.  ``index=False`` is used by the API
        bootstrap so a first-run large sample is registered immediately while
        its expensive parse/embedding/media work runs in the post-startup
        maintenance task.
        """

        bundled_path = DEFAULT_MULTIMODAL_KNOWLEDGE_SAMPLE_PATH
        if not bundled_path.is_file():
            return None
        payload = bundled_path.read_bytes()
        source_hash = hashlib.sha256(payload).hexdigest()
        runtime_path = KNOWLEDGE_UPLOAD_DIR / f"{DEFAULT_MULTIMODAL_KNOWLEDGE_SOURCE_ID}.pdf"
        KNOWLEDGE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        if not runtime_path.is_file() or hashlib.sha256(runtime_path.read_bytes()).hexdigest() != source_hash:
            shutil.copyfile(bundled_path, runtime_path)

        # Keep the stable ID available for the clean-install branch below.
        # Without this assignment the first startup raised UnboundLocalError
        # after creating the row, so the bundled source never reached the
        # parser or the knowledge-library projection.
        document_id = DEFAULT_MULTIMODAL_KNOWLEDGE_SOURCE_ID
        with SessionLocal() as session:
            row = session.get(SourceDocumentModel, DEFAULT_MULTIMODAL_KNOWLEDGE_SOURCE_ID)
            if row is None:
                # A previous local run may have imported the same user-provided
                # PDF manually. Reuse that row instead of showing two copies.
                row = session.scalar(select(SourceDocumentModel).where(
                    SourceDocumentModel.source_uri == DEFAULT_MULTIMODAL_KNOWLEDGE_URI,
                    SourceDocumentModel.status != "deleted",
                ).order_by(SourceDocumentModel.created_at.asc()))
            if row is None:
                row = SourceDocumentModel(
                    document_id=DEFAULT_MULTIMODAL_KNOWLEDGE_SOURCE_ID,
                    domain_id=DEFAULT_DOMAIN_ID,
                    bank_id=None,
                    name=DEFAULT_MULTIMODAL_KNOWLEDGE_TITLE,
                    media_type="application/pdf",
                    content_hash=source_hash,
                    status="queued",
                    source_id=DEFAULT_MULTIMODAL_KNOWLEDGE_SOURCE_ID,
                    business_usage="knowledge_base",
                    license_gate_status="allow_noncommercial",
                    ai_ingestion_allowed=True,
                    source_uri=DEFAULT_MULTIMODAL_KNOWLEDGE_URI,
                    namespace="user",
                    folder_id=KNOWLEDGE_USER_FOLDER_ID,
                    attribution=DEFAULT_MULTIMODAL_KNOWLEDGE_ATTRIBUTION,
                    source_scope="user",
                    file_name=DEFAULT_MULTIMODAL_KNOWLEDGE_FILE_NAME,
                    size_bytes=len(payload),
                    enabled=False,
                    index_stage="准备示例资料",
                    index_progress=0,
                )
                session.add(row)
            elif row.status == "deleted":
                # A user may remove the bundled sample from the library. Keep
                # that choice durable across service restarts while retaining
                # the attributed source file for an explicit future re-import.
                session.commit()
                return None
            elif row.content_hash == source_hash and row.image_count > 0 and row.graph_status == "ready":
                # Upgrade pre-V3.5 reused system rows without forcing a
                # needless parse/index cycle.
                row.source_id = DEFAULT_MULTIMODAL_KNOWLEDGE_SOURCE_ID
                row.source_scope = "user"
                row.namespace = "user"
                row.folder_id = KNOWLEDGE_USER_FOLDER_ID
                session.commit()
                return self.detail(row.document_id)
            else:
                row.domain_id = DEFAULT_DOMAIN_ID
                row.name = DEFAULT_MULTIMODAL_KNOWLEDGE_TITLE
                row.media_type = "application/pdf"
                row.content_hash = source_hash
                # The bundled guide uses a stable source ID even when an
                # older local run first registered it under an opaque import
                # ID.  This keeps its reproducible Figure-caption evaluation
                # fixture independent from runtime document IDs.
                row.source_id = DEFAULT_MULTIMODAL_KNOWLEDGE_SOURCE_ID
                row.business_usage = "knowledge_base"
                row.license_gate_status = "allow_noncommercial"
                row.ai_ingestion_allowed = True
                row.source_uri = DEFAULT_MULTIMODAL_KNOWLEDGE_URI
                row.namespace = "user"
                row.folder_id = None
                row.attribution = DEFAULT_MULTIMODAL_KNOWLEDGE_ATTRIBUTION
                row.source_scope = "user"
                row.file_name = DEFAULT_MULTIMODAL_KNOWLEDGE_FILE_NAME
                row.size_bytes = len(payload)
                row.enabled = False
                row.status = "queued"
                row.index_stage = "准备示例资料"
                row.index_progress = 0
            document_id = row.document_id
            session.commit()

            if not index:
                # Registration is deliberately idempotent and keeps an
                # existing complete source untouched.  A newly registered or
                # changed source is made visible as pending; the background
                # maintenance pass will call this method again with the
                # default ``index=True`` and perform the normal atomic build.
                if row.status not in {"ready", "indexing", "rebuilding"}:
                    row.status, row.enabled = "queued", False
                    row.index_stage, row.index_progress = "待处理", 0
                session.commit()
                return self.detail(row.document_id)

        return self._index(
            document_id=document_id,
            source_path=runtime_path,
            title=DEFAULT_MULTIMODAL_KNOWLEDGE_TITLE,
            file_name=DEFAULT_MULTIMODAL_KNOWLEDGE_FILE_NAME,
            media_type="application/pdf",
            scope="user",
            namespace="user",
            domain_id=DEFAULT_DOMAIN_ID,
            attribution=DEFAULT_MULTIMODAL_KNOWLEDGE_ATTRIBUTION,
            source_uri=DEFAULT_MULTIMODAL_KNOWLEDGE_URI,
            license_gate_status="allow_noncommercial",
        )

    def set_enabled(self, document_id: str, enabled: bool) -> dict[str, object]:
        # Keep the compatibility method on the same invalidation path as the
        # folder-aware PATCH endpoint.  Otherwise a just-disabled source could
        # remain visible from the process-local retrieval cache for its TTL.
        return self.update_source(document_id, enabled=enabled)

    def reindex(self, document_id: str) -> dict[str, object]:
        with SessionLocal() as session:
            row = self._document(session, document_id)
            versions = list(session.scalars(
                select(DocumentVersionModel)
                .where(DocumentVersionModel.document_id == document_id)
                .order_by(DocumentVersionModel.created_at.desc(), DocumentVersionModel.version_id.desc())
            ))
            version = self._select_reindex_source_version(versions)
            if version is None:
                raise ValueError("原始资料文件已不可用，无法重新索引。")
        return self._enqueue_index(document_id, reason="reindex")

    def delete(self, document_id: str) -> None:
        with SessionLocal() as session:
            row = self._document(session, document_id)
            versions = list(session.scalars(select(DocumentVersionModel).where(DocumentVersionModel.document_id == document_id)))
            paths = [Path(item.source_path) for item in versions]
        remove_document = row.source_scope == "user"
        try:
            self._purge(document_id, remove_document=remove_document)
        except Exception:
            # Deleting canonical source metadata must remain possible while the
            # derived vector service is offline; next rebuild drops old points.
            knowledge_multimodal_service.purge_document(document_id)
            with SessionLocal() as session:
                session.query(KnowledgeChunkModel).filter_by(document_id=document_id).delete(synchronize_session=False)
                session.query(DocumentVersionModel).filter_by(document_id=document_id).delete(synchronize_session=False)
                if remove_document:
                    row = session.get(SourceDocumentModel, document_id)
                    if row:
                        session.delete(row)
                session.commit()
        if not remove_document:
            # System and question-explanation sources remain as a durable
            # tombstone so an intentional removal is not undone by startup
            # syncing. Their original files are never deleted from the source
            # directories; only runtime-derived assets are cleaned below.
            with SessionLocal() as session:
                row = session.get(SourceDocumentModel, document_id)
                if row is not None:
                    row.status = "deleted"
                    row.enabled = False
                    row.business_usage = "knowledge_deleted"
                    row.index_stage = "已从知识库移除"
                    row.index_progress = 0
                    row.index_job_id = None
                    row.index_error = None
                    row.image_count = 0
                    row.image_index_status = "empty"
                    row.image_index_error = None
                    row.graph_status = "empty"
                    row.graph_node_count = 0
                    row.graph_edge_count = 0
                    row.graph_error = None
                session.commit()
        for path in paths:
            if KNOWLEDGE_UPLOAD_DIR in path.parents:
                path.unlink(missing_ok=True)
                path.with_suffix(".parsed.md").unlink(missing_ok=True)

    def ensure_cmexam_explanations(self, limit: int = 180) -> dict[str, object]:
        """Compatibility entry point for the maintained CMExam corpus."""

        result = self.sync_published_question_explanations(
            bank_id="bank-cmexam-real", limit_per_bank=limit,
        )
        source = next(iter(result.get("sources", [])), None)
        if not source:
            raise ValueError("CMExam 尚未导入，无法建立解析知识库。")
        return self.detail(str(source["document_id"]))

    @staticmethod
    def _qbank_explanation_document_id(bank_id: str) -> str:
        if bank_id == "bank-cmexam-real":
            # Preserve the existing public identity so old citations and local
            # databases upgrade without creating a duplicate CMExam source.
            return "source-cmexam-explanations-v31"
        safe_bank_id = re.sub(r"[^A-Za-z0-9_-]+", "-", bank_id).strip("-")[:80]
        return f"source-qbank-{safe_bank_id}-explanations-v352"

    @staticmethod
    def _question_explanation_projection(bank: QuestionModel) -> str:
        options = "；".join(
            str(item.get("text") or "").strip()
            for item in (bank.options or [])
            if isinstance(item, dict) and str(item.get("text") or "").strip()
        )
        lines = [
            f"## {bank.title or bank.question_id}",
            f"题目：{bank.stem.strip()}",
        ]
        if options:
            lines.append(f"选项：{options}")
        if bank.topic:
            lines.append(f"知识点：{bank.topic}")
        if bank.explanation.strip():
            lines.append(f"解析：{bank.explanation.strip()}")
        return "\n".join(lines)

    def sync_published_question_explanations(
        self, *, bank_id: str | None = None, limit_per_bank: int | None = None,
    ) -> dict[str, object]:
        """Materialize published question explanations as text-only sources.

        Question images remain in the question-asset domain by design.  This
        projection contains only learner-visible question evidence and is
        indexed into the qbank explanation scope, keeping qbank retrieval
        useful without polluting the knowledge-image collection.
        """

        with SessionLocal() as session:
            # ``adaptive-*`` banks are short-lived session artifacts created
            # by the learning loop.  They are not learner-owned catalog
            # sources and materialising every one of them here made startup
            # rebuild dozens of tiny explanation documents.  Stable catalog
            # banks use the ``bank-*`` namespace; keep a permissive fallback
            # for tests and future published banks while excluding only those
            # ephemeral adaptive projections.
            bank_query = select(QuestionBankModel).where(
                QuestionBankModel.status == "published",
                ~QuestionBankModel.bank_id.like("adaptive-%"),
            )
            if bank_id:
                bank_query = bank_query.where(QuestionBankModel.bank_id == bank_id)
            banks = list(session.scalars(bank_query.order_by(QuestionBankModel.bank_id)))

        synced: list[dict[str, object]] = []
        skipped: list[str] = []
        for bank in banks:
            with SessionLocal() as session:
                question_query = select(QuestionModel).where(
                    QuestionModel.bank_id == bank.bank_id,
                    QuestionModel.business_usage == "user_ready",
                    QuestionModel.stem.is_not(None),
                ).order_by(QuestionModel.question_id)
                if limit_per_bank is not None:
                    question_query = question_query.limit(limit_per_bank)
                questions = list(session.scalars(question_query))
                existing = session.get(SourceDocumentModel, self._qbank_explanation_document_id(bank.bank_id))
                if existing is not None and existing.status == "deleted":
                    skipped.append(bank.bank_id)
                    continue

            if not questions:
                skipped.append(bank.bank_id)
                continue
            title = "CMExam 官方解析库" if bank.bank_id == "bank-cmexam-real" else f"{bank.name} · 题目解析"
            projection = "\n\n".join([
                f"# {title}",
                f"来自已发布题库“{bank.name}”的题目与解析，用于学习过程中的资料检索。",
                *[self._question_explanation_projection(question) for question in questions],
            ])
            digest = hashlib.sha256(projection.encode("utf-8")).hexdigest()
            document_id = self._qbank_explanation_document_id(bank.bank_id)
            source_path = KNOWLEDGE_UPLOAD_DIR / "parsed" / f"{document_id}.md"
            with SessionLocal() as session:
                existing = session.get(SourceDocumentModel, document_id)
                has_chunks = bool(existing and session.scalar(select(func.count(KnowledgeChunkModel.chunk_id)).where(
                    KnowledgeChunkModel.document_id == document_id,
                )))
                if existing and existing.content_hash == digest and existing.status == "ready" and has_chunks:
                    # Repair placement metadata without rebuilding unchanged
                    # content.  This also fixes sources from the pre-folder
                    # implementation on the next startup.
                    existing.bank_id = bank.bank_id
                    existing.folder_id = KNOWLEDGE_QBANK_FOLDER_ID
                    existing.source_scope = "qbank_explanations"
                    existing.namespace = "qbank_explanations"
                    existing.business_usage = "knowledge_base"
                    session.commit()
                    skipped.append(bank.bank_id)
                    continue
                if existing:
                    # Keep the source row and identity, replace only derived
                    # versions/chunks before building the new canonical one.
                    pass
            if existing:
                self._purge(document_id, remove_document=False)
            KNOWLEDGE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
            source_path.parent.mkdir(parents=True, exist_ok=True)
            source_path.write_text(projection, encoding="utf-8")
            with SessionLocal() as session:
                row = session.get(SourceDocumentModel, document_id)
                if row is None:
                    row = SourceDocumentModel(
                        document_id=document_id, domain_id=bank.domain_id, bank_id=bank.bank_id,
                        folder_id=KNOWLEDGE_QBANK_FOLDER_ID, name=title, media_type="text/markdown",
                        content_hash=digest, status="queued", source_id=document_id,
                        business_usage="knowledge_base", license_gate_status="allow",
                        ai_ingestion_allowed=True, source_uri=f"qbank://{bank.bank_id}/published-explanations",
                        namespace="qbank_explanations", attribution=f"{bank.name} · 已发布题目解析",
                        source_scope="qbank_explanations", file_name=f"{bank.name} · 题目解析.md",
                        size_bytes=len(projection.encode("utf-8")), enabled=False,
                        index_stage="准备解析", index_progress=0,
                    )
                    session.add(row)
                else:
                    row.bank_id = bank.bank_id
                    row.domain_id = bank.domain_id
                    row.folder_id = KNOWLEDGE_QBANK_FOLDER_ID
                    row.name, row.file_name = title, f"{bank.name} · 题目解析.md"
                    row.media_type, row.content_hash = "text/markdown", digest
                    row.status, row.enabled = "queued", False
                    row.source_id = document_id
                    row.business_usage = "knowledge_base"
                    row.license_gate_status, row.ai_ingestion_allowed = "allow", True
                    row.source_uri = f"qbank://{bank.bank_id}/published-explanations"
                    row.namespace, row.source_scope = "qbank_explanations", "qbank_explanations"
                    row.attribution = f"{bank.name} · 已发布题目解析"
                    row.size_bytes, row.index_stage, row.index_progress = len(projection.encode("utf-8")), "准备解析", 0
                    row.index_error = None
                session.commit()
            item = self._index(
                document_id=document_id, source_path=source_path, title=title,
                file_name=f"{bank.name} · 题目解析.md", media_type="text/markdown",
                scope="qbank_explanations", namespace="qbank_explanations", domain_id=bank.domain_id,
                attribution=f"{bank.name} · 已发布题目解析",
                source_uri=f"qbank://{bank.bank_id}/published-explanations",
                license_gate_status="allow",
            )
            synced.append({"document_id": document_id, "bank_id": bank.bank_id, "title": title, "chunk_count": item.get("chunk_count", 0)})
        rag_service.clear_retrieval_cache()
        return {"synced": len(synced), "skipped": skipped, "sources": synced}

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

    def _index(
        self,
        *,
        document_id: str,
        source_path: Path,
        title: str,
        file_name: str,
        media_type: str,
        scope: str,
        namespace: str,
        domain_id: str,
        attribution: str | None,
        source_uri: str | None,
        license_gate_status: str = "allow",
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> dict[str, object]:
        # Keep the normalized text projection in the ignored runtime area.
        # Source directories remain source-only, which prevents startup sync
        # from treating ``*.parsed.md`` as another knowledge document.
        parsed_projection = KNOWLEDGE_UPLOAD_DIR / "parsed" / f"{re.sub(r'[^A-Za-z0-9_.-]+', '_', document_id)}.md"
        parsed_document = parse_document(source_path, progress_callback=progress_callback)
        if progress_callback is not None:
            progress_callback("文本切分", 1, 1)
        parsed_projection.parent.mkdir(parents=True, exist_ok=True)
        parsed_projection.write_text(parsed_document.text_projection(), encoding="utf-8")
        markdown, parser = parsed_projection, parsed_document.parser
        # The bundled guide may reuse an existing local document row.  Its
        # evidence fixture must still resolve by a stable public source ID,
        # rather than whichever opaque document ID happened to be created on
        # that machine.  Other sources keep their normal document identity.
        source_identifier = (
            DEFAULT_MULTIMODAL_KNOWLEDGE_SOURCE_ID
            if source_uri == DEFAULT_MULTIMODAL_KNOWLEDGE_URI
            else document_id
        )
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
                pending.license_gate_status, pending.ai_ingestion_allowed = license_gate_status, True
                session.commit()
        vector_error: str | None = None
        if progress_callback is not None:
            progress_callback("生成向量", 1, 1)
        try:
            rag_service.index_markdown(markdown, document_id=document_id, document_name=title, domain_id=domain_id, child_size=700,
                                       namespace=namespace, source_id=source_identifier, source_uri=source_uri, business_usage="knowledge_base",
                                       license_gate_status=license_gate_status, ai_ingestion_allowed=True, version_label=f"{PARSER_VERSION}-structured-450",
                                       parsed_document=parsed_document)
        except Exception as exc:
            # Text-vector maintenance is a derived capability.  Keep the
            # committed text chunks available for sparse retrieval and still
            # continue with PDF/DOCX media extraction and the evidence graph;
            # the source status below records the exact retryable failure.
            vector_error = _public_vector_error(exc)
        # Text retrieval is canonical and must remain usable when the optional
        # image encoder or image Qdrant collection is unavailable.  Media
        # extraction and the deterministic evidence graph therefore happen
        # after the text index commit, with image-vector failure isolated to
        # the source's truthful status fields.
        with SessionLocal() as session:
            version = session.scalar(select(DocumentVersionModel).where(
                DocumentVersionModel.document_id == document_id,
            ).order_by(DocumentVersionModel.created_at.desc(), DocumentVersionModel.version_id.desc()))
            if version is not None:
                # ``RagService`` indexes the normalized markdown projection;
                # retain the original upload as the durable source path so a
                # later background reindex can extract embedded media again.
                version.source_path = str(source_path.resolve())
                version.parser = parser
                session.commit()
        if version is not None:
            media = knowledge_multimodal_service.ingest_document(
                document_id=document_id,
                version_id=version.version_id,
                source_path=source_path,
                media_type=media_type,
                parsed_document=parsed_document,
            )
            if progress_callback is not None:
                progress_callback("图片索引", 1, 1)
            if int(media.get("image_count") or 0) > 0:
                try:
                    rag_service.rebuild_knowledge_image_index(document_ids=[document_id])
                except Exception as exc:
                    # The text path has already succeeded.  Keep the exact
                    # failure class for the UI/diagnostics without exposing
                    # provider keys or local paths.
                    knowledge_multimodal_service.set_image_index_status(
                        [document_id], "failed", type(exc).__name__
                    )
            if progress_callback is not None:
                progress_callback("证据关联", 1, 1)
        with SessionLocal() as session:
            row = session.get(SourceDocumentModel, document_id)
            assert row is not None
            row.name, row.file_name, row.media_type = title, file_name, media_type
            row.source_scope, row.namespace, row.domain_id = scope, namespace, domain_id
            if scope == "qbank_explanations":
                row.folder_id = "folder-qbank-explanations"
            elif scope == "user":
                # Preserve an explicit folder selected by the caller.  The
                # default upload path uses 我的资料, while the curated
                # clinical directory must remain a real directory instead of
                # being flattened into the generic user folder after indexing.
                if row.folder_id is None:
                    row.folder_id = KNOWLEDGE_USER_FOLDER_ID
            elif source_uri == DEFAULT_MULTIMODAL_KNOWLEDGE_URI:
                row.folder_id = KNOWLEDGE_CLINICAL_GUIDELINES_FOLDER_ID
            elif row.folder_id is None:
                row.folder_id = "folder-system"
            state = rag_service.index_state()
            parsed_chunk_count = int(parsed_document.stats.chunk_count)
            has_text_evidence = parsed_chunk_count > 0
            if not has_text_evidence and parsed_document.stats.pages_needing_ocr:
                # A scanned source is visible in the library, but it must not
                # become an enabled knowledge source with a status anchor as
                # if that anchor were real正文 evidence.
                row.status, row.enabled = "needs_ocr", False
                row.index_stage, row.index_progress = "需要文字识别", 0
                row.index_error = "扫描页尚未完成文字识别。"
            elif not has_text_evidence:
                row.status, row.enabled = "failed", False
                row.index_stage, row.index_progress = "没有可用正文", 0
                row.index_error = "资料中没有可用正文片段。"
            else:
                # Vector services are derived infrastructure.  Relational
                # chunks remain searchable through the sparse fallback when a
                # Qdrant/embedding request fails, so do not hide valid text
                # evidence behind a misleading source-level failure.
                row.status, row.enabled = "ready", True
                row.index_stage, row.index_progress = (
                    ("正文已完成，向量待重试", 90) if vector_error else ("completed", 100)
                )
                row.index_error = vector_error
            row.business_usage = "knowledge_base"
            row.license_gate_status, row.ai_ingestion_allowed = license_gate_status, True
            row.attribution, row.source_uri = attribution, source_uri or str(source_path.resolve())
            row.content_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
            row.size_bytes, row.parser_version, row.embedding_model = source_path.stat().st_size, parser, str(state.get("model") or MODEL_NAME)
            row.embedding_provider = str(state.get("provider") or "") or None
            row.embedding_dimension = int(state["vector_dimension"]) if isinstance(state.get("vector_dimension"), int) else None
            row.index_version = int(state.get("index_version") or 0)
            row.parse_stats = {**parsed_document.stats.as_dict(), "chunk_count": parsed_chunk_count}
            session.commit()
        rag_service.clear_retrieval_cache()
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
            # Record the dispatch before leaving the transaction.  Startup
            # reconciliation can then safely run after a local-guideline sync
            # without immediately enqueueing a duplicate copy of the same job.
            job.detail = {**dict(job.detail or {}), "_last_dispatched_at": datetime.utcnow().isoformat()}
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
            row = session.get(SourceDocumentModel, job.target_id)
            if row is None or row.business_usage != "knowledge_base":
                # Old local runs could leave a Redis message behind after a
                # source was removed.  Consume it as a terminal job instead
                # of retrying the same KeyError forever and starving valid
                # indexing work.
                job.status, job.stage = "failed", "source_missing"
                job.error_message = "source_not_found"
                job.completed_at = datetime.utcnow()
                session.commit()
                return {"job_id": job_id, "status": "failed", "error": "source_not_found"}
            versions = list(session.scalars(
                select(DocumentVersionModel)
                .where(DocumentVersionModel.document_id == row.document_id)
                .order_by(DocumentVersionModel.created_at.desc(), DocumentVersionModel.version_id.desc())
            ))
            version = self._select_reindex_source_version(versions)
            if version is None:
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
            def report_parser_progress(stage: str, page: int, total: int) -> None:
                # Parsing progress occupies the first third of the job.  A
                # page callback keeps a large scanned book visibly moving and
                # is safe to lose because the durable job remains retryable.
                phase_progress = {
                    "文本切分": 40,
                    "生成向量": 60,
                    "图片索引": 86,
                    "证据关联": 95,
                }
                if stage in phase_progress:
                    progress = phase_progress[stage]
                else:
                    progress = 15 if total <= 0 else min(35, 15 + round(page / total * 20))
                with SessionLocal() as session:
                    current_job = session.get(BackgroundJobModel, job_id)
                    current_row = self._document(session, current_job.target_id) if current_job else None
                    if current_job is None or current_row is None or current_job.status == "completed":
                        return
                    current_job.stage, current_job.progress = stage, progress
                    current_row.index_stage, current_row.index_progress = stage, progress
                    session.commit()

            with SessionLocal() as session:
                job = session.get(BackgroundJobModel, job_id)
                row = self._document(session, job.target_id) if job else None
                assert job is not None and row is not None
                job.stage, job.progress = "解析文档", 15
                row.index_stage, row.index_progress = "解析文档", 15
                # Do not delete the previous canonical version here.  The
                # worker may still fail during parsing, embedding, or Qdrant
                # replacement; retaining old chunks makes retry and recovery
                # lossless.  The derived-index rebuild selects only the newest
                # successful version for retrieval.
                session.commit()
            self._index(**args, progress_callback=report_parser_progress)
            with SessionLocal() as session:
                job = session.get(BackgroundJobModel, job_id)
                row = self._document(session, job.target_id) if job else None
                assert job is not None and row is not None
                # Text chunks can remain usable through the governed sparse
                # path while a transient vector write awaits retry.  Preserve
                # that truthful partial state instead of overwriting it with a
                # misleading "完成" receipt.
                if row.index_error:
                    job.status, job.stage, job.progress, job.completed_at = "completed", row.index_stage or "向量待重试", row.index_progress or 90, datetime.utcnow()
                else:
                    job.status, job.stage, job.progress, job.completed_at = "completed", "完成", 100, datetime.utcnow()
                    row.index_stage, row.index_progress = "完成", 100
                row.index_job_id = job_id
                session.commit()
            return {"job_id": job_id, "status": "completed"}
        except Exception as exc:
            safe_error = _public_index_error(exc)
            with SessionLocal() as session:
                job = session.get(BackgroundJobModel, job_id)
                row = self._document(session, job.target_id) if job else None
                if job:
                    job.status, job.stage, job.error_message, job.completed_at = "failed", "failed", safe_error, datetime.utcnow()
                if row:
                    if had_previous_chunks:
                        # The old source/index remains usable. Surface the
                        # failed replacement separately without downgrading a
                        # truthful ready state or hiding the old evidence.
                        for name, value in previous_state.items():
                            setattr(row, name, value)
                        row.index_stage, row.index_error = "failed", type(exc).__name__
                    else:
                        row.status, row.enabled, row.index_stage, row.index_error = "failed", False, "failed", safe_error
                session.commit()
            raise

    def _parse(self, source_path: Path, *, output_path: Path | None = None) -> tuple[Path, str]:
        suffix = source_path.suffix.lower()
        target = output_path or (KNOWLEDGE_UPLOAD_DIR / "parsed" / f"{source_path.stem}.md")
        parsed = parse_document(source_path)
        text = parsed.text_projection()
        if suffix == ".pdf":
            parser = "pymupdf-page-aware" if parsed.stats.pages_with_text else "pymupdf-scanned-pages"
        else:
            parser = "python-docx" if suffix == ".docx" else parsed.parser
        if len(text.strip()) < 40:
            raise ValueError("未能从资料中解析出足够的可索引文本。")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        return target, parser

    @staticmethod
    def _document(session: object, document_id: str) -> SourceDocumentModel:
        row = session.get(SourceDocumentModel, document_id)  # type: ignore[attr-defined]
        if row is None or row.business_usage != "knowledge_base":
            raise KeyError(document_id)
        return row

    @staticmethod
    def _select_reindex_source_version(versions: list[DocumentVersionModel]) -> DocumentVersionModel | None:
        """Choose the durable source file, never the derived parsed Markdown.

        A knowledge version also has a normalized ``.parsed.md`` projection for
        text retrieval. Older records used that projection as ``source_path``
        after indexing, which made a later reindex silently lose embedded PDF
        or DOCX media. Prefer an existing original upload/source path and only
        fall back to a non-derived file when no sibling is available.
        """

        usable = [item for item in versions if Path(item.source_path).is_file()]
        if not usable:
            return None

        def is_derived_projection(item: DocumentVersionModel) -> bool:
            path = Path(item.source_path)
            # Current projections live in ``runtime/knowledge/parsed`` and
            # older builds used a ``*.parsed.md`` suffix.  Checking only the
            # suffix allowed a retry to select ``parsed/document.md`` as if it
            # were the original PDF, silently losing OCR and media assets.
            return path.name.casefold().endswith(".parsed.md") or path.parent.name.casefold() == "parsed"

        original = [
            item for item in usable
            if not is_derived_projection(item)
        ]
        return original[0] if original else usable[0]

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
    def _folder_public(row: KnowledgeFolderModel, source_count: int) -> dict[str, object]:
        return {
            "id": row.folder_id,
            "name": row.name,
            "description": row.description,
            "scope": row.scope,
            "is_system": row.is_system,
            "source_count": source_count,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

    @staticmethod
    def _validate_folder_name(value: str) -> str:
        clean_name = re.sub(r"\s+", " ", value.strip())
        if not clean_name:
            raise ValueError("资料目录名称不能为空。")
        if len(clean_name) > 120:
            raise ValueError("资料目录名称不能超过 120 个字符。")
        return clean_name

    @staticmethod
    def _public(row: SourceDocumentModel, chunk_count: int, folder: KnowledgeFolderModel | None = None) -> dict[str, object]:
        return {"id": row.document_id, "title": row.name, "file_name": row.file_name or row.name, "media_type": row.media_type,
                "scope": row.source_scope, "status": row.status, "size_bytes": row.size_bytes, "chunk_count": chunk_count,
                "folder_id": row.folder_id, "folder_name": folder.name if folder else None,
                "enabled": row.enabled, "parser_version": row.parser_version, "embedding_model": row.embedding_model,
                "embedding_provider": row.embedding_provider, "index_version": row.index_version, "index_job_id": row.index_job_id,
                "index_stage": row.index_stage, "index_progress": row.index_progress, "index_error": row.index_error,
                "image_count": row.image_count, "image_index_status": row.image_index_status,
                "image_index_error": row.image_index_error, "graph_status": row.graph_status,
                "graph_node_count": row.graph_node_count, "graph_edge_count": row.graph_edge_count,
                "graph_error": row.graph_error, "parse_stats": row.parse_stats or {}, "media_preview": [],
                "attribution": row.attribution, "created_at": row.created_at, "updated_at": row.updated_at}

    @staticmethod
    def _purge(document_id: str, *, remove_document: bool) -> None:
        # Vector collections are derived infrastructure.  Reindexing or
        # removing a source must still clean the relational chunks/assets when
        # Qdrant is offline; otherwise one unavailable vector call prevents
        # the next qbank/document in the same synchronization pass from ever
        # being materialised.
        try:
            rag_service.delete_documents([document_id])
        except Exception:
            pass
        try:
            rag_service.delete_image_documents([document_id])
        except Exception:
            # Derived image storage is optional; relational cleanup below is
            # still required when Qdrant is unavailable.
            pass
        knowledge_multimodal_service.purge_document(document_id)
        with SessionLocal() as session:
            session.query(KnowledgeChunkModel).filter_by(document_id=document_id).delete(synchronize_session=False)
            session.query(DocumentVersionModel).filter_by(document_id=document_id).delete(synchronize_session=False)
            if remove_document:
                row = session.get(SourceDocumentModel, document_id)
                if row:
                    session.delete(row)
            session.commit()

    @classmethod
    def _retire_source(cls, document_id: str) -> None:
        """Remove derived evidence but retain a tombstone for local sync."""
        cls._purge(document_id, remove_document=False)
        with SessionLocal() as session:
            row = session.get(SourceDocumentModel, document_id)
            if row is not None:
                row.status = "deleted"
                row.enabled = False
                row.business_usage = "knowledge_deleted"
                row.index_stage = "已从知识库移除"
                row.index_progress = 0
                row.index_job_id = None
                row.index_error = None
                row.image_count = 0
                row.image_index_status = "empty"
                row.image_index_error = None
                row.graph_status = "empty"
                row.graph_node_count = 0
                row.graph_edge_count = 0
                row.graph_error = None
            session.commit()


knowledge_service = KnowledgeService()
