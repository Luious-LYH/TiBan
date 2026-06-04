import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request


DEFAULT_BACKENDS = ("http://127.0.0.1:8000/api", "http://127.0.0.1:8001/api")

REQUIRED_CAPABILITIES = {
    "provider_diagnostics",
    "provider_evidence_ladder",
    "provider_preflight",
    "provider_request_preview",
    "report_upload_receipt",
    "provider_self_test",
    "provider_visual_self_test",
    "provider_self_test_receipt",
}


def sanitize_text(detail: str, limit: int | None = None) -> str:
    detail = re.sub(r"sk-[A-Za-z0-9]{8,}", "sk-***", detail)
    detail = re.sub(r"(?i)(api[_-]?key|authorization|token|secret|password|llm_api_key)(['\"\s:=]+)([^,;\\s}\\]]+)", r"\1\2***", detail)
    detail = re.sub(r"(?i)(api[_-]?base|base[_-]?url|llm_base_url)(['\"\s:=]+)([^,;\\s}\\]]+)", r"\1\2***", detail)
    detail = re.sub(r"https?://(?!127\.0\.0\.1|localhost)([^/\s\"'<>]+)([^\s\"'<>]*)", r"https://<provider-host-redacted>\2", detail)
    return detail[:limit] if limit else detail


def sanitize_detail(detail: str) -> str:
    return sanitize_text(detail, 300)


def sanitize_public_value(value: object) -> object:
    if isinstance(value, str):
        return sanitize_text(value)
    if isinstance(value, list):
        return [sanitize_public_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): sanitize_public_value(item) for key, item in value.items()}
    return value


def redact_provider_preview(preview: str | None) -> str | None:
    if not preview:
        return preview
    if preview.startswith("backend .env configured"):
        return preview
    try:
        parsed = urllib.parse.urlsplit(preview)
    except ValueError:
        return "<provider-base-redacted>"
    if not parsed.scheme or not parsed.netloc:
        return "<provider-base-redacted>"
    path = parsed.path.rstrip("/") or "/"
    return f"{parsed.scheme}://<provider-host-redacted>{path}"


def post_json(api_base: str, path: str, payload: dict, timeout: float) -> dict:
    request = urllib.request.Request(
        f"{api_base.rstrip('/')}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            return json.loads(body)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"POST {path} failed with HTTP {exc.code}: {sanitize_detail(detail)}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"POST {path} failed: {sanitize_detail(str(exc.reason))}") from exc
    except TimeoutError as exc:
        raise RuntimeError("Request timed out.") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON response from {path}.") from exc


def get_json(api_base: str, path: str, timeout: float) -> dict:
    try:
        with urllib.request.urlopen(f"{api_base.rstrip('/')}{path}", timeout=timeout) as response:
            body = response.read().decode("utf-8")
            return json.loads(body)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"GET {path} failed with HTTP {exc.code}: {sanitize_detail(detail)}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"GET {path} failed: {sanitize_detail(str(exc.reason))}") from exc
    except TimeoutError as exc:
        raise RuntimeError("Request timed out.") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON response from {path}.") from exc


def print_section(title: str, payload: dict) -> None:
    print(f"\n## {title}")
    print(json.dumps(sanitize_public_value(payload), ensure_ascii=False, indent=2))


def compact_audit(item: dict | None) -> dict | None:
    if not isinstance(item, dict):
        return None
    return {
        "id": item.get("id"),
        "event": item.get("event") or item.get("event_type"),
        "created_at": item.get("created_at") or item.get("timestamp"),
        "generation_mode": item.get("generation_mode") or item.get("mode"),
        "provider_called": item.get("provider_called"),
        "risk_level": item.get("risk_level"),
    }


def compact_admission_state(state: dict | None) -> dict | None:
    if not isinstance(state, dict):
        return None
    return {
        "provider_name": state.get("provider_name"),
        "grade": state.get("grade"),
        "total_score": state.get("total_score"),
        "provider_called": state.get("provider_called"),
        "safe_for_training": state.get("safe_for_training"),
        "recommendation": state.get("recommendation"),
    }


def compact_provider_status(status: dict | None) -> dict | None:
    if not isinstance(status, dict):
        return None
    return {
        "provider": status.get("provider"),
        "mode": status.get("mode"),
        "model": status.get("model"),
        "ok": status.get("ok"),
        "error": status.get("error"),
        "latency_ms": status.get("latency_ms"),
        "configured": status.get("configured"),
    }


