from typing import Optional

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.session import get_db
from ...services.offering_service import build_offering_service
from ...services.teacher_service import build_teacher_service


def _get_main_module():
    from ... import main
    return main


main = _get_main_module()
router = APIRouter()


async def upsert_teacher_security_question(
    payload: main.TeacherSecurityQuestionUpdateRequest,
    db: Optional[AsyncSession] = Depends(get_db),
):
    service = build_teacher_service(main_module=main, db=db)
    return await service.upsert_teacher_security_question(payload=payload)


async def change_teacher_password(
    payload: main.TeacherPasswordChangeRequest,
    db: Optional[AsyncSession] = Depends(get_db),
):
    service = build_teacher_service(main_module=main, db=db)
    return await service.change_teacher_password(payload=payload)


async def get_teacher_courses(
    teacher_username: str,
    db: Optional[AsyncSession] = Depends(get_db),
):
    service = build_teacher_service(main_module=main, db=db)
    return await service.get_teacher_courses(teacher_username=teacher_username)


async def get_teacher_publish_targets(
    teacher_username: str,
    db: Optional[AsyncSession] = Depends(get_db),
):
    service = build_teacher_service(main_module=main, db=db)
    return await service.get_teacher_publish_targets(teacher_username=teacher_username)


async def list_teacher_course_students(
    course_id: str,
    teacher_username: str,
    keyword: str = "",
    class_name: str = "",
    admission_year: str = "",
    page: int = 1,
    page_size: int = 20,
    db: Optional[AsyncSession] = Depends(get_db),
):
    service = build_teacher_service(main_module=main, db=db)
    return await service.list_course_students(
        course_id=course_id,
        teacher_username=teacher_username,
        keyword=keyword,
        class_name=class_name,
        admission_year=admission_year,
        page=page,
        page_size=page_size,
    )


async def list_teacher_course_student_classes(
    course_id: str,
    teacher_username: str,
    db: Optional[AsyncSession] = Depends(get_db),
):
    service = build_teacher_service(main_module=main, db=db)
    return await service.list_course_student_class_options(course_id=course_id, teacher_username=teacher_username)


async def list_teacher_course_student_admission_years(
    course_id: str,
    teacher_username: str,
    db: Optional[AsyncSession] = Depends(get_db),
):
    service = build_teacher_service(main_module=main, db=db)
    return await service.list_course_student_admission_year_options(course_id=course_id, teacher_username=teacher_username)


async def download_teacher_course_student_template(
    course_id: str,
    teacher_username: str,
    format: str = "xlsx",
    db: Optional[AsyncSession] = Depends(get_db),
):
    service = build_teacher_service(main_module=main, db=db)
    return await service.download_course_student_template(
        course_id=course_id,
        teacher_username=teacher_username,
        format=format,
    )


async def import_teacher_course_students(
    course_id: str,
    teacher_username: str,
    file: UploadFile = File(...),
    db: Optional[AsyncSession] = Depends(get_db),
):
    service = build_teacher_service(main_module=main, db=db)
    return await service.import_course_students(
        course_id=course_id,
        teacher_username=teacher_username,
        file=file,
    )


async def reset_teacher_course_student_password(
    course_id: str,
    student_id: str,
    teacher_username: str,
    db: Optional[AsyncSession] = Depends(get_db),
):
    service = build_teacher_service(main_module=main, db=db)
    return await service.reset_course_student_password(
        course_id=course_id,
        student_id=student_id,
        teacher_username=teacher_username,
    )


async def remove_teacher_course_student(
    course_id: str,
    student_id: str,
    teacher_username: str,
    db: Optional[AsyncSession] = Depends(get_db),
):
    service = build_teacher_service(main_module=main, db=db)
    return await service.remove_course_student(
        course_id=course_id,
        student_id=student_id,
        teacher_username=teacher_username,
    )


