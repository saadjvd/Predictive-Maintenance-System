"""Flask Blueprint routes for AI Equipment Diagnostics."""
from flask import Blueprint, request, jsonify, g
from app.security.decorators import login_required
from app.modules.diagnostics.services import DiagnosticService

diagnostics_bp = Blueprint("diagnostics", __name__)


@diagnostics_bp.route("/diagnostics/start", methods=["POST"])
@login_required
def start_diagnostic():
    """Triggers an automated multi-agent diagnostic run for a machine."""
    org_id = g.current_org_id
    user_id = g.current_user.id if hasattr(g, "current_user") and g.current_user else None
    data = request.get_json(silent=True) or {}

    machine_id = data.get("machine_id")
    if not machine_id:
        return jsonify({"error": "machine_id is required"}), 400

    component_id = data.get("component_id")
    trigger_type = data.get("trigger_type", "MANUAL_ENGINEER")
    trigger_event_id = data.get("trigger_event_id")

    try:
        result = DiagnosticService.start_diagnostic_session(
            organization_id=org_id,
            machine_id=machine_id,
            component_id=component_id,
            trigger_type=trigger_type,
            trigger_event_id=trigger_event_id,
            user_id=user_id,
        )
        return jsonify(result), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"Failed to execute diagnostic session: {str(e)}"}), 500


@diagnostics_bp.route("/diagnostics/sessions", methods=["GET"])
@login_required
def list_diagnostic_sessions():
    """Lists diagnostic sessions for the organization or specific machine."""
    org_id = g.current_org_id
    machine_id = request.args.get("machine_id")
    limit = request.args.get("limit", 50, type=int)

    try:
        sessions = DiagnosticService.list_sessions(org_id, machine_id=machine_id, limit=limit)
        return jsonify(sessions), 200
    except Exception as e:
        return jsonify({"error": f"Failed to list diagnostic sessions: {str(e)}"}), 500


@diagnostics_bp.route("/diagnostics/<string:session_id>", methods=["GET"])
@login_required
def get_diagnostic_session(session_id):
    """Retrieves full details of a diagnostic session."""
    org_id = g.current_org_id
    try:
        result = DiagnosticService.get_session(session_id, org_id)
        return jsonify(result), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"Failed to retrieve diagnostic session: {str(e)}"}), 500


@diagnostics_bp.route("/diagnostics/<string:session_id>/status", methods=["GET"])
@login_required
def get_diagnostic_status(session_id):
    """Polls diagnostic session status."""
    org_id = g.current_org_id
    try:
        status = DiagnosticService.get_session_status(session_id, org_id)
        return jsonify(status), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"Failed to get session status: {str(e)}"}), 500


@diagnostics_bp.route("/diagnostics/<string:session_id>/report", methods=["GET"])
@login_required
def get_diagnostic_report(session_id):
    """Retrieves the synthesized diagnostic report for a session."""
    org_id = g.current_org_id
    try:
        report = DiagnosticService.get_session_report(session_id, org_id)
        return jsonify(report), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"Failed to retrieve diagnostic report: {str(e)}"}), 500


@diagnostics_bp.route("/diagnostics/<string:session_id>/agent-executions", methods=["GET"])
@login_required
def get_agent_executions(session_id):
    """Retrieves execution traces for all agents in a diagnostic session."""
    org_id = g.current_org_id
    try:
        executions = DiagnosticService.get_agent_executions(session_id, org_id)
        return jsonify(executions), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"Failed to retrieve agent executions: {str(e)}"}), 500


@diagnostics_bp.route("/diagnostics/<string:session_id>/review", methods=["POST"])
@login_required
def review_diagnostic_session(session_id):
    """Human engineer review of a diagnostic session."""
    org_id = g.current_org_id
    user_id = g.current_user.id if hasattr(g, "current_user") and g.current_user else None
    data = request.get_json(silent=True) or {}

    status = data.get("status")
    if not status:
        return jsonify({"error": "status is required"}), 400

    notes = data.get("notes")

    try:
        result = DiagnosticService.review_session(
            session_id=session_id,
            organization_id=org_id,
            user_id=user_id or "anonymous_engineer",
            review_status=status,
            review_notes=notes,
        )
        return jsonify(result), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Failed to submit review: {str(e)}"}), 500

