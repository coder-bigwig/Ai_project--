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

async def start_experiment(experiment_id: str, student_id: str):
    """学生开始实验（JupyterHub 多租户）"""
    if experiment_id not in experiments_db:
        raise HTTPException(status_code=404, detail="实验不存在")

    student_id = _normalize_text(student_id)
    if not student_id:
        raise HTTPException(status_code=400, detail="student_id不能为空")
    _ensure_student(student_id)

    experiment = experiments_db[experiment_id]
    student = students_db[student_id]
    if not _is_experiment_visible_to_student(experiment, student):
        raise HTTPException(status_code=403, detail="该实验当前未发布给你")
    user_notebook_name = f"{student_id}_{experiment_id[:8]}.ipynb"
    notebook_relpath = f"work/{user_notebook_name}"

    existing_records = [
        exp for exp in student_experiments_db.values()
        if exp.student_id == student_id and exp.experiment_id == experiment_id
    ]
    student_exp = max(
        existing_records,
        key=lambda item: item.start_time or datetime.min
    ) if existing_records else None

    if student_exp is None:
        student_exp = StudentExperiment(
            id=str(uuid.uuid4()),
            experiment_id=experiment_id,
            student_id=student_id,
            status=ExperimentStatus.IN_PROGRESS,
            start_time=datetime.now(),
            notebook_content=user_notebook_name  # Store the filename for later reference
        )
        student_experiments_db[student_exp.id] = student_exp

    # Best-effort: spawn server and copy template into user's work dir.
    user_token_for_url = None
    if _jupyterhub_enabled():
        try:
            if _ensure_user_server_running(student_id):
                user_token = _create_short_lived_user_token(student_id)
                if user_token:
                    user_token_for_url = user_token
                    # Ensure work directory exists in the user's server.
                    dir_resp = _user_contents_request(student_id, user_token, "GET", "work", params={"content": 0})
                    if dir_resp.status_code == 404:
                        _user_contents_request(student_id, user_token, "PUT", "work", json={"type": "directory"})

                    exists_resp = _user_contents_request(
                        student_id, user_token, "GET", notebook_relpath, params={"content": 0}
                    )
                    if exists_resp.status_code == 404:
                        notebook_json = None
                        template_path = _normalize_text(experiment.notebook_path or "")
                        if template_path:
                            tpl_resp = _user_contents_request(
                                student_id, user_token, "GET", template_path, params={"content": 1}
                            )
                            if tpl_resp.status_code == 200:
                                tpl_payload = tpl_resp.json() or {}
                                if tpl_payload.get("type") == "notebook" and tpl_payload.get("content"):
                                    notebook_json = tpl_payload.get("content")

                        if notebook_json is None:
                            notebook_json = _empty_notebook_json()

                        put_resp = _user_contents_request(
                            student_id,
                            user_token,
                            "PUT",
                            notebook_relpath,
                            json={"type": "notebook", "format": "json", "content": notebook_json},
                        )
                        if put_resp.status_code not in {200, 201}:
                            print(
                                f"Failed to create notebook via Jupyter API ({put_resp.status_code}): {put_resp.text[:200]}"
                            )
        except Exception as exc:
            print(f"JupyterHub integration error: {exc}")

    jupyter_url = _build_user_lab_url(student_id, path=notebook_relpath, token=user_token_for_url)
    return {
        "student_experiment_id": student_exp.id,
        "jupyter_url": jupyter_url,
        "message": "实验环境已启动"
    }

