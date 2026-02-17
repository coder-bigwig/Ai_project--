from collections.abc import Sequence
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.models import OperationLogORM


class OperationLogRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_all(self) -> Sequence[OperationLogORM]:
        result = await self.db.execute(select(OperationLogORM).order_by(desc(OperationLogORM.created_at)))
        return list(result.scalars().all())

    async def upsert(self, payload: dict[str, Any]) -> OperationLogORM:
        log_id = str(payload.get("id") or "").strip()
        if not log_id:
            raise ValueError("operation log id is required")

        record = await self.db.get(OperationLogORM, log_id)
        if record is None:
            record = OperationLogORM(**payload)
            self.db.add(record)
            return record

        for key, value in payload.items():
            setattr(record, key, value)
        return record

