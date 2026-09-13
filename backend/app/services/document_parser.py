"""Layout-aware document parsing for the knowledge library.

The parser is intentionally dependency-light.  PyMuPDF and python-docx are
the fast, deterministic path used by the local product; an optional Docling
adapter can be added later without changing the parsed-document contract.
The important boundary is that every source becomes structured elements before
chunking.  Page snapshots are kept as preview evidence and are never treated as
teaching figures by the image index.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Iterable

import fitz


URL_ONLY_RE = re.compile(r"^(?:https?://|www\.)\S+$", re.IGNORECASE)
FIGURE_CAPTION_RE = re.compile(
    r"^\s*(?P<label>(?:fig(?:ure)?\.?\s*\d+(?:[-–]\d+)?[a-z]?|图\s*\d+(?:[-–]\d+)?[a-z]?))"
    # OCR frequently removes the punctuation/space after a label, for
    # example ``图1-2颈椎...``.  Accept that form only when the caption body
    # starts with a letter, so a prose fragment such as ``图2-1），此外...``
    # is not promoted to a figure caption.
    r"\s*(?:[:：.、\-]\s*|\s+|(?=[A-Za-z\u4e00-\u9fff]))(?P<body>.+)$",
    re.IGNORECASE | re.DOTALL,
)
HEADING_RE = re.compile(r"^\s*(?:\d+(?:\.\d+){0,4}[.)]?\s+|[一二三四五六七八九十]+[、.]\s+)?[^.!?。！？]{2,90}$")
OCR_HEADING_RE = re.compile(
    r"^\s*(?:"
    r"第\s*[0-9一二三四五六七八九十百千万]+\s*[章节篇部]"
    r"|\d+(?:\.\d+){1,4}\s*[.)、]?\s*\S"
    r"|[一二三四五六七八九十百千万]+\s*[、.]\s*\S"
    r"|[（(]\s*[0-9一二三四五六七八九十百千万]+\s*[）)]\s*\S"
    r")"
)
OCR_RENDER_SCALE = max(1.0, min(2.5, float(os.getenv("TIBAN_OCR_RENDER_SCALE", "1.5"))))
OCR_CACHE_ROOT = Path(os.getenv(
    "TIBAN_OCR_CACHE_DIR",
    Path(__file__).resolve().parents[2] / "runtime" / "ocr-pages",
))


def estimate_tokens(value: str) -> int:
    """Return a stable token estimate without loading an embedding model.

    CJK characters are close to one token, while Latin words and punctuation
    are counted in small groups.  This is deliberately an upper-bound-ish
    fallback used for chunk sizing, not a model quality metric.
    """

    text = str(value or "")
    cjk = len(re.findall(r"[\u4e00-\u9fff]", text))
    latin = len(re.findall(r"[A-Za-z0-9_]+", text))
    punctuation = len(re.findall(r"[^\w\s\u4e00-\u9fff]", text, re.UNICODE))
    whitespace = len(re.findall(r"\s+", text))
    return max(1, cjk + math.ceil(latin * 1.25) + math.ceil(punctuation / 4) + math.ceil(whitespace / 8))


@dataclass(frozen=True)
class DocumentElement:
    element_id: str
    element_type: str
    page: int
    bbox: tuple[float, float, float, float] | None
    reading_order: int
    parent_element_id: str | None
    section_path: str
    text: str
    source_version_id: str | None = None


@dataclass(frozen=True)
class ParsedImage:
    element_id: str
    payload: bytes
    filename: str
    mime_type: str
    page: int
    bbox: tuple[float, float, float, float] | None
    asset_type: str = "figure"
    caption: str | None = None
    section_path: str | None = None
    concepts: tuple[str, ...] = ()


@dataclass
class DocumentParseStats:
    page_count: int = 0
    pages_with_text: int = 0
    pages_needing_ocr: int = 0
    table_count: int = 0
    figure_count: int = 0
    page_snapshot_count: int = 0
    filtered_asset_count: int = 0
    blank_page_count: int = 0
    chunk_count: int = 0
    text_token_count: int = 0
    failed_pages: list[int] = field(default_factory=list)
    ocr_engine: str | None = None
    ocr_pages_processed: int = 0
    ocr_cache_hits: int = 0

    @property
    def coverage(self) -> float:
        if self.page_count <= 0:
            return 0.0
        # A page waiting for OCR is not covered yet.  Counting it as complete
        # made a scanned 400-page book appear fully processed with zero text.
        return round(self.pages_with_text / self.page_count, 4)

    def as_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["coverage"] = self.coverage
        return value


@dataclass
class ParsedChunk:
    content: str
    section_path: str
    page_start: int
    page_end: int
    ordinal: int
    element_ids: list[str]
    element_type: str
    parent_chunk_id: str
    provenance: dict[str, Any]
    token_count: int


@dataclass
class ParsedDocument:
    source_path: Path
    parser: str
    elements: list[DocumentElement]
    images: list[ParsedImage]
    stats: DocumentParseStats
    source_version_id: str | None = None

    def text_projection(self) -> str:
        """Create a readable runtime projection for legacy index consumers."""

        lines: list[str] = []
        current_page = 0
        for element in self.elements:
            if element.page != current_page:
                current_page = element.page
                lines.append(f"## 第 {current_page} 页")
            if not element.text.strip() or URL_ONLY_RE.fullmatch(element.text.strip()):
                continue
            if element.element_type == "heading":
                lines.append(f"### {element.text.strip()}")
            elif element.element_type == "caption":
                lines.append(f"**{element.text.strip()}**")
            else:
                lines.append(element.text.strip())
        return "\n\n".join(lines).strip() + "\n"

    def chunks(self, *, max_tokens: int = 450, overlap_tokens: int = 60) -> list[ParsedChunk]:
        """Build hierarchy-aware chunks from elements, not from raw pages."""

        max_tokens = max(120, int(max_tokens))
        overlap_tokens = max(0, min(int(overlap_tokens), max_tokens // 3))
        # Page snapshots are visual preview evidence only.  They are never
        # indexed as if the page itself were extracted teaching text.
        candidates = [
            element for element in self.elements
            if element.element_type != "page_snapshot" and _indexable_text(element.text)
        ]
        chunks: list[ParsedChunk] = []
        buffer: list[DocumentElement] = []
        buffer_tokens = 0

        def flush(items: list[DocumentElement]) -> None:
            if not items:
                return
            content = _render_elements(items)
            if not _indexable_text(content):
                return
            first = items[0]
            last = items[-1]
            section = first.section_path or "导言"
            element_type = "mixed" if len({item.element_type for item in items}) > 1 else first.element_type
            parent_id = "parent-" + hashlib.sha256(f"{self.source_path}:{section}".encode("utf-8")).hexdigest()[:16]
            ordinal = len(chunks)
            chunks.append(ParsedChunk(
                content=content,
                section_path=section,
                page_start=first.page,
                page_end=last.page,
                ordinal=ordinal,
                element_ids=[item.element_id for item in items],
                element_type=element_type,
                parent_chunk_id=parent_id,
                provenance={
                    "source_path": self.source_path.name,
                    "page_start": first.page,
                    "page_end": last.page,
                    "section_path": section,
                    "element_ids": [item.element_id for item in items],
                },
                token_count=estimate_tokens(content),
            ))

        def overlap_tail(items: list[DocumentElement]) -> tuple[list[DocumentElement], int]:
            """Keep a bounded context tail without carrying history forward.

            The previous implementation kept the whole short buffer whenever
            a new OCR heading changed the section.  With noisy OCR this made
            every following chunk contain all preceding text.  A tail is only
            useful when it contains one or two small context elements from the
            same section, and it must never exceed the requested overlap.
            """

            if overlap_tokens <= 0 or not items:
                return [], 0
            tail: list[DocumentElement] = []
            tail_tokens = 0
            for prior in reversed(items):
                if prior.element_type == "heading":
                    break
                prior_tokens = estimate_tokens(prior.text)
                if prior_tokens > overlap_tokens or tail_tokens + prior_tokens > overlap_tokens:
                    break
                tail.insert(0, prior)
                tail_tokens += prior_tokens
                if len(tail) >= 2:
                    break
            return tail, tail_tokens

        for element in candidates:
            element_tokens = estimate_tokens(element.text)
            # A long paragraph/heading is split on sentence or character
            # boundaries while retaining a small overlap for retrieval context.
            if element_tokens > max_tokens:
                if buffer:
                    flush(buffer)
                    buffer = []
                    buffer_tokens = 0
                pieces = _split_long_text(element.text, max_tokens, overlap_tokens)
                for piece_index, piece in enumerate(pieces):
                    synthetic = DocumentElement(
                        element_id=f"{element.element_id}-part-{piece_index}",
                        element_type=element.element_type,
                        page=element.page,
                        bbox=element.bbox,
                        reading_order=element.reading_order,
                        parent_element_id=element.parent_element_id,
                        section_path=element.section_path,
                        text=piece,
                        source_version_id=element.source_version_id,
                    )
                    flush([synthetic])
                continue
            if buffer and (buffer_tokens + element_tokens > max_tokens or element.section_path != buffer[0].section_path):
                previous = buffer
                flush(previous)
                # Never carry context across a real section boundary.  For
                # size-based splits, keep only a bounded tail from the same
                # section and never let it grow cumulatively.
                if element.section_path != previous[0].section_path:
                    buffer = []
                    buffer_tokens = 0
                else:
                    buffer, buffer_tokens = overlap_tail(previous)
            # A retained tail plus the next element can itself exceed the
            # limit.  Flush the tail and start the new element cleanly.
            if buffer and buffer_tokens + element_tokens > max_tokens:
                flush(buffer)
                buffer = []
                buffer_tokens = 0
            buffer.append(element)
            buffer_tokens += element_tokens
        flush(buffer)
        self.stats.chunk_count = len(chunks)
        self.stats.text_token_count = sum(item.token_count for item in chunks)
        return chunks


def _indexable_text(value: str) -> bool:
    compact = re.sub(r"\s+", " ", str(value or "")).strip()
    if not compact or URL_ONLY_RE.fullmatch(compact):
        return False
    return any(char.isalnum() or "\u4e00" <= char <= "\u9fff" for char in compact)


def _render_elements(elements: Iterable[DocumentElement]) -> str:
    rendered: list[str] = []
    for element in elements:
        text = re.sub(r"\s+", " ", element.text).strip()
        if not _indexable_text(text):
            continue
        if element.element_type == "heading":
            # OCR headings commonly become their own section_path.  Rendering
            # both values produced visible duplicate titles in previews and
            # also inflated the retrieval text.
            rendered.append(text if element.section_path == text else f"{element.section_path}\n{text}")
        elif element.element_type == "caption":
            rendered.append(f"图注：{text}")
        else:
            rendered.append(text)
    return "\n\n".join(rendered)


def _split_long_text(value: str, max_tokens: int, overlap_tokens: int) -> list[str]:
    text = re.sub(r"\s+", " ", value).strip()
    if estimate_tokens(text) <= max_tokens:
        return [text]
    # Prefer sentence/line boundaries.  The final character fallback also
    # handles OCR output and long tables without losing the entire page.
    units = [part.strip() for part in re.split(r"(?<=[。！？.!?；;])\s+|\n+", text) if part.strip()]
    if not units:
        units = [text]
    pieces: list[str] = []
    current = ""
    for unit in units:
        candidate = f"{current} {unit}".strip()
        if current and estimate_tokens(candidate) > max_tokens:
            pieces.append(current)
            overlap = current[-max(0, overlap_tokens * 2):] if overlap_tokens else ""
            current = f"{overlap} {unit}".strip()
        elif estimate_tokens(unit) > max_tokens:
            if current:
                pieces.append(current)
                current = ""
            step = max(80, max_tokens * 2)
            raw = unit
            for start in range(0, len(raw), max(1, step - overlap_tokens * 2)):
                pieces.append(raw[start:start + step])
            current = ""
        else:
            current = candidate
    if current:
        pieces.append(current)
    return [part for part in pieces if _indexable_text(part)]


def parse_document(
    source_path: Path,
    *,
    source_version_id: str | None = None,
    progress_callback: Callable[[str, int, int], None] | None = None,
) -> ParsedDocument:
    suffix = source_path.suffix.lower()
    if suffix == ".pdf":
        return _parse_pdf(source_path, source_version_id=source_version_id, progress_callback=progress_callback)
    if suffix == ".docx":
        return _parse_docx(source_path, source_version_id=source_version_id)
    if suffix in {".md", ".txt"}:
        return _parse_plain(source_path, source_version_id=source_version_id)
    if suffix == ".doc":
        raise ValueError("旧版 DOC 需要先另存为 DOCX 或 PDF。")
    raise ValueError(f"暂不支持 {suffix or '未知'} 文件格式。")


def _parse_plain(source_path: Path, *, source_version_id: str | None) -> ParsedDocument:
    text = source_path.read_text(encoding="utf-8", errors="replace")
    stats = DocumentParseStats(page_count=1, pages_with_text=1 if _indexable_text(text) else 0)
    elements: list[DocumentElement] = []
    section = "导言"
    order = 0
    for line in text.splitlines():
        clean = re.sub(r"\s+", " ", line).strip()
        if not clean or URL_ONLY_RE.fullmatch(clean):
            continue
        element_type = "heading" if clean.startswith("#") else "paragraph"
        if element_type == "heading":
            section = clean.lstrip("#").strip() or section
        elements.append(DocumentElement(
            element_id=f"line-{order}", element_type=element_type, page=1, bbox=None,
            reading_order=order, parent_element_id=None, section_path=section,
            text=clean.lstrip("#").strip(), source_version_id=source_version_id,
        ))
        order += 1
    if not elements:
        raise ValueError("未能从资料中解析出可索引正文。")
    parser = "heading-aware-markdown" if source_path.suffix.lower() == ".md" else "utf8-text"
    return ParsedDocument(source_path, parser, elements, [], stats, source_version_id)


def _parse_pdf(
    source_path: Path,
    *,
    source_version_id: str | None,
    progress_callback: Callable[[str, int, int], None] | None = None,
) -> ParsedDocument:
    try:
        pdf = fitz.open(source_path)
    except Exception as exc:
        raise ValueError(f"PDF 无法读取：{type(exc).__name__}") from exc
    stats = DocumentParseStats(page_count=len(pdf))
    elements: list[DocumentElement] = []
    images: list[ParsedImage] = []
    repeated_lines = _repeated_page_lines(pdf)
    reading_order = 0
    section = "导言"
    cache_key = _ocr_source_cache_key(source_path)
    try:
        for page_number, page in enumerate(pdf, start=1):
            try:
                blocks = page.get_text("blocks", sort=True)
                page_text: list[str] = []
                ocr_elements: list[DocumentElement] = []
                captions = _caption_blocks(blocks)
                for block_index, block in enumerate(blocks):
                    if len(block) < 5 or int(block[6]) != 0:
                        continue
                    raw = str(block[4] or "")
                    for line in raw.splitlines():
                        clean = re.sub(r"\s+", " ", line).strip()
                        if not _indexable_text(clean) or clean in repeated_lines or URL_ONLY_RE.fullmatch(clean):
                            continue
                        page_text.append(clean)
                        is_caption = any(clean == item[0] or clean.startswith(item[0]) for item in captions)
                        is_heading = not is_caption and _looks_like_heading(clean)
                        if is_heading and len(clean) <= 120:
                            section = clean
                        element_type = "caption" if is_caption else "heading" if is_heading else "paragraph"
                        bbox = (float(block[0]), float(block[1]), float(block[2]), float(block[3]))
                        elements.append(DocumentElement(
                            element_id=f"p{page_number}-t{block_index}-{reading_order}",
                            element_type=element_type, page=page_number, bbox=bbox,
                            reading_order=reading_order, parent_element_id=None,
                            section_path=section, text=clean, source_version_id=source_version_id,
                        ))
                        reading_order += 1
                if not page_text:
                    before_cache_hits = stats.ocr_cache_hits
                    ocr_elements = _ocr_page_elements(
                        page, page_number, section, source_version_id, cache_key=cache_key,
                    )
                    if _ocr_page_cache_exists(cache_key, page_number):
                        stats.ocr_cache_hits += 1
                    if ocr_elements:
                        elements.extend(
                            DocumentElement(
                                element_id=f"{item.element_id}-ocr",
                                element_type=item.element_type,
                                page=item.page,
                                bbox=item.bbox,
                                reading_order=reading_order + offset,
                                parent_element_id=item.parent_element_id,
                                section_path=item.section_path,
                                text=item.text,
                                source_version_id=item.source_version_id,
                            )
                            for offset, item in enumerate(ocr_elements)
                        )
                        reading_order += len(ocr_elements)
                        page_text.extend(item.text for item in ocr_elements)
                        stats.ocr_pages_processed += 1
                        stats.ocr_engine = "rapidocr_onnxruntime"
                    elif _ocr_page_cache_exists(cache_key, page_number) and stats.ocr_cache_hits == before_cache_hits:
                        # An empty cached result is still a processed page;
                        # keeping this distinction prevents a restart from
                        # repeatedly trying a page that OCR already failed.
                        stats.ocr_engine = stats.ocr_engine or "rapidocr_onnxruntime"
                if page_text:
                    stats.pages_with_text += 1
                image_items, filtered = _pdf_images(
                    page, pdf, page_number, captions, section, source_version_id,
                    reading_order, ocr_elements=ocr_elements,
                )
                images.extend(image_items)
                stats.figure_count += sum(item.asset_type == "figure" for item in image_items)
                stats.page_snapshot_count += sum(item.asset_type == "page_snapshot" for item in image_items)
                stats.filtered_asset_count += filtered
                if not page_text and not image_items:
                    if _is_visually_blank_page(page):
                        stats.blank_page_count += 1
                    else:
                        stats.pages_needing_ocr += 1
                        stats.failed_pages.append(page_number)
                elif not page_text and image_items:
                    # A full-page scan is visual preview evidence, not an
                    # extracted figure.  It still needs OCR before text search.
                    if all(item.asset_type == "page_snapshot" for item in image_items):
                        stats.pages_needing_ocr += 1
                        stats.failed_pages.append(page_number)
                if progress_callback is not None:
                    progress_callback("OCR" if not page_text else "解析文档", page_number, len(pdf))
            except Exception:
                stats.failed_pages.append(page_number)
    finally:
        pdf.close()
    if not elements and images:
        # This is a status anchor, not extracted正文.  It makes the source
        # visible in the library while keeping retrieval honest until OCR is
        # configured for the scanned pages.
        elements.append(DocumentElement(
            element_id="document-ocr-required", element_type="page_snapshot", page=1,
            bbox=None, reading_order=0, parent_element_id=None, section_path="资料状态",
            text=f"《{source_path.stem}》为扫描版 PDF，页面文字尚未完成识别。当前仅保留页面预览，不能据此生成正文证据。",
            source_version_id=source_version_id,
        ))
    if not elements and not images:
        raise ValueError("未能从 PDF 中解析出正文或可预览页面。")
    if stats.ocr_pages_processed:
        parser = "pymupdf-layout-aware+rapidocr"
    else:
        parser = "pymupdf-layout-aware" if stats.pages_with_text else "pymupdf-scanned-pages"
    return ParsedDocument(source_path, parser, elements, images, stats, source_version_id)


@lru_cache(maxsize=1)
def _get_ocr_engine() -> Any | None:
    """Load the local OCR adapter only when a scanned page needs it.

    OCR is deliberately optional at import time.  Text-native PDFs and all
    existing Markdown/DOCX flows do not pay the model-loading cost, while a
    scanned PDF gets a real OCR path when the desktop dependency is installed.
    """

    try:
        from rapidocr_onnxruntime import RapidOCR
    except Exception:
        return None
    try:
        return RapidOCR()
    except Exception:
        return None


def _ocr_source_cache_key(source_path: Path) -> str:
    """Return a stable runtime-only key for page OCR results.

    The cache deliberately uses file metadata instead of copying the source or
    storing its contents in the database.  A changed file gets a new key, and
    a restarted worker can reuse completed pages from the same source.
    """

    try:
        stat = source_path.stat()
        identity = f"{source_path.resolve()}:{stat.st_size}:{stat.st_mtime_ns}:scale={OCR_RENDER_SCALE}"
    except OSError:
        identity = str(source_path)
    return hashlib.sha256(identity.encode("utf-8", errors="replace")).hexdigest()[:24]


def _ocr_page_cache_path(cache_key: str, page_number: int) -> Path:
    return OCR_CACHE_ROOT / cache_key / f"page-{page_number:04d}.json"


def _ocr_page_cache_exists(cache_key: str, page_number: int) -> bool:
    return _ocr_page_cache_path(cache_key, page_number).is_file()


def _load_ocr_page_cache(cache_key: str, page_number: int) -> list[dict[str, Any]] | None:
    path = _ocr_page_cache_path(cache_key, page_number)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        items = payload.get("items") if isinstance(payload, dict) else None
        if not isinstance(items, list):
            return None
        return [item for item in items if isinstance(item, dict)]
    except (OSError, ValueError, TypeError):
        # A half-written cache entry is disposable.  The page will be OCR'd
        # again and rewritten atomically below.
        return None


def _save_ocr_page_cache(cache_key: str, page_number: int, items: list[dict[str, Any]]) -> None:
    path = _ocr_page_cache_path(cache_key, page_number)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps({"version": 1, "items": items}, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        temporary.replace(path)
    except OSError:
        # OCR cache is an optimization, never a reason to fail document
        # indexing.  The current page still remains available in memory.
        return


def _ocr_page_elements(
    page: fitz.Page,
    page_number: int,
    section: str,
    source_version_id: str | None,
    *,
    cache_key: str | None = None,
) -> list[DocumentElement]:
    engine = _get_ocr_engine()
    cached_items = _load_ocr_page_cache(cache_key, page_number) if cache_key else None
    if cached_items is None:
        if engine is None:
            return []
        try:
            # 1.5x is materially faster on scanned Chinese textbooks while
            # RapidOCR's own max-side limit keeps memory bounded.
            pixmap = page.get_pixmap(matrix=fitz.Matrix(OCR_RENDER_SCALE, OCR_RENDER_SCALE), alpha=False)
            result, _elapsed = engine(pixmap.tobytes("png"))
        except Exception:
            return []
        if not result:
            if cache_key:
                _save_ocr_page_cache(cache_key, page_number, [])
            return []
        scale_x = float(page.rect.width) / max(float(pixmap.width), 1.0)
        scale_y = float(page.rect.height) / max(float(pixmap.height), 1.0)
        cached_items = []
        for raw_item in result:
            if not isinstance(raw_item, (list, tuple)) or len(raw_item) < 2:
                continue
            raw_box, raw_text = raw_item[0], raw_item[1]
            text = re.sub(r"\s+", " ", str(raw_text or "")).strip()
            if not _indexable_text(text) or URL_ONLY_RE.fullmatch(text) or text.strip("� ") == "":
                continue
            try:
                points = [(float(point[0]), float(point[1])) for point in raw_box]
                bbox = [
                    min(point[0] for point in points) * scale_x,
                    min(point[1] for point in points) * scale_y,
                    max(point[0] for point in points) * scale_x,
                    max(point[1] for point in points) * scale_y,
                ]
            except (TypeError, ValueError, IndexError):
                bbox = None
            cached_items.append({"text": text, "bbox": bbox})
        if cache_key:
            _save_ocr_page_cache(cache_key, page_number, cached_items)
    if not cached_items:
        return []
    cleaned_items = _dedupe_ocr_items(cached_items)
    if cache_key and cleaned_items != cached_items:
        _save_ocr_page_cache(cache_key, page_number, cleaned_items)
    cached_items = cleaned_items
    items: list[DocumentElement] = []
    current_section = section
    for index, cached_item in enumerate(cached_items):
        text = str(cached_item.get("text") or "").strip()
        raw_bbox = cached_item.get("bbox")
        bbox = tuple(float(value) for value in raw_bbox) if isinstance(raw_bbox, list) and len(raw_bbox) == 4 else None
        element_type = "caption" if FIGURE_CAPTION_RE.match(text) else "paragraph"
        if element_type != "caption" and _looks_like_ocr_heading(text):
            element_type = "heading"
            current_section = text[:120]
        items.append(DocumentElement(
            element_id=f"p{page_number}-ocr-{index}",
            element_type=element_type,
            page=page_number,
            bbox=bbox,
            reading_order=index,
            parent_element_id=None,
            section_path=current_section,
            text=text,
            source_version_id=source_version_id,
        ))
    return items


def _dedupe_ocr_items(items: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove OCR duplicates without deleting legitimate repeated labels.

    OCR engines can emit the same line twice at the same position, especially
    on scanned covers and watermarked pages.  Deduplicate by normalized text
    *and* rounded bbox; the same word at two different positions is retained.
    """

    result: list[dict[str, Any]] = []
    seen: set[tuple[str, tuple[float, ...] | None]] = set()
    for item in items:
        text = re.sub(r"\s+", " ", str(item.get("text") or "")).strip()
        if not text:
            continue
        raw_bbox = item.get("bbox")
        bbox: tuple[float, ...] | None = None
        if isinstance(raw_bbox, (list, tuple)) and len(raw_bbox) == 4:
            try:
                bbox = tuple(round(float(value), 1) for value in raw_bbox)
            except (TypeError, ValueError):
                bbox = None
        key = (text.casefold(), bbox)
        if key in seen:
            continue
        seen.add(key)
        result.append({"text": text, "bbox": list(bbox) if bbox is not None else raw_bbox})
    return result


