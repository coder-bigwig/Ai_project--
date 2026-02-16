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

async def list_admin_teachers(admin_username: str):
    _ensure_admin(admin_username)
    return _list_admin_teacher_items()

async def create_admin_teacher(payload: TeacherCreateRequest):
    admin_username = _normalize_text(payload.admin_username)
    _ensure_admin(admin_username)

    teacher_username = _normalize_text(payload.username)
    real_name = _normalize_text(payload.real_name) or teacher_username
    if not teacher_username:
        raise HTTPException(status_code=400, detail="教师账号不能为空")
    if is_admin(teacher_username):
        raise HTTPException(status_code=409, detail="账号与管理员冲突")
    if teacher_username in students_db:
        raise HTTPException(status_code=409, detail="账号与学生学号冲突")
    if is_teacher(teacher_username):
        raise HTTPException(status_code=409, detail="教师账号已存在")

    teachers_db[teacher_username] = TeacherRecord(
        username=teacher_username,
        real_name=real_name,
        created_by=admin_username,
        created_at=datetime.now(),
    )
    _save_user_registry()
    _append_operation_log(
        operator=admin_username,
        action="teachers.create",
        target=teacher_username,
        detail=f"real_name={real_name}",
    )
    return {
        "message": "教师账号已创建",
        "teacher": {
            "username": teacher_username,
            "real_name": real_name,
            "source": "registry",
            "created_by": admin_username,
            "created_at": teachers_db[teacher_username].created_at,
        },
    }

async def delete_admin_teacher(teacher_username: str, admin_username: str):
    _ensure_admin(admin_username)
    normalized_teacher = _normalize_text(teacher_username)
    if not normalized_teacher:
        raise HTTPException(status_code=400, detail="教师账号不能为空")
    if normalized_teacher in TEACHER_ACCOUNTS and normalized_teacher not in teachers_db:
        raise HTTPException(status_code=400, detail="内置教师账号请通过环境变量修改")
    if normalized_teacher not in teachers_db:
        raise HTTPException(status_code=404, detail="教师账号不存在")

    del teachers_db[normalized_teacher]
    _save_user_registry()

    overrides = resource_policy_db.get("overrides", {})
    if isinstance(overrides, dict) and normalized_teacher in overrides:
        overrides.pop(normalized_teacher, None)
        resource_policy_db["overrides"] = overrides
        _save_resource_policy()

    teacher_account_password_hashes_db.pop(normalized_teacher, None)
    account_security_questions_db.pop(normalized_teacher, None)
    _save_user_registry()

    _append_operation_log(
        operator=admin_username,
        action="teachers.delete",
        target=normalized_teacher,
    )
    return {"message": "教师账号已删除", "username": normalized_teacher}

async def list_admin_classes(teacher_username: str):
    _ensure_teacher(teacher_username)
    return sorted(_list_accessible_classes(teacher_username), key=lambda item: item.name)

async def download_class_template(teacher_username: str, format: str = "xlsx"):
    _ensure_teacher(teacher_username)
    template_format = format.lower()

    if template_format == "csv":
        payload = _build_class_csv_template()
        return StreamingResponse(
            io.BytesIO(payload),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=class_import_template.csv"},
        )

    if template_format == "xlsx":
        payload = _build_class_xlsx_template()
        return StreamingResponse(
            io.BytesIO(payload),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=class_import_template.xlsx"},
        )

    raise HTTPException(status_code=400, detail="format 必须是 xlsx 或 csv")

