from __future__ import annotations

import io
import json
import struct
import sys
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import fitz
from PIL import Image

from app.db.database import SessionLocal
from app.db.models import (
    DocumentVersionModel,
    KnowledgeChunkModel,
    KnowledgeEntityModel,
    KnowledgeMediaAssetModel,
    KnowledgeRelationModel,
    SourceDocumentModel,
    VectorIndexStateModel,
)
from app.services.agent_runtime import AgentContext
from app.services.knowledge_multimodal_service import KNOWLEDGE_MEDIA_ROOT, knowledge_multimodal_service
from app.services.knowledge_service import knowledge_service
from app.services.rag_service import IMAGE_COLLECTION, IMAGE_INDEX_KEY, Citation, rag_service


def _png_bytes() -> bytes:
    image = Image.new("RGB", (240, 160), (42, 116, 108))
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _pdf_with_image(path: Path) -> None:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "内镜图像与息肉识别指南：图像资料需要结合活检和病理进行教学复核。")
    page.insert_image(fitz.Rect(72, 100, 240, 220), stream=_png_bytes())
    page.insert_text((72, 242), "Fig. 1. Endoscopic image documentation for polyp observation and biopsy review.")
    document.save(path)
    document.close()


def _pdf_with_uncaptioned_image(path: Path) -> None:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "课程页面装饰，不应被识别为可检索的教学图像。")
    page.insert_image(fitz.Rect(72, 100, 240, 220), stream=_png_bytes())
    document.save(path)
    document.close()


def _seed_source(document_id: str, version_id: str) -> None:
    with SessionLocal() as session:
        session.add(SourceDocumentModel(
            document_id=document_id, domain_id="endoscopy", name="图像资料回归", media_type="application/pdf",
            content_hash="test", status="ready", source_id=document_id, business_usage="knowledge_base",
            license_gate_status="allow", ai_ingestion_allowed=True, namespace="user", source_scope="user",
            file_name="multimodal.pdf", size_bytes=1, enabled=True,
        ))
        session.add(DocumentVersionModel(
            version_id=version_id, document_id=document_id, version_label="test", source_path="pending",
            content_hash="test", parser="test", status="indexed",
        ))
        session.add(KnowledgeChunkModel(
            chunk_id=f"chunk-{document_id}", document_id=document_id, version_id=version_id,
            parent_section="图像资料", page=1, ordinal=0,
            content="内镜图像与息肉识别指南：图像资料需要结合活检和病理进行教学复核。",
            content_hash="test", token_count=30, namespace="user",
        ))
        session.commit()


def _cleanup(document_id: str) -> None:
    try:
        knowledge_multimodal_service.purge_document(document_id)
    finally:
        with SessionLocal() as session:
            session.query(KnowledgeChunkModel).filter_by(document_id=document_id).delete(synchronize_session=False)
            session.query(DocumentVersionModel).filter_by(document_id=document_id).delete(synchronize_session=False)
            session.query(SourceDocumentModel).filter_by(document_id=document_id).delete(synchronize_session=False)
            session.commit()


def test_reindex_prefers_original_source_over_parsed_projection(tmp_path: Path) -> None:
    original = tmp_path / "guide.pdf"
    parsed = tmp_path / "guide.parsed.md"
    original.write_bytes(b"pdf")
    parsed.write_text("normalized text", encoding="utf-8")
    original_version = DocumentVersionModel(
        version_id="original", document_id="doc", source_path=str(original),
        content_hash="original", parser="pdf", status="indexed",
    )
    parsed_version = DocumentVersionModel(
        version_id="parsed", document_id="doc", source_path=str(parsed),
        content_hash="parsed", parser="markdown", status="indexed",
    )

    selected = knowledge_service._select_reindex_source_version([
        parsed_version, original_version,
    ])

    assert selected is original_version


