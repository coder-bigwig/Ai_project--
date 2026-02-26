from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from ..file_storage import remove_legacy_file
from ..repositories import (
    AttachmentRepository,
    CourseMemberRepository,
    CourseOfferingRepository,
    CourseRepository,
    ExperimentRepository,
    SubmissionPdfRepository,
    UserRepository,
)
from .identity_service import ensure_teacher_or_admin, normalize_text, resolve_user_role


class ExperimentService:
    RECYCLE_RETENTION_DAYS = 30

    def __init__(self, main_module, db: Optional[AsyncSession] = None):
        if db is None:
            raise HTTPException(status_code=503, detail="PostgreSQL session unavailable")
        self.main = main_module
        self.db = db

    @staticmethod
    def _safe_datetime(value, fallback: datetime | None = None) -> datetime | None:
        if isinstance(value, datetime):
            return value
        return fallback

    @staticmethod
    def _to_utc_datetime(value: datetime | None) -> datetime | None:
        if not isinstance(value, datetime):
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

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
            password_hash=row.password_hash or self.main._default_password_hash(role="student"),
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
            description=row.description or None,
            difficulty=difficulty,
            tags=list(row.tags or []),
            notebook_path=row.notebook_path or None,
            resources=dict(row.resources or {}),
            deadline=row.deadline,
            created_at=row.created_at,
            created_by=row.created_by,
            published=bool(row.published),
            publish_scope=publish_scope,
            target_class_names=list(row.target_class_names or []),
            target_student_ids=list(row.target_student_ids or []),
        )

    def _to_recycle_payload(self, row) -> dict:
        deleted_at = self._safe_datetime(getattr(row, "deleted_at", None))
        expires_at = deleted_at + timedelta(days=self.RECYCLE_RETENTION_DAYS) if deleted_at else None
        return {
            "id": row.id,
            "title": row.title,
            "description": row.description or "",
            "difficulty": row.difficulty or "",
            "course_id": row.course_id,
            "course_name": row.course_name or "",
            "published": bool(row.published),
            "created_at": row.created_at,
            "deleted_at": deleted_at,
            "expires_at": expires_at,
        }

    async def _assert_experiment_manage_permission(self, row, teacher_username: str) -> tuple[str, str]:
        normalized_teacher, role = await ensure_teacher_or_admin(self.db, teacher_username)
        if role != "admin" and normalize_text(row.created_by) != normalized_teacher:
            raise HTTPException(status_code=403, detail="鏃犳潈闄愭搷浣滆瀹為獙")
        return normalized_teacher, role

    async def _hard_delete_experiment(self, experiment_id: str):
        attachment_repo = AttachmentRepository(self.db)
        experiment_repo = ExperimentRepository(self.db)
        pdf_repo = SubmissionPdfRepository(self.db)

        attachments = await attachment_repo.list_by_experiment(experiment_id)
        removed_attachment_ids = [item.id for item in attachments]
        for item in attachments:
            remove_legacy_file(item.file_path)

        for item in await pdf_repo.list_by_experiment(experiment_id):
            remove_legacy_file(item.file_path)

        if removed_attachment_ids:
            await attachment_repo.delete_many(removed_attachment_ids)
        await experiment_repo.delete(experiment_id)

    async def _purge_expired_recycle_items(self, teacher_username: str) -> int:
        experiment_repo = ExperimentRepository(self.db)
        expire_before = datetime.now(timezone.utc) - timedelta(days=self.RECYCLE_RETENTION_DAYS)
        recycle_rows = await experiment_repo.list_recycle_by_creator(teacher_username)
        expired_rows = []
        for item in recycle_rows:
            deleted_at = self._to_utc_datetime(self._safe_datetime(item.deleted_at))
            if deleted_at and deleted_at <= expire_before:
                expired_rows.append(item)
        if not expired_rows:
            return 0

        for row in expired_rows:
            await self._hard_delete_experiment(row.id)
        return len(expired_rows)

    @staticmethod
    def _resolve_course_name(experiment) -> str:
        explicit = normalize_text(getattr(experiment, "course_name", ""))
        if explicit:
            return explicit
        notebook_path = normalize_text(getattr(experiment, "notebook_path", ""))
        first_segment = next((seg for seg in notebook_path.split("/") if seg), "")
        if first_segment and first_segment.lower() != "course":
            return first_segment
        return "Python程序设计"

    def _normalize_publish_targets(self, experiment):
        self.main._normalize_experiment_publish_targets(experiment)
        self.main._validate_experiment_publish_targets(experiment)

    def _to_experiment_payload(self, experiment: "Experiment") -> dict:
        now = datetime.now()
        created_at = self._safe_datetime(experiment.created_at, now)
        return {
            "id": experiment.id,
            "course_id": experiment.course_id,
            "course_name": experiment.course_name or "",
            "title": experiment.title,
            "description": experiment.description or "",
            "difficulty": str(getattr(experiment.difficulty, "value", experiment.difficulty or "")),
            "tags": list(experiment.tags or []),
            "notebook_path": experiment.notebook_path or "",
            "resources": dict(experiment.resources or {}),
            "deadline": self._safe_datetime(experiment.deadline),
            "created_at": created_at,
            "updated_at": now,
            "created_by": experiment.created_by,
            "published": bool(experiment.published),
            "publish_scope": str(getattr(experiment.publish_scope, "value", experiment.publish_scope or "all")),
            "target_class_names": list(experiment.target_class_names or []),
            "target_student_ids": list(experiment.target_student_ids or []),
            "extra": {},
        }

    async def _commit_pg(self):
        try:
            await self.db.commit()
        except SQLAlchemyError as exc:
            await self.db.rollback()
            raise HTTPException(status_code=500, detail="PostgreSQL写入失败") from exc

    async def _resolve_or_create_teacher_course_pg(
        self,
        teacher_username: str,
        course_name: str,
        requested_course_id: Optional[str] = None,
        actor_role: str = "teacher",
    ):
        repo = CourseRepository(self.db)
        normalized_teacher = normalize_text(teacher_username)
        normalized_name = normalize_text(course_name) or "Python程序设计"
        normalized_requested_id = normalize_text(requested_course_id)

        if normalized_requested_id:
            course = await repo.get(normalized_requested_id)
            if not course:
                raise HTTPException(status_code=404, detail="课程不存在")
            if normalize_text(course.created_by) != normalized_teacher:
                can_collaborate = (
                    actor_role == "admin"
                    or await self._has_active_course_collaboration_access(normalized_teacher, normalized_requested_id)
                )
                if can_collaborate:
                    return course
                raise HTTPException(status_code=403, detail="不能使用其他教师创建的课程")
            return course

        existing = await repo.find_by_teacher_and_name(normalized_teacher, normalized_name)
        if existing:
            return existing

        now = datetime.now()
        created = await repo.create(
            {
                "id": str(uuid.uuid4()),
                "name": normalized_name,
                "description": "",
                "created_by": normalized_teacher,
                "created_at": now,
                "updated_at": now,
            }
        )
        return created

    async def _has_active_course_collaboration_access(self, teacher_username: str, course_id: str) -> bool:
        normalized_teacher = normalize_text(teacher_username)
        normalized_course_id = normalize_text(course_id)
        if not normalized_teacher or not normalized_course_id:
            return False

        member_rows = await CourseMemberRepository(self.db).list_by_user(normalized_teacher)
        active_member_rows = [
            item
            for item in member_rows
            if normalize_text(item.role).lower() in {"teacher", "ta"}
            and normalize_text(item.status).lower() == "active"
        ]
        offering_ids = [item.offering_id for item in active_member_rows if item.offering_id]
        if not offering_ids:
            return False

        offering_rows = await CourseOfferingRepository(self.db).list_by_ids(offering_ids)
        return any(
            normalize_text(item.template_course_id) == normalized_course_id
            and normalize_text(item.status).lower() != "archived"
            for item in offering_rows
        )

    async def _find_student_row(self, username: str):
        repo = UserRepository(self.db)
        student = await repo.get_student_by_student_id(username)
        if student is not None:
            return student

        user = await repo.get_by_username(username)
        if user is None:
            return None
        if normalize_text(user.role).lower() != "student":
            return None
        return user

    async def create_experiment(self, experiment: "Experiment"):
        normalized_teacher = normalize_text(experiment.created_by)
        normalized_teacher, role = await ensure_teacher_or_admin(self.db, normalized_teacher)
        experiment.created_by = normalized_teacher

        course_row = await self._resolve_or_create_teacher_course_pg(
            normalized_teacher,
            self._resolve_course_name(experiment),
            experiment.course_id,
            actor_role=role,
        )

        experiment.id = str(uuid.uuid4())
        experiment.created_at = datetime.now()
        experiment.course_id = course_row.id
        experiment.course_name = course_row.name
        self._normalize_publish_targets(experiment)

        course_row.updated_at = experiment.created_at
        course_repo = CourseRepository(self.db)
        experiment_repo = ExperimentRepository(self.db)
        await course_repo.upsert(
            {
                "id": course_row.id,
                "name": course_row.name,
                "description": course_row.description or "",
                "created_by": course_row.created_by,
                "created_at": course_row.created_at,
                "updated_at": course_row.updated_at,
            }
        )
        await experiment_repo.upsert(self._to_experiment_payload(experiment))
        await self._commit_pg()
        return experiment

    async def list_experiments(
        self,
        difficulty: Optional["DifficultyLevel"] = None,
        tag: Optional[str] = None,
        username: Optional[str] = None,
    ):
        experiment_repo = ExperimentRepository(self.db)
        rows = await experiment_repo.list_all()
        experiments = [self._to_experiment_model(item) for item in rows]

        normalized_username = normalize_text(username)
        if normalized_username:
            role = await resolve_user_role(self.db, normalized_username)
            if role not in {"teacher", "admin"}:
                student_row = await self._find_student_row(normalized_username)
                if not student_row:
                    experiments = []
                else:
                    student = self._to_student_record(student_row)
                    experiments = [e for e in experiments if self.main._is_experiment_visible_to_student(e, student)]

        if difficulty:
            experiments = [e for e in experiments if e.difficulty == difficulty]
        if tag:
            experiments = [e for e in experiments if tag in e.tags]
        return experiments

    async def get_experiment(self, experiment_id: str):
        experiment_repo = ExperimentRepository(self.db)
        row = await experiment_repo.get(experiment_id)
        if not row:
            raise HTTPException(status_code=404, detail="实验不存在")
        return self._to_experiment_model(row)

    async def update_experiment(self, experiment_id: str, experiment: "Experiment"):
        existing_row = await ExperimentRepository(self.db).get(experiment_id)
        if not existing_row:
            raise HTTPException(status_code=404, detail="实验不存在")
        existing = self._to_experiment_model(existing_row)

        experiment.id = experiment_id
        if experiment.created_at is None:
            experiment.created_at = existing.created_at
        if not experiment.created_by:
            experiment.created_by = existing.created_by

        normalized_teacher = normalize_text(experiment.created_by)
        normalized_teacher, role = await ensure_teacher_or_admin(self.db, normalized_teacher)
        experiment.created_by = normalized_teacher

        requested_course_id = experiment.course_id or existing.course_id
        requested_course_name = self._resolve_course_name(experiment)
        if not normalize_text(experiment.course_name):
            requested_course_name = self._resolve_course_name(existing)

        course_row = await self._resolve_or_create_teacher_course_pg(
            normalized_teacher,
            requested_course_name,
            requested_course_id,
            actor_role=role,
        )

        experiment.course_id = course_row.id
        experiment.course_name = course_row.name
        self._normalize_publish_targets(experiment)

        course_row.updated_at = datetime.now()
        course_repo = CourseRepository(self.db)
        experiment_repo = ExperimentRepository(self.db)
        await course_repo.upsert(
            {
                "id": course_row.id,
                "name": course_row.name,
                "description": course_row.description or "",
                "created_by": course_row.created_by,
                "created_at": course_row.created_at,
                "updated_at": course_row.updated_at,
            }
        )
        await experiment_repo.upsert(self._to_experiment_payload(experiment))
        await self._commit_pg()
        return experiment

    async def delete_experiment(self, experiment_id: str, teacher_username: str):
        experiment_repo = ExperimentRepository(self.db)
        course_repo = CourseRepository(self.db)

        normalized_teacher = normalize_text(teacher_username)
        if not normalized_teacher:
            raise HTTPException(status_code=400, detail="teacher_username is required")

        existing = await experiment_repo.get(experiment_id, include_deleted=True)
        if existing is None:
            raise HTTPException(status_code=404, detail="experiment not found")
        await self._assert_experiment_manage_permission(existing, normalized_teacher)

        if existing.deleted_at is not None:
            return {"message": "experiment already in recycle bin", "recycle_retention_days": self.RECYCLE_RETENTION_DAYS}

        now = datetime.now(timezone.utc)
        await experiment_repo.soft_delete(experiment_id, deleted_at=now)
        existing.updated_at = now

        course_id = normalize_text(existing.course_id)
        if course_id:
            await course_repo.touch(course_id, now)

        await self._commit_pg()
        return {
            "message": "experiment deleted and moved to recycle bin",
            "recycle_retention_days": self.RECYCLE_RETENTION_DAYS,
        }

    async def list_recycle_experiments(self, teacher_username: str, course_id: Optional[str] = None):
        normalized_teacher = normalize_text(teacher_username)
        if not normalized_teacher:
            raise HTTPException(status_code=400, detail="teacher_username is required")
        await ensure_teacher_or_admin(self.db, normalized_teacher)

        await self._purge_expired_recycle_items(normalized_teacher)

        experiment_repo = ExperimentRepository(self.db)
        rows = await experiment_repo.list_recycle_by_creator(normalized_teacher)
        normalized_course_id = normalize_text(course_id)
        if normalized_course_id:
            rows = [item for item in rows if normalize_text(item.course_id) == normalized_course_id]

        return {
            "retention_days": self.RECYCLE_RETENTION_DAYS,
            "items": [self._to_recycle_payload(item) for item in rows],
        }

    async def restore_experiment(self, experiment_id: str, teacher_username: str):
        normalized_teacher = normalize_text(teacher_username)
        if not normalized_teacher:
            raise HTTPException(status_code=400, detail="teacher_username is required")

        experiment_repo = ExperimentRepository(self.db)
        course_repo = CourseRepository(self.db)
        row = await experiment_repo.get(experiment_id, include_deleted=True)
        if row is None:
            raise HTTPException(status_code=404, detail="experiment not found")
        await self._assert_experiment_manage_permission(row, normalized_teacher)

        if row.deleted_at is None:
            return {"message": "experiment is not in recycle bin"}

        expire_before = datetime.now(timezone.utc) - timedelta(days=self.RECYCLE_RETENTION_DAYS)
        row_deleted_at = self._to_utc_datetime(self._safe_datetime(row.deleted_at))
        if row_deleted_at is None:
            raise HTTPException(status_code=400, detail="invalid recycle timestamp")
        if row_deleted_at <= expire_before:
            await self._hard_delete_experiment(experiment_id)
            await self._commit_pg()
            raise HTTPException(status_code=410, detail="recycle item expired and has been purged")

        now = datetime.now(timezone.utc)
        await experiment_repo.restore(experiment_id)
        row.updated_at = now

        course_id = normalize_text(row.course_id)
        if course_id:
            await course_repo.touch(course_id, now)

        await self._commit_pg()
        return {"message": "experiment restored"}

    async def permanently_delete_experiment(self, experiment_id: str, teacher_username: str):
        normalized_teacher = normalize_text(teacher_username)
        if not normalized_teacher:
            raise HTTPException(status_code=400, detail="teacher_username is required")

        experiment_repo = ExperimentRepository(self.db)
        course_repo = CourseRepository(self.db)
        row = await experiment_repo.get(experiment_id, include_deleted=True)
        if row is None:
            raise HTTPException(status_code=404, detail="experiment not found")
        await self._assert_experiment_manage_permission(row, normalized_teacher)

        if row.deleted_at is None:
            raise HTTPException(status_code=400, detail="experiment is not in recycle bin")

        now = datetime.now(timezone.utc)
        await self._hard_delete_experiment(experiment_id)

        course_id = normalize_text(row.course_id)
        if course_id:
            await course_repo.touch(course_id, now)

        await self._commit_pg()
        return {"message": "experiment permanently deleted"}

def build_experiment_service(main_module, db: Optional[AsyncSession] = None) -> ExperimentService:
    return ExperimentService(main_module=main_module, db=db)
