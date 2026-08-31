"""BYOK model-evaluation workbench with isolated frozen evaluation packs.

Evaluation data is never exposed to Tutor retrieval, learner QBank queries or
Question Factory.  Provider credentials are accepted only as call arguments;
they are not written to ORM rows, logs, traces or artifacts.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any
from uuid import uuid4

from sqlalchemy import select

from app.core.config import LOCAL_VQA_ROOT, SAFETY_NOTICE
from app.domains import get_domain
from app.db.database import SessionLocal
from app.db.models import EvalArtifactModel, EvalCaseModel, EvalDatasetModel, EvalDatasetVersionModel, EvalRunModel
from app.services.data_governance import resolve_local_asset
from app.services.llm_provider import llm_provider
from app.services.qbank_import_service import CMEXAM_ROOT, _answer_letters, _option_map


TEXT_DATASET_ID = "cmexam-text-eval-v1"
VLM_DATASET_ID = "endobench-vlm-eval-v1"
GENERAL_DATASET_ID = "general-science-text-eval-v1"
TEXT_VERSION = "cmexam-text-eval-v1"
VLM_VERSION = "endobench-vlm-eval-v1"
GENERAL_VERSION = "general-science-text-eval-v1"
TEXT_LIMIT = 100
VLM_LIMIT = 100
PROMPT_VERSION = "model-eval-answer-json-v1"
ARTIFACT_DIR = Path(__file__).resolve().parents[3] / "artifacts" / "eval" / "model-runs"
RUNTIME_PACK_DIR = Path(__file__).resolve().parents[2] / "runtime" / "eval_packs"


def _sha(value: str | bytes) -> str:
    raw = value.encode("utf-8") if isinstance(value, str) else value
    return hashlib.sha256(raw).hexdigest()


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    return sorted(values)[max(0, math.ceil(len(values) * percentile) - 1)]


def _safe_candidate(parsed_answer: str | None) -> str:
    """Retain only answer-shaped output; never persist raw model reasoning."""

    if parsed_answer:
        return json.dumps({"answer": parsed_answer}, ensure_ascii=False)
    return "unparsed provider response withheld; no raw reasoning retained"


def _safe_error(error: str | None, secret: str) -> str | None:
    """Keep provider diagnostics useful without allowing a key to escape."""

    if error is None:
        return None
    cleaned = str(error)
    if secret:
        cleaned = cleaned.replace(secret, "[redacted]")
    return cleaned[:320]


def _parse_answer(text: str) -> str | None:
    cleaned = text.strip()
    try:
        payload = json.loads(cleaned.strip("` \n"))
        if isinstance(payload, dict):
            value = payload.get("answer") or payload.get("option") or payload.get("choice")
            if isinstance(value, str):
                match = re.search(r"\b([A-E])\b", value.upper())
                if match:
                    return match.group(1)
    except json.JSONDecodeError:
        pass
    match = re.search(r"(?:^|[^A-Z])([A-E])(?:[^A-Z]|$)", cleaned.upper())
    return match.group(1) if match else None


def _text_pack_path() -> Path:
    return RUNTIME_PACK_DIR / f"{TEXT_DATASET_ID}.json"


def _vlm_pack_path() -> Path:
    return RUNTIME_PACK_DIR / f"{VLM_DATASET_ID}.json"


def _general_pack_path() -> Path:
    return RUNTIME_PACK_DIR / f"{GENERAL_DATASET_ID}.json"


def _build_text_pack() -> dict[str, Any]:
    path = CMEXAM_ROOT / "data" / "test_with_annotations.csv"
    if not path.is_file():
        raise FileNotFoundError(path)
    cases: list[dict[str, Any]] = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for index, row in enumerate(csv.DictReader(handle)):
            options, answers = _option_map(row.get("Options", "")), _answer_letters(row.get("Answer", ""))
            if len(options) < 2 or len(answers) != 1 or answers[0] not in options:
                continue
            cases.append({
                "case_id": f"cmexam-eval-{index:06d}",
                "source_item_id": f"test_with_annotations.csv:{index}",
                "question": str(row.get("Question") or "").strip(),
                "options": [{"id": key, "text": value} for key, value in options.items()],
                "gold_answer": answers[0],
                "task": "text_single_choice",
                "topic": str(row.get("Disease Group") or row.get("Clinical Department") or ""),
            })
            if len(cases) >= TEXT_LIMIT:
                break
    return _pack_payload(TEXT_DATASET_ID, TEXT_VERSION, "CMExam", "text", False, cases)


def _build_vlm_pack() -> dict[str, Any]:
    path = LOCAL_VQA_ROOT / "EndoBench" / "EndoBench.json"
    if not path.is_file():
        raise FileNotFoundError(path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    cases: list[dict[str, Any]] = []
    for item in raw:
        relative = str(item.get("image_path") or "").replace("\\", "/")
        try:
            image = resolve_local_asset("endobench", f"EndoBench-Images/{relative}")
        except (ValueError, FileNotFoundError):
            continue
        answer = str(item.get("answer") or "").strip().upper()
        options = item.get("options")
        if not relative or not image.is_file() or not re.fullmatch(r"[A-E]", answer) or not isinstance(options, list) or len(options) < 2:
            continue
        cases.append({
            "case_id": f"endobench-eval-{item.get('id', len(cases))}",
            "source_item_id": str(item.get("id", len(cases))),
            "question": str(item.get("question") or "").strip(),
            "options": [{"id": chr(65 + index), "text": str(value)} for index, value in enumerate(options)],
            "gold_answer": answer,
            "task": str(item.get("subtask") or item.get("task") or "endoscopy_vlm"),
            "topic": str(item.get("category") or item.get("scene") or ""),
            "image_rel_path": relative,
        })
        if len(cases) >= VLM_LIMIT:
            break
    return _pack_payload(VLM_DATASET_ID, VLM_VERSION, "EndoBench", "image", True, cases)


def _build_general_pack() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[1] / "data" / "general_science_fixture.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    cases = [
        {
            "case_id": f"general-science-eval-{item['id']}",
            "source_item_id": item["id"],
            "question": item["stem"],
            "options": [{"id": option_id, "text": option_text} for option_id, option_text in item["options"]],
            "gold_answer": item["answer"],
            "task": "text_single_choice",
            "topic": item["topic"],
        }
        for item in raw
    ]
    return _pack_payload(GENERAL_DATASET_ID, GENERAL_VERSION, "TiBan General Science fixture", "text", False, cases)


def _pack_payload(dataset_id: str, version: str, source_dataset: str, modality: str, supports_vision: bool, cases: list[dict[str, Any]]) -> dict[str, Any]:
    canonical = json.dumps(cases, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {
        "dataset_id": dataset_id,
        "domain_id": "general_science" if dataset_id == GENERAL_DATASET_ID else "endoscopy",
        "version": version,
        "source_dataset": source_dataset,
        "modality": modality,
        "supports_vision": supports_vision,
        "sample_count": len(cases),
        "dataset_hash": _sha(canonical),
        "tutor_indexed": False,
        "cases": cases,
    }


def _pack_domain_id(pack: dict[str, Any]) -> str:
    """Normalize pre-Stage-7 cached/test packs at the evaluation boundary.

    Runtime packs generated before domain scoping, and small unit-test fixtures,
    may not contain ``domain_id``.  The dataset id remains the canonical
    compatibility discriminator; production packs always carry the explicit
    field and are validated by the public response schema.
    """

    return str(pack.get("domain_id") or ("general_science" if pack.get("dataset_id") == GENERAL_DATASET_ID else "endoscopy"))


def _load_pack(dataset_id: str) -> dict[str, Any]:
    RUNTIME_PACK_DIR.mkdir(parents=True, exist_ok=True)
    path = _text_pack_path() if dataset_id == TEXT_DATASET_ID else _vlm_pack_path() if dataset_id == VLM_DATASET_ID else _general_pack_path() if dataset_id == GENERAL_DATASET_ID else None
    builder = _build_text_pack if dataset_id == TEXT_DATASET_ID else _build_vlm_pack if dataset_id == VLM_DATASET_ID else _build_general_pack if dataset_id == GENERAL_DATASET_ID else None
    if path is None or builder is None:
        raise KeyError(dataset_id)
    if path.is_file():
        payload = json.loads(path.read_text(encoding="utf-8"))
        # Runtime packs are intentionally ignored/generated.  Older local
        # caches predate Stage 7's domain field; normalize them in memory so a
        # stale cache cannot break the public dataset contract.
        payload.setdefault("domain_id", "general_science" if dataset_id == GENERAL_DATASET_ID else "endoscopy")
        return payload
    payload = builder()
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def _dataset_public(pack: dict[str, Any]) -> dict[str, Any]:
    descriptions = {
        TEXT_DATASET_ID: "冻结的 100 条 CMExam 单选文本评测；答案留在评测域，不进入 Tutor RAG。",
        VLM_DATASET_ID: "冻结的 100 条 EndoBench 内镜视觉评测；Evaluation-only，不进入 Tutor、Factory 或 learner QBank。",
        GENERAL_DATASET_ID: "冻结的 TiBan 自建通用科学文本评测；与医疗评测、QBank 和知识库隔离。",
    }
    return {
        "dataset_id": pack["dataset_id"],
        "domain_id": pack["domain_id"],
        "name": "CMExam 文本评测" if pack["dataset_id"] == TEXT_DATASET_ID else "EndoBench VLM 评测" if pack["dataset_id"] == VLM_DATASET_ID else "通用科学文本评测",
        "description": descriptions[pack["dataset_id"]],
        "source_dataset": pack["source_dataset"],
        "modality": pack["modality"],
        "version": pack["version"],
        "dataset_hash": pack["dataset_hash"],
        "sample_count": pack["sample_count"],
        "supports_vision": pack["supports_vision"],
        "tutor_indexed": False,
    }


def ensure_datasets() -> list[dict[str, Any]]:
    # Medical evaluation packs remain available whenever their governed local
    # source fixtures are mounted.  A clean checkout must still expose the
    # project-authored General pack rather than making all Evaluation depend on
    # non-redistributed medical data.
    packs: list[dict[str, Any]] = []
    for dataset_id in (TEXT_DATASET_ID, VLM_DATASET_ID, GENERAL_DATASET_ID):
        try:
            packs.append(_load_pack(dataset_id))
        except FileNotFoundError:
            if dataset_id == GENERAL_DATASET_ID:
                raise
    with SessionLocal() as session:
        for pack in packs:
            existing = session.get(EvalDatasetModel, pack["dataset_id"])
            if existing is None:
                session.add(EvalDatasetModel(**{key: pack[key] for key in ("dataset_id", "domain_id", "source_dataset", "modality", "version", "dataset_hash", "sample_count", "supports_vision", "tutor_indexed")}, name=_dataset_public(pack)["name"], description=_dataset_public(pack)["description"]))
            else:
                for key in ("domain_id", "version", "dataset_hash", "sample_count", "supports_vision", "tutor_indexed"):
                    setattr(existing, key, pack[key])
            version_id = f"{pack['dataset_id']}-{pack['dataset_hash'][:12]}"
            if session.get(EvalDatasetVersionModel, version_id) is None:
                session.add(EvalDatasetVersionModel(dataset_version_id=version_id, dataset_id=pack["dataset_id"], version=pack["version"], dataset_hash=pack["dataset_hash"], manifest={"domain_id": pack["domain_id"], "sample_count": pack["sample_count"], "source_dataset": pack["source_dataset"], "tutor_indexed": False}))
        session.commit()
    return [_dataset_public(pack) for pack in packs]


def list_datasets() -> list[dict[str, Any]]:
    return ensure_datasets()


def test_connection(*, base_url: str, api_key: str, model: str) -> dict[str, Any]:
    result = llm_provider.chat(
        system_prompt="You are a connection probe. Return exactly JSON: {\"ok\":true}.",
        user_prompt="connection probe",
        base_url=base_url,
        api_key=api_key,
        model=model,
        provider="byok_openai_compatible",
        max_tokens=20,
        temperature=0,
        allow_fallback=False,
    )
    return {"ok": result.ok, "provider": result.provider, "model": result.model, "latency_ms": result.latency_ms, "error": _safe_error(result.error, api_key), "fallback": False}


def _prompt(case: dict[str, Any], modality: str) -> str:
    options = "\n".join(f"{item['id']}. {item['text']}" for item in case["options"])
    image_note = " An image is attached; use only visible evidence." if modality == "image" else ""
    return f"""Return JSON only, with exactly one field `answer` containing one option letter A-E. Do not provide reasoning or markdown.{image_note}