def test_bundled_multimodal_guide_registers_on_a_clean_database(tmp_path: Path, monkeypatch) -> None:
    """The first-run bundled guide must reach the normal indexing path."""

    document_id = "v35-default-guide-test"
    source_uri = "https://example.test/v35-default-guide-test"
    source_path = tmp_path / "bundled-guide.pdf"
    _pdf_with_image(source_path)
    runtime_dir = tmp_path / "runtime-knowledge"
    captured: dict[str, object] = {}

    monkeypatch.setattr("app.services.knowledge_service.DEFAULT_MULTIMODAL_KNOWLEDGE_SOURCE_ID", document_id)
    monkeypatch.setattr("app.services.knowledge_service.DEFAULT_MULTIMODAL_KNOWLEDGE_SAMPLE_PATH", source_path)
    monkeypatch.setattr("app.services.knowledge_service.DEFAULT_MULTIMODAL_KNOWLEDGE_URI", source_uri)
    monkeypatch.setattr("app.services.knowledge_service.KNOWLEDGE_UPLOAD_DIR", runtime_dir)
    monkeypatch.setattr(
        knowledge_service,
        "_index",
        lambda **kwargs: captured.update(kwargs) or {"id": kwargs["document_id"]},
    )
    try:
        result = knowledge_service.ensure_default_multimodal_guide()
        assert result == {"id": document_id}
        assert captured["document_id"] == document_id
        assert Path(str(captured["source_path"])).is_file()
        with SessionLocal() as session:
            source = session.get(SourceDocumentModel, document_id)
            assert source is not None
            assert source.name == "消化道内镜图像记录建议"
            assert source.source_uri == source_uri
    finally:
        with SessionLocal() as session:
            session.query(SourceDocumentModel).filter_by(document_id=document_id).delete(synchronize_session=False)
            session.commit()


def test_pdf_media_is_extracted_with_opaque_metadata_and_graph_evidence(tmp_path: Path) -> None:
    document_id = "v35-knowledge-pdf-test"
    version_id = f"{document_id}-v1"
    source_path = tmp_path / "teaching-guide.pdf"
    _pdf_with_image(source_path)
    _seed_source(document_id, version_id)
    try:
        result = knowledge_multimodal_service.ingest_document(
            document_id=document_id, version_id=version_id, source_path=source_path, media_type="application/pdf"
        )
        assert result["image_count"] == 1
        assert result["graph_node_count"] >= 3
        assert result["graph_edge_count"] >= 1
        with SessionLocal() as session:
            asset = session.query(KnowledgeMediaAssetModel).filter_by(document_id=document_id).one()
            chunk = session.query(KnowledgeChunkModel).filter_by(document_id=document_id).one()
            assert asset.storage_path.startswith(f"{document_id}/")
            assert not Path(asset.storage_path).is_absolute()
            assert asset.asset_id in chunk.media_asset_ids
            assert asset.alt_text and asset.alt_text.startswith("Fig. 1.")
            assert asset.size_bytes < 1_000_000
            assert "base64" not in str(asset.__dict__).lower()
            assert (KNOWLEDGE_MEDIA_ROOT / asset.storage_path).is_file()
    finally:
        _cleanup(document_id)


def test_pdf_ignores_large_uncaptioned_layout_images(tmp_path: Path) -> None:
    source_path = tmp_path / "uncaptioned.pdf"
    _pdf_with_uncaptioned_image(source_path)

    images, errors = knowledge_multimodal_service._extract_pdf(source_path)

    assert images == []
    assert errors == []


def test_pdf_supports_common_chinese_figure_caption(tmp_path: Path) -> None:
    page = SimpleNamespace(get_text=lambda _kind: [(72, 242, 300, 280, "图 1：结肠镜观察中的回盲瓣与阑尾开口。\n", 0, 0)])

    captions = knowledge_multimodal_service._pdf_figure_captions(page)

    assert len(captions) == 1
    assert captions[0].text == "图 1：结肠镜观察中的回盲瓣与阑尾开口。"
    assert captions[0].label == "图1"


def test_caption_graph_expands_text_evidence_to_its_figure(tmp_path: Path) -> None:
    document_id = "v35-caption-graph-test"
    version_id = f"{document_id}-v1"
    source_path = tmp_path / "captioned.pdf"
    _pdf_with_image(source_path)
    _seed_source(document_id, version_id)
    try:
        knowledge_multimodal_service.ingest_document(
            document_id=document_id, version_id=version_id, source_path=source_path, media_type="application/pdf"
        )
        images, paths = rag_service._graph_related_images([
            Citation(
                chunk_id=f"chunk-{document_id}", document_name="图像资料回归", page=1,
                section="图像资料", snippet="内镜图像与息肉识别指南", score=0.9,
                document_id=document_id, namespace="user",
            )
        ], domain_id="endoscopy", limit=3)

        assert len(images) == 1
        assert images[0]["caption"].startswith("Fig. 1.")
        assert "caption_concept_graph" in images[0]["retrieval_channels"]
        assert paths[0]["relation"] == "depicted_in_figure"

        excluded, excluded_paths = rag_service._graph_related_images(
            [
                Citation(
                    chunk_id=f"chunk-{document_id}", document_name="图像资料回归", page=1,
                    section="图像资料", snippet="内镜图像与息肉识别指南", score=0.9,
                    document_id=document_id, namespace="user",
                )
            ],
            query="内镜图像",
            domain_id="endoscopy",
            namespaces=["qbank_explanations"],
            limit=3,
        )
        assert excluded == []
        assert excluded_paths == []
    finally:
        _cleanup(document_id)


