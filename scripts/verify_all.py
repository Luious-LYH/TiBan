import argparse
import hashlib
import json
import locale
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SECRET_PATTERN = re.compile(r"sk-[A-Za-z0-9]{16,}")
ANSI_PATTERN = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
SKIP_SECRET_DIRS = {
    ".git",
    "__pycache__",
    "node_modules",
    "dist",
    "runtime_logs",
}
STATE_FILES = [
    "backend/app/data/audit_logs.json",
    "backend/app/data/learner_profile.json",
    "backend/runtime/patient_cards.json",
]
UPLOAD_DIR = ROOT / "backend/runtime/uploads"
NOISE_LINE_PATTERNS = [
    re.compile(r"^warning: in the working copy of .+ LF will be replaced by CRLF the next time Git touches it$"),
]

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def sanitize(text: str) -> str:
    text = ANSI_PATTERN.sub("", text)
    text = re.sub(r"sk-[A-Za-z0-9]{8,}", "sk-***", text)
    text = re.sub(r"(?i)(api[_-]?key|authorization|token|secret|password|llm_api_key)(['\"\s:=]+)([^,;\\s}\\]]+)", r"\1\2***", text)
    text = re.sub(r"(?i)(--provider-api-base\s+)(\S+)", r"\1***", text)
    text = re.sub(r"(?i)(--api-base\s+)(\S+)", r"\1***", text)
    return text


def print_section(title: str) -> None:
    print(f"\n## {title}")


def command_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUTF8", "1")
    return env


def decode_output(data: bytes) -> str:
    if not data:
        return ""
    text = ""
    encodings = ["utf-8-sig", locale.getpreferredencoding(False), "gbk"]
    seen: set[str] = set()
    for encoding in encodings:
        normalized = encoding.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        try:
            text = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if not text:
        text = data.decode("utf-8", errors="replace")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def strip_noise(text: str) -> str:
    lines = []
    for line in text.splitlines():
        if any(pattern.match(line) for pattern in NOISE_LINE_PATTERNS):
            continue
        lines.append(line)
    return "\n".join(lines)


