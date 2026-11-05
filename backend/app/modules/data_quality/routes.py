from flask import Blueprint, jsonify, request, g
from app.security import login_required
from app.modules.data_quality.services import DataQualityService

data_quality_bp = Blueprint("data_quality", __name__)


@data_quality_bp.route("/equipment/<machine_id>/data-quality", methods=["GET"])
@login_required
def get_equipment_data_quality(machine_id: str):
    """Assess and return live data quality across all signals of an equipment asset (Requirement 5)."""
    try:
        summary = DataQualityService.evaluate_machine_quality(
            machine_id=machine_id, organization_id=g.current_org_id
        )
        return jsonify(summary), 200
    except ValueError as e:
        return jsonify({"error": "Not Found", "message": str(e)}), 404
    except Exception as e:
        return jsonify({"error": "Internal Error", "message": str(e)}), 500


@data_quality_bp.route("/equipment/<machine_id>/data-quality/events", methods=["GET"])
@login_required
def get_equipment_quality_events(machine_id: str):
    """Retrieve historical data quality events and issue logs."""
    limit = int(request.args.get("limit", 50))
    try:
        events = DataQualityService.get_quality_events(
            machine_id=machine_id, organization_id=g.current_org_id, limit=limit
        )
        return jsonify({
            "machine_id": machine_id,
            "count": len(events),
            "events": events,
        }), 200
    except Exception as e:
        return jsonify({"error": "Internal Error", "message": str(e)}), 500