def test_governed_graph_entities_exclude_pdf_headers_and_ocr_fragments() -> None:
    """A learner-facing graph must not use PDF furniture as an entity."""

    labels = knowledge_multimodal_service._entity_names(
        "Review Article — Image Documentation in Gastrointestinal Endoscopy. "
        "Photo documentation is an important quality control measure."
    )

    assert "图像记录" in labels
    assert "质量控制" in labels
    assert "article" not in labels
    assert "review" not in labels
    assert "port" not in labels


def test_figure_caption_eval_fixture_is_image_free_and_complete() -> None:
    """The reproducible eval set contains expectations, never source pixels."""

    fixture = Path(__file__).resolve().parents[1] / "app" / "data" / "multimodal_knowledge_eval_v35.json"
    payload = json.loads(fixture.read_text(encoding="utf-8"))

    assert payload["source_id"] == "source-endoscopy-image-documentation-v35"
    assert len(payload["cases"]) == 4
    assert all("expected_page" in case and "expected_caption_contains" in case for case in payload["cases"])
    assert "base64" not in fixture.read_text(encoding="utf-8").lower()


def test_clip_provider_prefers_its_local_cache_without_network_probe(monkeypatch, tmp_path: Path) -> None:
    from app.services.embedding_provider import ClipImageEmbeddingProvider

    captured: dict[str, object] = {}

    class FakeSentenceTransformer:
        def __init__(self, _model_id: str, **kwargs: object) -> None:
            captured.update(kwargs)

    monkeypatch.setitem(sys.modules, "sentence_transformers", SimpleNamespace(SentenceTransformer=FakeSentenceTransformer))
    provider = ClipImageEmbeddingProvider("clip", "clip-test", tmp_path / "clip")

    assert isinstance(provider.model, FakeSentenceTransformer)
    assert captured["local_files_only"] is True


def test_clip_query_is_reduced_to_controlled_concepts() -> None:
    from app.services.rag_service import _clip_query_text

    query = "请结合资料中的结肠镜系统图像说明学习时应重点观察哪些解剖标志，并说明资料出处。"
    reduced = _clip_query_text(query)

    assert reduced == "结肠镜 图像"
    assert len(reduced) < len(query)


def test_image_fusion_uses_only_explainable_evidence_bonus() -> None:
    """A graph relation can lift an image without being presented as confidence."""

    citation = Citation(
        chunk_id="captioned-chunk", document_name="图像资料", page=5, section="第 5 页",
        snippet="系统图像记录", score=0.8, document_id="guide", namespace="system",
    )
    ranked = rag_service._fuse_image_results([
        {
            "asset_id": "clip-only", "document_id": "guide", "page": 4,
            "clip_score": 0.61, "retrieval_channels": ["clip"], "evidence_links": [],
        },
        {
            "asset_id": "captioned", "document_id": "guide", "page": 5,
            "clip_score": 0.55, "graph_match_count": 2,
            "retrieval_channels": ["clip", "caption_concept_graph"], "evidence_links": ["资料关联：结肠镜 → 图示"],
        },
    ], citations=[citation], limit=2)

    assert ranked[0]["asset_id"] == "captioned"
    assert ranked[0]["evidence_association_bonus"] == 0.27
    assert "与相关文字证据同页" in ranked[0]["evidence_links"]
    assert "confidence" not in ranked[0]


