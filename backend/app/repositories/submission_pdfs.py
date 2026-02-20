from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import SubmissionPdfORM


class SubmissionPdfRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, payload: dict[str, Any]) -> SubmissionPdfORM:
        record = SubmissionPdfORM(**payload)
        self.db.add(record)
        return record

    async def get(self, pdf_id: str) -> SubmissionPdfORM | None:
        if not pdf_id:
            return None
        return await self.db.get(SubmissionPdfORM, pdf_id)

    async def list_all(self) -> Sequence[SubmissionPdfORM]:
        result = await self.db.execute(select(SubmissionPdfORM))
        return list(result.scalars().all())

    async def list_by_submission(self, submission_id: str) -> Sequence[SubmissionPdfORM]:
        stmt = select(SubmissionPdfORM).where(SubmissionPdfORM.submission_id == submission_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update(self, record: SubmissionPdfORM, payload: dict[str, Any]) -> SubmissionPdfORM:
        for key, value in payload.items():
            setattr(record, key, value)
        return record

    async def upsert(self, payload: dict[str, Any]) -> SubmissionPdfORM:
        pdf_id = str(payload.get("id") or "").strip()
        if not pdf_id:
            raise ValueError("submission pdf id is required")
        record = await self.get(pdf_id)
        if record is None:
            return await self.create(payload)
        return await self.update(record, payload)
