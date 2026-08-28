from __future__ import annotations

import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.services.agent_runtime import AgentContext, tutor_runner


router = APIRouter(prefix='/api/v3/tutor', tags=['stage2-tutor'])


class TutorStreamRequest(BaseModel):
    question_id: str
    learner_id: str = 'demo_learner'
    message: str = Field(min_length=1, max_length=2000)
    attempt_id: str | None = None
    conversation: list[dict[str, str]] = Field(default_factory=list, max_length=12)


@router.post('/stream')
def tutor_stream(request: TutorStreamRequest) -> StreamingResponse:
    phase = 'post_submit' if request.attempt_id else 'pre_submit'

    def event_stream():
        context = AgentContext(
            question_id=request.question_id,
            learner_id=request.learner_id,
            user_message=request.message,
            phase=phase,
            attempt_id=request.attempt_id,
            metadata={"conversation": request.conversation[-12:]},
        )
        for event in tutor_runner.stream(context):
            yield f'event: {event.event}\ndata: {json.dumps(event.data, ensure_ascii=False)}\n\n'

    return StreamingResponse(event_stream(), media_type='text/event-stream', headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})
