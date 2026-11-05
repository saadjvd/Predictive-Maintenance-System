"""PharmaPredict AI — Unit & Integration Tests for P10-F01 Deployment Architecture.

Verifies:
- Issue #68: Enterprise Productization & Deployment Architecture
- Issue #69: Production Containerization & Environment Configuration
- Issue #70: Canonical Infrastructure Probes & Automated Database Migrations
"""
import pytest
from unittest.mock import patch
from flask import Flask
from app import create_app
from app.config import ProductionConfig, StagingConfig, DEFAULT_DEV_SECRET
from app.database_migrations import (
    check_migration_status,
    apply_migrations,
    verify_database_on_startup,
    get_current_db_revision,
    get_head_revision
)


class TestCanonicalHealthProbes:
    """Tests for Issue #70 Canonical Infrastructure Probes."""

    def test_liveness_probe_returns_200(self, client):
        """Verify unversioned /health/live returns HTTP 200 immediately."""
        response = client.get("/health/live")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "alive"
        assert "timestamp" in data

    def test_readiness_probe_healthy_returns_200(self, client):
        """Verify unversioned /health/ready returns HTTP 200 when dependencies are healthy."""
        response = client.get("/health/ready")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "ready"
        assert "dependencies" in data
        assert data["dependencies"]["database"]["healthy"] is True
        assert data["dependencies"]["database"]["status"] == "connected"
        assert "latency_ms" in data["dependencies"]["database"]

    def test_readiness_probe_db_failure_returns_503(self, client):
        """Verify /health/ready returns HTTP 503 when the database is unreachable."""
        with patch("app.health_probes.db.session.execute", side_effect=Exception("DB Connection Timeout")):
            response = client.get("/health/ready")
            assert response.status_code == 503
            data = response.get_json()
            assert data["status"] == "not_ready"
            assert data["dependencies"]["database"]["healthy"] is False
            assert "unreachable" in data["dependencies"]["database"]["status"]

    def test_system_operational_probe_returns_diagnostics(self, client):
        """Verify /health/system returns comprehensive diagnostics without leaking credentials."""
        response = client.get("/health/system")
        assert response.status_code == 200
        data = response.get_json()
        assert data["service"] == "PharmaPredict AI"
        assert data["version"] == "1.0.0"
        assert "uptime_seconds" in data
        assert isinstance(data["uptime_seconds"], int)
        assert "components" in data
        assert "database" in data["components"]
        assert "cache_queue" in data["components"]
        assert "capabilities" in data
        assert data["capabilities"]["enterprise_multisite"] is True
        assert data["capabilities"]["cmms_gateway_ready"] is True
        assert data["capabilities"]["reliability_analytics_ready"] is True
        assert data["capabilities"]["audit_trail_21cfr11"] is True

        # Confirm no passwords or sensitive tokens leaked in the output
        raw_text = response.get_data(as_text=True)
        assert "password" not in raw_text.lower()
        assert "secret" not in raw_text.lower()

    def test_versioned_api_probe_aliases(self, client):
        """Verify /api/v1/health/live and /api/v1/health/ready aliases return matching status."""
        live_resp = client.get("/api/v1/health/live")
        assert live_resp.status_code == 200
        assert live_resp.get_json()["status"] == "alive"

        ready_resp = client.get("/api/v1/health/ready")
        assert ready_resp.status_code == 200
        assert ready_resp.get_json()["status"] == "ready"

        sys_resp = client.get("/api/v1/health/system")
        assert sys_resp.status_code == 200
        assert sys_resp.get_json()["service"] == "PharmaPredict AI"


