from __future__ import annotations

from typing import Any

from app.schemas import PracticeSubmitRequest, PracticeSubmitResponse
from app.services.stage1_service import Stage1Service


class Stage1PracticeWorkflowAdapter:
    """Adapter around the mature Stage 5 transactional practice service."""

    def __init__(self, service: Stage1Service) -> None:
        self._service = service

    def submit(self, request: PracticeSubmitRequest) -> PracticeSubmitResponse:
        return self._service.submit(request)

    def create_session(self, learner_id: str, bank_id: str, mode: str, question_count: int, shuffle_seed: int | None) -> dict[str, Any]:
        return self._service.create_session(learner_id, bank_id, mode, question_count, shuffle_seed)
