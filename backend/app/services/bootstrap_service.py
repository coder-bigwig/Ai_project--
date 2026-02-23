from __future__ import annotations

import uuid
from datetime import datetime
from typing import Callable

from sqlalchemy.ext.asyncio import AsyncSession

from ..config import ADMIN_ACCOUNTS, DEFAULT_PASSWORD, TEACHER_ACCOUNTS
from ..repositories import AuthUserRepository, UserRepository
from .identity_service import normalize_text


def _stable_account_id(role: str, username: str) -> str:
    normalized_role = normalize_text(role).lower() or "student"
    normalized_username = normalize_text(username).lower()
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"builtin:{normalized_role}:{normalized_username}"))


async def ensure_builtin_accounts(
    db: AsyncSession,
    *,
    password_hasher: Callable[[str], str],
) -> dict:
    now = datetime.now()
    default_hash = normalize_text(password_hasher(DEFAULT_PASSWORD))

    auth_repo = AuthUserRepository(db)
    user_repo = UserRepository(db)

    created_auth = 0
    created_teacher_profiles = 0

    async def upsert_auth_account(username: str, role: str):
        nonlocal created_auth

        normalized_username = normalize_text(username)
        normalized_role = normalize_text(role).lower()
        if not normalized_username or normalized_role not in {"admin", "teacher"}:
            return

        existing = await auth_repo.get_by_login_identifier(normalized_username)
        created = existing is None

        await auth_repo.upsert_by_email(
            {
                "id": existing.id if existing is not None else _stable_account_id(normalized_role, normalized_username),
                "email": normalized_username,
                "username": normalized_username,
                "role": normalized_role,
                # Keep existing password hash so manual password changes survive restart.
                "password_hash": normalize_text(existing.password_hash) if existing is not None else default_hash,
                "is_active": bool(existing.is_active) if existing is not None else True,
                "created_at": existing.created_at if existing is not None else now,
                "updated_at": now,
            }
        )
        if created:
            created_auth += 1

    async def ensure_teacher_profile(username: str):
        nonlocal created_teacher_profiles

        normalized_username = normalize_text(username)
        if not normalized_username:
            return

        existing = await user_repo.get_by_username(normalized_username)
        if existing is None:
            await user_repo.create(
                {
                    "id": _stable_account_id("teacher_profile", normalized_username),
                    "username": normalized_username,
                    "role": "teacher",
                    "real_name": normalized_username,
                    "student_id": None,
                    "class_name": "",
                    "admission_year": "",
                    "organization": "",
                    "phone": "",
                    "password_hash": "",
                    "security_question": "",
                    "security_answer_hash": "",
                    "created_by": "system",
                    "is_active": True,
                    "created_at": now,
                    "updated_at": now,
                    "extra": {},
                }
            )
            created_teacher_profiles += 1
            return

        if normalize_text(existing.role).lower() == "teacher":
            existing.is_active = True
            existing.updated_at = now

    for admin_username in ADMIN_ACCOUNTS:
        await upsert_auth_account(admin_username, "admin")

    for teacher_username in TEACHER_ACCOUNTS:
        await upsert_auth_account(teacher_username, "teacher")
        await ensure_teacher_profile(teacher_username)

    await db.commit()
    return {
        "created_auth_accounts": created_auth,
        "created_teacher_profiles": created_teacher_profiles,
    }
