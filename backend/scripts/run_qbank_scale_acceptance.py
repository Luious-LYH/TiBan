"""Run the Stage 3 QBank scale acceptance in a dedicated PostgreSQL database.

Usage (PowerShell):
  $env:ENDO_DATABASE_URL='postgresql+psycopg://USER:PASSWORD@127.0.0.1:55432/endotutor_stage3_scale'
  python scripts/run_qbank_scale_acceptance.py --prepare-db

The script rejects any database name other than ``endotutor_stage3_scale`` and
never deletes, truncates or modifies the demo database.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
from pathlib import Path
from statistics import median
from time import perf_counter

import psycopg
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import make_url


BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import DATABASE_URL
from app.db.database import SessionLocal
from app.main import app
from app.services.qbank_import_service import import_cmexam_scale


SCALE_DB_NAME = "endotutor_stage3_scale"


def _percentile(values: list[float], percentile: float) -> float:
    return sorted(values)[max(0, math.ceil(len(values) * percentile) - 1)]


def _assert_isolated_database() -> None:
    url = make_url(DATABASE_URL)
    if url.get_backend_name() != "postgresql" or url.database != SCALE_DB_NAME:
        raise RuntimeError(f"QBank scale acceptance requires isolated PostgreSQL database {SCALE_DB_NAME!r}")


def _prepare_database() -> None:
    _assert_isolated_database()
    url = make_url(DATABASE_URL)
    admin = url.set(database="postgres")
    admin_dsn = admin.render_as_string(hide_password=False).replace("postgresql+psycopg://", "postgresql://", 1)
    with psycopg.connect(admin_dsn, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (SCALE_DB_NAME,))
            if cursor.fetchone() is None:
                cursor.execute(f'CREATE DATABASE "{SCALE_DB_NAME}"')
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND_ROOT, check=True, env=os.environ.copy())


def _measure(client: TestClient, path: str, params: dict[str, object] | None = None, count: int = 20) -> tuple[list[float], list[dict[str, object]]]:
    latencies: list[float] = []
    payloads: list[dict[str, object]] = []
    for _ in range(count):
        started = perf_counter()
        response = client.get(path, params=params)
        elapsed = (perf_counter() - started) * 1000
        if response.status_code != 200:
            raise RuntimeError(f"API check failed for {path}: {response.status_code} {response.text[:240]}")
        latencies.append(elapsed)
        payloads.append(response.json())
    return latencies, payloads


def _latency_summary(values: list[float]) -> dict[str, float]:
    return {"p50_ms": round(median(values), 2), "p95_ms": round(_percentile(values, 0.95), 2)}


def main(*, prepare_db: bool) -> None:
    if prepare_db:
        _prepare_database()
    _assert_isolated_database()
    started = perf_counter()
    imported = import_cmexam_scale(batch_size=1000)
    import_ms = (perf_counter() - started) * 1000
    if int(imported["imported"]) < 50_000:
        raise RuntimeError(f"scale acceptance requires at least 50k valid questions, imported={imported['imported']}")

    with SessionLocal() as session:
        database_size_bytes = int(session.execute(text("SELECT pg_database_size(current_database())")).scalar_one())

    with TestClient(app) as client:
        first_page_latencies, first_page_payloads = _measure(
            client,
            "/api/v3/practice/questions",
            {"bank_id": imported["bank_id"], "limit": 50, "offset": 0},
        )
        second_page_latencies, second_page_payloads = _measure(
            client,
            "/api/v3/practice/questions",
            {"bank_id": imported["bank_id"], "limit": 50, "offset": 50},
        )
        first_page = first_page_payloads[-1]["items"]
        second_page = second_page_payloads[-1]["items"]
        if len(first_page) != 50 or len(second_page) != 50 or {item["id"] for item in first_page} & {item["id"] for item in second_page}:
            raise RuntimeError("pagination returned an incomplete or overlapping page")
        subject = str(next(item["subject"] for item in first_page if item.get("subject")))
        filter_latencies, filter_payloads = _measure(
            client,
            "/api/v3/practice/questions",
            {"bank_id": imported["bank_id"], "subject": subject, "limit": 50},
        )
        if not filter_payloads[-1]["items"] or not all(item.get("subject") == subject for item in filter_payloads[-1]["items"]):
            raise RuntimeError("subject filter is not correctly scoped")

        session_latencies: list[float] = []
        stable_selection: list[str] | None = None
        for seed in range(10, 20):
            session_started = perf_counter()
            response = client.post("/api/v3/practice/sessions", json={
                "learner_id": "stage3-scale-learner",
                "bank_id": imported["bank_id"],
                "mode": "study",
                "question_count": 50,
                "shuffle_seed": seed,
            })
            session_latencies.append((perf_counter() - session_started) * 1000)
            if response.status_code != 200:
                raise RuntimeError(f"session creation failed: {response.status_code} {response.text[:240]}")
            payload = response.json()
            if payload["question_count"] != 50 or len(set(payload["question_ids"])) != 50:
                raise RuntimeError("50-question session did not retain a unique random sample")
            if seed == 10:
                stable_selection = list(payload["question_ids"])
                session_id = payload["session_id"]

        replay = client.post("/api/v3/practice/sessions", json={
            "learner_id": "stage3-scale-replay",
            "bank_id": imported["bank_id"],
            "mode": "study",
            "question_count": 50,
            "shuffle_seed": 10,
        })
        if replay.status_code != 200 or replay.json()["question_ids"] != stable_selection:
            raise RuntimeError("seeded session sampling is not reproducible")

        question = client.get(f"/api/v3/practice/questions/{stable_selection[0]}").json()["item"]
        submitted = client.post("/api/v3/practice/submit", json={
            "learner_id": "stage3-scale-learner",
            "session_id": session_id,
            "question_id": question["id"],
            "selected_answer": "invalid-option-for-scale-acceptance",
            "mode": "study",
        })
        if submitted.status_code != 200:
            raise RuntimeError(f"session attempt failed: {submitted.status_code} {submitted.text[:240]}")
        navigator = client.get(f"/api/v3/practice/sessions/{session_id}").json()
        unused = client.get(f"/api/v3/practice/sessions/{session_id}", params={"state": "unanswered"}).json()
        incorrect = client.get(f"/api/v3/practice/sessions/{session_id}", params={"state": "incorrect"}).json()
        if len(navigator["items"]) != 50 or len(unused["items"]) != 49 or len(incorrect["items"]) != 1:
            raise RuntimeError("navigator state or unused/incorrect filters are inconsistent")

    artifact = {
        "artifact_version": "qbank-scale-acceptance-v1",
        "database": {"kind": "isolated_postgresql", "name": SCALE_DB_NAME, "size_bytes": database_size_bytes},
        "dataset": {"name": "CMExam", "role": "scale acceptance only", "demo_data_unchanged": True},
        "import": {**imported, "duration_ms": round(import_ms, 2)},
        "api_latency": {
            "pagination_page_1": _latency_summary(first_page_latencies),
            "pagination_page_2": _latency_summary(second_page_latencies),
            "subject_filter": _latency_summary(filter_latencies),
            "create_50_question_session": _latency_summary(session_latencies),
        },
        "functional_checks": {
            "pagination_non_overlapping": True,
            "subject_filter": subject,
            "seeded_random_sampling_reproducible": True,
            "session_question_count": 50,
            "unused_count_after_one_attempt": len(unused["items"]),
            "incorrect_count_after_one_invalid_attempt": len(incorrect["items"]),
            "navigator_state": [item["state"] for item in navigator["items"]],
        },
    }
    target = PROJECT_ROOT / "artifacts" / "qbank"
    target.mkdir(parents=True, exist_ok=True)
    (target / "qbank-scale-acceptance-v1.json").write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"imported": imported["imported"], "database_size_bytes": database_size_bytes, "artifact": "artifacts/qbank/qbank-scale-acceptance-v1.json"}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare-db", action="store_true", help="create the isolated acceptance database if absent, then run migrations")
    args = parser.parse_args()
    main(prepare_db=args.prepare_db)
