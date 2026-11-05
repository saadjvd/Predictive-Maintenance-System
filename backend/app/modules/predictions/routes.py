from flask import Blueprint, request, jsonify, g
from app.security.decorators import login_required
from app.modules.predictions.services import PredictionService

predictions_bp = Blueprint("predictions", __name__)


# =============================================================================
# 1. Failure Modes
# =============================================================================

@predictions_bp.route("/failure-modes", methods=["GET"])
@login_required
def get_failure_modes():
    """List standard and organization-specific failure modes."""
    org_id = g.current_org_id
    category_id = request.args.get("category_id")
    try:
        modes = PredictionService.get_failure_modes(org_id, category_id=category_id)
        return jsonify(modes), 200
    except Exception as e:
        return jsonify({"error": f"Failed to retrieve failure modes: {str(e)}"}), 500


@predictions_bp.route("/failure-modes", methods=["POST"])
@login_required
def create_failure_mode():
    """Create a custom failure mode for the organization."""
    org_id = g.current_org_id
    data = request.get_json(silent=True) or {}
    try:
        mode = PredictionService.create_failure_mode(org_id, data)
        return jsonify(mode), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"Failed to create failure mode: {str(e)}"}), 500


# =============================================================================
# 2. Failure Records
# =============================================================================

@predictions_bp.route("/equipment/<string:machine_id>/failure-records", methods=["GET"])
@login_required
def get_failure_records(machine_id):
    """List failure and maintenance records for equipment."""
    org_id = g.current_org_id
    component_id = request.args.get("component_id")
    limit = request.args.get("limit", 100, type=int)
    try:
        records = PredictionService.get_failure_records(
            organization_id=org_id,
            machine_id=machine_id,
            component_id=component_id,
            limit=min(limit, 500),
        )
        return jsonify(records), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"Failed to retrieve failure records: {str(e)}"}), 500


@predictions_bp.route("/equipment/<string:machine_id>/failure-records", methods=["POST"])
@login_required
def create_failure_record(machine_id):
    """Log a failure or maintenance event for equipment."""
    org_id = g.current_org_id
    user_id = g.current_user.id if hasattr(g, "current_user") and g.current_user else None
    data = request.get_json(silent=True) or {}
    try:
        record = PredictionService.create_failure_record(
            organization_id=org_id,
            machine_id=machine_id,
            user_id=user_id,
            data=data,
        )
        return jsonify(record), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"Failed to create failure record: {str(e)}"}), 500


@predictions_bp.route("/failure-records/<string:record_id>/verify", methods=["PATCH"])
@login_required
def verify_failure_record(record_id):
    """Maintenance engineer verification of a failure/maintenance record."""
    org_id = g.current_org_id
    user_id = g.current_user.id if hasattr(g, "current_user") and g.current_user else None
    data = request.get_json(silent=True) or {}
    status = data.get("verification_status")
    if not status:
        return jsonify({"error": "'verification_status' is required."}), 400

    try:
        updated = PredictionService.verify_failure_record(
            organization_id=org_id,
            record_id=record_id,
            user_id=user_id,
            status=status,
            confirmed_root_cause=data.get("confirmed_root_cause"),
            maintenance_action=data.get("maintenance_action"),
        )
        return jsonify(updated), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"Failed to verify failure record: {str(e)}"}), 500


# =============================================================================
# 3. Model Eligibility
# =============================================================================

@predictions_bp.route("/equipment/<string:machine_id>/prediction-eligibility", methods=["GET"])
@login_required
def get_prediction_eligibility(machine_id):
    """Evaluate whether equipment is eligible for failure prediction and RUL estimation."""
    org_id = g.current_org_id
    try:
        eligibility = PredictionService.get_machine_eligibility(
            organization_id=org_id,
            machine_id=machine_id,
        )
        return jsonify(eligibility), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"Eligibility evaluation failed: {str(e)}"}), 500


# =============================================================================
# 4. Model Training & Registry
# =============================================================================

@predictions_bp.route("/equipment/<string:machine_id>/predictive-models/train", methods=["POST"])
@login_required
def train_predictive_model(machine_id):
    """Train, calibrate, and validate a supervised predictive model."""
    org_id = g.current_org_id
    user_id = g.current_user.id if hasattr(g, "current_user") and g.current_user else None
    data = request.get_json(silent=True) or {}

    failure_mode_id = data.get("failure_mode_id")
    if not failure_mode_id:
        return jsonify({"error": "'failure_mode_id' is required."}), 400

    algorithm = data.get("algorithm", "RANDOM_FOREST")
    prediction_horizon_hours = data.get("prediction_horizon_hours", 168)
    hyperparameters = data.get("hyperparameters", {})

    try:
        result = PredictionService.train_predictive_model(
            organization_id=org_id,
            machine_id=machine_id,
            user_id=user_id,
            failure_mode_id=failure_mode_id,
            algorithm=algorithm,
            prediction_horizon_hours=prediction_horizon_hours,
            hyperparameters=hyperparameters,
        )
        return jsonify(result), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"Model training failed: {str(e)}"}), 500


