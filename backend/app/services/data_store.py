import json
import shutil
import time
from uuid import uuid4
from pathlib import Path
from typing import Any

from app.core.config import DATA_DIR, RUNTIME_DATA_DIR


MUTABLE_DATA_FILES = {
    "audit_logs.json",
    "learner_profile.json",
    "model_admission_state.json",
    "models.json",
    "portfolio_study_state.json",
}


def data_path(name: str, *, for_write: bool = False) -> Path:
    """Resolve mutable demo state outside the tracked seed-data directory."""
    seed_path = DATA_DIR / name
    if name not in MUTABLE_DATA_FILES:
        return seed_path
    runtime_path = RUNTIME_DATA_DIR / name
    if not runtime_path.exists():
        RUNTIME_DATA_DIR.mkdir(parents=True, exist_ok=True)
        if seed_path.exists():
            shutil.copy2(seed_path, runtime_path)
        elif for_write:
            runtime_path.write_text("{}", encoding="utf-8")
    return runtime_path


def reset_runtime_data() -> list[str]:
    """Restore deterministic demo state from version-controlled seeds."""
    RUNTIME_DATA_DIR.mkdir(parents=True, exist_ok=True)
    restored: list[str] = []
    for name in sorted(MUTABLE_DATA_FILES):
        seed_path = DATA_DIR / name
        runtime_path = RUNTIME_DATA_DIR / name
        if seed_path.exists():
            shutil.copy2(seed_path, runtime_path)
            restored.append(name)
        elif runtime_path.exists():
            runtime_path.unlink()
            restored.append(name)
    return restored


def read_json(name: str) -> Any:
    path = data_path(name)
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(name: str, payload: Any) -> None:
    path = data_path(name, for_write=True)
    tmp = path.with_name(f"{path.name}.{uuid4().hex}.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    for attempt in range(3):
        try:
            tmp.replace(path)
            return
        except PermissionError:
            if attempt == 2:
                raise
            time.sleep(0.05 * (attempt + 1))