Question: {case['question']}
Options:
{options}
"""


def run_evaluation(*, dataset_id: str, base_url: str, api_key: str, model: str, sample_count: int = 10) -> dict[str, Any]:
    if not api_key.strip():
        raise ValueError("api_key is required for a BYOK evaluation")
    pack = _load_pack(dataset_id)
    samples = list(pack["cases"][: min(sample_count, pack["sample_count"])])
    run_id = f"evalrun_{uuid4().hex[:14]}"
    case_outputs: list[dict[str, Any]] = []
    latencies: list[float] = []
    errors: list[dict[str, Any]] = []
    total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    for case in samples:
        image_path = f"eval://endobench/{case['image_rel_path']}" if pack["modality"] == "image" else None
        result = llm_provider.chat(
            system_prompt=("You are a medical-education benchmark respondent. Answer the multiple-choice question, but output only the requested JSON letter. This is evaluation data, not clinical advice." if _pack_domain_id(pack) == "endoscopy" else "You are a general-science benchmark respondent. Answer the multiple-choice question and output only the requested JSON letter."),
            user_prompt=_prompt(case, pack["modality"]),
            image_path=image_path,
            base_url=base_url,
            api_key=api_key,
            model=model,
            provider="byok_openai_compatible",
            max_tokens=80,
            temperature=0,
            allow_fallback=False,
        )
        parsed = _parse_answer(result.text) if result.ok else None
        valid = parsed is not None and parsed in {item["id"] for item in case["options"]}
        correct = bool(valid and parsed == case["gold_answer"])
        if result.latency_ms is not None:
            latencies.append(float(result.latency_ms))
        for key, value in (result.usage or {}).items():
            if key in total_usage:
                total_usage[key] += value
        error_category = None
        if not result.ok:
            error_category = "provider_error"
        elif not valid:
            error_category = "invalid_parse"
        elif not correct:
            error_category = "incorrect"
        if error_category:
            errors.append({"case_id": case["case_id"], "category": error_category, "provider_error": _safe_error(result.error, api_key) if not result.ok else None})
        case_outputs.append({
            "case_id": case["case_id"],
            "source_item_id": case["source_item_id"],
            "question": case["question"],
            "candidate_output": _safe_candidate(parsed if valid else None),
            "parsed_answer": parsed if valid else None,
            "gold_answer": case["gold_answer"],
            "correct": correct if result.ok else None,
            "valid_parse": valid,
            "latency_ms": result.latency_ms,
            "error_category": error_category,
            "task": case["task"],
            "topic": case.get("topic"),
            "image_attached": result.image_attached,
        })
    count = len(samples)
    valid_count = sum(bool(item["valid_parse"]) for item in case_outputs)
    correct_count = sum(bool(item["correct"]) for item in case_outputs)
    aggregate = {
        "sample_count": count,
        "accuracy": round(correct_count / count, 4) if count else 0.0,
        "valid_parse_rate": round(valid_count / count, 4) if count else 0.0,
        "failure_rate": round(sum(item["error_category"] == "provider_error" for item in case_outputs) / count, 4) if count else 0.0,
        "latency_p50_ms": round(median(latencies), 2) if latencies else None,
        "latency_p95_ms": round(_percentile(latencies, 0.95), 2) if latencies else None,
        "token_usage": total_usage,
    }
    created_at = datetime.now(timezone.utc).isoformat()
    status = "completed" if not errors or all(item["category"] != "provider_error" for item in errors) else "completed_with_failures"
    artifact_path = f"artifacts/eval/model-runs/{run_id}.json"
    artifact = {
        "artifact_version": "model-evaluation-run-v1",
        "eval_run_id": run_id,
        "created_at": created_at,
        "completed_at": created_at,
        "provider": "byok_openai_compatible",
        "model": model,
        "dataset_id": pack["dataset_id"],
        "dataset_version": pack["version"],
        "dataset_hash": pack["dataset_hash"],
        "dataset": {"dataset_id": pack["dataset_id"], "domain_id": _pack_domain_id(pack), **{key: pack[key] for key in ("version", "dataset_hash", "source_dataset", "modality", "sample_count")}},
        "prompt_version": PROMPT_VERSION,
        "status": status,
        "sample_count": count,
        "fallback": False,
        "aggregate": aggregate,
        "usage": total_usage,
        "errors": errors,
        "cases": case_outputs,
        "artifact_path": artifact_path,
        "safety_notice": get_domain(_pack_domain_id(pack)).learner_notice,
        "secret_policy": "api_key request-scoped; not persisted, logged, traced or artifacted",
    }
    artifact_bytes = json.dumps(artifact, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    artifact_hash = _sha(artifact_bytes)
    artifact["artifact_hash"] = artifact_hash
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    artifact_file_path = ARTIFACT_DIR / f"{run_id}.json"
    artifact_file_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with SessionLocal() as session:
        session.add(EvalRunModel(eval_run_id=run_id, dataset_id=pack["dataset_id"], dataset_version=pack["version"], dataset_hash=pack["dataset_hash"], provider="byok_openai_compatible", model=model, prompt_version=PROMPT_VERSION, status=status, sample_count=count, aggregate=aggregate, usage=total_usage, errors=errors, completed_at=datetime.utcnow()))
        session.flush()
        session.add_all([EvalCaseModel(eval_case_id=f"{run_id}_{index:04d}", eval_run_id=run_id, source_item_id=item["source_item_id"], question=item["question"], candidate_output=item["candidate_output"], parsed_answer=item["parsed_answer"], gold_answer=item["gold_answer"], correct=item["correct"], valid_parse=item["valid_parse"], latency_ms=item["latency_ms"], error_category=item["error_category"], task=item["task"], topic=item["topic"]) for index, item in enumerate(case_outputs)])
        session.add(EvalArtifactModel(artifact_id=f"artifact_{uuid4().hex[:12]}", eval_run_id=run_id, artifact_path=artifact_path, artifact_hash=artifact_hash, created_at=datetime.utcnow()))
        session.commit()
    public_cases = [
        {
            **{key: item[key] for key in ("case_id", "source_item_id", "question", "candidate_output", "parsed_answer", "valid_parse", "latency_ms", "error_category", "task", "topic", "image_attached")},
            "gold_answer": None,
            "correct": None,
        }
        for item in case_outputs
    ]
    return {
        "eval_run_id": run_id,
        "dataset_id": pack["dataset_id"],
        "dataset_version": pack["version"],
        "dataset_hash": pack["dataset_hash"],
        "provider": "byok_openai_compatible",
        "model": model,
        "prompt_version": PROMPT_VERSION,
        "status": status,
        "sample_count": count,
        "aggregate": aggregate,
        "usage": total_usage,
        "errors": errors,
        "created_at": created_at,
        "completed_at": created_at,
        "artifact_path": artifact_path,
        "cases": public_cases,
        "gold_revealed": False,
        "fallback": False,
            "safety_notice": get_domain(_pack_domain_id(pack)).learner_notice,
    }


def get_run(eval_run_id: str, *, reveal_gold: bool = False) -> dict[str, Any]:
    with SessionLocal() as session:
        run = session.get(EvalRunModel, eval_run_id)
        if run is None:
            raise KeyError(eval_run_id)
        cases = list(session.scalars(select(EvalCaseModel).where(EvalCaseModel.eval_run_id == eval_run_id).order_by(EvalCaseModel.created_at, EvalCaseModel.eval_case_id)))
        artifact = session.scalar(select(EvalArtifactModel).where(EvalArtifactModel.eval_run_id == eval_run_id))
        return {
            "eval_run_id": run.eval_run_id,
            "dataset_id": run.dataset_id,
            "dataset_version": run.dataset_version,
            "dataset_hash": run.dataset_hash,
            "provider": run.provider,
            "model": run.model,
            "prompt_version": run.prompt_version,
            "status": run.status,
            "sample_count": run.sample_count,
            "aggregate": run.aggregate,
            "usage": run.usage,
            "errors": run.errors,
            "created_at": run.created_at.isoformat(),
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "artifact_path": artifact.artifact_path if artifact else None,
            "cases": [
                {
                    "eval_case_id": case.eval_case_id,
                    "source_item_id": case.source_item_id,
                    "question": case.question,
                    "candidate_output": case.candidate_output,
                    "parsed_answer": case.parsed_answer,
                    "gold_answer": case.gold_answer if reveal_gold else None,
                    "correct": case.correct if reveal_gold else None,
                    "valid_parse": case.valid_parse,
                    "latency_ms": case.latency_ms,
                    "error_category": case.error_category,
                    "task": case.task,
                    "topic": case.topic,
                }
                for case in cases
            ],
            "gold_revealed": reveal_gold,
            "fallback": False,
            "safety_notice": SAFETY_NOTICE,
        }
