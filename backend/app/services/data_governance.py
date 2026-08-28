"""Stage 2.5 data policy and safe local asset resolution.

The application never treats a dataset as product-ready merely because a file is
present.  Registry decisions live here so importers, RAG and asset delivery use
the same policy vocabulary.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.core.config import LOCAL_VQA_ROOT


BUSINESS_USAGES = {"user_ready", "needs_explanation", "generation_source", "benchmark_only", "excluded"}
LICENSE_GATE_STATUSES = {"allow", "allow_noncommercial", "metadata_only", "do_not_ingest", "needs_review"}
TUTOR_NAMESPACES = {"medical_general", "gastroenterology", "endoscopy", "qbank_explanations", "user_uploaded", "factory_sources"}


@dataclass(frozen=True)
class DatasetPolicy:
    dataset_id: str
    name: str
    license: str
    license_url: str
    source_url: str
    default_usage: str
    tutor_rag_allowed: bool
    factory_source_allowed: bool
    attribution: str


DATASET_POLICIES: dict[str, DatasetPolicy] = {
    "cmexam": DatasetPolicy(
        "cmexam", "CMExam", "Apache-2.0 / upstream research-use note", "https://github.com/williamliujl/CMExam/blob/main/LICENSE",
        "https://github.com/williamliujl/CMExam", "user_ready", False, False, "CMExam upstream; academic/research-use note retained.",
    ),
    "cmb-exam": DatasetPolicy(
        "cmb-exam", "CMB-Exam", "Apache-2.0", "https://huggingface.co/datasets/FreedomIntelligence/CMB",
        "https://github.com/FreedomIntelligence/CMB", "user_ready", False, False, "FreedomIntelligence CMB; preserve upstream attribution.",
    ),
    "kvasir-vqa": DatasetPolicy(
        "kvasir-vqa", "Kvasir-VQA", "CC BY-NC 4.0", "https://creativecommons.org/licenses/by-nc/4.0/",
        "https://github.com/ENDObenchmark/Kvasir-VQA", "generation_source", False, True, "Kvasir-VQA attribution required; non-commercial use.",
    ),
    "kvasir-vqa-x1": DatasetPolicy(
        "kvasir-vqa-x1", "Kvasir-VQA-x1", "CC BY-NC 4.0", "https://creativecommons.org/licenses/by-nc/4.0/",
        "https://github.com/ENDObenchmark/Kvasir-VQA-x1", "generation_source", False, True, "Kvasir-VQA-x1 attribution required; non-commercial use.",
    ),
    "endobench": DatasetPolicy(
        "endobench", "EndoBench", "CC BY-SA 3.0", "https://creativecommons.org/licenses/by-sa/3.0/",
        "https://github.com/medAI-NEU/EndoBench", "benchmark_only", False, False, "Evaluation-only; never use as Tutor/RAG/Factory input.",
    ),
}


LOCAL_DATASET_DIRS = {
    "kvasir-vqa": "Kvasir-VQA",
    "kvasir-vqa-x1": "Kvasir-VQA-x1",
    "endobench": "EndoBench",
}


def dataset_policy(dataset_id: str) -> DatasetPolicy:
    try:
        return DATASET_POLICIES[dataset_id]
    except KeyError as exc:
        raise ValueError(f"Unknown dataset policy: {dataset_id}") from exc


def local_dataset_root(dataset_id: str) -> Path:
    try:
        return (LOCAL_VQA_ROOT / LOCAL_DATASET_DIRS[dataset_id]).resolve()
    except KeyError as exc:
        raise ValueError(f"Local asset delivery is not enabled for: {dataset_id}") from exc


def resolve_local_asset(dataset_id: str, relative_path: str) -> Path:
    """Resolve one local image without allowing absolute paths or traversal."""

    root = local_dataset_root(dataset_id)
    candidate = (root / relative_path.replace("\\", "/")).resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError("asset path escapes the configured dataset root")
    if not candidate.is_file():
        raise FileNotFoundError(relative_path)
    if candidate.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
        raise ValueError("only image assets are available through this route")
    return candidate


def tutor_namespace_allowed(namespace: str) -> bool:
    return namespace in TUTOR_NAMESPACES


def source_can_enter_tutor(*, business_usage: str, license_gate_status: str, ai_ingestion_allowed: bool) -> bool:
    return (
        business_usage != "benchmark_only"
        and business_usage != "excluded"
        and license_gate_status in {"allow", "allow_noncommercial"}
        and ai_ingestion_allowed
    )
