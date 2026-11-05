import asyncio
import logging
from flask import Blueprint, request, jsonify, g
from app.extensions import db
from app.models.user import Role
from app.models.equipment import Machine
from app.security import login_required, roles_required
from app.modules.signal_mapping.services import SignalMappingService
from app.modules.connectivity.routes import _get_or_create_client

logger = logging.getLogger(__name__)

signals_bp = Blueprint("signals", __name__)

SIGNAL_MANAGE_ROLES = [Role.ORG_ADMIN, Role.MAINTENANCE_MANAGER, Role.MAINTENANCE_ENGINEER]


# ==============================================================================
# SIGNAL DEFINITIONS (CATALOG)
# ==============================================================================

@signals_bp.route("/signals/definitions", methods=["GET"])
@login_required
def list_signal_definitions():
    """Retrieve catalog of standard and organization-custom signal definitions."""
    group = request.args.get("group")
    definitions = SignalMappingService.list_definitions(g.current_org_id, group=group)
    return jsonify({
        "count": len(definitions),
        "definitions": definitions,
    }), 200


@signals_bp.route("/signals/definitions", methods=["POST"])
@login_required
@roles_required(*SIGNAL_MANAGE_ROLES)
def create_custom_definition():
    """Create a new custom signal definition for the tenant organization."""
    data = request.get_json(silent=True) or {}
    if not data.get("signal_code") or not data.get("name"):
        return jsonify({
            "error": "Validation Error",
            "message": "Both 'signal_code' and 'name' are required.",
        }), 400

    try:
        created = SignalMappingService.create_custom_definition(g.current_org_id, data)
        return jsonify({"message": "Custom signal definition created.", "definition": created}), 201
    except ValueError as e:
        return jsonify({"error": "Validation Error", "message": str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating custom definition: {e}")
        return jsonify({"error": "Internal Error", "message": str(e)}), 500


# ==============================================================================
# MACHINE SIGNAL MAPPINGS
# ==============================================================================

@signals_bp.route("/equipment/<machine_id>/signals", methods=["GET"])
@login_required
def list_machine_signals(machine_id: str):
    """List all mapped signals for an equipment asset."""
    machine = db.session.get(Machine, machine_id)
    if not machine or machine.organization_id != g.current_org_id:
        return jsonify({"error": "Not Found", "message": "Equipment not found or access denied."}), 404

    signals = SignalMappingService.list_signals(machine_id, g.current_org_id)
    return jsonify({
        "machine_id": machine_id,
        "count": len(signals),
        "signals": signals,
    }), 200


@signals_bp.route("/equipment/<machine_id>/signals", methods=["POST"])
@login_required
@roles_required(*SIGNAL_MANAGE_ROLES)
def create_machine_signals(machine_id: str):
    """Create one or more signal mappings for an equipment asset."""
    machine = db.session.get(Machine, machine_id)
    if not machine or machine.organization_id != g.current_org_id:
        return jsonify({"error": "Not Found", "message": "Equipment not found or access denied."}), 404

    payload = request.get_json(silent=True) or {}

    # Support single signal or bulk array of signals
    if isinstance(payload, list):
        items = payload
    elif "signals" in payload and isinstance(payload["signals"], list):
        items = payload["signals"]
    else:
        items = [payload]

    # Validate items
    for idx, item in enumerate(items):
        if not item.get("signal_definition_id"):
            return jsonify({
                "error": "Validation Error",
                "message": f"Item at index {idx} is missing 'signal_definition_id'.",
            }), 400
        if not item.get("source_node_id"):
            return jsonify({
                "error": "Validation Error",
                "message": f"Item at index {idx} is missing 'source_node_id'.",
            }), 400

    try:
        user_id = g.current_user.id if hasattr(g, "current_user") and g.current_user else None
        created = SignalMappingService.bulk_create_signals(
            machine_id=machine_id,
            organization_id=g.current_org_id,
            items=items,
            user_id=user_id,
        )
        return jsonify({
            "message": f"Successfully mapped {len(created)} signal(s).",
            "count": len(created),
            "signals": created,
        }), 201
    except ValueError as e:
        return jsonify({"error": "Validation Error", "message": str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating machine signals: {e}")
        return jsonify({"error": "Internal Error", "message": str(e)}), 500


@signals_bp.route("/equipment/<machine_id>/signals/<signal_id>", methods=["PATCH"])
@login_required
@roles_required(*SIGNAL_MANAGE_ROLES)
def update_machine_signal(machine_id: str, signal_id: str):
    """Update a signal mapping configuration. Bumps mapping_version and resets status to PENDING."""
    machine = db.session.get(Machine, machine_id)
    if not machine or machine.organization_id != g.current_org_id:
        return jsonify({"error": "Not Found", "message": "Equipment not found or access denied."}), 404

    data = request.get_json(silent=True) or {}
    try:
        user_id = g.current_user.id if hasattr(g, "current_user") and g.current_user else None
        updated = SignalMappingService.update_signal(
            signal_id=signal_id,
            organization_id=g.current_org_id,
            data=data,
            user_id=user_id,
        )
        return jsonify({
            "message": "Signal mapping updated. Validation status reset to PENDING.",
            "signal": updated,
        }), 200
    except ValueError as e:
        return jsonify({"error": "Validation Error", "message": str(e)}), 400
    except Exception as e:
        logger.error(f"Error updating machine signal: {e}")
        return jsonify({"error": "Internal Error", "message": str(e)}), 500


@signals_bp.route("/equipment/<machine_id>/signals/<signal_id>", methods=["DELETE"])
@login_required
@roles_required(*SIGNAL_MANAGE_ROLES)
def delete_machine_signal(machine_id: str, signal_id: str):
    """Delete a machine signal mapping."""
    machine = db.session.get(Machine, machine_id)
    if not machine or machine.organization_id != g.current_org_id:
        return jsonify({"error": "Not Found", "message": "Equipment not found or access denied."}), 404

    try:
        SignalMappingService.delete_signal(signal_id, g.current_org_id)
        return jsonify({"message": "Signal mapping deleted successfully."}), 200
    except ValueError as e:
        return jsonify({"error": "Validation Error", "message": str(e)}), 404
    except Exception as e:
        logger.error(f"Error deleting machine signal: {e}")
        return jsonify({"error": "Internal Error", "message": str(e)}), 500


# ==============================================================================
# SIGNAL VALIDATION ENGINE ENDPOINTS
# ==============================================================================

@signals_bp.route("/equipment/<machine_id>/signals/validate", methods=["POST"])
@login_required
@roles_required(*SIGNAL_MANAGE_ROLES)
def validate_machine_signals(machine_id: str):
    """Execute the 7-check validation engine against mapped signals. STRICTLY READ-ONLY."""
    machine = db.session.get(Machine, machine_id)
    if not machine or machine.organization_id != g.current_org_id:
        return jsonify({"error": "Not Found", "message": "Equipment not found or access denied."}), 404

    data = request.get_json(silent=True) or {}
    signal_ids = data.get("signal_ids")
    endpoint_url = data.get("endpoint_url")

    client, is_temp = _get_or_create_client(machine_id, endpoint_url)

    async def _run_validation():
        if is_temp:
            try:
                await client.connect()
            except Exception as e:
                logger.warning(f"Could not connect temporary OPC UA client for live sampling: {e}")

        try:
            user_id = g.current_user.id if hasattr(g, "current_user") and g.current_user else None
            return await SignalMappingService.validate_machine_signals(
                machine_id=machine_id,
                organization_id=g.current_org_id,
                signal_ids=signal_ids,
                client=client if client.is_connected() else None,
                user_id=user_id,
            )
        finally:
            if is_temp and client.is_connected():
                try:
                    await client.disconnect()
                except Exception:
                    pass

    try:
        results = asyncio.run(_run_validation())
        summary = SignalMappingService.get_summary(machine_id, g.current_org_id)
        return jsonify({
            "machine_id": machine_id,
            "count": len(results),
            "results": results,
            "summary": summary,
        }), 200
    except Exception as e:
        logger.error(f"Validation execution failed for machine {machine_id}: {e}")
        return jsonify({"error": "Validation Error", "message": str(e)}), 500


@signals_bp.route("/equipment/<machine_id>/signals/validation-results", methods=["GET"])
@login_required
def get_validation_results(machine_id: str):
    """Retrieve audit history of validation results for an equipment asset."""
    machine = db.session.get(Machine, machine_id)
    if not machine or machine.organization_id != g.current_org_id:
        return jsonify({"error": "Not Found", "message": "Equipment not found or access denied."}), 404

    results = SignalMappingService.get_validation_results(machine_id, g.current_org_id)
    return jsonify({
        "machine_id": machine_id,
        "count": len(results),
        "results": results,
    }), 200


@signals_bp.route("/equipment/<machine_id>/signals/mapping-summary", methods=["GET"])
@login_required
def get_mapping_summary(machine_id: str):
    """Retrieve high-level mapping status, counts, and readiness for monitoring."""
    machine = db.session.get(Machine, machine_id)
    if not machine or machine.organization_id != g.current_org_id:
        return jsonify({"error": "Not Found", "message": "Equipment not found or access denied."}), 404

    summary = SignalMappingService.get_summary(machine_id, g.current_org_id)
    return jsonify(summary), 200
