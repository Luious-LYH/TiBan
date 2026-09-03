"""Dramatiq actors for non-Factory derived work."""

from __future__ import annotations

import dramatiq

from app.workers.broker import broker


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


@dramatiq.actor(max_retries=1, time_limit=1_800_000)
def process_evaluation_lab_actor(run_id: str) -> dict[str, object]:
    """Run one frozen Evaluation Lab candidate through the configured runtime."""
    from app.services.evaluation_lab_service import evaluation_lab_service

    return evaluation_lab_service.process_run(run_id)