async def import_admin_classes(teacher_username: str, file: UploadFile = File(...)):
    _ensure_teacher(teacher_username)
    normalized_teacher = _normalize_text(teacher_username)
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")

    file_content = await file.read()
    parsed_rows = _parse_class_import_rows(file.filename, file_content)
    now = datetime.now()

    existing_class_names = {item.name for item in _list_accessible_classes(normalized_teacher)}
    file_class_names = set()
    success_classes: List[ClassRecord] = []
    errors = []
    skipped_count = 0

    for row_number, row in parsed_rows:
        admission_year_raw, major_name, class_name = row
        normalized_year = _normalize_admission_year(admission_year_raw)
        normalized_major = _normalize_text(major_name)
        normalized_class = _normalize_text(class_name)

        if not all([normalized_year, normalized_major, normalized_class]):
            errors.append({"row": row_number, "reason": "required fields cannot be empty"})
            continue

        merged_class_name = _build_class_name(normalized_year, normalized_major, normalized_class)
        if not merged_class_name:
            errors.append({"row": row_number, "reason": "班级名称格式无效"})
            continue

        if merged_class_name in existing_class_names:
            skipped_count += 1
            errors.append({"row": row_number, "reason": f"班级重复（系统中已存在）: {merged_class_name}"})
            continue

        if merged_class_name in file_class_names:
            skipped_count += 1
            errors.append({"row": row_number, "reason": f"班级重复（文件内）: {merged_class_name}"})
            continue

        file_class_names.add(merged_class_name)
        success_classes.append(
            ClassRecord(
                id=str(uuid.uuid4()),
                name=merged_class_name,
                created_by=normalized_teacher,
                created_at=now,
            )
        )

    for record in success_classes:
        classes_db[record.id] = record

    if success_classes:
        _save_user_registry()
    _append_operation_log(
        operator=normalized_teacher,
        action="classes.import",
        target="classes",
        detail=f"success={len(success_classes)}, skipped={skipped_count}, failed={len(errors) - skipped_count}",
    )

    failed_count = len(errors) - skipped_count
    return {
        "total_rows": len(parsed_rows),
        "success_count": len(success_classes),
        "skipped_count": skipped_count,
        "failed_count": failed_count,
        "errors": errors,
    }

async def create_admin_class(payload: ClassCreateRequest):
    _ensure_teacher(payload.teacher_username)
    normalized_teacher = _normalize_text(payload.teacher_username)
    class_name = _normalize_text(payload.name)
    if not class_name:
        raise HTTPException(status_code=400, detail="班级名称不能为空")
    if any(item.name == class_name for item in _list_accessible_classes(normalized_teacher)):
        raise HTTPException(status_code=400, detail="班级已存在")

    record = ClassRecord(
        id=str(uuid.uuid4()),
        name=class_name,
        created_by=normalized_teacher,
        created_at=datetime.now(),
    )
    classes_db[record.id] = record
    _save_user_registry()
    _append_operation_log(
        operator=normalized_teacher,
        action="classes.create",
        target=class_name,
        detail=f"class_id={record.id}",
    )
    return record

async def delete_admin_class(class_id: str, teacher_username: str):
    _ensure_teacher(teacher_username)
    normalized_teacher = _normalize_text(teacher_username)
    if class_id not in classes_db:
        raise HTTPException(status_code=404, detail="班级不存在")

    class_record = classes_db[class_id]
    class_owner = _normalize_text(class_record.created_by)
    if not _is_admin_user(normalized_teacher) and class_owner != normalized_teacher:
        raise HTTPException(status_code=403, detail="不能删除其他教师创建的班级")

    class_name = class_record.name
    if any(
        item.class_name == class_name and _student_owner_username(item) == class_owner
        for item in students_db.values()
    ):
        raise HTTPException(status_code=409, detail="班级已被学生使用，无法删除")

    del classes_db[class_id]
    _save_user_registry()
    _append_operation_log(
        operator=normalized_teacher,
        action="classes.delete",
        target=class_name,
        detail=f"class_id={class_id}",
    )
    return {"message": "班级已删除"}

async def download_student_template(teacher_username: str, format: str = "xlsx"):
    _ensure_teacher(teacher_username)
    template_format = format.lower()

    if template_format == "csv":
        payload = _build_csv_template()
        return StreamingResponse(
            io.BytesIO(payload),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=student_import_template.csv"},
        )

    if template_format == "xlsx":
        payload = _build_xlsx_template()
        return StreamingResponse(
            io.BytesIO(payload),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=student_import_template.xlsx"},
        )

    raise HTTPException(status_code=400, detail="format 必须是 xlsx 或 csv")

