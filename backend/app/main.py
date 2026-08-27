from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import APP_NAME
from app.db.bootstrap import initialize_database
from app.routers.banks import router as stage1_banks_router
from app.routers.evaluation import router as stage1_evaluation_router
from app.routers.practice import canonical_router as stage1_practice_router
from app.routers.practice import legacy_router as stage1_practice_compat_router
from app.routers.tutor import router as stage1_tutor_router
from app.routers.tutor_agent import router as stage2_tutor_router
from app.routers.api import router

app = FastAPI(
    title="消化内镜研修与模型评测平台",
    description="面向消化内镜教学研修、报告草稿辅助和模型评测演示的本机服务。",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
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
app.include_router(stage1_tutor_router)
app.include_router(stage2_tutor_router)
app.include_router(stage1_evaluation_router)
app.include_router(router)


@app.on_event("startup")
def startup_database() -> None:
    initialize_database()


@app.get("/")
def root() -> dict[str, str]:
    return {"service": APP_NAME, "status": "ok", "docs": "/docs"}
