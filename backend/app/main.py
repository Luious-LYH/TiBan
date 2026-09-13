from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from threading import Thread

from app.core.config import ALLOWED_ORIGINS, APP_NAME, APP_VERSION, DEFAULT_LOCAL_MULTIMODAL_TEXTBOOK_PATH, KNOWLEDGE_EXTERNAL_GUIDES_AUTO_SYNC
from app.db.bootstrap import initialize_database
from app.routers.banks import router as stage1_banks_router
from app.routers.evaluation import router as stage1_evaluation_router
from app.routers.practice import canonical_router as stage1_practice_router
from app.routers.practice import legacy_router as stage1_practice_compat_router
from app.routers.tutor_agent import router as stage2_tutor_router
from app.routers.learning import router as stage2_learning_router
from app.routers.review import router as v31_review_router
from app.routers.knowledge import router as v31_knowledge_router
from app.routers.mentor import router as v32_mentor_router
from app.routers.factory import router as stage2_factory_router
from app.routers.assets import router as stage25_assets_router
from app.routers.domains import router as domains_router
from app.routers.settings import router as settings_router
from app.routers.api import router

app = FastAPI(
    title="TiBan 学习与模型评测平台",
    description="Agent-native 自适应题库与学习工作台，支持按领域配置题库、学习、复习与智能辅导。",
    version=APP_VERSION,
)

logger = logging.getLogger(__name__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(ALLOWED_ORIGINS),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Stage 1 canonical routers are registered before the legacy portfolio router so
# the main product flow uses the new contracts while old developer pages remain
# available during migration.
app.include_router(stage1_banks_router)
app.include_router(stage1_practice_router)
app.include_router(stage1_practice_compat_router)
app.include_router(stage2_tutor_router)
app.include_router(stage2_learning_router)
app.include_router(v31_review_router)
app.include_router(v31_knowledge_router)
app.include_router(v32_mentor_router)
app.include_router(stage2_factory_router)
app.include_router(stage25_assets_router)
app.include_router(domains_router)
app.include_router(settings_router)
app.include_router(stage1_evaluation_router)
app.include_router(router)


@app.on_event("startup")
def startup_database() -> None:
    initialize_database()
    # Retire V3.1-excluded generated corpora in the relational eligibility
    # graph only. This is deliberately independent from Qdrant availability.
    from app.services.knowledge_service import knowledge_service
    # Keep each optional corpus independent.  A stopped Qdrant must not abort
    # local-file registration or prevent the qbank explanation projection from
    # being repaired on the next startup.
    try:
        # Register the bundled sample before serving the first request, but do
        # not make the first-run API health check wait for parsing, embeddings,
        # image extraction, or graph construction.
        if knowledge_service.ensure_default_multimodal_guide(index=False) is None:
            logger.warning("bundled multimodal knowledge sample is unavailable")
    except Exception as exc:
        logger.warning("bundled multimodal knowledge sample could not be prepared: %s", type(exc).__name__)
    try:
        # Registration is safe and idempotent; indexing the external directory
        # is an explicit action and remains disabled by default.
        sync_result = knowledge_service.sync_local_guidelines(enqueue=KNOWLEDGE_EXTERNAL_GUIDES_AUTO_SYNC)
        if sync_result.get("directory_found") and (sync_result.get("created") or sync_result.get("queued")):
            logger.info(
                "local clinical-guideline knowledge registration: created=%s pending=%s ignored=%s",
                sync_result.get("created"), sync_result.get("queued"),
                len(sync_result.get("ignored") or []),
            )
    except Exception as exc:
        logger.warning("local clinical-guideline registration failed: %s", type(exc).__name__)
    try:
        quarantined = knowledge_service.quarantine_legacy_guideline_indexes()
        if quarantined:
            logger.info("withheld %s legacy clinical-guide indexes pending structured processing", quarantined)
    except Exception as exc:
        logger.warning("legacy clinical-guideline quarantine failed: %s", type(exc).__name__)
    try:
        # A single deliberately supplied textbook is a learner-owned root
        # document. It is not part of the clinical-guideline directory.
        if DEFAULT_LOCAL_MULTIMODAL_TEXTBOOK_PATH.is_file():
            knowledge_service.register_local_source(
                DEFAULT_LOCAL_MULTIMODAL_TEXTBOOK_PATH,
                title="《医学影像学》教学材料",
                folder_id=None,
                attribution="本机导入资料 · 《医学影像学》教材",
                enqueue=False,
            )
    except Exception as exc:
        logger.warning("local textbook registration failed: %s", type(exc).__name__)
    knowledge_service.retire_legacy_system_corpus()
    # Instance-level Settings are intentionally runtime scoped; an API service
    # restart restores the Compose/.env defaults instead of retaining a key.
    from app.services.runtime_settings_service import runtime_settings_service
    runtime_settings_service.reset_shared()
    # Requeue only durable pending evidence; a browser-close signal is never
    # relied upon as the sole trigger for Reflection.
    from app.services.memory_reflection_service import memory_reflection_service
    memory_reflection_service.reconcile_inactive(limit=12)

    # Maintenance must never hold the ASGI lifespan open.  In particular, the
    # first CMExam/qbank projection and the bundled multimodal sample can take
    # materially longer than a browser health check on a local machine.  The
    # work is idempotent and each corpus has its own error boundary, so a
    # failed optional task cannot make the API appear down.
    def finish_startup_maintenance() -> None:
        try:
            if knowledge_service.ensure_default_multimodal_guide() is not None:
                logger.info("bundled multimodal knowledge sample maintenance finished")
        except Exception as exc:
            logger.warning("bundled multimodal knowledge maintenance failed: %s", type(exc).__name__)
        try:
            qbank_sync = knowledge_service.sync_published_question_explanations()
            if qbank_sync.get("synced"):
                logger.info("published question-bank explanations synchronized: %s", qbank_sync.get("synced"))
        except Exception as exc:
            logger.warning("published question-bank explanation sync failed: %s", type(exc).__name__)
        try:
            requeued = knowledge_service.requeue_pending_index_jobs()
            if requeued:
                logger.info("re-dispatched %s pending knowledge-index jobs", requeued)
        except Exception as exc:
            logger.warning("pending knowledge-index reconciliation failed: %s", type(exc).__name__)

    Thread(target=finish_startup_maintenance, name="tiban-knowledge-maintenance", daemon=True).start()


@app.get("/")
def root() -> dict[str, str]:
    return {"service": APP_NAME, "status": "ok", "version": APP_VERSION, "docs": "/docs"}
