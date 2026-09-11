"""Small internal error taxonomy at application boundaries."""

from __future__ import annotations


class ApplicationError(RuntimeError):
    code = "application_error"


class ProviderAuthError(ApplicationError):
    code = "provider_auth"


class ProviderRateLimitError(ApplicationError):
    code = "provider_rate_limited"


class ProviderTimeoutError(ApplicationError):
    code = "provider_timeout"


class ProviderUnavailableError(ApplicationError):
    code = "provider_unavailable"


class VisionNotSupportedError(ApplicationError):
    code = "vision_not_supported"


class ImageInputError(ApplicationError):
    code = "image_input_unavailable"


class RetrievalUnavailableError(ApplicationError):
    code = "retrieval_unavailable"


class PersistenceError(ApplicationError):
    code = "persistence_error"


def normalize_provider_error(message: str | None) -> ApplicationError:
    normalized = (message or "provider unavailable").lower()
    if any(marker in normalized for marker in ("vision", "multimodal", "image input", "image_url", "visual", "does not support image")):
        return VisionNotSupportedError("当前模型或服务不支持图片输入，请更换支持视觉的模型后重试。")
    if any(marker in normalized for marker in ("image_not_available", "image_input_unavailable", "image_unavailable", "image file")):
        return ImageInputError("题目或附件图片暂时无法读取，请重新打开题目或重新附加图片。")
    if "401" in normalized or "403" in normalized or "auth" in normalized:
        return ProviderAuthError("模型服务鉴权失败，请检查 API Key 和连接地址后重试。")
    if "429" in normalized or "rate" in normalized:
        return ProviderRateLimitError("模型服务当前请求过多，请稍后重试。")
    if "timeout" in normalized or "timed out" in normalized or "504" in normalized:
        return ProviderTimeoutError("模型服务响应超时，请检查网络或稍后重试。")
    if normalized in {"provider unavailable", "provider_not_configured", "vision_provider_not_configured", "empty_response", "provider_error"}:
        if normalized == "vision_provider_not_configured":
            return VisionNotSupportedError("当前实例尚未配置支持图片输入的模型，请先配置视觉模型后重试。")
        return ProviderUnavailableError("当前模型服务暂时不可用，请检查设置中的 API 配置后重试。")
    return ProviderUnavailableError("当前模型服务暂时不可用，请检查设置中的 API 配置后重试。")
