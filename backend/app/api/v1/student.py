import mimetypes
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.session import get_db
from ...repositories import (
    CourseMemberRepository,
    CourseOfferingRepository,
    CourseStudentMembershipRepository,
    ResourceRepository,
)
from ...services.identity_service import ensure_student_user, normalize_text
from ...services.kv_policy_service import get_kv_json
from ...services.offering_service import build_offering_service
from ...services.student_service import build_student_service


def _get_main_module():
    from ... import main
    return main


main = _get_main_module()
router = APIRouter()
RESOURCE_SCOPE_BINDINGS_KV_KEY = "resource_scope_bindings_v1"


async def get_student_courses_with_status(
    student_id: str,
    db: Optional[AsyncSession] = Depends(get_db),
):
    service = build_offering_service(main_module=main, db=db)
    return await service.list_student_offerings(student_key=student_id)


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


async def join_student_offering(
    offering_id: str,
    payload: main.StudentOfferingJoinRequest,
    db: Optional[AsyncSession] = Depends(get_db),
):
    service = build_offering_service(main_module=main, db=db)
    return await service.join(offering_id=offering_id, student_key=payload.student_id)


async def join_student_offering_by_code(
    payload: main.StudentOfferingJoinByCodeRequest,
    db: Optional[AsyncSession] = Depends(get_db),
):
    service = build_offering_service(main_module=main, db=db)
    return await service.join_by_code(student_key=payload.student_id, join_code=payload.join_code)


async def leave_student_offering(
    offering_id: str,
    payload: main.StudentOfferingJoinRequest,
    db: Optional[AsyncSession] = Depends(get_db),
):
    service = build_offering_service(main_module=main, db=db)
    return await service.leave(offering_id=offering_id, student_key=payload.student_id)


async def get_student_offering_experiments(
    offering_id: str,
    student_id: str,
    db: Optional[AsyncSession] = Depends(get_db),
):
    service = build_offering_service(main_module=main, db=db)
    return await service.list_offering_experiments(offering_id=offering_id, student_key=student_id)


def _resource_preview_mode(file_type: str) -> str:
    normalized = normalize_text(file_type).lower().lstrip(".")
    if normalized == "pdf":
        return "pdf"
    if normalized in {"xls", "xlsx"}:
        return "sheet"
    if normalized in {"md", "markdown"}:
        return "markdown"
    if normalized in {"txt", "csv", "json", "py", "log"}:
        return "text"
    if normalized == "docx":
        return "docx"
    return "unsupported"


def _normalize_resource_scope(course_id: Optional[str] = None, offering_id: Optional[str] = None) -> dict[str, str]:
    return {
        "course_id": normalize_text(course_id),
        "offering_id": normalize_text(offering_id),
    }


def _has_resource_scope(scope: dict[str, str]) -> bool:
    return bool(scope.get("course_id") or scope.get("offering_id"))


def _resource_scope_or_empty(scope: Optional[dict]) -> dict[str, str]:
    if not isinstance(scope, dict):
        return _normalize_resource_scope()
    return _normalize_resource_scope(scope.get("course_id"), scope.get("offering_id"))


def _resource_scope_matches(scope: Optional[dict], scope_filter: dict[str, str]) -> bool:
    if not _has_resource_scope(scope_filter):
        return True
    normalized_scope = _resource_scope_or_empty(scope)
    return (
        normalized_scope["course_id"] == scope_filter["course_id"]
        and normalized_scope["offering_id"] == scope_filter["offering_id"]
    )


async def _load_resource_scope_bindings(db: AsyncSession) -> dict[str, dict[str, str]]:
    payload = await get_kv_json(db, RESOURCE_SCOPE_BINDINGS_KV_KEY, {"resources": {}})
    raw_bindings = payload.get("resources", {}) if isinstance(payload, dict) else {}
    if not isinstance(raw_bindings, dict):
        return {}

    bindings: dict[str, dict[str, str]] = {}
    for resource_id, scope in raw_bindings.items():
        normalized_id = normalize_text(resource_id)
        if not normalized_id:
            continue
        normalized_scope = _resource_scope_or_empty(scope)
        if not _has_resource_scope(normalized_scope):
            continue
        bindings[normalized_id] = normalized_scope
    return bindings


def _student_key_candidates(student_row, raw_student_id: str) -> list[str]:
    values = [
        normalize_text(getattr(student_row, "student_id", "")),
        normalize_text(getattr(student_row, "username", "")),
        normalize_text(raw_student_id),
    ]
    candidates: list[str] = []
    for item in values:
        if item and item not in candidates:
            candidates.append(item)
    return candidates


async def _has_active_offering_membership(
    db: AsyncSession,
    student_keys: list[str],
    offering_id: str,
) -> bool:
    if not offering_id:
        return False
    member_repo = CourseMemberRepository(db)
    for key in student_keys:
        member = await member_repo.get_by_offering_and_user(offering_id, key)
        if not member:
            continue
        role = normalize_text(member.role).lower()
        status = normalize_text(member.status).lower()
        if role == "student" and status == "active":
            return True
    return False


