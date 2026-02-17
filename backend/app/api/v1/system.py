from datetime import datetime

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from ...db.session import is_postgres_ready, storage_backend_name
from ...state import (
    attachments_db,
    classes_db,
    courses_db,
    experiments_db,
    operation_logs_db,
    resource_files_db,
    resource_policy_db,
    students_db,
)

router = APIRouter()


@router.get("/")
def root():
    return {"message": "福州理工学院AI编程实践教学平台 API", "version": "1.0.0"}


@router.get("/api/health")
def api_health():
    return {
        "status": "ok",
        "service": "experiment-manager",
        "storage_backend": storage_backend_name(),
        "postgres_ready": is_postgres_ready(),
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/metrics", response_class=PlainTextResponse)
def metrics():
    lines = [
        "# HELP training_backend_up Backend process up status (1=up).",
        "# TYPE training_backend_up gauge",
        "training_backend_up 1",
        "# HELP training_backend_students_total Total students loaded in memory.",
        "# TYPE training_backend_students_total gauge",
        f"training_backend_students_total {len(students_db)}",
        "# HELP training_backend_classes_total Total classes loaded in memory.",
        "# TYPE training_backend_classes_total gauge",
        f"training_backend_classes_total {len(classes_db)}",
        "# HELP training_backend_courses_total Total courses loaded in memory.",
        "# TYPE training_backend_courses_total gauge",
        f"training_backend_courses_total {len(courses_db)}",
        "# HELP training_backend_experiments_total Total experiments loaded in memory.",
        "# TYPE training_backend_experiments_total gauge",
        f"training_backend_experiments_total {len(experiments_db)}",
        "# HELP training_backend_attachments_total Total attachments loaded in memory.",
        "# TYPE training_backend_attachments_total gauge",
        f"training_backend_attachments_total {len(attachments_db)}",
        "# HELP training_backend_resources_total Total uploaded resources loaded in memory.",
        "# TYPE training_backend_resources_total gauge",
        f"training_backend_resources_total {len(resource_files_db)}",
        "# HELP training_backend_resource_quota_overrides_total Total custom user resource overrides.",
        "# TYPE training_backend_resource_quota_overrides_total gauge",
        f"training_backend_resource_quota_overrides_total {len(resource_policy_db.get('overrides', {}))}",
        "# HELP training_backend_operation_logs_total Total operation logs retained.",
        "# TYPE training_backend_operation_logs_total gauge",
        f"training_backend_operation_logs_total {len(operation_logs_db)}",
    ]
    return "\n".join(lines) + "\n"