def _is_visually_blank_page(page: fitz.Page) -> bool:
    """Distinguish an empty scan page from a page whose OCR failed."""

    try:
        pixmap = page.get_pixmap(matrix=fitz.Matrix(0.25, 0.25), alpha=False)
        samples = pixmap.samples
        channels = max(1, int(getattr(pixmap, "n", 3)))
        if not samples:
            return True
        dark_pixels = 0
        pixel_count = len(samples) // channels
        for offset in range(0, len(samples), channels):
            brightness = sum(samples[offset:offset + min(channels, 3)]) / min(channels, 3)
            if brightness < 238:
                dark_pixels += 1
        return pixel_count == 0 or dark_pixels / pixel_count < 0.002
    except Exception:
        # If a cheap blank-page probe fails, keep the conservative OCR-needed
        # classification rather than silently dropping a page.
        return False


def _repeated_page_lines(pdf: fitz.Document) -> set[str]:
    counts: dict[str, int] = {}
    page_count = max(len(pdf), 1)
    for page in pdf:
        for block in page.get_text("blocks"):
            if len(block) < 5 or int(block[6]) != 0:
                continue
            for line in str(block[4] or "").splitlines():
                clean = re.sub(r"\s+", " ", line).strip()
                if 3 <= len(clean) <= 140:
                    counts[clean] = counts.get(clean, 0) + 1
    threshold = max(3, math.ceil(page_count * 0.35))
    return {line for line, count in counts.items() if count >= threshold}