async def _has_course_membership(
    db: AsyncSession,
    student_keys: list[str],
    course_id: str,
) -> bool:
    if not course_id:
        return False

    membership_repo = CourseStudentMembershipRepository(db)
    for key in student_keys:
        membership = await membership_repo.get_by_course_and_student(course_id, key)
        if membership is not None:
            return True

    member_repo = CourseMemberRepository(db)
    offering_repo = CourseOfferingRepository(db)
    offering_ids: list[str] = []
    for key in student_keys:
        rows = await member_repo.list_by_user(key)
        for row in rows:
            role = normalize_text(row.role).lower()
            status = normalize_text(row.status).lower()
            normalized_offering_id = normalize_text(row.offering_id)
            if role != "student" or status != "active" or not normalized_offering_id:
                continue
            if normalized_offering_id not in offering_ids:
                offering_ids.append(normalized_offering_id)

    if not offering_ids:
        return False

    offerings = await offering_repo.list_by_ids(offering_ids)
    for item in offerings:
        if normalize_text(item.template_course_id) == course_id:
            return True
    return False


async def _ensure_student_resource_scope_access(
    db: AsyncSession,
    student_row,
    raw_student_id: str,
    course_id: Optional[str],
    offering_id: Optional[str],
) -> dict[str, str]:
    scope = _normalize_resource_scope(course_id=course_id, offering_id=offering_id)
    if not _has_resource_scope(scope):
        raise HTTPException(status_code=400, detail="course_id 或 offering_id 至少提供一个")

    student_keys = _student_key_candidates(student_row, raw_student_id)
    normalized_course_id = scope["course_id"]
    normalized_offering_id = scope["offering_id"]

    if normalized_offering_id:
        offering = await CourseOfferingRepository(db).get(normalized_offering_id)
        if offering is None:
            raise HTTPException(status_code=404, detail="开课不存在")
        if not await _has_active_offering_membership(db, student_keys, normalized_offering_id):
            raise HTTPException(status_code=403, detail="无权访问该课程资料")

        offering_course_id = normalize_text(offering.template_course_id)
        if normalized_course_id and offering_course_id and normalized_course_id != offering_course_id:
            raise HTTPException(status_code=400, detail="course_id 与 offering_id 不匹配")
        if offering_course_id:
            normalized_course_id = offering_course_id

    if normalized_course_id and not await _has_course_membership(db, student_keys, normalized_course_id):
        raise HTTPException(status_code=403, detail="无权访问该课程资料")

    return _normalize_resource_scope(course_id=normalized_course_id, offering_id=normalized_offering_id)


def _student_resource_payload(row, scope: Optional[dict] = None) -> dict:
    normalized_scope = _resource_scope_or_empty(scope)
    preview_mode = _resource_preview_mode(row.file_type)
    return {
        "id": row.id,
        "filename": row.filename,
        "file_type": row.file_type,
        "content_type": row.content_type,
        "size": row.size,
        "created_at": row.created_at,
        "created_by": row.created_by,
        "course_id": normalized_scope["course_id"],
        "offering_id": normalized_scope["offering_id"],
        "preview_mode": preview_mode,
        "previewable": preview_mode != "unsupported",
        "preview_url": f"/api/student/resources/{row.id}/preview",
        "download_url": f"/api/student/resources/{row.id}/download",
    }


async def list_student_resource_files(
    student_id: str,
    name: Optional[str] = None,
    file_type: Optional[str] = None,
    course_id: Optional[str] = None,
    offering_id: Optional[str] = None,
    db: Optional[AsyncSession] = Depends(get_db),
):
    if db is None:
        raise HTTPException(status_code=503, detail="PostgreSQL session unavailable")
    student_row = await ensure_student_user(db, student_id)
    scope_filter = await _ensure_student_resource_scope_access(
        db=db,
        student_row=student_row,
        raw_student_id=student_id,
        course_id=course_id,
        offering_id=offering_id,
    )

    normalized_name = normalize_text(name).lower()
    normalized_type = normalize_text(file_type).lower().lstrip(".")
    bindings = await _load_resource_scope_bindings(db)
    rows = await ResourceRepository(db).list_all()

    payload_items = []
    for row in rows:
        if normalized_name and normalized_name not in normalize_text(row.filename).lower():
            continue
        if normalized_type and normalize_text(row.file_type).lower().lstrip(".") != normalized_type:
            continue
        if not main.os.path.exists(row.file_path):
            continue

        scope = _resource_scope_or_empty(bindings.get(row.id))
        if not _resource_scope_matches(scope, scope_filter):
            continue

        payload_items.append(_student_resource_payload(row, scope=scope))

    payload_items.sort(key=lambda item: item.get("created_at"), reverse=True)
    return {"total": len(payload_items), "items": payload_items}