async def import_students(teacher_username: str, file: UploadFile = File(...)):
    _ensure_teacher(teacher_username)
    normalized_teacher = _normalize_text(teacher_username)
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")

    file_content = await file.read()
    parsed_rows = _parse_student_import_rows(file.filename, file_content)

    class_names = {item.name for item in _list_accessible_classes(normalized_teacher)}
    existing_student_ids = set(students_db.keys())
    file_student_ids = set()
    now = datetime.now()

    success_students: List[StudentRecord] = []
    errors = []
    skipped_count = 0

    for row_number, row in parsed_rows:
        student_id, real_name, class_name, organization, phone, admission_year_raw = row
        admission_year = _normalize_admission_year(admission_year_raw) or _infer_admission_year(student_id)
        if not all([student_id, real_name, class_name, organization, phone]):
            errors.append({"row": row_number, "student_id": student_id, "reason": "字段不能为空"})
            continue
        if not admission_year:
            errors.append({"row": row_number, "student_id": student_id, "reason": "入学年级无效"})
            continue
        if is_teacher(student_id):
            errors.append({"row": row_number, "student_id": student_id, "reason": "student id conflicts with teacher account"})
            continue
        if class_name not in class_names:
            errors.append({"row": row_number, "student_id": student_id, "reason": "class does not exist"})
            continue
        if student_id in existing_student_ids:
            skipped_count += 1
            errors.append({"row": row_number, "student_id": student_id, "reason": "学号重复（系统中已存在）"})
            continue
        if student_id in file_student_ids:
            skipped_count += 1
            errors.append({"row": row_number, "student_id": student_id, "reason": "duplicate student id in system"})
            continue

        file_student_ids.add(student_id)
        success_students.append(
            StudentRecord(
                student_id=student_id,
                username=student_id,
                real_name=real_name,
                class_name=class_name,
                admission_year=admission_year,
                organization=organization,
                phone=phone,
                role="student",
                created_by=normalized_teacher,
                password_hash=_hash_password(DEFAULT_PASSWORD),
                created_at=now,
                updated_at=now,
            )
        )

    for item in success_students:
        students_db[item.student_id] = item

    if success_students:
        _save_user_registry()
    _append_operation_log(
        operator=normalized_teacher,
        action="students.import",
        target="students",
        detail=f"success={len(success_students)}, skipped={skipped_count}, failed={len(errors) - skipped_count}",
    )

    failed_count = len(errors) - skipped_count
    return {
        "total_rows": len(parsed_rows),
        "success_count": len(success_students),
        "skipped_count": skipped_count,
        "failed_count": failed_count,
        "errors": errors,
    }

async def list_admin_students(
    teacher_username: str,
    keyword: str = "",
    class_name: str = "",
    admission_year: str = "",
    page: int = 1,
    page_size: int = 20,
):
    _ensure_teacher(teacher_username)
    normalized_teacher = _normalize_text(teacher_username)
    page = max(page, 1)
    page_size = max(1, min(page_size, 100))

    normalized_keyword = _normalize_text(keyword).lower()
    normalized_class_name = _normalize_text(class_name)
    normalized_admission_year = _normalize_admission_year(admission_year)
    students = [item for item in students_db.values() if _student_visible_to_teacher(item, normalized_teacher)]

    if normalized_keyword:
        students = [
            item for item in students
            if normalized_keyword in item.student_id.lower() or normalized_keyword in item.real_name.lower()
        ]

    if normalized_class_name:
        students = [item for item in students if item.class_name == normalized_class_name]
    if normalized_admission_year:
        students = [
            item for item in students
            if _normalize_admission_year(item.admission_year) == normalized_admission_year
        ]

    students.sort(key=lambda item: item.created_at, reverse=True)
    total = len(students)
    start = (page - 1) * page_size
    end = start + page_size
    paged_students = students[start:end]

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "student_id": item.student_id,
                "username": item.username,
                "real_name": item.real_name,
                "class_name": item.class_name,
                "admission_year": _normalize_admission_year(item.admission_year),
                "admission_year_label": _format_admission_year_label(item.admission_year),
                "organization": item.organization,
                "phone": item.phone,
                "role": item.role,
                "created_at": item.created_at,
                "updated_at": item.updated_at,
            }
            for item in paged_students
        ],
    }

