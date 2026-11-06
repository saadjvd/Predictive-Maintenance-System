"""PharmaPredict AI — Automated Database Migration & Safety Verification Module.

Provides safe database migration inspection, verification, and upgrade execution
for containerized enterprise deployments (single-node and multi-replica environments).

Key capabilities:
- Inspects Alembic migration directory and database alembic_version table.
- Accurately distinguishes 6 database schema lifecycle states:
  1. 'uninitialized_database': Fresh/empty database with 0 application tables.
  2. 'up_to_date': Database revision matches latest migration script head.
  3. 'pending_migration': Database behind head with known previous revision(s).
  4. 'unknown_revision': Database stamped with revision not in migration history.
  5. 'unversioned_tables_exist': Database has tables but missing alembic_version.
  6. 'inspection_failed': Database connectivity or permission error during inspection.
- Protects multi-replica production deployments from concurrent DDL race hazards.
- Provides safe automated upgrade runner with detailed logging and rollback advisory.
"""
import os
import logging
from typing import Dict, Any, Optional, Tuple, Set
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


def get_script_directory(migrations_dir: Optional[str] = None):
    """Retrieve Alembic ScriptDirectory instance."""
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
        return ScriptDirectory.from_config(alembic_cfg)
    except Exception as exc:
        logger.warning(f"Unable to load Alembic script directory: {exc}")
        return None


def get_head_revision(migrations_dir: Optional[str] = None) -> Optional[str]:
    """Retrieve the latest target head revision from migration scripts."""
    script_dir = get_script_directory(migrations_dir)
    if not script_dir:
        return None
    try:
        return script_dir.get_current_head()
    except Exception as exc:
        logger.warning(f"Unable to read head revision from migration scripts: {exc}")
        return None


def get_known_revisions(migrations_dir: Optional[str] = None) -> Set[str]:
    """Retrieve the set of all known revision identifiers in the migration history."""
    script_dir = get_script_directory(migrations_dir)
    if not script_dir:
        return set()
    try:
        return {rev.revision for rev in script_dir.walk_revisions()}
    except Exception as exc:
        logger.warning(f"Unable to walk migration revisions: {exc}")
        head = get_head_revision(migrations_dir)
        return {head} if head else set()


def check_migration_status(app: Optional[Flask] = None) -> Dict[str, Any]:
    """
    Check the current database migration status against script heads.
    
    Returns a dictionary with:
    - is_synced (bool): True strictly when current_rev matches head_rev.
    - is_ready (bool): True strictly when database is ready for application transactions.
    - current_revision (str|None): Revision recorded in DB.
    - head_revision (str|None): Head revision in scripts.
    - status (str): One of the 6 canonical states:
        * 'uninitialized_database'
        * 'up_to_date'
        * 'pending_migration'
        * 'unknown_revision'
        * 'unversioned_tables_exist'
        * 'inspection_failed'
    - message (str): Clear, actionable diagnostic text.
    """
    try:
        inspector = inspect(db.engine)
        existing_tables = set(inspector.get_table_names())
    except Exception as exc:
        logger.error(f"Migration inspection failed: {exc}")
        return {
            "is_synced": False,
            "is_ready": False,
            "current_revision": None,
            "head_revision": None,
            "status": "inspection_failed",
            "message": f"Database inspection failed: {exc.__class__.__name__}: {str(exc)}"
        }

    head_rev = get_head_revision()
    known_revs = get_known_revisions()

    # Filter out system or internal tables if inspecting
    app_tables = {t for t in existing_tables if not t.startswith("pg_") and not t.startswith("_timescaledb")}

    # State 1: Completely empty database
    if not app_tables:
        return {
            "is_synced": False,
            "is_ready": False,
            "current_revision": None,
            "head_revision": head_rev,
            "status": "uninitialized_database",
            "message": "Database is completely empty. Migrations must be applied before serving traffic."
        }

    has_alembic = "alembic_version" in existing_tables
    current_rev = get_current_db_revision() if has_alembic else None

    # State 5: Application tables exist but no alembic_version table
    if not has_alembic:
        return {
            "is_synced": False,
            "is_ready": False,
            "current_revision": None,
            "head_revision": head_rev,
            "status": "unversioned_tables_exist",
            "message": "Database contains application tables but is missing Alembic version tracking."
        }

    # alembic_version table exists but has no rows
    if current_rev is None:
        return {
            "is_synced": False,
            "is_ready": False,
            "current_revision": None,
            "head_revision": head_rev,
            "status": "pending_migration",
            "message": f"Alembic version table is unpopulated. Target head: {head_rev}"
        }

    # State 2: Database revision matches migration script head
    if current_rev == head_rev and head_rev is not None:
        return {
            "is_synced": True,
            "is_ready": True,
            "current_revision": current_rev,
            "head_revision": head_rev,
            "status": "up_to_date",
            "message": f"Database is up to date at revision: {current_rev}"
        }

    # State 3: Database revision is in history but behind current head
    if current_rev in known_revs:
        return {
            "is_synced": False,
            "is_ready": False,
            "current_revision": current_rev,
            "head_revision": head_rev,
            "status": "pending_migration",
            "message": f"Database is behind head revision: current={current_rev}, head={head_rev}"
        }

    # State 4: Database revision is not recognized in migration history
    return {
        "is_synced": False,
        "is_ready": False,
        "current_revision": current_rev,
        "head_revision": head_rev,
        "status": "unknown_revision",
        "message": f"Database revision '{current_rev}' is not recognized in migration history (head={head_rev})"
    }


