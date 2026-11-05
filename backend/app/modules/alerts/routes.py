from flask import Blueprint, request, jsonify, g
from app.security.decorators import login_required, roles_required
from app.modules.alerts.services import AlertService

alerts_bp = Blueprint("alerts", __name__, url_prefix="/alerts")


@alerts_bp.route("", methods=["GET"])
@login_required
def get_alerts():
    """List organization equipment alerts with optional filtering."""
    org_id = g.current_org_id
    machine_id = request.args.get("machine_id")
    status = request.args.get("status")
    severity = request.args.get("severity")
    limit = request.args.get("limit", 50, type=int)

    alerts = AlertService.get_organization_alerts(
        organization_id=org_id,
        machine_id=machine_id,
        status=status,
        severity=severity,
        limit=min(limit, 200),
    )
    return jsonify({"alerts": alerts, "count": len(alerts)}), 200


@alerts_bp.route("/<string:alert_id>", methods=["GET"])
@login_required
def get_alert_detail(alert_id):
    """Get single alert detail with history."""
    org_id = g.current_org_id
    alert = AlertService.get_alert_detail(alert_id, org_id)
    if not alert:
        return jsonify({"error": "Alert not found"}), 404
    return jsonify({"alert": alert}), 200


@alerts_bp.route("/<string:alert_id>/acknowledge", methods=["POST"])
@login_required
def acknowledge_alert(alert_id):
    """Acknowledge an equipment alert."""
    org_id = g.current_org_id
    user_id = g.current_user.id
    data = request.get_json(silent=True) or {}
    notes = data.get("notes")

    try:
        alert = AlertService.acknowledge_alert(
            alert_id=alert_id,
            organization_id=org_id,
            user_id=user_id,
            notes=notes,
        )
        return jsonify({
            "message": "Alert acknowledged successfully",
            "alert": alert.to_dict(),
        }), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"Failed to acknowledge alert: {str(e)}"}), 500


@alerts_bp.route("/<string:alert_id>/status", methods=["PATCH"])
@login_required
def update_alert_status(alert_id):
    """Transition alert status (UNDER_INVESTIGATION, RESOLVED, CLOSED)."""
    org_id = g.current_org_id
    user_id = g.current_user.id
    data = request.get_json(silent=True) or {}
    new_status = data.get("status")
    notes = data.get("notes")

    if not new_status:
        return jsonify({"error": "Missing 'status' in request body"}), 400

    try:
        alert = AlertService.update_alert_status(
            alert_id=alert_id,
            organization_id=org_id,
            user_id=user_id,
            new_status=new_status,
            notes=notes,
        )
        return jsonify({
            "message": f"Alert status updated to {new_status}",
            "alert": alert.to_dict(),
        }), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Failed to update alert status: {str(e)}"}), 500
