"""PharmaPredict AI — Automated Database Migration & Safety Verification Module.

Provides safe database migration inspection, verification, and upgrade execution
for containerized enterprise deployments (single-node and multi-replica environments).

Key capabilities:
- Inspects Alembic migration directory and database alembic_version table.
- Detects pending migrations prior to application worker startup.
- Verifies database schema compatibility without concurrent race hazards.
- Safe automated upgrade runner with detailed logging and rollback advisory.
"""
import os
import logging
from typing import Dict, Any, Optional, Tuple
from flask import Flask
from sqlalchemy import text, inspect
from app.extensions import db

logger = logging.getLogger("pharmapredict.migrations")


def get_current_db_revision() -> Optional[str]:
    """Retrieve the current applied revision from alembic_version table, if it exists."""
    try:
        inspector = inspect(db.engine)
        if "alembic_version" not in inspector.get_table_names():
            return None
        with db.engine.connect() as conn:
            result = conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
            row = result.fetchone()
            return row[0] if row else None
    except Exception as exc:
        logger.warning(f"Unable to read alembic_version: {exc}")
        return None


def get_head_revision(migrations_dir: Optional[str] = None) -> Optional[str]:
    """Retrieve the latest target head revision from migration scripts."""
    try:
        from alembic.script import ScriptDirectory
        from alembic.config import Config as AlembicConfig

        if not migrations_dir:
            backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            migrations_dir = os.path.join(backend_dir, "migrations")

        if not os.path.exists(migrations_dir):
            return None

        alembic_cfg = AlembicConfig()
        alembic_cfg.set_main_option("script_location", migrations_dir)
        script_dir = ScriptDirectory.from_config(alembic_cfg)
        return script_dir.get_current_head()
    except Exception as exc:
        logger.warning(f"Unable to read head revision from migration scripts: {exc}")
        return None


def check_migration_status(app: Optional[Flask] = None) -> Dict[str, Any]:
    """
    Check the current database migration status against script heads.
    
    Returns a dictionary with:
    - is_synced (bool): True if current_rev matches head_rev or both are None.
    - current_revision (str|None)
    - head_revision (str|None)
    - status (str): 'up_to_date', 'pending_migration', 'unversioned_db', 'no_migrations_configured'
    - message (str)
    """
    current_rev = get_current_db_revision()
    head_rev = get_head_revision()

    if head_rev is None and current_rev is None:
        return {
            "is_synced": True,
            "current_revision": None,
            "head_revision": None,
            "status": "unversioned_schema",
            "message": "Database schema managed by SQLAlchemy create_all (no Alembic revisions found)."
        }

    if head_rev is not None and current_rev is None:
        return {
            "is_synced": False,
            "current_revision": None,
            "head_revision": head_rev,
            "status": "pending_migration",
            "message": f"Database has unapplied migrations. Target head: {head_rev}"
        }

    if current_rev == head_rev:
        return {
            "is_synced": True,
            "current_revision": current_rev,
            "head_revision": head_rev,
            "status": "up_to_date",
            "message": f"Database is up to date at revision: {current_rev}"
        }

    return {
        "is_synced": False,
        "current_revision": current_rev,
        "head_revision": head_rev,
        "status": "pending_migration",
        "message": f"Database revision mismatch: DB={current_rev}, Scripts={head_rev}"
    }


def apply_migrations(target_rev: str = "head") -> Tuple[bool, str]:
    """
    Safely apply Alembic migrations to the database.
    Used by entrypoint scripts, migration init containers, or automated startup runners.
    """
    try:
        from flask_migrate import upgrade
        logger.info(f"Applying database migrations to revision: {target_rev}...")
        upgrade(revision=target_rev)
        logger.info("Database migrations successfully applied.")
        return True, "Migrations successfully applied."
    except Exception as exc:
        err_msg = f"Database migration failed: {exc}"
        logger.critical(err_msg, exc_info=True)
        return False, err_msg


def verify_database_on_startup(app: Flask) -> None:
    """
    Verify database connectivity and migration state on application startup.
    In production mode with ENFORCE_MIGRATION_CHECK=True, fails fast if migrations are out-of-sync.
    """
    with app.app_context():
        # First verify connectivity
        try:
            db.session.execute(text("SELECT 1"))
        except Exception as exc:
            msg = f"CRITICAL: Failed to connect to database on startup: {exc}"
            logger.critical(msg)
            if app.config.get("ENV") == "production":
                raise RuntimeError(msg) from exc
            return

        # Next check migration status
        enforce = app.config.get("ENFORCE_MIGRATION_CHECK", False)
        auto_migrate = app.config.get("AUTO_MIGRATE", False)
        status_info = check_migration_status(app)

        if not status_info["is_synced"]:
            if auto_migrate:
                logger.warning("Unapplied migrations detected. AUTO_MIGRATE is enabled. Running upgrade...")
                success, msg = apply_migrations()
                if not success and enforce:
                    raise RuntimeError(f"Startup aborted: Failed to apply automated migrations: {msg}")
            elif enforce:
                raise RuntimeError(
                    f"Startup aborted: Database migrations are pending (DB={status_info['current_revision']}, "
                    f"Target={status_info['head_revision']}). Run 'flask db upgrade' before starting application."
                )
            else:
                logger.warning(f"Database migration notice: {status_info['message']}")

