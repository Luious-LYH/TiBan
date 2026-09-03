from __future__ import annotations

import json
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.services.mentor_agent_service import mentor_agent_service


router = APIRouter(prefix="/api/v3/mentor", tags=["v32-mentor-agent"])


class MentorMessagePublic(BaseModel):
    id: str
    role: Literal["user", "assistant"]
    content: str
    activity: list[dict[str, object]] = Field(default_factory=list)
    sources: list[dict[str, object]] = Field(default_factory=list)
    created_at: str


class MentorConversationPublic(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    messages: list[MentorMessagePublic] = Field(default_factory=list)


class MentorConversationListResponse(BaseModel):
    items: list[MentorConversationPublic]
    api_source: str = "backend"


class MentorConversationResponse(BaseModel):
    item: MentorConversationPublic
    api_source: str = "backend"


class MentorConversationDeleteResponse(BaseModel):
    conversation_id: str
    deleted: bool
    api_source: str = "backend"


class MentorMessageRequest(BaseModel):
    learner_id: str = "demo_learner"
    message: str = Field(min_length=1, max_length=2000)


@router.get("/conversations", response_model=MentorConversationListResponse)
def list_conversations(learner_id: str = "demo_learner") -> MentorConversationListResponse:
    return MentorConversationListResponse(items=[MentorConversationPublic.model_validate(item) for item in mentor_agent_service.list_conversations(learner_id)])


@router.post("/conversations", response_model=MentorConversationResponse)
def create_conversation(learner_id: str = "demo_learner") -> MentorConversationResponse:
    return MentorConversationResponse(item=MentorConversationPublic.model_validate(mentor_agent_service.create_conversation(learner_id)))


@router.get("/conversations/{conversation_id}", response_model=MentorConversationResponse)
def conversation_detail(conversation_id: str, learner_id: str = "demo_learner") -> MentorConversationResponse:
    try:
        return MentorConversationResponse(item=MentorConversationPublic.model_validate(mentor_agent_service.detail(conversation_id, learner_id)))
    except KeyError as exc:
        raise HTTPException(404, "带教对话不存在。") from exc


@router.delete("/conversations/{conversation_id}", response_model=MentorConversationDeleteResponse)
def delete_conversation(conversation_id: str, learner_id: str = "demo_learner") -> MentorConversationDeleteResponse:
    try:
        return MentorConversationDeleteResponse(**mentor_agent_service.delete_conversation(conversation_id, learner_id))
    except KeyError as exc:
        raise HTTPException(404, "带教对话不存在。") from exc


@router.post("/conversations/{conversation_id}/stream")
def stream_message(conversation_id: str, request: MentorMessageRequest) -> StreamingResponse:
    def event_stream():
        try:
            for event in mentor_agent_service.stream_message(
                conversation_id=conversation_id, learner_id=request.learner_id, message=request.message
            ):
                yield f"event: {event.event}\ndata: {json.dumps(event.data, ensure_ascii=False)}\n\n"
        except KeyError:
            yield "event: error\ndata: {\"code\":\"not_found\",\"message\":\"带教对话不存在。\"}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
