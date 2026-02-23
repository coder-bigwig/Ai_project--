from __future__ import annotations

import os
import io
import uuid
from datetime import datetime
from typing import Optional

from fastapi import File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import DEFAULT_ADMISSION_YEAR_OPTIONS, DEFAULT_PASSWORD
from ..repositories import (
    AttachmentRepository,
    AuthUserRepository,
    CourseMemberRepository,
    CourseOfferingRepository,
    CourseStudentMembershipRepository,
    CourseRepository,
    ExperimentRepository,
    PasswordHashRepository,
    SecurityQuestionRepository,
    StudentExperimentRepository,
    UserRepository,
)
from .identity_service import ensure_teacher_or_admin, normalize_text, resolve_user_role
from .operation_log_service import append_operation_log


class TeacherService:

    def __init__(self, main_module, db: Optional[AsyncSession] = None):
        if db is None:
            raise HTTPException(status_code=503, detail="PostgreSQL session unavailable")
        self.main = main_module
        self.db = db

    async def _commit(self):
        try:
            await self.db.commit()
        except Exception as exc:
            await self.db.rollback()
            raise HTTPException(status_code=500, detail="教师端数据写入失败") from exc

    def _to_course_record(self, row):
        return self.main.CourseRecord(
            id=row.id,
            name=row.name,
            description=row.description or "",
            created_by=row.created_by,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

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

    def _course_payload(self, course, experiments: list):
        ordered_experiments = sorted(
            experiments,
            key=lambda item: item.created_at or datetime.min,
            reverse=True,
        )
        published_count = sum(1 for item in ordered_experiments if item.published)
        latest_experiment_at = ordered_experiments[0].created_at if ordered_experiments else None
        tags = sorted({tag for item in ordered_experiments for tag in (item.tags or []) if normalize_text(tag)})
        return {
            "id": course.id,
            "name": course.name,
            "description": course.description or "",
            "created_by": course.created_by,
            "created_at": course.created_at,
            "updated_at": course.updated_at,
            "experiment_count": len(ordered_experiments),
            "published_count": published_count,
            "latest_experiment_at": latest_experiment_at,
            "tags": tags,
            "experiments": ordered_experiments,
        }

    async def _ensure_teacher(self, username: str) -> tuple[str, str]:
        return await ensure_teacher_or_admin(self.db, username)

    async def _update_auth_password(self, username: str, new_hash: str):
        auth_repo = AuthUserRepository(self.db)
        auth_user = await auth_repo.get_by_login_identifier(username)
        if auth_user is not None:
            auth_user.password_hash = new_hash
            auth_user.updated_at = datetime.now()

    async def upsert_teacher_security_question(self, payload):
        teacher_username = normalize_text(payload.teacher_username)
        question = self.main._normalize_security_question(payload.security_question or "")
        answer = payload.security_answer or ""

        if not teacher_username or not question or not answer:
            raise HTTPException(status_code=400, detail="账号、密保问题和答案不能为空")
        if len(question) < 2:
            raise HTTPException(status_code=400, detail="密保问题至少 2 个字")
        if len(self.main._normalize_security_answer(answer)) < 2:
            raise HTTPException(status_code=400, detail="密保答案至少 2 个字")

        normalized_teacher, _ = await self._ensure_teacher(teacher_username)
        repo = SecurityQuestionRepository(self.db)
        existing = await repo.get_by_username(normalized_teacher)
        await repo.upsert(
            {
                "id": existing.id if existing else str(uuid.uuid4()),
                "username": normalized_teacher,
                "role": "teacher",
                "question": question,
                "answer_hash": self.main._hash_security_answer(answer),
                "created_at": existing.created_at if existing else datetime.now(),
                "updated_at": datetime.now(),
            }
        )
        await append_operation_log(
            self.db,
            operator=normalized_teacher,
            action="accounts.update_security_question",
            target=normalized_teacher,
            detail="教师/管理员更新密保问题",
        )
        await self._commit()
        return {"message": "密保问题已保存"}

    async def change_teacher_password(self, payload):
        teacher_username = normalize_text(payload.teacher_username)
        old_password = payload.old_password or ""
        new_password = payload.new_password or ""

        if not teacher_username or not old_password or not new_password:
            raise HTTPException(status_code=400, detail="账号、旧密码和新密码不能为空")
        await self._ensure_teacher(teacher_username)
        if len(new_password) < 6:
            raise HTTPException(status_code=400, detail="新密码长度不能少于6位")
        if old_password == new_password:
            raise HTTPException(status_code=400, detail="新密码不能与旧密码相同")

        repo = PasswordHashRepository(self.db)
        current_row = await repo.get_by_username(teacher_username)
        current_hash = current_row.password_hash if current_row else self.main._default_password_hash()
        if current_hash != self.main._hash_password(old_password):
            raise HTTPException(status_code=401, detail="旧密码错误")

        new_hash = self.main._hash_password(new_password)
        if new_hash == self.main._default_password_hash():
            await repo.delete_by_username(teacher_username)
        else:
            await repo.upsert(
                {
                    "id": current_row.id if current_row else str(uuid.uuid4()),
                    "username": teacher_username,
                    "role": "teacher",
                    "password_hash": new_hash,
                    "created_at": current_row.created_at if current_row else datetime.now(),
                    "updated_at": datetime.now(),
                }
            )

        await self._update_auth_password(teacher_username, new_hash)
        await append_operation_log(
            self.db,
            operator=teacher_username,
            action="accounts.change_password",
            target=teacher_username,
            detail="教师端修改密码",
        )
        await self._commit()
        return {"message": "密码修改成功"}

    async def get_teacher_courses(self, teacher_username: str):
        normalized_teacher, _ = await self._ensure_teacher(teacher_username)
        course_repo = CourseRepository(self.db)
        course_rows = await course_repo.list_by_creator(normalized_teacher)

        # Include courses where this teacher is an active teacher/ta member in any non-archived offering.
        member_rows = await CourseMemberRepository(self.db).list_by_user(normalized_teacher)
        active_member_rows = [
            item
            for item in member_rows
            if normalize_text(item.role).lower() in {"teacher", "ta"}
            and normalize_text(item.status).lower() == "active"
        ]
        offering_ids = [item.offering_id for item in active_member_rows if item.offering_id]
        if offering_ids:
            offering_rows = await CourseOfferingRepository(self.db).list_by_ids(offering_ids)
            merged_course_rows = {normalize_text(item.id): item for item in course_rows}
            for offering in offering_rows:
                if normalize_text(offering.status).lower() == "archived":
                    continue
                course_id = normalize_text(offering.template_course_id)
                if not course_id or course_id in merged_course_rows:
                    continue
                course_row = await course_repo.get(course_id)
                if course_row is not None:
                    merged_course_rows[course_id] = course_row
            course_rows = list(merged_course_rows.values())

        experiment_rows = await ExperimentRepository(self.db).list_all()
        experiments = [self._to_experiment_model(item) for item in experiment_rows]

        payload = []
        for row in course_rows:
            course = self._to_course_record(row)
            related = [
                item
                for item in experiments
                if normalize_text(item.course_id) == normalize_text(course.id)
            ]
            payload.append(self._course_payload(course, related))
        payload.sort(key=lambda item: item.get("updated_at") or item.get("created_at") or datetime.min, reverse=True)
        return payload

    async def get_teacher_publish_targets(self, teacher_username: str):
        normalized_teacher, role = await self._ensure_teacher(teacher_username)
        user_repo = UserRepository(self.db)
        class_rows = await user_repo.list_classes()
        student_rows = await user_repo.list_by_role("student")

        classes = []
        for row in class_rows:
            if role == "admin" or normalize_text(row.created_by) == normalized_teacher:
                classes.append(self.main.ClassRecord(id=row.id, name=row.name, created_by=row.created_by, created_at=row.created_at))
        classes.sort(key=lambda item: item.name)

        class_owner_map = {}
        for item in classes:
            class_owner_map[item.name] = normalize_text(item.created_by)

        students = []
        for row in student_rows:
            student = self.main.StudentRecord(
                student_id=row.student_id or row.username,
                username=row.username,
                real_name=row.real_name or row.username,
                class_name=row.class_name or "",
                admission_year=row.admission_year or "",
                organization=row.organization or "",
                phone=row.phone or "",
                role="student",
                created_by=row.created_by or "",
                password_hash=row.password_hash or "",
                security_question=row.security_question or "",
                security_answer_hash=row.security_answer_hash or "",
                created_at=row.created_at,
                updated_at=row.updated_at,
            )
            if role == "admin":
                students.append(student)
                continue
            owner = normalize_text(student.created_by) or class_owner_map.get(student.class_name, "")
            if owner == normalized_teacher:
                students.append(student)
        students.sort(key=lambda item: (item.class_name, item.student_id))

        return {
            "classes": [{"id": item.id, "name": item.name} for item in classes],
            "students": [
                {"student_id": item.student_id, "real_name": item.real_name, "class_name": item.class_name}
                for item in students
            ],
        }

    @staticmethod
    def _admission_year(value) -> str:
        raw = normalize_text(value)
        if not raw:
            return ""
        digits = "".join(ch for ch in raw if ch.isdigit())
        if len(digits) == 4 and digits.startswith("20"):
            return digits
        if len(digits) == 2:
            return f"20{digits}"
        return ""

    @staticmethod
    def _infer_admission_year(student_id: str) -> str:
        normalized = normalize_text(student_id)
        if len(normalized) >= 2 and normalized[:2].isdigit():
            return f"20{normalized[:2]}"
        return ""

    @classmethod
    def _format_admission_year_label(cls, admission_year: str) -> str:
        normalized = cls._admission_year(admission_year)
        return f"{normalized}级" if normalized else ""

    async def _ensure_course_manager(self, course_id: str, teacher_username: str):
        normalized_teacher, role = await self._ensure_teacher(teacher_username)
        normalized_course_id = normalize_text(course_id)
        if not normalized_course_id:
            raise HTTPException(status_code=400, detail="course_id is required")

        course = await CourseRepository(self.db).get(normalized_course_id)
        if course is None:
            raise HTTPException(status_code=404, detail="course not found")

        if role == "admin" or normalize_text(course.created_by) == normalized_teacher:
            return normalized_teacher, role, course

        # Collaborative teachers/TAs can manage a course if they are active members
        # of any active offering under this template course.
        member_rows = await CourseMemberRepository(self.db).list_by_user(normalized_teacher)
        active_member_rows = [
            item
            for item in member_rows
            if normalize_text(item.role).lower() in {"teacher", "ta"}
            and normalize_text(item.status).lower() == "active"
        ]
        offering_ids = [item.offering_id for item in active_member_rows if item.offering_id]
        if offering_ids:
            offering_rows = await CourseOfferingRepository(self.db).list_by_ids(offering_ids)
            has_course_access = any(
                normalize_text(item.template_course_id) == normalized_course_id
                and normalize_text(item.status).lower() != "archived"
                for item in offering_rows
            )
            if has_course_access:
                return normalized_teacher, role, course

        raise HTTPException(status_code=403, detail="permission denied for this course")

    async def _course_student_pairs(self, course_id: str):
        membership_repo = CourseStudentMembershipRepository(self.db)
        memberships = await membership_repo.list_by_course(course_id)
        if not memberships:
            return []

        student_rows = await UserRepository(self.db).list_by_role("student")
        by_student_id = {}
        by_username = {}
        for row in student_rows:
            student_id = normalize_text(row.student_id or row.username)
            username = normalize_text(row.username)
            if student_id:
                by_student_id[student_id] = row
            if username:
                by_username[username] = row

        pairs = []
        for membership in memberships:
            key = normalize_text(membership.student_id)
            student = by_student_id.get(key) or by_username.get(key)
            if student is None:
                continue
            canonical_student_id = normalize_text(student.student_id or student.username)
            if canonical_student_id and membership.student_id != canonical_student_id:
                membership.student_id = canonical_student_id
            pairs.append((membership, student))
        return pairs

    async def list_course_students(
        self,
        course_id: str,
        teacher_username: str,
        keyword: str = "",
        class_name: str = "",
        admission_year: str = "",
        page: int = 1,
        page_size: int = 20,
    ):
        await self._ensure_course_manager(course_id=course_id, teacher_username=teacher_username)
        page = max(page, 1)
        page_size = max(1, min(page_size, 100))

        normalized_keyword = normalize_text(keyword).lower()
        normalized_class_name = normalize_text(class_name)
        normalized_admission_year = self._admission_year(admission_year)

        rows = []
        for membership, student in await self._course_student_pairs(course_id):
            student_id = normalize_text(student.student_id or student.username)
            real_name = normalize_text(student.real_name)
            row_class_name = normalize_text(student.class_name)
            row_admission_year = self._admission_year(student.admission_year)
            if normalized_keyword and normalized_keyword not in student_id.lower() and normalized_keyword not in real_name.lower():
                continue
            if normalized_class_name and row_class_name != normalized_class_name:
                continue
            if normalized_admission_year and row_admission_year != normalized_admission_year:
                continue
            rows.append(
                {
                    "student_id": student_id,
                    "username": normalize_text(student.username) or student_id,
                    "real_name": real_name or student_id,
                    "class_name": row_class_name,
                    "admission_year": row_admission_year,
                    "admission_year_label": self._format_admission_year_label(row_admission_year),
                    "organization": normalize_text(student.organization),
                    "phone": normalize_text(student.phone),
                    "role": "student",
                    "created_at": student.created_at,
                    "updated_at": student.updated_at,
                    "joined_at": membership.created_at,
                }
            )

        rows.sort(
            key=lambda item: item.get("joined_at") or item.get("updated_at") or item.get("created_at") or datetime.min,
            reverse=True,
        )
        total = len(rows)
        start = (page - 1) * page_size
        end = start + page_size
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": rows[start:end],
        }

    async def list_course_student_class_options(self, course_id: str, teacher_username: str):
        await self._ensure_course_manager(course_id=course_id, teacher_username=teacher_username)
        class_names = {
            normalize_text(student.class_name)
            for _, student in await self._course_student_pairs(course_id)
            if normalize_text(student.class_name)
        }
        return [{"value": name, "label": name} for name in sorted(class_names)]

    async def list_course_student_admission_year_options(self, course_id: str, teacher_username: str):
        await self._ensure_course_manager(course_id=course_id, teacher_username=teacher_username)
        year_set = set(DEFAULT_ADMISSION_YEAR_OPTIONS)
        for _, student in await self._course_student_pairs(course_id):
            year = self._admission_year(student.admission_year)
            if year:
                year_set.add(year)
        return [{"value": year, "label": f"{year}级"} for year in sorted(year_set)]

    async def download_course_student_template(self, course_id: str, teacher_username: str, format: str = "xlsx"):
        await self._ensure_course_manager(course_id=course_id, teacher_username=teacher_username)
        template_format = normalize_text(format).lower()
        if template_format == "csv":
            payload = self.main._build_csv_template()
            return StreamingResponse(
                io.BytesIO(payload),
                media_type="text/csv; charset=utf-8",
                headers={"Content-Disposition": "attachment; filename=student_import_template.csv"},
            )
        if template_format == "xlsx":
            payload = self.main._build_xlsx_template()
            return StreamingResponse(
                io.BytesIO(payload),
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": "attachment; filename=student_import_template.xlsx"},
            )
        raise HTTPException(status_code=400, detail="format must be xlsx or csv")

    async def import_course_students(
        self,
        course_id: str,
        teacher_username: str,
        file: UploadFile = File(...),
    ):
        normalized_teacher, _, course = await self._ensure_course_manager(course_id=course_id, teacher_username=teacher_username)
        if not file.filename:
            raise HTTPException(status_code=400, detail="file name is required")

        file_content = await file.read()
        parsed_rows = self.main._parse_student_import_rows(file.filename, file_content)

        user_repo = UserRepository(self.db)
        auth_repo = AuthUserRepository(self.db)
        membership_repo = CourseStudentMembershipRepository(self.db)

        now = datetime.now()
        seen_in_file = set()
        success_count = 0
        created_count = 0
        skipped_count = 0
        failed_count = 0
        errors = []

        default_hash = self.main._hash_password(DEFAULT_PASSWORD)

        for row_number, row in parsed_rows:
            student_id, real_name, class_name, organization, phone, admission_year_raw = row
            student_id = normalize_text(student_id)
            real_name = normalize_text(real_name)
            class_name = normalize_text(class_name)
            organization = normalize_text(organization)
            phone = normalize_text(phone)
            admission_year = self._admission_year(admission_year_raw) or self._infer_admission_year(student_id)

            if not all([student_id, real_name, class_name, organization, phone]):
                failed_count += 1
                errors.append({"row": row_number, "student_id": student_id, "reason": "required fields are missing"})
                continue
            if not admission_year:
                failed_count += 1
                errors.append({"row": row_number, "student_id": student_id, "reason": "invalid admission year"})
                continue
            if student_id in seen_in_file:
                skipped_count += 1
                errors.append({"row": row_number, "student_id": student_id, "reason": "duplicate student id in file"})
                continue
            seen_in_file.add(student_id)

            role_value = await resolve_user_role(self.db, student_id)
            if role_value in {"teacher", "admin"}:
                failed_count += 1
                errors.append({"row": row_number, "student_id": student_id, "reason": "student id conflicts with teacher/admin"})
                continue

            student_row = await user_repo.get_student_by_student_id(student_id)
            if student_row is None:
                conflict_row = await user_repo.get_by_username(student_id)
                if conflict_row is not None:
                    if normalize_text(conflict_row.role).lower() != "student":
                        failed_count += 1
                        errors.append({"row": row_number, "student_id": student_id, "reason": "student id conflicts with existing username"})
                        continue
                    student_row = conflict_row
                    if not normalize_text(student_row.student_id):
                        student_row.student_id = student_id
                else:
                    student_row = await user_repo.upsert(
                        {
                            "id": str(uuid.uuid4()),
                            "username": student_id,
                            "role": "student",
                            "real_name": real_name,
                            "student_id": student_id,
                            "class_name": class_name,
                            "admission_year": admission_year,
                            "organization": organization,
                            "phone": phone,
                            "password_hash": default_hash,
                            "security_question": "",
                            "security_answer_hash": "",
                            "created_by": normalized_teacher,
                            "is_active": True,
                            "created_at": now,
                            "updated_at": now,
                            "extra": {},
                        }
                    )
                    await auth_repo.upsert_by_email(
                        {
                            "id": str(uuid.uuid4()),
                            "email": student_id,
                            "username": student_id,
                            "role": "student",
                            "password_hash": default_hash,
                            "is_active": True,
                            "created_at": now,
                            "updated_at": now,
                        }
                    )
                    created_count += 1

            canonical_student_id = normalize_text(student_row.student_id or student_row.username or student_id)
            existing_membership = await membership_repo.get_by_course_and_student(course.id, canonical_student_id)
            if existing_membership is not None:
                skipped_count += 1
                errors.append({"row": row_number, "student_id": canonical_student_id, "reason": "already enrolled in this course"})
                continue

            await membership_repo.create(
                {
                    "id": str(uuid.uuid4()),
                    "course_id": course.id,
                    "student_id": canonical_student_id,
                    "added_by": normalized_teacher,
                    "created_at": now,
                    "updated_at": now,
                }
            )
            success_count += 1

        await append_operation_log(
            self.db,
            operator=normalized_teacher,
            action="courses.students.import",
            target=course.id,
            detail=f"success={success_count}, created={created_count}, skipped={skipped_count}, failed={failed_count}",
        )
        await self._commit()
        return {
            "total_rows": len(parsed_rows),
            "success_count": success_count,
            "created_count": created_count,
            "skipped_count": skipped_count,
            "failed_count": failed_count,
            "errors": errors,
        }

    async def reset_course_student_password(self, course_id: str, student_id: str, teacher_username: str):
        normalized_teacher, _, course = await self._ensure_course_manager(course_id=course_id, teacher_username=teacher_username)
        normalized_student_id = normalize_text(student_id)
        if not normalized_student_id:
            raise HTTPException(status_code=400, detail="student_id is required")

        membership_repo = CourseStudentMembershipRepository(self.db)
        membership = await membership_repo.get_by_course_and_student(course.id, normalized_student_id)
        student = await UserRepository(self.db).get_student_by_student_id(normalized_student_id)
        if student is None:
            student = await UserRepository(self.db).get_by_username(normalized_student_id)
        if student is not None:
            canonical_student_id = normalize_text(student.student_id or student.username)
            if membership is None and canonical_student_id:
                membership = await membership_repo.get_by_course_and_student(course.id, canonical_student_id)
                normalized_student_id = canonical_student_id

        if membership is None:
            raise HTTPException(status_code=404, detail="student is not enrolled in this course")
        if student is None or normalize_text(student.role).lower() != "student":
            raise HTTPException(status_code=404, detail="student account not found")

        new_hash = self.main._hash_password(DEFAULT_PASSWORD)
        student.password_hash = new_hash
        student.updated_at = datetime.now()

        auth_user = await AuthUserRepository(self.db).get_by_login_identifier(student.username or normalized_student_id)
        if auth_user is not None:
            auth_user.password_hash = new_hash
            auth_user.updated_at = datetime.now()

        await append_operation_log(
            self.db,
            operator=normalized_teacher,
            action="courses.students.reset_password",
            target=f"{course.id}:{normalized_student_id}",
            detail="password reset to default",
        )
        await self._commit()
        return {"message": "password reset", "student_id": normalized_student_id}

    async def remove_course_student(self, course_id: str, student_id: str, teacher_username: str):
        normalized_teacher, _, course = await self._ensure_course_manager(course_id=course_id, teacher_username=teacher_username)
        normalized_student_id = normalize_text(student_id)
        if not normalized_student_id:
            raise HTTPException(status_code=400, detail="student_id is required")

        membership_repo = CourseStudentMembershipRepository(self.db)
        deleted = await membership_repo.delete_by_course_and_student(course.id, normalized_student_id)
        if deleted == 0:
            student = await UserRepository(self.db).get_by_username(normalized_student_id)
            if student is not None:
                canonical_student_id = normalize_text(student.student_id or student.username)
                if canonical_student_id and canonical_student_id != normalized_student_id:
                    deleted = await membership_repo.delete_by_course_and_student(course.id, canonical_student_id)
                    normalized_student_id = canonical_student_id
        if deleted == 0:
            raise HTTPException(status_code=404, detail="student is not enrolled in this course")

        await append_operation_log(
            self.db,
            operator=normalized_teacher,
            action="courses.students.remove",
            target=f"{course.id}:{normalized_student_id}",
        )
        await self._commit()
        return {"message": "removed from course", "student_id": normalized_student_id}

    async def batch_remove_course_students(self, course_id: str, teacher_username: str, class_name: str = ""):
        normalized_teacher, _, course = await self._ensure_course_manager(course_id=course_id, teacher_username=teacher_username)
        normalized_class_name = normalize_text(class_name)
        if not normalized_class_name:
            raise HTTPException(status_code=400, detail="class_name is required")

        target_student_ids = []
        for _, student in await self._course_student_pairs(course.id):
            if normalize_text(student.class_name) == normalized_class_name:
                target_student_ids.append(normalize_text(student.student_id or student.username))

        deleted = await CourseStudentMembershipRepository(self.db).delete_by_course_and_students(course.id, target_student_ids)
        await append_operation_log(
            self.db,
            operator=normalized_teacher,
            action="courses.students.batch_remove",
            target=course.id,
            detail=f"class_name={normalized_class_name}, deleted={deleted}",
        )
        await self._commit()
        return {
            "message": "batch remove completed",
            "course_id": course.id,
            "class_name": normalized_class_name,
            "deleted_count": int(deleted or 0),
            "deleted_student_ids": target_student_ids,
        }

    async def create_teacher_course(self, payload):
        normalized_teacher, _ = await self._ensure_teacher(payload.teacher_username)
        course_name = normalize_text(payload.name)
        if not course_name:
            raise HTTPException(status_code=400, detail="课程名称不能为空")

        repo = CourseRepository(self.db)

        now = datetime.now()
        row = await repo.create(
            {
                "id": str(uuid.uuid4()),
                "name": course_name,
                "description": normalize_text(payload.description or ""),
                "created_by": normalized_teacher,
                "created_at": now,
                "updated_at": now,
            }
        )
        await append_operation_log(
            self.db,
            operator=normalized_teacher,
            action="courses.create",
            target=course_name,
            detail=f"course_id={row.id}",
        )
        await self._commit()
        course = self._to_course_record(row)
        return self._course_payload(course, [])

    async def update_teacher_course(self, course_id: str, payload):
        normalized_teacher, _ = await self._ensure_teacher(payload.teacher_username)
        course_repo = CourseRepository(self.db)
        exp_repo = ExperimentRepository(self.db)
        row = await course_repo.get(course_id)
        if not row or normalize_text(row.created_by) != normalized_teacher:
            raise HTTPException(status_code=404, detail="课程不存在")

        next_name = normalize_text(payload.name) or row.name
        if normalize_text(next_name).lower() != normalize_text(row.name).lower():
            existing = await course_repo.find_by_teacher_and_name(normalized_teacher, next_name)
            if existing and existing.id != row.id:
                raise HTTPException(status_code=409, detail="课程名称已存在")
            old_name = row.name
            row.name = next_name

            experiment_rows = await exp_repo.list_by_course_ids([course_id])
            for item in experiment_rows:
                if normalize_text(item.created_by) != normalized_teacher:
                    continue
                if normalize_text(item.course_name) == normalize_text(old_name):
                    item.course_name = next_name

        if payload.description is not None:
            row.description = normalize_text(payload.description)
        row.updated_at = datetime.now()

        related_rows = await exp_repo.list_by_course_ids([course_id])
        related = [self._to_experiment_model(item) for item in related_rows if normalize_text(item.created_by) == normalized_teacher]
        await append_operation_log(
            self.db,
            operator=normalized_teacher,
            action="courses.update",
            target=course_id,
            detail=f"name={row.name}",
        )
        await self._commit()
        return self._course_payload(self._to_course_record(row), related)

    async def delete_teacher_course(self, course_id: str, teacher_username: str, delete_experiments: bool = False):
        normalized_teacher, _ = await self._ensure_teacher(teacher_username)

        course_repo = CourseRepository(self.db)
        exp_repo = ExperimentRepository(self.db)
        att_repo = AttachmentRepository(self.db)
        course_row = await course_repo.get(course_id)
        if not course_row or normalize_text(course_row.created_by) != normalized_teacher:
            raise HTTPException(status_code=404, detail="课程不存在")

        exp_rows = [
            item
            for item in await exp_repo.list_by_course_ids([course_id])
            if normalize_text(item.created_by) == normalized_teacher
        ]
        if exp_rows and not delete_experiments:
            raise HTTPException(status_code=409, detail="课程下存在实验，请先删除实验或传入 delete_experiments=true")

        if delete_experiments:
            for exp in exp_rows:
                attachments = await att_repo.list_by_experiment(exp.id)
                for att in attachments:
                    if os.path.exists(att.file_path):
                        try:
                            os.remove(att.file_path)
                        except OSError:
                            pass
                    await att_repo.delete(att.id)
                await exp_repo.delete(exp.id)

        await course_repo.delete(course_id)
        await append_operation_log(
            self.db,
            operator=normalized_teacher,
            action="courses.delete",
            target=course_id,
            detail=f"delete_experiments={bool(delete_experiments)}",
        )
        await self._commit()
        return {"message": "课程已删除", "id": course_id}

    async def toggle_course_publish(self, course_id: str, teacher_username: str, published: bool):
        normalized_teacher, _ = await self._ensure_teacher(teacher_username)
        course_repo = CourseRepository(self.db)
        exp_repo = ExperimentRepository(self.db)
        course = await course_repo.get(course_id)
        if not course or normalize_text(course.created_by) != normalized_teacher:
            raise HTTPException(status_code=404, detail="课程不存在")

        related = [
            item
            for item in await exp_repo.list_by_course_ids([course_id])
            if normalize_text(item.created_by) == normalized_teacher
        ]
        if not related:
            return {"message": "课程下暂无实验", "published": published, "updated": 0}

        for item in related:
            item.published = published
        course.updated_at = datetime.now()
        await append_operation_log(
            self.db,
            operator=normalized_teacher,
            action="courses.toggle_publish",
            target=course_id,
            detail=f"published={bool(published)}",
        )
        await self._commit()
        return {
            "message": f"Course publish state updated: {'published' if published else 'unpublished'}",
            "published": published,
            "updated": len(related),
        }

    async def get_all_student_progress(self, teacher_username: str):
        normalized_teacher, _ = await self._ensure_teacher(teacher_username)

        exp_rows = await ExperimentRepository(self.db).list_all()
        owned_experiment_ids = {
            item.id
            for item in exp_rows
            if normalize_text(item.created_by) == normalized_teacher
        }

        student_rows = await UserRepository(self.db).list_by_role("student")
        student_ids = {normalize_text(item.student_id or item.username) for item in student_rows}

        submissions = await StudentExperimentRepository(self.db).list_all()
        payload = []
        for row in submissions:
            if row.experiment_id not in owned_experiment_ids:
                continue
            if normalize_text(row.student_id) not in student_ids:
                continue
            status_value = row.status or self.main.ExperimentStatus.NOT_STARTED.value
            payload.append(
                {
                    "student_id": row.student_id,
                    "experiment_id": row.experiment_id,
                    "status": status_value,
                    "start_time": row.start_time,
                    "submit_time": row.submit_time,
                    "score": row.score,
                }
            )
        return payload

    async def get_statistics(self):
        experiments = await ExperimentRepository(self.db).list_all()
        submissions = await StudentExperimentRepository(self.db).list_all()
        status_count = {}
        for row in submissions:
            status_value = row.status or self.main.ExperimentStatus.NOT_STARTED.value
            status_count[status_value] = status_count.get(status_value, 0) + 1
        return {
            "total_experiments": len(experiments),
            "total_submissions": len(submissions),
            "status_distribution": status_count,
        }


def build_teacher_service(main_module, db: Optional[AsyncSession] = None) -> TeacherService:
    return TeacherService(main_module=main_module, db=db)