class TestDatabaseMigrationManagement:
    """Tests for Issue #70 Automated Database Migrations & Status Verification."""

    def test_check_migration_status_reports_synced_or_baseline(self, app):
        """Verify migration status check returns structured diagnostic information."""
        with app.app_context():
            status = check_migration_status(app)
            assert isinstance(status, dict)
            assert "is_synced" in status
            assert "current_revision" in status
            assert "head_revision" in status
            assert "status" in status
            assert status["status"] in ("up_to_date", "unversioned_schema", "pending_migration")

    def test_verify_database_on_startup_passes_on_dev(self, app):
        """Verify startup database check runs cleanly without raising on development/testing app."""
        # Should not raise any exception
        verify_database_on_startup(app)

    def test_verify_database_on_startup_aborts_on_unreachable_production_db(self):
        """Verify startup verification raises RuntimeError if production database is unreachable."""
        test_app = Flask(__name__)
        test_app.config["ENV"] = "production"
        test_app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"

        with patch("app.database_migrations.db.session.execute", side_effect=Exception("Connection refused")):
            with pytest.raises(RuntimeError) as exc_info:
                verify_database_on_startup(test_app)
            assert "Failed to connect to database" in str(exc_info.value)

    def test_verify_database_on_startup_aborts_on_pending_migrations_when_enforced(self, app):
        """Verify startup verification aborts when ENFORCE_MIGRATION_CHECK is enabled and migrations are pending."""
        app.config["ENFORCE_MIGRATION_CHECK"] = True
        app.config["AUTO_MIGRATE"] = False

        mock_status = {
            "is_synced": False,
            "current_revision": "rev_001",
            "head_revision": "rev_002",
            "status": "pending_migration",
            "message": "Mismatch"
        }

        with patch("app.database_migrations.check_migration_status", return_value=mock_status):
            with pytest.raises(RuntimeError) as exc_info:
                verify_database_on_startup(app)
            assert "Database migrations are pending" in str(exc_info.value)


class TestHardenedEnvironmentConfiguration:
    """Tests for Issue #69 Production Environment Configuration & Validation."""

    def test_production_config_rejects_default_dev_secret(self):
        """Verify ProductionConfig rejects the default development SECRET_KEY."""
        with patch.object(ProductionConfig, "SECRET_KEY", DEFAULT_DEV_SECRET):
            with pytest.raises(ValueError) as exc_info:
                ProductionConfig.validate()
            assert "strong, cryptographically random SECRET_KEY" in str(exc_info.value)

    def test_production_config_rejects_short_secret(self):
        """Verify ProductionConfig rejects SECRET_KEY shorter than 32 characters."""
        with patch.object(ProductionConfig, "SECRET_KEY", "too-short-secret"):
            with pytest.raises(ValueError) as exc_info:
                ProductionConfig.validate()
            assert "minimum 32 characters" in str(exc_info.value)

    def test_production_config_rejects_sqlite_database(self):
        """Verify ProductionConfig rejects SQLite for production deployments."""
        valid_secret = "a" * 48
        with patch.object(ProductionConfig, "SECRET_KEY", valid_secret):
            with patch.object(ProductionConfig, "SQLALCHEMY_DATABASE_URI", "sqlite:///test.db"):
                with pytest.raises(ValueError) as exc_info:
                    ProductionConfig.validate()
                assert "enterprise database" in str(exc_info.value)
                assert "SQLite is prohibited" in str(exc_info.value)

    def test_production_config_accepts_valid_parameters(self):
        """Verify ProductionConfig passes validation with valid enterprise settings."""
        valid_secret = "b" * 48
        valid_pg = "postgresql://user:pass@db-cluster.internal:5432/pharmapredict_db"
        with patch.object(ProductionConfig, "SECRET_KEY", valid_secret):
            with patch.object(ProductionConfig, "SQLALCHEMY_DATABASE_URI", valid_pg):
                # Should not raise
                ProductionConfig.validate()

    def test_staging_config_rejects_weak_secret(self):
        """Verify StagingConfig enforces minimum security requirements."""
        with patch.object(StagingConfig, "SECRET_KEY", DEFAULT_DEV_SECRET):
            with pytest.raises(ValueError):
                StagingConfig.validate()

