from datetime import datetime
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from ..repositories import AttachmentRepository, CourseRepository, ExperimentRepository, UserRepository


class ExperimentService:
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

    def _to_course_record(self, row):
        return self.main.CourseRecord(
            id=row.id,
            name=row.name,
            description=row.description or "",
            created_by=row.created_by,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

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
            course_name=row.course_name,
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

    def _to_course_payload(self, course) -> dict:
        now = datetime.now()
        return {
            "id": course.id,
            "name": course.name,
            "description": course.description or "",
            "created_by": course.created_by,
            "created_at": self._safe_datetime(course.created_at, now),
            "updated_at": self._safe_datetime(course.updated_at, now),
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
    ):
        repo = CourseRepository(self.db)
        normalized_teacher = self.main._normalize_text(teacher_username)
        normalized_name = self.main._normalize_text(course_name) or "Python程序设计"
        normalized_requested_id = self.main._normalize_text(requested_course_id)

        if normalized_requested_id:
            course = await repo.get(normalized_requested_id)
            if not course:
                raise HTTPException(status_code=404, detail="课程不存在")
            if self.main._normalize_text(course.created_by) != normalized_teacher:
                raise HTTPException(status_code=403, detail="不能使用其他教师创建的课程")
            return course, False

        existing = await repo.find_by_teacher_and_name(normalized_teacher, normalized_name)
        if existing:
            return existing, False

        now = datetime.now()
        created = await repo.create(
            {
                "id": str(self.main.uuid.uuid4()),
                "name": normalized_name,
                "description": "",
                "created_by": normalized_teacher,
                "created_at": now,
                "updated_at": now,
            }
        )
        return created, True

    async def _find_student_row(self, username: str):
        repo = UserRepository(self.db)
        student = await repo.get_student_by_student_id(username)
        if student is not None:
            return student

        user = await repo.get_by_username(username)
        if user is None:
            return None
        if self.main._normalize_text(user.role).lower() != "student":
            return None
        return user

    async def create_experiment(self, experiment: "Experiment"):
        normalized_teacher = self.main._normalize_text(experiment.created_by)
        self.main._ensure_teacher(normalized_teacher)
        experiment.created_by = normalized_teacher

        course_row, _ = await self._resolve_or_create_teacher_course_pg(
            normalized_teacher,
            self.main._resolve_course_name(experiment),
            experiment.course_id,
        )

        experiment.id = str(self.main.uuid.uuid4())
        experiment.created_at = datetime.now()
        experiment.course_id = course_row.id
        experiment.course_name = course_row.name
        self.main._normalize_experiment_publish_targets(experiment)
        self.main._validate_experiment_publish_targets(experiment)

        course_row.updated_at = experiment.created_at
        course_repo = CourseRepository(self.db)
        experiment_repo = ExperimentRepository(self.db)
        await course_repo.upsert(self._to_course_payload(course_row))
        await experiment_repo.upsert(self._to_experiment_payload(experiment))
        await self._commit_pg()

        self.main.courses_db[course_row.id] = self._to_course_record(course_row)
        self.main.experiments_db[experiment.id] = experiment
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

        self.main.experiments_db.clear()
        for item in experiments:
            if item.id:
                self.main.experiments_db[item.id] = item

        normalized_username = self.main._normalize_text(username)
        if normalized_username and not (self.main.is_teacher(normalized_username) or self.main.is_admin(normalized_username)):
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
        model = self._to_experiment_model(row)
        if model.id:
            self.main.experiments_db[model.id] = model
        return model

    async def update_experiment(self, experiment_id: str, experiment: "Experiment"):
        existing = await self.get_experiment(experiment_id)

        experiment.id = experiment_id
        if experiment.created_at is None:
            experiment.created_at = existing.created_at
        if not experiment.created_by:
            experiment.created_by = existing.created_by

        normalized_teacher = self.main._normalize_text(experiment.created_by)
        self.main._ensure_teacher(normalized_teacher)
        experiment.created_by = normalized_teacher

        requested_course_id = experiment.course_id or existing.course_id
        requested_course_name = self.main._resolve_course_name(experiment)
        if not self.main._normalize_text(experiment.course_name):
            requested_course_name = self.main._resolve_course_name(existing)

        course_row, _ = await self._resolve_or_create_teacher_course_pg(
            normalized_teacher,
            requested_course_name,
            requested_course_id,
        )

        experiment.course_id = course_row.id
        experiment.course_name = course_row.name
        self.main._normalize_experiment_publish_targets(experiment)
        self.main._validate_experiment_publish_targets(experiment)

        course_row.updated_at = datetime.now()
        course_repo = CourseRepository(self.db)
        experiment_repo = ExperimentRepository(self.db)
        await course_repo.upsert(self._to_course_payload(course_row))
        await experiment_repo.upsert(self._to_experiment_payload(experiment))
        await self._commit_pg()

        self.main.courses_db[course_row.id] = self._to_course_record(course_row)
        self.main.experiments_db[experiment_id] = experiment
        return experiment

    async def delete_experiment(self, experiment_id: str):
        experiment_repo = ExperimentRepository(self.db)
        attachment_repo = AttachmentRepository(self.db)
        course_repo = CourseRepository(self.db)

        existing = await experiment_repo.get(experiment_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="实验不存在")

        removed_exp = self._to_experiment_model(existing)
        attachments = await attachment_repo.list_by_experiment(experiment_id)
        removed_attachment_ids = [item.id for item in attachments]

        for item in attachments:
            if item.file_path and self.main.os.path.exists(item.file_path):
                try:
                    self.main.os.remove(item.file_path)
                except OSError:
                    pass

        if removed_attachment_ids:
            await attachment_repo.delete_many(removed_attachment_ids)
        await experiment_repo.delete(experiment_id)

        course_id = self.main._normalize_text(removed_exp.course_id)
        if course_id:
            await course_repo.touch(course_id, datetime.now())

        await self._commit_pg()

        self.main.experiments_db.pop(experiment_id, None)
        for att_id in removed_attachment_ids:
            self.main.attachments_db.pop(att_id, None)
        if course_id and course_id in self.main.courses_db:
            self.main.courses_db[course_id].updated_at = datetime.now()

        return {"message": "实验已删除"}


def build_experiment_service(main_module, db: Optional[AsyncSession] = None) -> ExperimentService:
    return ExperimentService(main_module=main_module, db=db)
