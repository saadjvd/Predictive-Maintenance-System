from datetime import datetime, timezone
from flask import Blueprint, jsonify, current_app
from sqlalchemy import text
from app.extensions import db
from app.health_probes import liveness_probe, readiness_probe, system_operational_probe

health_bp = Blueprint("health", __name__)


@health_bp.route("/health", methods=["GET"])
def health_check():
    """
    Standard versioned API health check endpoint (/api/v1/health).
    Verifies service status, configuration, and database connectivity.
    """
    db_status = "unknown"
    try:
        # Check database connectivity
        db.session.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as exc:
        db_status = f"unreachable ({str(exc.__class__.__name__)})"

    return jsonify({
        "status": "healthy" if db_status == "connected" else "degraded",
        "service": current_app.config.get("APP_NAME", "PharmaPredict AI"),
        "version": current_app.config.get("APP_VERSION", "1.0.0"),
        "environment": current_app.config.get("ENV", "development"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database": db_status,
        "capabilities": [
            "health_monitoring",
            "predictive_maintenance_api",
            "opc_ua_gateway_ready",
            "tenancy_isolation_ready",
            "canonical_infrastructure_probes",
            "automated_database_migrations"
        ]
    }), 200 if db_status == "connected" else 503


@health_bp.route("/health/live", methods=["GET"])
def api_liveness():
    """Versioned alias for liveness probe (/api/v1/health/live)."""
    return liveness_probe()


@health_bp.route("/health/ready", methods=["GET"])
def api_readiness():
    """Versioned alias for readiness probe (/api/v1/health/ready)."""
    return readiness_probe()


@health_bp.route("/health/system", methods=["GET"])
def api_system():
    """Versioned alias for operational diagnostics (/api/v1/health/system)."""
    return system_operational_probe()