async def list_admission_year_options(teacher_username: str):
    _ensure_teacher(teacher_username)
    normalized_teacher = _normalize_text(teacher_username)
    year_set = {year for year in DEFAULT_ADMISSION_YEAR_OPTIONS}
    year_set.update(
        _normalize_admission_year(item.admission_year)
        for item in students_db.values()
        if _normalize_admission_year(item.admission_year) and _student_visible_to_teacher(item, normalized_teacher)
    )
    years = sorted(year_set)
    return [{"value": year, "label": f"{year}级"} for year in years]

async def reset_student_password(student_id: str, teacher_username: str):
    _ensure_teacher(teacher_username)
    normalized_teacher = _normalize_text(teacher_username)
    if student_id not in students_db:
        raise HTTPException(status_code=404, detail="学生不存在")

    student = students_db[student_id]
    if not _student_visible_to_teacher(student, normalized_teacher):
        raise HTTPException(status_code=403, detail="不能操作其他教师的学生")
    student.password_hash = _hash_password(DEFAULT_PASSWORD)
    student.updated_at = datetime.now()
    _save_user_registry()
    _append_operation_log(
        operator=normalized_teacher,
        action="students.reset_password",
        target=student_id,
        detail="密码重置为默认密码",
    )
    return {"message": "密码已重置", "student_id": student_id}

async def delete_student(student_id: str, teacher_username: str):
    _ensure_teacher(teacher_username)
    normalized_teacher = _normalize_text(teacher_username)
    if student_id not in students_db:
        raise HTTPException(status_code=404, detail="学生不存在")

    if not _student_visible_to_teacher(students_db[student_id], normalized_teacher):
        raise HTTPException(status_code=403, detail="不能删除其他教师的学生")
    del students_db[student_id]
    _save_user_registry()
    _append_operation_log(
        operator=normalized_teacher,
        action="students.delete",
        target=student_id,
        detail="删除学生账号",
    )
    return {"message": "学生已删除", "student_id": student_id}

async def batch_delete_students(teacher_username: str, class_name: str = ""):
    _ensure_teacher(teacher_username)
    normalized_teacher = _normalize_text(teacher_username)
    normalized_class_name = _normalize_text(class_name)
    if not normalized_class_name:
        raise HTTPException(status_code=400, detail="class_name不能为空")

    target_records = [
        item
        for item in students_db.values()
        if item.class_name == normalized_class_name and _student_visible_to_teacher(item, normalized_teacher)
    ]
    target_ids = [item.student_id for item in target_records]

    for student_id in target_ids:
        del students_db[student_id]

    if target_ids:
        _save_user_registry()

    _append_operation_log(
        operator=normalized_teacher,
        action="students.batch_delete",
        target=normalized_class_name,
        detail=f"class_name={normalized_class_name}, deleted={len(target_ids)}",
    )
    return {
        "message": "批量删除完成",
        "class_name": normalized_class_name,
        "deleted_count": len(target_ids),
        "deleted_student_ids": target_ids,
    }

async def get_resource_control_overview(admin_username: str):
    _ensure_admin(admin_username)
    budget = _normalize_resource_budget(resource_policy_db.get("budget", {}))
    users = _collect_resource_control_users()
    summary = _resource_assignment_summary(users, budget)
    return {
        "budget": budget,
        "summary": summary,
        "defaults": resource_policy_db.get("defaults", deepcopy(DEFAULT_RESOURCE_ROLE_LIMITS)),
        "users": users,
    }

