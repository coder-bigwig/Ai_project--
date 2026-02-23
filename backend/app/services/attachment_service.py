from __future__ import annotations

import os
import uuid
from datetime import datetime
from typing import Optional

from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from ..file_storage import build_virtual_path, row_has_file_content
from ..repositories import AttachmentRepository, ExperimentRepository


class AttachmentService:
    def __init__(self, main_module, db: Optional[AsyncSession] = None):
        if db is None:
            raise HTTPException(status_code=503, detail="PostgreSQL session unavailable")
        self.main = main_module
        self.db = db

    async def _commit(self):
        try:
            await self.db.commit()
        except Exception as exc:
            await self.db.rollback()
            raise HTTPException(status_code=500, detail="Failed to persist attachment metadata") from exc

    @staticmethod
    def _to_model(main_module, row):
        return main_module.Attachment(
            id=row.id,
            experiment_id=row.experiment_id,
            filename=row.filename,
            file_path=row.file_path,
            content_type=row.content_type,
            size=row.size,
            created_at=row.created_at,
        )

    async def upload_attachments(self, experiment_id: str, files: list[UploadFile]):
        experiment = await ExperimentRepository(self.db).get(experiment_id)
        if not experiment:
            raise HTTPException(status_code=404, detail="Experiment not found")

        repo = AttachmentRepository(self.db)
        uploaded: list = []
        try:
            for file in files:
                if not file.filename:
                    continue

                file_bytes = await file.read()
                if not file_bytes:
                    raise HTTPException(status_code=400, detail="Attachment file is empty")

                att_id = str(uuid.uuid4())
                safe_filename = file.filename.replace(" ", "_")
                payload = {
                    "id": att_id,
                    "experiment_id": experiment_id,
                    "filename": file.filename,
                    "file_path": build_virtual_path("attachments", att_id, safe_filename),
                    "file_data": file_bytes,
                    "content_type": file.content_type or "application/octet-stream",
                    "size": len(file_bytes),
                    "created_at": datetime.now(),
                    "updated_at": datetime.now(),
                }
                row = await repo.create(payload)
                uploaded.append(self._to_model(self.main, row))

            await self._commit()
        except HTTPException:
            await self.db.rollback()
            raise
        except Exception as exc:
            await self.db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to save attachment: {exc}") from exc

        return uploaded

    async def list_attachments(self, experiment_id: str):
        rows = await AttachmentRepository(self.db).list_by_experiment(experiment_id)
        return [self._to_model(self.main, row) for row in rows]

    async def get_attachment_row(self, attachment_id: str):
        row = await AttachmentRepository(self.db).get(attachment_id)
        if not row:
            raise HTTPException(status_code=404, detail="Attachment not found")
        return row

    async def find_paired_word_attachment(self, attachment_id: str):
        row = await self.get_attachment_row(attachment_id)

        lower_filename = row.filename.lower()
        is_pdf = row.content_type == "application/pdf" or lower_filename.endswith(".pdf")
        if not is_pdf:
            return row

        base_name = os.path.splitext(row.filename)[0]
        candidates = await AttachmentRepository(self.db).list_by_experiment(row.experiment_id)
        matched = []
        for item in candidates:
            item_base = os.path.splitext(item.filename)[0]
            item_lower = item.filename.lower()
            if item.id == row.id:
                continue
            if item_base != base_name:
                continue
            if not (item_lower.endswith(".docx") or item_lower.endswith(".doc")):
                continue
            if not row_has_file_content(item):
                continue
            matched.append(item)

        if not matched:
            return row

        matched.sort(key=lambda item: 0 if item.filename.lower().endswith(".docx") else 1)
        return matched[0]


def build_attachment_service(main_module, db: Optional[AsyncSession] = None) -> AttachmentService:
    return AttachmentService(main_module=main_module, db=db)
