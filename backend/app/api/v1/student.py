import mimetypes
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.session import get_db
from ...services.student_service import build_student_service


def _get_main_module():
    from ... import main
    return main


main = _get_main_module()
router = APIRouter()


async def get_student_courses_with_status(
    student_id: str,
    db: Optional[AsyncSession] = Depends(get_db),
):
    service = build_student_service(main_module=main, db=db)
    return await service.get_student_courses_with_status(student_id=student_id)


async def get_student_profile(
    student_id: str,
    db: Optional[AsyncSession] = Depends(get_db),
):
    service = build_student_service(main_module=main, db=db)
    return await service.get_student_profile(student_id=student_id)


async def upsert_student_security_question(
    payload: main.StudentSecurityQuestionUpdateRequest,
    db: Optional[AsyncSession] = Depends(get_db),
):
    service = build_student_service(main_module=main, db=db)
    return await service.upsert_student_security_question(payload=payload)


async def change_student_password(
    payload: main.StudentPasswordChangeRequest,
    db: Optional[AsyncSession] = Depends(get_db),
):
    service = build_student_service(main_module=main, db=db)
    return await service.change_student_password(payload=payload)


async def list_student_resource_files(
    student_id: str,
    name: Optional[str] = None,
    file_type: Optional[str] = None,
):
    main._ensure_student(student_id)
    items = main._list_resource_records(name_filter=name or "", type_filter=file_type or "")
    payload_items = [main._resource_to_payload(item, route_prefix="/api/student/resources") for item in items]
    return {"total": len(payload_items), "items": payload_items}


async def get_student_resource_file_detail(resource_id: str, student_id: str):
    main._ensure_student(student_id)
    record = main._get_resource_or_404(resource_id)
    main._ensure_resource_file_exists(record)

    payload = main._resource_to_payload(record, route_prefix="/api/student/resources")
    preview_mode = payload["preview_mode"]
    if preview_mode in {"markdown", "text"}:
        payload["preview_text"] = main._read_text_preview(record.file_path)
    elif preview_mode == "docx":
        payload["preview_text"] = main._read_docx_preview(record.file_path)
    else:
        payload["preview_text"] = ""
    return payload


async def preview_student_resource_file(resource_id: str, student_id: str):
    main._ensure_student(student_id)
    record = main._get_resource_or_404(resource_id)
    main._ensure_resource_file_exists(record)

    preview_mode = main._resource_preview_mode(record)
    if preview_mode != "pdf":
        raise HTTPException(status_code=400, detail="该文件类型不支持二进制在线预览")

    return FileResponse(
        path=record.file_path,
        filename="document.pdf",
        media_type="application/pdf",
        content_disposition_type="inline",
    )


async def download_student_resource_file(resource_id: str, student_id: str):
    main._ensure_student(student_id)
    record = main._get_resource_or_404(resource_id)
    main._ensure_resource_file_exists(record)

    media_type = record.content_type or mimetypes.guess_type(record.filename)[0] or "application/octet-stream"
    return FileResponse(
        path=record.file_path,
        filename=record.filename,
        media_type=media_type,
        content_disposition_type="attachment",
    )


router.add_api_route("/api/student/courses-with-status", get_student_courses_with_status, methods=["GET"])
router.add_api_route("/api/student/profile", get_student_profile, methods=["GET"])
router.add_api_route("/api/student/profile/security-question", upsert_student_security_question, methods=["POST"])
router.add_api_route("/api/student/profile/change-password", change_student_password, methods=["POST"])
router.add_api_route("/api/student/resources", list_student_resource_files, methods=["GET"])
router.add_api_route("/api/student/resources/{resource_id}", get_student_resource_file_detail, methods=["GET"])
router.add_api_route("/api/student/resources/{resource_id}/preview", preview_student_resource_file, methods=["GET"])
router.add_api_route("/api/student/resources/{resource_id}/download", download_student_resource_file, methods=["GET"])
