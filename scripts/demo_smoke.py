import argparse
import json
import re
import sys
import urllib.error
import urllib.request


DEFAULT_BACKENDS = ("http://127.0.0.1:8000/api", "http://127.0.0.1:8001/api")

REQUIRED_CAPABILITIES = {
    "provider_preflight",
    "provider_request_preview",
    "real_sample_coverage",
    "demo_check_sandbox",
    "demo_check_restore_verified",
    "demo_check_exam_card_receipt",
    "challenge_benchmark",
    "challenge_audit_receipt",
    "patient_card_generation_receipt",
    "patient_card_approve",
    "skill_run_receipt",
}


def sanitize_detail(detail: str) -> str:
    detail = re.sub(r"sk-[A-Za-z0-9]{8,}", "sk-***", detail)
    detail = re.sub(r"(?i)(api[_-]?key|authorization|token|secret|password|llm_api_key)(['\"\s:=]+)([^,;\\s}\\]]+)", r"\1\2***", detail)
    detail = re.sub(r"(?i)(api[_-]?base|base[_-]?url|llm_base_url)(['\"\s:=]+)([^,;\\s}\\]]+)", r"\1\2***", detail)
    return detail[:300]


def get_json(api_base: str, path: str, timeout: float) -> dict:
    try:
        with urllib.request.urlopen(f"{api_base.rstrip('/')}{path}", timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"GET {path} failed with HTTP {exc.code}: {sanitize_detail(detail)}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"GET {path} failed: {sanitize_detail(str(exc.reason))}") from exc
    except TimeoutError as exc:
        raise RuntimeError(f"GET {path} timed out.") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"GET {path} returned invalid JSON.") from exc


def post_json(api_base: str, path: str, timeout: float) -> dict:
    request = urllib.request.Request(f"{api_base.rstrip('/')}{path}", data=b"", method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"POST {path} failed with HTTP {exc.code}: {sanitize_detail(detail)}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"POST {path} failed: {sanitize_detail(str(exc.reason))}") from exc
    except TimeoutError as exc:
        raise RuntimeError(f"POST {path} timed out.") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"POST {path} returned invalid JSON.") from exc


