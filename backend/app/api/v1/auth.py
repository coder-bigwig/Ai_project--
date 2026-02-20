from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.session import get_db
from ...repositories.users import UserRepository
from ...services.auth_service import AuthService
from ...storage_config import DOUBLE_WRITE_JSON, PG_READ_PREFERRED, STORAGE_BACKEND

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


class ForgotPasswordResetRequest(BaseModel):
    username: str
    security_answer: str
    new_password: str


def _get_main_module():
    from ... import main

    return main


def _role_value(role) -> str:
    if hasattr(role, "value"):
        return str(role.value or "")
    return str(role or "")


def _legacy_student_login_payload(main, student):
    security_question_set = bool(main._normalize_security_question(student.security_question or ""))
    return {
        "username": student.username,
        "role": student.role,
        "ai_session_token": main._create_ai_session_token(student.username),
        "student_id": student.student_id,
        "real_name": student.real_name,
        "class_name": student.class_name,
        "organization": student.organization,
        "major": student.organization,
        "admission_year": main._normalize_admission_year(student.admission_year),
        "security_question_set": security_question_set,
        "force_security_setup": not security_question_set,
    }


def _legacy_login(main, username: str, password: str):
    if main.is_admin(username):
        if not main._verify_account_password(username, password):
            raise HTTPException(status_code=401, detail="用户名或密码错误")
        return {
            "username": username,
            "role": "admin",
            "ai_session_token": main._create_ai_session_token(username),
            "force_security_setup": False,
        }

    if main.is_teacher(username):
        if not main._verify_account_password(username, password):
            raise HTTPException(status_code=401, detail="用户名或密码错误")
        return {
            "username": username,
            "role": "teacher",
            "ai_session_token": main._create_ai_session_token(username),
            "force_security_setup": False,
        }

    student = main.students_db.get(username)
    if not student:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    if student.password_hash != main._hash_password(password):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return _legacy_student_login_payload(main, student)


def _legacy_login_or_none(main, username: str, password: str):
    try:
        return _legacy_login(main, username=username, password=password)
    except HTTPException as exc:
        if exc.status_code == 401:
            return None
        raise


async def _postgres_login_or_none(main, db: Optional[AsyncSession], username: str, password: str):
    if db is None:
        return None

    service = AuthService(db=db, password_hasher=main._hash_password)
    auth_user = await service.authenticate(identifier=username, password=password)
    if auth_user is None:
        return None

    account_username = main._normalize_text(auth_user.username or auth_user.email)
    role = _role_value(auth_user.role).lower()
    if role in {"admin", "teacher"}:
        return {
            "username": account_username,
            "role": role,
            "ai_session_token": main._create_ai_session_token(account_username),
            "force_security_setup": False,
        }

    user_repo = UserRepository(db)
    student = await user_repo.get_by_username(account_username)
    if student is None:
        student = await user_repo.get_student_by_student_id(account_username)
    if student is None:
        return None

    security_question_set = bool(main._normalize_security_question(student.security_question or ""))
    student_username = main._normalize_text(student.username or student.student_id or account_username)
    student_id = main._normalize_text(student.student_id or student_username)
    return {
        "username": student_username,
        "role": "student",
        "ai_session_token": main._create_ai_session_token(student_username),
        "student_id": student_id,
        "real_name": student.real_name,
        "class_name": student.class_name,
        "organization": student.organization,
        "major": student.organization,
        "admission_year": main._normalize_admission_year(student.admission_year),
        "security_question_set": security_question_set,
        "force_security_setup": not security_question_set,
    }


def _append_reset_password_log(main, username: str, role: str):
    normalized_role = main._normalize_text(role).lower()
    if normalized_role in {"teacher", "admin"}:
        main._append_operation_log(
            operator=username,
            action="accounts.reset_password_with_security",
            target=username,
            detail="教师/管理员通过密保重置密码",
        )
        return
    main._append_operation_log(
        operator=username,
        action="students.reset_password_with_security",
        target=username,
        detail="学生通过密保重置密码",
    )


