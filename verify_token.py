"""验证启动实验后返回的 jupyter_url 中包含 token。"""

from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request


API_BASE = "http://localhost:8001/api"


def request_json(url: str, method: str = "GET", body: dict | None = None):
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url=url, method=method, data=data, headers=headers)
    with urllib.request.urlopen(request, timeout=10) as response:
        raw = response.read().decode("utf-8", errors="replace")
        return json.loads(raw or "{}"), response.status


def pick_student_id() -> str:
    url = (
        f"{API_BASE}/admin/students?"
        "teacher_username=teacher_001&page=1&page_size=1"
    )
    payload, _ = request_json(url)
    items = payload.get("items") if isinstance(payload, dict) else None
    if isinstance(items, list) and items:
        student_id = str(items[0].get("student_id") or "").strip()
        if student_id:
            return student_id
    return "student001"


def main() -> int:
    experiments, _ = request_json(f"{API_BASE}/experiments")
    if not isinstance(experiments, list) or not experiments:
        print("No experiments found")
        return 1

    experiment_id = str(experiments[0].get("id") or "").strip()
    if not experiment_id:
        print("First experiment has invalid id")
        return 1

    student_id = pick_student_id()
    print(f"Testing experiment: {experiment_id}")
    print(f"Using student_id: {student_id}")

    url = (
        f"{API_BASE}/student-experiments/start/"
        f"{urllib.parse.quote(experiment_id)}?student_id={urllib.parse.quote(student_id)}"
    )
    payload, status = request_json(url, method="POST")
    print(f"HTTP status: {status}")
    print(f"Response: {json.dumps(payload, ensure_ascii=False)}")

    jupyter_url = str(payload.get("jupyter_url") or "")
    if "token=" in jupyter_url:
        print("SUCCESS: token found in jupyter_url")
        return 0

    print(f"FAILURE: token missing in {jupyter_url}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
