import ipaddress
import os
import urllib.parse
from pathlib import Path

from dotenv import load_dotenv

APP_NAME = "消化内镜研修与模型评测平台"
SAFETY_NOTICE = "仅供教学研修或医生复核前辅助，不作为独立诊断依据。"
DEMO_LEARNER_ID = "demo_learner"

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
BACKEND_DIR = BASE_DIR.parent
PROJECT_DIR = BACKEND_DIR.parent
UPLOAD_DIR = BACKEND_DIR / "runtime" / "uploads"
RUNTIME_DATA_DIR = BACKEND_DIR / "runtime" / "data"

load_dotenv(PROJECT_DIR / ".env")
load_dotenv(BACKEND_DIR / ".env")

def _env_first(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name)
        if value is not None and value.strip():
            return value.strip()
    return default


LOCAL_VQA_ROOT = Path(_env_first("ENDO_LOCAL_VQA_ROOT", default=r"E:\2.Projects\ARIS\VQA\data"))


DATABASE_URL = _env_first(
    "ENDO_DATABASE_URL",
    "DATABASE_URL",
    default=f"sqlite:///{(RUNTIME_DATA_DIR / 'stage1.sqlite3').as_posix()}",
)


LLM_PROVIDER = _env_first("LLM_PROVIDER", "OPENAI_PROVIDER", default="openai_compatible")
LLM_BASE_URL = _env_first("LLM_BASE_URL", "OPENAI_BASE_URL").rstrip("/")
LLM_API_KEY = _env_first("LLM_API_KEY", "OPENAI_API_KEY")
LLM_MODEL = _env_first("LLM_MODEL", "OPENAI_MODEL", default="gpt-5.6-sol")
_reasoning_effort_raw = _env_first("model_reasoning_effort", "LLM_MODEL_REASONING_EFFORT", "MODEL_REASONING_EFFORT")
LLM_MODEL_REASONING_EFFORT = {
    "低": "low",
    "中": "medium",
    "高": "high",
}.get(_reasoning_effort_raw.strip().lower(), _reasoning_effort_raw.strip().lower())
LLM_FALLBACK_PROVIDER = _env_first("LLM_FALLBACK_PROVIDER", default="openai_compatible")
LLM_FALLBACK_BASE_URL = _env_first("LLM_FALLBACK_BASE_URL").rstrip("/")
LLM_FALLBACK_API_KEY = _env_first("LLM_FALLBACK_API_KEY")
LLM_FALLBACK_MODEL = _env_first("LLM_FALLBACK_MODEL", default=LLM_MODEL)
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "25"))
FACTORY_PROVIDER_ENABLED = _env_first("FACTORY_PROVIDER_ENABLED").lower() == "true"
# Private-network Providers remain blocked by default.  A developer running a
# deliberately local/LAN OpenAI-compatible gateway may opt in for the current
# process; this flag is intentionally not enabled by any checked-in config.
LLM_PROVIDER_ALLOW_PRIVATE_NETWORK = _env_first("LLM_PROVIDER_ALLOW_PRIVATE_NETWORK").lower() == "true"


def _normalize_allowlist_host(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        return ""
    if "://" in cleaned:
        try:
            hostname = urllib.parse.urlsplit(cleaned).hostname or ""
        except ValueError:
            return ""
    else:
        host_part = cleaned.split("/", 1)[0]
        if host_part.startswith("[") and "]" in host_part:
            hostname = host_part[1:].split("]", 1)[0]
        elif host_part.count(":") == 1 and host_part.rsplit(":", 1)[1].isdigit():
            hostname = host_part.rsplit(":", 1)[0]
        else:
            hostname = host_part
    normalized = hostname.strip().strip("[]").lower().rstrip(".")
    try:
        ipaddress.ip_address(normalized)
        return ""
    except ValueError:
        return normalized


_private_host_allowlist_raw = os.getenv(
    "LLM_PROVIDER_PRIVATE_HOST_ALLOWLIST",
    os.getenv("LLM_ALLOWED_PRIVATE_HOSTS", ""),
)
LLM_PROVIDER_PRIVATE_HOST_ALLOWLIST = tuple(
    sorted(
        {
            normalized
            for item in _private_host_allowlist_raw.split(",")
            if (normalized := _normalize_allowlist_host(item))
        },
    ),
)