async def submit_experiment(
    student_exp_id: str,
    submission: SubmitExperimentRequest
):
    """提交实验"""
    if student_exp_id not in student_experiments_db:
        raise HTTPException(status_code=404, detail="学生实验记录不存在")
    
    student_exp = student_experiments_db[student_exp_id]

    # Primary strategy (multi-tenant): read notebook from the student's JupyterHub server.
    # Fallback: accept payload.notebook_content if provided.
    try:
        if _jupyterhub_enabled():
            student_id = _normalize_text(student_exp.student_id)
            if not student_id:
                raise ValueError("student_id missing")

            if not _ensure_user_server_running(student_id):
                raise RuntimeError("JupyterHub server not running")

            user_token = _create_short_lived_user_token(student_id)
            if not user_token:
                raise RuntimeError("Failed to create user API token")

            def _parse_iso(value) -> datetime:
                if not value:
                    return datetime.min
                if isinstance(value, str):
                    text = value.replace("Z", "+00:00")
                    try:
                        return datetime.fromisoformat(text)
                    except ValueError:
                        return datetime.min
                return datetime.min

            target_path = ""
            list_resp = _user_contents_request(student_id, user_token, "GET", "work", params={"content": 1})
            if list_resp.status_code == 200:
                listing = list_resp.json() or {}
                entries = listing.get("content") if isinstance(listing, dict) else None
                if isinstance(entries, list):
                    notebook_entries = []
                    for entry in entries:
                        if not isinstance(entry, dict):
                            continue
                        name = (entry.get("name") or "").lower()
                        etype = entry.get("type") or ""
                        if etype == "notebook" or name.endswith(".ipynb"):
                            notebook_entries.append(
                                (
                                    _parse_iso(entry.get("last_modified") or entry.get("created")),
                                    entry.get("path") or "",
                                )
                            )
                    notebook_entries.sort(key=lambda item: item[0], reverse=True)
                    if notebook_entries and notebook_entries[0][1]:
                        target_path = notebook_entries[0][1]

            if not target_path:
                assigned_name = f"{student_id}_{student_exp.experiment_id[:8]}.ipynb"
                target_path = f"work/{assigned_name}"

            file_resp = _user_contents_request(student_id, user_token, "GET", target_path, params={"content": 1})
            if file_resp.status_code != 200:
                raise RuntimeError(f"Failed to read notebook ({file_resp.status_code})")

            file_payload = file_resp.json() or {}
            notebook_content = file_payload.get("content")
            if isinstance(notebook_content, dict):
                student_exp.notebook_content = json.dumps(notebook_content, ensure_ascii=False)
            else:
                student_exp.notebook_content = json.dumps(file_payload, ensure_ascii=False)
        elif submission and submission.notebook_content:
            student_exp.notebook_content = submission.notebook_content
        else:
            student_exp.notebook_content = "Error: JupyterHub not configured, and no notebook content provided"
    except Exception as e:
        student_exp.notebook_content = f"Error reading notebook: {str(e)}"
        print(f"Error reading notebook: {e}")

    student_exp.status = ExperimentStatus.SUBMITTED
    student_exp.submit_time = datetime.now()
    
    return {
        "message": "实验已提交",
        "submit_time": student_exp.submit_time
    }

async def upload_submission_pdf(student_exp_id: str, file: UploadFile = File(...)):
    """学生上传提交PDF"""
    if student_exp_id not in student_experiments_db:
        raise HTTPException(status_code=404, detail="学生实验记录不存在")
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")

    is_pdf = (
        file.filename.lower().endswith(".pdf")
        or (file.content_type or "").lower() == "application/pdf"
    )
    if not is_pdf:
        raise HTTPException(status_code=400, detail="仅支持 PDF 文件")

    student_exp = student_experiments_db[student_exp_id]
    submission_pdf_id = str(uuid.uuid4())
    safe_filename = file.filename.replace(" ", "_")
    file_path = os.path.join(UPLOAD_DIR, f"submission_{submission_pdf_id}_{safe_filename}")

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"保存PDF失败: {exc}") from exc

    file_size = os.path.getsize(file_path)
    if file_size <= 0:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=400, detail="PDF文件为空")

    record = StudentSubmissionPDF(
        id=submission_pdf_id,
        student_exp_id=student_exp_id,
        experiment_id=student_exp.experiment_id,
        student_id=student_exp.student_id,
        filename=file.filename,
        file_path=file_path,
        content_type="application/pdf",
        size=file_size,
        created_at=datetime.now(),
    )
    submission_pdfs_db[submission_pdf_id] = record

    return {
        "id": record.id,
        "student_exp_id": record.student_exp_id,
        "filename": record.filename,
        "size": record.size,
        "created_at": record.created_at,
        "review_status": _pdf_status(record),
        "download_url": f"/api/student-submissions/{record.id}/download",
    }

async def list_submission_pdfs(student_exp_id: str):
    """获取某次提交的 PDF 文件"""
    if student_exp_id not in student_experiments_db:
        raise HTTPException(status_code=404, detail="学生实验记录不存在")

    return [_pdf_to_payload(item) for item in _get_submission_pdfs(student_exp_id)]

async def mark_submission_pdf_viewed(pdf_id: str, teacher_username: str):
    """教师标记 PDF 已查阅"""
    _ensure_teacher(teacher_username)
    if pdf_id not in submission_pdfs_db:
        raise HTTPException(status_code=404, detail="提交 PDF 不存在")

    item = submission_pdfs_db[pdf_id]
    item.viewed = True
    item.viewed_at = datetime.now()
    item.viewed_by = teacher_username
    return _pdf_to_payload(item)