async def get_student_resource_file_detail(
    resource_id: str,
    student_id: str,
    course_id: Optional[str] = None,
    offering_id: Optional[str] = None,
    db: Optional[AsyncSession] = Depends(get_db),
):
    if db is None:
        raise HTTPException(status_code=503, detail="PostgreSQL session unavailable")

    student_row = await ensure_student_user(db, student_id)
    scope_filter = await _ensure_student_resource_scope_access(
        db=db,
        student_row=student_row,
        raw_student_id=student_id,
        course_id=course_id,
        offering_id=offering_id,
    )
    bindings = await _load_resource_scope_bindings(db)
    scope = _resource_scope_or_empty(bindings.get(resource_id))
    if not _resource_scope_matches(scope, scope_filter):
        raise HTTPException(status_code=404, detail="资源文件不存在")

    row = await ResourceRepository(db).get(resource_id)
    if not row or not main.os.path.exists(row.file_path):
        raise HTTPException(status_code=404, detail="资源文件不存在")

    payload = _student_resource_payload(row, scope=scope)
    preview_mode = payload["preview_mode"]
    if preview_mode in {"markdown", "text"}:
        payload["preview_text"] = main._read_text_preview(row.file_path)
    elif preview_mode == "docx":
        payload["preview_text"] = main._read_docx_preview(row.file_path)
    else:
        payload["preview_text"] = ""
    return payload


async def preview_student_resource_file(
    resource_id: str,
    student_id: str,
    course_id: Optional[str] = None,
    offering_id: Optional[str] = None,
    db: Optional[AsyncSession] = Depends(get_db),
):
    if db is None:
        raise HTTPException(status_code=503, detail="PostgreSQL session unavailable")

    student_row = await ensure_student_user(db, student_id)
    scope_filter = await _ensure_student_resource_scope_access(
        db=db,
        student_row=student_row,
        raw_student_id=student_id,
        course_id=course_id,
        offering_id=offering_id,
    )
    bindings = await _load_resource_scope_bindings(db)
    scope = _resource_scope_or_empty(bindings.get(resource_id))
    if not _resource_scope_matches(scope, scope_filter):
        raise HTTPException(status_code=404, detail="资源文件不存在")

    row = await ResourceRepository(db).get(resource_id)
    if not row or not main.os.path.exists(row.file_path):
        raise HTTPException(status_code=404, detail="资源文件不存在")

    if _resource_preview_mode(row.file_type) != "pdf":
        raise HTTPException(status_code=400, detail="该文件类型不支持二进制在线预览")

    return FileResponse(
        path=row.file_path,
        filename="document.pdf",
        media_type="application/pdf",
        content_disposition_type="inline",
    )


async def download_student_resource_file(
    resource_id: str,
    student_id: str,
    course_id: Optional[str] = None,
    offering_id: Optional[str] = None,
    db: Optional[AsyncSession] = Depends(get_db),
):
    if db is None:
        raise HTTPException(status_code=503, detail="PostgreSQL session unavailable")

    student_row = await ensure_student_user(db, student_id)
    scope_filter = await _ensure_student_resource_scope_access(
        db=db,
        student_row=student_row,
        raw_student_id=student_id,
        course_id=course_id,
        offering_id=offering_id,
    )
    bindings = await _load_resource_scope_bindings(db)
    scope = _resource_scope_or_empty(bindings.get(resource_id))
    if not _resource_scope_matches(scope, scope_filter):
        raise HTTPException(status_code=404, detail="资源文件不存在")

    row = await ResourceRepository(db).get(resource_id)
    if not row or not main.os.path.exists(row.file_path):
        raise HTTPException(status_code=404, detail="资源文件不存在")

    media_type = row.content_type or mimetypes.guess_type(row.filename)[0] or "application/octet-stream"
    return FileResponse(
        path=row.file_path,
        filename=row.filename,
        media_type=media_type,
        content_disposition_type="attachment",
    )


router.add_api_route("/api/student/courses-with-status", get_student_courses_with_status, methods=["GET"])
router.add_api_route("/api/student/offerings", get_student_courses_with_status, methods=["GET"])
router.add_api_route("/api/student/profile", get_student_profile, methods=["GET"])
router.add_api_route("/api/student/profile/security-question", upsert_student_security_question, methods=["POST"])
router.add_api_route("/api/student/profile/change-password", change_student_password, methods=["POST"])
router.add_api_route("/api/student/offerings/{offering_id}/join", join_student_offering, methods=["POST"])
router.add_api_route("/api/student/offerings/join-by-code", join_student_offering_by_code, methods=["POST"])
router.add_api_route("/api/student/join-by-code", join_student_offering_by_code, methods=["POST"])
router.add_api_route("/api/student/offerings/{offering_id}/leave", leave_student_offering, methods=["POST"])
router.add_api_route("/api/student/offerings/{offering_id}/experiments", get_student_offering_experiments, methods=["GET"])
router.add_api_route("/api/student/resources", list_student_resource_files, methods=["GET"])
router.add_api_route("/api/student/resources/{resource_id}", get_student_resource_file_detail, methods=["GET"])
router.add_api_route("/api/student/resources/{resource_id}/preview", preview_student_resource_file, methods=["GET"])
router.add_api_route("/api/student/resources/{resource_id}/download", download_student_resource_file, methods=["GET"])
