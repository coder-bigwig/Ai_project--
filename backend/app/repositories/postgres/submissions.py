from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.models import SubmissionORM, SubmissionPdfORM


class SubmissionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_all(self) -> Sequence[SubmissionORM]:
        result = await self.db.execute(select(SubmissionORM))
        return list(result.scalars().all())

    async def get(self, submission_id: str) -> SubmissionORM | None:
        if not submission_id:
            return None
        return await self.db.get(SubmissionORM, submission_id)

    async def upsert(self, payload: dict[str, Any]) -> SubmissionORM:
        submission_id = str(payload.get("id") or "").strip()
        if not submission_id:
            raise ValueError("submission id is required")

        record = await self.get(submission_id)
        if record is None:
            record = SubmissionORM(**payload)
            self.db.add(record)
            return record

        for key, value in payload.items():
            setattr(record, key, value)
        return record


class SubmissionPdfRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_all(self) -> Sequence[SubmissionPdfORM]:
        result = await self.db.execute(select(SubmissionPdfORM))
        return list(result.scalars().all())

    async def get(self, pdf_id: str) -> SubmissionPdfORM | None:
        if not pdf_id:
            return None
        return await self.db.get(SubmissionPdfORM, pdf_id)

    async def upsert(self, payload: dict[str, Any]) -> SubmissionPdfORM:
        pdf_id = str(payload.get("id") or "").strip()
        if not pdf_id:
            raise ValueError("submission pdf id is required")

        record = await self.get(pdf_id)
        if record is None:
            record = SubmissionPdfORM(**payload)
            self.db.add(record)
            return record

        for key, value in payload.items():
            setattr(record, key, value)
        return record