async def add_submission_pdf_annotation(pdf_id: str, payload: PDFAnnotationCreateRequest):
    """教师对PDF添加批注"""
    _ensure_teacher(payload.teacher_username)
    if pdf_id not in submission_pdfs_db:
        raise HTTPException(status_code=404, detail="提交 PDF 不存在")

    content = _normalize_text(payload.content)
    if not content:
        raise HTTPException(status_code=400, detail="批注内容不能为空")

    item = submission_pdfs_db[pdf_id]
    if not item.viewed:
        item.viewed = True
        item.viewed_at = datetime.now()
        item.viewed_by = payload.teacher_username

    annotation = PDFAnnotation(
        id=str(uuid.uuid4()),
        teacher_username=payload.teacher_username,
        content=content,
        created_at=datetime.now(),
    )
    item.annotations.append(annotation)
    return _pdf_to_payload(item)

async def get_student_experiments(student_id: str):
    """获取学生的所有实验"""
    student_exps = [
        exp for exp in student_experiments_db.values()
        if exp.student_id == student_id
    ]
    return student_exps

async def get_student_experiment_detail(student_exp_id: str):
    """获取学生实验详情"""
    if student_exp_id not in student_experiments_db:
        raise HTTPException(status_code=404, detail="学生实验记录不存在")
    return student_experiments_db[student_exp_id]

async def download_submission_pdf(pdf_id: str, teacher_username: Optional[str] = None):
    """下载学生提交的PDF文件"""
    if pdf_id not in submission_pdfs_db:
        raise HTTPException(status_code=404, detail="提交 PDF 不存在")

    record = submission_pdfs_db[pdf_id]
    if not os.path.exists(record.file_path):
        raise HTTPException(status_code=404, detail="PDF 文件不存在")

    if teacher_username and is_teacher(teacher_username):
        record.viewed = True
        record.viewed_at = datetime.now()
        record.viewed_by = teacher_username

    return FileResponse(
        path=record.file_path,
        filename=record.filename,
        media_type="application/pdf",
        content_disposition_type="inline",
    )

async def get_experiment_submissions(experiment_id: str):
    """教师查看某个实验的所有提交"""
    submissions = []
    for exp in student_experiments_db.values():
        if exp.experiment_id != experiment_id:
            continue
        if not _is_student_progress_record(exp.student_id):
            continue
        payload = exp.dict()
        pdf_items = _get_submission_pdfs(exp.id)
        payload["pdf_attachments"] = [
            _pdf_to_payload(item)
            for item in pdf_items
        ]
        payload["pdf_count"] = len(pdf_items)
        submissions.append(payload)

    return submissions

async def grade_experiment(
    student_exp_id: str,
    score: float,
    comment: Optional[str] = None,
    teacher_username: Optional[str] = None
):
    """教师评分"""
    if student_exp_id not in student_experiments_db:
        raise HTTPException(status_code=404, detail="学生实验记录不存在")
    
    if not (0 <= score <= 100):
        raise HTTPException(status_code=400, detail="分数必须在 0-100 之间")
    
    student_exp = student_experiments_db[student_exp_id]
    student_exp.score = score
    student_exp.teacher_comment = comment
    student_exp.status = ExperimentStatus.GRADED

    reviewer = teacher_username if teacher_username and is_teacher(teacher_username) else "teacher"
    now = datetime.now()
    for item in submission_pdfs_db.values():
        if item.student_exp_id != student_exp_id:
            continue
        item.reviewed = True
        item.reviewed_at = now
        item.reviewed_by = reviewer
        if not item.viewed:
            item.viewed = True
            item.viewed_at = now
            item.viewed_by = reviewer
    
    return {
        "message": "评分成功",
        "score": score
    }

router.add_api_route("/api/student-experiments/start/{experiment_id}", start_experiment, methods=["POST"])
router.add_api_route("/api/student-experiments/{student_exp_id}/submit", submit_experiment, methods=["POST"])
router.add_api_route("/api/student-experiments/{student_exp_id}/pdf", upload_submission_pdf, methods=["POST"])
router.add_api_route("/api/student-experiments/{student_exp_id}/pdfs", list_submission_pdfs, methods=["GET"])
router.add_api_route("/api/student-submissions/{pdf_id}/view", mark_submission_pdf_viewed, methods=["POST"])
router.add_api_route("/api/student-submissions/{pdf_id}/annotations", add_submission_pdf_annotation, methods=["POST"])
router.add_api_route("/api/student-experiments/my-experiments/{student_id}", get_student_experiments, methods=["GET"])
router.add_api_route("/api/student-experiments/{student_exp_id}", get_student_experiment_detail, methods=["GET"])
router.add_api_route("/api/student-submissions/{pdf_id}/download", download_submission_pdf, methods=["GET"])
router.add_api_route("/api/teacher/experiments/{experiment_id}/submissions", get_experiment_submissions, methods=["GET"])
router.add_api_route("/api/teacher/grade/{student_exp_id}", grade_experiment, methods=["POST"])
