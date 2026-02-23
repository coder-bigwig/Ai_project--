import io
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.session import get_db
from ...file_storage import read_row_file_bytes
from ...services.attachment_service import build_attachment_service


def _get_main_module():
    from ... import main

    return main


main = _get_main_module()
router = APIRouter()


async def upload_attachments(
    experiment_id: str,
    files: List[UploadFile] = File(...),
    db: Optional[AsyncSession] = Depends(get_db),
):
    service = build_attachment_service(main_module=main, db=db)
    return await service.upload_attachments(experiment_id=experiment_id, files=files)


async def list_attachments(
    experiment_id: str,
    db: Optional[AsyncSession] = Depends(get_db),
):
    service = build_attachment_service(main_module=main, db=db)
    return await service.list_attachments(experiment_id=experiment_id)


async def download_attachment(
    attachment_id: str,
    db: Optional[AsyncSession] = Depends(get_db),
):
    service = build_attachment_service(main_module=main, db=db)
    row = await service.get_attachment_row(attachment_id=attachment_id)
    file_bytes = read_row_file_bytes(row)
    if not file_bytes:
        raise HTTPException(status_code=404, detail="Attachment file not found")

    lower_filename = row.filename.lower()
    is_pdf = row.content_type == "application/pdf" or lower_filename.endswith(".pdf")
    is_ppt = (
        row.content_type
        in [
            "application/vnd.ms-powerpoint",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ]
        or lower_filename.endswith(".ppt")
        or lower_filename.endswith(".pptx")
    )
    content_disposition = "inline" if (is_pdf or is_ppt) else "attachment"

    if is_pdf:
        media_type = "application/pdf"
    elif lower_filename.endswith(".pptx"):
        media_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    elif lower_filename.endswith(".ppt"):
        media_type = "application/vnd.ms-powerpoint"
    else:
        media_type = row.content_type or "application/octet-stream"

    response_filename = "document.pdf" if is_pdf else row.filename
    return StreamingResponse(
        io.BytesIO(file_bytes),
        media_type=media_type,
        headers={"Content-Disposition": f'{content_disposition}; filename="{response_filename}"'},
    )


async def download_attachment_word(
    attachment_id: str,
    db: Optional[AsyncSession] = Depends(get_db),
):
    service = build_attachment_service(main_module=main, db=db)
    target_attachment = await service.find_paired_word_attachment(attachment_id=attachment_id)
    file_bytes = read_row_file_bytes(target_attachment)
    if not file_bytes:
        raise HTTPException(status_code=404, detail="Attachment file not found")

    lower_filename = target_attachment.filename.lower()
    if lower_filename.endswith(".docx"):
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    elif lower_filename.endswith(".doc"):
        media_type = "application/msword"
    elif lower_filename.endswith(".pdf"):
        media_type = "application/pdf"
    elif lower_filename.endswith(".pptx"):
        media_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    elif lower_filename.endswith(".ppt"):
        media_type = "application/vnd.ms-powerpoint"
    else:
        media_type = target_attachment.content_type or "application/octet-stream"

    return StreamingResponse(
        io.BytesIO(file_bytes),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{target_attachment.filename}"'},
    )


router.add_api_route("/api/teacher/experiments/{experiment_id}/attachments", upload_attachments, methods=["POST"])
router.add_api_route(
    "/api/experiments/{experiment_id}/attachments",
    list_attachments,
    methods=["GET"],
    response_model=list[main.Attachment],
)
router.add_api_route("/api/attachments/{attachment_id}/download", download_attachment, methods=["GET"])
router.add_api_route("/api/attachments/{attachment_id}/download-word", download_attachment_word, methods=["GET"])
