"""Governed media and evidence-graph work for the knowledge library.

The relational knowledge graph remains the source of truth.  Image bytes live
only below the runtime knowledge directory; database rows and retrieval
payloads contain opaque asset IDs and compact provenance metadata.  The graph
builder is deliberately deterministic and evidence-bound: it extracts small
concept labels from each chunk and never invents a relationship through an
untraceable model call.
"""

from __future__ import annotations

import hashlib
import mimetypes
import posixpath
import re
import shutil
import zipfile
from dataclasses import dataclass
from math import hypot
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

import fitz
from sqlalchemy import delete, select

from app.core import config
from app.db.database import SessionLocal
from app.db.models import (
    DocumentVersionModel,
    KnowledgeChunkModel,
    KnowledgeEntityModel,
    KnowledgeMediaAssetModel,
    KnowledgeRelationModel,
    SourceDocumentModel,
)
from app.services.image_asset_service import inspect_image


KNOWLEDGE_MEDIA_ROOT = config.RUNTIME_ROOT / "knowledge-media"
_IMAGE_MIME_BY_EXTENSION = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}
_IMAGE_EXT_BY_MIME = {value: key.lstrip(".") for key, value in _IMAGE_MIME_BY_EXTENSION.items()}
_MAX_DOCUMENT_IMAGES = 120

# These are intentionally small, stable labels rather than an attempted
# general-purpose NLP model.  Every edge is tied to the chunk that contained
# both concepts, so a user can always inspect the evidence that produced it.
#
# The first version also accepted every ASCII word and every short CJK span as
# a node.  PDF headers and OCR fragments then produced misleading paths such
# as ``article -> port``.  A governed graph is more useful when it contains
# fewer, domain-relevant concepts than when it creates a dense but meaningless
# web of page furniture.
_COMMON_ENTITY_TERMS = (
    "内镜图像记录", "图像记录", "图像文档", "质量控制", "上消化道内镜", "下消化道内镜",
    "结肠镜检查", "胃镜检查", "内镜", "胃镜", "结肠镜", "食管", "胃", "结肠", "直肠", "小肠", "息肉", "腺瘤", "病变",
    "活检", "病理", "黏膜", "出血", "溃疡", "炎症", "图像", "指南", "诊断", "筛查", "治疗",
    "风险", "随访", "知识库", "检索", "向量", "嵌入", "模型", "代理", "题库", "训练",
    "image documentation", "photo documentation", "quality control", "systematic imaging", "upper gi endoscopy",
    "lower gi endoscopy", "upper gastrointestinal endoscopy", "lower gastrointestinal endoscopy", "endoscopic landmarks", "pathologic findings",
    "图像示例", "系统图像示例", "直肠", "乙状结肠", "盲肠", "回盲瓣", "阑尾开口",
    "examples of systematic imaging", "proximal esophagus", "distal esophagus", "z-line", "cardia", "fundus", "antrum", "duodenal bulb",
    "rectum", "sigmoid", "cecum", "ileocecal valve", "appendiceal orifice",
    "endoscopy", "gastroscopy", "colonoscopy", "polyp", "adenoma", "biopsy", "pathology",
    "image", "retrieval", "embedding", "agent", "model",
)
_ENTITY_STOPWORDS = {
    "这是", "可以", "如果", "因为", "因此", "以及", "相关", "内容", "资料", "问题", "一个", "进行",
    "the", "and", "for", "with", "from", "this", "that", "using", "into",
}
_CONCEPT_ALIASES = {
    "endoscopy": "内镜",
    "gastroscopy": "胃镜",
    "colonoscopy": "结肠镜",
    "polyp": "息肉",
    "adenoma": "腺瘤",
    "biopsy": "活检",
    "pathology": "病理",
    "image documentation": "图像记录",
    "photo documentation": "图像记录",
    "systematic imaging": "图像记录",
    "examples of systematic imaging": "图像示例",
    "系统图像示例": "图像示例",
    "upper gi endoscopy": "上消化道内镜",
    "upper gastrointestinal endoscopy": "上消化道内镜",
    "lower gi endoscopy": "下消化道内镜",
    "lower gastrointestinal endoscopy": "下消化道内镜",
    "quality control": "质量控制",
    "rectum": "直肠",
    "sigmoid": "乙状结肠",
    "cecum": "盲肠",
    "ileocecal valve": "回盲瓣",
    "appendiceal orifice": "阑尾开口",
}