def test_image_index_uses_fake_clip_provider_and_keeps_failure_truthful(monkeypatch) -> None:
    document_id = "v35-knowledge-index-test"
    version_id = f"{document_id}-v1"
    image_path = KNOWLEDGE_MEDIA_ROOT / document_id / "manual" / "asset.png"
    image_path.parent.mkdir(parents=True, exist_ok=True)
    image_path.write_bytes(_png_bytes())
    _seed_source(document_id, version_id)
    with SessionLocal() as session:
        session.add(KnowledgeMediaAssetModel(
            asset_id="kmedia_fake_asset", document_id=document_id, version_id=version_id,
            storage_path=f"{document_id}/manual/asset.png", original_filename="asset.png", sha256="f" * 64,
            mime_type="image/png", width=8, height=6, size_bytes=image_path.stat().st_size,
            page=1, ordinal=0, status="ready",
        ))
        session.commit()

    class FakeImageProvider:
        provider_id = "clip"
        model_id = "clip-ViT-B-32"

        def embed_images(self, paths: list[Path]) -> list[list[float]]:
            assert paths == [image_path.resolve()]
            return [[0.1, 0.2, 0.3]]

        def embed_text(self, text: str) -> list[float]:
            return [0.1, 0.2, 0.3]

        def dimension(self) -> int:
            return 3

    class FakeQdrant:
        def __init__(self) -> None:
            self.points = []
            self.created = False

        def collection_exists(self, _name: str) -> bool:
            return self.created

        def delete_collection(self, _name: str) -> None:
            self.created = False

        def create_collection(self, _name: str, **_kwargs: object) -> None:
            self.created = True

        def upsert(self, _name: str, *, points: list[object], wait: bool) -> None:
            self.points.extend(points)

        def delete(self, *_args: object, **_kwargs: object) -> None:
            return None

    fake_qdrant = FakeQdrant()
    monkeypatch.setattr("app.services.rag_service.configured_image_embedding_provider", lambda: FakeImageProvider())
    monkeypatch.setattr(type(rag_service), "qdrant", property(lambda _self: fake_qdrant))
    try:
        indexed = rag_service.rebuild_knowledge_image_index(document_ids=[document_id])
        assert indexed == ["kmedia_fake_asset"]
        assert fake_qdrant.created is True
        assert fake_qdrant.points
        with SessionLocal() as session:
            state = session.get(VectorIndexStateModel, IMAGE_INDEX_KEY)
            source = session.get(SourceDocumentModel, document_id)
            assert state is not None and state.status == "ready"
            assert source is not None and source.image_index_status == "ready"

        monkeypatch.setattr("app.services.rag_service.configured_image_embedding_provider", lambda: (_ for _ in ()).throw(RuntimeError("clip_unavailable")))
        try:
            rag_service.rebuild_knowledge_image_index(document_ids=[document_id])
        except RuntimeError:
            pass
        else:
            raise AssertionError("image encoder failure should be surfaced")
        with SessionLocal() as session:
            state = session.get(VectorIndexStateModel, IMAGE_INDEX_KEY)
            source = session.get(SourceDocumentModel, document_id)
            assert state is not None and state.status == "failed"
            assert source is not None and source.image_index_status == "failed"
    finally:
        _cleanup(document_id)
        with SessionLocal() as session:
            session.query(VectorIndexStateModel).filter_by(index_key=IMAGE_INDEX_KEY).delete(synchronize_session=False)
            session.commit()
        import shutil
        shutil.rmtree(KNOWLEDGE_MEDIA_ROOT / document_id, ignore_errors=True)


def test_tutor_keeps_image_only_knowledge_results(monkeypatch) -> None:
    """An image hit is evidence even when the text retriever has no hit."""

    from app.adapters.tutor_dependencies import _retrieve_knowledge
    from app.services.rag_service import rag_service

    monkeypatch.setenv("TUTOR_RETRIEVAL_ENABLED", "true")
    monkeypatch.setattr(
        "app.adapters.tutor_dependencies._question_context",
        lambda _context: {"domain_id": "endoscopy", "stem": "图像观察"},
    )
    monkeypatch.setattr(
        "app.adapters.tutor_dependencies.get_domain",
        lambda _domain_id: type("Manifest", (), {"domain_id": "endoscopy"})(),
    )
    monkeypatch.setattr(rag_service, "retrieve_multimodal", lambda *_args, **_kwargs: {
        "citations": [],
        "image_results": [{
            "asset_id": "knowledge-image-only",
            "url": "/api/v3/knowledge/media/knowledge-image-only",
            "document_name": "图像指南",
            "page": 2,
        }],
    })

    result = _retrieve_knowledge(AgentContext(
        question_id="question-image-only",
        learner_id="learner-image-only",
        user_message="请结合图像资料解释",
        phase="mentor",
    ))

    assert result == [{
        "document_name": "图像指南",
        "page": "2",
        "section": "资料图片",
        "snippet": "检索到相关资料图片。",
        "source_uri": "",
        "namespace": "knowledge_media",
        "image_urls": ["/api/v3/knowledge/media/knowledge-image-only"],
        "media_asset_ids": ["knowledge-image-only"],
        "concepts": [],
        "evidence_links": [],
    }]


