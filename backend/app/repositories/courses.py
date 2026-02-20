from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import CourseORM


class CourseRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, payload: dict[str, Any]) -> CourseORM:
        record = CourseORM(**payload)
        self.db.add(record)
        return record

    async def get(self, course_id: str) -> CourseORM | None:
        if not course_id:
            return None
        return await self.db.get(CourseORM, course_id)

    async def list_all(self) -> Sequence[CourseORM]:
        result = await self.db.execute(select(CourseORM))
        return list(result.scalars().all())

    async def list_by_creator(self, created_by: str) -> Sequence[CourseORM]:
        stmt = select(CourseORM).where(CourseORM.created_by == created_by)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def find_by_teacher_and_name(self, teacher_username: str, course_name: str) -> CourseORM | None:
        normalized_name = (course_name or "").strip().lower()
        if not teacher_username or not normalized_name:
            return None
        stmt = select(CourseORM).where(
            CourseORM.created_by == teacher_username,
            func.lower(CourseORM.name) == normalized_name,
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def update(self, record: CourseORM, payload: dict[str, Any]) -> CourseORM:
        for key, value in payload.items():
            setattr(record, key, value)
        return record

    async def upsert(self, payload: dict[str, Any]) -> CourseORM:
        course_id = str(payload.get("id") or "").strip()
        if not course_id:
            raise ValueError("course id is required")

        record = await self.get(course_id)
        if record is None:
            return await self.create(payload)
        return await self.update(record, payload)

    async def touch(self, course_id: str, updated_at: datetime) -> CourseORM | None:
        record = await self.get(course_id)
        if record is None:
            return None
        record.updated_at = updated_at
        return record

    async def delete(self, course_id: str) -> CourseORM | None:
        record = await self.get(course_id)
        if record is None:
            return None
        await self.db.delete(record)
        return record
