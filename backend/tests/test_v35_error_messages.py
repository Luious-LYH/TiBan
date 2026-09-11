from __future__ import annotations

from app.application.errors import normalize_provider_error


def test_provider_failures_are_user_facing_and_localized() -> None:
    assert "当前模型服务暂时不可用" in str(normalize_provider_error("provider unavailable"))
    assert "鉴权失败" in str(normalize_provider_error("http_401"))
    assert "响应超时" in str(normalize_provider_error("TimeoutError"))


def test_visual_provider_failure_is_not_hidden_as_a_generic_error() -> None:
    error = normalize_provider_error("the model does not support image input")
    assert error.code == "vision_not_supported"
    assert "不支持图片输入" in str(error)
