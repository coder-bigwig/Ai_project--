from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import config
from ..db.models import CourseORM, ExperimentORM, UserORM
from ..repositories.postgres import (
    AttachmentRepository,
    CourseRepository,
    ExperimentRepository,
    KVStoreRepository,
    OperationLogRepository,
    ResourceRepository,
    SubmissionPdfRepository,
    SubmissionRepository,
    UserRepository,
)

_ID_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_DNS, "experiment-manager.storage-migration.v1")


def _stable_id(prefix: str, value: str) -> str:
    raw = f"{prefix}:{value}".strip()
    return str(uuid.uuid5(_ID_NAMESPACE, raw))


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _normalize_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value))
        except (OSError, ValueError):
            return None
    if isinstance(value, str):
        text = value.strip().replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            return None
    return None


def _load_json(path: str, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as fp:
            data = json.load(fp)
        return data if data is not None else default
    except Exception:
        return default


def _resolve_path(default_path: str, uploads_dir: str | None) -> str:
    if not uploads_dir:
        return default_path
    return os.path.join(uploads_dir, os.path.basename(default_path))


async def has_any_core_data(db: AsyncSession) -> bool:
    checks = [
        select(func.count()).select_from(UserORM),
        select(func.count()).select_from(CourseORM),
        select(func.count()).select_from(ExperimentORM),
    ]
    for stmt in checks:
        count = await db.scalar(stmt)
        if count and int(count) > 0:
            return True
    return False


async def migrate_from_upload_json(db: AsyncSession, uploads_dir: str | None = None) -> dict[str, int]:
    user_repo = UserRepository(db)
    course_repo = CourseRepository(db)
    experiment_repo = ExperimentRepository(db)
    submission_repo = SubmissionRepository(db)
    submission_pdf_repo = SubmissionPdfRepository(db)
    resource_repo = ResourceRepository(db)
    attachment_repo = AttachmentRepository(db)
    operation_log_repo = OperationLogRepository(db)
    kv_repo = KVStoreRepository(db)

    user_registry = _load_json(_resolve_path(config.USER_REGISTRY_FILE, uploads_dir), {})
    resource_registry = _load_json(_resolve_path(config.RESOURCE_REGISTRY_FILE, uploads_dir), {})
    experiment_registry = _load_json(_resolve_path(config.EXPERIMENT_REGISTRY_FILE, uploads_dir), {})
    course_registry = _load_json(_resolve_path(config.COURSE_REGISTRY_FILE, uploads_dir), {})
    attachment_registry = _load_json(_resolve_path(config.ATTACHMENT_REGISTRY_FILE, uploads_dir), {})
    ai_shared_config = _load_json(_resolve_path(config.AI_SHARED_CONFIG_FILE, uploads_dir), {})
    ai_chat_history = _load_json(_resolve_path(config.AI_CHAT_HISTORY_FILE, uploads_dir), {})
    resource_policy = _load_json(_resolve_path(config.RESOURCE_POLICY_FILE, uploads_dir), {})
    operation_log = _load_json(_resolve_path(config.OPERATION_LOG_FILE, uploads_dir), {})
    student_submission_registry = _load_json(
        _resolve_path(os.path.join(config.UPLOAD_DIR, "student_experiment_registry.json"), uploads_dir),
        {},
    )
    submission_pdf_registry = _load_json(
        _resolve_path(os.path.join(config.UPLOAD_DIR, "submission_pdf_registry.json"), uploads_dir),
        {},
    )

    counters = {
        "classes": 0,
        "teachers": 0,
        "students": 0,
        "courses": 0,
        "experiments": 0,
        "submissions": 0,
        "submission_pdfs": 0,
        "resources": 0,
        "attachments": 0,
        "operation_logs": 0,
        "kv_keys": 0,
    }

    for item in _normalize_list(user_registry.get("classes")):
        name = _normalize_text(item.get("name"))
        created_by = _normalize_text(item.get("created_by")) or "system"
        if not name:
            continue
        class_id = _normalize_text(item.get("id")) or _stable_id("class", f"{created_by}:{name.lower()}")
        payload = {
            "id": class_id,
            "name": name,
            "created_by": created_by,
            "created_at": _parse_datetime(item.get("created_at")) or datetime.now(),
        }
        await user_repo.upsert_class(payload)
        counters["classes"] += 1

    for item in _normalize_list(user_registry.get("teachers")):
        username = _normalize_text(item.get("username"))
        if not username:
            continue
        payload = {
            "id": _stable_id("teacher", username),
            "username": username,
            "role": "teacher",
            "real_name": _normalize_text(item.get("real_name")) or username,
            "created_by": _normalize_text(item.get("created_by")) or "system",
            "created_at": _parse_datetime(item.get("created_at")) or datetime.now(),
            "updated_at": datetime.now(),
            "extra": {},
        }
        await user_repo.upsert_user(payload)
        counters["teachers"] += 1

    for item in _normalize_list(user_registry.get("students")):
        student_id = _normalize_text(item.get("student_id"))
        username = _normalize_text(item.get("username")) or student_id
        if not student_id or not username:
            continue
        payload = {
            "id": _stable_id("student", student_id),
            "username": username,
            "role": _normalize_text(item.get("role")) or "student",
            "real_name": _normalize_text(item.get("real_name")) or username,
            "student_id": student_id,
            "class_name": _normalize_text(item.get("class_name")),
            "admission_year": _normalize_text(item.get("admission_year")),
            "organization": _normalize_text(item.get("organization")),
            "phone": _normalize_text(item.get("phone")),
            "password_hash": _normalize_text(item.get("password_hash")),
            "security_question": _normalize_text(item.get("security_question")),
            "security_answer_hash": _normalize_text(item.get("security_answer_hash")),
            "created_by": _normalize_text(item.get("created_by")),
            "created_at": _parse_datetime(item.get("created_at")) or datetime.now(),
            "updated_at": _parse_datetime(item.get("updated_at")) or datetime.now(),
            "extra": {},
        }
        await user_repo.upsert_user(payload)
        counters["students"] += 1

    account_password_hashes = _normalize_dict(user_registry.get("account_password_hashes"))
    account_security_questions = _normalize_dict(user_registry.get("account_security_questions"))

    for item in _normalize_list(course_registry.get("courses")):
        name = _normalize_text(item.get("name"))
        created_by = _normalize_text(item.get("created_by"))
        if not name:
            continue
        course_id = _normalize_text(item.get("id")) or _stable_id("course", f"{created_by}:{name.lower()}")
        payload = {
            "id": course_id,
            "name": name,
            "description": _normalize_text(item.get("description")),
            "created_by": created_by or "system",
            "created_at": _parse_datetime(item.get("created_at")) or datetime.now(),
            "updated_at": _parse_datetime(item.get("updated_at")) or datetime.now(),
        }
        await course_repo.upsert(payload)
        counters["courses"] += 1

    for item in _normalize_list(experiment_registry.get("experiments")):
        title = _normalize_text(item.get("title"))
        created_by = _normalize_text(item.get("created_by"))
        notebook_path = _normalize_text(item.get("notebook_path"))
        if not title:
            continue
        experiment_id = _normalize_text(item.get("id")) or _stable_id(
            "experiment", notebook_path or f"{created_by}:{title.lower()}"
        )
        payload = {
            "id": experiment_id,
            "course_id": _normalize_text(item.get("course_id")) or None,
            "course_name": _normalize_text(item.get("course_name")),
            "title": title,
            "description": _normalize_text(item.get("description")),
            "difficulty": _normalize_text(item.get("difficulty")),
            "tags": _normalize_list(item.get("tags")),
            "notebook_path": notebook_path,
            "resources": _normalize_dict(item.get("resources")),
            "deadline": _parse_datetime(item.get("deadline")),
            "created_at": _parse_datetime(item.get("created_at")) or datetime.now(),
            "updated_at": datetime.now(),
            "created_by": created_by or "system",
            "published": bool(item.get("published", True)),
            "publish_scope": _normalize_text(item.get("publish_scope")) or "all",
            "target_class_names": _normalize_list(item.get("target_class_names")),
            "target_student_ids": _normalize_list(item.get("target_student_ids")),
            "extra": {},
        }
        await experiment_repo.upsert(payload)
        counters["experiments"] += 1

    for item in _normalize_list(student_submission_registry.get("items")):
        submission_id = _normalize_text(item.get("id")) or _stable_id(
            "submission",
            f"{_normalize_text(item.get('experiment_id'))}:{_normalize_text(item.get('student_id'))}:{_normalize_text(item.get('start_time'))}",
        )
        experiment_id = _normalize_text(item.get("experiment_id"))
        student_id = _normalize_text(item.get("student_id"))
        if not submission_id or not experiment_id or not student_id:
            continue
        payload = {
            "id": submission_id,
            "experiment_id": experiment_id,
            "student_id": student_id,
            "status": _normalize_text(item.get("status")),
            "start_time": _parse_datetime(item.get("start_time")),
            "submit_time": _parse_datetime(item.get("submit_time")),
            "notebook_content": _normalize_text(item.get("notebook_content")),
            "score": item.get("score"),
            "ai_feedback": _normalize_text(item.get("ai_feedback")),
            "teacher_comment": _normalize_text(item.get("teacher_comment")),
            "created_at": _parse_datetime(item.get("created_at")) or datetime.now(),
            "updated_at": _parse_datetime(item.get("updated_at")) or datetime.now(),
            "extra": {},
        }
        await submission_repo.upsert(payload)
        counters["submissions"] += 1

    for item in _normalize_list(submission_pdf_registry.get("items")):
        pdf_id = _normalize_text(item.get("id")) or _stable_id(
            "submission_pdf",
            f"{_normalize_text(item.get('student_exp_id'))}:{_normalize_text(item.get('filename'))}:{_normalize_text(item.get('created_at'))}",
        )
        submission_id = _normalize_text(item.get("student_exp_id"))
        if not pdf_id or not submission_id:
            continue
        payload = {
            "id": pdf_id,
            "submission_id": submission_id,
            "experiment_id": _normalize_text(item.get("experiment_id")),
            "student_id": _normalize_text(item.get("student_id")),
            "filename": _normalize_text(item.get("filename")),
            "file_path": _normalize_text(item.get("file_path")),
            "content_type": _normalize_text(item.get("content_type")),
            "size": int(item.get("size") or 0),
            "viewed": bool(item.get("viewed", False)),
            "viewed_at": _parse_datetime(item.get("viewed_at")),
            "viewed_by": _normalize_text(item.get("viewed_by")),
            "reviewed": bool(item.get("reviewed", False)),
            "reviewed_at": _parse_datetime(item.get("reviewed_at")),
            "reviewed_by": _normalize_text(item.get("reviewed_by")),
            "annotations": _normalize_list(item.get("annotations")),
            "created_at": _parse_datetime(item.get("created_at")) or datetime.now(),
            "updated_at": _parse_datetime(item.get("updated_at")) or datetime.now(),
        }
        await submission_pdf_repo.upsert(payload)
        counters["submission_pdfs"] += 1

    for item in _normalize_list(resource_registry.get("items")):
        resource_id = _normalize_text(item.get("id")) or _stable_id(
            "resource", f"{_normalize_text(item.get('filename'))}:{_normalize_text(item.get('file_path'))}"
        )
        payload = {
            "id": resource_id,
            "filename": _normalize_text(item.get("filename")),
            "file_path": _normalize_text(item.get("file_path")),
            "file_type": _normalize_text(item.get("file_type")),
            "content_type": _normalize_text(item.get("content_type")),
            "size": int(item.get("size") or 0),
            "created_by": _normalize_text(item.get("created_by")),
            "created_at": _parse_datetime(item.get("created_at")) or datetime.now(),
            "updated_at": _parse_datetime(item.get("updated_at")) or datetime.now(),
        }
        await resource_repo.upsert(payload)
        counters["resources"] += 1

    for item in _normalize_list(attachment_registry.get("items")):
        attachment_id = _normalize_text(item.get("id")) or _stable_id(
            "attachment",
            f"{_normalize_text(item.get('experiment_id'))}:{_normalize_text(item.get('filename'))}:{_normalize_text(item.get('file_path'))}",
        )
        payload = {
            "id": attachment_id,
            "experiment_id": _normalize_text(item.get("experiment_id")),
            "filename": _normalize_text(item.get("filename")),
            "file_path": _normalize_text(item.get("file_path")),
            "content_type": _normalize_text(item.get("content_type")),
            "size": int(item.get("size") or 0),
            "created_at": _parse_datetime(item.get("created_at")) or datetime.now(),
            "updated_at": _parse_datetime(item.get("updated_at")) or datetime.now(),
        }
        if not payload["experiment_id"]:
            continue
        await attachment_repo.upsert(payload)
        counters["attachments"] += 1

    for item in _normalize_list(operation_log.get("items")):
        log_id = _normalize_text(item.get("id")) or _stable_id(
            "operation_log",
            f"{_normalize_text(item.get('operator'))}:{_normalize_text(item.get('action'))}:{_normalize_text(item.get('created_at'))}",
        )
        payload = {
            "id": log_id,
            "operator": _normalize_text(item.get("operator")) or "system",
            "action": _normalize_text(item.get("action")) or "unknown",
            "target": _normalize_text(item.get("target")),
            "detail": _normalize_text(item.get("detail")),
            "success": bool(item.get("success", True)),
            "created_at": _parse_datetime(item.get("created_at")) or datetime.now(),
        }
        await operation_log_repo.upsert(payload)
        counters["operation_logs"] += 1

    await kv_repo.upsert("account_password_hashes", account_password_hashes)
    await kv_repo.upsert("account_security_questions", account_security_questions)
    await kv_repo.upsert("ai_shared_config", _normalize_dict(ai_shared_config))
    await kv_repo.upsert("ai_chat_history", _normalize_dict(ai_chat_history))
    await kv_repo.upsert("resource_policy", _normalize_dict(resource_policy))
    counters["kv_keys"] += 5

    return counters