async def batch_remove_teacher_course_students(
    course_id: str,
    teacher_username: str,
    class_name: str = "",
    db: Optional[AsyncSession] = Depends(get_db),
):
    service = build_teacher_service(main_module=main, db=db)
    return await service.batch_remove_course_students(
        course_id=course_id,
        teacher_username=teacher_username,
        class_name=class_name,
    )


async def create_teacher_course(
    payload: main.CourseCreateRequest,
    db: Optional[AsyncSession] = Depends(get_db),
):
    service = build_teacher_service(main_module=main, db=db)
    return await service.create_teacher_course(payload=payload)


async def update_teacher_course(
    course_id: str,
    payload: main.CourseUpdateRequest,
    db: Optional[AsyncSession] = Depends(get_db),
):
    service = build_teacher_service(main_module=main, db=db)
    return await service.update_teacher_course(course_id=course_id, payload=payload)


async def delete_teacher_course(
    course_id: str,
    teacher_username: str,
    delete_experiments: bool = False,
    db: Optional[AsyncSession] = Depends(get_db),
):
    service = build_teacher_service(main_module=main, db=db)
    return await service.delete_teacher_course(
        course_id=course_id,
        teacher_username=teacher_username,
        delete_experiments=delete_experiments,
    )


async def toggle_course_publish(
    course_id: str,
    teacher_username: str,
    published: bool,
    db: Optional[AsyncSession] = Depends(get_db),
):
    service = build_teacher_service(main_module=main, db=db)
    return await service.toggle_course_publish(
        course_id=course_id,
        teacher_username=teacher_username,
        published=published,
    )


async def get_all_student_progress(
    teacher_username: str,
    db: Optional[AsyncSession] = Depends(get_db),
):
    service = build_teacher_service(main_module=main, db=db)
    return await service.get_all_student_progress(teacher_username=teacher_username)


async def get_statistics(
    teacher_username: str = "",
    course_id: str = "",
    days: int = 30,
    db: Optional[AsyncSession] = Depends(get_db),
):
    service = build_teacher_service(main_module=main, db=db)
    return await service.get_statistics(
        teacher_username=teacher_username,
        course_id=course_id,
        days=days,
    )


async def create_teacher_offering(
    payload: main.OfferingCreateRequest,
    db: Optional[AsyncSession] = Depends(get_db),
):
    service = build_offering_service(main_module=main, db=db)
    return await service.create_offering(
        teacher_id=payload.teacher_username,
        template_course_id=payload.template_course_id,
        offering_code=payload.offering_code,
        term=payload.term or "",
        major=payload.major or "",
        class_name=payload.class_name,
        join_code=None,
    )


async def list_teacher_offerings(
    teacher_username: str,
    db: Optional[AsyncSession] = Depends(get_db),
):
    service = build_offering_service(main_module=main, db=db)
    return await service.list_teacher_offerings(teacher_id=teacher_username)


async def update_teacher_offering(
    offering_id: str,
    payload: main.OfferingUpdateRequest,
    db: Optional[AsyncSession] = Depends(get_db),
):
    service = build_offering_service(main_module=main, db=db)
    return await service.update_offering_status(
        teacher_id=payload.teacher_username,
        offering_id=offering_id,
        status=payload.status,
    )


async def delete_teacher_offering(
    offering_id: str,
    teacher_username: str,
    db: Optional[AsyncSession] = Depends(get_db),
):
    service = build_offering_service(main_module=main, db=db)
    return await service.remove_offering(
        teacher_id=teacher_username,
        offering_id=offering_id,
    )


async def get_teacher_offering_detail(
    offering_id: str,
    teacher_username: str,
    db: Optional[AsyncSession] = Depends(get_db),
):
    service = build_offering_service(main_module=main, db=db)
    return await service.get_teacher_offering_detail(
        teacher_id=teacher_username,
        offering_id=offering_id,
    )


