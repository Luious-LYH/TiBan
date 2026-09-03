import base64
import hashlib
import json
import re
import struct
from queue import Queue
from threading import Thread
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import inspect, text
from qdrant_client import QdrantClient
import redis

from app.core.config import APP_NAME, APP_VERSION, QDRANT_URL, REDIS_URL, SAFETY_NOTICE, UPLOAD_DIR
from app.db.database import engine
from app.schemas import (
    ExamSessionRequest,
    FavoriteRequest,
    ImageUploadRequest,
    ImageUploadResponse,
    ModelAdmissionTestRequest,
    ModelSelectRequest,
    PatientCardApproveRequest,
    PatientCardRequest,
    ProviderPreflightRequest,
    ProviderRequestPreviewRequest,
    ProviderSelfTestRequest,
    ReportDraftRequest,
    ReportJudgeRequest,
    SubmissionRequest,
)
from app.services.audit_service import audit_service, now_iso
from app.services.dashboard_service import dashboard_service
from app.services.data_store import reset_runtime_data
from app.services.grading_service import grading_service
from app.services.memory_service import memory_service
from app.services.model_service import model_service
from app.services.portfolio_agent_runtime import portfolio_agent_runtime
from app.services.portfolio_eval_service import portfolio_eval_service
from app.services.portfolio_study_service import portfolio_study_service
from app.services.question_bank_import_service import question_bank_import_service
from app.services.question_service import question_service
from app.services.report_service import report_service
from app.services.v3_facade_service import v3_facade_service

router = APIRouter(prefix="/api")


@router.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "service": APP_NAME,
        "version": APP_VERSION,
        "capabilities": [
            "v3_session",
            "model_evaluation",
            "custom_model_evaluation",
            "practice_facade",
            "report_facade",
            "delivery_report",
            "report_upload_receipt",
            "profile_growth",
            "runtime_state_isolation",
            "observable_agent_runtime",
            "offline_agent_evaluation",
            "sparse_evidence_retrieval",
            "bounded_tool_recovery",
            "session_checkpoint_replay",
            "ndjson_agent_event_stream",
            "adaptive_study_state",
            "wrong_case_and_spaced_review",
            "qbank_first_study_workspace",
            "curated_text_question_bank",
            "multiform_practice_grading",
            "pre_submit_tutor_sidecar",
            "qbank_import_validation",
        ],
    }


@router.get("/ready")
def readiness() -> JSONResponse:
    """Report local service dependencies without probing external LLMs.

    ``/health`` is intentionally a cheap liveness endpoint. Compose and an
    operator can use this endpoint when they need to know whether the
    database, Redis queue, Qdrant index service, and schema are usable. Every
    network probe has a short timeout so an offline derived service cannot
    hold the request open for the normal client timeout.
    """

    checks: dict[str, object] = {}
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        checks["database"] = {"status": "ok"}
    except Exception as exc:
        checks["database"] = {"status": "error", "error": type(exc).__name__}

    required_tables = {"question_banks", "questions", "attempts", "practice_sessions", "source_documents", "knowledge_chunks"}
    try:
        tables = set(inspect(engine).get_table_names())
        missing = sorted(required_tables - tables)
        checks["schema"] = {"status": "ok" if not missing else "error", "missing": missing}
    except Exception as exc:
        checks["schema"] = {"status": "error", "error": type(exc).__name__}

    try:
        client = redis.Redis.from_url(REDIS_URL, socket_connect_timeout=0.35, socket_timeout=0.35)
        client.ping()
        checks["redis"] = {"status": "ok"}
    except Exception as exc:
        checks["redis"] = {"status": "error", "error": type(exc).__name__}

    try:
        qdrant = QdrantClient(url=QDRANT_URL, timeout=0.8)
        qdrant.get_collections()
        checks["qdrant"] = {"status": "ok"}
    except Exception as exc:
        checks["qdrant"] = {"status": "error", "error": type(exc).__name__}

    ready = all(isinstance(value, dict) and value.get("status") == "ok" for value in checks.values())
    payload = {"status": "ready" if ready else "not_ready", "service": APP_NAME, "version": APP_VERSION, "checks": checks}
    return JSONResponse(payload, status_code=200 if ready else 503)


