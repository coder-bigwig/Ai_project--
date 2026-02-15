"""本地联调：检查教师/学生角色识别与教师课程拉取（无需第三方依赖）。"""

from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request


API_BASE = "http://localhost:8001"


def request_json(path: str):
    url = f"{API_BASE}{path}"
    with urllib.request.urlopen(url, timeout=8) as response:
        raw = response.read().decode("utf-8", errors="replace")
        return json.loads(raw or "{}"), response.status


def check_role(username: str, expected_role: str) -> bool:
    payload, status = request_json(
        f"/api/check-role?username={urllib.parse.quote(username)}"
    )
    actual = payload.get("role")
    print(f"   用户 {username} -> 状态码 {status}, role={actual}")
    return actual == expected_role


def main() -> int:
    print("=" * 50)
    print("教师登录流程相关接口检查")
    print("=" * 50)

    ok = True

    print("\n1. 检查教师角色识别...")
    teacher_ok = check_role("teacher_001", "teacher")
    print("   OK" if teacher_ok else "   FAIL")
    ok = ok and teacher_ok

    print("\n2. 检查教师课程列表...")
    courses, status = request_json(
        "/api/teacher/courses?teacher_username=teacher_001"
    )
    course_count = len(courses) if isinstance(courses, list) else 0
    print(f"   状态码 {status}, 课程数量 {course_count}")
    if not isinstance(courses, list):
        print("   FAIL 返回结构异常")
        ok = False
    else:
        print("   OK")

    print("\n3. 检查学生角色识别...")
    student_ok = check_role("student_001", "student")
    print("   OK" if student_ok else "   FAIL")
    ok = ok and student_ok

    print("\n" + "=" * 50)
    print("检查结束")
    print("=" * 50)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
