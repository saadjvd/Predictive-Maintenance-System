"""PharmaPredict AI — Canonical Infrastructure Health & Probe Endpoints.

Provides unversioned, low-overhead HTTP probe endpoints for container orchestrators
(Kubernetes liveness/readiness probes, Docker daemon healthchecks, load balancers)
and infrastructure operations consoles.

Endpoints:
- /health/live   : Liveness probe (process responsiveness)
- /health/ready  : Readiness probe (database and cache dependency health)
- /health/system : Operational component diagnostics (safe, credential-masked)
"""
import os
import time
from datetime import datetime, timezone
from typing import Dict, Any, Tuple
from flask import Blueprint, jsonify, current_app
from sqlalchemy import text
from app.extensions import db

health_probes_bp = Blueprint("health_probes", __name__)

_PROCESS_START_TIME = datetime.now(timezone.utc)


def _check_database() -> Tuple[bool, str, float]:
    """Check database connectivity and query response latency."""
    start = time.perf_counter()
    try:
        db.session.execute(text("SELECT 1"))
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        return True, "connected", latency_ms
    except Exception as exc:
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        return False, f"unreachable ({exc.__class__.__name__})", latency_ms


def _check_redis() -> Tuple[bool, str, float]:
    """Check Redis connectivity if configured."""
    redis_url = current_app.config.get("REDIS_URL") or os.getenv("REDIS_URL")
    if not redis_url:
        return True, "not_configured", 0.0

    start = time.perf_counter()
    try:
        import redis
        client = redis.Redis.from_url(redis_url, socket_timeout=1.5, socket_connect_timeout=1.5)
        client.ping()
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        return True, "connected", latency_ms
    except ImportError:
        return True, "client_not_installed", 0.0
    except Exception as exc:
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        return False, f"unreachable ({exc.__class__.__name__})", latency_ms


@health_probes_bp.route("/health/live", methods=["GET"])
def liveness_probe():
    """
    Kubernetes Liveness Probe / Container Heartbeat.
    Confirms the WSGI/Flask process is running and handling HTTP traffic.
    Ultra-low latency (zero external network/disk I/O).
    """
    return jsonify({
        "status": "alive",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }), 200


@health_probes_bp.route("/health/ready", methods=["GET"])
def readiness_probe():
    """
    Kubernetes Readiness Probe / Load Balancer Target Health.
    Confirms that critical runtime dependencies (Database, Redis) are online
    and capable of serving client transactions.
    Returns HTTP 200 if ready, or HTTP 503 if any mandatory dependency is degraded.
    """
    db_ok, db_status, db_latency = _check_database()
    redis_ok, redis_status, redis_latency = _check_redis()

    is_ready = db_ok and redis_ok
    status_code = 200 if is_ready else 503

    response_payload = {
        "status": "ready" if is_ready else "not_ready",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dependencies": {
            "database": {
                "status": db_status,
                "healthy": db_ok,
                "latency_ms": db_latency
            },
            "redis": {
                "status": redis_status,
                "healthy": redis_ok,
                "latency_ms": redis_latency
            }
        }
    }

    return jsonify(response_payload), status_code


@health_probes_bp.route("/health/system", methods=["GET"])
def system_operational_probe():
    """
    Enterprise Operations & Monitoring Status Endpoint.
    Returns detailed component status, process uptime, and capability flags.
    Credentials and sensitive connection parameters are strictly masked.
    """
    db_ok, db_status, db_latency = _check_database()
    redis_ok, redis_status, redis_latency = _check_redis()

    now = datetime.now(timezone.utc)
    uptime_seconds = int((now - _PROCESS_START_TIME).total_seconds())

    # Safe sanitized environment info
    env_name = current_app.config.get("ENV", "development")
    version = current_app.config.get("APP_VERSION", "1.0.0")
    service_name = current_app.config.get("APP_NAME", "PharmaPredict AI")

    # Determine database engine flavor safely without leaking credentials
    db_uri = str(current_app.config.get("SQLALCHEMY_DATABASE_URI", ""))
    if "postgresql" in db_uri or "timescaledb" in db_uri:
        db_engine = "postgresql/timescaledb"
    elif "sqlite" in db_uri:
        db_engine = "sqlite"
    else:
        db_engine = "unknown"

    return jsonify({
        "service": service_name,
        "version": version,
        "environment": env_name,
        "timestamp": now.isoformat(),
        "uptime_seconds": uptime_seconds,
        "components": {
            "database": {
                "engine": db_engine,
                "status": db_status,
                "healthy": db_ok,
                "latency_ms": db_latency
            },
            "cache_queue": {
                "status": redis_status,
                "healthy": redis_ok,
                "latency_ms": redis_latency
            }
        },
        "capabilities": {
            "enterprise_multisite": True,
            "cmms_gateway_ready": True,
            "reliability_analytics_ready": True,
            "model_governance_ready": True,
            "audit_trail_21cfr11": True
        }
    }), 200 if (db_ok and redis_ok) else 503

