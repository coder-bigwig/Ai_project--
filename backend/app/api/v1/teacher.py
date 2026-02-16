from fastapi import APIRouter


def _get_main_module():
    from ... import main
    return main


main = _get_main_module()


def _bind_main_symbols():
    for name in dir(main):
        if name.startswith("__"):
            continue
        globals().setdefault(name, getattr(main, name))


_bind_main_symbols()
router = APIRouter()

async def upsert_teacher_security_question(payload: TeacherSecurityQuestionUpdateRequest):
    teacher_username = _normalize_text(payload.teacher_username)
    question = _normalize_security_question(payload.security_question or "")
    answer = payload.security_answer or ""

    if not teacher_username or not question or not answer:
        raise HTTPException(status_code=400, detail="账号、密保问题和答案不能为空")
    if len(question) < 2:
        raise HTTPException(status_code=400, detail="密保问题至少 2 个字")
    if len(_normalize_security_answer(answer)) < 2:
        raise HTTPException(status_code=400, detail="密保答案至少 2 个字")

    _ensure_teacher(teacher_username)
    account_security_questions_db[teacher_username] = {
        "question": question,
        "answer_hash": _hash_security_answer(answer),
    }
    _save_user_registry()
    _append_operation_log(
        operator=teacher_username,
        action="accounts.update_security_question",
        target=teacher_username,
        detail="教师/管理员更新密保问题",
    )
    return {"message": "密保问题已保存"}

async def change_teacher_password(payload: TeacherPasswordChangeRequest):
    teacher_username = _normalize_text(payload.teacher_username)
    old_password = payload.old_password or ""
    new_password = payload.new_password or ""

    if not teacher_username or not old_password or not new_password:
        raise HTTPException(status_code=400, detail="账号、旧密码和新密码不能为空")

    _ensure_teacher(teacher_username)

    if not _verify_account_password(teacher_username, old_password):
        raise HTTPException(status_code=401, detail="旧密码错误")

    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="新密码长度不能少于 6 位")

    if old_password == new_password:
        raise HTTPException(status_code=400, detail="新密码不能与旧密码相同")

    new_hash = _hash_password(new_password)
    if new_hash == _default_password_hash():
        teacher_account_password_hashes_db.pop(teacher_username, None)
    else:
        teacher_account_password_hashes_db[teacher_username] = new_hash
    _save_user_registry()
    _append_operation_log(
        operator=teacher_username,
        action="accounts.change_password",
        target=teacher_username,
        detail="教师端修改密码",
    )
    return {"message": "密码修改成功"}

async def get_teacher_courses(teacher_username: str):
    """Return course list for the current teacher with nested experiments."""
    normalized_teacher = _normalize_text(teacher_username)
    _ensure_teacher(normalized_teacher)

    course_items = [
        item
        for item in courses_db.values()
        if _normalize_text(item.created_by) == normalized_teacher
    ]
    course_items.sort(
        key=lambda item: item.updated_at or item.created_at or datetime.min,
        reverse=True,
    )
    return [_course_to_payload(item) for item in course_items]

async def get_teacher_publish_targets(teacher_username: str):
    normalized_teacher = _normalize_text(teacher_username)
    _ensure_teacher(normalized_teacher)

    classes = sorted(_list_accessible_classes(normalized_teacher), key=lambda item: item.name)
    students = [
        item
        for item in students_db.values()
        if _student_visible_to_teacher(item, normalized_teacher)
    ]
    students.sort(key=lambda item: (item.class_name, item.student_id))

    return {
        "classes": [
            {
                "id": item.id,
                "name": item.name,
            }
            for item in classes
        ],
        "students": [
            {
                "student_id": item.student_id,
                "real_name": item.real_name,
                "class_name": item.class_name,
            }
            for item in students
        ],
    }

async def create_teacher_course(payload: CourseCreateRequest):
    normalized_teacher = _normalize_text(payload.teacher_username)
    _ensure_teacher(normalized_teacher)

    course_name = _normalize_text(payload.name)
    if not course_name:
        raise HTTPException(status_code=400, detail="课程名称不能为空")

    if _find_teacher_course_by_name(normalized_teacher, course_name):
        raise HTTPException(status_code=409, detail="课程名称已存在")

    course = _create_course_record(course_name, normalized_teacher, payload.description or "")
    _save_course_registry()
    return _course_to_payload(course)