def _looks_like_heading(value: str) -> bool:
    if len(value) > 100 or URL_ONLY_RE.fullmatch(value):
        return False
    if FIGURE_CAPTION_RE.match(value):
        return False
    return bool(HEADING_RE.match(value)) and (value[:1].isdigit() or value[:1] in "一二三四五六七八九十" or len(value) < 42)


def _looks_like_ocr_heading(value: str) -> bool:
    """Use conservative section markers for OCR text.

    A generic "short line" heuristic classifies ordinary OCR body lines as
    headings.  That changes the section for every line and defeats chunking.
    Only explicit chapter/section numbering is trusted for scanned pages.
    """

    compact = re.sub(r"\s+", " ", str(value or "")).strip()
    if not compact or len(compact) > 100 or FIGURE_CAPTION_RE.match(compact):
        return False
    return bool(OCR_HEADING_RE.match(compact))


def _caption_blocks(blocks: Iterable[tuple[Any, ...]]) -> list[tuple[str, fitz.Rect, str]]:
    result: list[tuple[str, fitz.Rect, str]] = []
    for block in blocks:
        if len(block) < 5 or int(block[6]) != 0:
            continue
        text = re.sub(r"\s+", " ", str(block[4] or "")).strip()
        match = FIGURE_CAPTION_RE.match(text)
        if not match or len(text) < 12:
            continue
        label = re.sub(r"\s+", "", match.group("label")).rstrip(".")
        label = re.sub(r"^figure", "Fig.", label, flags=re.IGNORECASE)
        result.append((text, fitz.Rect(float(block[0]), float(block[1]), float(block[2]), float(block[3])), label))
    return result


