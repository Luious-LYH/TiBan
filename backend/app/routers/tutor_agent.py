from __future__ import annotations

import json
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.services.agent_runtime import AgentContext, tutor_runner
from app.services.tutor_session_service import tutor_session_service


router = APIRouter(prefix='/api/v3/tutor', tags=['stage2-tutor'])


class TutorStreamRequest(BaseModel):
    practice_session_id: str = Field(min_length=1, max_length=150)
    tutor_thread_id: str = Field(min_length=1, max_length=150)
    question_id: str
    learner_id: str = 'demo_learner'
    message: str = Field(min_length=1, max_length=2000)
    attempt_id: str | None = None
    mode: Literal['study', 'exam', 'review'] = 'study'


@router.post('/stream')
def tutor_stream(request: TutorStreamRequest) -> StreamingResponse:
    phase = 'post_submit' if request.attempt_id else 'pre_submit'
    try:
        conversation = tutor_session_service.start_turn(
            practice_session_id=request.practice_session_id,
            tutor_thread_id=request.tutor_thread_id,
            learner_id=request.learner_id,
            question_id=request.question_id,
            content=request.message,
        )
    except KeyError as exc:
        raise HTTPException(409, "当前智能辅导上下文已失效，请重新进入本次练习。") from exc

    def event_stream():
        context = AgentContext(
            question_id=request.question_id,
            learner_id=request.learner_id,
            user_message=request.message,
            phase=phase,
            mode=request.mode,
            attempt_id=request.attempt_id,
            practice_session_id=request.practice_session_id,
            tutor_thread_id=request.tutor_thread_id,
            metadata={"conversation": conversation, "agent_profile": "tutor"},
        )
        answer: list[str] = []
        activities: list[dict[str, object]] = []
        sources: list[dict[str, object]] = []
        run_id: str | None = None
        for event in tutor_runner.stream(context):
            if event.event == "message_start":
                run_id = str(event.data.get("run_id") or "") or None
            elif event.event == "token":
                answer.append(str(event.data.get("text") or ""))
            elif event.event == "activity":
                activities.append(dict(event.data))
            elif event.event == "source":
                sources.append(dict(event.data))
            yield f'event: {event.event}\ndata: {json.dumps(event.data, ensure_ascii=False)}\n\n'
        tutor_session_service.finish_turn(
            practice_session_id=request.practice_session_id,
            tutor_thread_id=request.tutor_thread_id,
            learner_id=request.learner_id,
            content="".join(answer).strip(),
            run_id=run_id,
            activity=activities,
            sources=sources,
            user_message=request.message,
        )

    return StreamingResponse(event_stream(), media_type='text/event-stream', headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})
