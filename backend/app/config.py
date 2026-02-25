from typing import List
import os
import re

APP_TITLE = "缂備礁鍊哥换鎰玻閻愮儤鍋犻柛鈩冦仦缁憋綁鎮楀☉宕囩暤婵炲懎鐡慖缂傚倸鍊归悧婊堝煝閼测斁鍋撻崷顓炰哗閺夆晜妫冨顐⑩枎韫囷絽濡冲Δ鐘靛仜閸熻儻銇?- 闁诲骸婀遍崑銈夋偘濞嗘垹涓嶉柨娑樺閸婃咖PI"

JUPYTERHUB_INTERNAL_URL = os.getenv("JUPYTERHUB_INTERNAL_URL", "http://jupyterhub:8000").rstrip("/")
# Prefer same-origin reverse-proxy path to avoid cross-origin cookie/WebSocket auth mismatches.
JUPYTERHUB_PUBLIC_URL = os.getenv("JUPYTERHUB_PUBLIC_URL", "/jupyter").rstrip("/")
JUPYTERHUB_API_TOKEN = os.getenv("JUPYTERHUB_API_TOKEN", "").strip()
JUPYTERHUB_REQUEST_TIMEOUT_SECONDS = float(os.getenv("JUPYTERHUB_REQUEST_TIMEOUT_SECONDS", "10"))
JUPYTERHUB_START_TIMEOUT_SECONDS = float(os.getenv("JUPYTERHUB_START_TIMEOUT_SECONDS", "60"))
# Keep user browser sessions stable for long classes.
JUPYTERHUB_USER_TOKEN_EXPIRES_SECONDS = int(os.getenv("JUPYTERHUB_USER_TOKEN_EXPIRES_SECONDS", "43200"))
JUPYTER_WORKSPACE_UI = str(os.getenv("JUPYTER_WORKSPACE_UI", "lab") or "").strip().lower()
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "").strip()

def _parse_account_list(raw: str) -> List[str]:
    parts = [item.strip() for item in str(raw or "").split(",")]
    return [item for item in parts if item]


