from __future__ import annotations

import os
import shutil
import uuid
from datetime import datetime
from typing import Optional

from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from ..repositories import AttachmentRepository, ExperimentRepository


class AttachmentService:
    def __init__(self, main_module, db: Optional[AsyncSession] = None):
        self.main = main_module
        self.db = db

    async def _commit(self):
        if self.db is None:
            return
        try:
            await self.db.commit()
        except Exception as exc:
            await self.db.rollback()
            raise HTTPException(status_code=500, detail="附件元数据写入失败") from exc

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
        if self.db is None:
            if experiment_id not in self.main.experiments_db:
                raise HTTPException(status_code=404, detail="实验不存在")
            uploaded = []
            for file in files:
                att_id = str(uuid.uuid4())
                safe_filename = file.filename.replace(" ", "_")
                file_path = os.path.join(self.main.UPLOAD_DIR, f"{att_id}_{safe_filename}")
                with open(file_path, "wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)
                attachment = self.main.Attachment(
                    id=att_id,
                    experiment_id=experiment_id,
                    filename=file.filename,
                    file_path=file_path,
                    content_type=file.content_type or "application/octet-stream",
                    size=os.path.getsize(file_path),
                    created_at=datetime.now(),
                )
                self.main.attachments_db[att_id] = attachment
                uploaded.append(attachment)
            return uploaded

        experiment = await ExperimentRepository(self.db).get(experiment_id)
        if not experiment:
            raise HTTPException(status_code=404, detail="实验不存在")

        repo = AttachmentRepository(self.db)
        uploaded: list = []
        created_paths: list[str] = []
        try:
            for file in files:
                if not file.filename:
                    continue
                att_id = str(uuid.uuid4())
                safe_filename = file.filename.replace(" ", "_")
                file_path = os.path.join(self.main.UPLOAD_DIR, f"{att_id}_{safe_filename}")
                with open(file_path, "wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)
                created_paths.append(file_path)

                payload = {
                    "id": att_id,
                    "experiment_id": experiment_id,
                    "filename": file.filename,
                    "file_path": file_path,
                    "content_type": file.content_type or "application/octet-stream",
                    "size": os.path.getsize(file_path),
                    "created_at": datetime.now(),
                    "updated_at": datetime.now(),
                }
                row = await repo.create(payload)
                uploaded.append(self._to_model(self.main, row))

            await self._commit()
        except Exception as exc:
            await self.db.rollback()
            for path in created_paths:
                if os.path.exists(path):
                    try:
                        os.remove(path)
                    except OSError:
                        pass
            raise HTTPException(status_code=500, detail=f"保存附件失败: {exc}") from exc

        for item in uploaded:
            self.main.attachments_db[item.id] = item
        return uploaded

    async def list_attachments(self, experiment_id: str):
        if self.db is None:
            return [att for att in self.main.attachments_db.values() if att.experiment_id == experiment_id]

        rows = await AttachmentRepository(self.db).list_by_experiment(experiment_id)
        items = [self._to_model(self.main, row) for row in rows]
        for item in items:
            self.main.attachments_db[item.id] = item
        return items

    async def get_attachment(self, attachment_id: str):
        if self.db is None:
            item = self.main.attachments_db.get(attachment_id)
            if not item:
                raise HTTPException(status_code=404, detail="附件不存在")
            return item

        row = await AttachmentRepository(self.db).get(attachment_id)
        if not row:
            raise HTTPException(status_code=404, detail="附件不存在")
        item = self._to_model(self.main, row)
        self.main.attachments_db[item.id] = item
        return item


def build_attachment_service(main_module, db: Optional[AsyncSession] = None) -> AttachmentService:
    return AttachmentService(main_module=main_module, db=db)