def _legacy_reset_password(
    main,
    normalized_username: str,
    security_answer: str,
    new_password: str,
    persist_json: bool = True,
):
    if main.is_teacher(normalized_username) or main.is_admin(normalized_username):
        security_payload = main.account_security_questions_db.get(normalized_username) or {}
        question = main._normalize_security_question(security_payload.get("question") or "")
        answer_hash = main._normalize_text(security_payload.get("answer_hash") or "")
        if not question or not answer_hash:
            raise HTTPException(status_code=400, detail="该账号未设置密保问题")
        if not main._verify_security_answer(answer_hash, security_answer):
            raise HTTPException(status_code=401, detail="密保答案错误")

        new_hash = main._hash_password(new_password)
        if new_hash == main._default_password_hash():
            main.teacher_account_password_hashes_db.pop(normalized_username, None)
        else:
            main.teacher_account_password_hashes_db[normalized_username] = new_hash
        if persist_json:
            main._save_user_registry()
        _append_reset_password_log(main, normalized_username, "teacher")
        return {"role": "teacher", "new_hash": new_hash, "student_id": None}

    student = main.students_db.get(normalized_username)
    if not student:
        raise HTTPException(status_code=404, detail="账号不存在")
    question = main._normalize_security_question(student.security_question or "")
    answer_hash = main._normalize_text(student.security_answer_hash or "")
    if not question or not answer_hash:
        raise HTTPException(status_code=400, detail="该账号未设置密保问题")
    if not main._verify_security_answer(answer_hash, security_answer):
        raise HTTPException(status_code=401, detail="密保答案错误")

    new_hash = main._hash_password(new_password)
    student.password_hash = new_hash
    student.updated_at = main.datetime.now()
    if persist_json:
        main._save_user_registry()
    _append_reset_password_log(main, normalized_username, "student")
    return {"role": "student", "new_hash": new_hash, "student_id": student.student_id}


def _apply_legacy_password_state(
    main,
    username: str,
    role: str,
    new_hash: str,
    student_id: str | None,
    persist_json: bool,
):
    normalized_role = main._normalize_text(role).lower()
    if normalized_role in {"teacher", "admin"}:
        if new_hash == main._default_password_hash():
            main.teacher_account_password_hashes_db.pop(username, None)
        else:
            main.teacher_account_password_hashes_db[username] = new_hash
    else:
        student = None
        if student_id:
            student = main.students_db.get(student_id)
        if student is None:
            student = main.students_db.get(username)
        if student is not None:
            student.password_hash = new_hash
            student.updated_at = datetime.now()

    if persist_json:
        main._save_user_registry()


async def _postgres_reset_password_or_none(
    main,
    db: Optional[AsyncSession],
    normalized_username: str,
    security_answer: str,
    new_password: str,
):
    if db is None:
        return None

    service = AuthService(db=db, password_hasher=main._hash_password)
    user_repo = UserRepository(db)
    auth_user = await service.get_user_by_identifier(normalized_username)

    student_row = None
    if auth_user is None:
        student_row = await user_repo.get_student_by_student_id(normalized_username)
        if student_row is not None:
            student_username = main._normalize_text(student_row.username or student_row.student_id)
            auth_user = await service.get_user_by_identifier(student_username)

    if auth_user is None:
        return None

    account_username = main._normalize_text(auth_user.username or auth_user.email or normalized_username)
    role = _role_value(auth_user.role).lower()

    if role in {"teacher", "admin"}:
        security_payload = main.account_security_questions_db.get(account_username) or {}
        question = main._normalize_security_question(security_payload.get("question") or "")
        answer_hash = main._normalize_text(security_payload.get("answer_hash") or "")
        if not question or not answer_hash:
            raise HTTPException(status_code=400, detail="该账号未设置密保问题")
        if not main._verify_security_answer(answer_hash, security_answer):
            raise HTTPException(status_code=401, detail="密保答案错误")
    else:
        if student_row is None:
            student_row = await user_repo.get_by_username(account_username)
        if student_row is None:
            student_row = await user_repo.get_student_by_student_id(account_username)

        if student_row is None:
            student = main.students_db.get(normalized_username)
            if not student:
                raise HTTPException(status_code=404, detail="账号不存在")
            question = main._normalize_security_question(student.security_question or "")
            answer_hash = main._normalize_text(student.security_answer_hash or "")
            student_id = student.student_id
        else:
            question = main._normalize_security_question(student_row.security_question or "")
            answer_hash = main._normalize_text(student_row.security_answer_hash or "")
            student_id = main._normalize_text(student_row.student_id or student_row.username)

        if not question or not answer_hash:
            raise HTTPException(status_code=400, detail="该账号未设置密保问题")
        if not main._verify_security_answer(answer_hash, security_answer):
            raise HTTPException(status_code=401, detail="密保答案错误")

        new_hash = main._hash_password(new_password)
        changed = await service.set_password(auth_user.id, new_hash)
        if changed is None:
            return None
        return {
            "role": "student",
            "username": account_username,
            "student_id": student_id,
            "new_hash": new_hash,
        }

    new_hash = main._hash_password(new_password)
    changed = await service.set_password(auth_user.id, new_hash)
    if changed is None:
        return None
    return {
        "role": role if role in {"teacher", "admin"} else "student",
        "username": account_username,
        "student_id": None,
        "new_hash": new_hash,
    }


