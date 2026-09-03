from __future__ import annotations

import json
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.services.coach_agent_service import coach_agent_service


router = APIRouter(prefix="/api/v3/coach", tags=["v31-coach-agent"])


class CoachMessagePublic(BaseModel):
    id: str
    role: Literal["user", "assistant"]
    content: str
    activity: list[dict[str, object]] = Field(default_factory=list)
    sources: list[dict[str, object]] = Field(default_factory=list)
    created_at: str


class CoachConversationPublic(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    messages: list[CoachMessagePublic] = Field(default_factory=list)


class CoachConversationListResponse(BaseModel):
    items: list[CoachConversationPublic]
    api_source: str = "backend"


class CoachConversationResponse(BaseModel):
    item: CoachConversationPublic
    api_source: str = "backend"


class CoachMessageRequest(BaseModel):
    learner_id: str = "demo_learner"
    message: str = Field(min_length=1, max_length=2000)


@router.get("/conversations", response_model=CoachConversationListResponse)
def list_conversations(learner_id: str = "demo_learner") -> CoachConversationListResponse:
    return CoachConversationListResponse(items=[CoachConversationPublic.model_validate(item) for item in coach_agent_service.list_conversations(learner_id)])


@router.post("/conversations", response_model=CoachConversationResponse)
def create_conversation(learner_id: str = "demo_learner") -> CoachConversationResponse:
    return CoachConversationResponse(item=CoachConversationPublic.model_validate(coach_agent_service.create_conversation(learner_id)))


@router.get("/conversations/{conversation_id}", response_model=CoachConversationResponse)
def conversation_detail(conversation_id: str, learner_id: str = "demo_learner") -> CoachConversationResponse:
    try:
        return CoachConversationResponse(item=CoachConversationPublic.model_validate(coach_agent_service.detail(conversation_id, learner_id)))
    except KeyError as exc:
        raise HTTPException(404, "带教对话不存在。") from exc


@router.post("/conversations/{conversation_id}/stream")
def stream_message(conversation_id: str, request: CoachMessageRequest) -> StreamingResponse:
    def event_stream():
        try:
            for event in coach_agent_service.stream_message(
                conversation_id=conversation_id, learner_id=request.learner_id, message=request.message
            ):
                yield f"event: {event.event}\ndata: {json.dumps(event.data, ensure_ascii=False)}\n\n"
        except KeyError:
            yield "event: error\ndata: {\"code\":\"not_found\",\"message\":\"带教对话不存在。\"}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
