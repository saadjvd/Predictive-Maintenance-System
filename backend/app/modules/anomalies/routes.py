from flask import Blueprint, request, jsonify, g
from app.security.decorators import login_required
from app.modules.anomalies.services import AnomalyService

anomalies_bp = Blueprint("anomalies", __name__)


@anomalies_bp.route("/equipment/<string:machine_id>/anomalies", methods=["GET"])
@login_required
def get_equipment_anomalies(machine_id):
    """List anomaly events for an equipment."""
    org_id = g.current_org_id
    severity = request.args.get("severity")
    status = request.args.get("status")
    limit = request.args.get("limit", 50, type=int)

    anomalies = AnomalyService.get_machine_anomalies(
        organization_id=org_id,
        machine_id=machine_id,
        severity=severity,
        status=status,
        limit=min(limit, 200),
    )
    return jsonify({"anomalies": anomalies, "count": len(anomalies)}), 200


@anomalies_bp.route("/anomalies/<string:anomaly_id>", methods=["GET"])
@login_required
def get_anomaly_detail(anomaly_id):
    """Get single anomaly event with evidence trail."""
    org_id = g.current_org_id
    anomaly = AnomalyService.get_anomaly_detail(anomaly_id, org_id)
    if not anomaly:
        return jsonify({"error": "Anomaly event not found"}), 404
    return jsonify({"anomaly": anomaly}), 200


@anomalies_bp.route("/equipment/<string:machine_id>/ml-models", methods=["GET"])
@login_required
def get_equipment_ml_models(machine_id):
    """Get ML model registry and versions for an equipment."""
    org_id = g.current_org_id
    data = AnomalyService.get_machine_ml_models(machine_id, org_id)
    return jsonify(data), 200


@anomalies_bp.route("/equipment/<string:machine_id>/ml-models/train", methods=["POST"])
@login_required
def train_equipment_ml_model(machine_id):
    """Trigger multivariate Isolation Forest model training."""
    org_id = g.current_org_id
    user_id = g.current_user.id
    data = request.get_json(silent=True) or {}
    lookback_days = data.get("lookback_days", 7)

    try:
        result = AnomalyService.train_machine_model(
            organization_id=org_id,
            machine_id=machine_id,
            user_id=user_id,
            lookback_days=lookback_days,
        )
        return jsonify({
            "message": "Isolation Forest model trained and deployed successfully",
            "result": result,
        }), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Failed to train model: {str(e)}"}), 500
