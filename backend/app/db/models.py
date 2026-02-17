from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


def _json_dict() -> dict[str, Any]:
    return {}


def _json_list() -> list[Any]:
    return []


class TimestampVersionMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"), default=1)


class ClassroomORM(Base):
    __tablename__ = "classes"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class UserORM(Base, TimestampVersionMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    username: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    real_name: Mapped[str] = mapped_column(String(255), nullable=False, default="", server_default=text("''"))
    student_id: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True, index=True)
    class_name: Mapped[str] = mapped_column(String(255), nullable=False, default="", server_default=text("''"))
    admission_year: Mapped[str] = mapped_column(String(32), nullable=False, default="", server_default=text("''"))
    organization: Mapped[str] = mapped_column(String(255), nullable=False, default="", server_default=text("''"))
    phone: Mapped[str] = mapped_column(String(64), nullable=False, default="", server_default=text("''"))
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False, default="", server_default=text("''"))
    security_question: Mapped[str] = mapped_column(String(255), nullable=False, default="", server_default=text("''"))
    security_answer_hash: Mapped[str] = mapped_column(String(128), nullable=False, default="", server_default=text("''"))
    created_by: Mapped[str] = mapped_column(String(128), nullable=False, default="", server_default=text("''"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    extra: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=_json_dict, server_default=text("'{}'::jsonb"))


class CourseORM(Base, TimestampVersionMixin):
    __tablename__ = "courses"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default=text("''"))
    created_by: Mapped[str] = mapped_column(String(128), nullable=False, index=True)


class ExperimentORM(Base, TimestampVersionMixin):
    __tablename__ = "experiments"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    course_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("courses.id", ondelete="SET NULL"), nullable=True, index=True)
    course_name: Mapped[str] = mapped_column(String(255), nullable=False, default="", server_default=text("''"))
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default=text("''"))
    difficulty: Mapped[str] = mapped_column(String(32), nullable=False, default="", server_default=text("''"), index=True)
    tags: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=_json_list, server_default=text("'[]'::jsonb"))
    notebook_path: Mapped[str] = mapped_column(String(500), nullable=False, default="", server_default=text("''"))
    resources: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=_json_dict, server_default=text("'{}'::jsonb"))
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"), index=True)
    publish_scope: Mapped[str] = mapped_column(String(32), nullable=False, default="all", server_default=text("'all'"))
    target_class_names: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=_json_list, server_default=text("'[]'::jsonb"))
    target_student_ids: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=_json_list, server_default=text("'[]'::jsonb"))
    extra: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=_json_dict, server_default=text("'{}'::jsonb"))


class SubmissionORM(Base, TimestampVersionMixin):
    __tablename__ = "submissions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    experiment_id: Mapped[str] = mapped_column(String(64), ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="", server_default=text("''"), index=True)
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    submit_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notebook_content: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default=text("''"))
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    ai_feedback: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default=text("''"))
    teacher_comment: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default=text("''"))
    extra: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=_json_dict, server_default=text("'{}'::jsonb"))


class SubmissionPdfORM(Base, TimestampVersionMixin):
    __tablename__ = "submission_pdfs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    submission_id: Mapped[str] = mapped_column(String(64), ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False, index=True)
    experiment_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    student_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str] = mapped_column(String(255), nullable=False, default="", server_default=text("''"))
    size: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    viewed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    viewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    viewed_by: Mapped[str] = mapped_column(String(128), nullable=False, default="", server_default=text("''"))
    reviewed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[str] = mapped_column(String(128), nullable=False, default="", server_default=text("''"))
    annotations: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=_json_list, server_default=text("'[]'::jsonb"))


class ResourceORM(Base, TimestampVersionMixin):
    __tablename__ = "resources"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str] = mapped_column(String(64), nullable=False, default="", server_default=text("''"))
    content_type: Mapped[str] = mapped_column(String(255), nullable=False, default="", server_default=text("''"))
    size: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    created_by: Mapped[str] = mapped_column(String(128), nullable=False, default="", server_default=text("''"), index=True)


class AttachmentORM(Base, TimestampVersionMixin):
    __tablename__ = "attachments"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    experiment_id: Mapped[str] = mapped_column(String(64), ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str] = mapped_column(String(255), nullable=False, default="", server_default=text("''"))
    size: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))


class OperationLogORM(Base):
    __tablename__ = "operation_logs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    operator: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    target: Mapped[str] = mapped_column(String(255), nullable=False, default="", server_default=text("''"))
    detail: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default=text("''"))
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)


class AppKVStoreORM(Base):
    __tablename__ = "app_kv_store"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=_json_dict, server_default=text("'{}'::jsonb"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

