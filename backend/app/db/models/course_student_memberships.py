from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base


class CourseStudentMembershipORM(Base):
    __tablename__ = "course_student_memberships"
    __table_args__ = (
        UniqueConstraint("course_id", "student_id", name="uq_course_student_memberships_course_student"),
        Index("ix_course_student_memberships_course_id", "course_id"),
        Index("ix_course_student_memberships_student_id", "student_id"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    course_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    added_by: Mapped[str] = mapped_column(String(128), nullable=False, default="", server_default=text("''"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
