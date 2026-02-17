from datetime import datetime
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import APP_TITLE
from .state import *
from . import registry_store as _registry_store
from .integrations import jupyterhub_integration as _jupyterhub_integration
from .services import ai_service as _ai_service
from .db.session import close_db_engine, get_db, init_db_engine, init_db_schema, storage_backend_name
from .services.json_to_pg_migrator import has_any_core_data, migrate_from_upload_json
from .services.postgres_state_loader import load_state_from_postgres
from .storage_config import AUTO_IMPORT_JSON_TO_PG


def _export_module_symbols(module):
    for name in dir(module):
        if name.startswith("__"):
            continue
        globals().setdefault(name, getattr(module, name))


_export_module_symbols(_registry_store)
_export_module_symbols(_jupyterhub_integration)
_export_module_symbols(_ai_service)

app = FastAPI(title=APP_TITLE)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _load_json_registries(enable_seed: bool = True):
    _load_user_registry()
    print(f"Loaded user registry: {len(classes_db)} classes, {len(teachers_db)} managed teachers, {len(students_db)} students")
    _load_resource_registry()
    print(f"Loaded resource registry: {len(resource_files_db)} files")
    _load_experiment_registry()
    print(f"Loaded experiment registry: {len(experiments_db)} experiments")
    _load_course_registry()
    print(f"Loaded course registry: {len(courses_db)} courses")
    _load_attachment_registry()
    print(f"Loaded attachment registry: {len(attachments_db)} attachments")
    _load_submission_registry()
    print(f"Loaded submission registry: {len(student_experiments_db)} submissions")
    _load_submission_pdf_registry()
    print(f"Loaded submission pdf registry: {len(submission_pdfs_db)} pdfs")
    _load_ai_shared_config()
    print("Loaded ai shared config")
    _load_ai_chat_history()
    print(f"Loaded ai chat history users: {len(ai_chat_history_db)}")
    _load_resource_policy()
    print("Loaded resource policy")
    _load_operation_logs()
    print(f"Loaded operation logs: {len(operation_logs_db)}")
    _sync_courses_from_experiments()

    if not enable_seed:
        return

    seed_version, _ = _read_seed_marker()
    if seed_version == 0:
        _ensure_default_experiments()
        _ensure_default_attachments()
        try:
            _write_seed_marker(2, {"seeded_at": datetime.now().isoformat()})
        except OSError as exc:
            print(f"Failed to write seed marker: {exc}")
    elif seed_version == 1:
        try:
            if _cleanup_seeded_attachments():
                print("[seed] Cleaned duplicate seeded attachments")
            _write_seed_marker(2, {"migrated_from": 1, "migrated_at": datetime.now().isoformat()})
        except OSError as exc:
            print(f"Failed to write seed marker: {exc}")


@app.on_event("startup")
async def startup_event():
    """应用启动时加载数据。"""
    backend_mode = storage_backend_name()

    if backend_mode in {"json", "hybrid"}:
        _load_json_registries(enable_seed=True)

    pg_ok = await init_db_engine(force=False)
    if pg_ok:
        await init_db_schema()
        async for db in get_db():
            if db is None:
                break

            if AUTO_IMPORT_JSON_TO_PG:
                should_import = backend_mode == "hybrid"
                if backend_mode == "postgres":
                    should_import = not await has_any_core_data(db)
                if should_import:
                    summary = await migrate_from_upload_json(db=db)
                    await db.commit()
                    print(f"[storage] JSON -> PostgreSQL import summary: {summary}")

            if backend_mode == "postgres":
                summary = await load_state_from_postgres(main_module=sys.modules[__name__], db=db)
                print(f"[storage] Loaded runtime state from PostgreSQL: {summary}")
            break
    elif backend_mode == "postgres":
        print("[storage] PostgreSQL backend requested but DB init failed, fallback to JSON registry load")
        _load_json_registries(enable_seed=False)


@app.on_event("shutdown")
async def shutdown_event():
    await close_db_engine()


from .api.v1.router import router as api_v1_router

app.include_router(api_v1_router, prefix="")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
