"""PharmaPredict AI — Flask Blueprint Routes for Factory Pilots."""
from flask import Blueprint, request, jsonify, g
from app.security.decorators import login_required, roles_required
from app.models.user import Role
from app.modules.pilots.services import PilotService
from app.modules.pilots.schemas import (
    CreatePilotSchema,
    UpdatePilotSchema,
    AssignEquipmentSchema,
    SubmitApprovalSchema,
    SubmitEngineerFeedbackSchema,
    ModelEvaluationSchema,
)

pilots_bp = Blueprint("pilots", __name__)


# =============================================================================
# PILOT CRUD & LIFECYCLE
# =============================================================================

@pilots_bp.route("/pilots", methods=["GET"])
@login_required
def list_pilots():
    """Lists pilots for the authenticated organization."""
    org_id = g.current_org_id
    site_id = request.args.get("site_id")
    status = request.args.get("status")
    limit = request.args.get("limit", 50, type=int)
    offset = request.args.get("offset", 0, type=int)

    try:
        pilots = PilotService.list_pilots(
            organization_id=org_id,
            site_id=site_id,
            status=status,
            limit=limit,
            offset=offset,
        )
        return jsonify(pilots), 200
    except Exception as e:
        return jsonify({"error": f"Failed to list pilots: {str(e)}"}), 500


@pilots_bp.route("/pilots", methods=["POST"])
@login_required
@roles_required(Role.ORG_ADMIN, Role.MAINTENANCE_MANAGER, Role.MAINTENANCE_ENGINEER, Role.PLATFORM_ADMIN)
def create_pilot():
    """Creates a new pilot in DRAFT status with initial GAMP 5 readiness checklist."""
    org_id = g.current_org_id
    user_id = g.current_user.id if hasattr(g, "current_user") and g.current_user else None
    data = request.get_json(silent=True) or {}

    try:
        validated = CreatePilotSchema(**data)
    except Exception as e:
        return jsonify({"error": "Validation failed", "details": str(e)}), 400

    try:
        pilot = PilotService.create_pilot(
            organization_id=org_id,
            site_id=data["site_id"],
            pilot_name=data["pilot_name"],
            description=data.get("description"),
            objectives=data.get("objectives"),
            monitoring_mode=data.get("monitoring_mode", "SHADOW"),
            planned_start_date=data.get("planned_start_date"),
            planned_end_date=data.get("planned_end_date"),
            evaluation_criteria=data.get("evaluation_criteria"),
            target_kpis=data.get("target_kpis"),
            responsible_engineer_id=data.get("responsible_engineer_id"),
            created_by_id=user_id,
        )
        return jsonify(pilot), 201
    except Exception as e:
        return jsonify({"error": f"Failed to create pilot: {str(e)}"}), 500


@pilots_bp.route("/pilots/<string:pilot_id>", methods=["GET"])
@login_required
def get_pilot(pilot_id):
    """Retrieves full details of a pilot including equipment, approvals, and checks."""
    org_id = g.current_org_id
    try:
        details = PilotService.get_pilot_details(pilot_id, org_id)
        return jsonify(details), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"Failed to retrieve pilot: {str(e)}"}), 500


@pilots_bp.route("/pilots/<string:pilot_id>", methods=["PATCH"])
@login_required
@roles_required(Role.ORG_ADMIN, Role.MAINTENANCE_MANAGER, Role.MAINTENANCE_ENGINEER, Role.PLATFORM_ADMIN)
def update_pilot(pilot_id):
    """Updates pilot metadata."""
    org_id = g.current_org_id
    data = request.get_json(silent=True) or {}

    try:
        validated = UpdatePilotSchema(**data)
    except Exception as e:
        return jsonify({"error": "Validation failed", "details": str(e)}), 400

    try:
        updated = PilotService.update_pilot(pilot_id, org_id, **data)
        return jsonify(updated), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"Failed to update pilot: {str(e)}"}), 500


# =============================================================================
# EQUIPMENT ASSIGNMENT
# =============================================================================

@pilots_bp.route("/pilots/<string:pilot_id>/equipment", methods=["POST"])
@login_required
@roles_required(Role.ORG_ADMIN, Role.MAINTENANCE_MANAGER, Role.MAINTENANCE_ENGINEER, Role.PLATFORM_ADMIN)
def assign_equipment(pilot_id):
    """Enrolls equipment in a factory pilot."""
    org_id = g.current_org_id
    data = request.get_json(silent=True) or {}

    try:
        validated = AssignEquipmentSchema(**data)
    except Exception as e:
        return jsonify({"error": "Validation failed", "details": str(e)}), 400

    try:
        results = PilotService.assign_equipment(
            pilot_id=pilot_id,
            organization_id=org_id,
            machine_ids=[str(mid) for mid in data["machine_ids"]],
            monitoring_mode=data.get("monitoring_mode", "SHADOW"),
        )
        return jsonify(results), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"Failed to assign equipment: {str(e)}"}), 500