def run_command(title: str, command: list[str], cwd: Path = ROOT) -> None:
    print_section(title)
    print(sanitize(" ".join(command)))
    result = subprocess.run(
        command,
        cwd=cwd,
        env=command_env(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout = strip_noise(decode_output(result.stdout)).rstrip()
    stderr = strip_noise(decode_output(result.stderr)).rstrip()
    if stdout:
        print(sanitize(stdout))
    if stderr:
        print(sanitize(stderr))
    if result.returncode != 0:
        raise RuntimeError(f"{title} failed with exit code {result.returncode}.")


def resolve_binary(name: str) -> str:
    candidates = [name]
    if os.name == "nt" and not name.lower().endswith((".exe", ".cmd", ".bat")):
        candidates = [f"{name}.cmd", f"{name}.exe", f"{name}.bat", name]
    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    raise RuntimeError(f"Required executable not found on PATH: {name}")


def scan_secrets() -> None:
    print_section("Secret scan")
    hits: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT)
        if any(part in SKIP_SECRET_DIRS for part in relative.parts):
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if SECRET_PATTERN.search(content):
            hits.append(str(relative))
    if hits:
        print("Potential secret-like tokens found in:")
        for item in hits:
            print(f"- {item}")
        raise RuntimeError("Secret scan failed.")
    print("No secret-like sk-* tokens found in workspace files.")


def ensure_real_sample_assets() -> None:
    print_section("Real sample assets")
    knowledge_path = ROOT / "backend/app/data/real_sample_knowledge.json"
    if not knowledge_path.exists():
        raise RuntimeError("Missing backend/app/data/real_sample_knowledge.json.")
    try:
        items = json.loads(knowledge_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid real_sample_knowledge.json: {exc}") from exc
    if not isinstance(items, list) or not items:
        raise RuntimeError("real_sample_knowledge.json has no sample records.")
    missing: list[str] = []
    checked = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        image_url = str(item.get("image_url") or "")
        if not image_url:
            missing.append(f"{item.get('id', '<unknown>')}: missing image_url")
            continue
        if not image_url.startswith("/assets/real_samples/"):
            missing.append(f"{item.get('id', '<unknown>')}: unsupported image_url {image_url}")
            continue
        asset_path = ROOT / "frontend/public" / image_url.lstrip("/")
        if not asset_path.exists() or not asset_path.is_file() or asset_path.stat().st_size <= 0:
            missing.append(f"{item.get('id', '<unknown>')}: {image_url}")
            continue
        checked += 1
    if missing:
        print("Missing or invalid real sample image assets:")
        for item in missing:
            print(f"- {item}")
        raise RuntimeError("Real sample asset check failed.")
    print(f"All {checked} real sample image assets are present under frontend/public/assets/real_samples.")


def file_fingerprint(path: Path) -> str:
    if not path.exists():
        return "<missing>"
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return f"sha256:{digest}:bytes:{path.stat().st_size}"


def snapshot_state_files() -> dict[str, str]:
    return {relative: file_fingerprint(ROOT / relative) for relative in STATE_FILES}


def snapshot_upload_files() -> dict[str, str]:
    if not UPLOAD_DIR.exists():
        return {}
    return {
        str(path.relative_to(ROOT)): file_fingerprint(path)
        for path in sorted(UPLOAD_DIR.iterdir())
        if path.is_file()
    }


def ensure_state_files_clean(before: dict[str, str]) -> None:
    print_section("State file diff")
    after = snapshot_state_files()
    changed = [relative for relative, old_value in before.items() if after.get(relative) != old_value]
    if changed:
        print("State files changed:")
        for item in changed:
            print(f"- {item}: {before[item]} -> {after.get(item)}")
        raise RuntimeError("Runtime state files changed during verification.")
    print("No learner/audit/card state file content drift.")


def ensure_upload_files_clean(before: dict[str, str]) -> None:
    print_section("Upload directory diff")
    after = snapshot_upload_files()
    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    changed = sorted(path for path in set(before) & set(after) if before[path] != after[path])
    if added or removed or changed:
        if added:
            print("Upload files added:")
            for item in added:
                print(f"- {item}: {after[item]}")
        if removed:
            print("Upload files removed:")
            for item in removed:
                print(f"- {item}: {before[item]}")
        if changed:
            print("Upload files changed:")
            for item in changed:
                print(f"- {item}: {before[item]} -> {after[item]}")
        raise RuntimeError("Upload runtime files changed during verification.")
    print("No backend/runtime/uploads file drift.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run ARIS v2.0 backend, Provider, UI, lint/build, and safety verification.")
    parser.add_argument("--frontend", default=os.getenv("ARIS_FRONTEND_URL", "http://127.0.0.1:5173"))
    parser.add_argument("--provider-api-base", default="http://127.0.0.1:9999/v1", help="Safe local Provider base used only for preflight; no key is sent.")
    parser.add_argument("--skip-build", action="store_true", help="Skip npm lint/build.")
    parser.add_argument("--skip-ui", action="store_true", help="Skip browser UI route smoke.")
    args = parser.parse_args()

    git_bin = resolve_binary("git")
    state_before = snapshot_state_files()
    uploads_before = snapshot_upload_files()
    command_error: RuntimeError | None = None

    try:
        run_command("Backend compile", [sys.executable, "-m", "compileall", "backend/app"])
        run_command("Demo sandbox smoke", [sys.executable, "scripts/demo_smoke.py"])
        run_command("Report upload receipt smoke", [sys.executable, "scripts/report_upload_smoke.py"])
        run_command("Provider preflight smoke", [sys.executable, "scripts/provider_smoke.py", "--api-base", args.provider_api_base])
        run_command("Provider readiness doctor", [sys.executable, "scripts/provider_doctor.py"])
        run_command("Delivery evidence report export", [sys.executable, "scripts/export_delivery_report.py", "--output", "runtime_logs/delivery_evidence_report.md"])
        if not args.skip_ui:
            node_bin = resolve_binary("node")
            run_command("Frontend route UI smoke", [node_bin, "scripts/ui_smoke.mjs", "--frontend", args.frontend])
        if not args.skip_build:
            npm_bin = resolve_binary("npm")
            run_command("Frontend lint", [npm_bin, "run", "lint"], cwd=ROOT / "frontend")
            run_command("Frontend build", [npm_bin, "run", "build"], cwd=ROOT / "frontend")
        run_command("Git diff check", [git_bin, "diff", "--check"])
        ensure_real_sample_assets()
        scan_secrets()
    except RuntimeError as exc:
        command_error = exc
    finally:
        try:
            ensure_state_files_clean(state_before)
            ensure_upload_files_clean(uploads_before)
        except RuntimeError as state_exc:
            if command_error:
                raise RuntimeError(f"{command_error}\nState guard also failed: {state_exc}") from state_exc
            raise
    if command_error:
        raise command_error

    checked_parts = ["core backend loop", "report upload receipt", "Provider preflight", "Provider readiness doctor", "delivery evidence report"]
    if not args.skip_ui:
        checked_parts.append("UI routes")
    if not args.skip_build:
        checked_parts.append("lint/build")
    checked_parts.extend(["git diff check", "real-sample assets", "secret scan", "state/upload guard"])
    print(f"\nARIS verification passed. Checked: {', '.join(checked_parts)}.")
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
