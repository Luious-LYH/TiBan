from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.config import SAFETY_NOTICE
from app.schemas import EvaluationArtifactResponse
from app.services.model_eval_service import get_run, list_datasets, run_evaluation, test_connection
from app.services.portfolio_agent_runtime import portfolio_agent_runtime


router = APIRouter(prefix="/api/v3/evaluation", tags=["stage1-evaluation"])
_HOST_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_COMPOSE_ARTIFACT_ROOT = Path("/app/artifacts")
# Backend source is the Docker build context, while evaluation artifacts stay
# at the repository root.  Compose mounts that existing, read-only artifact
# folder at /app/artifacts; host runs continue to resolve ../artifacts.
ARTIFACT_ROOT = _COMPOSE_ARTIFACT_ROOT if _COMPOSE_ARTIFACT_ROOT.exists() else _HOST_PROJECT_ROOT / "artifacts"
ARTIFACT_PATH = ARTIFACT_ROOT / "eval" / "latest.json"


def _artifact() -> dict[str, Any]:
    path = ARTIFACT_PATH.resolve()
    if not path.exists():
        return {
            "artifact_available": False,
            "artifact_path": None,
            "mode": "not_run",
            "sample_count": 0,
            "metrics": {},
            "cases": [],
            "notice": "尚未运行",
            "safety_notice": SAFETY_NOTICE,
        }
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        "artifact_available": True,
        "artifact_path": "artifacts/eval/latest.json",
        "mode": str(payload.get("conditions", {}).get("mode", "offline_artifact")),
        "metric_version": payload.get("metric_version"),
        "sample_count": int(payload.get("metrics", {}).get("case_count", len(payload.get("cases", [])))),
        "metrics": payload.get("metrics", {}),
        "cases": payload.get("cases", []),
        "probes": _public_probes(payload),
        # The current artifact contains one sparse retrieval replay only.
        # Do not invent Dense/Hybrid/Rerank rows merely to fill a comparison.
        "strategy_comparison": _public_strategies(payload),
        "created_at": payload.get("created_at"),
        "notice": "离线确定性 artifact；不代表真实候选模型或临床性能。",
        "safety_notice": SAFETY_NOTICE,
    }


def _evidence_catalog() -> dict[str, dict[str, str]]:
    catalog: dict[str, dict[str, str]] = {}
    for case in portfolio_agent_runtime.list_cases():
        for fact in case.get("facts", []):
            evidence_id = str(fact.get("id", ""))
            if evidence_id:
                catalog[evidence_id] = {
                    "evidence_id": evidence_id,
                    "label": str(fact.get("label", "教学证据")),
                    "source_title": str(case.get("source_dataset", "公开教学样例")),
                    "section": str(fact.get("dimension", "事实依据")),
                    "snippet": str(fact.get("evidence", "")),
                    "query_context": f"{case.get('title', '')} {fact.get('label', '')} {(fact.get('aliases') or [''])[0]}",
                }
    return catalog


def _public_probes(payload: dict[str, Any]) -> list[dict[str, Any]]:
    catalog = _evidence_catalog()
    raw_probes = payload.get("retrieval_eval", {}).get("probes", [])
    items: list[dict[str, Any]] = []
    for raw in raw_probes:
        if not isinstance(raw, dict):
            continue
        expected_id = str(raw.get("expected_evidence_id", ""))
        expected = catalog.get(expected_id)
        if expected is None:
            continue
        retrieved = []
        for rank, evidence_id in enumerate(raw.get("ranked_evidence_ids", []), start=1):
            evidence = catalog.get(str(evidence_id))
            if evidence is not None:
                retrieved.append({**{key: value for key, value in evidence.items() if key != "query_context"}, "rank": rank})
        items.append({
            "id": str(raw.get("query_id", expected_id)),
            "query": expected["query_context"],
            "expected_evidence": {key: value for key, value in expected.items() if key != "query_context"},
            "retrieved": retrieved,
            "hit_at_1": bool(raw.get("hit_at_1")),
            "hit_at_3": bool(raw.get("hit_at_3")),
        })
    return items


