from __future__ import annotations

import json
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from .. import config
from ..db.models import AuthUserORM, AuthUserRole
from ..repositories.password_reset_repository import PasswordResetRepository
from ..repositories.user_repository import AuthUserRepository

_IMPORT_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_DNS, "experiment-manager.auth-import.v1")


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_email(value: Any) -> str:
    return _normalize_text(value).lower()


def _load_json(path: str, default: Any) -> Any:
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


def _stable_id(prefix: str, value: str) -> str:
    raw = f"{prefix}:{value}".strip()
    return str(uuid.uuid5(_IMPORT_NAMESPACE, raw))


class AuthService:
    def __init__(
        self,
        db: AsyncSession,
        password_hasher: Callable[[str], str],
    ):
        self.db = db
        self.password_hasher = password_hasher
        self.user_repo = AuthUserRepository(db)
        self.reset_repo = PasswordResetRepository(db)

    async def get_user_by_identifier(self, identifier: str) -> AuthUserORM | None:
        return await self.user_repo.get_by_login_identifier(identifier)

    async def authenticate(self, identifier: str, password: str) -> AuthUserORM | None:
        user = await self.user_repo.get_by_login_identifier(identifier)
        if user is None or not bool(user.is_active):
            return None
        expected_hash = _normalize_text(user.password_hash)
        provided_hash = _normalize_text(self.password_hasher(password or ""))
        if not expected_hash or expected_hash != provided_hash:
            return None
        return user

    async def set_password(self, user_id: str, new_password_hash: str) -> AuthUserORM | None:
        user = await self.user_repo.get_by_id(user_id)
        if user is None:
            return None
        user.password_hash = _normalize_text(new_password_hash)
        user.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
        return user

    async def create_reset_token(self, user_id: str, ttl_minutes: int = 15) -> str:
        user = await self.user_repo.get_by_id(user_id)
        if user is None:
            raise ValueError("user not found")

        expires_at = datetime.now(timezone.utc) + timedelta(minutes=max(1, int(ttl_minutes or 15)))
        for _ in range(3):
            token = secrets.token_urlsafe(32)
            existing = await self.reset_repo.get_by_token(token)
            if existing is not None:
                continue
            payload = {
                "id": str(uuid.uuid4()),
                "user_id": user.id,
                "token": token,
                "expires_at": expires_at,
                "used_at": None,
            }
            await self.reset_repo.create(payload)
            return token
        raise RuntimeError("failed to generate unique reset token")

    async def verify_reset_token(self, token: str) -> str | None:
        record = await self.reset_repo.verify_token(token=token)
        if record is None:
            return None
        return record.user_id

    async def consume_reset_token(self, token: str) -> bool:
        user_id = await self.reset_repo.consume_token(token=token)
        return bool(user_id)


async def import_auth_users_from_upload_json(
    db: AsyncSession,
    password_hasher: Callable[[str], str],
    default_password: str,
    uploads_dir: str | None = None,
) -> dict[str, int]:
    user_registry = _load_json(_resolve_path(config.USER_REGISTRY_FILE, uploads_dir), {})
    raw_teachers = user_registry.get("teachers") if isinstance(user_registry, dict) else []
    raw_students = user_registry.get("students") if isinstance(user_registry, dict) else []
    account_hashes = user_registry.get("account_password_hashes") if isinstance(user_registry, dict) else {}

    teachers = raw_teachers if isinstance(raw_teachers, list) else []
    students = raw_students if isinstance(raw_students, list) else []
    account_hashes = account_hashes if isinstance(account_hashes, dict) else {}

    default_hash = password_hasher(default_password)
    repo = AuthUserRepository(db)

    counters = {
        "admins": 0,
        "teachers": 0,
        "students": 0,
        "created": 0,
        "updated": 0,
    }

    async def _upsert(email: str, username: str, role: AuthUserRole, password_hash: str) -> None:
        normalized_email = _normalize_email(email)
        normalized_username = _normalize_text(username)
        normalized_hash = _normalize_text(password_hash)
        if not normalized_email:
            return
        _, created = await repo.upsert_by_email(
            {
                "id": _stable_id("auth_user", f"{role.value}:{normalized_username or normalized_email}"),
                "email": normalized_email,
                "username": normalized_username or None,
                "role": role,
                "password_hash": normalized_hash,
                "is_active": True,
                "updated_at": datetime.now(timezone.utc),
            }
        )
        counters["created" if created else "updated"] += 1

    for admin_username in config.ADMIN_ACCOUNTS:
        username = _normalize_text(admin_username)
        if not username:
            continue
        saved_hash = _normalize_text(account_hashes.get(username)) or default_hash
        await _upsert(email=username, username=username, role=AuthUserRole.admin, password_hash=saved_hash)
        counters["admins"] += 1

    teacher_names = {_normalize_text(item) for item in config.TEACHER_ACCOUNTS if _normalize_text(item)}
    for row in teachers:
        if not isinstance(row, dict):
            continue
        username = _normalize_text(row.get("username"))
        if username:
            teacher_names.add(username)

    for username in sorted(teacher_names):
        saved_hash = _normalize_text(account_hashes.get(username)) or default_hash
        await _upsert(email=username, username=username, role=AuthUserRole.teacher, password_hash=saved_hash)
        counters["teachers"] += 1

    for row in students:
        if not isinstance(row, dict):
            continue
        username = _normalize_text(row.get("username")) or _normalize_text(row.get("student_id"))
        if not username:
            continue
        saved_hash = _normalize_text(row.get("password_hash")) or default_hash
        await _upsert(email=username, username=username, role=AuthUserRole.student, password_hash=saved_hash)
        counters["students"] += 1

    return counters
