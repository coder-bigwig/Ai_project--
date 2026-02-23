from collections.abc import Sequence
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import CourseOfferingORM


class CourseOfferingRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, payload: dict[str, Any]) -> CourseOfferingORM:
        record = CourseOfferingORM(**payload)
        self.db.add(record)
        return record

    async def get(self, offering_id: str) -> CourseOfferingORM | None:
        if not offering_id:
            return None
        return await self.db.get(CourseOfferingORM, offering_id)

    async def get_by_code(self, offering_code: str) -> CourseOfferingORM | None:
        normalized_code = str(offering_code or "").strip().lower()
        if not normalized_code:
            return None
        stmt = select(CourseOfferingORM).where(func.lower(CourseOfferingORM.offering_code) == normalized_code)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def get_by_join_code(self, join_code: str) -> CourseOfferingORM | None:
        normalized_code = str(join_code or "").strip().lower()
        if not normalized_code:
            return None
        stmt = select(CourseOfferingORM).where(func.lower(CourseOfferingORM.join_code) == normalized_code)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def list_all(self) -> Sequence[CourseOfferingORM]:
        result = await self.db.execute(select(CourseOfferingORM))
        return list(result.scalars().all())

    async def list_by_template_course(self, template_course_id: str) -> Sequence[CourseOfferingORM]:
        if not template_course_id:
            return []
        stmt = select(CourseOfferingORM).where(CourseOfferingORM.template_course_id == template_course_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_by_ids(self, offering_ids: Sequence[str]) -> Sequence[CourseOfferingORM]:
        ids = [item for item in offering_ids if item]
        if not ids:
            return []
        stmt = select(CourseOfferingORM).where(CourseOfferingORM.id.in_(ids))
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update(self, record: CourseOfferingORM, payload: dict[str, Any]) -> CourseOfferingORM:
        for key, value in payload.items():
            setattr(record, key, value)
        return record

    async def delete(self, offering_id: str) -> CourseOfferingORM | None:
        record = await self.get(offering_id)
        if record is None:
            return None
        await self.db.delete(record)
        return record