def _pdf_images(
    page: fitz.Page,
    pdf: fitz.Document,
    page_number: int,
    captions: list[tuple[str, fitz.Rect, str]],
    section: str,
    source_version_id: str | None,
    reading_order: int,
    *,
    ocr_elements: list[DocumentElement] | None = None,
) -> tuple[list[ParsedImage], int]:
    items: list[ParsedImage] = []
    filtered = 0
    seen: set[str] = set()
    page_area = max(float(page.rect.width * page.rect.height), 1.0)
    image_infos = page.get_images(full=True)
    has_usable_text = bool(re.sub(r"\s+", "", page.get_text("text")))
    if not has_usable_text:
        # Scanned pages expose a single page-sized bitmap rather than separate
        # PDF image objects.  Keep that bitmap as a preview, and only derive a
        # searchable figure crop when OCR found a reliable caption and a
        # bounded visual region immediately above it.
        items.extend(_scan_page_figures(page, page_number, section, ocr_elements or [], source_version_id))
        if page_number > 12:
            return items, len(image_infos)
        # Rendered pages are useful as an explicit preview for a scan, but they
        # must never be added to the figure/image vector collection.
        try:
            pixmap = page.get_pixmap(matrix=fitz.Matrix(1.25, 1.25), alpha=False)
            payload = pixmap.tobytes("png")
            items.append(ParsedImage(
                element_id=f"p{page_number}-snapshot", payload=payload,
                filename=f"第{page_number}页.png", mime_type="image/png", page=page_number,
                bbox=(0.0, 0.0, float(page.rect.width), float(page.rect.height)),
                asset_type="page_snapshot", caption=f"扫描页预览 · 第 {page_number} 页", section_path=section,
            ))
        except Exception:
            return [], 1
        return items, len(image_infos)
    for image_index, image_info in enumerate(image_infos):
        try:
            xref = int(image_info[0])
            extracted = pdf.extract_image(xref)
            payload = bytes(extracted.get("image", b""))
            extension = str(extracted.get("ext") or "").lower()
            mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}.get(extension)
            rects = list(page.get_image_rects(xref))
            rect = rects[0] if rects else None
            if not payload or not mime or rect is None:
                filtered += 1
                continue
            digest = hashlib.sha256(payload).hexdigest()
            if digest in seen:
                filtered += 1
                continue
            seen.add(digest)
            width = int(extracted.get("width") or 0)
            height = int(extracted.get("height") or 0)
            coverage = float(rect.width * rect.height) / page_area
            caption = _nearest_caption(rect, captions)
            # Full-page image objects are scan/page backgrounds.  A teaching
            # figure must be a real sub-region with an explicit caption.
            if coverage >= 0.68 or width < 160 or height < 100 or width * height < 28_000 or caption is None:
                filtered += 1
                continue
            items.append(ParsedImage(
                element_id=f"p{page_number}-figure-{image_index}", payload=payload,
                filename=f"第{page_number}页{caption[2]}.{extension}", mime_type=mime,
                page=page_number, bbox=(float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1)),
                asset_type="figure", caption=caption[0][:900], section_path=section,
            ))
        except Exception:
            filtered += 1
    return items, filtered


