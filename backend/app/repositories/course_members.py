from collections.abc import Sequence
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import CourseMemberORM


class CourseMemberRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, payload: dict[str, Any]) -> CourseMemberORM:
        record = CourseMemberORM(**payload)
        self.db.add(record)
        return record

    async def get(self, member_id: str) -> CourseMemberORM | None:
        if not member_id:
            return None
        return await self.db.get(CourseMemberORM, member_id)

    async def get_by_offering_and_user(self, offering_id: str, user_key: str) -> CourseMemberORM | None:
        if not offering_id or not user_key:
            return None
        stmt = select(CourseMemberORM).where(
            and_(
                CourseMemberORM.offering_id == offering_id,
                CourseMemberORM.user_key == user_key,
            )
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def list_by_offering(self, offering_id: str) -> Sequence[CourseMemberORM]:
        if not offering_id:
            return []
        stmt = select(CourseMemberORM).where(CourseMemberORM.offering_id == offering_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_by_user(self, user_key: str) -> Sequence[CourseMemberORM]:
        if not user_key:
            return []
        stmt = select(CourseMemberORM).where(CourseMemberORM.user_key == user_key)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_by_users(self, user_keys: Sequence[str]) -> Sequence[CourseMemberORM]:
        values = [item for item in user_keys if item]
        if not values:
            return []
        stmt = select(CourseMemberORM).where(CourseMemberORM.user_key.in_(values))
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update(self, record: CourseMemberORM, payload: dict[str, Any]) -> CourseMemberORM:
        for key, value in payload.items():
            setattr(record, key, value)
        return record
