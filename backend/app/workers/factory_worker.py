from __future__ import annotations

import os
from pathlib import Path

import dramatiq
from dramatiq.brokers.redis import RedisBroker

from app.services.factory_service import process_factory_job
from app.services.rag_service import rag_service


broker = RedisBroker(url=os.getenv("REDIS_URL", "redis://127.0.0.1:56379/0"))
dramatiq.set_broker(broker)


def _prewarm_embedding_if_configured() -> None:
    """Make Factory readiness mean the real FastEmbed path is already warm.

    The flag is Compose-owned so importing the actor in unit tests never
    downloads or initializes a model.  Failure is intentionally fatal: a
    worker that cannot warm its embedding dependency must not accept jobs and
    turn the first user upload into a stale actor timeout.
    """

    if os.getenv("FACTORY_EMBEDDING_PREWARM", "false").strip().lower() not in {"1", "true", "yes", "on"}:
        return
    ready_file = Path(os.getenv("FACTORY_WORKER_READY_FILE", "/tmp/factory-worker-ready"))
    ready_file.parent.mkdir(parents=True, exist_ok=True)
    lock_file = ready_file.with_name(f"{ready_file.name}.lock")

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
            if ready_file.exists():
                return
            details = rag_service.prewarm()
            ready_file.write_text(f"{details['model']} {details['elapsed_ms']}ms\n", encoding="utf-8")
            print(f"factory embedding prewarm complete: {details['model']} in {details['elapsed_ms']}ms", flush=True)
        finally:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


_prewarm_embedding_if_configured()


@dramatiq.actor(max_retries=1, time_limit=120_000)
def process_factory_job_actor(job_id: str) -> dict[str, object]:
    return process_factory_job(job_id)
