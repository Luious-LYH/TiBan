"""Public Evaluation Lab API.

Legacy portfolio evaluation remains a developer/CI service. The learner-facing
contract starts here and never accepts a request-level provider credential.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from app.services.evaluation_lab_service import evaluation_lab_service
from app.services.model_discovery_service import model_discovery_service


router = APIRouter(prefix="/api/v3/evaluation", tags=["evaluation-lab"])


class EvalSuiteRequest(BaseModel):
    bank_id: str = Field(min_length=1, max_length=100)
    sample_size: int = Field(default=30, ge=1, le=100)
    seed: int | None = Field(default=None, ge=1, le=2_147_483_647)


class EvalBankPublic(BaseModel):
    bank_id: str
    domain_id: str
    name: str
    version: str
    eligible_question_count: int


class RetrievalProfilePublic(BaseModel):
    name: str
    mode: Literal["sparse", "dense", "hybrid"]
    top_k: int
    candidate_pool: int
    rerank_enabled: bool
    rrf_k: int
    section_dedupe: bool


class SavedRagProfilePublic(RetrievalProfilePublic):
    profile_id: str
    bank_id: str
    created_at: str
    updated_at: str


class EvaluationCatalogResponse(BaseModel):
    banks: list[EvalBankPublic]
    runtime_models: list[str]
    default_profile: RetrievalProfilePublic
    prompt_version: str


class EvalSuitePublic(BaseModel):
    suite_id: str
    bank_id: str
    bank_name: str
    sample_size: int
    seed: int
    suite_hash: str
    suite_short: str
    bank_version: str
    prompt_version: str
    created_at: str


class EvaluationRunPublic(BaseModel):
    run_id: str
    name: str
    provider: str
    base_url: str
    model: str
    retrieval_profile: RetrievalProfilePublic | None = None
    status: str
    aggregate: dict[str, Any]
    progress: int
    stage: str
    error: str | None = None


class EvaluationExperimentResponse(BaseModel):
    experiment_id: str
    experiment_type: Literal["model", "rag"]
    status: str
    suite: EvalSuitePublic
    fixed_snapshot: dict[str, Any]
    runs: list[EvaluationRunPublic]
    created_at: str


class EvaluationDeleteResponse(BaseModel):
    deleted_experiment_count: int
    deleted_run_count: int


class ModelDiscoveryRequest(BaseModel):
    base_url: str = Field(min_length=1, max_length=512)
    api_key: str = Field(min_length=1, max_length=512)
    api_format: Literal["openai"] = "openai"


class DiscoveredModelPublic(BaseModel):
    id: str
    display_name: str | None = None
    owned_by: str | None = None


class ModelDiscoveryResponse(BaseModel):
    models: list[DiscoveredModelPublic]
    latency_ms: int


class ModelExperimentRequest(BaseModel):
    suite_id: str = Field(min_length=1, max_length=150)
    models: list[str] = Field(default_factory=list, max_length=6)
    base_url: str | None = Field(default=None, max_length=512)
    api_key: str | None = Field(default=None, max_length=512)
    provider: str | None = Field(default=None, max_length=120)

    @field_validator("models")
    @classmethod
    def clean_models(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item and item.strip()]


class RetrievalProfileRequest(BaseModel):
    name: str = Field(default="对比方案", min_length=1, max_length=80)
    mode: Literal["sparse", "dense", "hybrid"] = "hybrid"
    top_k: int = Field(default=5, ge=1, le=12)
    candidate_pool: int = Field(default=20, ge=1, le=80)
    rerank_enabled: bool = False
    rrf_k: int = Field(default=60, ge=1, le=240)
    section_dedupe: bool = True


class SavedRagProfileRequest(RetrievalProfileRequest):
    bank_id: str = Field(min_length=1, max_length=100)
    profile_id: str | None = Field(default=None, max_length=150)


class RagProfileDeleteResponse(BaseModel):
    profile_id: str
    deleted: bool = True


class RagExperimentRequest(BaseModel):
    suite_id: str = Field(min_length=1, max_length=150)
    model: str | None = Field(default=None, max_length=180)
    variants: list[RetrievalProfileRequest] = Field(default_factory=list, max_length=2)


@router.get("/lab/catalog", response_model=EvaluationCatalogResponse)
def evaluation_lab_catalog() -> dict[str, Any]:
    return evaluation_lab_service.catalog()


@router.post("/lab/suites", response_model=EvalSuitePublic)
def create_eval_suite(request: EvalSuiteRequest) -> dict[str, Any]:
    try:
        return evaluation_lab_service.create_suite(bank_id=request.bank_id, sample_size=request.sample_size, seed=request.seed)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Question bank not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/lab/suites/latest", response_model=EvalSuitePublic | None)
def latest_eval_suite(bank_id: str = Query(min_length=1, max_length=100)) -> dict[str, Any] | None:
    return evaluation_lab_service.latest_suite(bank_id=bank_id)


@router.get("/lab/profiles", response_model=list[SavedRagProfilePublic])
def list_rag_profiles(bank_id: str = Query(min_length=1, max_length=100)) -> list[dict[str, Any]]:
    return evaluation_lab_service.list_rag_profiles(bank_id=bank_id)


@router.post("/lab/profiles", response_model=SavedRagProfilePublic)
def save_rag_profile(request: SavedRagProfileRequest) -> dict[str, Any]:
    try:
        return evaluation_lab_service.save_rag_profile(
            bank_id=request.bank_id,
            profile=request.model_dump(exclude={"bank_id", "profile_id"}),
            profile_id=request.profile_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="RAG 对比方案不存在或题库不存在。") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/lab/profiles/{profile_id}", response_model=RagProfileDeleteResponse)
def delete_rag_profile(
    profile_id: str,
    bank_id: str = Query(min_length=1, max_length=100),
) -> dict[str, Any]:
    try:
        evaluation_lab_service.delete_rag_profile(bank_id=bank_id, profile_id=profile_id)
        return {"profile_id": profile_id, "deleted": True}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="RAG 对比方案不存在。") from exc


@router.post("/lab/experiments/model", response_model=EvaluationExperimentResponse)
def create_model_experiment(request: ModelExperimentRequest) -> dict[str, Any]:
    try:
        return evaluation_lab_service.create_model_experiment(
            suite_id=request.suite_id, models=request.models, base_url=request.base_url,
            api_key=request.api_key, provider=request.provider,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="评测集不存在。") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/lab/models/discover", response_model=ModelDiscoveryResponse)
def discover_models(request: ModelDiscoveryRequest) -> dict[str, Any]:
    try:
        return model_discovery_service.discover(
            base_url=request.base_url,
            api_key=request.api_key,
            api_format=request.api_format,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/lab/experiments/rag", response_model=EvaluationExperimentResponse)
def create_rag_experiment(request: RagExperimentRequest) -> dict[str, Any]:
    try:
        return evaluation_lab_service.create_rag_experiment(
            suite_id=request.suite_id, model=request.model,
            variants=[item.model_dump() for item in request.variants],
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="评测集不存在。") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/lab/experiments/latest", response_model=EvaluationExperimentResponse | None)
def latest_evaluation_experiment(
    bank_id: str = Query(min_length=1, max_length=100),
    experiment_type: Literal["model", "rag"] = Query(...),
) -> dict[str, Any] | None:
    return evaluation_lab_service.latest_experiment(bank_id=bank_id, experiment_type=experiment_type)


@router.delete("/lab/experiments", response_model=EvaluationDeleteResponse)
def delete_evaluation_experiments(
    bank_id: str = Query(min_length=1, max_length=100),
    experiment_type: Literal["model", "rag"] = Query(...),
) -> dict[str, int]:
    return evaluation_lab_service.delete_experiments(bank_id=bank_id, experiment_type=experiment_type)


@router.get("/lab/experiments/{experiment_id}", response_model=EvaluationExperimentResponse)
def get_evaluation_experiment(experiment_id: str) -> dict[str, Any]:
    try:
        return evaluation_lab_service.experiment(experiment_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Evaluation experiment not found.") from exc
