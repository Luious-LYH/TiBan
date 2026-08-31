from __future__ import annotations

from collections import Counter

from fastapi import APIRouter, HTTPException, Query

from app.composition import practice_use_cases
from app.domains import PLATFORM_NOTICE, get_domain
from app.db.seed import TYPE_LABEL
from app.schemas import (
    PracticeQuestionDetailResponse,
    PracticeQuestionListResponse,
    PracticeSessionCreateRequest,
    PracticeSessionDetailPublic,
    PracticeSessionPublic,
    PracticeSubmitRequest,
    PracticeSubmitResponse,
)
from app.services.stage1_service import stage1_service


canonical_router = APIRouter(prefix="/api/v3", tags=["stage1-practice"])
legacy_router = APIRouter(prefix="/api", tags=["stage1-practice-compat"])


def _type_counts(items: list[dict[str, object]]) -> dict[str, int]:
    counts = Counter(str(item["question_type"]) for item in items)
    labels = {TYPE_LABEL.get(code, "问答评分"): count for code, count in counts.items()}
    return {**dict(counts), **labels}


@canonical_router.get("/practice/questions", response_model=PracticeQuestionListResponse)
def list_questions_v3(
    bank_id: str | None = Query(default=None),
    domain_id: str | None = Query(default=None),
    question_type: str | None = Query(default=None),
    body_part: str | None = Query(default=None),
    subject: str | None = Query(default=None),
    topic: str | None = Query(default=None),
    search: str | None = Query(default=None),
    session_id: str | None = Query(default=None),
    limit: int = Query(default=18, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, object]:
    try:
        items = stage1_service.list_public_questions(
            bank_id=bank_id,
            domain_id=domain_id,
            question_type=question_type,
            body_part=body_part,
            subject=subject,
            topic=topic,
            search=search,
            session_id=session_id,
            limit=limit,
            offset=offset,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Practice session not found.") from exc
    learner_notice = get_domain(domain_id).learner_notice if domain_id else (
        get_domain(str(items[0]["domain_id"])).learner_notice if items else PLATFORM_NOTICE
    )
    return {
        "items": items,
        "total": len(items),
        "available_type_counts": _type_counts(items),
        "bank_id": bank_id,
        "safety_notice": learner_notice,
    }


@canonical_router.get("/practice/questions/{question_id}", response_model=PracticeQuestionDetailResponse)
def get_question_v3(question_id: str) -> dict[str, object]:
    try:
        item = stage1_service.public_question(question_id)
        return {"item": item, "safety_notice": get_domain(str(item["domain_id"])).learner_notice}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Question not found.") from exc


@canonical_router.post("/practice/sessions", response_model=PracticeSessionPublic)
def create_session_v3(request: PracticeSessionCreateRequest) -> dict[str, object]:
    try:
        return practice_use_cases.create_practice_session(
            request.learner_id,
            request.bank_id,
            request.mode,
            request.question_count,
            request.shuffle_seed,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Question bank not found.") from exc


@canonical_router.get("/practice/sessions/{session_id}", response_model=PracticeSessionDetailPublic)
def get_session_v3(
    session_id: str,
    state: str | None = Query(default=None, pattern="^(unanswered|correct|incorrect)$"),
) -> dict[str, object]:
    try:
        return stage1_service.session_detail(session_id, state)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Practice session not found.") from exc


@canonical_router.post("/practice/submit", response_model=PracticeSubmitResponse)
def submit_v3(request: PracticeSubmitRequest) -> PracticeSubmitResponse:
    try:
        return practice_use_cases.submit_answer(request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Question or bank not found.") from exc


@legacy_router.get("/practice/questions")
def list_questions_compat(
    bank_id: str | None = Query(default=None),
    question_class: str | None = Query(default=None),
    difficulty: str | None = Query(default=None),
    body_part: str | None = Query(default=None),
    question_type: str | None = Query(default=None),
    limit: int = Query(default=18, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, object]:
    items = stage1_service.list_public_questions(
        bank_id=bank_id,
        domain_id=None,
        body_part=body_part,
        question_type=question_type,
        limit=limit,
        offset=offset,
        legacy=True,
    )
    # This endpoint is retained for the pre-v3 teaching-seed client.  Its
    # historical contract is a compact text-only catalog; the canonical v3
    # endpoint remains the source of truth for the full, multimodal learner
    # inventory (including imported Kvasir image questions).
    items = [item for item in items if not item.get("image_url")]
    if question_class:
        items = [item for item in items if item.get("question_class") == question_class]
    if difficulty:
        items = [item for item in items if item.get("difficulty") == difficulty]
    # The compatibility endpoint is also the small public teaching-seed
    # contract used by older clients.  A large imported QBank can legitimately
    # occupy the first page with one question type, so add one representative
    # of each supported type when it is absent.  This does not alter the
    # canonical session builder or its ordering; it only keeps the old catalog
    # preview representative and type counts truthful for that preview.
    present_types = {item.get("question_type_code") for item in items}
    for code in ("single_choice", "multiple_choice", "true_false", "short_answer"):
        if code in present_types:
            continue
        label = TYPE_LABEL[code]
        supplemental = stage1_service.list_public_questions(
            bank_id=bank_id,
            body_part=body_part,
            question_type=label,
            limit=1,
            offset=0,
            legacy=True,
        )
        if supplemental:
            candidate = supplemental[0]
            if not question_class or candidate.get("question_class") == question_class:
                if not difficulty or candidate.get("difficulty") == difficulty:
                    items.append(candidate)
                    present_types.add(code)
    return {
        "items": items,
        "total": len(items),
        "available_type_counts": _type_counts([
            {"question_type": item.get("question_type_code", "short_answer")} for item in items
        ]),
        "bank_id": bank_id,
        "safety_notice": PLATFORM_NOTICE,
        "api_source": "backend",
    }


@legacy_router.get("/practice/questions/{question_id}")
def get_question_compat(question_id: str) -> dict[str, object]:
    try:
        item = stage1_service.public_question(question_id, legacy=True)
        return {"item": item, "safety_notice": get_domain(str(item["domain_id"])).learner_notice}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Question not found.") from exc


@legacy_router.post("/practice/sessions")
def create_session_compat(request: PracticeSessionCreateRequest) -> dict[str, object]:
    try:
        return practice_use_cases.create_practice_session(
            request.learner_id,
            request.bank_id,
            request.mode,
            request.question_count,
            request.shuffle_seed,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Question bank not found.") from exc


@legacy_router.post("/practice/submit")
def submit_compat(request: PracticeSubmitRequest) -> dict[str, object]:
    try:
        return practice_use_cases.submit_answer(request).model_dump(mode="json")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Question or bank not found.") from exc
