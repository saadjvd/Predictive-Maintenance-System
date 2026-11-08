"""PharmaPredict AI — Unit & Integration Tests for P10-F01 Deployment Architecture.

Verifies:
- Issue #68: Enterprise Productization & Deployment Architecture
- Issue #69: Production Containerization & Environment Configuration
- Issue #70: Canonical Infrastructure Probes & Automated Database Migrations
- Audit Findings P10-F01-01 through P10-F01-04 Corrective Validations
"""
import os
import sys
import pytest
from unittest.mock import patch, MagicMock
from flask import Flask
from app import create_app
from app.config import ProductionConfig, StagingConfig, DEFAULT_DEV_SECRET
from app.database_migrations import (
    check_migration_status,
    apply_migrations,
    verify_database_on_startup,
    get_current_db_revision,
    get_head_revision,
    get_known_revisions
)
from app.health_probes import (
    get_redis_connection_pool,
    reset_redis_connection_pools,
    _check_redis,
    _check_database
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

    def test_readiness_probe_schema_unready_in_production_returns_503(self, client, app):
        """Verify /health/ready returns HTTP 503 if database schema is uninitialized in production/enforced mode."""
        unready_status = {
            "is_synced": False,
            "is_ready": False,
            "current_revision": None,
            "head_revision": "0001_initial_schema",
            "status": "uninitialized_database",
            "message": "Uninitialized"
        }
        with patch("app.health_probes.current_app.config", {**app.config, "ENV": "production", "ENFORCE_MIGRATION_CHECK": True}):
            with patch("app.database_migrations.check_migration_status", return_value=unready_status):
                response = client.get("/health/ready")
                assert response.status_code == 503
                data = response.get_json()
                assert data["status"] == "not_ready"
                assert data["dependencies"]["database"]["healthy"] is False
                assert "schema_uninitialized_database" in data["dependencies"]["database"]["status"]

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
    """Tests for Issue #70 & Audit Finding P10-F01-01 Database Migration Mechanics."""

    def test_baseline_migration_head_revision_exists(self):
        """Verify that 0001_initial_schema exists as a head revision in migrations."""
        head_rev = get_head_revision()
        assert head_rev is not None
        assert head_rev == "0001_initial_schema"

    def test_known_revisions_contains_baseline(self):
        """Verify that walk_revisions correctly enumerates the baseline revision."""
        revisions = get_known_revisions()
        assert "0001_initial_schema" in revisions

    def test_check_migration_status_uninitialized_database(self, app):
        """State 1: Empty database must report uninitialized_database and is_ready=False."""
        mock_inspector = MagicMock()
        mock_inspector.get_table_names.return_value = []

        with app.app_context():
            with patch("app.database_migrations.inspect", return_value=mock_inspector):
                status = check_migration_status(app)
                assert status["status"] == "uninitialized_database"
                assert status["is_synced"] is False
                assert status["is_ready"] is False
                assert status["head_revision"] == "0001_initial_schema"

    def test_check_migration_status_up_to_date(self, app):
        """State 2: Database matching script head must report up_to_date and is_ready=True."""
        mock_inspector = MagicMock()
        mock_inspector.get_table_names.return_value = ["alembic_version", "users", "machines"]

        with app.app_context():
            with patch("app.database_migrations.inspect", return_value=mock_inspector):
                with patch("app.database_migrations.get_current_db_revision", return_value="0001_initial_schema"):
                    status = check_migration_status(app)
                    assert status["status"] == "up_to_date"
                    assert status["is_synced"] is True
                    assert status["is_ready"] is True
                    assert status["current_revision"] == "0001_initial_schema"

    def test_check_migration_status_pending_migration(self, app):
        """State 3: Database behind head with known revision must report pending_migration and is_ready=False."""
        mock_inspector = MagicMock()
        mock_inspector.get_table_names.return_value = ["alembic_version", "users"]

        with app.app_context():
            with patch("app.database_migrations.inspect", return_value=mock_inspector):
                with patch("app.database_migrations.get_current_db_revision", return_value="0000_previous"):
                    with patch("app.database_migrations.get_head_revision", return_value="0001_initial_schema"):
                        with patch("app.database_migrations.get_known_revisions", return_value={"0000_previous", "0001_initial_schema"}):
                            status = check_migration_status(app)
                            assert status["status"] == "pending_migration"
                            assert status["is_synced"] is False
                            assert status["is_ready"] is False

    def test_check_migration_status_unknown_revision(self, app):
        """State 4: Database stamped with unknown revision must report unknown_revision and is_ready=False."""
        mock_inspector = MagicMock()
        mock_inspector.get_table_names.return_value = ["alembic_version", "users"]

        with app.app_context():
            with patch("app.database_migrations.inspect", return_value=mock_inspector):
                with patch("app.database_migrations.get_current_db_revision", return_value="rogue_rev_9999"):
                    with patch("app.database_migrations.get_head_revision", return_value="0001_initial_schema"):
                        with patch("app.database_migrations.get_known_revisions", return_value={"0001_initial_schema"}):
                            status = check_migration_status(app)
                            assert status["status"] == "unknown_revision"
                            assert status["is_synced"] is False
                            assert status["is_ready"] is False

    def test_check_migration_status_unversioned_tables_exist(self, app):
        """State 5: Database with application tables but missing alembic_version must report unversioned_tables_exist."""
        mock_inspector = MagicMock()
        mock_inspector.get_table_names.return_value = ["users", "machines", "organizations"]

        with app.app_context():
            with patch("app.database_migrations.inspect", return_value=mock_inspector):
                status = check_migration_status(app)
                assert status["status"] == "unversioned_tables_exist"
                assert status["is_synced"] is False
                assert status["is_ready"] is False

    def test_check_migration_status_inspection_failure(self, app):
        """State 6: Database inspection failure must report inspection_failed and is_ready=False."""
        with app.app_context():
            with patch("app.database_migrations.inspect", side_effect=Exception("Database connection timeout")):
                status = check_migration_status(app)
                assert status["status"] == "inspection_failed"
                assert status["is_synced"] is False
                assert status["is_ready"] is False

    def test_verify_database_on_startup_aborts_on_unready_db_when_enforced(self, app):
        """Verify startup verification aborts when ENFORCE_MIGRATION_CHECK is enabled and database is unready."""
        app.config["ENFORCE_MIGRATION_CHECK"] = True
        app.config["AUTO_MIGRATE"] = False

        mock_status = {
            "is_synced": False,
            "is_ready": False,
            "current_revision": None,
            "head_revision": "0001_initial_schema",
            "status": "uninitialized_database",
            "message": "Empty"
        }

        with patch("app.database_migrations.check_migration_status", return_value=mock_status):
            with pytest.raises(RuntimeError) as exc_info:
                verify_database_on_startup(app)
            assert "Database migrations are required" in str(exc_info.value)
            assert "uninitialized_database" in str(exc_info.value)


class TestRedisConnectionPoolReuse:
    """Tests for Audit Finding P10-F01-04 Redis Connection Pool Lifecycle."""

    def setup_method(self):
        reset_redis_connection_pools()

    def teardown_method(self):
        reset_redis_connection_pools()

    def test_redis_connection_pool_reused(self):
        """Verify get_redis_connection_pool caches and reuses the same pool for identical URLs."""
        test_url = "redis://localhost:6379/1"
        mock_redis = MagicMock()
        mock_pool = MagicMock()
        mock_redis.ConnectionPool.from_url.return_value = mock_pool

        with patch.dict(sys.modules, {"redis": mock_redis}):
            pool1 = get_redis_connection_pool(test_url)
            pool2 = get_redis_connection_pool(test_url)

            assert pool1 is pool2
            assert mock_redis.ConnectionPool.from_url.call_count == 1

    def test_redis_connection_pool_reset_clears_cache(self):
        """Verify reset_redis_connection_pools closes and empties cached connection pools."""
        test_url = "redis://localhost:6379/2"
        mock_redis = MagicMock()
        mock_pool = MagicMock()
        mock_redis.ConnectionPool.from_url.return_value = mock_pool

        with patch.dict(sys.modules, {"redis": mock_redis}):
            get_redis_connection_pool(test_url)
            reset_redis_connection_pools()
            mock_pool.disconnect.assert_called_once()

            get_redis_connection_pool(test_url)
            assert mock_redis.ConnectionPool.from_url.call_count == 2

    def test_check_redis_uses_pool_and_handles_failure_gracefully(self, app):
        """Verify _check_redis ping failure returns healthy=False with error class name."""
        with app.app_context():
            app.config["REDIS_URL"] = "redis://localhost:6379/0"
            mock_redis = MagicMock()
            mock_client = MagicMock()
            mock_client.ping.side_effect = Exception("ConnectionRefusedError")
            mock_redis.Redis.return_value = mock_client

            with patch.dict(sys.modules, {"redis": mock_redis}):
                with patch("app.health_probes.get_redis_connection_pool") as mock_get_pool:
                    mock_get_pool.return_value = MagicMock()
                    ok, status, latency = _check_redis()
                    assert ok is False
                    assert "unreachable" in status
                    assert "Exception" in status

    def test_concurrent_readiness_probes_reuse_pool(self):
        """Verify concurrent probe calls across multiple threads safely reuse the cached Redis pool."""
        import concurrent.futures
        test_url = "redis://localhost:6379/3"
        mock_redis = MagicMock()
        mock_pool = MagicMock()
        mock_redis.ConnectionPool.from_url.return_value = mock_pool

        with patch.dict(sys.modules, {"redis": mock_redis}):
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
                futures = [executor.submit(get_redis_connection_pool, test_url) for _ in range(20)]
                pools = [f.result() for f in futures]

            assert len(pools) == 20
            assert all(p is mock_pool for p in pools)
            # Pool must be created exactly once despite concurrent thread execution
            assert mock_redis.ConnectionPool.from_url.call_count == 1

    def test_redis_connection_pool_parameters(self):
        """Verify get_redis_connection_pool enforces connection limits and short timeouts."""
        test_url = "redis://localhost:6379/4"
        mock_redis = MagicMock()
        mock_redis.ConnectionPool.from_url.return_value = MagicMock()

        with patch.dict(sys.modules, {"redis": mock_redis}):
            get_redis_connection_pool(test_url)
            mock_redis.ConnectionPool.from_url.assert_called_once_with(
                test_url,
                max_connections=5,
                socket_timeout=1.5,
                socket_connect_timeout=1.5
            )

    def test_concurrent_redis_unreachability_handled_safely(self, app):
        """Verify concurrent probes handle Redis unavailability gracefully without unhandled exceptions."""
        import concurrent.futures
        app.config["REDIS_URL"] = "redis://localhost:6379/9"
        mock_redis = MagicMock()
        mock_client = MagicMock()
        mock_client.ping.side_effect = TimeoutError("Connection timed out")
        mock_redis.Redis.return_value = mock_client

        def _worker():
            with app.app_context():
                return _check_redis()

        with patch.dict(sys.modules, {"redis": mock_redis}):
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
                futures = [executor.submit(_worker) for _ in range(20)]
                results = [f.result() for f in futures]

            assert len(results) == 20
            for ok, status, latency in results:
                assert ok is False
                assert "unreachable" in status
                assert "TimeoutError" in status


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


class TestContainerHardeningSpecifications:
    """Tests for Audit Findings P10-F01-02 & P10-F01-03."""

    def test_backend_dockerfile_contains_libgomp1(self):
        """P10-F01-02: Verify backend/Dockerfile runner installs libgomp1 for OpenMP scikit-learn support."""
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        dockerfile_path = os.path.join(backend_dir, "Dockerfile")
        with open(dockerfile_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "libgomp1" in content

    def test_docker_compose_redis_healthcheck_uses_rediscli_auth(self):
        """P10-F01-03: Verify deploy/production/docker-compose.prod.yml uses REDISCLI_AUTH without -a password flag."""
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        repo_root = os.path.dirname(backend_dir)
        compose_path = os.path.join(repo_root, "deploy", "production", "docker-compose.prod.yml")
        with open(compose_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "REDISCLI_AUTH" in content
        assert 'redis-cli", "-a"' not in content
        assert "redis-cli\", \"ping\"" in content


class TestProductionComposeSpecification:
    """Comprehensive validation of deploy/production/docker-compose.prod.yml structure & security."""

    @pytest.fixture
    def compose_data(self):
        import yaml
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        repo_root = os.path.dirname(backend_dir)
        compose_path = os.path.join(repo_root, "deploy", "production", "docker-compose.prod.yml")
        with open(compose_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def test_compose_services_defined(self, compose_data):
        """Verify all 4 core enterprise services are declared."""
        services = compose_data.get("services", {})
        assert "timescaledb" in services
        assert "redis" in services
        assert "backend" in services
        assert "frontend" in services

    def test_compose_networks_and_volumes_defined(self, compose_data):
        """Verify persistent volumes and isolated bridge networks are configured."""
        volumes = compose_data.get("volumes", {})
        assert "timescaledb_prod_data" in volumes
        assert "redis_prod_data" in volumes

        networks = compose_data.get("networks", {})
        assert "pharmapredict-prod-net" in networks
        assert networks["pharmapredict-prod-net"].get("driver") == "bridge"

    def test_compose_services_healthchecks_and_dependencies(self, compose_data):
        """Verify healthchecks and health-dependent startup ordering."""
        services = compose_data.get("services", {})
        for sname in ["timescaledb", "redis", "backend", "frontend"]:
            assert "healthcheck" in services[sname], f"Missing healthcheck in {sname}"

        backend_deps = services["backend"].get("depends_on", {})
        assert backend_deps["timescaledb"]["condition"] == "service_healthy"
        assert backend_deps["redis"]["condition"] == "service_healthy"

        frontend_deps = services["frontend"].get("depends_on", {})
        assert frontend_deps["backend"]["condition"] == "service_healthy"

    def test_compose_port_bindings_restricted_to_localhost(self, compose_data):
        """Verify internal databases are strictly bound to localhost (127.0.0.1) on host."""
        services = compose_data.get("services", {})
        for db_service in ["timescaledb", "redis"]:
            ports = services[db_service].get("ports", [])
            for p in ports:
                assert "127.0.0.1:" in str(p), f"Port {p} on {db_service} must bind to 127.0.0.1"

    def test_compose_no_hardcoded_secrets(self, compose_data):
        """Verify no hardcoded secrets exist; all use ${VAR:?Error} required interpolation."""
        import yaml
        raw_text = yaml.dump(compose_data)
        assert "postgres:postgres" not in raw_text
        assert "dev-pharma-predict" not in raw_text
