from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base


class CourseOfferingORM(Base):
    __tablename__ = "course_offerings"
    __table_args__ = (
        UniqueConstraint("offering_code", name="uq_course_offerings_offering_code"),
        UniqueConstraint("join_code", name="uq_course_offerings_join_code"),
        Index("ix_course_offerings_template_course_id", "template_course_id"),
        Index("ix_course_offerings_created_by", "created_by"),
        Index("ix_course_offerings_status", "status"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    template_course_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
    )
    offering_code: Mapped[str] = mapped_column(String(128), nullable=False)
    join_code: Mapped[str] = mapped_column(String(8), nullable=False)
    term: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default=text("''"))
    major: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default=text("''"))
    class_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default=text("''"))
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active", server_default=text("'active'"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
