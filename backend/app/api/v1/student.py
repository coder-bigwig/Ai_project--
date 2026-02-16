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

async def get_student_courses_with_status(student_id: str):
    """获取学生的课程列表及完成状态"""
    normalized_student_id = _normalize_text(student_id)
    _ensure_student(normalized_student_id)
    student = students_db[normalized_student_id]

    # 获取对该学生可见的课程
    published_courses = [exp for exp in experiments_db.values() if _is_experiment_visible_to_student(exp, student)]
    
    # 获取该学生已有的实验记录
    student_records = {
        exp.experiment_id: exp
        for exp in student_experiments_db.values()
        if exp.student_id == normalized_student_id
    }
    
    # 组合数据
    courses_with_status = []
    for course in published_courses:
        record = student_records.get(course.id)
        courses_with_status.append({
            "course": course,
            "status": record.status.value if record else "未开始",
            "start_time": record.start_time if record else None,
            "submit_time": record.submit_time if record else None,
            "score": record.score if record else None,
            "student_exp_id": record.id if record else None
        })
    
    return courses_with_status

async def get_student_profile(student_id: str):
    """Get student profile for student-side header display."""
    student = students_db.get(student_id)
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")
    return {
        "student_id": student.student_id,
        "real_name": student.real_name,
        "class_name": student.class_name,
        "organization": student.organization,
        "major": student.organization,
        "admission_year": _normalize_admission_year(student.admission_year),
        "admission_year_label": _format_admission_year_label(student.admission_year),
        "security_question": _normalize_security_question(student.security_question or ""),
        "security_question_set": bool(_normalize_security_question(student.security_question or "")),
    }

async def upsert_student_security_question(payload: StudentSecurityQuestionUpdateRequest):
    student_id = _normalize_text(payload.student_id)
    question = _normalize_security_question(payload.security_question or "")
    answer = payload.security_answer or ""

    if not student_id or not question or not answer:
        raise HTTPException(status_code=400, detail="学号、密保问题和答案不能为空")
    if len(question) < 2:
        raise HTTPException(status_code=400, detail="密保问题至少2个字符")
    if len(_normalize_security_answer(answer)) < 2:
        raise HTTPException(status_code=400, detail="密保答案至少2个字符")

    student = students_db.get(student_id)
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")

    student.security_question = question
    student.security_answer_hash = _hash_security_answer(answer)
    student.updated_at = datetime.now()
    _save_user_registry()
    return {"message": "密保问题已保存"}

async def change_student_password(payload: StudentPasswordChangeRequest):
    student_id = _normalize_text(payload.student_id)
    old_password = payload.old_password or ""
    new_password = payload.new_password or ""

    if not student_id or not old_password or not new_password:
        raise HTTPException(status_code=400, detail="学号、旧密码和新密码不能为空")

    student = students_db.get(student_id)
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")

    if student.password_hash != _hash_password(old_password):
        raise HTTPException(status_code=401, detail="旧密码错误")

    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="新密码长度不能少于6位")

    if old_password == new_password:
        raise HTTPException(status_code=400, detail="新密码不能与旧密码相同")

    student.password_hash = _hash_password(new_password)
    student.updated_at = datetime.now()
    _save_user_registry()

    return {"message": "密码修改成功"}

async def list_student_resource_files(
    student_id: str,
    name: Optional[str] = None,
    file_type: Optional[str] = None
):
    """学生查看资源文件列表"""
    _ensure_student(student_id)
    items = _list_resource_records(name_filter=name or "", type_filter=file_type or "")
    payload_items = [_resource_to_payload(item, route_prefix="/api/student/resources") for item in items]
    return {"total": len(payload_items), "items": payload_items}

async def get_student_resource_file_detail(resource_id: str, student_id: str):
    """学生查看资源文件详情"""
    _ensure_student(student_id)
    record = _get_resource_or_404(resource_id)
    _ensure_resource_file_exists(record)

    payload = _resource_to_payload(record, route_prefix="/api/student/resources")
    preview_mode = payload["preview_mode"]
    if preview_mode in {"markdown", "text"}:
        payload["preview_text"] = _read_text_preview(record.file_path)
    elif preview_mode == "docx":
        payload["preview_text"] = _read_docx_preview(record.file_path)
    else:
        payload["preview_text"] = ""
    return payload

async def preview_student_resource_file(resource_id: str, student_id: str):
    """学生在线预览资源文件"""
    _ensure_student(student_id)
    record = _get_resource_or_404(resource_id)
    _ensure_resource_file_exists(record)

    preview_mode = _resource_preview_mode(record)
    if preview_mode != "pdf":
        raise HTTPException(status_code=400, detail="该文件类型不支持二进制在线预览")

    return FileResponse(
        path=record.file_path,
        filename="document.pdf",
        media_type="application/pdf",
        content_disposition_type="inline",
    )

async def download_student_resource_file(resource_id: str, student_id: str):
    """学生下载资源文件"""
    _ensure_student(student_id)
    record = _get_resource_or_404(resource_id)
    _ensure_resource_file_exists(record)

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
