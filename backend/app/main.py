import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import APP_TITLE
from .state import *
from . import registry_store as _registry_store
from .integrations import jupyterhub_integration as _jupyterhub_integration
from .services import ai_service as _ai_service
from .db.session import close_db_engine, get_db, init_db_engine, init_db_schema, storage_backend_name
from .services.postgres_state_loader import load_state_from_postgres


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


@app.on_event("startup")
async def startup_event():
    """应用启动时加载数据。"""
    backend_mode = storage_backend_name()
    if backend_mode != "postgres":
        raise RuntimeError(f"Unsupported storage backend: {backend_mode!r}. Only 'postgres' is allowed.")

    pg_ok = await init_db_engine(force=True)
    if not pg_ok:
        raise RuntimeError("PostgreSQL initialization failed. Service exits without JSON fallback.")

    await init_db_schema()
    async for db in get_db():
        summary = await load_state_from_postgres(main_module=sys.modules[__name__], db=db)
        print(f"[storage] Loaded runtime cache from PostgreSQL: {summary}")
        break


@app.on_event("shutdown")
async def shutdown_event():
    await close_db_engine()


from .api.v1.router import router as api_v1_router

app.include_router(api_v1_router, prefix="")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