@router.get("/provider/status")
def provider_status() -> dict[str, object]:
    return v3_facade_service.public_json_payload(model_service.provider_status())


@router.get("/provider/diagnostics")
def provider_diagnostics() -> dict[str, object]:
    return v3_facade_service.public_json_payload(model_service.provider_diagnostics())


@router.post("/provider/preflight")
def provider_preflight(request: ProviderPreflightRequest) -> dict[str, object]:
    return v3_facade_service.public_json_payload(model_service.provider_preflight(request).model_dump())


@router.post("/provider/request-preview")
def provider_request_preview(request: ProviderRequestPreviewRequest) -> dict[str, object]:
    return v3_facade_service.public_json_payload(model_service.provider_request_preview(request).model_dump())


@router.post("/provider/self-test")
def provider_self_test(request: ProviderSelfTestRequest) -> dict[str, object]:
    return v3_facade_service.public_json_payload(model_service.provider_self_test(request).model_dump())


@router.get("/dashboard")
def dashboard() -> dict[str, object]:
    return v3_facade_service.public_json_payload(dashboard_service.get_dashboard())


@router.get("/platform/readiness")
def platform_readiness() -> dict[str, object]:
    return v3_facade_service.public_json_payload(dashboard_service.get_readiness())


@router.get("/platform/delivery-report")
def platform_delivery_report() -> dict[str, object]:
    return v3_facade_service._sanitize_value(dashboard_service.get_delivery_report())


@router.post("/demo/reset")
def demo_reset() -> dict[str, object]:
    restored = reset_runtime_data()
    return {
        "status": "reset",
        "restored": restored,
        "runtime_isolated": True,
        "message": "演示状态已恢复，版本库中的种子数据未被修改。",
        "safety_notice": SAFETY_NOTICE,
    }


@router.get("/portfolio/cases")
def portfolio_cases() -> dict[str, object]:
    items = portfolio_agent_runtime.list_cases()
    return {
        "items": items,
        "total": len(items),
        "source": "versioned_portfolio_case_pack",
        "safety_notice": SAFETY_NOTICE,
    }