@router.post("/api/auth/login")
async def login(
    payload: LoginRequest,
    db: Optional[AsyncSession] = Depends(get_db),
):
    """统一登录入口"""
    main = _get_main_module()
    username = main._normalize_text(payload.username)
    password = payload.password or ""
    if not username or not password:
        raise HTTPException(status_code=400, detail="用户名和密码不能为空")

    if STORAGE_BACKEND == "json":
        return _legacy_login(main, username=username, password=password)

    if STORAGE_BACKEND == "postgres":
        if db is None:
            raise HTTPException(status_code=503, detail="PostgreSQL session unavailable")
        result = await _postgres_login_or_none(main, db=db, username=username, password=password)
        if result is None:
            raise HTTPException(status_code=401, detail="用户名或密码错误")
        return result

    if PG_READ_PREFERRED:
        result = await _postgres_login_or_none(main, db=db, username=username, password=password)
        if result is not None:
            return result
        fallback = _legacy_login_or_none(main, username=username, password=password)
        if fallback is not None:
            return fallback
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    fallback = _legacy_login_or_none(main, username=username, password=password)
    if fallback is not None:
        return fallback
    result = await _postgres_login_or_none(main, db=db, username=username, password=password)
    if result is not None:
        return result
    raise HTTPException(status_code=401, detail="用户名或密码错误")


@router.get("/api/auth/security-question")
async def get_security_question(username: str):
    main = _get_main_module()
    normalized_username = main._normalize_text(username)
    if not normalized_username:
        raise HTTPException(status_code=400, detail="用户名不能为空")

    if main.is_teacher(normalized_username) or main.is_admin(normalized_username):
        payload = main.account_security_questions_db.get(normalized_username) or {}
        question = main._normalize_security_question(payload.get("question") or "")
        if not question:
            raise HTTPException(status_code=404, detail="该账号未设置密保问题")
        role = "admin" if main.is_admin(normalized_username) else "teacher"
        return {"username": normalized_username, "role": role, "security_question": question}

    student = main.students_db.get(normalized_username)
    if not student:
        raise HTTPException(status_code=404, detail="账号不存在")
    question = main._normalize_security_question(student.security_question or "")
    if not question:
        raise HTTPException(status_code=404, detail="该账号未设置密保问题")
    return {"username": student.username, "role": "student", "security_question": question}


@router.post("/api/auth/forgot-password-reset")
async def reset_password_with_security_question(
    payload: ForgotPasswordResetRequest,
    db: Optional[AsyncSession] = Depends(get_db),
):
    main = _get_main_module()
    normalized_username = main._normalize_text(payload.username)
    security_answer = payload.security_answer or ""
    new_password = payload.new_password or ""

    if not normalized_username or not security_answer or not new_password:
        raise HTTPException(status_code=400, detail="账号、密保答案和新密码不能为空")
    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="新密码长度不能少于6位")

    if STORAGE_BACKEND == "json":
        _legacy_reset_password(
            main,
            normalized_username=normalized_username,
            security_answer=security_answer,
            new_password=new_password,
            persist_json=True,
        )
        return {"message": "密码重置成功"}

    if STORAGE_BACKEND == "postgres":
        if db is None:
            raise HTTPException(status_code=503, detail="PostgreSQL session unavailable")
        result = await _postgres_reset_password_or_none(
            main,
            db=db,
            normalized_username=normalized_username,
            security_answer=security_answer,
            new_password=new_password,
        )
        if result is None:
            raise HTTPException(status_code=404, detail="账号不存在")
        try:
            await db.commit()
        except Exception:
            await db.rollback()
            raise HTTPException(status_code=500, detail="密码重置失败")
        _apply_legacy_password_state(
            main,
            username=result["username"],
            role=result["role"],
            new_hash=result["new_hash"],
            student_id=result["student_id"],
            persist_json=False,
        )
        _append_reset_password_log(main, result["username"], result["role"])
        return {"message": "密码重置成功"}

    result = await _postgres_reset_password_or_none(
        main,
        db=db,
        normalized_username=normalized_username,
        security_answer=security_answer,
        new_password=new_password,
    )

    if result is not None:
        if db is not None:
            try:
                await db.commit()
            except Exception:
                await db.rollback()
                raise HTTPException(status_code=500, detail="密码重置失败")
        _apply_legacy_password_state(
            main,
            username=result["username"],
            role=result["role"],
            new_hash=result["new_hash"],
            student_id=result["student_id"],
            persist_json=DOUBLE_WRITE_JSON,
        )
        _append_reset_password_log(main, result["username"], result["role"])
        return {"message": "密码重置成功"}

    _legacy_reset_password(
        main,
        normalized_username=normalized_username,
        security_answer=security_answer,
        new_password=new_password,
        persist_json=DOUBLE_WRITE_JSON,
    )
    return {"message": "密码重置成功"}


async def check_role(username: str):
    """检查用户角色"""
    main = _get_main_module()
    normalized = main._normalize_text(username)
    if main.is_admin(normalized):
        role = "admin"
    elif main.is_teacher(normalized):
        role = "teacher"
    else:
        role = "student"
    return {
        "username": normalized,
        "role": role,
    }


router.add_api_route("/api/check-role", check_role, methods=["GET"])
