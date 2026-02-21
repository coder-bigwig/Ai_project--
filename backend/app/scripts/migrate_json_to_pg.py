import argparse
import asyncio
import json
import sys

from ..db.session import close_db_engine, get_db, init_db_engine, init_db_schema
from ..services.json_to_pg_migrator import has_any_core_data, migrate_from_upload_json


async def _run(uploads_dir: str | None, force: bool) -> int:
    ok = await init_db_engine(force=True)
    if not ok:
        print("PostgreSQL engine init failed: missing DATABASE_URL or invalid config", file=sys.stderr)
        return 2

    await init_db_schema()

    async for db in get_db():
        if db is None:
            print("PostgreSQL session unavailable", file=sys.stderr)
            return 2

        if (not force) and await has_any_core_data(db):
            print("Skip migration: PostgreSQL already has core data. Use --force to upsert anyway.")
            return 0

        summary = await migrate_from_upload_json(db=db, uploads_dir=uploads_dir)
        await db.commit()
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Offline one-time import: /app/uploads/*.json registry data into PostgreSQL "
            "(idempotent upsert). Not executed during app startup."
        )
    )
    parser.add_argument(
        "--uploads-dir",
        default=None,
        help="Override uploads directory (default: use paths from app.config, usually /app/uploads).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Run upsert even when PostgreSQL already contains core data.",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    try:
        return asyncio.run(_run(uploads_dir=args.uploads_dir, force=args.force))
    finally:
        try:
            asyncio.run(close_db_engine())
        except RuntimeError:
            # Event loop already closed; safe to ignore.
            pass


if __name__ == "__main__":
    raise SystemExit(main())
