import argparse
import asyncio
import os
from dataclasses import dataclass

from sqlalchemy import select

from ..db.models import AttachmentORM, ResourceORM, SubmissionPdfORM
from ..db.session import close_db_engine, get_db, init_db_engine, init_db_schema
from ..file_storage import is_virtual_path


@dataclass
class MigrationStats:
    scanned: int = 0
    migrated: int = 0
    missing: int = 0
    empty: int = 0
    skipped_virtual: int = 0


async def _migrate_table(db, model, *, delete_source: bool) -> MigrationStats:
    stats = MigrationStats()
    result = await db.execute(select(model))
    rows = list(result.scalars().all())
    stats.scanned = len(rows)

    for row in rows:
        # Already migrated.
        if getattr(row, "file_data", None):
            continue

        file_path = str(getattr(row, "file_path", "") or "").strip()
        if not file_path:
            stats.missing += 1
            continue
        if is_virtual_path(file_path):
            stats.skipped_virtual += 1
            continue
        if not os.path.exists(file_path):
            stats.missing += 1
            continue

        try:
            with open(file_path, "rb") as file_obj:
                file_bytes = file_obj.read()
        except OSError:
            stats.missing += 1
            continue

        if not file_bytes:
            stats.empty += 1
            continue

        row.file_data = file_bytes
        row.size = len(file_bytes)
        stats.migrated += 1

        if delete_source:
            try:
                os.remove(file_path)
            except OSError:
                pass

    return stats


def _print_stats(title: str, stats: MigrationStats) -> None:
    print(
        f"{title}: scanned={stats.scanned}, migrated={stats.migrated}, "
        f"missing={stats.missing}, empty={stats.empty}, skipped_virtual={stats.skipped_virtual}"
    )


async def _run(delete_source: bool) -> int:
    ok = await init_db_engine(force=True)
    if not ok:
        print("migration: PostgreSQL init failed")
        return 2
    await init_db_schema()

    async for db in get_db():
        resource_stats = MigrationStats()
        attachment_stats = MigrationStats()
        submission_stats = MigrationStats()
        try:
            resource_stats = await _migrate_table(db, ResourceORM, delete_source=delete_source)
            attachment_stats = await _migrate_table(db, AttachmentORM, delete_source=delete_source)
            submission_stats = await _migrate_table(db, SubmissionPdfORM, delete_source=delete_source)
            await db.commit()
        except Exception as exc:
            await db.rollback()
            print(f"migration failed: {exc}")
            return 1
        finally:
            _print_stats("resources", resource_stats)
            _print_stats("attachments", attachment_stats)
            _print_stats("submission_pdfs", submission_stats)
        break

    await close_db_engine()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate legacy on-disk files into PostgreSQL BYTEA columns.")
    parser.add_argument(
        "--delete-source",
        action="store_true",
        help="Delete legacy source files from disk after successful blob migration.",
    )
    args = parser.parse_args()
    return asyncio.run(_run(delete_source=bool(args.delete_source)))


if __name__ == "__main__":
    raise SystemExit(main())
