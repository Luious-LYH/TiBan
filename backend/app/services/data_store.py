import json
import time
from uuid import uuid4
from pathlib import Path
from typing import Any

from app.core.config import DATA_DIR


def read_json(name: str) -> Any:
    path = DATA_DIR / name
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(name: str, payload: Any) -> None:
    path = DATA_DIR / name
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
