import argparse
import os
import subprocess
import sys
from pathlib import Path

from provider_smoke import (
    compact_admission_state,
    compact_audit,
    compact_provider_status,
    get_json,
    post_json,
    print_section,
    redact_provider_preview,
    resolve_backend,
)


ROOT = Path(__file__).resolve().parents[1]
ENV_KEYS = ("LLM_PROVIDER", "LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL", "LLM_TIMEOUT_SECONDS")
ENV_PATHS = (ROOT / ".env", ROOT / "backend/.env")


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def env_presence() -> dict[str, object]:
    files = []
    merged: dict[str, str] = {}
    for path in ENV_PATHS:
        values = parse_env_file(path)
        if values:
            merged.update(values)
        files.append(
            {
                "path": str(path.relative_to(ROOT)),
                "exists": path.exists(),
                "bytes": path.stat().st_size if path.exists() else 0,
                "keys_present": sorted(key for key in ENV_KEYS if key in values and bool(values[key])),
                "git_ignored": is_git_ignored(path),
            },
        )
    return {
        "files": files,
        "effective_keys_present": sorted(key for key in ENV_KEYS if merged.get(key)),
        "provider_declared": merged.get("LLM_PROVIDER", ""),
        "model_declared": merged.get("LLM_MODEL", ""),
        "base_url_present": bool(merged.get("LLM_BASE_URL")),
        "api_key_present": bool(merged.get("LLM_API_KEY")),
    }


def is_git_ignored(path: Path) -> bool:
    try:
        result = subprocess.run(
            ["git", "check-ignore", "-q", str(path.relative_to(ROOT))],
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return result.returncode == 0
    except OSError:
        return False


def next_actions(diagnostics: dict, env_status: dict[str, object], preflight_ok: bool) -> list[str]:
    actions: list[str] = []
    if not any(file["exists"] for file in env_status["files"]):  # type: ignore[index]
        actions.append("Copy backend/.env.example to backend/.env, then fill LLM_BASE_URL, LLM_API_KEY, LLM_PROVIDER and LLM_MODEL.")
    if not env_status.get("api_key_present"):
        actions.append("Keep the API key only in backend/.env or a local environment variable; do not type it during projected demos.")
    if env_status.get("base_url_present") and not diagnostics.get("base_url_configured"):
        actions.append("Restart the FastAPI backend after editing .env; config is read when the backend process starts.")
    if not preflight_ok:
        actions.append("Fix LLM_BASE_URL until Provider preflight is allowed; self-test is blocked before this.")
    if preflight_ok and diagnostics.get("provider_configured"):
        actions.append("Run: python scripts\\provider_doctor.py --self-test --include-image")
    if preflight_ok and not diagnostics.get("provider_configured"):
        actions.append("After configuring backend/.env and restarting FastAPI, re-run this doctor script.")
    return actions


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose ARIS Provider readiness without printing secrets or Provider hosts.")
    parser.add_argument("--backend", default=os.getenv("ARIS_BACKEND_URL", ""), help="Backend API base. Omit to auto-probe 8000 then 8001.")
    parser.add_argument("--self-test", action="store_true", help="Call Provider self-test using backend .env only; no key is sent from this CLI.")
    parser.add_argument("--include-image", action="store_true", help="Attach one public sample image in self-test.")
    parser.add_argument("--sample-id", default=os.getenv("ARIS_SMOKE_SAMPLE_ID", ""))
    parser.add_argument("--timeout", type=float, default=25.0)
    args = parser.parse_args()

    env_status = env_presence()
    print_section("Local .env status", env_status)

    api_base, health = resolve_backend(args.backend or None, args.timeout)
    print_section(
        "Backend health",
        {
            "backend_api_base": api_base,
            "status": health.get("status"),
            "version": health.get("version"),
            "provider_capabilities_present": all(
                capability in health.get("capabilities", [])
                for capability in ["provider_diagnostics", "provider_preflight", "provider_self_test", "provider_visual_self_test"]
            ),
        },
    )

    diagnostics = get_json(api_base, "/provider/diagnostics", args.timeout)
    diagnostics_public = {
        "ready_level": diagnostics.get("ready_level"),
        "provider_configured": diagnostics.get("provider_configured"),
        "provider_mode": diagnostics.get("provider_mode"),
        "provider": diagnostics.get("provider"),
        "model": diagnostics.get("model"),
        "base_url_configured": diagnostics.get("base_url_configured"),
        "api_key_configured": diagnostics.get("api_key_configured"),
        "missing": diagnostics.get("missing", []),
        "public_sample_count": diagnostics.get("public_sample_count"),
        "latest_self_test": compact_audit(diagnostics.get("latest_self_test")),
        "latest_admission": compact_audit(diagnostics.get("latest_admission")),
        "admission_state": compact_admission_state(diagnostics.get("admission_state")),
        "blocking_reason": diagnostics.get("blocking_reason"),
    }
    print_section("Backend Provider diagnostics", diagnostics_public)

    preflight = post_json(api_base, "/provider/preflight", {"api_base": ""}, args.timeout)
    preflight_public = {
        "ok": preflight.get("ok"),
        "safety_status": preflight.get("safety_status"),
        "mode": preflight.get("mode"),
        "normalized_preview": redact_provider_preview(preflight.get("normalized_preview")),
        "endpoint_paths": preflight.get("endpoint_paths", []),
        "blocked_reason": preflight.get("blocked_reason"),
        "request_sent": preflight.get("request_sent"),
        "key_persisted": preflight.get("key_persisted"),
        "warnings": preflight.get("warnings", []),
    }
    print_section("Backend .env preflight", preflight_public)

    preflight_ok = bool(preflight.get("ok"))
    if args.self_test:
        if not preflight_ok:
            print_section("Self-test skipped", {"reason": "backend .env Provider preflight is not allowed"})
            print_section("Next actions", {"items": next_actions(diagnostics, env_status, preflight_ok)})
            return 2
        if not diagnostics.get("provider_configured"):
            print_section("Self-test skipped", {"reason": "backend diagnostics says Provider is not configured"})
            print_section("Next actions", {"items": next_actions(diagnostics, env_status, preflight_ok)})
            return 3
        result = post_json(
            api_base,
            "/provider/self-test",
            {
                "provider_name": "Backend .env Provider",
                "api_base": "",
                "api_key": None,
                "model": None,
                "include_image": bool(args.include_image),
                "sample_id": args.sample_id or None,
            },
            args.timeout,
        )
        print_section(
            "Backend .env self-test",
            {
                "id": result.get("id"),
                "provider_called": result.get("provider_called"),
                "visual_probe": result.get("visual_probe"),
                "image_attached": result.get("image_attached"),
                "image_sample_id": result.get("image_sample_id"),
                "provider_status": compact_provider_status(result.get("provider_status")),
                "audit_logged": result.get("audit_logged"),
                "audit_log_id": result.get("audit_log_id"),
                "key_persisted": result.get("key_persisted"),
                "admission_state_updated": result.get("admission_state_updated"),
                "recommendation": result.get("recommendation"),
            },
        )
        print_section("Next actions", {"items": next_actions(diagnostics, env_status, preflight_ok)})
        return 0 if result.get("provider_called") else 4

    print_section("Next actions", {"items": next_actions(diagnostics, env_status, preflight_ok)})
    return 0 if preflight_ok or not diagnostics.get("provider_configured") else 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RuntimeError as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(130)