@pilots_bp.route("/pilots/<string:pilot_id>/equipment", methods=["GET"])
@login_required
def list_pilot_equipment(pilot_id):
    """Lists equipment assigned to the pilot."""
    org_id = g.current_org_id
    try:
        details = PilotService.get_pilot_details(pilot_id, org_id)
        return jsonify(details.get("equipment", [])), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"Failed to list pilot equipment: {str(e)}"}), 500


# =============================================================================
# READINESS REVIEWS & APPROVALS
# =============================================================================

@pilots_bp.route("/pilots/<string:pilot_id>/readiness-review", methods=["POST"])
@login_required
def perform_readiness_review(pilot_id):
    """Evaluates readiness checklist items and updates pilot status."""
    org_id = g.current_org_id
    user_id = g.current_user.id if hasattr(g, "current_user") and g.current_user else None
    try:
        result = PilotService.perform_readiness_review(pilot_id, org_id, user_id)
        return jsonify(result), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"Failed to perform readiness review: {str(e)}"}), 500


@pilots_bp.route("/pilots/<string:pilot_id>/readiness-checks/<string:check_id>", methods=["PATCH"])
@login_required
@roles_required(Role.ORG_ADMIN, Role.MAINTENANCE_MANAGER, Role.MAINTENANCE_ENGINEER, Role.PLATFORM_ADMIN)
def update_readiness_check(pilot_id, check_id):
    """Updates an individual readiness check item."""
    org_id = g.current_org_id
    user_id = g.current_user.id if hasattr(g, "current_user") and g.current_user else None
    data = request.get_json(silent=True) or {}

    status = data.get("status")
    if not status:
        return jsonify({"error": "status is required"}), 400

    try:
        result = PilotService.update_readiness_check(
            pilot_id=pilot_id,
            check_id=check_id,
            organization_id=org_id,
            status=status,
            evidence_summary=data.get("evidence_summary"),
            reviewer_id=user_id,
        )
        return jsonify(result), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"Failed to update readiness check: {str(e)}"}), 500


@pilots_bp.route("/pilots/<string:pilot_id>/approve", methods=["POST"])
@login_required
@roles_required(Role.ORG_ADMIN, Role.MAINTENANCE_MANAGER, Role.MAINTENANCE_ENGINEER, Role.PLATFORM_ADMIN)
def submit_approval(pilot_id):
    """Submits multi-department authorization (Engineering, Security, QA)."""
    org_id = g.current_org_id
    user_id = g.current_user.id if hasattr(g, "current_user") and g.current_user else None
    data = request.get_json(silent=True) or {}

    try:
        validated = SubmitApprovalSchema(**data)
    except Exception as e:
        return jsonify({"error": "Validation failed", "details": str(e)}), 400

    try:
        approval = PilotService.submit_approval(
            pilot_id=pilot_id,
            organization_id=org_id,
            approver_id=user_id,
            approval_type=data["approval_type"],
            decision=data["decision"],
            comments=data.get("comments"),
            signature_token=data.get("signature_token"),
        )
        return jsonify(approval), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"Failed to record approval: {str(e)}"}), 500


@pilots_bp.route("/pilots/<string:pilot_id>/activate", methods=["POST"])
@login_required
@roles_required(Role.ORG_ADMIN, Role.MAINTENANCE_MANAGER, Role.MAINTENANCE_ENGINEER, Role.PLATFORM_ADMIN)
def activate_pilot(pilot_id):
    """Enforces authorization check and activates pilot in strict SHADOW MODE."""
    org_id = g.current_org_id
    user_id = g.current_user.id if hasattr(g, "current_user") and g.current_user else None
    try:
        res = PilotService.activate_pilot(pilot_id, org_id, user_id)
        return jsonify(res), 200
    except PermissionError as e:
        return jsonify({"error": str(e), "code": "APPROVAL_REQUIRED"}), 403
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"Failed to activate pilot: {str(e)}"}), 500


@pilots_bp.route("/pilots/<string:pilot_id>/pause", methods=["POST"])
@login_required
def pause_pilot(pilot_id):
    org_id = g.current_org_id
    user_id = g.current_user.id if hasattr(g, "current_user") and g.current_user else None
    try:
        res = PilotService.pause_pilot(pilot_id, org_id, user_id)
        return jsonify(res), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"Failed to pause pilot: {str(e)}"}), 500


