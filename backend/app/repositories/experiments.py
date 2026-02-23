from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import ExperimentORM


class ExperimentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, payload: dict[str, Any]) -> ExperimentORM:
        record = ExperimentORM(**payload)
        self.db.add(record)
        return record

    async def get(self, experiment_id: str, include_deleted: bool = False) -> ExperimentORM | None:
        if not experiment_id:
            return None
        stmt = select(ExperimentORM).where(ExperimentORM.id == experiment_id)
        if not include_deleted:
            stmt = stmt.where(ExperimentORM.deleted_at.is_(None))
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def list_all(self, include_deleted: bool = False) -> Sequence[ExperimentORM]:
        stmt = select(ExperimentORM)
        if not include_deleted:
            stmt = stmt.where(ExperimentORM.deleted_at.is_(None))
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_by_course_ids(self, course_ids: Sequence[str], include_deleted: bool = False) -> Sequence[ExperimentORM]:
        ids = [item for item in course_ids if item]
        if not ids:
            return []
        stmt = select(ExperimentORM).where(ExperimentORM.course_id.in_(ids))
        if not include_deleted:
            stmt = stmt.where(ExperimentORM.deleted_at.is_(None))
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_by_creator(self, created_by: str, include_deleted: bool = False) -> Sequence[ExperimentORM]:
        stmt = select(ExperimentORM).where(ExperimentORM.created_by == created_by)
        if not include_deleted:
            stmt = stmt.where(ExperimentORM.deleted_at.is_(None))
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_recycle_by_creator(self, created_by: str) -> Sequence[ExperimentORM]:
        stmt = (
            select(ExperimentORM)
            .where(ExperimentORM.created_by == created_by, ExperimentORM.deleted_at.is_not(None))
            .order_by(ExperimentORM.deleted_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_soft_deleted_before(self, expire_before: datetime) -> Sequence[ExperimentORM]:
        stmt = select(ExperimentORM).where(
            ExperimentORM.deleted_at.is_not(None),
            ExperimentORM.deleted_at <= expire_before,
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update(self, record: ExperimentORM, payload: dict[str, Any]) -> ExperimentORM:
        for key, value in payload.items():
            setattr(record, key, value)
        return record

    async def upsert(self, payload: dict[str, Any]) -> ExperimentORM:
        experiment_id = str(payload.get("id") or "").strip()
        if not experiment_id:
            raise ValueError("experiment id is required")
        record = await self.get(experiment_id, include_deleted=True)
        if record is None:
            return await self.create(payload)
        return await self.update(record, payload)

    async def delete(self, experiment_id: str) -> ExperimentORM | None:
        record = await self.get(experiment_id, include_deleted=True)
        if record is None:
            return None
        await self.db.delete(record)
        return record

    async def soft_delete(self, experiment_id: str, deleted_at: datetime) -> ExperimentORM | None:
        record = await self.get(experiment_id, include_deleted=True)
        if record is None:
            return None
        record.deleted_at = deleted_at
        return record

    async def restore(self, experiment_id: str) -> ExperimentORM | None:
        record = await self.get(experiment_id, include_deleted=True)
        if record is None:
            return None
        record.deleted_at = None
        return record
