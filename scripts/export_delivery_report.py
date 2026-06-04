import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib import error, request


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BACKENDS = ("http://127.0.0.1:8000/api", "http://127.0.0.1:8001/api")
DEFAULT_OUTPUT = ROOT / "runtime_logs" / "delivery_evidence_report.md"
STATE_FILES = [
    ROOT / "backend/app/data/audit_logs.json",
    ROOT / "backend/app/data/learner_profile.json",
    ROOT / "backend/runtime/patient_cards.json",
]

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def sanitize(text: str) -> str:
    text = re.sub(r"sk-[A-Za-z0-9]{8,}", "sk-***", text)
    text = re.sub(r"(?i)(api[_-]?key|authorization|token|secret|password|llm_api_key)(['\"\s:=]+)([^,;\\s}\\]]+)", r"\1\2***", text)
    text = re.sub(r"(?i)(api[_-]?base|base[_-]?url|llm_base_url)(['\"\s:=]+)([^,;\\s}\\]]+)", r"\1\2***", text)
    return text


def sanitize_payload(value):
    if isinstance(value, dict):
        return {key: sanitize_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_payload(item) for item in value]
    if isinstance(value, str):
        return sanitize(value)
    return value


def file_fingerprint(path: Path) -> str:
    if not path.exists():
        return "<missing>"
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return f"sha256:{digest}:bytes:{path.stat().st_size}"


def snapshot_state_files() -> dict[str, str]:
    return {str(path.relative_to(ROOT)): file_fingerprint(path) for path in STATE_FILES}


def ensure_state_unchanged(before: dict[str, str]) -> None:
    after = snapshot_state_files()
    changed = [relative for relative, old_value in before.items() if after.get(relative) != old_value]
    if changed:
        details = ", ".join(f"{relative}: {before[relative]} -> {after.get(relative)}" for relative in changed)
        raise RuntimeError(f"Delivery report export changed state files: {details}")


def get_json(api_base: str, path: str, timeout: float) -> dict:
    url = f"{api_base.rstrip('/')}{path}"
    try:
        with request.urlopen(url, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"GET {path} failed with HTTP {exc.code}: {sanitize(detail[:300])}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"GET {path} failed: {sanitize(str(exc.reason))}") from exc
    except TimeoutError as exc:
        raise RuntimeError(f"GET {path} timed out.") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"GET {path} returned invalid JSON.") from exc


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
        if health.get("status") == "ok" and "delivery_report" in capabilities:
            return api_base, health
        errors.append(f"{api_base}: missing delivery_report capability")
    raise RuntimeError("No compatible ARIS backend found. Tried: " + " | ".join(errors))


def md_escape(value: object) -> str:
    text = sanitize(str(value if value is not None else ""))
    return text.replace("|", "\\|").replace("\n", " ").strip()


def bullet(items: list[object], empty: str = "暂无") -> list[str]:
    if not items:
        return [f"- {empty}"]
    return [f"- {md_escape(item)}" for item in items]


def table(headers: list[str], rows: list[list[object]]) -> list[str]:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    if rows:
        for row in rows:
            lines.append("| " + " | ".join(md_escape(cell) for cell in row) + " |")
    else:
        lines.append("| " + " | ".join(["暂无"] + [""] * (len(headers) - 1)) + " |")
    return lines