async def update_teacher_course(course_id: str, payload: CourseUpdateRequest):
    normalized_teacher = _normalize_text(payload.teacher_username)
    _ensure_teacher(normalized_teacher)

    course = courses_db.get(course_id)
    if not course or _normalize_text(course.created_by) != normalized_teacher:
        raise HTTPException(status_code=404, detail="课程不存在")

    next_name = _normalize_text(payload.name) or course.name
    if _normalize_text(next_name).lower() != _normalize_text(course.name).lower():
        if _find_teacher_course_by_name(normalized_teacher, next_name):
            raise HTTPException(status_code=409, detail="课程名称已存在")
        old_name = course.name
        course.name = next_name
        # Keep experiment grouping consistent with course rename.
        for exp in experiments_db.values():
            if _normalize_text(exp.course_id) != _normalize_text(course.id):
                continue
            if _normalize_text(exp.created_by) != normalized_teacher:
                continue
            if _normalize_text(exp.course_name) == _normalize_text(old_name):
                exp.course_name = next_name
        _save_experiment_registry()

    if payload.description is not None:
        course.description = _normalize_text(payload.description)
    course.updated_at = datetime.now()
    _save_course_registry()
    return _course_to_payload(course)

async def delete_teacher_course(course_id: str, teacher_username: str, delete_experiments: bool = False):
    normalized_teacher = _normalize_text(teacher_username)
    _ensure_teacher(normalized_teacher)

    course = courses_db.get(course_id)
    if not course or _normalize_text(course.created_by) != normalized_teacher:
        raise HTTPException(status_code=404, detail="课程不存在")

    related_experiments = _list_course_experiments(course)
    if related_experiments and not delete_experiments:
        raise HTTPException(status_code=409, detail="课程下存在实验，请先删除实验或传入 delete_experiments=true")

    if delete_experiments:
        removed_attachment_ids = []
        for item in related_experiments:
            experiments_db.pop(item.id, None)
            removed_attachment_ids.extend(
                att_id
                for att_id, att in attachments_db.items()
                if att.experiment_id == item.id
            )

        for att_id in removed_attachment_ids:
            att = attachments_db.pop(att_id, None)
            if att and os.path.exists(att.file_path):
                try:
                    os.remove(att.file_path)
                except OSError:
                    pass

        if removed_attachment_ids:
            _save_attachment_registry()

        _save_experiment_registry()

    courses_db.pop(course_id, None)
    _save_course_registry()
    return {"message": "课程已删除", "id": course_id}

async def toggle_course_publish(course_id: str, teacher_username: str, published: bool):
    """发布/取消发布课程"""
    normalized_teacher = _normalize_text(teacher_username)
    _ensure_teacher(normalized_teacher)

    course = courses_db.get(course_id)
    if not course or _normalize_text(course.created_by) != normalized_teacher:
        raise HTTPException(status_code=404, detail="课程不存在")

    related_experiments = _list_course_experiments(course)
    if not related_experiments:
        return {
            "message": "课程下暂无实验",
            "published": published,
            "updated": 0,
        }

    for item in related_experiments:
        item.published = published

    course.updated_at = datetime.now()
    _save_experiment_registry()
    _save_course_registry()
    return {
        "message": f"Course publish state updated: {'published' if published else 'unpublished'}",
        "published": published,
        "updated": len(related_experiments),
    }

async def get_all_student_progress(teacher_username: str):
    """Only include progress records for courses created by current teacher."""
    normalized_teacher = _normalize_text(teacher_username)
    _ensure_teacher(normalized_teacher)
    owned_course_ids = {
        item.id
        for item in experiments_db.values()
        if _normalize_text(item.created_by) == normalized_teacher
    }

    progress = [
        {
            "student_id": exp.student_id,
            "experiment_id": exp.experiment_id,
            "status": exp.status.value,
            "start_time": exp.start_time,
            "submit_time": exp.submit_time,
            "score": exp.score
        }
        for exp in student_experiments_db.values()
        if exp.experiment_id in owned_course_ids
        and _is_student_progress_record(exp.student_id)
    ]

    return progress

async def get_statistics():
    """获取统计"""
    total_experiments = len(experiments_db)
    total_submissions = len(student_experiments_db)
    
    status_count = {}
    for exp in student_experiments_db.values():
        status_count[exp.status.value] = status_count.get(exp.status.value, 0) + 1
    
    return {
        "total_experiments": total_experiments,
        "total_submissions": total_submissions,
        "status_distribution": status_count
    }

router.add_api_route("/api/teacher/profile/security-question", upsert_teacher_security_question, methods=["POST"])
router.add_api_route("/api/teacher/profile/change-password", change_teacher_password, methods=["POST"])
router.add_api_route("/api/teacher/courses", get_teacher_courses, methods=["GET"])
router.add_api_route("/api/teacher/publish-targets", get_teacher_publish_targets, methods=["GET"])
router.add_api_route("/api/teacher/courses", create_teacher_course, methods=["POST"])
router.add_api_route("/api/teacher/courses/{course_id}", update_teacher_course, methods=["PATCH"])
router.add_api_route("/api/teacher/courses/{course_id}", delete_teacher_course, methods=["DELETE"])
router.add_api_route("/api/teacher/courses/{course_id}/publish", toggle_course_publish, methods=["PATCH"])
router.add_api_route("/api/teacher/progress", get_all_student_progress, methods=["GET"])
router.add_api_route("/api/teacher/statistics", get_statistics, methods=["GET"])
