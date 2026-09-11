from __future__ import annotations

import base64
import json
import struct

from fastapi.testclient import TestClient

from app.adapters.tutor_gateway import OpenAICompatibleTutorGateway
from app.main import app
from app.services.agent_runtime import AgentContext, AgentRunner, ToolRegistry
from app.services.image_asset_service import inspect_image
from app.services.llm_provider import LLMProvider, LLMResult
from app.services.mentor_agent_service import MentorGateway


def _png_bytes(width: int = 2, height: int = 2) -> bytes:
    """Small header-valid PNG fixture; the asset service validates dimensions."""

    return b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">II", width, height) + b"\x08\x02\x00\x00\x00"


def _data_url(payload: bytes, mime: str = "image/png") -> str:
    return f"data:{mime};base64,{base64.b64encode(payload).decode('ascii')}"


def test_image_header_policy_accepts_png_and_rejects_mismatch() -> None:
    payload = _png_bytes(640, 480)
    assert inspect_image(payload, "image/png") == ("image/png", 640, 480)

    try:
        inspect_image(payload, "image/jpeg")
    except ValueError as exc:
        assert "MIME" in str(exc)
    else:
        raise AssertionError("a declared MIME mismatch must be rejected")

    for unsafe in (b"not an image", b"\x89PNG\r\n\x1a\n"):
        try:
            inspect_image(unsafe, "image/png")
        except ValueError:
            pass
        else:
            raise AssertionError("invalid image bytes must be rejected")


def test_multimodal_import_review_publish_and_asset_lifecycle() -> None:
    """Exercise the public chain, not a direct QuestionModel shortcut."""

    with TestClient(app) as client:
        staged_response = client.post(
            "/api/v3/assets/question-images",
            json={"filename": "cases/endo.png", "data_url": _data_url(_png_bytes())},
        )
        assert staged_response.status_code == 200, staged_response.text
        staged = staged_response.json()
        assert staged["asset_id"].startswith("img_question_")
        assert "base64" not in json.dumps(staged)

        content = json.dumps([{
            "题干": "图像题导入后是否保留图片？",
            "题型": "单选",
            "选项": "保留|不保留",
            "答案": "A",
            "解析": "图片通过受控资产地址提供。",
            "图片": "cases/endo.png",
        }], ensure_ascii=False)
        refs = [{"asset_id": staged["asset_id"], "filename": "cases/endo.png"}]
        batch_response = client.post(
            "/api/v3/factory/import-batches",
            json={
                "format": "json",
                "content": content,
                "domain_id": "endoscopy",
                "source_name": "多模态导入回归",
                "file_name": "multimodal.json",
                "image_assets": refs,
            },
        )
        assert batch_response.status_code == 200, batch_response.text
        batch = batch_response.json()["item"]
        assert batch["total_count"] == 1
        assert batch["items"][0]["image_url"] == staged["url"]

        reviewed = client.post(f"/api/v3/factory/import-batches/{batch['batch_id']}/review", json={"status": "approved"})
        assert reviewed.status_code == 200, reviewed.text
        published = client.post(
            f"/api/v3/factory/import-batches/{batch['batch_id']}/publish",
            json={"mode": "create_bank", "bank_name": "多模态导入回归题库"},
        )
        assert published.status_code == 200, published.text
        bank_id = published.json()["item"]["bank_id"]

        questions = client.get(f"/api/v3/question-banks/{bank_id}/questions")
        assert questions.status_code == 200, questions.text
        assert questions.json()["items"][0]["image_url"] == staged["url"]

        # Removing the review record must not remove an asset still used by a
        # published bank; removing the bank then removes its image asset.
        deleted_batch = client.delete(f"/api/v3/factory/import-batches/{batch['batch_id']}")
        assert deleted_batch.status_code == 200, deleted_batch.text
        assert client.get(staged["url"]).status_code == 200
        deleted_bank = client.delete(f"/api/v3/question-banks/{bank_id}")
        assert deleted_bank.status_code == 200, deleted_bank.text
        assert client.get(staged["url"]).status_code == 404


