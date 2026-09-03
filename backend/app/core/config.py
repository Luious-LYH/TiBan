import ipaddress
import os
import urllib.parse
from pathlib import Path

from dotenv import load_dotenv

APP_NAME = "TiBan 学习与模型评测平台"
APP_VERSION = "3.2.0"
SAFETY_NOTICE = "仅供教学研修或医生复核前辅助，不作为独立诊断依据。"
DEMO_LEARNER_ID = "demo_learner"

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
BACKEND_DIR = BASE_DIR.parent
PROJECT_DIR = BACKEND_DIR.parent
UPLOAD_DIR = BACKEND_DIR / "runtime" / "uploads"
RUNTIME_DATA_DIR = BACKEND_DIR / "runtime" / "data"

# A clean clone deliberately excludes mutable runtime state.  Create the
# local-only directories before constructing the default SQLite URL so a fresh
# checkout can run the application and its regression suite without relying on
# a developer's existing database folder.
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
RUNTIME_DATA_DIR.mkdir(parents=True, exist_ok=True)

load_dotenv(PROJECT_DIR / ".env")
load_dotenv(BACKEND_DIR / ".env")

def _env_first(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name)
        if value is not None and value.strip():
            return value.strip()
    return default


LOCAL_VQA_ROOT = Path(_env_first("ENDO_LOCAL_VQA_ROOT", default=str(PROJECT_DIR / "data" / "vqa")))
ARC_EASY_ROOT = Path(_env_first("TIBAN_ARC_EASY_ROOT", default=str(PROJECT_DIR / "data" / "external" / "arc_easy")))
LOCAL_PROJECT_DATA_ROOT = Path(
    _env_first("ENDO_PROJECT_DATA_ROOT", default=str(PROJECT_DIR / "data"))
)


DATABASE_URL = _env_first(
    "ENDO_DATABASE_URL",
    "DATABASE_URL",
    default=f"sqlite:///{(RUNTIME_DATA_DIR / 'stage1.sqlite3').as_posix()}",
)


# Public deployments use a provider chain.  Credentials remain environment-only:
# Cloudflare Workers AI -> OpenRouter -> BigModel.  The generic LLM_* names
# still take precedence so an instance owner can deliberately override it.
CLOUDFLARE_ACCOUNT_ID = _env_first("CLOUDFLARE_ACCOUNT_ID")
_cloudflare_ai_base_url = (
    f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/v1"
    if CLOUDFLARE_ACCOUNT_ID
    else ""
)
LLM_PROVIDER = _env_first("LLM_PROVIDER", "OPENAI_PROVIDER", default="cloudflare_workers_ai")
LLM_BASE_URL = _env_first("LLM_BASE_URL", "CLOUDFLARE_AI_BASE_URL", "OPENAI_BASE_URL", default=_cloudflare_ai_base_url).rstrip("/")
LLM_API_KEY = _env_first("LLM_API_KEY", "CLOUDFLARE_API_TOKEN", "OPENAI_API_KEY")
LLM_MODEL = _env_first("LLM_MODEL", "CLOUDFLARE_AI_MODEL", "OPENAI_MODEL", default="@cf/qwen/qwen3-30b-a3b-fp8")
_reasoning_effort_raw = _env_first("model_reasoning_effort", "LLM_MODEL_REASONING_EFFORT", "MODEL_REASONING_EFFORT")
LLM_MODEL_REASONING_EFFORT = {
    "低": "low",
    "中": "medium",
    "高": "high",
}.get(_reasoning_effort_raw.strip().lower(), _reasoning_effort_raw.strip().lower())
LLM_FALLBACK_PROVIDER = _env_first("LLM_FALLBACK_PROVIDER", default="openrouter")
LLM_FALLBACK_BASE_URL = _env_first(
    "LLM_FALLBACK_BASE_URL", "OPENROUTER_BASE_URL", default="https://openrouter.ai/api/v1"
).rstrip("/")
LLM_FALLBACK_API_KEY = _env_first("LLM_FALLBACK_API_KEY", "OPENROUTER_API_KEY")
LLM_FALLBACK_MODEL = _env_first("LLM_FALLBACK_MODEL", "OPENROUTER_MODEL", default="minimax/minimax-m3:free")
LLM_FINAL_FALLBACK_PROVIDER = _env_first("LLM_FINAL_FALLBACK_PROVIDER", default="bigmodel")
LLM_FINAL_FALLBACK_BASE_URL = _env_first(
    "LLM_FINAL_FALLBACK_BASE_URL", "BIGMODEL_BASE_URL", default="https://open.bigmodel.cn/api/paas/v4"
).rstrip("/")
LLM_FINAL_FALLBACK_API_KEY = _env_first("LLM_FINAL_FALLBACK_API_KEY", "BIGMODEL_API_KEY")
LLM_FINAL_FALLBACK_MODEL = _env_first("LLM_FINAL_FALLBACK_MODEL", "BIGMODEL_MODEL", default="GLM-5.3-Flash")
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "25"))
FACTORY_PROVIDER_ENABLED = _env_first("FACTORY_PROVIDER_ENABLED").lower() == "true"

# Vector inference is an instance concern, never a browser-owned setting.
# Online/demo deployments use a SiliconFlow-compatible endpoint by default;
# a self-hosted installation can deliberately choose the lazy local fallback.
EMBEDDING_MODE = _env_first("EMBEDDING_MODE", default="api").lower()
EMBEDDING_PROVIDER = _env_first("EMBEDDING_PROVIDER", default="siliconflow")
EMBEDDING_BASE_URL = _env_first(
    "EMBEDDING_BASE_URL",
    "SILICONFLOW_BASE_URL",
    default="https://api.siliconflow.cn/v1",
).rstrip("/")
EMBEDDING_API_KEY = _env_first("EMBEDDING_API_KEY", "SILICONFLOW_API_KEY")
EMBEDDING_MODEL = _env_first("EMBEDDING_MODEL", "SILICONFLOW_EMBEDDING_MODEL", default="BAAI/bge-m3")
EMBEDDING_LOCAL_MODEL = _env_first("EMBEDDING_LOCAL_MODEL", default="BAAI/bge-small-zh-v1.5")
EMBEDDING_TIMEOUT_SECONDS = float(_env_first("EMBEDDING_TIMEOUT_SECONDS", default="30"))
RERANKER_MODE = _env_first("RERANKER_MODE", default="api").lower()
RERANKER_PROVIDER = _env_first("RERANKER_PROVIDER", default="siliconflow")
RERANKER_BASE_URL = _env_first("RERANKER_BASE_URL", "SILICONFLOW_BASE_URL", default=EMBEDDING_BASE_URL).rstrip("/")
RERANKER_API_KEY = _env_first("RERANKER_API_KEY", "SILICONFLOW_API_KEY", "EMBEDDING_API_KEY")
RERANKER_MODEL = _env_first("RERANKER_MODEL", default="BAAI/bge-reranker-v2-m3")
# Large third-party QBanks are optional local import-validation fixtures, not
# a redistributed product catalogue. Keep their bootstrap opt-in; public
# clean-start and user-owned upload flows use the compact teaching seed.
DEMO_QBANK_BOOTSTRAP = _env_first("ENDO_DEMO_QBANK_BOOTSTRAP", default="false").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
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
