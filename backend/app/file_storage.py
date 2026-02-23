from __future__ import annotations

import io
import os
import zipfile
from xml.etree import ElementTree as ET

from fastapi import HTTPException

from .config import TEXT_PREVIEW_CHAR_LIMIT

VIRTUAL_PATH_PREFIX = "pg://"


def build_virtual_path(owner_type: str, owner_id: str, filename: str) -> str:
    safe_name = str(filename or "").replace("\\", "_").replace("/", "_")
    return f"{VIRTUAL_PATH_PREFIX}{owner_type}/{owner_id}/{safe_name}"


def is_virtual_path(path: str) -> bool:
    return str(path or "").startswith(VIRTUAL_PATH_PREFIX)


def legacy_file_exists(path: str) -> bool:
    normalized = str(path or "").strip()
    return bool(normalized) and (not is_virtual_path(normalized)) and os.path.exists(normalized)


def remove_legacy_file(path: str) -> None:
    if legacy_file_exists(path):
        try:
            os.remove(path)
        except OSError:
            pass


def has_inline_file_data(row) -> bool:
    data = getattr(row, "file_data", None)
    return isinstance(data, (bytes, bytearray, memoryview)) and len(data) > 0


def row_has_file_content(row) -> bool:
    if row is None:
        return False
    if has_inline_file_data(row):
        return True
    return legacy_file_exists(getattr(row, "file_path", ""))


def read_row_file_bytes(row) -> bytes | None:
    if row is None:
        return None

    data = getattr(row, "file_data", None)
    if isinstance(data, memoryview):
        return data.tobytes()
    if isinstance(data, bytearray):
        return bytes(data)
    if isinstance(data, bytes):
        return data

    file_path = getattr(row, "file_path", "")
    if not legacy_file_exists(file_path):
        return None
    with open(file_path, "rb") as file_obj:
        return file_obj.read()


def read_text_preview_from_bytes(raw: bytes) -> str:
    content = None
    for encoding in ("utf-8-sig", "utf-8", "gbk"):
        try:
            content = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if content is None:
        raise HTTPException(status_code=400, detail="Text file encoding is not supported")
    if len(content) > TEXT_PREVIEW_CHAR_LIMIT:
        return f"{content[:TEXT_PREVIEW_CHAR_LIMIT]}\n\n... (preview truncated)"
    return content


def read_docx_preview_from_bytes(raw: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(raw), "r") as archive:
            xml_bytes = archive.read("word/document.xml")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to parse Word file: {exc}") from exc

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise HTTPException(status_code=400, detail=f"Word content is corrupted: {exc}") from exc

    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    lines: list[str] = []
    for paragraph in root.findall(".//w:p", namespace):
        text_parts = [node.text for node in paragraph.findall(".//w:t", namespace) if node.text]
        if text_parts:
            lines.append("".join(text_parts))

    content = "\n".join(lines)
    if len(content) > TEXT_PREVIEW_CHAR_LIMIT:
        return f"{content[:TEXT_PREVIEW_CHAR_LIMIT]}\n\n... (preview truncated)"
    return content