def test_runner_blocks_visual_context_for_non_visual_gateway() -> None:
    class TextOnlyGateway:
        name = "text-only-test"
        supports_vision = False

        def select_tools(self, context: AgentContext, available_tools: set[str]) -> list[str]:
            return []

        def compose(self, context: AgentContext, observations: dict[str, object]) -> str:
            return "不应生成这段回答"

    events = list(AgentRunner(ToolRegistry(), TextOnlyGateway()).stream(AgentContext(
        question_id="q", learner_id="learner", user_message="请看图回答", phase="mentor", image_paths=["/controlled/image.png"],
    )))
    assert events[-1].event == "error"
    assert events[-1].data["code"] == "vision_not_supported"
    assert not any(event.event == "token" for event in events)


def test_provider_builds_an_image_content_block(monkeypatch) -> None:
    provider = LLMProvider()
    captured: dict[str, object] = {}
    monkeypatch.setattr(provider, "_image_data_url", lambda _path: "data:image/png;base64,AA==")
    monkeypatch.setattr(provider, "_vision_provider_attempts", lambda **_kwargs: [{
        "provider": "test", "base_url": "http://test.invalid/v1", "api_key": "runtime-only", "model": "vision-model",
    }])

    def fake_chat_once(**kwargs: object) -> LLMResult:
        captured.update(kwargs)
        return LLMResult(True, "已读取图片", "provider", "test", "vision-model", image_attached=True)

    monkeypatch.setattr(provider, "_chat_once", fake_chat_once)
    result = provider.chat(system_prompt="system", user_prompt="请观察图片", image_path="/controlled/image.png")

    assert result.ok is True
    assert captured["image_data"] == ["data:image/png;base64,AA=="]


def test_visual_provider_uses_glm_fallback_model(monkeypatch) -> None:
    provider = LLMProvider()
    captured: dict[str, object] = {}
    monkeypatch.setattr(provider, "_image_data_url", lambda _path: "data:image/png;base64,AA==")
    monkeypatch.setattr(provider, "_vision_provider_attempts", lambda **_kwargs: [{
        "provider": "bigmodel", "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "api_key": "runtime-only", "model": "GLM-4.6V-Flash",
    }])

    def fake_chat_once(**kwargs: object) -> LLMResult:
        captured.update(kwargs)
        return LLMResult(True, "已读取图片", "provider", "bigmodel", "GLM-4.6V-Flash", image_attached=True)

    monkeypatch.setattr(provider, "_chat_once", fake_chat_once)
    result = provider.chat(system_prompt="system", user_prompt="请观察图片", image_path="/controlled/image.png")

    assert result.ok is True
    assert captured["effective_model"] == "GLM-4.6V-Flash"


def test_mentor_gateway_reads_runtime_provider_and_vision_state(monkeypatch) -> None:
    status = {"configured": False, "vision_configured": False}
    monkeypatch.setattr("app.services.mentor_agent_service.llm_provider.status", lambda: status)

    gateway = MentorGateway()
    assert gateway.name == "local-learning-mentor"
    assert gateway.supports_vision is False

    status.update(configured=True, vision_configured=True)
    assert gateway.name == "openai-compatible-learning-mentor"
    assert gateway.supports_vision is True


