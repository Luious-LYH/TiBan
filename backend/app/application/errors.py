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


class RetrievalUnavailableError(ApplicationError):
    code = "retrieval_unavailable"


class PersistenceError(ApplicationError):
    code = "persistence_error"


def normalize_provider_error(message: str | None) -> ApplicationError:
    normalized = (message or "provider unavailable").lower()
    if "401" in normalized or "403" in normalized or "auth" in normalized:
        return ProviderAuthError("provider authentication failed")
    if "429" in normalized or "rate" in normalized:
        return ProviderRateLimitError("provider rate limited")
    if "timeout" in normalized or "timed out" in normalized or "504" in normalized:
        return ProviderTimeoutError("provider timed out")
    return ApplicationError("provider unavailable")
