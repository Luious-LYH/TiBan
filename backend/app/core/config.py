import ipaddress
import os
import urllib.parse
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