async def upsert_user_resource_quota(username: str, payload: ResourceQuotaUpdateRequest):
    _ensure_admin(payload.admin_username)
    target_user = _normalize_text(username)
    if not target_user:
        raise HTTPException(status_code=400, detail="username不能为空")

    user_map = {item["username"]: item for item in _managed_users()}
    user_item = user_map.get(target_user)
    if not user_item:
        raise HTTPException(status_code=404, detail="用户不存在，无法设置资源配额")

    role = user_item["role"]
    quota = _normalize_resource_quota(
        {
            "cpu_limit": payload.cpu_limit,
            "memory_limit": payload.memory_limit,
            "storage_limit": payload.storage_limit,
        },
        role,
    )
    now_iso = datetime.now().isoformat()
    next_override = {
        **quota,
        "updated_by": _normalize_text(payload.admin_username),
        "updated_at": now_iso,
        "note": _normalize_text(payload.note)[:200],
    }

    current_overrides = resource_policy_db.get("overrides", {})
    simulated_overrides = deepcopy(current_overrides)
    simulated_overrides[target_user] = next_override

    budget = _normalize_resource_budget(resource_policy_db.get("budget", {}))
    simulated_rows = _collect_resource_control_users(overrides=simulated_overrides)
    simulated_summary = _resource_assignment_summary(simulated_rows, budget)
    _validate_budget(simulated_summary, budget)

    resource_policy_db["overrides"] = simulated_overrides
    resource_policy_db["budget"] = budget
    _save_resource_policy()

    _append_operation_log(
        operator=payload.admin_username,
        action="resource_quota.update",
        target=target_user,
        detail=f"cpu={quota['cpu_limit']}, memory={quota['memory_limit']}, storage={quota['storage_limit']}",
    )

    target_row = next((item for item in simulated_rows if item["username"] == target_user), None)
    return {
        "message": "资源配额已更新",
        "item": target_row,
        "summary": simulated_summary,
    }

async def delete_user_resource_quota_override(username: str, admin_username: str):
    _ensure_admin(admin_username)
    target_user = _normalize_text(username)
    if not target_user:
        raise HTTPException(status_code=400, detail="username不能为空")

    if target_user not in {item["username"] for item in _managed_users()}:
        raise HTTPException(status_code=404, detail="用户不存在")

    current_overrides = resource_policy_db.get("overrides", {})
    simulated_overrides = deepcopy(current_overrides)
    simulated_overrides.pop(target_user, None)

    budget = _normalize_resource_budget(resource_policy_db.get("budget", {}))
    simulated_rows = _collect_resource_control_users(overrides=simulated_overrides)
    simulated_summary = _resource_assignment_summary(simulated_rows, budget)
    _validate_budget(simulated_summary, budget)

    resource_policy_db["overrides"] = simulated_overrides
    resource_policy_db["budget"] = budget
    _save_resource_policy()

    _append_operation_log(
        operator=admin_username,
        action="resource_quota.reset",
        target=target_user,
        detail="恢复默认资源配额",
    )

    return {
        "message": "该用户已恢复默认资源配额",
        "username": target_user,
        "summary": simulated_summary,
    }

async def update_resource_budget(payload: ResourceBudgetUpdateRequest):
    _ensure_admin(payload.admin_username)
    budget = _normalize_resource_budget(
        {
            "max_total_cpu": payload.max_total_cpu,
            "max_total_memory": payload.max_total_memory,
            "max_total_storage": payload.max_total_storage,
            "enforce_budget": payload.enforce_budget,
            "updated_by": payload.admin_username,
            "updated_at": datetime.now().isoformat(),
        }
    )

    rows = _collect_resource_control_users()
    summary = _resource_assignment_summary(rows, budget)
    _validate_budget(summary, budget)

    resource_policy_db["budget"] = budget
    _save_resource_policy()

    _append_operation_log(
        operator=payload.admin_username,
        action="resource_budget.update",
        target="server-budget",
        detail=(
            f"cpu={budget['max_total_cpu']}, memory={budget['max_total_memory']}, "
            f"storage={budget['max_total_storage']}, enforce={budget['enforce_budget']}"
        ),
    )

    return {
        "message": "服务器资源预算已更新",
        "budget": budget,
        "summary": summary,
    }

