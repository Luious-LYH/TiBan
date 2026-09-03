from __future__ import annotations

import json
import os
from pathlib import Path

import dramatiq

from app.services.factory_service import process_factory_job
from app.services.rag_service import rag_service
from app.workers.broker import broker


def _prewarm_embedding_if_configured() -> None:
    """Make Factory readiness mean the real FastEmbed path is already warm.

    The flag is Compose-owned so importing the actor in unit tests never
    downloads or initializes a model. A prewarm failure is recorded as
    degraded; broker/actor readiness is separate and remains usable for
    retryable queue work.
    """

    if os.getenv("FACTORY_EMBEDDING_PREWARM", "false").strip().lower() not in {"1", "true", "yes", "on"}:
        return
    ready_file = Path(os.getenv("FACTORY_WORKER_READY_FILE", "/tmp/factory-worker-ready"))
    marker_file = Path(os.getenv("FACTORY_EMBEDDING_PREWARM_FILE", f"{ready_file}.embedding"))
    ready_file.parent.mkdir(parents=True, exist_ok=True)
    marker_file.parent.mkdir(parents=True, exist_ok=True)
    lock_file = marker_file.with_name(f"{marker_file.name}.lock")

    # Dramatiq imports this module in every worker process.  A fresh cache
    # must be warmed once, not once per process: concurrent FastEmbed
    # downloads made cold start slower and could race over the same cache.
    try:
        import fcntl
    except ImportError:  # pragma: no cover - the production worker is Linux
        fcntl = None

    with lock_file.open("a+", encoding="utf-8") as handle:
        if fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            if marker_file.exists():
                return
            try:
                details = rag_service.prewarm()
                marker_file.write_text(json.dumps({"status": "ready", **details}, ensure_ascii=False), encoding="utf-8")
                print(f"factory embedding prewarm complete: {details['model']} in {details['elapsed_ms']}ms", flush=True)
            except Exception as exc:
                marker_file.write_text(json.dumps({"status": "degraded", "error": type(exc).__name__}, ensure_ascii=False), encoding="utf-8")
                print(f"factory embedding prewarm degraded: {type(exc).__name__}", flush=True)
        finally:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _write_worker_ready() -> None:
    """Mark broker and actor import readiness independently of prewarm."""

    ready_file = Path(os.getenv("FACTORY_WORKER_READY_FILE", "/tmp/factory-worker-ready"))
    ready_file.parent.mkdir(parents=True, exist_ok=True)
    ready_file.write_text("broker_and_actors_ready\n", encoding="utf-8")


_write_worker_ready()
_prewarm_embedding_if_configured()


@dramatiq.actor(max_retries=1, time_limit=120_000)
def process_factory_job_actor(job_id: str) -> dict[str, object]:
    return process_factory_job(job_id)
