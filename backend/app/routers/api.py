import base64
import hashlib
import re
import struct
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query

from app.core.config import APP_NAME, SAFETY_NOTICE, UPLOAD_DIR
from app.schemas import (
    ChallengeBenchmarkRequest,
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
    SkillRunRequest,
    SubmissionRequest,
    TutorChatRequest,
    TutorExplainRequest,
    TutorHintRequest,
)
from app.services.audit_service import audit_service, now_iso
from app.services.dashboard_service import dashboard_service
from app.services.demo_check_service import demo_check_service
from app.services.grading_service import grading_service
from app.services.memory_service import memory_service
from app.services.model_service import model_service
from app.services.question_service import question_service
from app.services.report_service import report_service
from app.services.skill_registry import skill_registry
from app.services.tutor_orchestrator import tutor_orchestrator

router = APIRouter(prefix="/api")


@router.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "service": APP_NAME,
        "version": "v2.0",
        "capabilities": [
            "provider_self_test",
            "provider_visual_self_test",
            "provider_self_test_receipt",
            "provider_diagnostics",
            "provider_evidence_ladder",
            "provider_preflight",
            "provider_request_preview",
            "report_upload_receipt",
            "model_admission_receipt",
            "knowledge_source_chain",
            "real_sample_coverage",
            "demo_check_sandbox",
            "demo_check_restore_verified",
            "demo_check_exam_card_receipt",
            "challenge_benchmark",
            "challenge_audit_receipt",
            "patient_card_generation_receipt",
            "patient_card_approve",
            "skill_run_receipt",
            "delivery_report",
        ],
    }


@router.get("/provider/status")
def provider_status() -> dict[str, object]:
    return model_service.provider_status()


@router.get("/provider/diagnostics")
def provider_diagnostics() -> dict[str, object]:
    return model_service.provider_diagnostics()


@router.post("/provider/preflight")
def provider_preflight(request: ProviderPreflightRequest) -> dict[str, object]:
    return model_service.provider_preflight(request).model_dump()


@router.post("/provider/request-preview")
def provider_request_preview(request: ProviderRequestPreviewRequest) -> dict[str, object]:
    return model_service.provider_request_preview(request).model_dump()


@router.post("/provider/self-test")
def provider_self_test(request: ProviderSelfTestRequest) -> dict[str, object]:
    return model_service.provider_self_test(request).model_dump()


@router.get("/dashboard")
def dashboard() -> dict[str, object]:
    return dashboard_service.get_dashboard()


@router.get("/platform/readiness")
def platform_readiness() -> dict[str, object]:
    return dashboard_service.get_readiness()


@router.get("/platform/delivery-report")
def platform_delivery_report() -> dict[str, object]:
    return dashboard_service.get_delivery_report()


@router.post("/platform/demo-check")
def platform_demo_check(learner_id: str = "demo_learner", persist: bool = False) -> dict[str, object]:
    return demo_check_service.run(learner_id=learner_id, persist=persist)


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
    return {"items": [item.model_dump() for item in items], "total": len(items)}


@router.get("/questions/{question_id}")
def get_question(question_id: str, learner_id: str = "demo_learner") -> dict[str, object]:
    try:
        question = question_service.get_question(question_id, learner_id)
        return {"item": question.model_dump()}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/submit")
def submit_answer(request: SubmissionRequest) -> dict[str, object]:
    try:
        return grading_service.grade(request).model_dump()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/tutor/hint")
def tutor_hint(request: TutorHintRequest) -> dict[str, object]:
    try:
        return tutor_orchestrator.hint(request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/tutor/explain")
def tutor_explain(request: TutorExplainRequest) -> dict[str, object]:
    try:
        return tutor_orchestrator.explain(request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/tutor/chat")
def tutor_chat(request: TutorChatRequest) -> dict[str, object]:
    try:
        return tutor_orchestrator.chat(request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/tutor/challenge-benchmark")
def challenge_benchmark(request: ChallengeBenchmarkRequest) -> dict[str, object]:
    try:
        return tutor_orchestrator.challenge_benchmark(request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/learner/profile")
def learner_profile() -> dict[str, object]:
    return memory_service.get_profile().model_dump()


@router.get("/learner/recommendations")
def learner_recommendations() -> dict[str, object]:
    return {"items": memory_service.get_recommendations(), "safety_notice": SAFETY_NOTICE}


@router.get("/learner/training-state")
def learner_training_state() -> dict[str, object]:
    state = memory_service.training_state()
    state["safety_notice"] = SAFETY_NOTICE
    return state


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
    return response.model_dump()


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
    return {"profile": profile.model_dump(), "safety_notice": SAFETY_NOTICE}


@router.post("/report-draft")
def report_draft(request: ReportDraftRequest) -> dict[str, object]:
    return report_service.generate_report_draft(request).model_dump()


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
    return response.model_copy(update={"audit_logged": True, "audit_log_id": audit.id}).model_dump()


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
    return report_service.judge_report_revision(request).model_dump()


@router.get("/knowledge/report")
def report_knowledge() -> dict[str, object]:
    return {"item": report_service.report_knowledge_base(), "safety_notice": SAFETY_NOTICE}


@router.get("/knowledge/cards")
def card_knowledge() -> dict[str, object]:
    return {"item": report_service.card_template_knowledge_base(), "safety_notice": SAFETY_NOTICE}


@router.get("/knowledge/real-samples")
def real_samples() -> dict[str, object]:
    items = question_service.list_questions()
    public_items = [item for item in items if item.source_dataset in {"Kvasir-VQA-x1", "Kvasir-VQA", "EndoBench"}]
    return {
        "items": [item.model_dump() for item in public_items],
        "total": len(public_items),
        "safety_notice": SAFETY_NOTICE,
    }


@router.post("/patient-card")
def patient_card(request: PatientCardRequest) -> dict[str, object]:
    return report_service.generate_patient_card(request).model_dump()


@router.post("/patient-card/{card_id}/approve")
def approve_patient_card(card_id: str, request: PatientCardApproveRequest) -> dict[str, object]:
    try:
        return report_service.approve_patient_card(card_id, request).model_dump()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Patient card not found: {card_id}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/models")
def list_models() -> dict[str, object]:
    return {
        "items": [model.model_dump() for model in model_service.list_models()],
        "notice": "模型能力分为 mock/预留，不代表真实临床评测。",
        "safety_notice": SAFETY_NOTICE,
    }


@router.post("/models/select")
def select_model(request: ModelSelectRequest) -> dict[str, object]:
    try:
        return model_service.select_model(request.model_id).model_dump()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/models/admission-test")
def model_admission_test(request: ModelAdmissionTestRequest) -> dict[str, object]:
    return model_service.admission_test(request).model_dump()


@router.get("/models/admission-state")
def model_admission_state() -> dict[str, object]:
    return {"item": model_service.admission_state(), "safety_notice": SAFETY_NOTICE}


@router.get("/skills")
def list_skills() -> dict[str, object]:
    skills = skill_registry.list_skills()
    return {"items": [skill.model_dump() for skill in skills], "total": len(skills)}


@router.post("/skills/run")
def run_skill(request: SkillRunRequest) -> dict[str, object]:
    try:
        return skill_registry.run(request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/audit")
def list_audit() -> dict[str, object]:
    logs = audit_service.list_logs()
    return {"items": [log.model_dump() for log in logs], "total": len(logs)}