def _public_strategies(payload: dict[str, Any]) -> list[dict[str, Any]]:
    comparison = payload.get("strategy_comparison")
    if not isinstance(comparison, list):
        return []
    rows = []
    for item in comparison:
        if not isinstance(item, dict) or not isinstance(item.get("metrics"), dict):
            continue
        rows.append({
            "name": str(item.get("name", "未命名策略")),
            "metrics": {str(key): float(value) for key, value in item["metrics"].items() if isinstance(value, (int, float))},
            "artifact_path": str(item.get("artifact_path", "artifacts/eval/latest.json")),
        })
    return rows


@router.get("/latest", response_model=EvaluationArtifactResponse)
def latest_evaluation() -> dict[str, Any]:
    return _artifact()


class EvaluationDatasetPublic(BaseModel):
    dataset_id: str
    domain_id: str
    name: str
    description: str
    source_dataset: str
    modality: str
    version: str
    dataset_hash: str
    sample_count: int = Field(ge=0)
    supports_vision: bool
    tutor_indexed: bool


class EvaluationDatasetListResponse(BaseModel):
    items: list[EvaluationDatasetPublic]
    api_source: str = "backend"


class EvaluationConnectionRequest(BaseModel):
    base_url: str = Field(min_length=1, max_length=500)
    model: str = Field(min_length=1, max_length=180)
    api_key: str = Field(min_length=1, max_length=1000)


class EvaluationConnectionResponse(BaseModel):
    ok: bool
    provider: str
    model: str
    latency_ms: int | None = None
    error: str | None = None
    fallback: bool = False
    key_persisted: bool = False


class EvaluationRunRequest(EvaluationConnectionRequest):
    dataset_id: str
    sample_count: int = Field(default=10, ge=1, le=300)


class EvaluationRunResponse(BaseModel):
    eval_run_id: str
    dataset_id: str
    dataset_version: str
    dataset_hash: str
    provider: str
    model: str
    prompt_version: str
    status: str
    sample_count: int
    aggregate: dict[str, Any]
    usage: dict[str, Any]
    errors: list[dict[str, Any]]
    created_at: str
    completed_at: str | None = None
    artifact_path: str | None = None
    cases: list[dict[str, Any]]
    gold_revealed: bool = False
    fallback: bool = False
    safety_notice: str = SAFETY_NOTICE


@router.get("/datasets", response_model=EvaluationDatasetListResponse)
def evaluation_datasets() -> dict[str, Any]:
    # Keep the public contract stable for pre-Stage-7 local cache/test
    # providers that predate domain scoping.  The canonical dataset registry
    # already emits this field; this boundary normalization prevents a stale
    # cache from breaking the whole evaluation catalog response.
    items = []
    for item in list_datasets():
        normalized = dict(item)
        normalized.setdefault(
            "domain_id",
            "general_science" if normalized.get("dataset_id") == "general-science-text-eval-v1" else "endoscopy",
        )
        items.append(normalized)
    return {"items": items, "api_source": "backend"}


@router.post("/connection-test", response_model=EvaluationConnectionResponse)
def evaluation_connection_test(request: EvaluationConnectionRequest) -> dict[str, Any]:
    try:
        # The key is used only inside this call and is intentionally absent
        # from both the response and any persistence layer.
        return test_connection(base_url=request.base_url, api_key=request.api_key, model=request.model)
    except Exception as exc:
        return {"ok": False, "provider": "byok_openai_compatible", "model": request.model, "error": type(exc).__name__, "fallback": False, "key_persisted": False}


@router.post("/runs", response_model=EvaluationRunResponse)
def create_evaluation_run(request: EvaluationRunRequest) -> dict[str, Any]:
    try:
        return run_evaluation(dataset_id=request.dataset_id, base_url=request.base_url, api_key=request.api_key, model=request.model, sample_count=request.sample_count)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Evaluation dataset not found.") from exc
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/runs/{eval_run_id}", response_model=EvaluationRunResponse)
def read_evaluation_run(eval_run_id: str, reveal_gold: bool = False) -> dict[str, Any]:
    try:
        # Gold answers are withheld unless the user makes the explicit reveal
        # request; normal result views still show parsed answer and correctness
        # only after reveal.
        return get_run(eval_run_id, reveal_gold=reveal_gold)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Evaluation run not found.") from exc
