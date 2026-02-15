"""本地联调：检查教师端基础接口可用性（无需第三方依赖）。"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request


def request_json(url: str, timeout: int = 5):
    with urllib.request.urlopen(url, timeout=timeout) as response:
        raw = response.read().decode("utf-8", errors="replace")
        return json.loads(raw or "{}"), response.status


def request_status(url: str, timeout: int = 5) -> int:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return response.status


def main() -> int:
    api_base = "http://localhost:8001"
    frontend_base = "http://localhost:8080"
    teacher_username = "teacher_001"

    print("=" * 60)
    print("教师端访问路径检查")
    print("=" * 60)

    # 1) 前端可访问
    print("\n1. 检查前端服务...")
    try:
        status = request_status(frontend_base, timeout=3)
        print(f"   OK 前端可访问 (状态码: {status})")
    except Exception as exc:  # noqa: BLE001
        print(f"   FAIL 前端访问失败: {exc}")
        return 1

    # 2) 角色 API
    print("\n2. 检查角色 API...")
    role_url = f"{api_base}/api/check-role?username={urllib.parse.quote(teacher_username)}"
    try:
        payload, status = request_json(role_url)
        print(f"   状态码: {status}")
        print(f"   响应: {json.dumps(payload, ensure_ascii=False)}")
        if payload.get("role") != "teacher":
            print(f"   FAIL 角色不正确: {payload.get('role')}")
            return 1
        print("   OK 角色识别正常")
    except urllib.error.HTTPError as exc:
        print(f"   FAIL HTTP 错误: {exc.code} {exc.reason}")
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"   FAIL 请求失败: {exc}")
        return 1

    # 3) 教师课程 API
    print("\n3. 检查教师课程 API...")
    courses_url = (
        f"{api_base}/api/teacher/courses?"
        f"teacher_username={urllib.parse.quote(teacher_username)}"
    )
    try:
        payload, status = request_json(courses_url)
        courses = payload if isinstance(payload, list) else []
        print(f"   状态码: {status}")
        print(f"   课程数量: {len(courses)}")
        if len(courses) == 0:
            print("   WARN 当前无课程数据（API可用但数据为空）")
        else:
            print("   OK 课程 API 正常")
    except urllib.error.HTTPError as exc:
        print(f"   FAIL HTTP 错误: {exc.code} {exc.reason}")
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"   FAIL 请求失败: {exc}")
        return 1

    print("\n全部检查完成。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