def render_report(report: dict, api_base: str) -> str:
    generated_at = report.get("generated_at") or datetime.now().isoformat(timespec="seconds")
    doctor = report.get("doctor_context", {})
    summary = report.get("platform_summary", {})
    provider = report.get("provider_state", {})
    integrity = report.get("report_integrity", {})
    lines: list[str] = [
        f"# {md_escape(report.get('title', 'ARIS v2.0 交付证据报告'))}",
        "",
        f"- 生成时间：{md_escape(generated_at)}",
        f"- 后端来源：{md_escape(api_base)}",
        f"- 项目范围：{md_escape(report.get('scope'))}",
        f"- 安全边界：{md_escape(report.get('safety_notice'))}",
        f"- 报告性质：只读当前运行状态；writes_state={md_escape(integrity.get('writes_state'))}；secrets_included={md_escape(integrity.get('secrets_included'))}",
        "",
        "## 医师训练对象",
        "",
        *table(
            ["字段", "值"],
            [
                ["医师", f"{doctor.get('name')} · {doctor.get('title')}"],
                ["科室/阶段", f"{doctor.get('department')} · {doctor.get('training_stage')}"],
                ["训练进度", f"{doctor.get('completed_today')}/{doctor.get('daily_target')} · 连续 {doctor.get('streak_days')} 天"],
                ["Learner ID", doctor.get("learner_id")],
            ],
        ),
        "",
        "## 平台总览",
        "",
        *table(
            ["指标", "当前值"],
            [
                ["就绪度", f"{summary.get('overall_score')}%"],
                ["后端在线", summary.get("backend_ready")],
                ["Provider", f"{summary.get('provider_mode')} · ready={summary.get('provider_ready')}"],
                ["知识库", f"题库 {summary.get('qbank_count')} · 真实样例 {summary.get('real_sample_count')} · 报告模板 {summary.get('report_template_count')}"],
                ["画像/考试", f"memory={summary.get('memory_ready')} · exam_session={summary.get('exam_session_count')}"],
                ["审计", f"{summary.get('audit_log_count')} 条摘要事件"],
                ["模型准入", f"Grade {summary.get('admission_grade')} · provider_called={summary.get('admission_provider_called')}"],
            ],
        ),
        "",
        "## 核心闭环证据",
        "",
        *table(
            ["模块", "状态", "证据", "入口"],
            [
                [item.get("name"), item.get("status"), item.get("evidence"), item.get("route")]
                for item in report.get("workflow_proofs", [])
            ],
        ),
        "",
        "## 知识库来源链",
        "",
        *table(
            ["来源", "文件", "记录", "消费页面", "证明"],
            [
                [
                    item.get("label"),
                    item.get("source_file"),
                    item.get("record_count"),
                    "、".join(str(value) for value in item.get("used_by", [])),
                    item.get("proof"),
                ]
                for item in report.get("knowledge_source_chain", [])
            ],
        ),
        "",
        "## 可核验证据收据",
        "",
        *table(
            ["收据", "状态", "说明", "入口"],
            [
                [item.get("label"), item.get("status"), item.get("detail"), item.get("href")]
                for item in report.get("evidence_receipts", [])
            ],
        ),
        "",
        "## 审计事件分布",
        "",
        *table(
            ["事件类型", "数量"],
            [[item.get("event_type"), item.get("count")] for item in report.get("audit_event_counts", [])],
        ),
        "",
        "## Provider 与模型准入边界",
        "",
        *table(
            ["字段", "当前值"],
            [
                ["Provider configured", provider.get("configured")],
                ["Mode", provider.get("mode")],
                ["Provider declared", provider.get("provider_declared")],
                ["Model", provider.get("model")],
                ["Admission provider_called", provider.get("admission_provider_called")],
                ["Admission safe_for_training", provider.get("admission_safe_for_training")],
            ],
        ),
        "",
        "## 当前能力边界",
        "",
        *bullet(report.get("current_boundaries", [])),
        "",
        "## 待补强项",
        "",
        *bullet(report.get("gaps", []), empty="当前 readiness 未报告新的阻塞项。"),
        "",
        "## 答辩前验证命令",
        "",
        *table(
            ["命令", "覆盖范围"],
            [[item.get("command"), item.get("covers")] for item in report.get("verification_commands", [])],
        ),
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Export an ARIS v2.0 delivery evidence Markdown report from the live backend.")
    parser.add_argument("--backend", help="Backend API base. When omitted, auto-probes 8000 then 8001.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Markdown output path. Default: runtime_logs/delivery_evidence_report.md")
    parser.add_argument("--json-output", help="Optional recursively sanitized JSON snapshot output path.")
    parser.add_argument("--timeout", type=float, default=15.0)
    args = parser.parse_args()

    state_before = snapshot_state_files()
    api_base, health = resolve_backend(args.backend, args.timeout)
    report = sanitize_payload(get_json(api_base, "/platform/delivery-report", args.timeout))
    try:
        rendered = render_report(report, api_base)
        output_path = Path(args.output)
        if not output_path.is_absolute():
            output_path = ROOT / output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered, encoding="utf-8")

        if args.json_output:
            json_path = Path(args.json_output)
            if not json_path.is_absolute():
                json_path = ROOT / json_path
            json_path.parent.mkdir(parents=True, exist_ok=True)
            json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    finally:
        ensure_state_unchanged(state_before)

    print(json.dumps({
        "api_base": api_base,
        "backend_version": health.get("version"),
        "output": str(output_path),
        "overall_score": report.get("platform_summary", {}).get("overall_score"),
        "real_sample_count": report.get("platform_summary", {}).get("real_sample_count"),
        "audit_log_count": report.get("platform_summary", {}).get("audit_log_count"),
        "writes_state": report.get("report_integrity", {}).get("writes_state"),
        "secrets_included": report.get("report_integrity", {}).get("secrets_included"),
        "state_unchanged": True,
    }, ensure_ascii=False, indent=2))
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
