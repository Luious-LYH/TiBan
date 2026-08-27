from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.config import SAFETY_NOTICE
from app.schemas import TutorHintRequestV3, TutorHintResponseV3
from app.services.stage1_service import stage1_service


router = APIRouter(prefix="/api/v3/tutor", tags=["stage1-tutor"])


@router.post("/hint", response_model=TutorHintResponseV3)
def rule_hint(request: TutorHintRequestV3) -> TutorHintResponseV3:
    try:
        question = stage1_service.public_question(request.question_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Question not found.") from exc
    body_part = str(question.get("body_part", "当前部位"))
    return TutorHintResponseV3(
        message=f"规则提示：先观察{body_part}的部位、形态和可支持事实，再排除超出单帧证据的结论。",
        mode="rule",
        sources=[str(question.get("citation_note", "平台教学样例"))],
        safety_notice=SAFETY_NOTICE,
    )