@router.get("/portfolio/study")
def portfolio_study(learner_id: str = "demo_learner") -> dict[str, object]:
    """Return the case-bank state, today's task and Agent recommendation."""
    try:
        return portfolio_study_service.snapshot(portfolio_agent_runtime.list_cases(), learner_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/question-banks")
def question_banks() -> dict[str, object]:
    return v3_facade_service.public_json_payload(question_bank_import_service.banks())


@router.get("/question-banks/import/templates")
def question_bank_import_templates() -> dict[str, object]:
    return v3_facade_service.public_json_payload(question_bank_import_service.templates())


@router.post("/question-banks/import/validate")
def question_bank_import_validate(payload: dict[str, object]) -> dict[str, object]:
    return v3_facade_service.public_json_payload(question_bank_import_service.validate(payload))


@router.post("/portfolio/study/favorites/{case_id}")
def portfolio_study_favorite(case_id: str, payload: dict[str, object]) -> dict[str, object]:
    """Idempotently add or remove a portfolio case from the learner's favorites."""
    favorited = payload.get("favorited")
    if not isinstance(favorited, bool):
        raise HTTPException(status_code=400, detail="favorited must be a boolean.")
    try:
        return portfolio_study_service.set_favorite(
            portfolio_agent_runtime.list_cases(),
            case_id,
            favorited,
            str(payload.get("learner_id") or "demo_learner"),
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/portfolio/study/favorite")
def portfolio_study_favorite_payload(payload: dict[str, object]) -> dict[str, object]:
    """Payload-form alias convenient for clients that do not encode path params."""
    case_id = str(payload.get("case_id") or "").strip()
    if not case_id:
        raise HTTPException(status_code=400, detail="case_id is required.")
    return portfolio_study_favorite(case_id, payload)


@router.post("/agent/runs")
def portfolio_agent_run(payload: dict[str, object]) -> dict[str, object]:
    case_id = str(payload.get("case_id") or "").strip()
    learner_answer = str(payload.get("learner_answer") or "").strip()
    if not case_id or not learner_answer:
        raise HTTPException(status_code=400, detail="case_id and learner_answer are required.")
    try:
        return portfolio_agent_runtime.run(
            case_id=case_id,
            learner_answer=learner_answer,
            learner_id=str(payload.get("learner_id") or "demo_learner"),
            failure_injection=payload.get("failure_injection") if isinstance(payload.get("failure_injection"), dict) else None,
            context_budget_tokens=int(payload.get("context_budget_tokens") or 800),
            commit_memory=payload.get("commit_memory") is True,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/agent/runs/{run_id}/replay")
def portfolio_agent_replay(run_id: str) -> dict[str, object]:
    try:
        return portfolio_agent_runtime.replay(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/agent/retrieve")
def portfolio_agent_retrieve(payload: dict[str, object]) -> dict[str, object]:
    query = str(payload.get("query") or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="query is required.")
    raw_filters = payload.get("metadata_filters")
    filters = {str(key): str(value) for key, value in raw_filters.items()} if isinstance(raw_filters, dict) else None
    try:
        return portfolio_agent_runtime.retrieve_evidence(query, top_k=int(payload.get("top_k") or 3), metadata_filters=filters)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/agent/runs/stream")
def portfolio_agent_run_stream(payload: dict[str, object]) -> StreamingResponse:
    """Run the real workflow in a worker and stream completed stages as NDJSON."""
    case_id = str(payload.get("case_id") or "").strip()
    learner_answer = str(payload.get("learner_answer") or "").strip()
    if not case_id or not learner_answer:
        raise HTTPException(status_code=400, detail="case_id and learner_answer are required.")
    try:
        portfolio_agent_runtime.get_case(case_id)
        budget = int(payload.get("context_budget_tokens") or 800)
        failure_injection = payload.get("failure_injection") if isinstance(payload.get("failure_injection"), dict) else None
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    def stream():
        events: Queue = Queue()
        sentinel = object()

        def worker() -> None:
            try:
                run = portfolio_agent_runtime.run(
                    case_id=case_id,
                    learner_answer=learner_answer,
                    learner_id=str(payload.get("learner_id") or "demo_learner"),
                    failure_injection=failure_injection,
                    context_budget_tokens=budget,
                    event_sink=events.put,
                    commit_memory=payload.get("commit_memory") is True,
                )
                events.put({"event": "final", "run": run})
            except Exception as exc:
                events.put({"event": "error", "error_code": type(exc).__name__, "message": "Agent run failed."})
            finally:
                events.put(sentinel)

        Thread(target=worker, name="portfolio-agent-stream", daemon=True).start()
        while True:
            event = events.get()
            if event is sentinel:
                break
            yield json.dumps(event, ensure_ascii=False) + "\n"

    return StreamingResponse(
        stream(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Content-Type-Options": "nosniff"},
    )


@router.post("/evals/run")
def portfolio_eval_run() -> dict[str, object]:
    return portfolio_eval_service.run()


@router.get("/evals/latest")
def portfolio_eval_latest() -> dict[str, object]:
    # The suite is intentionally small and deterministic; re-running ensures the
    # displayed artifact always matches the checked-out implementation.
    return portfolio_eval_service.run()


@router.get("/session")
def v3_session() -> dict[str, object]:
    return v3_facade_service.session()


@router.get("/practice/state")
def practice_state() -> dict[str, object]:
    return v3_facade_service.practice_state()


@router.get("/practice/questions")
def practice_questions(
    question_class: str | None = None,
    difficulty: str | None = None,
    body_part: str | None = None,
    question_type: str | None = None,
    only_wrong: bool = False,
    only_favorites: bool = False,
    limit: int = 18,
    shuffle_seed: int | None = None,
) -> dict[str, object]:
    return v3_facade_service.practice_questions(
        question_class=question_class,
        difficulty=difficulty,
        body_part=body_part,
        question_type=question_type,
        only_wrong=only_wrong,
        only_favorites=only_favorites,
        limit=limit,
        shuffle_seed=shuffle_seed,
    )


@router.get("/practice/questions/{question_id}")
def practice_question(question_id: str, learner_id: str = "demo_learner") -> dict[str, object]:
    try:
        return v3_facade_service.practice_question(question_id, learner_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/practice/submit")
def practice_submit(request: SubmissionRequest) -> dict[str, object]:
    try:
        return v3_facade_service.practice_submit(request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/practice/session")
def practice_session(request: ExamSessionRequest) -> dict[str, object]:
    try:
        return v3_facade_service.practice_session(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/questions")
def list_questions(
    question_class: str | None = None,
    difficulty: str | None = None,
    false_premise: bool | None = Query(default=None),
    body_part: str | None = None,
    task: str | None = None,
    question_type: str | None = None,
    source_dataset: str | None = None,
    only_favorites: bool = False,
    only_wrong: bool = False,
) -> dict[str, object]:
    items = question_service.list_questions(
        question_class=question_class,
        difficulty=difficulty,
        false_premise=false_premise,
        body_part=body_part,
        task=task,
        question_type=question_type,
        source_dataset=source_dataset,
        only_favorites=only_favorites,
        only_wrong=only_wrong,
    )
    return v3_facade_service.public_json_payload({"items": [v3_facade_service._question_payload(item.model_dump()) for item in items], "total": len(items)})


@router.get("/questions/{question_id}")
def get_question(question_id: str, learner_id: str = "demo_learner") -> dict[str, object]:
    try:
        question = question_service.get_question(question_id, learner_id)
        return v3_facade_service.public_json_payload({"item": v3_facade_service._question_payload(question.model_dump())})
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/submit")
def submit_answer(request: SubmissionRequest) -> dict[str, object]:
    try:
        return v3_facade_service.public_json_payload(grading_service.grade(request).model_dump())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/learner/profile")
def learner_profile() -> dict[str, object]:
    return v3_facade_service.public_json_payload(v3_facade_service._profile_payload(memory_service.get_profile().model_dump()))


@router.get("/learner/recommendations")
def learner_recommendations() -> dict[str, object]:
    return v3_facade_service.public_json_payload({"items": memory_service.get_recommendations(), "safety_notice": SAFETY_NOTICE})


@router.get("/learner/mentor-agent")
def learner_mentor_agent() -> dict[str, object]:
    return v3_facade_service.public_json_payload(memory_service.mentor_agent_advice())


@router.get("/learner/training-state")
def learner_training_state() -> dict[str, object]:
    state = memory_service.training_state()
    state["safety_notice"] = SAFETY_NOTICE
    return v3_facade_service.public_json_payload(v3_facade_service._practice_state_payload(state))


@router.post("/learner/exam-session")
def learner_exam_session(request: ExamSessionRequest) -> dict[str, object]:
    if not request.attempts:
        raise HTTPException(status_code=400, detail="Exam session requires at least one attempt.")
    response = memory_service.record_exam_session(request)
    audit_service.log(
        "exam_session",
        user_id=request.learner_id,
        entity_id=response.id,
        summary=response.memory_summary,
        risk_level="medium" if response.wrong_questions else "low",
    )
    return v3_facade_service.public_json_payload(response.model_dump())


@router.post("/learner/favorite")
def favorite_question(request: FavoriteRequest) -> dict[str, object]:
    profile = memory_service.set_favorite(request.question_id, request.favorited)
    audit_service.log(
        "favorite_update",
        user_id=request.learner_id,
        entity_id=request.question_id,
        summary="收藏题目" if request.favorited else "取消收藏题目",
        risk_level="low",
    )
    return v3_facade_service.public_json_payload({"profile": v3_facade_service._profile_payload(profile.model_dump()), "safety_notice": SAFETY_NOTICE})


@router.post("/report-draft")
def report_draft(request: ReportDraftRequest) -> dict[str, object]:
    if not request.image_name:
        raise HTTPException(status_code=400, detail="请先上传内镜图片，再生成报告草稿。")
    return v3_facade_service.report_generate(request)


@router.post("/report/generate")
def report_generate(request: ReportDraftRequest) -> dict[str, object]:
    if not request.image_name:
        raise HTTPException(status_code=400, detail="请先上传内镜图片，再生成报告草稿。")
    return v3_facade_service.report_generate(request)


@router.post("/report/image-upload")
def upload_report_image(request: ImageUploadRequest) -> dict[str, object]:
    match = re.match(r"^data:(image/(?:png|jpeg|jpg|webp));base64,(.+)$", request.data_url, re.DOTALL)
    if not match:
        raise HTTPException(status_code=400, detail="Only image data URLs are supported.")
    mime, encoded = match.groups()
    try:
        payload = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid base64 image payload.") from exc
    if not payload or len(payload) > 2_500_000:
        raise HTTPException(status_code=400, detail="Image must be between 1 byte and 2.5 MB.")
    width, height = _image_dimensions(payload, mime)
    if width is None or height is None:
        raise HTTPException(status_code=400, detail="Image header does not match the declared MIME type or dimensions are unsupported.")
    suffix = {"image/png": ".png", "image/jpeg": ".jpg", "image/jpg": ".jpg", "image/webp": ".webp"}[mime]
    safe_stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", request.filename.rsplit(".", 1)[0])[:40] or "endoscopy_upload"
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    output_name = f"{uuid4().hex[:12]}_{safe_stem}{suffix}"
    output_path = UPLOAD_DIR / output_name
    sha256_prefix = hashlib.sha256(payload).hexdigest()[:16]
    response = ImageUploadResponse(
        image_name=f"uploads/{output_name}",
        original_filename=request.filename,
        bytes=len(payload),
        mime_type=mime,
        width=width,
        height=height,
        sha256_prefix=sha256_prefix,
        source_type="uploaded_image",
        provider_input_allowed=True,
        audit_logged=False,
        audit_log_id=None,
        doctor_review_required=True,
        safety_notice=SAFETY_NOTICE,
        created_at=now_iso(),
    )
    try:
        output_path.write_bytes(payload)
        audit = audit_service.log(
            "image_upload",
            user_id=request.learner_id,
            entity_id=response.image_name,
            summary=(
                "上传内镜教学图片至后端受控目录；"
                f"尺寸 {width}x{height}；"
                "未包含真实身份字段。"
            ),
            risk_level="medium",
            metadata={
                "image_name": response.image_name,
                "mime_type": mime,
                "bytes": len(payload),
                "width": width,
                "height": height,
                "sha256_prefix": response.sha256_prefix,
                "provider_input_allowed": True,
            },
        )
    except Exception as exc:
        output_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="Failed to persist image upload receipt.") from exc
    return v3_facade_service.public_json_payload(response.model_copy(update={"audit_logged": True, "audit_log_id": audit.id}).model_dump())


@router.post("/report/image")
def report_image(request: ImageUploadRequest) -> dict[str, object]:
    return upload_report_image(request)


def _image_dimensions(payload: bytes, mime: str) -> tuple[int | None, int | None]:
    if mime == "image/png" and payload.startswith(b"\x89PNG\r\n\x1a\n") and len(payload) >= 24 and payload[12:16] == b"IHDR":
        return struct.unpack(">II", payload[16:24])
    if mime in {"image/jpeg", "image/jpg"} and payload.startswith(b"\xff\xd8"):
        return _jpeg_dimensions(payload)
    if mime == "image/webp":
        return _webp_dimensions(payload)
    return None, None


def _jpeg_dimensions(payload: bytes) -> tuple[int | None, int | None]:
    index = 2
    while index + 9 < len(payload):
        if payload[index] != 0xFF:
            index += 1
            continue
        while index < len(payload) and payload[index] == 0xFF:
            index += 1
        if index >= len(payload):
            return None, None
        marker = payload[index]
        index += 1
        if marker in {0xD8, 0xD9, 0x01} or 0xD0 <= marker <= 0xD7:
            continue
        if index + 2 > len(payload):
            return None, None
        segment_length = int.from_bytes(payload[index:index + 2], "big")
        if segment_length < 2 or index + segment_length > len(payload):
            return None, None
        if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
            if segment_length >= 7:
                height = int.from_bytes(payload[index + 3:index + 5], "big")
                width = int.from_bytes(payload[index + 5:index + 7], "big")
                return width, height
            return None, None
        index += segment_length
    return None, None


def _webp_dimensions(payload: bytes) -> tuple[int | None, int | None]:
    if len(payload) < 20 or not payload.startswith(b"RIFF") or payload[8:12] != b"WEBP":
        return None, None
    index = 12
    while index + 8 <= len(payload):
        chunk = payload[index:index + 4]
        chunk_size = int.from_bytes(payload[index + 4:index + 8], "little")
        data_start = index + 8
        data_end = data_start + chunk_size
        if data_end > len(payload):
            return None, None
        chunk_data = payload[data_start:data_end]
        if chunk == b"VP8X" and len(chunk_data) >= 10:
            width = int.from_bytes(chunk_data[4:7] + b"\x00", "little") + 1
            height = int.from_bytes(chunk_data[7:10] + b"\x00", "little") + 1
            return width, height
        if chunk == b"VP8L" and len(chunk_data) >= 5 and chunk_data[0] == 0x2F:
            packed = int.from_bytes(chunk_data[1:5], "little")
            width = (packed & 0x3FFF) + 1
            height = ((packed >> 14) & 0x3FFF) + 1
            return width, height
        if chunk == b"VP8 " and len(chunk_data) >= 10 and chunk_data[3:6] == b"\x9d\x01\x2a":
            width = int.from_bytes(chunk_data[6:8], "little") & 0x3FFF
            height = int.from_bytes(chunk_data[8:10], "little") & 0x3FFF
            return width, height
        index = data_end + (chunk_size % 2)
    return None, None


@router.post("/report/judge")
def report_judge(request: ReportJudgeRequest) -> dict[str, object]:
    return v3_facade_service.public_json_payload(v3_facade_service._report_judge_payload(report_service.judge_report_revision(request).model_dump()))


@router.post("/report/revise")
def report_revise(payload: dict[str, object]) -> dict[str, object]:
    return v3_facade_service.report_revise(payload)


@router.get("/knowledge/report")
def report_knowledge() -> dict[str, object]:
    return v3_facade_service.public_json_payload({"item": report_service.report_knowledge_base(), "safety_notice": SAFETY_NOTICE})


@router.get("/knowledge/cards")
def card_knowledge() -> dict[str, object]:
    return v3_facade_service.public_json_payload({"item": report_service.card_template_knowledge_base(), "safety_notice": SAFETY_NOTICE})


@router.get("/knowledge/real-samples")
def real_samples() -> dict[str, object]:
    items = question_service.list_questions()
    public_items = [item for item in items if item.source_dataset in {"Kvasir-VQA-x1", "Kvasir-VQA", "EndoBench"}]
    return v3_facade_service.public_json_payload({
        "items": [v3_facade_service._question_payload(item.model_dump()) for item in public_items],
        "total": len(public_items),
        "safety_notice": SAFETY_NOTICE,
    })


@router.post("/patient-card")
def patient_card(request: PatientCardRequest) -> dict[str, object]:
    return v3_facade_service.public_json_payload(report_service.generate_patient_card(request).model_dump())


@router.post("/patient-card/{card_id}/approve")
def approve_patient_card(card_id: str, request: PatientCardApproveRequest) -> dict[str, object]:
    try:
        return v3_facade_service.public_json_payload(report_service.approve_patient_card(card_id, request).model_dump())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Patient card not found: {card_id}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/models")
def list_models() -> dict[str, object]:
    return v3_facade_service.public_json_payload({
        "items": [model.model_dump() for model in model_service.list_models()],
        "notice": "模型能力分为平台评估预览，不代表真实临床评测。",
        "safety_notice": SAFETY_NOTICE,
    })


@router.get("/models/evaluation")
def model_evaluation() -> dict[str, object]:
    return v3_facade_service.model_evaluation()


@router.post("/models/custom-evaluate")
def custom_model_evaluate(payload: dict[str, object]) -> dict[str, object]:
    return v3_facade_service.custom_model_evaluate(payload)


@router.post("/models/select")
def select_model(request: ModelSelectRequest) -> dict[str, object]:
    try:
        return v3_facade_service.public_json_payload(model_service.select_model(request.model_id).model_dump())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/models/admission-test")
def model_admission_test(request: ModelAdmissionTestRequest) -> dict[str, object]:
    return v3_facade_service.public_json_payload(model_service.admission_test(request).model_dump())


@router.get("/models/admission-state")
def model_admission_state() -> dict[str, object]:
    return v3_facade_service.public_json_payload({"item": model_service.admission_state(), "safety_notice": SAFETY_NOTICE})


@router.get("/audit")
def list_audit() -> dict[str, object]:
    logs = audit_service.list_logs()
    return v3_facade_service.public_json_payload({"items": [log.model_dump() for log in logs], "total": len(logs)})