async def list_teacher_offering_members(
    offering_id: str,
    teacher_username: str,
    db: Optional[AsyncSession] = Depends(get_db),
):
    service = build_offering_service(main_module=main, db=db)
    return await service.list_teacher_offering_members(
        teacher_id=teacher_username,
        offering_id=offering_id,
    )


async def add_teacher_offering_members(
    offering_id: str,
    payload: main.OfferingMembersUpsertRequest,
    db: Optional[AsyncSession] = Depends(get_db),
):
    service = build_offering_service(main_module=main, db=db)
    members = [{"user_key": item.user_key, "role": item.role} for item in (payload.members or [])]
    return await service.add_members(
        teacher_id=payload.teacher_username,
        offering_id=offering_id,
        members=members,
    )


async def remove_teacher_offering_member(
    offering_id: str,
    user_key: str,
    teacher_username: str,
    db: Optional[AsyncSession] = Depends(get_db),
):
    service = build_offering_service(main_module=main, db=db)
    return await service.remove_member(
        teacher_id=teacher_username,
        offering_id=offering_id,
        user_key=user_key,
    )


router.add_api_route("/api/teacher/profile/security-question", upsert_teacher_security_question, methods=["POST"])
router.add_api_route("/api/teacher/profile/change-password", change_teacher_password, methods=["POST"])
router.add_api_route("/api/teacher/courses", get_teacher_courses, methods=["GET"])
router.add_api_route("/api/teacher/publish-targets", get_teacher_publish_targets, methods=["GET"])
router.add_api_route("/api/teacher/courses", create_teacher_course, methods=["POST"])
router.add_api_route("/api/teacher/courses/{course_id}/students", list_teacher_course_students, methods=["GET"])
router.add_api_route("/api/teacher/courses/{course_id}/students/classes", list_teacher_course_student_classes, methods=["GET"])
router.add_api_route("/api/teacher/courses/{course_id}/students/admission-years", list_teacher_course_student_admission_years, methods=["GET"])
router.add_api_route("/api/teacher/courses/{course_id}/students/template", download_teacher_course_student_template, methods=["GET"])
router.add_api_route("/api/teacher/courses/{course_id}/students/import", import_teacher_course_students, methods=["POST"])
router.add_api_route("/api/teacher/courses/{course_id}/students/{student_id}/reset-password", reset_teacher_course_student_password, methods=["POST"])
router.add_api_route("/api/teacher/courses/{course_id}/students/{student_id}", remove_teacher_course_student, methods=["DELETE"])
router.add_api_route("/api/teacher/courses/{course_id}/students", batch_remove_teacher_course_students, methods=["DELETE"])
router.add_api_route("/api/teacher/courses/{course_id}", update_teacher_course, methods=["PATCH"])
router.add_api_route("/api/teacher/courses/{course_id}", delete_teacher_course, methods=["DELETE"])
router.add_api_route("/api/teacher/courses/{course_id}/publish", toggle_course_publish, methods=["PATCH"])
router.add_api_route("/api/teacher/progress", get_all_student_progress, methods=["GET"])
router.add_api_route("/api/teacher/statistics", get_statistics, methods=["GET"])
router.add_api_route("/api/teacher/offerings", create_teacher_offering, methods=["POST"])
router.add_api_route("/api/teacher/offerings", list_teacher_offerings, methods=["GET"])
router.add_api_route("/api/teacher/offerings/{offering_id}", get_teacher_offering_detail, methods=["GET"])
router.add_api_route("/api/teacher/offerings/{offering_id}", update_teacher_offering, methods=["PATCH"])
router.add_api_route("/api/teacher/offerings/{offering_id}", delete_teacher_offering, methods=["DELETE"])
router.add_api_route("/api/teacher/offerings/{offering_id}/members", list_teacher_offering_members, methods=["GET"])
router.add_api_route("/api/teacher/offerings/{offering_id}/members", add_teacher_offering_members, methods=["POST"])
router.add_api_route("/api/teacher/offerings/{offering_id}/members/{user_key}", remove_teacher_offering_member, methods=["DELETE"])
