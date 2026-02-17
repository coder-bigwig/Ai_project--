from datetime import datetime
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from ..repositories.postgres import AttachmentRepository, CourseRepository, ExperimentRepository
from ..storage_config import PG_READ_PREFERRED, STORAGE_BACKEND, use_json_write, use_postgres


class ExperimentService:
    def __init__(self, main_module, db: Optional[AsyncSession] = None):
        self.main = main_module
        self.db = db
        self._enable_pg = use_postgres() and self.db is not None
        self._enable_json_write = use_json_write()
        self._prefer_pg_reads = self._enable_pg and (STORAGE_BACKEND == "postgres" or PG_READ_PREFERRED)

    @staticmethod
    def _safe_datetime(value, fallback: datetime | None = None) -> datetime | None:
        if isinstance(value, datetime):
            return value
        return fallback

    def _to_experiment_model(self, row) -> "Experiment":
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
        if not self._enable_pg:
            return
        try:
            await self.db.commit()
        except SQLAlchemyError as exc:
            await self.db.rollback()
            raise HTTPException(status_code=500, detail="PostgreSQL写入失败") from exc

    async def create_experiment(self, experiment: "Experiment"):
        normalized_teacher = self.main._normalize_text(experiment.created_by)
        self.main._ensure_teacher(normalized_teacher)
        experiment.created_by = normalized_teacher

        course_record, _ = self.main._resolve_or_create_teacher_course(
            normalized_teacher,
            self.main._resolve_course_name(experiment),
            experiment.course_id,
        )

        experiment.id = str(self.main.uuid.uuid4())
        experiment.created_at = datetime.now()
        experiment.course_id = course_record.id
        experiment.course_name = course_record.name
        self.main._normalize_experiment_publish_targets(experiment)
        self.main._validate_experiment_publish_targets(experiment)
        self.main.experiments_db[experiment.id] = experiment

        course_record.updated_at = experiment.created_at

        if self._enable_pg:
            course_repo = CourseRepository(self.db)
            experiment_repo = ExperimentRepository(self.db)
            await course_repo.upsert(self._to_course_payload(course_record))
            await experiment_repo.upsert(self._to_experiment_payload(experiment))
            await self._commit_pg()

        if self._enable_json_write:
            self.main._save_course_registry()
            self.main._save_experiment_registry()
        return experiment

    async def list_experiments(
        self,
        difficulty: Optional["DifficultyLevel"] = None,
        tag: Optional[str] = None,
        username: Optional[str] = None,
    ):
        experiments = []
        if self._prefer_pg_reads:
            experiment_repo = ExperimentRepository(self.db)
            rows = await experiment_repo.list_all()
            experiments = [self._to_experiment_model(item) for item in rows]
            self.main.experiments_db.clear()
            for item in experiments:
                if item.id:
                    self.main.experiments_db[item.id] = item
        else:
            experiments = list(self.main.experiments_db.values())

        normalized_username = self.main._normalize_text(username)
        if normalized_username and not (self.main.is_teacher(normalized_username) or self.main.is_admin(normalized_username)):
            student = self.main.students_db.get(normalized_username)
            if not student:
                experiments = []
            else:
                experiments = [e for e in experiments if self.main._is_experiment_visible_to_student(e, student)]

        if difficulty:
            experiments = [e for e in experiments if e.difficulty == difficulty]

        if tag:
            experiments = [e for e in experiments if tag in e.tags]

        return experiments

    async def get_experiment(self, experiment_id: str):
        if self._prefer_pg_reads:
            experiment_repo = ExperimentRepository(self.db)
            row = await experiment_repo.get(experiment_id)
            if not row:
                raise HTTPException(status_code=404, detail="实验不存在")
            model = self._to_experiment_model(row)
            if model.id:
                self.main.experiments_db[model.id] = model
            return model

        if experiment_id not in self.main.experiments_db:
            raise HTTPException(status_code=404, detail="实验不存在")
        return self.main.experiments_db[experiment_id]

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

        course_record, _ = self.main._resolve_or_create_teacher_course(
            normalized_teacher,
            requested_course_name,
            requested_course_id,
        )

        experiment.course_id = course_record.id
        experiment.course_name = course_record.name
        self.main._normalize_experiment_publish_targets(experiment)
        self.main._validate_experiment_publish_targets(experiment)
        self.main.experiments_db[experiment_id] = experiment
        course_record.updated_at = datetime.now()

        if self._enable_pg:
            course_repo = CourseRepository(self.db)
            experiment_repo = ExperimentRepository(self.db)
            await course_repo.upsert(self._to_course_payload(course_record))
            await experiment_repo.upsert(self._to_experiment_payload(experiment))
            await self._commit_pg()

        if self._enable_json_write:
            self.main._save_course_registry()
            self.main._save_experiment_registry()
        return experiment

    async def delete_experiment(self, experiment_id: str):
        if experiment_id not in self.main.experiments_db and not self._prefer_pg_reads:
            raise HTTPException(status_code=404, detail="实验不存在")

        removed_attachment_ids = [
            att_id
            for att_id, item in self.main.attachments_db.items()
            if item.experiment_id == experiment_id
        ]
        for att_id in removed_attachment_ids:
            item = self.main.attachments_db.pop(att_id, None)
            if item and self.main.os.path.exists(item.file_path):
                try:
                    self.main.os.remove(item.file_path)
                except OSError:
                    pass

        removed_exp = self.main.experiments_db.pop(experiment_id, None)
        if removed_exp is None and self._prefer_pg_reads:
            pg_item = await ExperimentRepository(self.db).get(experiment_id)
            if not pg_item:
                raise HTTPException(status_code=404, detail="实验不存在")
            removed_exp = self._to_experiment_model(pg_item)

        if not removed_exp:
            raise HTTPException(status_code=404, detail="实验不存在")

        course_id = self.main._normalize_text(removed_exp.course_id)
        if course_id and course_id in self.main.courses_db:
            self.main.courses_db[course_id].updated_at = datetime.now()

        if self._enable_pg:
            attachment_repo = AttachmentRepository(self.db)
            experiment_repo = ExperimentRepository(self.db)
            course_repo = CourseRepository(self.db)
            if removed_attachment_ids:
                await attachment_repo.delete_many(removed_attachment_ids)
            await experiment_repo.delete(experiment_id)
            if course_id:
                await course_repo.touch(course_id, datetime.now())
            await self._commit_pg()

        if self._enable_json_write:
            if removed_attachment_ids:
                self.main._save_attachment_registry()
            if course_id and course_id in self.main.courses_db:
                self.main._save_course_registry()
            self.main._save_experiment_registry()
        return {"message": "实验已删除"}


def build_experiment_service(main_module, db: Optional[AsyncSession] = None) -> ExperimentService:
    return ExperimentService(main_module=main_module, db=db)

