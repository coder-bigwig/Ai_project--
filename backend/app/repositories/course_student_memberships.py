from collections.abc import Sequence
from typing import Any

from sqlalchemy import and_, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import CourseStudentMembershipORM


class CourseStudentMembershipRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, payload: dict[str, Any]) -> CourseStudentMembershipORM:
        record = CourseStudentMembershipORM(**payload)
        self.db.add(record)
        return record

    async def get_by_course_and_student(self, course_id: str, student_id: str) -> CourseStudentMembershipORM | None:
        if not course_id or not student_id:
            return None
        stmt = select(CourseStudentMembershipORM).where(
            and_(
                CourseStudentMembershipORM.course_id == course_id,
                CourseStudentMembershipORM.student_id == student_id,
            )
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def list_by_course(self, course_id: str) -> Sequence[CourseStudentMembershipORM]:
        if not course_id:
            return []
        stmt = select(CourseStudentMembershipORM).where(CourseStudentMembershipORM.course_id == course_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_by_student(self, student_id: str) -> Sequence[CourseStudentMembershipORM]:
        if not student_id:
            return []
        stmt = select(CourseStudentMembershipORM).where(CourseStudentMembershipORM.student_id == student_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_by_students(self, student_ids: Sequence[str]) -> Sequence[CourseStudentMembershipORM]:
        cleaned = [item for item in student_ids if item]
        if not cleaned:
            return []
        stmt = select(CourseStudentMembershipORM).where(CourseStudentMembershipORM.student_id.in_(cleaned))
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_by_course_and_students(
        self,
        course_id: str,
        student_ids: Sequence[str],
    ) -> Sequence[CourseStudentMembershipORM]:
        cleaned = [item for item in student_ids if item]
        if not course_id or not cleaned:
            return []
        stmt = select(CourseStudentMembershipORM).where(
            and_(
                CourseStudentMembershipORM.course_id == course_id,
                CourseStudentMembershipORM.student_id.in_(cleaned),
            )
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def delete_record(self, record: CourseStudentMembershipORM) -> None:
        await self.db.delete(record)

    async def delete_by_course_and_student(self, course_id: str, student_id: str) -> int:
        if not course_id or not student_id:
            return 0
        stmt = delete(CourseStudentMembershipORM).where(
            and_(
                CourseStudentMembershipORM.course_id == course_id,
                CourseStudentMembershipORM.student_id == student_id,
            )
        )
        result = await self.db.execute(stmt)
        return int(result.rowcount or 0)

    async def delete_by_course_and_students(self, course_id: str, student_ids: Sequence[str]) -> int:
        cleaned = [item for item in student_ids if item]
        if not course_id or not cleaned:
            return 0
        stmt = delete(CourseStudentMembershipORM).where(
            and_(
                CourseStudentMembershipORM.course_id == course_id,
                CourseStudentMembershipORM.student_id.in_(cleaned),
            )
        )
        result = await self.db.execute(stmt)
        return int(result.rowcount or 0)
