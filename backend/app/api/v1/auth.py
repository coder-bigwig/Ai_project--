from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

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


@router.post("/api/auth/login")
async def login(payload: LoginRequest):
    """统一登录入口"""
    main = _get_main_module()
    username = main._normalize_text(payload.username)
    password = payload.password or ""
    if not username or not password:
        raise HTTPException(status_code=400, detail="用户名和密码不能为空")

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
async def reset_password_with_security_question(payload: ForgotPasswordResetRequest):
    main = _get_main_module()
    normalized_username = main._normalize_text(payload.username)
    security_answer = payload.security_answer or ""
    new_password = payload.new_password or ""

    if not normalized_username or not security_answer or not new_password:
        raise HTTPException(status_code=400, detail="账号、密保答案和新密码不能为空")
    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="新密码长度不能少于6位")

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
        main._save_user_registry()
        main._append_operation_log(
            operator=normalized_username,
            action="accounts.reset_password_with_security",
            target=normalized_username,
            detail="??/???????????",
        )
        return {"message": "密码重置成功"}

    student = main.students_db.get(normalized_username)
    if not student:
        raise HTTPException(status_code=404, detail="账号不存在")
    question = main._normalize_security_question(student.security_question or "")
    answer_hash = main._normalize_text(student.security_answer_hash or "")
    if not question or not answer_hash:
        raise HTTPException(status_code=400, detail="该账号未设置密保问题")
    if not main._verify_security_answer(answer_hash, security_answer):
        raise HTTPException(status_code=401, detail="密保答案错误")

    student.password_hash = main._hash_password(new_password)
    student.updated_at = main.datetime.now()
    main._save_user_registry()
    main._append_operation_log(
        operator=normalized_username,
        action="students.reset_password_with_security",
        target=normalized_username,
        detail="学生通过密保重置密码",
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