def test_graph_expansion_returns_a_governed_one_hop_neighbour() -> None:
    """Shared-entity expansion returns a new chunk, not the seed itself."""

    token = uuid4().hex[:12]
    document_id = f"v35-graph-{token}"
    version_id = f"{document_id}-v1"
    seed_id, neighbour_id, unrelated_id = [f"{document_id}-{suffix}" for suffix in ("seed", "neighbour", "unrelated")]
    entity_ids = [f"{document_id}-entity-{suffix}" for suffix in ("shared", "seed", "neighbour", "other")]
    try:
        with SessionLocal() as session:
            session.add(SourceDocumentModel(
                document_id=document_id,
                domain_id="endoscopy",
                name="GraphRAG 回归资料",
                media_type="text/markdown",
                content_hash=token,
                status="ready",
                source_id=document_id,
                business_usage="knowledge_base",
                license_gate_status="allow",
                ai_ingestion_allowed=True,
                namespace="user",
                source_scope="user",
                file_name="graph.md",
                enabled=True,
            ))
            session.add(DocumentVersionModel(
                version_id=version_id,
                document_id=document_id,
                version_label="v1",
                source_path="test://graph",
                content_hash=token,
                parser="test",
                status="indexed",
            ))
            session.add_all([
                KnowledgeChunkModel(
                    chunk_id=seed_id,
                    document_id=document_id,
                    version_id=version_id,
                    parent_section="种子证据",
                    page=1,
                    ordinal=0,
                    content="共享概念与种子概念的关系。",
                    content_hash=token,
                    token_count=10,
                    namespace="user",
                ),
                KnowledgeChunkModel(
                    chunk_id=neighbour_id,
                    document_id=document_id,
                    version_id=version_id,
                    parent_section="相邻证据",
                    page=2,
                    ordinal=1,
                    content="共享概念与相邻概念的关系。",
                    content_hash=token,
                    token_count=10,
                    namespace="user",
                ),
                KnowledgeChunkModel(
                    chunk_id=unrelated_id,
                    document_id=document_id,
                    version_id=version_id,
                    parent_section="无关证据",
                    page=3,
                    ordinal=2,
                    content="另一组概念的关系。",
                    content_hash=token,
                    token_count=10,
                    namespace="user",
                ),
            ])
            session.add_all([
                KnowledgeEntityModel(entity_id=entity_ids[0], document_id=document_id, canonical_name="共享概念", entity_type="concept"),
                KnowledgeEntityModel(entity_id=entity_ids[1], document_id=document_id, canonical_name="种子概念", entity_type="concept"),
                KnowledgeEntityModel(entity_id=entity_ids[2], document_id=document_id, canonical_name="相邻概念", entity_type="concept"),
                KnowledgeEntityModel(entity_id=entity_ids[3], document_id=document_id, canonical_name="其他概念", entity_type="concept"),
            ])
            session.add_all([
                KnowledgeRelationModel(
                    relation_id=f"{document_id}-relation-seed",
                    document_id=document_id,
                    source_entity_id=entity_ids[0],
                    target_entity_id=entity_ids[1],
                    relation_type="co_occurs_in_evidence",
                    chunk_id=seed_id,
                    confidence=0.8,
                ),
                KnowledgeRelationModel(
                    relation_id=f"{document_id}-relation-neighbour",
                    document_id=document_id,
                    source_entity_id=entity_ids[0],
                    target_entity_id=entity_ids[2],
                    relation_type="co_occurs_in_evidence",
                    chunk_id=neighbour_id,
                    confidence=0.7,
                ),
                KnowledgeRelationModel(
                    relation_id=f"{document_id}-relation-unrelated",
                    document_id=document_id,
                    source_entity_id=entity_ids[2],
                    target_entity_id=entity_ids[3],
                    relation_type="co_occurs_in_evidence",
                    chunk_id=unrelated_id,
                    confidence=0.99,
                ),
            ])
            session.commit()

        extra, paths = rag_service._expand_graph([
            Citation(
                chunk_id=seed_id,
                document_name="GraphRAG 回归资料",
                page=1,
                section="种子证据",
                snippet="共享概念与种子概念的关系。",
                score=0.9,
                document_id=document_id,
                namespace="user",
            )
        ], domain_id="endoscopy", limit=3)

        assert [item.chunk_id for item in extra] == [neighbour_id]
        assert paths[0]["seed_chunk_id"] == seed_id
        assert paths[0]["chunk_id"] == neighbour_id
        assert paths[0]["from"] == "共享概念"
    finally:
        _cleanup(document_id)
