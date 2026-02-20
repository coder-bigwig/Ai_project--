from __future__ import annotations

import json
import os
import shutil
import uuid
from datetime import datetime
from typing import Optional

from fastapi import File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from ..repositories import (
    ExperimentRepository,
    StudentExperimentRepository,
    SubmissionPdfRepository,
    UserRepository,
)


class SubmissionService:
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
            raise HTTPException(status_code=500, detail="提交记录写入失败") from exc

    def _to_experiment_model(self, row):
        difficulty = row.difficulty or self.main.DifficultyLevel.BEGINNER.value
        publish_scope = row.publish_scope or self.main.PublishScope.ALL.value
        try:
            difficulty = self.main.DifficultyLevel(difficulty)
        except ValueError:
            difficulty = self.main.DifficultyLevel.BEGINNER
        try:
            publish_scope = self.main.PublishScope(publish_scope)
        except ValueError:
            publish_scope = self.main.PublishScope.ALL
        return self.main.Experiment(
            id=row.id,
            course_id=row.course_id,
            course_name=row.course_name or "",
            title=row.title,
            description=row.description or "",
            difficulty=difficulty,
            tags=list(row.tags or []),
            notebook_path=row.notebook_path or "",
            resources=dict(row.resources or {}),
            deadline=row.deadline,
            created_at=row.created_at,
            created_by=row.created_by,
            published=bool(row.published),
            publish_scope=publish_scope,
            target_class_names=list(row.target_class_names or []),
            target_student_ids=list(row.target_student_ids or []),
        )

    def _to_student_record(self, row):
        student_id = row.student_id or row.username
        return self.main.StudentRecord(
            student_id=student_id,
            username=row.username,
            real_name=row.real_name or student_id,
            class_name=row.class_name or "",
            admission_year=row.admission_year or "",
            organization=row.organization or "",
            phone=row.phone or "",
            role="student",
            created_by=row.created_by or "",
            password_hash=row.password_hash or self.main._hash_password(self.main.DEFAULT_PASSWORD),
            security_question=row.security_question or "",
            security_answer_hash=row.security_answer_hash or "",
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def _to_student_experiment_model(self, row):
        status_value = row.status or self.main.ExperimentStatus.NOT_STARTED.value
        try:
            status_value = self.main.ExperimentStatus(status_value)
        except ValueError:
            status_value = self.main.ExperimentStatus.NOT_STARTED
        return self.main.StudentExperiment(
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

    def _pdf_status(self, row) -> str:
        if row.reviewed:
            return "已批阅"
        if row.viewed:
            return "已查阅"
        return "未查阅"

    def _pdf_to_payload(self, row) -> dict:
        annotations = []
        for ann in list(row.annotations or []):
            if not isinstance(ann, dict):
                continue
            annotations.append(
                {
                    "id": ann.get("id") or "",
                    "teacher_username": ann.get("teacher_username") or "",
                    "content": ann.get("content") or "",
                    "created_at": ann.get("created_at"),
                }
            )
        return {
            "id": row.id,
            "student_exp_id": row.submission_id,
            "experiment_id": row.experiment_id,
            "student_id": row.student_id,
            "filename": row.filename,
            "content_type": row.content_type,
            "size": row.size,
            "created_at": row.created_at,
            "download_url": f"/api/student-submissions/{row.id}/download",
            "viewed": row.viewed,
            "viewed_at": row.viewed_at,
            "viewed_by": row.viewed_by,
            "reviewed": row.reviewed,
            "reviewed_at": row.reviewed_at,
            "reviewed_by": row.reviewed_by,
            "review_status": self._pdf_status(row),
            "annotations": annotations,
        }

    async def start_experiment(self, experiment_id: str, student_id: str):
        student_id = self.main._normalize_text(student_id)
        if not student_id:
            raise HTTPException(status_code=400, detail="student_id不能为空")

        if self.db is None:
            if experiment_id not in self.main.experiments_db:
                raise HTTPException(status_code=404, detail="实验不存在")
            self.main._ensure_student(student_id)
            experiment = self.main.experiments_db[experiment_id]
            student = self.main.students_db[student_id]
            student_exp = max(
                [
                    exp
                    for exp in self.main.student_experiments_db.values()
                    if exp.student_id == student_id and exp.experiment_id == experiment_id
                ],
                key=lambda item: item.start_time or datetime.min,
                default=None,
            )
        else:
            exp_row = await ExperimentRepository(self.db).get(experiment_id)
            if not exp_row:
                raise HTTPException(status_code=404, detail="实验不存在")
            student_row = await UserRepository(self.db).get_student_by_student_id(student_id)
            if not student_row:
                raise HTTPException(status_code=404, detail="学生不存在")
            experiment = self._to_experiment_model(exp_row)
            student = self._to_student_record(student_row)
            self.main.experiments_db[experiment.id] = experiment
            self.main.students_db[student.student_id] = student

            existing = await StudentExperimentRepository(self.db).get_by_student_and_experiment(student_id, experiment_id)
            student_exp = self._to_student_experiment_model(existing) if existing else None

        if not self.main._is_experiment_visible_to_student(experiment, student):
            raise HTTPException(status_code=403, detail="该实验当前未发布给你")

        user_notebook_name = f"{student_id}_{experiment_id[:8]}.ipynb"
        notebook_relpath = f"work/{user_notebook_name}"

        if student_exp is None:
            record_id = str(uuid.uuid4())
            if self.db is None:
                student_exp = self.main.StudentExperiment(
                    id=record_id,
                    experiment_id=experiment_id,
                    student_id=student_id,
                    status=self.main.ExperimentStatus.IN_PROGRESS,
                    start_time=datetime.now(),
                    notebook_content=user_notebook_name,
                )
                self.main.student_experiments_db[student_exp.id] = student_exp
            else:
                payload = {
                    "id": record_id,
                    "experiment_id": experiment_id,
                    "student_id": student_id,
                    "status": self.main.ExperimentStatus.IN_PROGRESS.value,
                    "start_time": datetime.now(),
                    "notebook_content": user_notebook_name,
                    "submit_time": None,
                    "score": None,
                    "ai_feedback": "",
                    "teacher_comment": "",
                    "created_at": datetime.now(),
                    "updated_at": datetime.now(),
                }
                row = await StudentExperimentRepository(self.db).create(payload)
                await self._commit()
                student_exp = self._to_student_experiment_model(row)
                self.main.student_experiments_db[student_exp.id] = student_exp

        user_token_for_url = None
        if self.main._jupyterhub_enabled():
            try:
                if self.main._ensure_user_server_running(student_id):
                    user_token = self.main._create_short_lived_user_token(student_id)
                    if user_token:
                        user_token_for_url = user_token
                        dir_resp = self.main._user_contents_request(student_id, user_token, "GET", "work", params={"content": 0})
                        if dir_resp.status_code == 404:
                            self.main._user_contents_request(student_id, user_token, "PUT", "work", json={"type": "directory"})

                        exists_resp = self.main._user_contents_request(
                            student_id, user_token, "GET", notebook_relpath, params={"content": 0}
                        )
                        if exists_resp.status_code == 404:
                            notebook_json = None
                            template_path = self.main._normalize_text(experiment.notebook_path or "")
                            if template_path:
                                tpl_resp = self.main._user_contents_request(
                                    student_id,
                                    user_token,
                                    "GET",
                                    template_path,
                                    params={"content": 1},
                                )
                                if tpl_resp.status_code == 200:
                                    tpl_payload = tpl_resp.json() or {}
                                    if tpl_payload.get("type") == "notebook" and tpl_payload.get("content"):
                                        notebook_json = tpl_payload.get("content")
                            if notebook_json is None:
                                notebook_json = self.main._empty_notebook_json()
                            self.main._user_contents_request(
                                student_id,
                                user_token,
                                "PUT",
                                notebook_relpath,
                                json={"type": "notebook", "format": "json", "content": notebook_json},
                            )
            except Exception as exc:
                print(f"JupyterHub integration error: {exc}")

        jupyter_url = self.main._build_user_lab_url(student_id, path=notebook_relpath, token=user_token_for_url)
        return {"student_experiment_id": student_exp.id, "jupyter_url": jupyter_url, "message": "实验环境已启动"}

    async def submit_experiment(self, student_exp_id: str, submission):
        if self.db is None:
            student_exp = self.main.student_experiments_db.get(student_exp_id)
            if not student_exp:
                raise HTTPException(status_code=404, detail="学生实验记录不存在")
        else:
            row = await StudentExperimentRepository(self.db).get(student_exp_id)
            if not row:
                raise HTTPException(status_code=404, detail="学生实验记录不存在")
            student_exp = self._to_student_experiment_model(row)

        try:
            if self.main._jupyterhub_enabled():
                student_id = self.main._normalize_text(student_exp.student_id)
                if not student_id:
                    raise ValueError("student_id missing")
                if not self.main._ensure_user_server_running(student_id):
                    raise RuntimeError("JupyterHub server not running")
                user_token = self.main._create_short_lived_user_token(student_id)
                if not user_token:
                    raise RuntimeError("Failed to create user API token")

                target_path = ""
                list_resp = self.main._user_contents_request(student_id, user_token, "GET", "work", params={"content": 1})
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
                                modified = entry.get("last_modified") or entry.get("created")
                                dt_value = datetime.min
                                if isinstance(modified, str):
                                    text = modified.replace("Z", "+00:00")
                                    try:
                                        dt_value = datetime.fromisoformat(text)
                                    except ValueError:
                                        dt_value = datetime.min
                                notebook_entries.append((dt_value, entry.get("path") or ""))
                        notebook_entries.sort(key=lambda item: item[0], reverse=True)
                        if notebook_entries and notebook_entries[0][1]:
                            target_path = notebook_entries[0][1]

                if not target_path:
                    assigned_name = f"{student_id}_{student_exp.experiment_id[:8]}.ipynb"
                    target_path = f"work/{assigned_name}"

                file_resp = self.main._user_contents_request(student_id, user_token, "GET", target_path, params={"content": 1})
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
        except Exception as exc:
            student_exp.notebook_content = f"Error reading notebook: {exc}"
            print(f"Error reading notebook: {exc}")

        student_exp.status = self.main.ExperimentStatus.SUBMITTED
        student_exp.submit_time = datetime.now()

        if self.db is None:
            self.main.student_experiments_db[student_exp.id] = student_exp
        else:
            row = await StudentExperimentRepository(self.db).get(student_exp.id)
            row.notebook_content = student_exp.notebook_content or ""
            row.status = self.main.ExperimentStatus.SUBMITTED.value
            row.submit_time = student_exp.submit_time
            row.updated_at = datetime.now()
            await self._commit()
            self.main.student_experiments_db[student_exp.id] = student_exp

        return {"message": "实验已提交", "submit_time": student_exp.submit_time}

    async def upload_submission_pdf(self, student_exp_id: str, file: UploadFile = File(...)):
        if not file.filename:
            raise HTTPException(status_code=400, detail="文件名不能为空")
        is_pdf = file.filename.lower().endswith(".pdf") or (file.content_type or "").lower() == "application/pdf"
        if not is_pdf:
            raise HTTPException(status_code=400, detail="仅支持 PDF 文件")

        if self.db is None:
            student_exp = self.main.student_experiments_db.get(student_exp_id)
            if not student_exp:
                raise HTTPException(status_code=404, detail="学生实验记录不存在")
        else:
            row = await StudentExperimentRepository(self.db).get(student_exp_id)
            if not row:
                raise HTTPException(status_code=404, detail="学生实验记录不存在")
            student_exp = self._to_student_experiment_model(row)

        pdf_id = str(uuid.uuid4())
        safe_filename = file.filename.replace(" ", "_")
        file_path = os.path.join(self.main.UPLOAD_DIR, f"submission_{pdf_id}_{safe_filename}")
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

        if self.db is None:
            record = self.main.StudentSubmissionPDF(
                id=pdf_id,
                student_exp_id=student_exp_id,
                experiment_id=student_exp.experiment_id,
                student_id=student_exp.student_id,
                filename=file.filename,
                file_path=file_path,
                content_type="application/pdf",
                size=file_size,
                created_at=datetime.now(),
            )
            self.main.submission_pdfs_db[pdf_id] = record
            return {
                "id": record.id,
                "student_exp_id": record.student_exp_id,
                "filename": record.filename,
                "size": record.size,
                "created_at": record.created_at,
                "review_status": self.main._pdf_status(record),
                "download_url": f"/api/student-submissions/{record.id}/download",
            }

        now = datetime.now()
        row = await SubmissionPdfRepository(self.db).create(
            {
                "id": pdf_id,
                "submission_id": student_exp_id,
                "experiment_id": student_exp.experiment_id,
                "student_id": student_exp.student_id,
                "filename": file.filename,
                "file_path": file_path,
                "content_type": "application/pdf",
                "size": file_size,
                "viewed": False,
                "viewed_at": None,
                "viewed_by": "",
                "reviewed": False,
                "reviewed_at": None,
                "reviewed_by": "",
                "annotations": [],
                "created_at": now,
                "updated_at": now,
            }
        )
        await self._commit()
        self.main.submission_pdfs_db[row.id] = self.main.StudentSubmissionPDF(
            id=row.id,
            student_exp_id=row.submission_id,
            experiment_id=row.experiment_id,
            student_id=row.student_id,
            filename=row.filename,
            file_path=row.file_path,
            content_type=row.content_type,
            size=row.size,
            created_at=row.created_at,
            viewed=row.viewed,
            viewed_at=row.viewed_at,
            viewed_by=row.viewed_by or None,
            reviewed=row.reviewed,
            reviewed_at=row.reviewed_at,
            reviewed_by=row.reviewed_by or None,
            annotations=[],
        )
        return {
            "id": row.id,
            "student_exp_id": row.submission_id,
            "filename": row.filename,
            "size": row.size,
            "created_at": row.created_at,
            "review_status": self._pdf_status(row),
            "download_url": f"/api/student-submissions/{row.id}/download",
        }

    async def list_submission_pdfs(self, student_exp_id: str):
        if self.db is None:
            if student_exp_id not in self.main.student_experiments_db:
                raise HTTPException(status_code=404, detail="学生实验记录不存在")
            return [self.main._pdf_to_payload(item) for item in self.main._get_submission_pdfs(student_exp_id)]

        student_exp = await StudentExperimentRepository(self.db).get(student_exp_id)
        if not student_exp:
            raise HTTPException(status_code=404, detail="学生实验记录不存在")
        rows = await SubmissionPdfRepository(self.db).list_by_submission(student_exp_id)
        return [self._pdf_to_payload(item) for item in rows]

    async def mark_submission_pdf_viewed(self, pdf_id: str, teacher_username: str):
        self.main._ensure_teacher(teacher_username)
        if self.db is None:
            item = self.main.submission_pdfs_db.get(pdf_id)
            if not item:
                raise HTTPException(status_code=404, detail="提交 PDF 不存在")
            item.viewed = True
            item.viewed_at = datetime.now()
            item.viewed_by = teacher_username
            return self.main._pdf_to_payload(item)

        row = await SubmissionPdfRepository(self.db).get(pdf_id)
        if not row:
            raise HTTPException(status_code=404, detail="提交 PDF 不存在")
        row.viewed = True
        row.viewed_at = datetime.now()
        row.viewed_by = teacher_username
        row.updated_at = datetime.now()
        await self._commit()
        return self._pdf_to_payload(row)

    async def add_submission_pdf_annotation(self, pdf_id: str, payload):
        self.main._ensure_teacher(payload.teacher_username)
        content = self.main._normalize_text(payload.content)
        if not content:
            raise HTTPException(status_code=400, detail="批注内容不能为空")

        if self.db is None:
            item = self.main.submission_pdfs_db.get(pdf_id)
            if not item:
                raise HTTPException(status_code=404, detail="提交 PDF 不存在")
            if not item.viewed:
                item.viewed = True
                item.viewed_at = datetime.now()
                item.viewed_by = payload.teacher_username
            annotation = self.main.PDFAnnotation(
                id=str(uuid.uuid4()),
                teacher_username=payload.teacher_username,
                content=content,
                created_at=datetime.now(),
            )
            item.annotations.append(annotation)
            return self.main._pdf_to_payload(item)

        row = await SubmissionPdfRepository(self.db).get(pdf_id)
        if not row:
            raise HTTPException(status_code=404, detail="提交 PDF 不存在")
        if not row.viewed:
            row.viewed = True
            row.viewed_at = datetime.now()
            row.viewed_by = payload.teacher_username
        annotations = list(row.annotations or [])
        annotations.append(
            {
                "id": str(uuid.uuid4()),
                "teacher_username": payload.teacher_username,
                "content": content,
                "created_at": datetime.now().isoformat(),
            }
        )
        row.annotations = annotations
        row.updated_at = datetime.now()
        await self._commit()
        return self._pdf_to_payload(row)

    async def get_student_experiments(self, student_id: str):
        if self.db is None:
            return [exp for exp in self.main.student_experiments_db.values() if exp.student_id == student_id]
        rows = await StudentExperimentRepository(self.db).list_by_student(student_id)
        items = [self._to_student_experiment_model(row) for row in rows]
        for item in items:
            self.main.student_experiments_db[item.id] = item
        return items

    async def get_student_experiment_detail(self, student_exp_id: str):
        if self.db is None:
            item = self.main.student_experiments_db.get(student_exp_id)
            if not item:
                raise HTTPException(status_code=404, detail="学生实验记录不存在")
            return item
        row = await StudentExperimentRepository(self.db).get(student_exp_id)
        if not row:
            raise HTTPException(status_code=404, detail="学生实验记录不存在")
        item = self._to_student_experiment_model(row)
        self.main.student_experiments_db[item.id] = item
        return item

    async def get_submission_pdf_row(self, pdf_id: str):
        if self.db is None:
            item = self.main.submission_pdfs_db.get(pdf_id)
            if not item:
                raise HTTPException(status_code=404, detail="提交 PDF 不存在")
            return item
        row = await SubmissionPdfRepository(self.db).get(pdf_id)
        if not row:
            raise HTTPException(status_code=404, detail="提交 PDF 不存在")
        return row

    async def download_submission_pdf(self, pdf_id: str, teacher_username: Optional[str] = None):
        if self.db is None:
            record = self.main.submission_pdfs_db.get(pdf_id)
            if not record:
                raise HTTPException(status_code=404, detail="提交 PDF 不存在")
            if teacher_username and self.main.is_teacher(teacher_username):
                record.viewed = True
                record.viewed_at = datetime.now()
                record.viewed_by = teacher_username
            return record

        row = await SubmissionPdfRepository(self.db).get(pdf_id)
        if not row:
            raise HTTPException(status_code=404, detail="提交 PDF 不存在")
        if teacher_username and self.main.is_teacher(teacher_username):
            row.viewed = True
            row.viewed_at = datetime.now()
            row.viewed_by = teacher_username
            row.updated_at = datetime.now()
            await self._commit()
        return row

    async def get_experiment_submissions(self, experiment_id: str):
        if self.db is None:
            submissions = []
            for exp in self.main.student_experiments_db.values():
                if exp.experiment_id != experiment_id:
                    continue
                if not self.main._is_student_progress_record(exp.student_id):
                    continue
                payload = exp.dict()
                pdf_items = self.main._get_submission_pdfs(exp.id)
                payload["pdf_attachments"] = [self.main._pdf_to_payload(item) for item in pdf_items]
                payload["pdf_count"] = len(pdf_items)
                submissions.append(payload)
            return submissions

        exp_rows = await StudentExperimentRepository(self.db).list_by_experiment(experiment_id)
        submissions = []
        pdf_repo = SubmissionPdfRepository(self.db)
        for row in exp_rows:
            if not self.main._is_student_progress_record(row.student_id):
                continue
            model = self._to_student_experiment_model(row)
            payload = model.dict()
            pdf_rows = await pdf_repo.list_by_submission(row.id)
            payload["pdf_attachments"] = [self._pdf_to_payload(item) for item in pdf_rows]
            payload["pdf_count"] = len(pdf_rows)
            submissions.append(payload)
        return submissions

    async def grade_experiment(self, student_exp_id: str, score: float, comment: Optional[str], teacher_username: Optional[str]):
        if not (0 <= score <= 100):
            raise HTTPException(status_code=400, detail="分数必须在 0-100 之间")

        reviewer = teacher_username if teacher_username and self.main.is_teacher(teacher_username) else "teacher"

        if self.db is None:
            student_exp = self.main.student_experiments_db.get(student_exp_id)
            if not student_exp:
                raise HTTPException(status_code=404, detail="学生实验记录不存在")
            student_exp.score = score
            student_exp.teacher_comment = comment
            student_exp.status = self.main.ExperimentStatus.GRADED
            now = datetime.now()
            for item in self.main.submission_pdfs_db.values():
                if item.student_exp_id != student_exp_id:
                    continue
                item.reviewed = True
                item.reviewed_at = now
                item.reviewed_by = reviewer
                if not item.viewed:
                    item.viewed = True
                    item.viewed_at = now
                    item.viewed_by = reviewer
            return {"message": "评分成功", "score": score}

        student_row = await StudentExperimentRepository(self.db).get(student_exp_id)
        if not student_row:
            raise HTTPException(status_code=404, detail="学生实验记录不存在")
        student_row.score = score
        student_row.teacher_comment = comment
        student_row.status = self.main.ExperimentStatus.GRADED.value
        student_row.updated_at = datetime.now()

        pdf_repo = SubmissionPdfRepository(self.db)
        now = datetime.now()
        for item in await pdf_repo.list_by_submission(student_exp_id):
            item.reviewed = True
            item.reviewed_at = now
            item.reviewed_by = reviewer
            if not item.viewed:
                item.viewed = True
                item.viewed_at = now
                item.viewed_by = reviewer
            item.updated_at = now
        await self._commit()
        self.main.student_experiments_db[student_exp_id] = self._to_student_experiment_model(student_row)
        return {"message": "评分成功", "score": score}


def build_submission_service(main_module, db: Optional[AsyncSession] = None) -> SubmissionService:
    return SubmissionService(main_module=main_module, db=db)
