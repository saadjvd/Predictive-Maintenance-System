from flask import Blueprint, jsonify, request, g
from app.models.user import Role
from app.security import login_required, roles_required
from app.modules.baselines.services import BaselineService

baselines_bp = Blueprint("baselines", __name__)

BASELINE_MANAGE_ROLES = [Role.ORG_ADMIN, Role.MAINTENANCE_MANAGER, Role.MAINTENANCE_ENGINEER]
BASELINE_APPROVE_ROLES = [Role.ORG_ADMIN, Role.MAINTENANCE_MANAGER]


@baselines_bp.route("/equipment/<machine_id>/baselines", methods=["GET"])
@login_required
def get_equipment_baselines(machine_id: str):
    """Retrieve all baseline profiles and their versions for an equipment asset."""
    try:
        baselines = BaselineService.get_machine_baselines(
            machine_id=machine_id, organization_id=g.current_org_id
        )
        return jsonify({
            "machine_id": machine_id,
            "count": len(baselines),
            "baselines": baselines,
        }), 200
    except Exception as e:
        return jsonify({"error": "Internal Error", "message": str(e)}), 500


@baselines_bp.route("/equipment/<machine_id>/baselines/build", methods=["POST"])
@roles_required(*BASELINE_MANAGE_ROLES)
def build_equipment_baselines(machine_id: str):
    """Calculate candidate normal operating envelopes from clean historical telemetry (Requirement 7)."""
    data = request.get_json(silent=True) or {}
    operating_state = data.get("operating_state", "RUNNING")
    lookback_hours = int(data.get("lookback_hours", 168))

    try:
        res = BaselineService.build_machine_baselines(
            machine_id=machine_id,
            organization_id=g.current_org_id,
            user_id=g.current_user.id if hasattr(g, "current_user") and g.current_user else None,
            operating_state=operating_state,
            lookback_hours=lookback_hours,
        )
        return jsonify(res), 201
    except ValueError as e:
        return jsonify({"error": "Bad Request", "message": str(e)}), 400
    except Exception as e:
        return jsonify({"error": "Internal Error", "message": str(e)}), 500


@baselines_bp.route("/baselines/<profile_id>/approve", methods=["POST"])
@roles_required(*BASELINE_APPROVE_ROLES)
def approve_baseline_profile(profile_id: str):
    """Authorize and activate a candidate baseline version for condition monitoring."""
    data = request.get_json(silent=True) or {}
    version_id = data.get("version_id")
    if not version_id:
        return jsonify({"error": "Bad Request", "message": "version_id is required."}), 400

    try:
        res = BaselineService.approve_baseline(
            profile_id=profile_id,
            version_id=version_id,
            organization_id=g.current_org_id,
            user_id=g.current_user.id if hasattr(g, "current_user") and g.current_user else None,
        )
        return jsonify(res), 200
    except ValueError as e:
        return jsonify({"error": "Not Found", "message": str(e)}), 404
    except Exception as e:
        return jsonify({"error": "Internal Error", "message": str(e)}), 500

