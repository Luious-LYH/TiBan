from __future__ import annotations

import os

import dramatiq
from dramatiq.brokers.redis import RedisBroker

from app.services.factory_service import process_factory_job


broker = RedisBroker(url=os.getenv("REDIS_URL", "redis://127.0.0.1:56379/0"))
dramatiq.set_broker(broker)


@dramatiq.actor(max_retries=1, time_limit=120_000)
def process_factory_job_actor(job_id: str) -> dict[str, object]:
    return process_factory_job(job_id)