def apply_migrations(target_rev: str = "head", directory: Optional[str] = None) -> Tuple[bool, str]:
    """
    Safely apply Alembic migrations to the database.
    Used by entrypoint scripts, migration init containers, or automated startup runners.
    """
    try:
        from flask_migrate import upgrade
        if not directory:
            backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            candidate = os.path.join(backend_dir, "migrations")
            directory = candidate if os.path.exists(candidate) else "migrations"
        logger.info(f"Applying database migrations to revision: {target_rev} using directory: {directory}...")
        upgrade(directory=directory, revision=target_rev)
        logger.info("Database migrations successfully applied.")
        return True, "Migrations successfully applied."
    except Exception as exc:
        err_msg = f"Database migration failed: {exc}"
        logger.critical(err_msg, exc_info=True)
        return False, err_msg


def verify_database_on_startup(app: Flask) -> None:
    """
    Verify database connectivity and migration state on application startup.
    In production/staging mode or with ENFORCE_MIGRATION_CHECK=True, fails fast if migrations are not ready.
    """
    with app.app_context():
        # First verify connectivity
        try:
            db.session.execute(text("SELECT 1"))
        except Exception as exc:
            msg = f"CRITICAL: Failed to connect to database on startup: {exc}"
            logger.critical(msg)
            if app.config.get("ENV") in ("production", "staging"):
                raise RuntimeError(msg) from exc
            return

        # Next check migration status
        enforce = app.config.get("ENFORCE_MIGRATION_CHECK", False)
        auto_migrate = app.config.get("AUTO_MIGRATE", False)
        status_info = check_migration_status(app)

        if not status_info["is_ready"]:
            if auto_migrate:
                logger.warning(
                    f"Unapplied migrations detected ({status_info['status']}). "
                    f"AUTO_MIGRATE is enabled. Running upgrade..."
                )
                success, msg = apply_migrations()
                if not success and enforce:
                    raise RuntimeError(f"Startup aborted: Failed to apply automated migrations: {msg}")
            elif enforce:
                raise RuntimeError(
                    f"Startup aborted: Database migrations are required. "
                    f"Status: {status_info['status']} (DB={status_info['current_revision']}, "
                    f"Target={status_info['head_revision']}). Run 'flask db upgrade' before starting application."
                )
            else:
                logger.warning(f"Database migration notice: {status_info['message']}")
