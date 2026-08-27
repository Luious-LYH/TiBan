from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from app.core.config import SAFETY_NOTICE
from app.schemas import EvaluationArtifactResponse


router = APIRouter(prefix="/api/v3/evaluation", tags=["stage1-evaluation"])
ARTIFACT_PATH = Path(__file__).resolve().parents[2] / ".." / "artifacts" / "eval" / "latest.json"


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
        "created_at": payload.get("created_at"),
        "notice": "离线确定性 artifact；不代表真实候选模型或临床性能。",
        "safety_notice": SAFETY_NOTICE,
    }


@router.get("/latest", response_model=EvaluationArtifactResponse)
def latest_evaluation() -> dict[str, Any]:
    return _artifact()
