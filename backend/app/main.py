import asyncio
from contextlib import suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import registry_store as _registry_store
from .config import (
    APP_TITLE,
    COURSE_MEMBERSHIP_RECONCILE_ENABLED,
    COURSE_MEMBERSHIP_RECONCILE_INTERVAL_SECONDS,
    COURSE_MEMBERSHIP_RECONCILE_STARTUP_DELAY_SECONDS,
)
from .db.session import close_db_engine, get_db, init_db_engine, init_db_schema, storage_backend_name
from .integrations import jupyterhub_integration as _jupyterhub_integration
from .services import ai_service as _ai_service
from .services.bootstrap_service import ensure_builtin_accounts
from .services.membership_consistency_service import reconcile_membership_consistency
from .state import assert_legacy_state_write_blocked


def _export_module_symbols(
    module,
    *,
    deny_prefixes: tuple[str, ...] = (),
    deny_suffixes: tuple[str, ...] = (),
    deny_names: set[str] | None = None,
):
    deny_names = deny_names or set()
    for name in dir(module):
        if name.startswith("__"):
            continue
        if name in deny_names:
            continue
        if deny_prefixes and any(name.startswith(prefix) for prefix in deny_prefixes):
            continue
        if deny_suffixes and any(name.endswith(suffix) for suffix in deny_suffixes):
            continue
        globals().setdefault(name, getattr(module, name))


_export_module_symbols(
    _registry_store,
    deny_prefixes=("_load_", "_save_"),
    deny_suffixes=("_db",),
)
_export_module_symbols(
    _jupyterhub_integration,
    deny_suffixes=("_db",),
)
_export_module_symbols(
    _ai_service,
    deny_prefixes=("_load_", "_save_"),
    deny_suffixes=("_db",),
)

app = FastAPI(title=APP_TITLE)
_membership_reconcile_task: asyncio.Task | None = None

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def _run_membership_reconcile_once() -> dict[str, int]:
    async for db in get_db():
        stats = await reconcile_membership_consistency(db)
        if stats.get("changed_total", 0) > 0:
            await db.commit()
            print(
                "[membership-sync] repaired "
                f"offering_members(created={stats.get('created_offering_members', 0)}, "
                f"updated={stats.get('updated_offering_members', 0)}), "
                f"course_memberships(created={stats.get('created_course_memberships', 0)}, "
                f"updated={stats.get('updated_course_memberships', 0)})"
            )
        else:
            await db.rollback()
        return stats
    return {"changed_total": 0}


async def _membership_reconcile_worker() -> None:
    if COURSE_MEMBERSHIP_RECONCILE_STARTUP_DELAY_SECONDS > 0:
        await asyncio.sleep(COURSE_MEMBERSHIP_RECONCILE_STARTUP_DELAY_SECONDS)
    while True:
        try:
            await _run_membership_reconcile_once()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f"[membership-sync] reconcile failed: {exc}")
        await asyncio.sleep(COURSE_MEMBERSHIP_RECONCILE_INTERVAL_SECONDS)


@app.on_event("startup")
async def startup_event():
    """应用启动时仅初始化数据库连接和表结构。"""
    assert_legacy_state_write_blocked()
    backend_mode = storage_backend_name()
    if backend_mode != "postgres":
        raise RuntimeError(f"Unsupported storage backend: {backend_mode!r}. Only 'postgres' is allowed.")

    pg_ok = await init_db_engine(force=True)
    if not pg_ok:
        raise RuntimeError("PostgreSQL initialization failed. Service exits without JSON fallback.")

    await init_db_schema()

    async for db in get_db():
        result = await ensure_builtin_accounts(db, password_hasher=_hash_password)
        if result.get("created_auth_accounts") or result.get("created_teacher_profiles"):
            print(
                "[bootstrap] ensured builtin accounts: "
                f"auth_created={result.get('created_auth_accounts', 0)}, "
                f"teacher_profiles_created={result.get('created_teacher_profiles', 0)}"
            )
        break

    global _membership_reconcile_task
    if COURSE_MEMBERSHIP_RECONCILE_ENABLED and _membership_reconcile_task is None:
        _membership_reconcile_task = asyncio.create_task(_membership_reconcile_worker())
        print(
            "[membership-sync] background reconcile enabled "
            f"(interval={COURSE_MEMBERSHIP_RECONCILE_INTERVAL_SECONDS}s, "
            f"startup_delay={COURSE_MEMBERSHIP_RECONCILE_STARTUP_DELAY_SECONDS}s)"
        )


@app.on_event("shutdown")
async def shutdown_event():
    global _membership_reconcile_task
    if _membership_reconcile_task is not None:
        _membership_reconcile_task.cancel()
        with suppress(asyncio.CancelledError):
            await _membership_reconcile_task
        _membership_reconcile_task = None
    await close_db_engine()


from .api.v1.router import router as api_v1_router

app.include_router(api_v1_router, prefix="")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