def _env_flag(name: str, default: str = "1") -> bool:
    value = str(os.getenv(name, default) or "").strip().lower()
    return value not in {"0", "false", "no", "off"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(str(os.getenv(name, str(default)) or "").strip())
    except (TypeError, ValueError):
        return default
TEACHER_ACCOUNTS = _parse_account_list(
    os.getenv("TEACHER_ACCOUNTS", "teacher_001,teacher_002,teacher_003,teacher_004,teacher_005")
)
ADMIN_ACCOUNTS = _parse_account_list(os.getenv("ADMIN_ACCOUNTS", "admin"))
DEFAULT_PASSWORD = "123456"
UPLOAD_DIR = "/app/uploads"
SEED_MARKER_FILE = os.path.join(UPLOAD_DIR, ".seed_defaults_v1")  # legacy filename (kept for backward compat)
TEXT_PREVIEW_CHAR_LIMIT = 20000
ALLOWED_RESOURCE_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
    ".md",
    ".markdown",
    ".txt",
    ".csv",
    ".json",
    ".ppt",
    ".pptx",
    ".xls",
    ".xlsx",
}
TEMPLATE_HEADERS = ["\u5b66\u53f7", "\u59d3\u540d", "\u73ed\u7ea7", "\u5355\u4f4d\u540d\u79f0", "\u5165\u5b66\u5e74\u7ea7"]
LEGACY_TEMPLATE_HEADERS = ["\u5b66\u53f7", "\u59d3\u540d", "\u73ed\u7ea7", "\u5355\u4f4d\u540d\u79f0", "\u624b\u673a\u53f7"]
DEFAULT_ADMISSION_YEAR_OPTIONS = ["2020", "2021", "2022", "2023", "2024", "2025", "2026", "2027", "2028"]
CLASS_TEMPLATE_HEADERS = ["\u5165\u5b66\u5e74\u7ea7", "\u4e13\u4e1a", "\u73ed\u7ea7"]
DEFAULT_AI_SHARED_CONFIG = {
    "api_key": "",
    "tavily_api_key": "",
    "chat_model": "deepseek-chat",
    "reasoner_model": "deepseek-reasoner",
    "base_url": "https://api.deepseek.com",
    "system_prompt": "\u4f60\u662f\u798f\u5dde\u7406\u5de5\u5b66\u9662AI\u7f16\u7a0b\u5b9e\u8df5\u6559\u5b66\u5e73\u53f0\u5c0f\u52a9\u624b\u3002\u8bf7\u4f7f\u7528\u7b80\u6d01\u3001\u51c6\u786e\u3001\u6559\u5b66\u53cb\u597d\u7684\u4e2d\u6587\u56de\u7b54\u3002",
}
AI_RESPONSE_STYLE_RULES = (
    "\u56de\u7b54\u89c4\u5219\uff1a\u5148\u7ed9\u7ed3\u8bba\uff0c\u518d\u7ed9\u5173\u952e\u4f9d\u636e\u6216\u6b65\u9aa4\uff1b"
    "\u4ee3\u7801\u95ee\u9898\u4f18\u5148\u7ed9\u6700\u5c0f\u53ef\u8fd0\u884c\u793a\u4f8b\uff1b"
    "\u907f\u514d\u7a7a\u8bdd\u548c\u5957\u8bdd\uff0c\u4e0d\u8981\u7f16\u9020\u4e8b\u5b9e\uff1b"
    "\u4e0d\u786e\u5b9a\u65f6\u660e\u786e\u5199\u201c\u6211\u4e0d\u786e\u5b9a\uff0c\u9700\u8981\u8fdb\u4e00\u6b65\u68c0\u7d22\u786e\u8ba4\u201d\u3002"
)
DEFAULT_RESOURCE_ROLE_LIMITS = {
    "student": {"cpu_limit": 2.0, "memory_limit": "8G", "storage_limit": "2G"},
    "teacher": {"cpu_limit": 2.0, "memory_limit": "8G", "storage_limit": "2G"},
    "admin": {"cpu_limit": 4.0, "memory_limit": "8G", "storage_limit": "20G"},
}
DEFAULT_SERVER_RESOURCE_BUDGET = {
    "max_total_cpu": 64.0,
    "max_total_memory": "128G",
    "max_total_storage": "1T",
    "enforce_budget": False,
}
MAX_OPERATION_LOG_ITEMS = 5000
AI_CHAT_HISTORY_MAX_MESSAGES = max(20, int(os.getenv("AI_CHAT_HISTORY_MAX_MESSAGES", "240")))
AI_CHAT_HISTORY_MAX_MESSAGE_CHARS = max(1000, int(os.getenv("AI_CHAT_HISTORY_MAX_MESSAGE_CHARS", "12000")))
AI_CONTEXT_MAX_HISTORY_MESSAGES = max(10, int(os.getenv("AI_CONTEXT_MAX_HISTORY_MESSAGES", "80")))
AI_CONTEXT_MAX_TOTAL_CHARS = max(4000, int(os.getenv("AI_CONTEXT_MAX_TOTAL_CHARS", "48000")))
AI_SESSION_TTL_SECONDS = max(900, int(os.getenv("AI_SESSION_TTL_SECONDS", "43200")))
AI_SESSION_MAX_TOKENS = max(100, int(os.getenv("AI_SESSION_MAX_TOKENS", "5000")))
AI_WEB_SEARCH_CACHE_TTL_SECONDS = max(60, int(os.getenv("AI_WEB_SEARCH_CACHE_TTL_SECONDS", "3600")))
AI_WEB_SEARCH_CACHE_MAX_ITEMS = max(50, int(os.getenv("AI_WEB_SEARCH_CACHE_MAX_ITEMS", "1000")))
PASSWORD_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
COURSE_MEMBERSHIP_RECONCILE_ENABLED = _env_flag("COURSE_MEMBERSHIP_RECONCILE_ENABLED", "1")
COURSE_MEMBERSHIP_RECONCILE_INTERVAL_SECONDS = max(
    60,
    _env_int("COURSE_MEMBERSHIP_RECONCILE_INTERVAL_SECONDS", 300),
)
COURSE_MEMBERSHIP_RECONCILE_STARTUP_DELAY_SECONDS = max(
    0,
    _env_int("COURSE_MEMBERSHIP_RECONCILE_STARTUP_DELAY_SECONDS", 30),
)

os.makedirs(UPLOAD_DIR, exist_ok=True)
