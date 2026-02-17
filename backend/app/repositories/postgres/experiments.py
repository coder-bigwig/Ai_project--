from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.models import ExperimentORM


class ExperimentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_all(self) -> Sequence[ExperimentORM]:
        result = await self.db.execute(select(ExperimentORM))
        return list(result.scalars().all())

    async def get(self, experiment_id: str) -> ExperimentORM | None:
        if not experiment_id:
            return None
        return await self.db.get(ExperimentORM, experiment_id)

    async def upsert(self, payload: dict[str, Any]) -> ExperimentORM:
        experiment_id = str(payload.get("id") or "").strip()
        if not experiment_id:
            raise ValueError("experiment id is required")

        record = await self.get(experiment_id)
        if record is None:
            record = ExperimentORM(**payload)
            self.db.add(record)
            return record

        for key, value in payload.items():
            setattr(record, key, value)
        return record

    async def delete(self, experiment_id: str) -> ExperimentORM | None:
        record = await self.get(experiment_id)
        if record is None:
            return None
        await self.db.delete(record)
        return record