@predictions_bp.route("/equipment/<string:machine_id>/predictive-models", methods=["GET"])
@login_required
def get_predictive_models(machine_id):
    """List predictive models and version artifacts for equipment."""
    org_id = g.current_org_id
    try:
        models = PredictionService.get_predictive_models(
            organization_id=org_id,
            machine_id=machine_id,
        )
        return jsonify(models), 200
    except Exception as e:
        return jsonify({"error": f"Failed to retrieve predictive models: {str(e)}"}), 500


@predictions_bp.route("/predictive-models/<string:version_id>/approve", methods=["POST"])
@login_required
def approve_model_version(version_id):
    """Approve a trained and calibrated model version."""
    org_id = g.current_org_id
    user_id = g.current_user.id if hasattr(g, "current_user") and g.current_user else None
    try:
        approved = PredictionService.approve_model_version(
            organization_id=org_id,
            version_id=version_id,
            user_id=user_id,
        )
        return jsonify(approved), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"Failed to approve model: {str(e)}"}), 500


@predictions_bp.route("/predictive-models/<string:version_id>/activate", methods=["POST"])
@login_required
def activate_model_version(version_id):
    """Activate an approved model version for live prediction inference."""
    org_id = g.current_org_id
    user_id = g.current_user.id if hasattr(g, "current_user") and g.current_user else None
    try:
        activated = PredictionService.activate_model_version(
            organization_id=org_id,
            version_id=version_id,
            user_id=user_id,
        )
        return jsonify(activated), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"Failed to activate model: {str(e)}"}), 500


# =============================================================================
# 5. Prediction Execution & History
# =============================================================================

@predictions_bp.route("/equipment/<string:machine_id>/predictions/evaluate", methods=["POST"])
@login_required
def evaluate_equipment_predictions(machine_id):
    """Trigger on-demand calibrated risk and RUL evaluation."""
    org_id = g.current_org_id
    try:
        predictions = PredictionService.evaluate_predictions(
            organization_id=org_id,
            machine_id=machine_id,
        )
        return jsonify({
            "message": "Prediction evaluation completed",
            "predictions": predictions,
        }), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"Prediction evaluation failed: {str(e)}"}), 500


@predictions_bp.route("/equipment/<string:machine_id>/predictions", methods=["GET"])
@login_required
def get_equipment_predictions(machine_id):
    """Get latest and historical predictions for equipment."""
    org_id = g.current_org_id
    limit = request.args.get("limit", 50, type=int)
    try:
        predictions = PredictionService.get_equipment_predictions(
            organization_id=org_id,
            machine_id=machine_id,
            limit=min(limit, 200),
        )
        return jsonify(predictions), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"Failed to retrieve predictions: {str(e)}"}), 500


@predictions_bp.route("/predictions/<string:prediction_id>", methods=["GET"])
@login_required
def get_prediction_detail(prediction_id):
    """Get detailed prediction with evidence breakdown."""
    org_id = g.current_org_id
    try:
        detail = PredictionService.get_prediction_detail(
            organization_id=org_id,
            prediction_id=prediction_id,
        )
        return jsonify(detail), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"Failed to retrieve prediction detail: {str(e)}"}), 500


# =============================================================================
# 6. Predictive Alerts
# =============================================================================

@predictions_bp.route("/predictive-alerts", methods=["GET"])
@login_required
def get_predictive_alerts():
    """List actionable predictive maintenance alerts."""
    org_id = g.current_org_id
    machine_id = request.args.get("machine_id")
    status = request.args.get("status")
    limit = request.args.get("limit", 100, type=int)
    try:
        alerts = PredictionService.get_predictive_alerts(
            organization_id=org_id,
            machine_id=machine_id,
            status=status,
            limit=min(limit, 200),
        )
        return jsonify(alerts), 200
    except Exception as e:
        return jsonify({"error": f"Failed to retrieve predictive alerts: {str(e)}"}), 500


@predictions_bp.route("/predictive-alerts/<string:alert_id>/review", methods=["POST"])
@login_required
def review_predictive_alert(alert_id):
    """Acknowledge, investigate, resolve, or dismiss a predictive alert."""
    org_id = g.current_org_id
    user_id = g.current_user.id if hasattr(g, "current_user") and g.current_user else None
    data = request.get_json(silent=True) or {}
    new_status = data.get("status")
    if not new_status:
        return jsonify({"error": "'status' is required."}), 400

    engineer_notes = data.get("engineer_review_notes")
    try:
        alert = PredictionService.review_predictive_alert(
            organization_id=org_id,
            alert_id=alert_id,
            user_id=user_id,
            new_status=new_status,
            engineer_notes=engineer_notes,
        )
        return jsonify(alert), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"Failed to review predictive alert: {str(e)}"}), 500