def print_section(title: str, payload: dict) -> None:
    print(f"\n## {title}")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def require(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def readiness_summary(readiness: dict) -> dict[str, object]:
    coverage = readiness.get("real_sample_coverage") or {}
    return {
        "training_record_count": readiness.get("training_record_count"),
        "audit_log_count": readiness.get("audit_log_count"),
        "exam_session_count": readiness.get("exam_session_count"),
        "real_sample_count": readiness.get("real_sample_count"),
        "real_sample_records": coverage.get("total_records"),
        "real_sample_assets": f"{coverage.get('asset_present_count')}/{coverage.get('asset_checked_count')}",
    }


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
    raise RuntimeError("No compatible ARIS v2.0 backend found. Tried: " + " | ".join(errors))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run ARIS v2.0 demo smoke checks without keeping learner/audit/card mutations.")
    parser.add_argument("--backend", help="Backend API base. When omitted, auto-probes http://127.0.0.1:8000/api then http://127.0.0.1:8001/api.")
    parser.add_argument("--learner-id", default="demo_learner")
    parser.add_argument("--persist", action="store_true", help="Keep demo-check learner/audit/card writes. Default is sandbox restore.")
    parser.add_argument("--yes", action="store_true", help="Required with --persist to confirm keeping learner/audit/card writes.")
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()
    if args.persist and not args.yes:
        print("\nERROR: --persist keeps learner/audit/card writes. Re-run with --persist --yes if you intentionally want demo traces.", file=sys.stderr)
        return 2

    failures: list[str] = []
    api_base, health = resolve_backend(args.backend, args.timeout)
    capabilities = set(health.get("capabilities", []))
    missing = sorted(REQUIRED_CAPABILITIES - capabilities)
    require(health.get("status") == "ok", "Backend health status is not ok.", failures)
    require(not missing, f"Missing capabilities: {', '.join(missing)}", failures)
    print_section("Backend health", {"api_base": api_base, "status": health.get("status"), "version": health.get("version"), "missing_capabilities": missing})

    readiness = get_json(api_base, "/platform/readiness", args.timeout)
    before_summary = readiness_summary(readiness)
    source_chain = readiness.get("knowledge_source_chain", [])
    sample_coverage = readiness.get("real_sample_coverage") or {}
    receipts = readiness.get("evidence_receipts", [])
    require(bool(readiness.get("backend_ready")), "Readiness backend_ready is false.", failures)
    require(int(readiness.get("real_sample_count", 0) or 0) > 0, "No real public samples reported.", failures)
    require(int(sample_coverage.get("total_records", 0) or 0) > 0, "Real sample coverage total_records is missing.", failures)
    require(int(sample_coverage.get("mapped_question_count", 0) or 0) > 0, "Real sample coverage mapped_question_count is missing.", failures)
    require(
        sample_coverage.get("asset_present_count") == sample_coverage.get("asset_checked_count"),
        "Real sample coverage reports missing image assets.",
        failures,
    )
    require(len(source_chain) >= 3, "Knowledge source chain is incomplete.", failures)
    require(any(item.get("id") == "challenge_audit" for item in receipts), "Challenge benchmark receipt is missing.", failures)
    print_section(
        "Readiness",
        {
            "overall_score": readiness.get("overall_score"),
            "provider_mode": readiness.get("provider_mode"),
            "real_sample_count": readiness.get("real_sample_count"),
            "real_sample_coverage": sample_coverage,
            "knowledge_sources": [item.get("id") for item in source_chain],
            "state_summary": before_summary,
            "challenge_receipt": next((item for item in receipts if item.get("id") == "challenge_audit"), None),
        },
    )

    persist_text = "true" if args.persist else "false"
    demo = post_json(api_base, f"/platform/demo-check?learner_id={args.learner_id}&persist={persist_text}", args.timeout)
    audit_events = set(demo.get("audit_event_types", []))
    receipt_ids = {item.get("id") for item in demo.get("receipts", [])}
    require(demo.get("mode") == ("persisted" if args.persist else "sandbox"), "Demo-check mode mismatch.", failures)
    require(bool(demo.get("write_verified")), "Demo-check did not verify writes.", failures)
    require(bool(demo.get("restored_after_run")) is (not args.persist), "Demo-check restore/persist flag mismatch.", failures)
    require(bool(demo.get("restore_verified")) is (not args.persist), "Demo-check restore verification flag mismatch.", failures)
    require("challenge_benchmark" in audit_events, "Demo-check did not trigger challenge_benchmark audit event.", failures)
    require(
        {
            "answer_submit",
            "tutor_agent",
            "challenge_benchmark",
            "report_draft",
            "report_judge",
            "exam_session",
            "patient_card",
            "patient_card_approve",
            "audit_log",
        }.issubset(receipt_ids),
        "Demo-check receipts are incomplete.",
        failures,
    )

    after_summary = None
    if not args.persist:
        post_readiness = get_json(api_base, "/platform/readiness", args.timeout)
        after_summary = readiness_summary(post_readiness)
        require(after_summary == before_summary, "Sandbox readiness summary changed after restore.", failures)

    print_section(
        "Demo check",
        {
            "mode": demo.get("mode"),
            "write_verified": demo.get("write_verified"),
            "restored_after_run": demo.get("restored_after_run"),
            "restore_verified": demo.get("restore_verified"),
            "source_dataset": demo.get("source_dataset"),
            "audit_delta": demo.get("audit_delta"),
            "audit_event_types": demo.get("audit_event_types", []),
            "receipt_ids": sorted(receipt_ids),
            "state_summary_before": before_summary,
            "state_summary_after": after_summary,
        },
    )

    if failures:
        print_section("Failures", {"items": failures})
        return 2
    print("\nDemo smoke passed. Sandbox mode restored learner/audit/card data and the readiness summary stayed unchanged." if not args.persist else "\nDemo smoke passed. Persisted mode kept learner/audit/card writes.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RuntimeError as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(130)