async def list_admin_operation_logs(admin_username: str, limit: int = 200):
    _ensure_admin(admin_username)
    safe_limit = max(1, min(limit, 1000))
    items = sorted(operation_logs_db, key=lambda item: item.created_at, reverse=True)[:safe_limit]
    return {
        "total": len(operation_logs_db),
        "limit": safe_limit,
        "items": [_operation_log_to_dict(item) for item in items],
    }

async def cleanup_admin_operation_logs(admin_username: str, keep_recent: int = 200):
    _ensure_admin(admin_username)
    safe_keep = max(0, min(keep_recent, 1000))
    before_count = len(operation_logs_db)
    if safe_keep == 0:
        operation_logs_db.clear()
    elif before_count > safe_keep:
        del operation_logs_db[: before_count - safe_keep]

    removed_count = max(0, before_count - len(operation_logs_db))
    _append_operation_log(
        operator=admin_username,
        action="operation_logs.cleanup",
        target="operation-logs",
        detail=f"removed={removed_count}, keep_recent={safe_keep}",
    )
    return {
        "message": "操作日志清理完成",
        "removed_count": removed_count,
        "remaining": len(operation_logs_db),
    }

async def upload_resource_file(
    teacher_username: str,
    file: UploadFile = File(...)
):
    """管理员上传资源文件"""
    _ensure_teacher(teacher_username)

    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")

    original_filename = os.path.basename(file.filename)
    extension = os.path.splitext(original_filename)[1].lower()
    if extension not in ALLOWED_RESOURCE_EXTENSIONS:
        raise HTTPException(status_code=400, detail="暂不支持该文件类型")

    safe_filename = original_filename.replace(" ", "_").replace("/", "_").replace("\\", "_")
    resource_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"resource_{resource_id}_{safe_filename}")

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"文件保存失败: {exc}") from exc

    file_size = os.path.getsize(file_path)
    if file_size <= 0:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=400, detail="上传文件为空")

    inferred_content_type = file.content_type or mimetypes.guess_type(original_filename)[0] or "application/octet-stream"
    record = ResourceFile(
        id=resource_id,
        filename=original_filename,
        file_path=file_path,
        file_type=extension.lstrip("."),
        content_type=inferred_content_type,
        size=file_size,
        created_at=datetime.now(),
        created_by=teacher_username,
    )
    resource_files_db[record.id] = record
    _save_resource_registry()
    return _resource_to_payload(record)

async def list_resource_files(
    teacher_username: str,
    name: Optional[str] = None,
    file_type: Optional[str] = None
):
    """管理员查看资源文件列表"""
    _ensure_teacher(teacher_username)
    items = _list_resource_records(name_filter=name or "", type_filter=file_type or "")
    payload_items = [_resource_to_payload(item) for item in items]
    return {"total": len(payload_items), "items": payload_items}

async def get_resource_file_detail(resource_id: str, teacher_username: str):
    """管理员查看资源文件详情"""
    _ensure_teacher(teacher_username)
    record = _get_resource_or_404(resource_id)
    _ensure_resource_file_exists(record)

    payload = _resource_to_payload(record)
    preview_mode = payload["preview_mode"]
    if preview_mode in {"markdown", "text"}:
        payload["preview_text"] = _read_text_preview(record.file_path)
    elif preview_mode == "docx":
        payload["preview_text"] = _read_docx_preview(record.file_path)
    else:
        payload["preview_text"] = ""
    return payload

