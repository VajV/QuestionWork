"""
backup_db.py — Point-in-time database backup via pg_dump.

Creates a compressed pg_dump, rotates old backups, records the job in
the ``backup_jobs`` table, and optionally posts a Slack summary.

Usage:
    python scripts/backup_db.py                    # full backup
    python scripts/backup_db.py --dry-run          # show what would be done
    python scripts/backup_db.py --dest /tmp/bkp    # override output directory

Environment:
    DATABASE_URL           (required)
    BACKUP_DIR             (default from settings, e.g. /var/backups/questionwork)
    BACKUP_RETENTION_DAYS  (default 7 — older dumps are deleted)
    SLACK_WEBHOOK_URL      (optional — success/failure posted to Slack)
    SENTRY_DSN             (optional — errors forwarded to Sentry)

Cron example (nightly at 02:00):
    0 2 * * * cd /app/backend && .venv/bin/python scripts/backup_db.py >> /var/log/backup.log 2>&1

Restore:
    pg_restore -Fc -d <target_db_url> <dump_file>
"""

import argparse
import asyncio
import glob
import logging
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse

# ── Path setup ────────────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.normpath(os.path.join(_HERE, ".."))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_BACKEND, ".env"))
except ImportError:
    pass

import asyncpg

from app.core.config import settings
from app.core.alerts import capture_exception, slack_error, slack_ok

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("backup_db")


def _parse_dsn(database_url: str) -> dict:
    """Parse a postgres:// URL into pg_dump-friendly env vars."""
    parsed = urlparse(database_url)
    env = os.environ.copy()
    if parsed.hostname:
        env["PGHOST"] = parsed.hostname
    if parsed.port:
        env["PGPORT"] = str(parsed.port)
    if parsed.username:
        env["PGUSER"] = parsed.username
    if parsed.password:
        env["PGPASSWORD"] = parsed.password
    dbname = (parsed.path or "").lstrip("/") or "questionwork"
    return env, dbname


def _rotate_old_backups(dest_dir: str, retention_days: int, dry_run: bool) -> int:
    """Delete backup files older than retention_days. Returns count deleted."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    pattern = os.path.join(dest_dir, "questionwork_*.dump")
    deleted = 0
    for path in glob.glob(pattern):
        mtime = datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc)
        if mtime < cutoff:
            logger.info(f"{'[DRY-RUN] Would delete' if dry_run else 'Deleting'} old backup: {path}")
            if not dry_run:
                os.remove(path)
            deleted += 1
    return deleted


async def _record_job(pool, job_id: str, status: str, path: str = None,
                      size_bytes: int = None, error: str = None,
                      started_at: datetime = None, finished_at: datetime = None) -> None:
    """Write / update a backup_jobs row."""
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO backup_jobs (id, started_at, finished_at, status, size_bytes, path, error)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (id) DO UPDATE
                  SET finished_at = EXCLUDED.finished_at,
                      status      = EXCLUDED.status,
                      size_bytes  = EXCLUDED.size_bytes,
                      path        = EXCLUDED.path,
                      error       = EXCLUDED.error
                """,
                job_id,
                started_at or datetime.now(timezone.utc),
                finished_at,
                status,
                size_bytes,
                path,
                error,
            )
    except Exception as exc:
        logger.warning(f"Could not record backup job in DB: {exc}")


async def run(*, dry_run: bool = False, dest_dir: str = None) -> bool:
    """
    Execute a full pg_dump backup.

    Returns True on success, False on failure.
    """
    dest_dir = dest_dir or settings.BACKUP_DIR
    retention_days = settings.BACKUP_RETENTION_DAYS
    started_at = datetime.now(timezone.utc)
    job_id = f"bkp_{started_at.strftime('%Y%m%dT%H%M%S')}"

    logger.info(
        f"Backup starting — dest={dest_dir}, retention={retention_days}d, dry_run={dry_run}"
    )

    if not dry_run:
        os.makedirs(dest_dir, exist_ok=True)

    filename = f"questionwork_{started_at.strftime('%Y%m%dT%H%M%S')}.dump"
    dest_path = os.path.join(dest_dir, filename)

    pool = None
    try:
        pool = await asyncpg.create_pool(settings.DATABASE_URL, min_size=1, max_size=1)
        await _record_job(pool, job_id, "running", started_at=started_at)

        env, dbname = _parse_dsn(settings.DATABASE_URL)

        if dry_run:
            logger.info(f"[DRY-RUN] Would run pg_dump -Fc -f {dest_path} {dbname}")
            await _record_job(
                pool, job_id, "ok", path=dest_path + " (dry-run)",
                started_at=started_at, finished_at=datetime.now(timezone.utc)
            )
            slack_ok("Backup DRY-RUN OK", f"Would write: {dest_path}")
            return True

        logger.info(f"Running pg_dump → {dest_path}")
        result = subprocess.run(
            ["pg_dump", "-Fc", "-f", dest_path, dbname],
            env=env,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            err = result.stderr.strip()
            logger.error(f"pg_dump failed (rc={result.returncode}): {err}")
            await _record_job(
                pool, job_id, "error", error=err,
                started_at=started_at, finished_at=datetime.now(timezone.utc)
            )
            slack_error("Database Backup FAILED", err)
            return False

        size_bytes = os.path.getsize(dest_path)
        finished_at = datetime.now(timezone.utc)
        duration = (finished_at - started_at).total_seconds()
        logger.info(
            f"Backup complete: {dest_path} "
            f"({size_bytes / 1024 / 1024:.1f} MB, {duration:.1f}s)"
        )

        await _record_job(
            pool, job_id, "ok", path=dest_path, size_bytes=size_bytes,
            started_at=started_at, finished_at=finished_at
        )

        # ── Rotate old backups ─────────────────────────────────────────
        deleted = _rotate_old_backups(dest_dir, retention_days, dry_run=False)
        if deleted:
            logger.info(f"Rotated {deleted} old backup(s) (>{retention_days}d)")

        slack_ok(
            title="Database Backup OK",
            detail=(
                f"`{filename}` — {size_bytes / 1024 / 1024:.1f} MB in {duration:.0f}s. "
                f"Rotated {deleted} old file(s)."
            ),
        )
        return True

    except Exception as exc:
        logger.error(f"Unexpected backup error: {exc}", exc_info=True)
        capture_exception(exc)
        if pool:
            await _record_job(
                pool, job_id, "error", error=str(exc),
                started_at=started_at, finished_at=datetime.now(timezone.utc)
            )
        slack_error("Database Backup FAILED", str(exc))
        return False

    finally:
        if pool:
            await pool.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a pg_dump backup of the QuestionWork DB.")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing files.")
    parser.add_argument(
        "--dest", metavar="DIR", default=None,
        help=f"Override backup destination directory (default: {settings.BACKUP_DIR})",
    )
    args = parser.parse_args()

    ok = asyncio.run(run(dry_run=args.dry_run, dest_dir=args.dest))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
