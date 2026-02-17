import os
import re
from typing import Literal

StorageBackend = Literal["json", "postgres", "hybrid"]

_SCHEMA_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _parse_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _build_database_url() -> str:
    direct = (os.getenv("DATABASE_URL") or "").strip()
    if direct:
        return direct

    host = (os.getenv("POSTGRES_HOST") or "postgres").strip()
    port = (os.getenv("POSTGRES_PORT") or "5432").strip()
    user = (os.getenv("POSTGRES_USER") or "jupyterhub").strip()
    password = (os.getenv("POSTGRES_PASSWORD") or "").strip()
    dbname = (os.getenv("POSTGRES_DB") or "jupyterhub").strip()
    auth = f"{user}:{password}" if password else user
    return f"postgresql://{auth}@{host}:{port}/{dbname}"


def _normalize_backend(value: str) -> StorageBackend:
    normalized = str(value or "").strip().lower()
    if normalized in {"json", "postgres", "hybrid"}:
        return normalized  # type: ignore[return-value]
    return "json"


def _normalize_schema(value: str) -> str:
    schema = str(value or "public").strip() or "public"
    if not _SCHEMA_PATTERN.fullmatch(schema):
        return "public"
    return schema


STORAGE_BACKEND: StorageBackend = _normalize_backend(os.getenv("STORAGE_BACKEND", "postgres"))
DATABASE_URL: str = _build_database_url()
POSTGRES_SCHEMA: str = _normalize_schema(os.getenv("POSTGRES_SCHEMA", "public"))

# Migration/rollout switches
DOUBLE_WRITE_JSON: bool = _parse_bool("DOUBLE_WRITE_JSON", STORAGE_BACKEND == "hybrid")
PG_READ_PREFERRED: bool = _parse_bool("PG_READ_PREFERRED", STORAGE_BACKEND == "postgres")
AUTO_IMPORT_JSON_TO_PG: bool = _parse_bool("AUTO_IMPORT_JSON_TO_PG", False)


def use_postgres() -> bool:
    return STORAGE_BACKEND in {"postgres", "hybrid"}


def use_json_write() -> bool:
    return STORAGE_BACKEND == "json" or DOUBLE_WRITE_JSON or STORAGE_BACKEND == "hybrid"
