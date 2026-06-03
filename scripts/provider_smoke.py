import argparse
import json
import os
import sys
import urllib.error
import urllib.request


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
        raise RuntimeError(f"HTTP {exc.code}: {detail[:300]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Request failed: {exc.reason}") from exc
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
        raise RuntimeError(f"HTTP {exc.code}: {detail[:300]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Request failed: {exc.reason}") from exc
    except TimeoutError as exc:
        raise RuntimeError("Request timed out.") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON response from {path}.") from exc


def print_section(title: str, payload: dict) -> None:
    print(f"\n## {title}")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test ARIS OpenAI-compatible Provider wiring without printing API keys.")
    parser.add_argument("--backend", default=os.getenv("ARIS_BACKEND_URL", "http://127.0.0.1:8001/api"), help="Backend API base, default: http://127.0.0.1:8001/api")
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

    health = get_json(args.backend, "/health", args.timeout)
    print_section("Backend health", {"status": health.get("status"), "version": health.get("version"), "provider_preflight": "provider_preflight" in health.get("capabilities", [])})

    preflight = post_json(args.backend, "/provider/preflight", {"api_base": args.api_base}, args.timeout)
    preflight_public = {
        "ok": preflight.get("ok"),
        "safety_status": preflight.get("safety_status"),
        "mode": preflight.get("mode"),
        "normalized_preview": preflight.get("normalized_preview"),
        "endpoint_paths": preflight.get("endpoint_paths", []),
        "blocked_reason": preflight.get("blocked_reason"),
        "request_sent": preflight.get("request_sent"),
        "key_persisted": preflight.get("key_persisted"),
        "warnings": preflight.get("warnings", []),
        "next_actions": preflight.get("next_actions", []),
    }
    print_section("Provider preflight", preflight_public)

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
    result = post_json(args.backend, "/provider/self-test", payload, args.timeout)
    result_public = {
        "id": result.get("id"),
        "provider_called": result.get("provider_called"),
        "visual_probe": result.get("visual_probe"),
        "image_attached": result.get("image_attached"),
        "image_sample_id": result.get("image_sample_id"),
        "provider_status": result.get("provider_status"),
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
