from __future__ import annotations

from typing import Any

from app.application.practice.ports import PracticeWorkflowPort
from app.schemas import PracticeSubmitRequest, PracticeSubmitResponse


class PracticeUseCases:
    """Transport-free boundary for the stable deterministic learning workflow."""

    def __init__(self, workflow: PracticeWorkflowPort) -> None:
        self._workflow = workflow

    def submit_answer(self, request: PracticeSubmitRequest) -> PracticeSubmitResponse:
        # The adapter retains the atomic grade → Attempt → mastery → FSRS →
        # learning-memory transaction. No model/network operation is admitted.
        return self._workflow.submit(request)

    def create_practice_session(
        self, learner_id: str, bank_id: str, mode: str, question_count: int, shuffle_seed: int | None
    ) -> dict[str, Any]:
        return self._workflow.create_session(learner_id, bank_id, mode, question_count, shuffle_seed)
