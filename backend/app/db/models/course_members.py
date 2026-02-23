from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base


class CourseMemberORM(Base):
    __tablename__ = "course_members"
    __table_args__ = (
        UniqueConstraint("offering_id", "user_key", name="uq_course_members_offering_user"),
        Index("ix_course_members_user_key", "user_key"),
        Index("ix_course_members_role_status", "role", "status"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    offering_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("course_offerings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_key: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active", server_default=text("'active'"))
    join_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    leave_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
