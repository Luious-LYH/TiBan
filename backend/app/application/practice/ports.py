from __future__ import annotations

from typing import Any, Protocol

from app.schemas import PracticeSubmitRequest, PracticeSubmitResponse


class PracticeWorkflowPort(Protocol):
    """The application-facing contract for the established learning workflow."""

    def submit(self, request: PracticeSubmitRequest) -> PracticeSubmitResponse: ...

    def create_session(self, learner_id: str, bank_id: str, mode: str, question_count: int, shuffle_seed: int | None, question_scope: str = "all") -> dict[str, Any]: ...
