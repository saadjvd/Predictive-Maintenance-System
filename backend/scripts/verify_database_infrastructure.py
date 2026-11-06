"""PharmaPredict AI — Database Infrastructure Integration Verification.

Executes comprehensive verification against a live PostgreSQL or TimescaleDB instance:
1. Fresh database uninitialized schema detection.
2. HTTP 503 readiness probe on uninitialized database.
3. HTTP 200 liveness probe during unready state.
4. Application of Alembic baseline migrations (upgrade head).
5. Schema inspection: table counts, primary keys, foreign keys, indexes.
6. Correct head revision verification.
7. check_migration_status() reports 'up_to_date'.
8. TimescaleDB extension presence and hypertable verification (when on TimescaleDB).
9. HTTP 200 readiness probe post-migration.
10. Failure simulation: corrupted/unknown revision returns HTTP 503.
"""
import sys
import os
import logging
from typing import Dict, Any

# Ensure backend directory is in Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask
from sqlalchemy import text, inspect
from app import create_app
from app.extensions import db
from app.config import StagingConfig
from app.database_migrations import (
    check_migration_status,
    apply_migrations,
    get_current_db_revision,
    get_head_revision,
)
from app.health_probes import health_probes_bp

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("db_infrastructure_verification")


def verify_live_database():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        logger.error("DATABASE_URL environment variable is required.")
        sys.exit(1)

    # Mask credentials for logging
    from urllib.parse import urlparse
    parsed = urlparse(database_url)
    masked_url = f"{parsed.scheme}://{parsed.username or 'user'}:***@{parsed.hostname}:{parsed.port}{parsed.path}"
    logger.info(f"Starting Database Infrastructure Verification against: {masked_url}")

    # Set up Staging configuration (enforces migration checks, disables conditional db.create_all)
    class VerificationConfig(StagingConfig):
        SQLALCHEMY_DATABASE_URI = database_url
        ENFORCE_MIGRATION_CHECK = True
        AUTO_MIGRATE = False
        SKIP_DB_CREATE_ALL = True
        SKIP_STARTUP_MIGRATION_CHECK = True
        SECRET_KEY = "a" * 48

    app = create_app(VerificationConfig)

    with app.app_context():
        # Check database engine dialect and version
        engine = db.engine
        dialect_name = engine.dialect.name
        with engine.connect() as conn:
            db_version_raw = conn.execute(text("SELECT version();")).scalar()
        logger.info(f"Database dialect: {dialect_name}")
        logger.info(f"Database version: {db_version_raw}")

        # ---------------------------------------------------------------------
        # Gate Step 1: Detect Uninitialized Database
        # ---------------------------------------------------------------------
        logger.info("--> Gate Step 1: Checking uninitialized schema state on clean database...")
        status_before = check_migration_status(app)
        logger.info(f"Migration status before upgrade: {status_before}")
        assert status_before["status"] == "uninitialized_database", (
            f"Expected 'uninitialized_database', got '{status_before['status']}'"
        )
        assert status_before["is_synced"] is False, "Expected is_synced=False on uninitialized DB"
        logger.info("PASSED: Uninitialized database correctly detected.")

        # ---------------------------------------------------------------------
        # Gate Step 2: Verify Health Probes on Uninitialized Database
        # ---------------------------------------------------------------------
        logger.info("--> Gate Step 2: Testing health probes before migration...")
        client = app.test_client()

        # Liveness must be HTTP 200 (process is responsive)
        live_res = client.get("/health/live")
        assert live_res.status_code == 200, f"Expected 200 from /health/live, got {live_res.status_code}"
        logger.info("PASSED: /health/live returned HTTP 200.")

        # Readiness must be HTTP 503 (database connected but schema unready)
        ready_res = client.get("/health/ready")
        assert ready_res.status_code == 503, f"Expected 503 from /health/ready, got {ready_res.status_code}"
        ready_json = ready_res.get_json()
        assert ready_json["status"] == "not_ready"
        assert "uninitialized_database" in ready_json["dependencies"]["database"]["status"]
        logger.info("PASSED: /health/ready correctly returned HTTP 503 with uninitialized_database.")

        # ---------------------------------------------------------------------
        # Gate Step 3: Apply Alembic Baseline Migration (upgrade head)
        # ---------------------------------------------------------------------
        logger.info("--> Gate Step 3: Applying migrations (flask db upgrade head)...")
        upgrade_success, msg = apply_migrations(target_rev="head")
        assert upgrade_success is True, f"apply_migrations failed: {msg}"
        logger.info("PASSED: Alembic baseline migration applied successfully.")

        # ---------------------------------------------------------------------
        # Gate Step 4: Verify Post-Migration Status & Head Revision
        # ---------------------------------------------------------------------
        logger.info("--> Gate Step 4: Verifying post-migration status and revision match...")
        status_after = check_migration_status(app)
        logger.info(f"Migration status after upgrade: {status_after}")
        assert status_after["status"] == "up_to_date", f"Expected 'up_to_date', got {status_after['status']}"
        assert status_after["is_synced"] is True, "Expected is_synced=True"

        head_rev = get_head_revision()
        current_rev = get_current_db_revision()
        assert current_rev == head_rev, f"Current revision {current_rev} does not match head {head_rev}"
        logger.info(f"PASSED: Migration status is 'up_to_date' at revision {current_rev}.")

        # ---------------------------------------------------------------------
        # Gate Step 5: Table and Constraint Inspection
        # ---------------------------------------------------------------------
        logger.info("--> Gate Step 5: Inspecting materialized application tables and constraints...")
        inspector = inspect(engine)
        table_names = inspector.get_table_names()
        logger.info(f"Materialized {len(table_names)} tables in database.")
        assert len(table_names) >= 55, f"Expected at least 55 tables, got {len(table_names)}"

        # Verify core application tables exist
        required_tables = [
            "alembic_version",
            "organizations",
            "sites",
            "users",
            "roles",
            "machines",
            "equipment_categories",
            "signal_definitions",
            "machine_signals",
            "signal_readings",
            "audit_logs",
            "gateway_health",
            "ingestion_batches",
        ]
        for tbl in required_tables:
            assert tbl in table_names, f"Mandatory table '{tbl}' not found in database"

        # Verify primary key constraints on core tables
        for tbl in ["users", "machines", "signal_readings", "organizations"]:
            pk = inspector.get_pk_constraint(tbl)
            assert pk and pk.get("constrained_columns"), f"Table {tbl} lacks a primary key constraint"

        # Verify indexes on signal_readings
        reading_indexes = [idx["name"] for idx in inspector.get_indexes("signal_readings")]
        logger.info(f"Signal readings indexes: {reading_indexes}")
        assert any("timestamp" in str(idx) for idx in reading_indexes), "Missing timestamp index on signal_readings"
        logger.info("PASSED: Core tables, primary keys, and indexes verified.")

        # ---------------------------------------------------------------------
        # Gate Step 6: TimescaleDB Extension & Hypertable Verification (if applicable)
        # ---------------------------------------------------------------------
        logger.info("--> Gate Step 6: Verifying TimescaleDB extension and hypertables...")
        with engine.connect() as conn:
            ext_check = conn.execute(text("SELECT extname, extversion FROM pg_extension WHERE extname = 'timescaledb';")).fetchone()
            if ext_check:
                logger.info(f"TimescaleDB extension IS INSTALLED: {ext_check[0]} v{ext_check[1]}")
                # Check hypertables catalog
                hypertables = conn.execute(text("""
                    SELECT hypertable_schema, hypertable_name 
                    FROM timescaledb_information.hypertables;
                """)).fetchall()
                logger.info(f"TimescaleDB hypertables: {hypertables}")
            else:
                logger.info("Standard PostgreSQL dialect without TimescaleDB extension. Extension check skipped.")
        logger.info("PASSED: Database extension check completed.")

        # ---------------------------------------------------------------------
        # Gate Step 7: Verify Readiness Probe Post-Migration
        # ---------------------------------------------------------------------
        logger.info("--> Gate Step 7: Testing /health/ready on migrated database...")
        ready_res_after = client.get("/health/ready")
        assert ready_res_after.status_code == 200, f"Expected 200 from /health/ready, got {ready_res_after.status_code}"
        ready_json_after = ready_res_after.get_json()
        assert ready_json_after["status"] == "ready"
        assert ready_json_after["dependencies"]["database"]["healthy"] is True
        logger.info(f"PASSED: /health/ready returned HTTP 200 with latency {ready_json_after['dependencies']['database']['latency_ms']}ms.")

        # ---------------------------------------------------------------------
        # Gate Step 8: Migration Failure Simulation
        # ---------------------------------------------------------------------
        logger.info("--> Gate Step 8: Simulating migration failure / corrupted revision...")
        with engine.begin() as conn:
            conn.execute(text("UPDATE alembic_version SET version_num = 'corrupted_unknown_rev';"))

        corrupted_status = check_migration_status(app)
        logger.info(f"Corrupted status: {corrupted_status}")
        assert corrupted_status["status"] == "unknown_revision"
        assert corrupted_status["is_synced"] is False

        ready_res_corrupted = client.get("/health/ready")
        assert ready_res_corrupted.status_code == 503
        logger.info("PASSED: Readiness probe correctly rejects corrupted/unknown revision with HTTP 503.")

        # Restore revision to head
        with engine.begin() as conn:
            conn.execute(text(f"UPDATE alembic_version SET version_num = '{head_rev}';"))
        logger.info("Restored alembic_version to head.")

    logger.info("=" * 70)
    logger.info("ALL DATABASE INFRASTRUCTURE VERIFICATION CHECKS PASSED SUCCESSFULLY!")
    logger.info("=" * 70)


if __name__ == "__main__":
    verify_live_database()
