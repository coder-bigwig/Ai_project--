from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.models import ClassroomORM, UserORM


class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_users(self) -> Sequence[UserORM]:
        result = await self.db.execute(select(UserORM))
        return list(result.scalars().all())

    async def list_classes(self) -> Sequence[ClassroomORM]:
        result = await self.db.execute(select(ClassroomORM))
        return list(result.scalars().all())

    async def get_by_username(self, username: str) -> UserORM | None:
        if not username:
            return None
        stmt = select(UserORM).where(UserORM.username == username)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def upsert_user(self, payload: dict[str, Any]) -> UserORM:
        username = str(payload.get("username") or "").strip()
        user_id = str(payload.get("id") or "").strip()
        if not username:
            raise ValueError("username is required")
        if not user_id:
            raise ValueError("user id is required")

        record = await self.get_by_username(username)
        if record is None:
            record = UserORM(**payload)
            self.db.add(record)
            return record

        for key, value in payload.items():
            setattr(record, key, value)
        return record

    async def upsert_class(self, payload: dict[str, Any]) -> ClassroomORM:
        class_id = str(payload.get("id") or "").strip()
        if not class_id:
            raise ValueError("class id is required")

        record = await self.db.get(ClassroomORM, class_id)
        if record is None:
            record = ClassroomORM(**payload)
            self.db.add(record)
            return record

        for key, value in payload.items():
            setattr(record, key, value)
        return record

