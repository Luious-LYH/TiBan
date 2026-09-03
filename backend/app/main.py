from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import ALLOWED_ORIGINS, APP_NAME, APP_VERSION
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
    knowledge_service.retire_legacy_system_corpus()
    # Instance-level Settings are intentionally runtime scoped; an API service
    # restart restores the Compose/.env defaults instead of retaining a key.
    from app.services.runtime_settings_service import runtime_settings_service
    runtime_settings_service.reset_shared()
    # Requeue only durable pending evidence; a browser-close signal is never
    # relied upon as the sole trigger for Reflection.
    from app.services.memory_reflection_service import memory_reflection_service
    memory_reflection_service.reconcile_inactive(limit=12)


@app.get("/")
def root() -> dict[str, str]:
    return {"service": APP_NAME, "status": "ok", "version": APP_VERSION, "docs": "/docs"}