def test_tutor_forwards_current_question_image_to_the_existing_gateway(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    def fake_chat(**kwargs: object) -> LLMResult:
        calls.append(kwargs)
        text = '{"tools":[]}' if len(calls) == 1 else "已根据题目图片整理学习提示。"
        return LLMResult(True, text, "provider", "test", "vision-model")

    monkeypatch.setattr("app.adapters.tutor_gateway.llm_provider.chat", fake_chat)
    runner = AgentRunner(
        ToolRegistry(),
        OpenAICompatibleTutorGateway(),
        default_context=lambda _context: {"domain_id": "endoscopy", "image_url": "/api/v3/assets/question-images/img_question_demo"},
    )
    events = list(runner.stream(AgentContext(
        question_id="q", learner_id="learner", user_message="请根据图片给我提示", phase="pre_submit",
    )))

    assert events[-1].event == "message_end"
    assert all(call["image_paths"] == ["/api/v3/assets/question-images/img_question_demo"] for call in calls)


def test_mentor_routes_explicit_figure_reference_to_multimodal_knowledge() -> None:
    """A request that names supplied material must not fall back to general advice."""

    class EvidenceGateway:
        name = "evidence-test"
        supports_vision = True

        def select_tools(self, _context: AgentContext, available_tools: set[str]) -> list[str]:
            return sorted(available_tools)

        def compose(self, _context: AgentContext, observations: dict[str, object]) -> str:
            assert "search_knowledge" in observations
            return "已结合资料图片和出处整理观察重点。"

    registry = ToolRegistry()
    registry.register("search_knowledge", {"mentor"}, lambda _context: [{
        "document_name": "消化道内镜图像记录建议",
        "page": "5",
        "snippet": "Fig. 3. Suggested systematic imaging in colonoscopy.",
        "image_urls": ["/api/v3/knowledge/media/kmedia_demo"],
    }])
    events = list(AgentRunner(registry, EvidenceGateway()).stream(AgentContext(
        question_id="",
        learner_id="learner",
        user_message="请结合资料中的结肠镜系统图像说明观察重点和资料出处。",
        phase="mentor",
        metadata={"agent_profile": "mentor"},
    )))

    assert any(event.event == "tool_start" and event.data["tool_name"] == "search_knowledge" for event in events)
    assert any(event.event == "source" and event.data["document_name"] == "消化道内镜图像记录建议" for event in events)
    assert events[-1].event == "message_end"


def test_mentor_scopes_explicit_endoscopy_material_to_endoscopy_domain(monkeypatch) -> None:
    from app.services.mentor_agent_service import _search_knowledge
    from app.services.rag_service import rag_service

    captured: dict[str, object] = {}
    monkeypatch.setenv("TUTOR_RETRIEVAL_ENABLED", "true")
    monkeypatch.setattr(rag_service, "retrieve_multimodal", lambda _query, **kwargs: captured.update(kwargs) or {
        "citations": [], "image_results": [],
    })

    _search_knowledge(AgentContext(
        question_id="", learner_id="learner", phase="mentor",
        user_message="请结合资料中的结肠镜系统图像说明观察重点。",
    ))

    assert captured["domain_id"] == "endoscopy"
    assert captured["namespaces"] == ["system", "user"]


def test_mentor_image_message_keeps_only_an_opaque_asset_reference(monkeypatch) -> None:
    class TextOnlyGateway:
        name = "text-only-test"
        supports_vision = False

        def select_tools(self, context: AgentContext, available_tools: set[str]) -> list[str]:
            return []

        def compose(self, context: AgentContext, observations: dict[str, object]) -> str:
            return "不应生成这段回答"

    with TestClient(app) as client:
        # App startup refreshes the shared runtime gateway from the project
        # defaults. Apply this isolated text-only gateway after startup so the
        # test remains independent of the local .env provider chain.
        monkeypatch.setattr(
            "app.services.mentor_agent_service.mentor_runner",
            AgentRunner(ToolRegistry(), TextOnlyGateway()),
        )
        asset = client.post(
            "/api/v3/assets/chat-images",
            json={"filename": "学习图片.png", "data_url": _data_url(_png_bytes())},
        ).json()
        conversation = client.post("/api/v3/mentor/conversations", params={"learner_id": "v35-image-mentor"}).json()
        conversation_id = conversation["item"]["id"]
        response = client.post(
            f"/api/v3/mentor/conversations/{conversation_id}/stream",
            json={"learner_id": "v35-image-mentor", "message": "请看这张图", "image_asset_id": asset["asset_id"]},
        )
        assert response.status_code == 200
        assert "vision_not_supported" in response.text
        detail = client.get(
            f"/api/v3/mentor/conversations/{conversation_id}",
            params={"learner_id": "v35-image-mentor"},
        ).json()

    user_message = detail["item"]["messages"][0]
    assert user_message["image_attached"] is True
    assert user_message["image_asset_id"] == asset["asset_id"]
    assert "base64" not in json.dumps(detail, ensure_ascii=False)
