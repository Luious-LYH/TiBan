import argparse
import base64
import hashlib
import json
import struct
import sys
import urllib.error
import urllib.request
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT_LOG_PATH = ROOT / "backend/app/data/audit_logs.json"
UPLOAD_DIR = ROOT / "backend/runtime/uploads"
DEFAULT_BACKENDS = ("http://127.0.0.1:8000/api", "http://127.0.0.1:8001/api")
REQUIRED_CAPABILITY = "report_upload_receipt"


def make_png(width: int = 2, height: int = 3) -> bytes:
    rows = []
    for y in range(height):
        row = bytearray([0])
        for x in range(width):
            row.extend([32 + x * 40, 96 + y * 25, 160, 255])
        rows.append(bytes(row))
    raw = b"".join(rows)
    return (
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + png_chunk(b"IDAT", zlib.compress(raw))
        + png_chunk(b"IEND", b"")
    )


def png_chunk(kind: bytes, data: bytes) -> bytes:
    checksum = zlib.crc32(kind + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", checksum)


def get_json(api_base: str, path: str, timeout: float) -> dict:
    try:
        with urllib.request.urlopen(f"{api_base.rstrip('/')}{path}", timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")[:300]
        raise RuntimeError(f"GET {path} failed with HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"GET {path} failed: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"GET {path} returned invalid JSON.") from exc


def post_json(api_base: str, path: str, payload: dict, timeout: float) -> dict:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{api_base.rstrip('/')}{path}",
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")[:300]
        raise RuntimeError(f"POST {path} failed with HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"POST {path} failed: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"POST {path} returned invalid JSON.") from exc


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
        if health.get("status") == "ok" and REQUIRED_CAPABILITY in capabilities:
            return api_base, health
        errors.append(f"{api_base}: missing capability {REQUIRED_CAPABILITY}")
    raise RuntimeError("No compatible backend found. Tried: " + " | ".join(errors))


def read_optional_bytes(path: Path) -> bytes | None:
    return path.read_bytes() if path.exists() else None


def restore_optional_bytes(path: Path, payload: bytes | None) -> None:
    if payload is None:
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def upload_file_set() -> set[Path]:
    if not UPLOAD_DIR.exists():
        return set()
    return {item.resolve() for item in UPLOAD_DIR.iterdir() if item.is_file()}


def cleanup_uploads(before_files: set[Path], image_name: str | None) -> list[str]:
    removed: list[str] = []
    upload_root = UPLOAD_DIR.resolve()
    candidates = upload_file_set() - before_files
    if image_name and image_name.startswith("uploads/"):
        candidates.add((UPLOAD_DIR / image_name.removeprefix("uploads/")).resolve())
    for path in candidates:
        try:
            path.relative_to(upload_root)
        except ValueError:
            continue
        if path.exists() and path.is_file():
            path.unlink()
            removed.append(str(path.relative_to(ROOT)))
    return sorted(set(removed))


def require(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-check report image upload receipt and restore local runtime drift.")
    parser.add_argument("--backend", help="Backend API base. Defaults to probing 8000 then 8001.")
    parser.add_argument("--learner-id", default="upload_smoke_learner")
    parser.add_argument("--timeout", type=float, default=20.0)
    args = parser.parse_args()

    audit_before = read_optional_bytes(AUDIT_LOG_PATH)
    files_before = upload_file_set()
    image_name: str | None = None
    removed_uploads: list[str] = []

    try:
        api_base, health = resolve_backend(args.backend, args.timeout)
        image_bytes = make_png()
        sha256_prefix = hashlib.sha256(image_bytes).hexdigest()[:16]
        response = post_json(
            api_base,
            "/report/image-upload",
            {
                "filename": "smoke_report_upload.png",
                "data_url": f"data:image/png;base64,{base64.b64encode(image_bytes).decode('ascii')}",
                "learner_id": args.learner_id,
            },
            args.timeout,
        )
        image_name = str(response.get("image_name") or "")
        audit_log_id = str(response.get("audit_log_id") or "")
        audit_payload = get_json(api_base, "/audit", args.timeout)
        audit_items = audit_payload.get("items", [])
        audit_match = next(
            (
                item for item in audit_items
                if isinstance(item, dict)
                and item.get("id") == audit_log_id
                and item.get("event_type") == "image_upload"
            ),
            None,
        )

        failures: list[str] = []
        require(health.get("status") == "ok", "Backend health is not ok.", failures)
        require(image_name.startswith("uploads/"), "Upload did not return an uploads/... image_name.", failures)
        require(response.get("original_filename") == "smoke_report_upload.png", "Original filename mismatch.", failures)
        require(response.get("bytes") == len(image_bytes), "Uploaded byte count mismatch.", failures)
        require(response.get("mime_type") == "image/png", "MIME type mismatch.", failures)
        require(response.get("width") == 2 and response.get("height") == 3, "PNG dimensions were not parsed as 2 x 3.", failures)
        require(response.get("sha256_prefix") == sha256_prefix, "sha256_prefix mismatch.", failures)
        require(response.get("provider_input_allowed") is True, "provider_input_allowed is not true.", failures)
        require(response.get("audit_logged") is True, "audit_logged is not true.", failures)
        require(bool(audit_log_id), "audit_log_id is missing.", failures)
        require(bool(audit_match), "image_upload audit log was not readable through /audit.", failures)
        if audit_match:
            metadata = audit_match.get("metadata") or {}
            require(metadata.get("sha256_prefix") == sha256_prefix, "Audit metadata sha256_prefix mismatch.", failures)
            require(metadata.get("width") == 2 and metadata.get("height") == 3, "Audit metadata dimensions mismatch.", failures)

        draft = post_json(
            api_base,
            "/report-draft",
            {
                "finding_text": "上传 smoke：胃窦局部黏膜充血，需医生结合完整检查复核。",
                "exam_type": "gastroscopy",
                "image_name": image_name,
                "template_name": "胃镜结构化训练模板",
                "provider_name": "mock",
                "api_base": "http://127.0.0.1:9999/v1",
                "api_key": "smoke-placeholder",
                "model": "smoke-no-network",
            },
            args.timeout,
        )
        upload_ledger = next(
            (
                item for item in draft.get("evidence_ledger", [])
                if isinstance(item, dict) and item.get("evidence_id") == "upload_001"
            ),
            None,
        )
        source_trace = draft.get("source_trace", [])
        upload_trace = next(
            (
                item for item in source_trace
                if isinstance(item, dict) and item.get("source_type") == "uploaded_image"
            ),
            None,
        )
        require(bool(upload_ledger), "Report draft did not include upload_001 evidence ledger.", failures)
        if upload_ledger:
            require(upload_ledger.get("audit_log_id") == audit_log_id, "Report evidence ledger audit_log_id mismatch.", failures)
            require(upload_ledger.get("sha256_prefix") == sha256_prefix, "Report evidence ledger sha256_prefix mismatch.", failures)
            require(upload_ledger.get("width") == 2 and upload_ledger.get("height") == 3, "Report evidence ledger dimensions mismatch.", failures)
        require(bool(upload_trace), "Report source_trace did not include uploaded_image.", failures)
        if upload_trace:
            detail = str(upload_trace.get("detail") or "")
            require(audit_log_id in detail and sha256_prefix in detail, "Report source_trace did not echo upload receipt id/hash.", failures)

        if failures:
            print(json.dumps({"api_base": api_base, "failures": failures, "response": response, "draft": draft}, ensure_ascii=False, indent=2))
            return 2

        print(json.dumps({
            "api_base": api_base,
            "capability": REQUIRED_CAPABILITY,
            "image_name": image_name,
            "bytes": response.get("bytes"),
            "dimensions": f"{response.get('width')} x {response.get('height')}",
            "sha256_prefix": sha256_prefix,
            "audit_log_id": audit_log_id,
            "report_generation_mode": draft.get("generation_mode"),
            "report_ledger_bound": bool(upload_ledger),
            "provider_input_allowed": response.get("provider_input_allowed"),
        }, ensure_ascii=False, indent=2))
        print("\nReport upload smoke passed. Audit and uploaded file will be restored before exit.")
        return 0
    finally:
        restore_optional_bytes(AUDIT_LOG_PATH, audit_before)
        removed_uploads = cleanup_uploads(files_before, image_name)
        if removed_uploads:
            print("\nRemoved upload smoke files:")
            for item in removed_uploads:
                print(f"- {item}")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RuntimeError as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(130)
