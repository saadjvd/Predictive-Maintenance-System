from datetime import datetime, timezone
from flask import Blueprint, jsonify, current_app
from sqlalchemy import text
from app.extensions import db

health_bp = Blueprint("health", __name__)


@health_bp.route("/health", methods=["GET"])
def health_check():
    """
    Health check endpoint.
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
        "status": "healthy",
        "service": current_app.config.get("APP_NAME", "PharmaPredict AI"),
        "version": current_app.config.get("APP_VERSION", "0.1.0"),
        "environment": current_app.config.get("ENV", "development"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database": db_status,
        "capabilities": [
            "health_monitoring",
            "predictive_maintenance_api",
            "opc_ua_gateway_ready",
            "tenancy_isolation_ready"
        ]
    }), 200

