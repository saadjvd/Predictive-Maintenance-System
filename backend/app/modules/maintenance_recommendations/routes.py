"""Flask routes for Maintenance Recommendations and Human Approvals."""
from flask import Blueprint, request, jsonify, g
from app.security.decorators import login_required
from app.modules.maintenance_recommendations.services import MaintenanceRecommendationService

recommendations_bp = Blueprint("recommendations", __name__)


@recommendations_bp.route("/maintenance/recommendations", methods=["GET"])
@login_required
def list_recommendations():
    """Lists maintenance recommendations for the current organization."""
    org_id = g.current_org_id
    machine_id = request.args.get("machine_id")
    priority = request.args.get("priority")
    approval_status = request.args.get("approval_status")
    session_id = request.args.get("session_id")
    limit = request.args.get("limit", 100, type=int)

    try:
        recs = MaintenanceRecommendationService.list_recommendations(
            organization_id=org_id,
            machine_id=machine_id,
            priority=priority,
            approval_status=approval_status,
            session_id=session_id,
            limit=limit,
        )
        return jsonify(recs), 200
    except Exception as e:
        return jsonify({"error": f"Failed to list recommendations: {str(e)}"}), 500


@recommendations_bp.route("/maintenance/recommendations/<string:rec_id>", methods=["GET"])
@login_required
def get_recommendation(rec_id):
    """Retrieves a single maintenance recommendation."""
    org_id = g.current_org_id
    try:
        rec = MaintenanceRecommendationService.get_recommendation(rec_id, org_id)
        return jsonify(rec), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"Failed to retrieve recommendation: {str(e)}"}), 500


@recommendations_bp.route("/maintenance/recommendations/<string:rec_id>/approve", methods=["POST"])
@login_required
def approve_recommendation(rec_id):
    """Authorizes an AI maintenance recommendation and creates a work order reference."""
    org_id = g.current_org_id
    user_id = g.current_user.id if hasattr(g, "current_user") and g.current_user else "anonymous_engineer"
    data = request.get_json(silent=True) or {}

    notes = data.get("notes")
    technician_id = data.get("assigned_technician_id")
    scheduled_for = data.get("scheduled_for")

    try:
        result = MaintenanceRecommendationService.approve_recommendation(
            recommendation_id=rec_id,
            organization_id=org_id,
            user_id=user_id,
            notes=notes,
            assigned_technician_id=technician_id,
            scheduled_for=scheduled_for,
        )
        return jsonify(result), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Failed to approve recommendation: {str(e)}"}), 500


@recommendations_bp.route("/maintenance/recommendations/<string:rec_id>/reject", methods=["POST"])
@login_required
def reject_recommendation(rec_id):
    """Rejects a recommendation with a mandatory justification reason."""
    org_id = g.current_org_id
    user_id = g.current_user.id if hasattr(g, "current_user") and g.current_user else "anonymous_engineer"
    data = request.get_json(silent=True) or {}

    reason = data.get("reason")
    if not reason:
        return jsonify({"error": "reason is required for GMP rejection audit log"}), 400

    notes = data.get("notes")

    try:
        result = MaintenanceRecommendationService.reject_recommendation(
            recommendation_id=rec_id,
            organization_id=org_id,
            user_id=user_id,
            rejection_reason=reason,
            notes=notes,
        )
        return jsonify(result), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Failed to reject recommendation: {str(e)}"}), 500

