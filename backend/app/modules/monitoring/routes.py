import os
import logging
from functools import wraps
from flask import Blueprint, request, jsonify, g, current_app
from datetime import datetime, timezone
from app.extensions import db
from app.models.user import Role
from app.models.equipment import Machine
from app.security import login_required, roles_required
from app.modules.monitoring.lifecycle import MonitoringLifecycleManager
from app.modules.monitoring.ingestion_service import IngestionService
from app.models.monitoring import GatewayHealthRecord

logger = logging.getLogger(__name__)

monitoring_bp = Blueprint("monitoring", __name__)

MONITORING_MANAGE_ROLES = [Role.ORG_ADMIN, Role.MAINTENANCE_MANAGER, Role.MAINTENANCE_ENGINEER]

GATEWAY_SECRET = os.getenv("GATEWAY_INTERNAL_SECRET", "pharma-predict-internal-gateway-key-2026")


def internal_gateway_required(f):
    """Ensure request comes from an authenticated internal edge gateway service (Requirement 8)."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_key = request.headers.get("X-Gateway-Secret") or request.headers.get("X-Service-Token")
        # Also allow valid internal Bearer token
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
            if token == GATEWAY_SECRET:
                auth_key = token

        if not auth_key or auth_key != GATEWAY_SECRET:
            return jsonify({
                "error": "Forbidden",
                "message": "Access denied: valid internal gateway credentials required.",
            }), 403
        return f(*args, **kwargs)
    return decorated


# ==============================================================================
# MONITORING LIFECYCLE ENDPOINTS
# ==============================================================================

@monitoring_bp.route("/equipment/<machine_id>/monitoring/activate", methods=["POST"])
@login_required
@roles_required(*MONITORING_MANAGE_ROLES)
def activate_monitoring(machine_id: str):
    """Activate continuous OPC UA monitoring for a registered machine (Requirement 3)."""
    machine = db.session.get(Machine, machine_id)
    if not machine or machine.organization_id != g.current_org_id:
        return jsonify({"error": "Not Found", "message": "Equipment not found or access denied."}), 404

    data = request.get_json(silent=True) or {}
    endpoint_url = data.get("endpoint_url")
    user_id = g.current_user.id if hasattr(g, "current_user") and g.current_user else None

    try:
        session_data = MonitoringLifecycleManager.activate_monitoring(
            machine_id=machine_id,
            organization_id=g.current_org_id,
            user_id=user_id,
            endpoint_url=endpoint_url,
        )
        return jsonify({
            "message": "Monitoring activation initiated.",
            "session": session_data,
        }), 200
    except ValueError as e:
        return jsonify({"error": "Activation Rejected", "message": str(e)}), 400
    except Exception as e:
        logger.error(f"Error activating monitoring for {machine_id}: {e}")
        return jsonify({"error": "Internal Error", "message": str(e)}), 500


@monitoring_bp.route("/equipment/<machine_id>/monitoring/deactivate", methods=["POST"])
@login_required
@roles_required(*MONITORING_MANAGE_ROLES)
def deactivate_monitoring(machine_id: str):
    """Deactivate continuous monitoring gracefully (Requirement 3)."""
    machine = db.session.get(Machine, machine_id)
    if not machine or machine.organization_id != g.current_org_id:
        return jsonify({"error": "Not Found", "message": "Equipment not found or access denied."}), 404

    user_id = g.current_user.id if hasattr(g, "current_user") and g.current_user else None

    try:
        session_data = MonitoringLifecycleManager.deactivate_monitoring(
            machine_id=machine_id,
            organization_id=g.current_org_id,
            user_id=user_id,
        )
        return jsonify({
            "message": "Monitoring stopped successfully.",
            "session": session_data,
        }), 200
    except ValueError as e:
        return jsonify({"error": "Deactivation Error", "message": str(e)}), 400
    except Exception as e:
        logger.error(f"Error deactivating monitoring for {machine_id}: {e}")
        return jsonify({"error": "Internal Error", "message": str(e)}), 500


@monitoring_bp.route("/equipment/<machine_id>/monitoring/status", methods=["GET"])
@login_required
def get_monitoring_status(machine_id: str):
    """Get real-time monitoring state, preconditions, and gateway health."""
    machine = db.session.get(Machine, machine_id)
    if not machine or machine.organization_id != g.current_org_id:
        return jsonify({"error": "Not Found", "message": "Equipment not found or access denied."}), 404

    try:
        status_data = MonitoringLifecycleManager.get_status(machine_id, g.current_org_id)
        return jsonify(status_data), 200
    except Exception as e:
        logger.error(f"Error getting monitoring status for {machine_id}: {e}")
        return jsonify({"error": "Internal Error", "message": str(e)}), 500


# ==============================================================================
# SENSOR READINGS ENDPOINTS
# ==============================================================================

@monitoring_bp.route("/equipment/<machine_id>/readings/latest", methods=["GET"])
@login_required
def get_latest_readings(machine_id: str):
    """Retrieve latest telemetry readings for all mapped signals with freshness indicators."""
    machine = db.session.get(Machine, machine_id)
    if not machine or machine.organization_id != g.current_org_id:
        return jsonify({"error": "Not Found", "message": "Equipment not found or access denied."}), 404

    readings = IngestionService.get_latest_readings(machine_id, g.current_org_id)
    return jsonify({
        "machine_id": machine_id,
        "count": len(readings),
        "readings": readings,
        "simulator_flag": True,
    }), 200


@monitoring_bp.route("/equipment/<machine_id>/readings/history", methods=["GET"])
@login_required
def get_historical_readings(machine_id: str):
    """Retrieve bounded historical time-series telemetry for trending charts."""
    machine = db.session.get(Machine, machine_id)
    if not machine or machine.organization_id != g.current_org_id:
        return jsonify({"error": "Not Found", "message": "Equipment not found or access denied."}), 404

    signal_id = request.args.get("signal_id")
    start_str = request.args.get("start_time")
    end_str = request.args.get("end_time")
    limit = int(request.args.get("limit", 200))

    start_dt = None
    if start_str:
        try:
            start_dt = datetime.fromisoformat(start_str.strip().replace(" ", "+").replace("Z", "+00:00"))
        except ValueError:
            logger.warning(f"Invalid start_time format: {start_str}")

    end_dt = None
    if end_str:
        try:
            end_dt = datetime.fromisoformat(end_str.strip().replace(" ", "+").replace("Z", "+00:00"))
        except ValueError:
            logger.warning(f"Invalid end_time format: {end_str}")

    readings = IngestionService.get_historical_readings(
        machine_id=machine_id,
        organization_id=g.current_org_id,
        signal_id=signal_id,
        start_time=start_dt,
        end_time=end_dt,
        limit=limit,
    )

    return jsonify({
        "machine_id": machine_id,
        "count": len(readings),
        "readings": readings,
        "simulator_flag": True,
    }), 200


# ==============================================================================
# GATEWAY HEALTH & INTERNAL INGESTION
# ==============================================================================

@monitoring_bp.route("/gateways/<gateway_id>/health", methods=["GET"])
@login_required
def get_gateway_health(gateway_id: str):
    """Retrieve gateway connectivity and buffering statistics."""
    record = GatewayHealthRecord.query.filter_by(gateway_id=gateway_id).first()
    if not record:
        return jsonify({
            "gateway_id": gateway_id,
            "connection_status": "ONLINE",
            "queue_depth": 0,
            "buffered_readings": 0,
            "dropped_readings": 0,
            "last_heartbeat": datetime.now(timezone.utc).isoformat(),
        }), 200
    return jsonify(record.to_dict()), 200


@monitoring_bp.route("/internal/ingestion/readings", methods=["POST"])
@internal_gateway_required
def internal_ingest_readings():
    """Secure internal service endpoint for edge gateways to push telemetry batches."""
    payload = request.get_json(silent=True) or {}
    readings = payload.get("readings", [])
    gateway_id = payload.get("gateway_id", "gw-default")
    batch_id = payload.get("batch_identifier")

    if not isinstance(readings, list) or not readings:
        return jsonify({"error": "Validation Error", "message": "Field 'readings' must be a non-empty array."}), 400

    try:
        result = IngestionService.ingest_batch(
            gateway_id=gateway_id,
            readings_data=readings,
            batch_identifier=batch_id,
        )
        return jsonify({
            "message": "Batch ingested successfully.",
            "metrics": result,
        }), 201
    except Exception as e:
        logger.error(f"[InternalIngestion] Ingestion error: {e}")
        return jsonify({"error": "Ingestion Failed", "message": str(e)}), 500

