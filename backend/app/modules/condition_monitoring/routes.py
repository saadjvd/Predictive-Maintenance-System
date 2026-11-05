from flask import Blueprint, request, jsonify, g
from app.security.decorators import login_required
from app.modules.condition_monitoring.services import ConditionMonitoringService
from app.modules.anomalies.services import AnomalyService

condition_monitoring_bp = Blueprint("condition_monitoring", __name__)


@condition_monitoring_bp.route("/equipment/<string:machine_id>/condition", methods=["GET"])
@login_required
def get_equipment_condition(machine_id):
    """Retrieve the latest condition monitoring summary and indicators."""
    org_id = g.current_org_id
    try:
        data = ConditionMonitoringService.get_equipment_condition_summary(
            organization_id=org_id,
            machine_id=machine_id,
        )
        return jsonify(data), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"Failed to get condition summary: {str(e)}"}), 500


@condition_monitoring_bp.route("/equipment/<string:machine_id>/condition/evaluate", methods=["POST"])
@login_required
def trigger_condition_evaluation(machine_id):
    """Trigger an on-demand condition and anomaly evaluation."""
    org_id = g.current_org_id
    data = request.get_json(silent=True) or {}
    recent_minutes = data.get("recent_minutes", 15)

    try:
        result = AnomalyService.evaluate_machine_condition(
            organization_id=org_id,
            machine_id=machine_id,
            recent_minutes=recent_minutes,
        )
        return jsonify({
            "message": "Condition evaluation completed",
            "evaluation": result,
        }), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"Evaluation failed: {str(e)}"}), 500


@condition_monitoring_bp.route("/equipment/<string:machine_id>/condition/history", methods=["GET"])
@login_required
def get_equipment_condition_history(machine_id):
    """Retrieve historical condition observations."""
    org_id = g.current_org_id
    limit = request.args.get("limit", 50, type=int)

    history = ConditionMonitoringService.get_condition_history(
        organization_id=org_id,
        machine_id=machine_id,
        limit=min(limit, 200),
    )
    return jsonify({"history": history, "count": len(history)}), 200