def compact_evidence_ladder(steps: object) -> list[dict[str, object]]:
    if not isinstance(steps, list):
        return []
    compact: list[dict[str, object]] = []
    for item in steps:
        if not isinstance(item, dict):
            continue
        compact.append(
            {
                "id": item.get("id"),
                "state": item.get("state"),
                "proof_kind": item.get("proof_kind"),
                "label": item.get("label"),
            }
        )
    return compact


def validate_evidence_ladder(steps: object) -> None:
    compact = compact_evidence_ladder(steps)
    required_ids = {
        "provider_env",
        "base_preflight",
        "request_preview",
        "provider_self_test",
        "blind_admission",
        "candidate_unlock",
    }
    ids = {str(item.get("id")) for item in compact}
    missing = sorted(required_ids - ids)
    invalid_states = [
        item for item in compact
        if item.get("state") not in {"done", "current", "pending", "blocked"}
    ]
    if missing or invalid_states:
        raise RuntimeError(
            "Provider evidence ladder is malformed: "
            f"missing={missing or []}; invalid_states={invalid_states or []}"
        )


def resolve_backend(explicit_backend: str | None, timeout: float) -> tuple[str, dict]:
    candidates = [explicit_backend] if explicit_backend else list(DEFAULT_BACKENDS)
    errors: list[str] = []
    for candidate in candidates:
        if not candidate:
            continue
        api_base = candidate.rstrip("/")
        try:
            health = get_json(api_base, "/health", timeout)
        except RuntimeError as exc:
            errors.append(f"{api_base}: {exc}")
            continue
        capabilities = set(health.get("capabilities", []))
        missing = sorted(REQUIRED_CAPABILITIES - capabilities)
        if health.get("status") == "ok" and not missing:
            return api_base, health
        errors.append(f"{api_base}: health ok but missing capabilities: {', '.join(missing) or 'status_not_ok'}")
    raise RuntimeError("No compatible ARIS v2.0 Provider backend found. Tried: " + " | ".join(errors))


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test ARIS OpenAI-compatible Provider wiring without printing API keys.")
    parser.add_argument("--backend", default=os.getenv("ARIS_BACKEND_URL", ""), help="Backend API base. When omitted, auto-probes 8000 then 8001.")
    parser.add_argument("--provider-name", default=os.getenv("LLM_PROVIDER_NAME", "CLI Provider Smoke"), help="Display name only.")
    parser.add_argument("--api-base", default=os.getenv("LLM_BASE_URL", ""), help="Provider base URL. Falls back to backend .env if blank.")
    parser.add_argument("--api-key-env", default="LLM_API_KEY", help="Environment variable that contains the API key. The value is never printed.")
    parser.add_argument("--model", default=os.getenv("LLM_MODEL", ""), help="Optional request model override.")
    parser.add_argument("--include-image", action="store_true", help="Attach one public sample image in the backend visual self-test.")
    parser.add_argument("--sample-id", default=os.getenv("ARIS_SMOKE_SAMPLE_ID", ""), help="Optional public sample id for visual self-test.")
    parser.add_argument("--self-test", action="store_true", help="After preflight, run /provider/self-test.")
    parser.add_argument("--use-backend-env-key", action="store_true", help="Run self-test without sending a request key, using backend .env if configured.")
    parser.add_argument("--timeout", type=float, default=25.0)
    args = parser.parse_args()

    api_base, health = resolve_backend(args.backend or None, args.timeout)
    capabilities = set(health.get("capabilities", []))
    missing = sorted(REQUIRED_CAPABILITIES - capabilities)
    print_section(
        "Backend health",
        {
            "backend_api_base": api_base,
            "status": health.get("status"),
            "version": health.get("version"),
            "missing_capabilities": missing,
        },
    )

    diagnostics = get_json(api_base, "/provider/diagnostics", args.timeout)
    validate_evidence_ladder(diagnostics.get("evidence_ladder"))
    diagnostics_public = {
        "ready_level": diagnostics.get("ready_level"),
        "provider_configured": diagnostics.get("provider_configured"),
        "provider_mode": diagnostics.get("provider_mode"),
        "provider": diagnostics.get("provider"),
        "base_url_configured": diagnostics.get("base_url_configured"),
        "api_key_configured": diagnostics.get("api_key_configured"),
        "private_host_allowlist_configured": diagnostics.get("private_host_allowlist_configured"),
        "private_host_allowlist_count": diagnostics.get("private_host_allowlist_count"),
        "missing": diagnostics.get("missing", []),
        "public_sample_count": diagnostics.get("public_sample_count"),
        "latest_self_test": compact_audit(diagnostics.get("latest_self_test")),
        "latest_admission": compact_audit(diagnostics.get("latest_admission")),
        "admission_state": compact_admission_state(diagnostics.get("admission_state")),
        "evidence_ladder": compact_evidence_ladder(diagnostics.get("evidence_ladder")),
        "blocking_reason": diagnostics.get("blocking_reason"),
        "next_actions": diagnostics.get("next_actions", []),
        "privacy_notice": diagnostics.get("privacy_notice"),
    }
    print_section("Provider diagnostics", diagnostics_public)

    preflight = post_json(api_base, "/provider/preflight", {"api_base": args.api_base}, args.timeout)
    preflight_public = {
        "ok": preflight.get("ok"),
        "safety_status": preflight.get("safety_status"),
        "mode": preflight.get("mode"),
        "normalized_preview": redact_provider_preview(preflight.get("normalized_preview")),
        "endpoint_paths": preflight.get("endpoint_paths", []),
        "blocked_reason": preflight.get("blocked_reason"),
        "private_host_allowlist_configured": preflight.get("private_host_allowlist_configured"),
        "private_host_allowlist_used": preflight.get("private_host_allowlist_used"),
        "request_sent": preflight.get("request_sent"),
        "key_persisted": preflight.get("key_persisted"),
        "warnings": preflight.get("warnings", []),
        "next_actions": preflight.get("next_actions", []),
    }
    print_section("Provider preflight", preflight_public)

    preview = post_json(
        api_base,
        "/provider/request-preview",
        {
            "provider_name": args.provider_name,
            "api_base": args.api_base,
            "api_key_present": bool(os.getenv(args.api_key_env, "")) or bool(args.use_backend_env_key),
            "model": args.model or None,
            "selected_sample_ids": ["real_x1_0", "real_x1_2", "real_x1_3"],
            "test_focus": ["基础识别", "错误前提", "报告安全"],
            "preview_mode": "admission",
        },
        args.timeout,
    )
    preview_public = {
        "id": preview.get("id"),
        "api_source": preview.get("api_source"),
        "ready_for_provider_call": preview.get("ready_for_provider_call"),
        "blocked_reason": preview.get("blocked_reason"),
        "safety_status": preview.get("safety_status"),
        "endpoint_paths": preview.get("endpoint_paths", []),
        "sample_count": preview.get("sample_count"),
        "image_attachment_count": preview.get("image_attachment_count"),
        "request_sent": preview.get("request_sent"),
        "key_persisted": preview.get("key_persisted"),
        "audit_logged": preview.get("audit_logged"),
        "state_updated": preview.get("state_updated"),
        "reference_answer_sent": preview.get("reference_answer_sent"),
    }
    print_section("Provider request preview", preview_public)
    if preview.get("request_sent") or preview.get("key_persisted") or preview.get("audit_logged") or preview.get("state_updated"):
        print("\nProvider request preview is not read-only. Check backend dry-run implementation.")
        return 5
    if preview.get("reference_answer_sent") or int(preview.get("sample_count") or 0) <= 0:
        print("\nProvider request preview did not preserve blind-probe/sample constraints.")
        return 5

    if not preflight.get("ok"):
        print("\nPreflight blocked Provider calls. Fix API Base before running self-test.")
        return 2
    if not args.self_test:
        print("\nPreflight passed. Re-run with --self-test to call Provider self-test.")
        return 0

    api_key = os.getenv(args.api_key_env, "")
    if not api_key and not args.use_backend_env_key:
        print(f"\nNo key sent. Set {args.api_key_env} or pass --use-backend-env-key if backend .env is configured.")
        return 3

    payload = {
        "provider_name": args.provider_name,
        "api_base": args.api_base,
        "api_key": api_key or None,
        "model": args.model or None,
        "include_image": bool(args.include_image),
        "sample_id": args.sample_id or None,
    }
    result = post_json(api_base, "/provider/self-test", payload, args.timeout)
    result_public = {
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
    }
    print_section("Provider self-test", result_public)
    return 0 if result.get("provider_called") else 4


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RuntimeError as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(130)
