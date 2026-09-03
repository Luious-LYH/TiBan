"""Dramatiq actors for non-Factory derived work."""

from __future__ import annotations

import os

import dramatiq
from dramatiq.brokers.redis import RedisBroker

broker = RedisBroker(url=os.getenv("REDIS_URL", "redis://127.0.0.1:56379/0"))
dramatiq.set_broker(broker)


@dramatiq.actor(max_retries=2, time_limit=180_000)
def process_knowledge_index_actor(job_id: str) -> dict[str, object]:
    from app.services.knowledge_service import knowledge_service

    return knowledge_service.process_index_job(job_id)


@dramatiq.actor(max_retries=2, time_limit=120_000)
def process_memory_reflection_actor(job_id: str) -> dict[str, object]:
    from app.services.memory_reflection_service import memory_reflection_service

    return memory_reflection_service.process(job_id)


@dramatiq.actor(max_retries=1, time_limit=900_000)
def rebuild_vector_indexes_actor(job_id: str) -> dict[str, object]:
    from app.services.runtime_settings_service import runtime_settings_service

    return runtime_settings_service.process_index_rebuild(job_id)