def _scan_page_figures(
    page: fitz.Page,
    page_number: int,
    section: str,
    ocr_elements: list[DocumentElement],
    source_version_id: str | None,
) -> list[ParsedImage]:
    """Derive caption-bounded figure crops from a scanned page.

    A scan has no trustworthy embedded-image boundary.  The crop is therefore
    intentionally conservative: it needs an OCR caption and a visually
    bounded region above that caption, excludes the caption text itself, and
    is never allowed to become a full-page snapshot.  If Pillow is unavailable
    or the geometry is ambiguous, returning no figures is the truthful result.
    """

    captions = [item for item in ocr_elements if item.element_type == "caption" and item.bbox]
    if not captions:
        return []
    try:
        from io import BytesIO
        from PIL import Image, ImageStat

        scale = 1.5
        pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        rendered = Image.open(BytesIO(pixmap.tobytes("png"))).convert("RGB")
    except Exception:
        return []

    page_width = float(page.rect.width)
    page_height = float(page.rect.height)
    text_items = [
        item for item in ocr_elements
        if item.bbox and item.element_type != "caption" and len(item.text.strip()) >= 4
    ]
    figures: list[ParsedImage] = []
    for figure_index, caption in enumerate(captions):
        assert caption.bbox is not None
        _cx0, cy0, _cx1, _cy1 = caption.bbox
        previous = [
            item for item in text_items
            if item.bbox and item.bbox[3] <= cy0 - 8
        ]
        previous_bottom = max((float(item.bbox[3]) for item in previous if item.bbox), default=0.0)
        crop_y0 = previous_bottom + 8.0
        crop_y1 = cy0 - 8.0
        crop_height = crop_y1 - crop_y0
        # A figure group needs a meaningful visual band.  Tiny bands are
        # usually OCR labels, running text or a caption split across lines.
        if crop_height < 70.0 or crop_height > page_height * 0.62:
            continue
        # Use the content column rather than the complete page margin.  This
        # keeps a scan crop bounded even when a caption is near the edge.
        crop_x0 = max(0.0, min(page_width - 1.0, min(float(_cx0) - page_width * 0.28, page_width * 0.06)))
        crop_x1 = min(page_width, max(float(_cx1) + page_width * 0.28, page_width * 0.94))
        if crop_x1 - crop_x0 < page_width * 0.32:
            continue
        left = max(0, int(round(crop_x0 * scale)))
        top = max(0, int(round(crop_y0 * scale)))
        right = min(rendered.width, int(round(crop_x1 * scale)))
        bottom = min(rendered.height, int(round(crop_y1 * scale)))
        if right - left < 180 or bottom - top < 90:
            continue
        crop = rendered.crop((left, top, right, bottom))
        gray = crop.convert("L")
        mean = float(ImageStat.Stat(gray).mean[0])
        extrema = gray.getextrema()
        if mean > 249.0 or (extrema[1] - extrema[0] < 24):
            continue
        output = BytesIO()
        crop.save(output, format="PNG", optimize=True)
        label_match = FIGURE_CAPTION_RE.match(caption.text.strip())
        label = re.sub(r"\s+", "", label_match.group("label")) if label_match else f"图{figure_index + 1}"
        figures.append(ParsedImage(
            element_id=f"p{page_number}-scan-figure-{figure_index}",
            payload=output.getvalue(),
            filename=f"第{page_number}页{label}.png",
            mime_type="image/png",
            page=page_number,
            bbox=(crop_x0, crop_y0, crop_x1, crop_y1),
            asset_type="figure",
            caption=caption.text.strip()[:900],
            section_path=section,
            concepts=(),
        ))
    return figures[:8]


