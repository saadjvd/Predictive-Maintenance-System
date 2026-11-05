from flask import Blueprint, jsonify, g
from app.security import login_required
from app.modules.operating_context.services import OperatingContextService

operating_context_bp = Blueprint("operating_context", __name__)


@operating_context_bp.route("/equipment/<machine_id>/operating-context", methods=["GET"])
@login_required
def get_equipment_operating_context(machine_id: str):
    """Retrieve machine current operating regime (IDLE, STARTUP, RUNNING, HIGH_LOAD, etc.)."""
    try:
        context = OperatingContextService.get_current_operating_context(
            machine_id=machine_id, organization_id=g.current_org_id
        )
        return jsonify(context), 200
    except ValueError as e:
        return jsonify({"error": "Not Found", "message": str(e)}), 404
    except Exception as e:
        return jsonify({"error": "Internal Error", "message": str(e)}), 500