async def delete_resource_file(resource_id: str, teacher_username: str):
    """管理员删除资源文件"""
    _ensure_teacher(teacher_username)
    record = _get_resource_or_404(resource_id)

    if os.path.exists(record.file_path):
        try:
            os.remove(record.file_path)
        except OSError as exc:
            raise HTTPException(status_code=500, detail=f"删除文件失败: {exc}") from exc

    resource_files_db.pop(resource_id, None)
    _save_resource_registry()
    return {"message": "资源文件已删除", "id": resource_id}

async def preview_resource_file(resource_id: str, teacher_username: str):
    """在线预览资源文件"""
    _ensure_teacher(teacher_username)
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

async def download_resource_file(resource_id: str, teacher_username: str):
    """下载资源文件"""
    _ensure_teacher(teacher_username)
    record = _get_resource_or_404(resource_id)
    _ensure_resource_file_exists(record)

    media_type = record.content_type or mimetypes.guess_type(record.filename)[0] or "application/octet-stream"
    return FileResponse(
        path=record.file_path,
        filename=record.filename,
        media_type=media_type,
        content_disposition_type="attachment",
    )

router.add_api_route("/api/admin/teachers", list_admin_teachers, methods=["GET"])
router.add_api_route("/api/admin/teachers", create_admin_teacher, methods=["POST"])
router.add_api_route("/api/admin/teachers/{teacher_username}", delete_admin_teacher, methods=["DELETE"])
router.add_api_route("/api/admin/classes", list_admin_classes, methods=["GET"], response_model=list[main.ClassRecord])
router.add_api_route("/api/admin/classes/template", download_class_template, methods=["GET"])
router.add_api_route("/api/admin/classes/import", import_admin_classes, methods=["POST"])
router.add_api_route("/api/admin/classes", create_admin_class, methods=["POST"], response_model=main.ClassRecord)
router.add_api_route("/api/admin/classes/{class_id}", delete_admin_class, methods=["DELETE"])
router.add_api_route("/api/admin/students/template", download_student_template, methods=["GET"])
router.add_api_route("/api/admin/students/import", import_students, methods=["POST"])
router.add_api_route("/api/admin/students", list_admin_students, methods=["GET"])
router.add_api_route("/api/admin/students/admission-years", list_admission_year_options, methods=["GET"])
router.add_api_route("/api/admin/students/{student_id}/reset-password", reset_student_password, methods=["POST"])
router.add_api_route("/api/admin/students/{student_id}", delete_student, methods=["DELETE"])
router.add_api_route("/api/admin/students", batch_delete_students, methods=["DELETE"])
router.add_api_route("/api/admin/resource-control/overview", get_resource_control_overview, methods=["GET"])
router.add_api_route("/api/admin/resource-control/users/{username}", upsert_user_resource_quota, methods=["PUT"])
router.add_api_route("/api/admin/resource-control/users/{username}", delete_user_resource_quota_override, methods=["DELETE"])
router.add_api_route("/api/admin/resource-control/budget", update_resource_budget, methods=["PUT"])
router.add_api_route("/api/admin/operation-logs", list_admin_operation_logs, methods=["GET"])
router.add_api_route("/api/admin/operation-logs", cleanup_admin_operation_logs, methods=["DELETE"])
router.add_api_route("/api/admin/resources/upload", upload_resource_file, methods=["POST"])
router.add_api_route("/api/admin/resources", list_resource_files, methods=["GET"])
router.add_api_route("/api/admin/resources/{resource_id}", get_resource_file_detail, methods=["GET"])
router.add_api_route("/api/admin/resources/{resource_id}", delete_resource_file, methods=["DELETE"])
router.add_api_route("/api/admin/resources/{resource_id}/preview", preview_resource_file, methods=["GET"])
router.add_api_route("/api/admin/resources/{resource_id}/download", download_resource_file, methods=["GET"])