@pilots_bp.route("/pilots/<string:pilot_id>/complete", methods=["POST"])
@login_required
def complete_pilot(pilot_id):
    org_id = g.current_org_id
    user_id = g.current_user.id if hasattr(g, "current_user") and g.current_user else None
    try:
        res = PilotService.complete_pilot(pilot_id, org_id, user_id)
        return jsonify(res), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"Failed to complete pilot: {str(e)}"}), 500


# =============================================================================
# ENGINEER FEEDBACK & VALIDATION
# =============================================================================

@pilots_bp.route("/pilots/<string:pilot_id>/feedback", methods=["POST"])
@pilots_bp.route("/diagnostics/<string:session_id>/feedback", methods=["POST"])
@login_required
def submit_engineer_feedback(pilot_id=None, session_id=None):
    """Submits certified maintenance engineer feedback on diagnostic sessions."""
    org_id = g.current_org_id
    user_id = g.current_user.id if hasattr(g, "current_user") and g.current_user else None
    data = request.get_json(silent=True) or {}

    diag_id = session_id or data.get("diagnostic_session_id")
    if not diag_id:
        return jsonify({"error": "diagnostic_session_id is required"}), 400

    # If pilot_id is not in URL, locate active pilot for this organization
    target_pilot_id = pilot_id or data.get("pilot_id")
    if not target_pilot_id:
        active_pilot = PilotService.list_pilots(org_id, limit=1)
        if active_pilot:
            target_pilot_id = active_pilot[0]["id"]
        else:
            return jsonify({"error": "pilot_id is required"}), 400

    try:
        fb = PilotService.submit_engineer_feedback(
            pilot_id=target_pilot_id,
            organization_id=org_id,
            diagnostic_session_id=str(diag_id),
            engineer_id=user_id,
            assessment=data["assessment"],
            anomaly_event_id=str(data["anomaly_event_id"]) if data.get("anomaly_event_id") else None,
            verified_root_cause=data.get("verified_root_cause"),
            inspection_findings=data.get("inspection_findings"),
            action_taken=data.get("action_taken"),
            actual_outcome=data.get("actual_outcome"),
            comments=data.get("comments"),
            false_alarm_flag=data.get("false_alarm_flag", False),
            reference_label=data.get("reference_label", "UNVERIFIED"),
        )
        return jsonify(fb), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"Failed to record engineer feedback: {str(e)}"}), 500


@pilots_bp.route("/pilots/<string:pilot_id>/feedback", methods=["GET"])
@login_required
def list_engineer_feedback(pilot_id):
    org_id = g.current_org_id
    try:
        feedbacks = PilotService.list_engineer_feedback(pilot_id, org_id)
        return jsonify(feedbacks), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"Failed to list feedback: {str(e)}"}), 500


# =============================================================================
# METRICS & REPORTS
# =============================================================================

@pilots_bp.route("/pilots/<string:pilot_id>/metrics", methods=["GET"])
@login_required
def get_pilot_metrics(pilot_id):
    """Retrieves empirical pilot KPIs."""
    org_id = g.current_org_id
    try:
        metrics = PilotService.get_pilot_metrics(pilot_id, org_id)
        return jsonify(metrics), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"Failed to compute pilot metrics: {str(e)}"}), 500


@pilots_bp.route("/pilots/<string:pilot_id>/report", methods=["POST"])
@login_required
@roles_required(Role.ORG_ADMIN, Role.MAINTENANCE_MANAGER, Role.MAINTENANCE_ENGINEER, Role.PLATFORM_ADMIN)
def generate_pilot_report(pilot_id):
    """Generates an executive Go/No-Go report."""
    org_id = g.current_org_id
    user_id = g.current_user.id if hasattr(g, "current_user") and g.current_user else None
    data = request.get_json(silent=True) or {}
    report_type = data.get("report_type", "FINAL_PILOT_REPORT")

    try:
        report = PilotService.generate_pilot_report(pilot_id, org_id, user_id, report_type)
        return jsonify(report), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"Failed to generate pilot report: {str(e)}"}), 500


@pilots_bp.route("/pilots/<string:pilot_id>/evaluations", methods=["GET"])
@login_required
def get_pilot_evaluations(pilot_id):
    """Retrieves model and agent evaluation metrics for the pilot."""
    org_id = g.current_org_id
    try:
        pilot = PilotService.get_pilot_details(pilot_id, org_id)
        # Fetch model and agent evaluations
        from app.models.pilot import PilotModelEvaluation, PilotAgentEvaluation
        models = [m.to_dict() for m in PilotModelEvaluation.query.filter_by(pilot_id=pilot_id).all()]
        agents = [a.to_dict() for a in PilotAgentEvaluation.query.filter_by(pilot_id=pilot_id).all()]
        return jsonify({"model_evaluations": models, "agent_evaluations": agents}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"Failed to get evaluations: {str(e)}"}), 500
