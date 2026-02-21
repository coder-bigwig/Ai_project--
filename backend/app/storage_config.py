import os
import re
from typing import Literal

StorageBackend = Literal["postgres"]

_SCHEMA_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_FALSE_VALUES = {"0", "false", "no", "off", ""}


def _is_enabled(raw: str | None) -> bool:
    if raw is None:
        return False
    return str(raw).strip().lower() not in _FALSE_VALUES


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
    if normalized and normalized != "postgres":
        raise RuntimeError(
            f"Unsupported STORAGE_BACKEND={value!r}. Only 'postgres' is allowed; json/hybrid modes are removed."
        )
    return "postgres"


def _normalize_schema(value: str) -> str:
    schema = str(value or "experiment_manager").strip() or "experiment_manager"
    if not _SCHEMA_PATTERN.fullmatch(schema):
        raise RuntimeError(
            f"Invalid POSTGRES_SCHEMA={value!r}. Expected SQL identifier like 'experiment_manager'."
        )
    return schema


def _enforce_removed_legacy_switches() -> None:
    if _is_enabled(os.getenv("AUTO_IMPORT_JSON_TO_PG")):
        raise RuntimeError("AUTO_IMPORT_JSON_TO_PG is removed. Use offline migrate_json_to_pg script instead.")
    if _is_enabled(os.getenv("DOUBLE_WRITE_JSON")):
        raise RuntimeError("DOUBLE_WRITE_JSON is removed because JSON registry is no longer a runtime datastore.")


_enforce_removed_legacy_switches()
STORAGE_BACKEND: StorageBackend = _normalize_backend(os.getenv("STORAGE_BACKEND", "postgres"))
DATABASE_URL: str = _build_database_url()
POSTGRES_SCHEMA: str = _normalize_schema(os.getenv("POSTGRES_SCHEMA", "experiment_manager"))

# Kept as constants for backward-compatible imports in existing modules.
DOUBLE_WRITE_JSON: bool = False
PG_READ_PREFERRED: bool = True


def use_postgres() -> bool:
    return True


def use_json_write() -> bool:
    return False