def _nearest_caption(rect: fitz.Rect, captions: list[tuple[str, fitz.Rect, str]]) -> tuple[str, fitz.Rect, str] | None:
    if not captions:
        return None
    center_x = (rect.x0 + rect.x1) / 2

    def distance(item: tuple[str, fitz.Rect, str]) -> float:
        _text, candidate, _label = item
        vertical = candidate.y0 - rect.y1
        horizontal = abs((candidate.x0 + candidate.x1) / 2 - center_x)
        if vertical >= -18:
            return max(vertical, 0) + horizontal * 0.18
        return 180 + math.hypot(horizontal, candidate.y0 - rect.y1)

    selected = min(captions, key=distance)
    return selected if distance(selected) <= 420 else None


def _parse_docx(source_path: Path, *, source_version_id: str | None) -> ParsedDocument:
    from docx import Document

    document = Document(source_path)
    stats = DocumentParseStats(page_count=1)
    elements: list[DocumentElement] = []
    images: list[ParsedImage] = []
    order = 0
    section = "导言"
    for paragraph in document.paragraphs:
        text = re.sub(r"\s+", " ", paragraph.text or "").strip()
        if not _indexable_text(text):
            continue
        style = str(getattr(paragraph.style, "name", "") or "").lower()
        element_type = "heading" if "heading" in style or text.startswith("#") else "caption" if FIGURE_CAPTION_RE.match(text) else "paragraph"
        if element_type == "heading":
            section = text.lstrip("# ").strip() or section
        elements.append(DocumentElement(
            element_id=f"p1-t{order}", element_type=element_type, page=1, bbox=None,
            reading_order=order, parent_element_id=None, section_path=section,
            text=text.lstrip("# ").strip(), source_version_id=source_version_id,
        ))
        order += 1
    for table_index, table in enumerate(document.tables):
        rows = []
        for row in table.rows:
            cells = [re.sub(r"\s+", " ", cell.text).strip() for cell in row.cells]
            cells = [cell for cell in cells if cell]
            if cells:
                rows.append(" | ".join(cells))
        if rows:
            stats.table_count += 1
            elements.append(DocumentElement(
                element_id=f"table-{table_index}", element_type="table", page=1, bbox=None,
                reading_order=order, parent_element_id=None, section_path=section,
                text="\n".join(rows), source_version_id=source_version_id,
            ))
            order += 1
    # python-docx exposes the relationship target for each embedded image.
    # Walk drawings in paragraph order so image/text provenance remains stable;
    # an image without alt text or a nearby Figure caption is intentionally not
    # promoted to a retrievable teaching figure.
    seen_relations: set[str] = set()
    paragraphs = list(document.paragraphs)
    for paragraph_index, paragraph in enumerate(paragraphs):
        for node in paragraph._p.iter():  # type: ignore[attr-defined]
            if not str(node.tag).endswith("}blip"):
                continue
            relation_id = next((str(key).split("}")[-1]) for key in node.attrib if str(key).endswith("}embed")), None
            if not relation_id or relation_id in seen_relations:
                continue
            relationship = document.part.rels.get(relation_id)
            if relationship is None or not str(getattr(relationship, "reltype", "")).endswith("/image"):
                continue
            seen_relations.add(relation_id)
            target = relationship.target_part
            mime = str(getattr(target, "content_type", "") or "")
            if mime not in {"image/png", "image/jpeg", "image/webp"}:
                stats.filtered_asset_count += 1
                continue
            alt_text = None
            for sibling in paragraph._p.iter():  # type: ignore[attr-defined]
                if str(sibling.tag).endswith("}docPr"):
                    alt_text = str(sibling.get("descr") or sibling.get("title") or "").strip() or None
                    if alt_text:
                        break
            nearby = next((
                re.sub(r"\s+", " ", later.text or "").strip()
                for later in paragraphs[paragraph_index + 1:paragraph_index + 4]
                if FIGURE_CAPTION_RE.match(re.sub(r"\s+", " ", later.text or "").strip())
            ), None)
            caption = alt_text or nearby
            if not caption:
                stats.filtered_asset_count += 1
                continue
            image_id = f"docx-image-{len(images)}"
            images.append(ParsedImage(
                element_id=image_id, payload=bytes(target.blob),
                filename=Path(str(getattr(target, "partname", "image.png"))).name,
                mime_type=mime, page=1, bbox=None, asset_type="figure",
                caption=caption[:900], section_path=section,
            ))
            stats.figure_count += 1
    stats.pages_with_text = 1 if elements else 0
    if not elements:
        raise ValueError("未能从 DOCX 中解析出可索引正文。")
    return ParsedDocument(source_path, "python-docx-structured", elements, images, stats, source_version_id)
