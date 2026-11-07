"""PharmaPredict AI — Cloud Pre-Deployment Migration Runner.

Executes deterministic, safe Alembic database migrations during cloud deployment
pre-deploy phase (e.g. Render preDeployCommand) prior to routing live traffic.

Design Principles:
- Single execution per deployment (avoids multi-replica DDL races).
- Diagnostic status checks before and after migration.
- Safe abort on unversioned existing tables or unknown revisions.
- Zero credential leakage in stdout/stderr logs.
- Clean exit codes: 0 for success, 1 for failure/abort.
"""
import sys
import os
import logging
from urllib.parse import urlparse

# Ensure backend root is in Python module search path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [deploy_migrations] %(message)s"
)
logger = logging.getLogger("pharmapredict.deploy_migrations")


def mask_database_url(url: str) -> str:
    """Mask credentials in database connection URI for safe log emission."""
    try:
        parsed = urlparse(url)
        username = parsed.username or "user"
        host = parsed.hostname or "localhost"
        port = f":{parsed.port}" if parsed.port else ""
        return f"{parsed.scheme}://{username}:***@{host}{port}{parsed.path}"
    except Exception:
        return "<masked_database_uri>"


def run_deployment_migrations() -> int:
    """Execute pre-deployment database migration and return exit code (0 = OK, 1 = Error)."""
    # Force migration bypass flags during migration runner initialization
    os.environ["SKIP_STARTUP_MIGRATION_CHECK"] = "true"
    os.environ["SKIP_DB_CREATE_ALL"] = "true"

    from app import create_app
    from app.extensions import db
    from app.database_migrations import (
        check_migration_status,
        apply_migrations,
        get_head_revision,
        get_current_db_revision,
    )

    env_name = os.getenv("FLASK_ENV", "staging")
    app = create_app(env_name)

    db_uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    logger.info(f"Target Environment: {env_name.upper()}")
    logger.info(f"Target Database: {mask_database_url(db_uri)}")

    with app.app_context():
        # 1. Connectivity verification
        try:
            from sqlalchemy import text
            with db.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("Database connectivity check: OK")
        except Exception as conn_err:
            logger.critical(f"Database connectivity failed: {conn_err}")
            return 1

        # 2. Pre-migration state inspection
        initial_status = check_migration_status(app)
        status_name = initial_status.get("status")
        current_rev = initial_status.get("current_revision")
        head_rev = initial_status.get("head_revision")

        logger.info(
            f"Pre-migration status: '{status_name}' "
            f"(current={current_rev}, head={head_rev})"
        )

        if status_name == "up_to_date":
            logger.info(f"Database is already up to date at head revision: {current_rev}. No migration needed.")
            return 0

        if status_name in ("unknown_revision", "unversioned_tables_exist"):
            logger.critical(
                f"Aborting migration: Unsafe schema state detected: '{status_name}'. "
                f"Manual DBA inspection required to prevent data loss."
            )
            return 1

        if status_name not in ("uninitialized_database", "pending_migration"):
            logger.critical(f"Aborting migration: Unexpected schema state: '{status_name}'")
            return 1

        # 3. Apply migrations to target head
        logger.info(f"Applying database migrations to head ({head_rev})...")
        success, message = apply_migrations(target_rev="head")
        if not success:
            logger.critical(f"Database migration failed: {message}")
            return 1

        logger.info(f"Migration execution completed: {message}")

        # 4. Post-migration verification
        final_status = check_migration_status(app)
        final_status_name = final_status.get("status")
        final_current_rev = final_status.get("current_revision")

        logger.info(
            f"Post-migration status: '{final_status_name}' "
            f"(current={final_current_rev}, head={head_rev})"
        )

        if final_status_name == "up_to_date" and final_current_rev == head_rev:
            logger.info("Database successfully migrated and verified up to date.")
            return 0
        else:
            logger.critical(
                f"Post-migration verification failed: expected 'up_to_date' at {head_rev}, "
                f"got '{final_status_name}' at {final_current_rev}"
            )
            return 1


if __name__ == "__main__":
    exit_code = run_deployment_migrations()
    sys.exit(exit_code)

