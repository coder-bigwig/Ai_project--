from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ..repositories.postgres import (
    AttachmentRepository,
    CourseRepository,
    ExperimentRepository,
    KVStoreRepository,
    OperationLogRepository,
    ResourceRepository,
    SubmissionPdfRepository,
    SubmissionRepository,
    UserRepository,
)


def _normalize_iso_datetime(value) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        text = value.strip().replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            return None
    return None


def _normalize_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _normalize_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


async def load_state_from_postgres(main_module, db: AsyncSession) -> dict[str, int]:
    user_repo = UserRepository(db)
    course_repo = CourseRepository(db)
    experiment_repo = ExperimentRepository(db)
    submission_repo = SubmissionRepository(db)
    submission_pdf_repo = SubmissionPdfRepository(db)
    resource_repo = ResourceRepository(db)
    attachment_repo = AttachmentRepository(db)
    operation_log_repo = OperationLogRepository(db)
    kv_repo = KVStoreRepository(db)

    classes = await user_repo.list_classes()
    users = await user_repo.list_users()
    courses = await course_repo.list_all()
    experiments = await experiment_repo.list_all()
    submissions = await submission_repo.list_all()
    submission_pdfs = await submission_pdf_repo.list_all()
    resources = await resource_repo.list_all()
    attachments = await attachment_repo.list_all()
    operation_logs = await operation_log_repo.list_all()
    kv_rows = await kv_repo.list_all()
    kv_map = {row.key: row.value_json for row in kv_rows}

    main_module.classes_db.clear()
    main_module.teachers_db.clear()
    main_module.students_db.clear()
    main_module.teacher_account_password_hashes_db.clear()
    main_module.account_security_questions_db.clear()
    main_module.courses_db.clear()
    main_module.experiments_db.clear()
    main_module.student_experiments_db.clear()
    main_module.submission_pdfs_db.clear()
    main_module.resource_files_db.clear()
    main_module.attachments_db.clear()
    main_module.operation_logs_db.clear()

    for row in classes:
        try:
            record = main_module.ClassRecord(
                id=row.id,
                name=row.name,
                created_by=row.created_by,
                created_at=row.created_at,
            )
            main_module.classes_db[record.id] = record
        except Exception:
            continue

    for row in users:
        try:
            role = (row.role or "").strip().lower()
            if role == "teacher":
                teacher = main_module.TeacherRecord(
                    username=row.username,
                    real_name=row.real_name or row.username,
                    created_by=row.created_by or "system",
                    created_at=row.created_at,
                )
                main_module.teachers_db[teacher.username] = teacher
            elif role == "student":
                student_id = row.student_id or row.username
                student = main_module.StudentRecord(
                    student_id=student_id,
                    username=row.username,
                    real_name=row.real_name or student_id,
                    class_name=row.class_name or "",
                    admission_year=row.admission_year or "",
                    organization=row.organization or "",
                    phone=row.phone or "",
                    role="student",
                    created_by=row.created_by or "",
                    password_hash=row.password_hash or main_module._hash_password(main_module.DEFAULT_PASSWORD),
                    security_question=row.security_question or "",
                    security_answer_hash=row.security_answer_hash or "",
                    created_at=row.created_at,
                    updated_at=row.updated_at,
                )
                main_module.students_db[student.student_id] = student
        except Exception:
            continue

    for row in courses:
        try:
            course = main_module.CourseRecord(
                id=row.id,
                name=row.name,
                description=row.description or "",
                created_by=row.created_by,
                created_at=row.created_at,
                updated_at=row.updated_at,
            )
            main_module.courses_db[course.id] = course
        except Exception:
            continue

    for row in experiments:
        try:
            difficulty = row.difficulty or main_module.DifficultyLevel.BEGINNER.value
            publish_scope = row.publish_scope or main_module.PublishScope.ALL.value
            exp = main_module.Experiment(
                id=row.id,
                course_id=row.course_id,
                course_name=row.course_name or "",
                title=row.title,
                description=row.description or "",
                difficulty=difficulty,
                tags=_normalize_list(row.tags),
                notebook_path=row.notebook_path or "",
                resources=_normalize_dict(row.resources),
                deadline=row.deadline,
                created_at=row.created_at,
                created_by=row.created_by,
                published=bool(row.published),
                publish_scope=publish_scope,
                target_class_names=_normalize_list(row.target_class_names),
                target_student_ids=_normalize_list(row.target_student_ids),
            )
            main_module.experiments_db[exp.id] = exp
        except Exception:
            continue

    for row in submissions:
        try:
            status_value = row.status or main_module.ExperimentStatus.NOT_STARTED.value
            try:
                status_value = main_module.ExperimentStatus(status_value)
            except ValueError:
                status_value = main_module.ExperimentStatus.NOT_STARTED
            item = main_module.StudentExperiment(
                id=row.id,
                experiment_id=row.experiment_id,
                student_id=row.student_id,
                status=status_value,
                start_time=row.start_time,
                submit_time=row.submit_time,
                notebook_content=row.notebook_content or "",
                score=row.score,
                ai_feedback=row.ai_feedback or "",
                teacher_comment=row.teacher_comment or "",
            )
            main_module.student_experiments_db[item.id] = item
        except Exception:
            continue

    for row in submission_pdfs:
        try:
            annotations = []
            for raw_item in _normalize_list(row.annotations):
                if not isinstance(raw_item, dict):
                    continue
                ann = main_module.PDFAnnotation(
                    id=str(raw_item.get("id") or ""),
                    teacher_username=str(raw_item.get("teacher_username") or ""),
                    content=str(raw_item.get("content") or ""),
                    created_at=_normalize_iso_datetime(raw_item.get("created_at")) or row.created_at,
                )
                annotations.append(ann)

            item = main_module.StudentSubmissionPDF(
                id=row.id,
                student_exp_id=row.submission_id,
                experiment_id=row.experiment_id,
                student_id=row.student_id,
                filename=row.filename,
                file_path=row.file_path,
                content_type=row.content_type or "",
                size=row.size,
                created_at=row.created_at,
                viewed=bool(row.viewed),
                viewed_at=row.viewed_at,
                viewed_by=row.viewed_by or None,
                reviewed=bool(row.reviewed),
                reviewed_at=row.reviewed_at,
                reviewed_by=row.reviewed_by or None,
                annotations=annotations,
            )
            main_module.submission_pdfs_db[item.id] = item
        except Exception:
            continue

    for row in resources:
        try:
            record = main_module.ResourceFile(
                id=row.id,
                filename=row.filename,
                file_path=row.file_path,
                file_type=row.file_type,
                content_type=row.content_type,
                size=row.size,
                created_at=row.created_at,
                created_by=row.created_by,
            )
            main_module.resource_files_db[record.id] = record
        except Exception:
            continue

    for row in attachments:
        try:
            record = main_module.Attachment(
                id=row.id,
                experiment_id=row.experiment_id,
                filename=row.filename,
                file_path=row.file_path,
                content_type=row.content_type,
                size=row.size,
                created_at=row.created_at,
            )
            main_module.attachments_db[record.id] = record
        except Exception:
            continue

    for row in operation_logs:
        try:
            item = main_module.OperationLogEntry(
                id=row.id,
                operator=row.operator,
                action=row.action,
                target=row.target,
                detail=row.detail or "",
                success=bool(row.success),
                created_at=row.created_at,
            )
            main_module.operation_logs_db.append(item)
        except Exception:
            continue

    account_hashes = _normalize_dict(kv_map.get("account_password_hashes"))
    for account, password_hash in account_hashes.items():
        normalized_account = main_module._normalize_text(account)
        normalized_hash = main_module._normalize_text(password_hash).lower()
        if normalized_account and main_module.PASSWORD_HASH_PATTERN.fullmatch(normalized_hash):
            main_module.teacher_account_password_hashes_db[normalized_account] = normalized_hash

    security_questions = _normalize_dict(kv_map.get("account_security_questions"))
    for account, payload in security_questions.items():
        normalized_account = main_module._normalize_text(account)
        raw_payload = payload if isinstance(payload, dict) else {}
        normalized_question = main_module._normalize_security_question(raw_payload.get("question") or "")
        normalized_answer_hash = main_module._normalize_text(raw_payload.get("answer_hash") or "").lower()
        if not normalized_account or not normalized_question:
            continue
        if not main_module.PASSWORD_HASH_PATTERN.fullmatch(normalized_answer_hash):
            continue
        main_module.account_security_questions_db[normalized_account] = {
            "question": normalized_question,
            "answer_hash": normalized_answer_hash,
        }

    main_module.ai_shared_config_db.clear()
    main_module.ai_shared_config_db.update(main_module.DEFAULT_AI_SHARED_CONFIG)
    ai_shared_config = _normalize_dict(kv_map.get("ai_shared_config"))
    if ai_shared_config:
        main_module.ai_shared_config_db.update(main_module._normalize_ai_shared_config(ai_shared_config))

    main_module.ai_chat_history_db.clear()
    ai_chat_history = _normalize_dict(kv_map.get("ai_chat_history"))
    for username, items in ai_chat_history.items():
        normalized_username = main_module._normalize_text(username)
        if not normalized_username:
            continue
        main_module.ai_chat_history_db[normalized_username] = main_module._normalize_chat_history_items(items)

    main_module.resource_policy_db.clear()
    main_module.resource_policy_db.update(main_module._default_resource_policy_payload())
    saved_policy = _normalize_dict(kv_map.get("resource_policy"))
    if saved_policy:
        main_module.resource_policy_db.update(saved_policy)

    return {
        "classes": len(main_module.classes_db),
        "teachers": len(main_module.teachers_db),
        "students": len(main_module.students_db),
        "courses": len(main_module.courses_db),
        "experiments": len(main_module.experiments_db),
        "submissions": len(main_module.student_experiments_db),
        "submission_pdfs": len(main_module.submission_pdfs_db),
        "resources": len(main_module.resource_files_db),
        "attachments": len(main_module.attachments_db),
        "operation_logs": len(main_module.operation_logs_db),
    }

