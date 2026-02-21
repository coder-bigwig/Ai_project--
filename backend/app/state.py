"""Runtime in-memory caches.

These containers are not authoritative storage. Source of truth is PostgreSQL.
They may be rebuilt from PostgreSQL at startup and are kept only for fast local access.
"""

from typing import Dict, List

from .config import DEFAULT_AI_SHARED_CONFIG

experiments_db: Dict[str, object] = {}
courses_db: Dict[str, object] = {}
student_experiments_db: Dict[str, object] = {}
classes_db: Dict[str, object] = {}
teachers_db: Dict[str, object] = {}
students_db: Dict[str, object] = {}
teacher_account_password_hashes_db: Dict[str, str] = {}
account_security_questions_db: Dict[str, Dict[str, str]] = {}
submission_pdfs_db: Dict[str, object] = {}
resource_files_db: Dict[str, object] = {}
ai_shared_config_db: Dict[str, str] = dict(DEFAULT_AI_SHARED_CONFIG)
ai_chat_history_db: Dict[str, List[Dict[str, str]]] = {}
ai_session_tokens_db: Dict[str, Dict[str, object]] = {}
ai_web_search_cache_db: Dict[str, Dict[str, object]] = {}
resource_policy_db: Dict[str, dict] = {}
operation_logs_db: List[object] = []
attachments_db: Dict[str, object] = {}
