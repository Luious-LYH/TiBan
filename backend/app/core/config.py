import os
from pathlib import Path

from dotenv import load_dotenv

APP_NAME = "endo-zhixun-agent-backend"
SAFETY_NOTICE = "仅供教学训练或医生审核前辅助，不作为独立诊断依据。"
DEMO_LEARNER_ID = "demo_learner"

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
BACKEND_DIR = BASE_DIR.parent
PROJECT_DIR = BACKEND_DIR.parent
UPLOAD_DIR = BACKEND_DIR / "runtime" / "uploads"

load_dotenv(PROJECT_DIR / ".env")
load_dotenv(BACKEND_DIR / ".env")

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "mock")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "").rstrip("/")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "25"))
