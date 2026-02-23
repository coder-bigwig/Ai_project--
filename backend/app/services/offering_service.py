from __future__ import annotations

import random
import re
import string
import uuid
from datetime import datetime
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..repositories import (
    CourseMemberRepository,
    CourseOfferingRepository,
    CourseRepository,
    CourseStudentMembershipRepository,
    ExperimentRepository,
)
from .identity_service import ensure_student_user, ensure_teacher_or_admin, normalize_text, resolve_user_role
from .membership_consistency_service import reconcile_membership_consistency

ALLOWED_MEMBER_ROLES = {"teacher", "ta", "student"}
ALLOWED_OFFERING_STATUS = {"active", "archived"}
JOIN_CODE_ALPHABET = string.ascii_uppercase + string.digits
JOIN_CODE_PATTERN = re.compile(r"^[A-Z0-9]{6,8}$")
MEMBER_ROLE_ORDER = {"teacher": 0, "ta": 1, "student": 2, "admin": 3}


class OfferingService:
    def __init__(self, main_module, db: Optional[AsyncSession] = None):
        if db is None:
            raise HTTPException(status_code=503, detail="PostgreSQL session unavailable")
        self.main = main_module
        self.db = db

    async def _commit(self):
        try:
            await self.db.commit()
        except Exception as exc:
            await self.db.rollback()
            raise HTTPException(status_code=500, detail="failed to persist offering changes") from exc

    def _normalize_offering_code(self, value: Any) -> str:
        return normalize_text(value)

    def _normalize_join_code(self, value: Any) -> str:
        return normalize_text(value).upper()

    def _random_join_code(self, length: int = 6) -> str:
        rng = random.SystemRandom()
        return "".join(rng.choice(JOIN_CODE_ALPHABET) for _ in range(length))

    async def _resolve_join_code(self, offering_repo: CourseOfferingRepository, provided_join_code: Any) -> str:
        normalized = self._normalize_join_code(provided_join_code)
        if normalized:
            if not JOIN_CODE_PATTERN.fullmatch(normalized):
                raise HTTPException(status_code=400, detail="join_code must be 6-8 uppercase letters or digits")
            if await offering_repo.get_by_join_code(normalized):
                raise HTTPException(status_code=409, detail="join_code already exists")
            return normalized

        for _ in range(128):
            candidate = self._random_join_code(length=6)
            if await offering_repo.get_by_join_code(candidate) is None:
                return candidate
        raise HTTPException(status_code=500, detail="failed to generate unique join_code")

    async def _resolve_offering_code(self, offering_repo: CourseOfferingRepository, provided_offering_code: Any) -> str:
        normalized = self._normalize_offering_code(provided_offering_code)
        if normalized:
            if await offering_repo.get_by_code(normalized):
                raise HTTPException(status_code=409, detail="offering_code already exists")
            return normalized

        for _ in range(128):
            candidate = f"OFF-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"
            if await offering_repo.get_by_code(candidate) is None:
                return candidate
        raise HTTPException(status_code=500, detail="failed to generate unique offering_code")

    def _offering_payload(self, offering, course=None, member=None) -> dict[str, Any]:
        return {
            "offering_id": offering.id,
            "template_course_id": offering.template_course_id,
            "offering_code": offering.offering_code,
            "join_code": offering.join_code,
            "term": offering.term or "",
            "major": offering.major or "",
            "class_name": offering.class_name,
            "status": offering.status or "active",
            "created_by": offering.created_by or "",
            "created_at": offering.created_at,
            "updated_at": offering.updated_at,
            "template_course_name": course.name if course else "",
            "template_course_description": (course.description or "") if course else "",
            "member_role": (member.role or "") if member else "",
            "member_status": (member.status or "") if member else "",
        }

    def _member_payload(self, member) -> dict[str, Any]:
        return {
            "id": member.id,
            "offering_id": member.offering_id,
            "user_key": member.user_key,
            "role": member.role,
            "status": member.status,
            "join_at": member.join_at,
            "leave_at": member.leave_at,
        }

    def _to_student_record(self, row):
        student_id = row.student_id or row.username
        return self.main.StudentRecord(
            student_id=student_id,
            username=row.username,
            real_name=row.real_name or student_id,
            class_name=row.class_name or "",
            admission_year=row.admission_year or "",
            organization=row.organization or "",
            phone=row.phone or "",
            role="student",
            created_by=row.created_by or "",
            password_hash=row.password_hash or self.main._hash_password(self.main.DEFAULT_PASSWORD),
            security_question=row.security_question or "",
            security_answer_hash=row.security_answer_hash or "",
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def _to_experiment_model(self, row):
        difficulty = row.difficulty or self.main.DifficultyLevel.BEGINNER.value
        publish_scope = row.publish_scope or self.main.PublishScope.ALL.value
        try:
            difficulty = self.main.DifficultyLevel(difficulty)
        except ValueError:
            difficulty = self.main.DifficultyLevel.BEGINNER
        try:
            publish_scope = self.main.PublishScope(publish_scope)
        except ValueError:
            publish_scope = self.main.PublishScope.ALL
        return self.main.Experiment(
            id=row.id,
            course_id=row.course_id,
            course_name=row.course_name or "",
            title=row.title,
            description=row.description or "",
            difficulty=difficulty,
            tags=list(row.tags or []),
            notebook_path=row.notebook_path or "",
            resources=dict(row.resources or {}),
            deadline=row.deadline,
            created_at=row.created_at,
            created_by=row.created_by,
            published=bool(row.published),
            publish_scope=publish_scope,
            target_class_names=list(row.target_class_names or []),
            target_student_ids=list(row.target_student_ids or []),
        )

    async def _resolve_student_keys(self, student_key: str) -> tuple[str, list[str], Any]:
        row = await ensure_student_user(self.db, student_key)
        canonical = normalize_text(row.student_id or row.username)
        candidates = []
        for item in [canonical, normalize_text(row.username), normalize_text(student_key)]:
            if item and item not in candidates:
                candidates.append(item)
        return canonical, candidates, row

    async def _ensure_offering_manager(self, offering_id: str, teacher_id: str):
        normalized_teacher, role = await ensure_teacher_or_admin(self.db, teacher_id)
        offering_repo = CourseOfferingRepository(self.db)
        member_repo = CourseMemberRepository(self.db)
        offering = await offering_repo.get(offering_id)
        if offering is None:
            raise HTTPException(status_code=404, detail="offering not found")
        if role == "admin":
            return offering, normalized_teacher
        member = await member_repo.get_by_offering_and_user(offering_id, normalized_teacher)
        member_role = normalize_text(member.role).lower() if member else ""
        member_status = normalize_text(member.status).lower() if member else ""
        if member and member_role in {"teacher", "ta"} and member_status == "active":
            return offering, normalized_teacher
        if normalize_text(offering.created_by) == normalized_teacher:
            return offering, normalized_teacher
        raise HTTPException(status_code=403, detail="permission denied for this offering")

    async def _hydrate_offerings(self, offerings, member_map: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        if not offerings:
            return []
        template_ids = {item.template_course_id for item in offerings if item and item.template_course_id}
        course_rows = await CourseRepository(self.db).list_all()
        course_map = {item.id: item for item in course_rows if item.id in template_ids}
        payload = []
        for item in offerings:
            member = member_map.get(item.id) if member_map else None
            payload.append(self._offering_payload(item, course=course_map.get(item.template_course_id), member=member))
        payload.sort(key=lambda row: row.get("updated_at") or row.get("created_at") or datetime.min, reverse=True)
        return payload

    async def _collect_member_rows(self, offering_id: str):
        rows = await CourseMemberRepository(self.db).list_by_offering(offering_id)
        return sorted(
            rows,
            key=lambda item: (
                MEMBER_ROLE_ORDER.get(normalize_text(item.role).lower(), 9),
                normalize_text(item.user_key).lower(),
            ),
        )

    def _assert_offering_active(self, offering) -> None:
        if normalize_text(offering.status).lower() != "active":
            raise HTTPException(status_code=400, detail="offering is not active")

    async def _upsert_course_student_membership(self, course_id: str, student_id: str, added_by: str = "") -> None:
        normalized_course_id = normalize_text(course_id)
        normalized_student_id = normalize_text(student_id)
        if not normalized_course_id or not normalized_student_id:
            return
        repo = CourseStudentMembershipRepository(self.db)
        existing = await repo.get_by_course_and_student(normalized_course_id, normalized_student_id)
        now = datetime.now()
        if existing is None:
            await repo.create(
                {
                    "id": str(uuid.uuid4()),
                    "course_id": normalized_course_id,
                    "student_id": normalized_student_id,
                    "added_by": normalize_text(added_by),
                    "created_at": now,
                    "updated_at": now,
                }
            )
            return
        if normalize_text(added_by):
            existing.added_by = normalize_text(added_by)
        existing.updated_at = now

    async def _cleanup_course_student_membership(self, course_id: str, student_id: str) -> None:
        normalized_course_id = normalize_text(course_id)
        normalized_student_id = normalize_text(student_id)
        if not normalized_course_id or not normalized_student_id:
            return

        member_repo = CourseMemberRepository(self.db)
        offering_repo = CourseOfferingRepository(self.db)
        member_rows = await member_repo.list_by_user(normalized_student_id)
        active_student_rows = [
            item
            for item in member_rows
            if normalize_text(item.role).lower() == "student"
            and normalize_text(item.status).lower() == "active"
        ]

        if active_student_rows:
            offering_ids = [item.offering_id for item in active_student_rows if normalize_text(item.offering_id)]
            offerings = await offering_repo.list_by_ids(offering_ids)
            has_same_course_active = any(normalize_text(item.template_course_id) == normalized_course_id for item in offerings)
            if has_same_course_active:
                return

        course_student_repo = CourseStudentMembershipRepository(self.db)
        record = await course_student_repo.get_by_course_and_student(normalized_course_id, normalized_student_id)
        if record is not None:
            await course_student_repo.delete_record(record)

    async def create_offering(
        self,
        teacher_id: str,
        template_course_id: str,
        offering_code: str | None = None,
        term: str = "",
        major: str = "",
        class_name: str | None = None,
        join_code: str | None = None,
    ) -> dict[str, Any]:
        normalized_teacher, role = await ensure_teacher_or_admin(self.db, teacher_id)
        normalized_course_id = normalize_text(template_course_id)
        normalized_class_name = normalize_text(class_name)
        if not normalized_course_id:
            raise HTTPException(status_code=400, detail="template_course_id is required")
        if not normalized_class_name:
            raise HTTPException(status_code=400, detail="class_name is required")

        course_repo = CourseRepository(self.db)
        course = await course_repo.get(normalized_course_id)
        if course is None:
            raise HTTPException(status_code=404, detail="template course not found")
        if role != "admin" and normalize_text(course.created_by) != normalized_teacher:
            raise HTTPException(status_code=403, detail="only the owner can open offerings from this template course")

        offering_repo = CourseOfferingRepository(self.db)
        normalized_offering_code = await self._resolve_offering_code(offering_repo, provided_offering_code=offering_code)
        # Always use system-generated join codes so each class has an independent random code.
        normalized_join_code = await self._resolve_join_code(offering_repo, provided_join_code=None)

        now = datetime.now()
        offering = await offering_repo.create(
            {
                "id": str(uuid.uuid4()),
                "template_course_id": normalized_course_id,
                "offering_code": normalized_offering_code,
                "join_code": normalized_join_code,
                "term": normalize_text(term),
                "major": normalize_text(major),
                "class_name": normalized_class_name,
                "created_by": normalized_teacher,
                "status": "active",
                "created_at": now,
                "updated_at": now,
            }
        )
        # Ensure the parent row exists before inserting members in the same transaction.
        await self.db.flush()
        member = await CourseMemberRepository(self.db).create(
            {
                "id": str(uuid.uuid4()),
                "offering_id": offering.id,
                "user_key": normalized_teacher,
                "role": "teacher",
                "status": "active",
                "join_at": now,
                "leave_at": None,
            }
        )
        # Backfill existing course-level students into this newly created class offering.
        await reconcile_membership_consistency(
            self.db,
            course_id=normalized_course_id,
        )
        await self._commit()
        return self._offering_payload(offering, course=course, member=member)

    async def update_offering_status(self, teacher_id: str, offering_id: str, status: str) -> dict[str, Any]:
        offering, _ = await self._ensure_offering_manager(offering_id=offering_id, teacher_id=teacher_id)
        normalized_status = normalize_text(status).lower()
        if normalized_status not in ALLOWED_OFFERING_STATUS:
            raise HTTPException(status_code=400, detail="status only supports active or archived")
        offering.status = normalized_status
        offering.updated_at = datetime.now()
        await self._commit()
        hydrated = await self._hydrate_offerings([offering])
        return hydrated[0] if hydrated else self._offering_payload(offering)

    async def remove_offering(self, teacher_id: str, offering_id: str) -> dict[str, Any]:
        offering, _ = await self._ensure_offering_manager(offering_id=offering_id, teacher_id=teacher_id)
        member_repo = CourseMemberRepository(self.db)
        student_member_rows = [
            item
            for item in await member_repo.list_by_offering(offering.id)
            if normalize_text(item.role).lower() == "student" and normalize_text(item.status).lower() == "active"
        ]
        student_ids = []
        for item in student_member_rows:
            student_id = normalize_text(item.user_key)
            if student_id and student_id not in student_ids:
                student_ids.append(student_id)

        deleted = await CourseOfferingRepository(self.db).delete(offering.id)
        if deleted is None:
            raise HTTPException(status_code=404, detail="offering not found")
        await self.db.flush()

        for student_id in student_ids:
            await self._cleanup_course_student_membership(
                course_id=offering.template_course_id,
                student_id=student_id,
            )

        await self._commit()
        return {
            "message": "offering removed",
            "offering_id": offering.id,
            "removed_student_count": len(student_ids),
        }

    async def get_teacher_offering_detail(self, teacher_id: str, offering_id: str) -> dict[str, Any]:
        offering, _ = await self._ensure_offering_manager(offering_id=offering_id, teacher_id=teacher_id)
        course = await CourseRepository(self.db).get(offering.template_course_id)
        payload = self._offering_payload(offering, course=course)
        members = await self._collect_member_rows(offering_id=offering_id)
        payload["members"] = [self._member_payload(item) for item in members]
        return payload

    async def list_teacher_offering_members(self, teacher_id: str, offering_id: str) -> list[dict[str, Any]]:
        await self._ensure_offering_manager(offering_id=offering_id, teacher_id=teacher_id)
        members = await self._collect_member_rows(offering_id=offering_id)
        return [self._member_payload(item) for item in members]

    async def add_members(self, teacher_id: str, offering_id: str, members: list[dict[str, Any]]) -> dict[str, Any]:
        offering, normalized_teacher = await self._ensure_offering_manager(offering_id=offering_id, teacher_id=teacher_id)
        member_repo = CourseMemberRepository(self.db)
        updated_rows = []
        now = datetime.now()
        for item in members or []:
            user_key = normalize_text((item or {}).get("user_key"))
            role = normalize_text((item or {}).get("role")).lower()
            if not user_key:
                continue
            if role not in ALLOWED_MEMBER_ROLES:
                raise HTTPException(status_code=400, detail=f"unsupported member role: {role}")
            if role == "student":
                canonical_student_key, _, _ = await self._resolve_student_keys(user_key)
                user_key = canonical_student_key
            elif role in {"teacher", "ta"}:
                target_role = await resolve_user_role(self.db, user_key)
                if target_role not in {"teacher", "admin"}:
                    raise HTTPException(status_code=404, detail=f"teacher account not found: {user_key}")
            existing = await member_repo.get_by_offering_and_user(offering_id, user_key)
            if existing is None:
                existing = await member_repo.create(
                    {
                        "id": str(uuid.uuid4()),
                        "offering_id": offering_id,
                        "user_key": user_key,
                        "role": role,
                        "status": "active",
                        "join_at": now,
                        "leave_at": None,
                    }
                )
            else:
                existing.role = role
                existing.status = "active"
                existing.join_at = now
                existing.leave_at = None
            if role == "student":
                await self._upsert_course_student_membership(
                    course_id=offering.template_course_id,
                    student_id=user_key,
                    added_by=normalized_teacher,
                )
            updated_rows.append(existing)
        offering.updated_at = datetime.now()
        await self._commit()
        hydrated = await self._hydrate_offerings([offering])
        return {
            "offering": hydrated[0] if hydrated else self._offering_payload(offering),
            "members": [self._member_payload(item) for item in updated_rows],
        }

    async def remove_member(self, teacher_id: str, offering_id: str, user_key: str) -> dict[str, Any]:
        offering, normalized_teacher = await self._ensure_offering_manager(offering_id=offering_id, teacher_id=teacher_id)
        normalized_user_key = normalize_text(user_key)
        if not normalized_user_key:
            raise HTTPException(status_code=400, detail="user_key is required")

        member_repo = CourseMemberRepository(self.db)
        member = await member_repo.get_by_offering_and_user(offering_id, normalized_user_key)
        if member is None:
            # For students, callers may pass username or student_id; try aliases if possible.
            try:
                _, candidate_keys, _ = await self._resolve_student_keys(normalized_user_key)
            except HTTPException:
                candidate_keys = [normalized_user_key]
            for item in candidate_keys:
                member = await member_repo.get_by_offering_and_user(offering_id, item)
                if member is not None:
                    break
        if member is None:
            raise HTTPException(status_code=404, detail="member not found in offering")

        target_user_key = normalize_text(member.user_key)
        if target_user_key == normalized_teacher:
            raise HTTPException(status_code=400, detail="cannot remove yourself from offering")
        if normalize_text(offering.created_by) == target_user_key:
            raise HTTPException(status_code=400, detail="cannot remove offering creator")

        if normalize_text(member.status).lower() == "removed":
            return {
                "message": "member already removed",
                "offering_id": offering_id,
                "user_key": target_user_key,
            }

        member.status = "removed"
        member.leave_at = datetime.now()
        if normalize_text(member.role).lower() == "student":
            await self._cleanup_course_student_membership(
                course_id=offering.template_course_id,
                student_id=target_user_key,
            )
        offering.updated_at = datetime.now()
        await self._commit()
        return {
            "message": "member removed",
            "offering_id": offering_id,
            "user_key": target_user_key,
            "status": member.status,
        }

    async def join(self, offering_id: str, student_key: str, require_active: bool = False) -> dict[str, Any]:
        offering = await CourseOfferingRepository(self.db).get(offering_id)
        if offering is None:
            raise HTTPException(status_code=404, detail="offering not found")
        if require_active:
            self._assert_offering_active(offering)

        canonical_student_key, candidate_keys, _ = await self._resolve_student_keys(student_key)
        member_repo = CourseMemberRepository(self.db)
        existing = None
        for key in candidate_keys:
            existing = await member_repo.get_by_offering_and_user(offering_id, key)
            if existing is not None:
                break

        now = datetime.now()
        changed = False
        if existing is None:
            existing = await member_repo.create(
                {
                    "id": str(uuid.uuid4()),
                    "offering_id": offering_id,
                    "user_key": canonical_student_key,
                    "role": "student",
                    "status": "active",
                    "join_at": now,
                    "leave_at": None,
                }
            )
            changed = True
        else:
            if existing.user_key != canonical_student_key:
                existing.user_key = canonical_student_key
                changed = True
            if normalize_text(existing.role).lower() != "student":
                existing.role = "student"
                changed = True
            existing_status = normalize_text(existing.status).lower()
            if existing_status != "active":
                existing.status = "active"
                existing.join_at = now
                existing.leave_at = None
                changed = True
            elif existing.leave_at is not None:
                existing.leave_at = None
                changed = True

        if changed:
            await self._upsert_course_student_membership(
                course_id=offering.template_course_id,
                student_id=canonical_student_key,
                added_by=canonical_student_key,
            )
            offering.updated_at = now
            await self._commit()

        hydrated = await self._hydrate_offerings([offering], member_map={offering.id: existing})
        payload = hydrated[0] if hydrated else self._offering_payload(offering, member=existing)
        payload["join_result"] = "joined" if changed else "already_joined"
        return payload

    async def join_by_code(self, student_key: str, join_code: str) -> dict[str, Any]:
        normalized_code = self._normalize_join_code(join_code)
        if not normalized_code:
            raise HTTPException(status_code=400, detail="join_code is required")
        offering = await CourseOfferingRepository(self.db).get_by_join_code(normalized_code)
        if offering is None:
            raise HTTPException(status_code=404, detail="join_code not found")
        self._assert_offering_active(offering)
        return await self.join(offering_id=offering.id, student_key=student_key, require_active=True)

    async def leave(self, offering_id: str, student_key: str) -> dict[str, Any]:
        offering = await CourseOfferingRepository(self.db).get(offering_id)
        if offering is None:
            raise HTTPException(status_code=404, detail="offering not found")

        canonical_student_key, candidate_keys, _ = await self._resolve_student_keys(student_key)
        member_repo = CourseMemberRepository(self.db)
        member = None
        for key in candidate_keys:
            member = await member_repo.get_by_offering_and_user(offering_id, key)
            if member is not None:
                break
        if member is None:
            raise HTTPException(status_code=404, detail="member not found in offering")

        member.user_key = canonical_student_key
        member.role = "student"
        member.status = "left"
        member.leave_at = datetime.now()
        await self._cleanup_course_student_membership(
            course_id=offering.template_course_id,
            student_id=canonical_student_key,
        )
        offering.updated_at = datetime.now()
        await self._commit()
        hydrated = await self._hydrate_offerings([offering], member_map={offering.id: member})
        return hydrated[0] if hydrated else self._offering_payload(offering, member=member)

    async def list_teacher_offerings(self, teacher_id: str) -> list[dict[str, Any]]:
        normalized_teacher, _ = await ensure_teacher_or_admin(self.db, teacher_id)
        member_rows = await CourseMemberRepository(self.db).list_by_user(normalized_teacher)
        filtered_members = [
            item
            for item in member_rows
            if normalize_text(item.role).lower() in {"teacher", "ta"}
            and normalize_text(item.status).lower() == "active"
        ]
        offering_ids = [item.offering_id for item in filtered_members if item.offering_id]
        offerings = [
            item
            for item in await CourseOfferingRepository(self.db).list_by_ids(offering_ids)
            if normalize_text(item.status).lower() == "active" and normalize_text(item.class_name)
        ]
        valid_offering_ids = {item.id for item in offerings}
        member_map = {item.offering_id: item for item in filtered_members if item.offering_id in valid_offering_ids}
        return await self._hydrate_offerings(offerings, member_map=member_map)

    async def list_student_offerings(self, student_key: str) -> list[dict[str, Any]]:
        canonical_student_key, candidate_keys, _ = await self._resolve_student_keys(student_key)
        member_rows = await CourseMemberRepository(self.db).list_by_users(candidate_keys)
        filtered_members = [
            item
            for item in member_rows
            if normalize_text(item.role).lower() == "student"
            and normalize_text(item.status).lower() in {"active", "left"}
        ]
        dedup_by_offering = {}
        for item in filtered_members:
            existing = dedup_by_offering.get(item.offering_id)
            if existing is None:
                dedup_by_offering[item.offering_id] = item
                continue
            if existing.user_key != canonical_student_key and item.user_key == canonical_student_key:
                dedup_by_offering[item.offering_id] = item

        chosen_members = list(dedup_by_offering.values())
        offering_ids = [item.offering_id for item in chosen_members if item.offering_id]
        offerings = await CourseOfferingRepository(self.db).list_by_ids(offering_ids)
        member_map = {item.offering_id: item for item in chosen_members}
        return await self._hydrate_offerings(offerings, member_map=member_map)

    async def list_offering_experiments(self, offering_id: str, student_key: str):
        offering = await CourseOfferingRepository(self.db).get(offering_id)
        if offering is None:
            raise HTTPException(status_code=404, detail="offering not found")

        canonical_student_key, candidate_keys, student_row = await self._resolve_student_keys(student_key)
        member_repo = CourseMemberRepository(self.db)
        member = None
        for key in candidate_keys:
            member = await member_repo.get_by_offering_and_user(offering_id, key)
            if member is not None:
                break
        if member is None or normalize_text(member.status).lower() != "active":
            raise HTTPException(status_code=403, detail="active membership is required")

        if member.user_key != canonical_student_key:
            member.user_key = canonical_student_key

        student = self._to_student_record(student_row)
        rows = await ExperimentRepository(self.db).list_by_course_ids([offering.template_course_id])
        experiments = []
        for row in rows:
            model = self._to_experiment_model(row)
            if self.main._is_experiment_visible_to_student(model, student):
                experiments.append(model)
        experiments.sort(key=lambda item: item.created_at or datetime.min, reverse=True)
        await self._commit()
        return experiments


def build_offering_service(main_module, db: Optional[AsyncSession] = None) -> OfferingService:
    return OfferingService(main_module=main_module, db=db)
