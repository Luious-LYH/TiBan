"""Safe, runtime-only image assets shared by Question Factory and chat.

The service intentionally uses a small header parser instead of decoding an
image in the API process.  It verifies the declared MIME, magic bytes, file
size and dimensions before the bytes enter the controlled upload directory.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import posixpath
import re
import struct
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import delete, select

from app.core.config import UPLOAD_DIR
from app.db.models import QuestionImageAssetModel


ALLOWED_MIME_TYPES = {"image/png", "image/jpeg", "image/webp"}
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_IMAGE_WIDTH = 12_000
MAX_IMAGE_HEIGHT = 12_000
MAX_IMAGE_PIXELS = 25_000_000
QUESTION_ASSET_TTL = timedelta(days=7)
CHAT_ASSET_TTL = timedelta(hours=2)


def _normalise_mime(value: str | None) -> str:
    mime = str(value or "").split(";", 1)[0].strip().lower()
    return "image/jpeg" if mime == "image/jpg" else mime


def normalise_filename(value: str | None) -> str:
    """Return a safe relative filename used only for import matching."""

    raw = str(value or "").replace("\\", "/").strip()
    if not raw or raw.startswith("/") or re.match(r"^[A-Za-z]:", raw):
        raise ValueError("图片文件名必须是相对路径。")
    normalised = posixpath.normpath(raw)
    if normalised in {"", "."} or normalised == ".." or normalised.startswith("../"):
        raise ValueError("图片文件名不能包含路径穿越。")
    if len(normalised) > 300 or any(ord(char) < 32 for char in normalised):
        raise ValueError("图片文件名无效。")
    return normalised


def _jpeg_dimensions(payload: bytes) -> tuple[int | None, int | None]:
    index = 2
    sof_markers = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
    while index + 9 < len(payload):
        if payload[index] != 0xFF:
            index += 1
            continue
        while index < len(payload) and payload[index] == 0xFF:
            index += 1
        if index >= len(payload):
            return None, None
        marker = payload[index]
        index += 1
        if marker in {0xD8, 0xD9, 0x01} or 0xD0 <= marker <= 0xD7:
            continue
        if index + 2 > len(payload):
            return None, None
        segment_length = int.from_bytes(payload[index:index + 2], "big")
        if segment_length < 2 or index + segment_length > len(payload):
            return None, None
        if marker in sof_markers and segment_length >= 7:
            height = int.from_bytes(payload[index + 3:index + 5], "big")
            width = int.from_bytes(payload[index + 5:index + 7], "big")
            return width, height
        index += segment_length
    return None, None


def _webp_dimensions(payload: bytes) -> tuple[int | None, int | None]:
    if len(payload) < 20 or not payload.startswith(b"RIFF") or payload[8:12] != b"WEBP":
        return None, None
    index = 12
    while index + 8 <= len(payload):
        chunk = payload[index:index + 4]
        chunk_size = int.from_bytes(payload[index + 4:index + 8], "little")
        start, end = index + 8, index + 8 + chunk_size
        if end > len(payload):
            return None, None
        data = payload[start:end]
        if chunk == b"VP8X" and len(data) >= 10:
            width = int.from_bytes(data[4:7] + b"\x00", "little") + 1
            height = int.from_bytes(data[7:10] + b"\x00", "little") + 1
            return width, height
        if chunk == b"VP8L" and len(data) >= 5 and data[0] == 0x2F:
            packed = int.from_bytes(data[1:5], "little")
            return (packed & 0x3FFF) + 1, ((packed >> 14) & 0x3FFF) + 1
        if chunk == b"VP8 " and len(data) >= 10 and data[3:6] == b"\x9d\x01\x2a":
            return int.from_bytes(data[6:8], "little") & 0x3FFF, int.from_bytes(data[8:10], "little") & 0x3FFF
        index = end + (chunk_size % 2)
    return None, None


def inspect_image(payload: bytes, declared_mime: str | None = None) -> tuple[str, int, int]:
    if not payload or len(payload) > MAX_IMAGE_BYTES:
        raise ValueError("图片大小必须在 1 字节到 8 MiB 之间。")
    declared = _normalise_mime(declared_mime)
    if payload.startswith(b"\x89PNG\r\n\x1a\n") and len(payload) >= 24 and payload[12:16] == b"IHDR":
        detected, width, height = "image/png", *struct.unpack(">II", payload[16:24])
    elif payload.startswith(b"\xff\xd8"):
        width, height = _jpeg_dimensions(payload)
        detected = "image/jpeg"
    elif payload.startswith(b"RIFF") and payload[8:12] == b"WEBP":
        detected = "image/webp"
        width, height = _webp_dimensions(payload)
    else:
        raise ValueError("图片文件头无法识别，仅支持 PNG、JPEG 或 WebP。")
    if detected not in ALLOWED_MIME_TYPES or (declared and declared != detected):
        raise ValueError("图片 MIME 类型与文件内容不一致。")
    if not width or not height or width > MAX_IMAGE_WIDTH or height > MAX_IMAGE_HEIGHT or width * height > MAX_IMAGE_PIXELS:
        raise ValueError("图片像素尺寸超出允许范围。")
    return detected, int(width), int(height)


def decode_data_url(data_url: str) -> tuple[bytes, str]:
    match = re.fullmatch(r"data:(image/(?:png|jpeg|jpg|webp));base64,([A-Za-z0-9+/=\r\n]+)", str(data_url or ""), re.IGNORECASE)
    if not match:
        raise ValueError("只支持 PNG、JPEG 或 WebP 图片。")
    declared = _normalise_mime(match.group(1))
    try:
        payload = base64.b64decode(match.group(2), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("图片内容无法读取。") from exc
    return payload, declared


class ImageAssetService:
    def stage_data_url(self, session: Any, *, kind: str, filename: str, data_url: str) -> dict[str, Any]:
        if kind not in {"question", "chat"}:
            raise ValueError("不支持的图片用途。")
        safe_name = normalise_filename(filename)
        payload, declared = decode_data_url(data_url)
        mime, width, height = inspect_image(payload, declared)
        asset_id = f"img_{kind}_{uuid4().hex[:16]}"
        extension = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}[mime]
        relative = Path("question-images" if kind == "question" else "chat") / f"{asset_id}.{extension}"
        destination = (UPLOAD_DIR / relative).resolve()
        upload_root = UPLOAD_DIR.resolve()
        if upload_root not in destination.parents:
            raise ValueError("图片存储路径无效。")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)
        now = datetime.utcnow()
        row = QuestionImageAssetModel(
            asset_id=asset_id, kind=kind, storage_path=relative.as_posix(), original_filename=safe_name,
            sha256=hashlib.sha256(payload).hexdigest(), mime_type=mime, width=width, height=height,
            size_bytes=len(payload), status="staged", created_at=now,
            expires_at=now + (QUESTION_ASSET_TTL if kind == "question" else CHAT_ASSET_TTL),
        )
        session.add(row)
        session.commit()
        return self.public_payload(row)

    def get(self, session: Any, asset_id: str, *, kind: str | None = None) -> QuestionImageAssetModel:
        row = session.get(QuestionImageAssetModel, asset_id)
        if row is None or (kind and row.kind != kind):
            raise KeyError(asset_id)
        if row.expires_at and row.expires_at < datetime.utcnow() and row.status != "published":
            self._delete_row(session, row)
            session.commit()
            raise KeyError(asset_id)
        if row.status not in {"staged", "published"}:
            raise KeyError(asset_id)
        return row

    def resolve_path(self, session: Any, asset_id: str, *, kind: str | None = None) -> Path:
        row = self.get(session, asset_id, kind=kind)
        path = (UPLOAD_DIR / row.storage_path).resolve()
        root = UPLOAD_DIR.resolve()
        if root not in path.parents or not path.is_file():
            raise FileNotFoundError(asset_id)
        return path

    @staticmethod
    def public_payload(row: QuestionImageAssetModel) -> dict[str, Any]:
        return {
            "asset_id": row.asset_id, "filename": row.original_filename,
            "url": f"/api/v3/assets/{'question-images' if row.kind == 'question' else 'chat-images'}/{row.asset_id}",
            "mime_type": row.mime_type, "width": row.width, "height": row.height,
            "size_bytes": row.size_bytes, "sha256_prefix": row.sha256[:16],
            "expires_at": row.expires_at.isoformat() if row.expires_at else None,
        }

    def link_question_assets(self, session: Any, asset_ids: set[str], *, batch_id: str | None = None, bank_id: str | None = None, published: bool = False) -> None:
        if not asset_ids:
            return
        rows = list(session.scalars(select(QuestionImageAssetModel).where(QuestionImageAssetModel.asset_id.in_(asset_ids))))
        if len(rows) != len(asset_ids) or any(row.kind != "question" for row in rows):
            raise ValueError("题目引用了不存在或用途不匹配的图片。")
        for row in rows:
            # An asset belongs to exactly one import batch and, after
            # publication, exactly one question bank.  Allow the same batch
            # to move from staged to published, but never let a later import
            # silently take ownership of an existing image.
            if row.batch_id and batch_id and row.batch_id != batch_id:
                raise ValueError("图片已关联到其他导入批次，不能重复使用。")
            if row.bank_id and bank_id and row.bank_id != bank_id:
                raise ValueError("图片已关联到其他题库，不能重复使用。")
            if row.status == "published" and not published:
                raise ValueError("已发布题库图片不能退回待审核状态。")
            if batch_id is not None:
                row.batch_id = batch_id
            if bank_id is not None:
                row.bank_id = bank_id
            row.status = "published" if published else "staged"
            row.expires_at = None if published else row.expires_at

    def cleanup_batch(self, session: Any, batch_id: str) -> None:
        # A published draft can retain the original batch id for provenance;
        # deleting the review batch must not break the already-published bank.
        rows = list(session.scalars(select(QuestionImageAssetModel).where(
            QuestionImageAssetModel.batch_id == batch_id,
            QuestionImageAssetModel.status != "published",
        )))
        for row in rows:
            self._delete_row(session, row)

    def cleanup_bank(self, session: Any, bank_id: str) -> None:
        rows = list(session.scalars(select(QuestionImageAssetModel).where(QuestionImageAssetModel.bank_id == bank_id)))
        for row in rows:
            self._delete_row(session, row)

    @staticmethod
    def _delete_row(session: Any, row: QuestionImageAssetModel) -> None:
        path = (UPLOAD_DIR / row.storage_path).resolve()
        root = UPLOAD_DIR.resolve()
        if root in path.parents:
            path.unlink(missing_ok=True)
        session.delete(row)


image_asset_service = ImageAssetService()