@dataclass(frozen=True)
class ExtractedImage:
    payload: bytes
    filename: str
    mime_type: str
    page: int
    ordinal: int
    alt_text: str | None = None
    section: str | None = None
    concepts: tuple[str, ...] = ()


@dataclass(frozen=True)
class FigureCaption:
    """A page-local Figure caption with its visual position in the PDF."""

    text: str
    rect: fitz.Rect
    label: str


class KnowledgeMultimodalService:
    """Extract and persist document media, graph evidence, and status metadata."""

    def ingest_document(
        self,
        *,
        document_id: str,
        version_id: str,
        source_path: Path,
        media_type: str,
    ) -> dict[str, Any]:
        """Replace current-version media and rebuild deterministic graph rows.

        A malformed embedded image is reported while valid text indexing stays
        usable.  The caller decides whether to continue to the optional image
        vector index; no image bytes are returned from this method.
        """

        extracted, extraction_errors = self._extract_images(source_path, media_type)
        self._remove_document_media(document_id, keep_version_id=version_id)
        assets: list[KnowledgeMediaAssetModel] = []
        destination_root = (KNOWLEDGE_MEDIA_ROOT / document_id / version_id).resolve()
        root = KNOWLEDGE_MEDIA_ROOT.resolve()
        if root not in destination_root.parents:
            raise ValueError("知识资料图片存储路径无效。")
        destination_root.mkdir(parents=True, exist_ok=True)

        for item in extracted[:_MAX_DOCUMENT_IMAGES]:
            try:
                detected, width, height = inspect_image(item.payload, item.mime_type)
            except ValueError as exc:
                extraction_errors.append(f"{item.filename}: {exc}")
                continue
            digest = hashlib.sha256(item.payload).hexdigest()
            asset_id = f"kmedia_{uuid4().hex[:16]}"
            extension = _IMAGE_EXT_BY_MIME[detected]
            relative = Path(document_id) / version_id / f"{asset_id}.{extension}"
            target = (KNOWLEDGE_MEDIA_ROOT / relative).resolve()
            if root not in target.parents:
                extraction_errors.append(f"{item.filename}: 图片存储路径无效")
                continue
            target.write_bytes(item.payload)
            assets.append(KnowledgeMediaAssetModel(
                asset_id=asset_id,
                document_id=document_id,
                version_id=version_id,
                storage_path=relative.as_posix(),
                original_filename=self._safe_filename(item.filename),
                sha256=digest,
                mime_type=detected,
                width=width,
                height=height,
                size_bytes=len(item.payload),
                page=max(1, int(item.page)),
                ordinal=int(item.ordinal),
                alt_text=item.alt_text,
                status="ready",
            ))

        with SessionLocal() as session:
            session.add_all(assets)
            session.flush()
            self._link_assets_to_chunks(session, document_id, version_id, assets)
            graph_counts = self._rebuild_graph(session, document_id, version_id)
            row = session.get(SourceDocumentModel, document_id)
            if row is not None:
                row.image_count = len(assets)
                if not assets:
                    row.image_index_status = "empty" if not extraction_errors else "failed"
                else:
                    # Embedding is a separate step.  The value is set to
                    # ``pending`` until RagService attempts the real encoder.
                    row.image_index_status = "pending"
                row.image_index_error = "; ".join(extraction_errors[:4]) if extraction_errors else None
                row.graph_status = "ready"
                row.graph_node_count, row.graph_edge_count = graph_counts
                row.graph_error = None
            session.commit()
        return {
            "image_count": len(assets),
            "asset_ids": [asset.asset_id for asset in assets],
            "image_errors": extraction_errors[:8],
            "graph_node_count": graph_counts[0],
            "graph_edge_count": graph_counts[1],
        }

    def set_image_index_status(self, document_ids: Iterable[str], status: str, error: str | None = None) -> None:
        allowed = {"empty", "pending", "ready", "failed", "stale"}
        value = status if status in allowed else "failed"
        with SessionLocal() as session:
            rows = list(session.scalars(select(SourceDocumentModel).where(SourceDocumentModel.document_id.in_(list(document_ids)))))
            for row in rows:
                row.image_index_status = value
                row.image_index_error = error
            session.commit()

    def list_assets(self, document_id: str | None = None, asset_ids: list[str] | None = None) -> list[KnowledgeMediaAssetModel]:
        with SessionLocal() as session:
            statement = select(KnowledgeMediaAssetModel).where(KnowledgeMediaAssetModel.status == "ready")
            if document_id:
                statement = statement.where(KnowledgeMediaAssetModel.document_id == document_id)
            if asset_ids:
                statement = statement.where(KnowledgeMediaAssetModel.asset_id.in_(asset_ids))
            return list(session.scalars(statement.order_by(KnowledgeMediaAssetModel.ordinal)))

    def resolve_path(self, asset_id: str) -> Path:
        with SessionLocal() as session:
            row = session.get(KnowledgeMediaAssetModel, asset_id)
            if row is None or row.status != "ready":
                raise KeyError(asset_id)
            relative = posixpath.normpath(str(row.storage_path).replace("\\", "/"))
            if relative in {"", ".", ".."} or relative.startswith("../") or Path(relative).is_absolute():
                raise ValueError("知识图片路径无效。")
            path = (KNOWLEDGE_MEDIA_ROOT / Path(relative)).resolve()
            root = KNOWLEDGE_MEDIA_ROOT.resolve()
            if root not in path.parents or not path.is_file():
                raise FileNotFoundError(asset_id)
            return path

    def public_asset(self, asset_id: str) -> dict[str, Any]:
        with SessionLocal() as session:
            row = session.get(KnowledgeMediaAssetModel, asset_id)
            if row is None or row.status != "ready":
                raise KeyError(asset_id)
            return {
                "asset_id": row.asset_id,
                "url": f"/api/v3/knowledge/media/{row.asset_id}",
                "mime_type": row.mime_type,
                "width": row.width,
                "height": row.height,
                "page": row.page,
                "alt_text": row.alt_text or "资料中的教学图片",
            }

    def purge_document(self, document_id: str) -> None:
        """Remove a source's media/graph rows and runtime bytes safely."""

        with SessionLocal() as session:
            rows = list(session.scalars(select(KnowledgeMediaAssetModel).where(KnowledgeMediaAssetModel.document_id == document_id)))
            for row in rows:
                path = (KNOWLEDGE_MEDIA_ROOT / row.storage_path).resolve()
                if KNOWLEDGE_MEDIA_ROOT.resolve() in path.parents:
                    path.unlink(missing_ok=True)
                session.delete(row)
            session.execute(delete(KnowledgeRelationModel).where(KnowledgeRelationModel.document_id == document_id))
            session.execute(delete(KnowledgeEntityModel).where(KnowledgeEntityModel.document_id == document_id))
            session.commit()
        root = KNOWLEDGE_MEDIA_ROOT / document_id
        if root.is_dir():
            shutil.rmtree(root, ignore_errors=True)

    def _extract_images(self, source_path: Path, media_type: str) -> tuple[list[ExtractedImage], list[str]]:
        suffix = source_path.suffix.lower()
        if suffix == ".pdf" or media_type == "application/pdf":
            return self._extract_pdf(source_path)
        if suffix == ".docx" or "wordprocessingml.document" in media_type:
            return self._extract_docx(source_path)
        if suffix in {".md", ".txt"}:
            return self._extract_markdown_images(source_path)
        return [], []

    def _extract_pdf(self, source_path: Path) -> tuple[list[ExtractedImage], list[str]]:
        """Extract only evidence-bearing PDF figures with their captions.

        A PDF often embeds publisher marks, ornaments and page furniture as
        image objects.  Indexing those makes CLIP retrieval look functional
        while producing useless results.  For PDF material, a usable teaching
        image therefore needs both sufficient visual detail and a nearby
        Figure caption; ordinary Markdown/DOCX images retain their explicit
        author-provided text path.
        """

        images: list[ExtractedImage] = []
        errors: list[str] = []
        try:
            pdf = fitz.open(source_path)
        except Exception as exc:
            return [], [f"PDF 图片读取失败：{type(exc).__name__}"]
        try:
            ordinal = 0
            seen: set[str] = set()
            for page_number, page in enumerate(pdf, start=1):
                captions = self._pdf_figure_captions(page)
                for image_info in page.get_images(full=True):
                    try:
                        xref = int(image_info[0])
                        extracted = pdf.extract_image(xref)
                        payload = bytes(extracted.get("image", b""))
                        extension = str(extracted.get("ext") or "").lower()
                        mime = _IMAGE_MIME_BY_EXTENSION.get(f".{extension}")
                        if not payload or not mime:
                            errors.append(f"PDF 第 {page_number} 页：图片格式不支持")
                            continue
                        digest = hashlib.sha256(payload).hexdigest()
                        if digest in seen:
                            continue
                        seen.add(digest)
                        try:
                            _, width, height = inspect_image(payload, mime)
                        except ValueError:
                            errors.append(f"PDF 第 {page_number} 页：图片内容无效")
                            continue
                        rects = list(page.get_image_rects(xref))
                        caption = self._nearest_caption(rects[0] if rects else None, captions)
                        if not self._is_evidence_figure(width, height, caption):
                            # This is expected for logos and layout elements;
                            # keep it out of learner-facing error messages.
                            continue
                        assert caption is not None
                        caption_text = self._clean_caption(caption.text)
                        concepts = tuple(self._entity_names(caption_text))
                        images.append(ExtractedImage(
                            payload,
                            f"第{page_number}页{caption.label}.{extension}",
                            mime,
                            page_number,
                            ordinal,
                            caption_text,
                            f"第 {page_number} 页 · {caption.label}",
                            concepts,
                        ))
                        ordinal += 1
                    except Exception as exc:
                        errors.append(f"PDF 第 {page_number} 页：{type(exc).__name__}")
                    if len(images) >= _MAX_DOCUMENT_IMAGES:
                        return images, errors
        finally:
            pdf.close()
        return images, errors

    @staticmethod
    def _clean_caption(value: str) -> str:
        return re.sub(r"\s+", " ", value).strip()[:900]

    @classmethod
    def _pdf_figure_captions(cls, page: fitz.Page) -> list[FigureCaption]:
        captions: list[FigureCaption] = []
        # Captions in English and Chinese publications usually occupy their
        # own text block.  Anchoring at the start of the block prevents a
        # body paragraph that merely mentions "Figure 1"/"图1" from becoming
        # an image caption, while supporting the common punctuation variants.
        patterns = (
            re.compile(r"^\s*(?P<label>\b(?:fig(?:ure)?\.?\s*\d+[a-z]?\.?))\s*(?:[:：.\-]\s*|\s+)(?P<body>.+)", re.I | re.S),
            re.compile(r"^\s*(?P<label>图\s*\d+[a-z]?)\s*(?:[:：.、\-]\s*|\s+)(?P<body>.+)", re.I | re.S),
        )
        for block in page.get_text("blocks"):
            if len(block) < 5:
                continue
            text = cls._clean_caption(str(block[4]))
            match = next((candidate for pattern in patterns if (candidate := pattern.match(text))), None)
            if not match:
                continue
            caption = cls._clean_caption(match.group(0))
            label = cls._normalize_figure_label(str(match.group("label")))
            if not label or len(caption) < 12:
                continue
            captions.append(FigureCaption(
                text=caption,
                rect=fitz.Rect(float(block[0]), float(block[1]), float(block[2]), float(block[3])),
                label=label,
            ))
        return captions

    @staticmethod
    def _normalize_figure_label(value: str) -> str:
        compact = re.sub(r"\s+", " ", value).strip().rstrip(".")
        if re.match(r"^图", compact, re.I):
            return re.sub(r"\s+", "", compact)
        return re.sub(r"^Figure", "Fig.", compact, flags=re.I)

    @staticmethod
    def _nearest_caption(image_rect: fitz.Rect | None, captions: list[FigureCaption]) -> FigureCaption | None:
        if image_rect is None or not captions:
            return None
        image_center = ((image_rect.x0 + image_rect.x1) / 2, (image_rect.y0 + image_rect.y1) / 2)

        def distance(candidate: FigureCaption) -> float:
            caption_center = ((candidate.rect.x0 + candidate.rect.x1) / 2, (candidate.rect.y0 + candidate.rect.y1) / 2)
            # Captions immediately below a figure are the common case.  A
            # left/right distance penalty handles multi-column layouts.
            vertical = candidate.rect.y0 - image_rect.y1
            if vertical >= -18:
                return max(vertical, 0) + abs(caption_center[0] - image_center[0]) * 0.18
            return 180 + hypot(caption_center[0] - image_center[0], caption_center[1] - image_center[1])

        selected = min(captions, key=distance)
        return selected if distance(selected) <= 420 else None

    @staticmethod
    def _is_evidence_figure(width: int, height: int, caption: FigureCaption | None) -> bool:
        # 76x56 publisher icons and similar assets are not useful visual
        # evidence.  Wide image strips remain valid because endoscopy figures
        # frequently contain a labelled sequence of frames.
        return caption is not None and width >= 160 and height >= 100 and width * height >= 28_000

    def _extract_docx(self, source_path: Path) -> tuple[list[ExtractedImage], list[str]]:
        images: list[ExtractedImage] = []
        errors: list[str] = []
        try:
            with zipfile.ZipFile(source_path) as archive:
                ordinal = 0
                for name in archive.namelist():
                    if not name.startswith("word/media/") or name.endswith("/"):
                        continue
                    payload = archive.read(name)
                    extension = Path(name).suffix.lower()
                    mime = _IMAGE_MIME_BY_EXTENSION.get(extension) or mimetypes.guess_type(name)[0]
                    if mime not in _IMAGE_MIME_BY_EXTENSION.values():
                        errors.append(f"DOCX {Path(name).name}：图片格式不支持")
                        continue
                    images.append(ExtractedImage(payload, Path(name).name, mime, 1, ordinal))
                    ordinal += 1
                    if len(images) >= _MAX_DOCUMENT_IMAGES:
                        break
        except (OSError, zipfile.BadZipFile) as exc:
            errors.append(f"DOCX 图片读取失败：{type(exc).__name__}")
        return images, errors

    def _extract_markdown_images(self, source_path: Path) -> tuple[list[ExtractedImage], list[str]]:
        try:
            text = source_path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return [], [f"资料图片读取失败：{type(exc).__name__}"]
        images: list[ExtractedImage] = []
        errors: list[str] = []
        for ordinal, match in enumerate(re.finditer(r"!\[([^]]*)\]\(([^)]+)\)", text)):
            raw_path = match.group(2).strip().strip("<>")
            if not raw_path or re.match(r"^(?:data:|https?://)", raw_path, re.I):
                continue
            normalised = posixpath.normpath(raw_path.replace("\\", "/"))
            if normalised in {"", ".", ".."} or normalised.startswith("../") or Path(normalised).is_absolute():
                errors.append(f"Markdown 图片路径不安全：{raw_path}")
                continue
            candidate = (source_path.parent / Path(normalised)).resolve()
            if source_path.parent.resolve() not in candidate.parents or not candidate.is_file():
                errors.append(f"Markdown 图片不存在：{raw_path}")
                continue
            mime = _IMAGE_MIME_BY_EXTENSION.get(candidate.suffix.lower())
            if not mime:
                errors.append(f"Markdown 图片格式不支持：{candidate.name}")
                continue
            images.append(ExtractedImage(candidate.read_bytes(), candidate.name, mime, 1, ordinal, match.group(1).strip() or None))
        return images[:_MAX_DOCUMENT_IMAGES], errors

    def _link_assets_to_chunks(self, session: Any, document_id: str, version_id: str, assets: list[KnowledgeMediaAssetModel]) -> None:
        chunks = list(session.scalars(select(KnowledgeChunkModel).where(
            KnowledgeChunkModel.document_id == document_id,
            KnowledgeChunkModel.version_id == version_id,
        ).order_by(KnowledgeChunkModel.ordinal)))
        if not chunks:
            return
        assignments: dict[str, list[str]] = {chunk.chunk_id: [] for chunk in chunks}
        for asset in assets:
            candidates = [chunk for chunk in chunks if chunk.page == asset.page] or chunks
            selected = max(candidates, key=lambda chunk: self._caption_chunk_score(asset.alt_text or "", chunk.content))
            assignments[selected.chunk_id].append(asset.asset_id)
        for chunk in chunks:
            chunk.media_asset_ids = assignments[chunk.chunk_id]
            chunk.modality = "mixed" if assignments[chunk.chunk_id] else "text"

    @staticmethod
    def _caption_chunk_score(caption: str, content: str) -> float:
        normalized_caption = caption.lower()
        normalized_content = content.lower()
        figure = re.search(r"\bfig(?:ure)?\.?\s*(\d+[a-z]?)", normalized_caption)
        if figure and re.search(rf"\bfig(?:ure)?\.?\s*{re.escape(figure.group(1))}\b", normalized_content):
            return 1000.0
        terms = set(re.findall(r"[a-z]{4,}|[\u4e00-\u9fff]{2,}", normalized_caption))
        return float(sum(1 for term in terms if term in normalized_content))

    def _rebuild_graph(self, session: Any, document_id: str, version_id: str) -> tuple[int, int]:
        chunk_ids = list(session.scalars(select(KnowledgeChunkModel.chunk_id).where(
            KnowledgeChunkModel.document_id == document_id,
            KnowledgeChunkModel.version_id == version_id,
        )))
        if chunk_ids:
            session.execute(delete(KnowledgeRelationModel).where(KnowledgeRelationModel.document_id == document_id))
        session.execute(delete(KnowledgeEntityModel).where(KnowledgeEntityModel.document_id == document_id))
        entity_by_name: dict[str, KnowledgeEntityModel] = {}
        edges: set[tuple[str, str, str]] = set()
        chunks = list(session.scalars(select(KnowledgeChunkModel).where(KnowledgeChunkModel.chunk_id.in_(chunk_ids)).order_by(KnowledgeChunkModel.ordinal)))
        chunk_by_id = {chunk.chunk_id: chunk for chunk in chunks}

        def get_concept(name: str, chunk_id: str) -> KnowledgeEntityModel:
            entity = entity_by_name.get(name)
            if entity is None:
                entity = KnowledgeEntityModel(
                    entity_id=f"entity_{hashlib.sha256(f'{document_id}:{name}'.encode()).hexdigest()[:20]}",
                    document_id=document_id,
                    canonical_name=name,
                    entity_type="concept",
                    properties={"evidence_chunk_ids": [chunk_id]},
                )
                entity_by_name[name] = entity
                session.add(entity)
            else:
                evidence = list(entity.properties.get("evidence_chunk_ids", []))
                if chunk_id not in evidence:
                    entity.properties = {**entity.properties, "evidence_chunk_ids": evidence + [chunk_id]}
            return entity

        for chunk in chunks:
            names = self._entity_names(f"{chunk.parent_section}\n{chunk.content}")
            entities = [get_concept(name, chunk.chunk_id) for name in names]
            for left, right in zip(entities, entities[1:]):
                key = (left.entity_id, right.entity_id, chunk.chunk_id)
                if key in edges:
                    continue
                edges.add(key)
                session.add(KnowledgeRelationModel(
                    relation_id=f"relation_{hashlib.sha256(':'.join(key).encode()).hexdigest()[:20]}",
                    document_id=document_id,
                    source_entity_id=left.entity_id,
                    target_entity_id=right.entity_id,
                    relation_type="co_occurs_in_text",
                    chunk_id=chunk.chunk_id,
                    confidence=0.62,
                ))
        assets = list(session.scalars(select(KnowledgeMediaAssetModel).where(
            KnowledgeMediaAssetModel.document_id == document_id,
            KnowledgeMediaAssetModel.version_id == version_id,
            KnowledgeMediaAssetModel.status == "ready",
        )))
        for asset in assets:
            linked = next((chunk for chunk in chunks if asset.asset_id in (chunk.media_asset_ids or [])), None)
            if linked is None:
                continue
            concepts = self._entity_names(asset.alt_text or "")
            if not concepts:
                continue
            image_name = f"图片 {asset.asset_id}"
            image_entity = KnowledgeEntityModel(
                entity_id=f"media_{hashlib.sha256(asset.asset_id.encode()).hexdigest()[:20]}",
                document_id=document_id,
                canonical_name=image_name,
                entity_type="figure",
                properties={
                    "media_asset_ids": [asset.asset_id],
                    "caption": asset.alt_text or "",
                    "page": asset.page,
                    "section": linked.parent_section,
                    "concepts": concepts,
                },
            )
            entity_by_name[image_name] = image_entity
            session.add(image_entity)
            for concept_name in concepts:
                concept = get_concept(concept_name, linked.chunk_id)
                key = (concept.entity_id, image_entity.entity_id, linked.chunk_id)
                if key in edges:
                    continue
                edges.add(key)
                session.add(KnowledgeRelationModel(
                    relation_id=f"relation_{hashlib.sha256(':'.join(key).encode()).hexdigest()[:20]}",
                    document_id=document_id,
                    source_entity_id=concept.entity_id,
                    target_entity_id=image_entity.entity_id,
                    relation_type="depicted_in_figure",
                    chunk_id=linked.chunk_id,
                    confidence=0.95,
                ))
        return len(entity_by_name), len(edges)

    @staticmethod
    def _entity_names(content: str) -> list[str]:
        """Extract only governed, evidence-bearing graph concepts.

        This is intentionally not an OCR/NLP guesser.  The evidence graph is
        used to expand learner-facing retrieval context, so a false node is
        worse than a missing node: it creates a plausible-looking but
        ungrounded relation.  New domain vocabulary is added to the controlled
        list above as the product supports more learning packs.
        """

        lowered = content.lower()
        found: list[str] = []
        for term in _COMMON_ENTITY_TERMS:
            normalized = term.lower()
            if normalized not in lowered or normalized in _ENTITY_STOPWORDS:
                continue
            canonical = _CONCEPT_ALIASES.get(normalized, term)
            # Prefer a specific phrase (for example ``image documentation``)
            # over its generic component (``image``).  This keeps graph hops
            # meaningful without hidden model inference.
            if canonical in found or any(normalized in item.lower() for item in found):
                continue
            found = [item for item in found if item.lower() not in normalized and item not in {"内镜", "胃镜", "结肠镜"}]
            found.append(canonical)
        return found[:8]

    @staticmethod
    def _safe_filename(value: str) -> str:
        name = Path(value).name.strip() or "knowledge-image"
        return re.sub(r"[^A-Za-z0-9._-\u4e00-\u9fff]", "_", name)[:300]

    def _remove_document_media(self, document_id: str, *, keep_version_id: str) -> None:
        with SessionLocal() as session:
            rows = list(session.scalars(select(KnowledgeMediaAssetModel).where(
                KnowledgeMediaAssetModel.document_id == document_id,
                KnowledgeMediaAssetModel.version_id != keep_version_id,
            )))
            # Also remove assets from a retried build of the same version.
            rows.extend(list(session.scalars(select(KnowledgeMediaAssetModel).where(
                KnowledgeMediaAssetModel.document_id == document_id,
                KnowledgeMediaAssetModel.version_id == keep_version_id,
            ))))
            for row in rows:
                path = (KNOWLEDGE_MEDIA_ROOT / row.storage_path).resolve()
                if KNOWLEDGE_MEDIA_ROOT.resolve() in path.parents:
                    path.unlink(missing_ok=True)
                session.delete(row)
            session.commit()
        old_root = KNOWLEDGE_MEDIA_ROOT / document_id
        if old_root.is_dir():
            for child in old_root.iterdir():
                if child.name != keep_version_id and child.is_dir():
                    shutil.rmtree(child, ignore_errors=True)


knowledge_multimodal_service = KnowledgeMultimodalService()
