import logging
from flask import Blueprint, request, jsonify, g
from app.extensions import db
from app.models.user import Role
from app.models.equipment import Machine
from app.security import login_required, roles_required
from app.modules.connectivity.models import (
    ConnectionState,
    ConnectionConfig,
    ConnectionHealth,
    SecurityPolicy,
    SecurityMode,
    UserAuthType,
)
from app.modules.connectivity.connection_manager import (
    ConnectionLifecycleManager,
    GatewayManager,
)

logger = logging.getLogger(__name__)

connectivity_bp = Blueprint("connectivity", __name__, url_prefix="/connectivity")


def update_machine_db_status(machine_id: str, state: ConnectionState, error_msg: str = None) -> None:
    """Publish OPC UA state transition to the database record for the machine (Requirement 10)."""
    try:
        from flask import current_app
        # Handle state mapping
        state_map = {
            ConnectionState.DISCONNECTED: ("Disconnected", "Suspended"),
            ConnectionState.CONNECTING: ("Configured", "Pending Validation"),
            ConnectionState.CONNECTED: ("Connected", "Active"),
            ConnectionState.RECONNECTING: ("Configured", "Pending Validation"),
            ConnectionState.ERROR: ("Error", "Suspended"),
        }

        conn_status, mon_status = state_map.get(state, ("Not Configured", "Not Started"))

        machine = db.session.get(Machine, machine_id)
        if machine:
            machine.connection_status = conn_status
            if state == ConnectionState.CONNECTED:
                machine.monitoring_status = mon_status
            elif state in (ConnectionState.ERROR, ConnectionState.DISCONNECTED):
                machine.monitoring_status = mon_status
            db.session.commit()
            logger.info(
                f"[Connectivity-DB] Machine {machine_id} status updated to {conn_status} ({mon_status})"
            )
    except Exception as e:
        logger.error(f"[Connectivity-DB] Failed to update machine {machine_id} status: {e}")
        db.session.rollback()


@connectivity_bp.route("/status/<machine_id>", methods=["GET"])
@login_required
def get_connection_status(machine_id: str):
    """Retrieve the real-time OPC UA connection state and health for a machine."""
    machine = db.session.get(Machine, machine_id)
    if not machine or machine.organization_id != g.current_org_id:
        return jsonify({"error": "Not Found", "message": "Equipment not found."}), 404

    manager = GatewayManager.get(machine_id)
    if not manager:
        return jsonify({
            "machine_id": machine_id,
            "state": ConnectionState.DISCONNECTED.value,
            "is_active": False,
            "db_connection_status": machine.connection_status,
            "db_monitoring_status": machine.monitoring_status,
        }), 200

    return jsonify({
        "machine_id": machine_id,
        "state": manager.get_state().value,
        "is_active": manager.get_state() == ConnectionState.CONNECTED,
        "db_connection_status": machine.connection_status,
        "db_monitoring_status": machine.monitoring_status,
        "config": manager.config.to_dict(),
    }), 200


@connectivity_bp.route("/connect/<machine_id>", methods=["POST"])
@roles_required(
    Role.PLATFORM_ADMIN,
    Role.ORG_ADMIN,
    Role.MAINTENANCE_MANAGER,
    Role.MAINTENANCE_ENGINEER
)
def initiate_connection(machine_id: str):
    """Initiate an asynchronous OPC UA connection for a machine."""
    machine = db.session.get(Machine, machine_id)
    if not machine or machine.organization_id != g.current_org_id:
        return jsonify({"error": "Not Found", "message": "Equipment not found."}), 404

    data = request.get_json(silent=True) or {}
    endpoint_url = data.get("endpoint_url")
    if not endpoint_url:
        return jsonify({
            "error": "Validation Error",
            "message": "OPC UA endpoint_url is required."
        }), 400

    # Build ConnectionConfig
    config = ConnectionConfig(
        endpoint_url=endpoint_url,
        timeout_sec=float(data.get("timeout_sec", 5.0)),
        security_policy=SecurityPolicy(data.get("security_policy", "None")),
        security_mode=SecurityMode(data.get("security_mode", "None")),
        user_auth_type=UserAuthType(data.get("user_auth_type", "Anonymous")),
        username=data.get("username"),
        password=data.get("password"),
        trusted_cert_fingerprints=data.get("trusted_cert_fingerprints", []),
        auto_trust_unknown=bool(data.get("auto_trust_unknown", False)),
        max_reconnect_attempts=int(data.get("max_reconnect_attempts", 5)),
    )

    existing = GatewayManager.get(machine_id)
    if existing:
        return jsonify({
            "message": "Gateway connection already registered for this machine.",
            "state": existing.get_state().value
        }), 200

    # Create manager and register status updater
    manager = ConnectionLifecycleManager(config=config, machine_id=machine_id)
    manager.register_status_callback(update_machine_db_status)
    manager.start_background_worker()

    GatewayManager.register(machine_id, manager)

    return jsonify({
        "message": f"OPC UA connection initiated for {machine.equipment_name}.",
        "state": manager.get_state().value,
        "endpoint_url": config.endpoint_url
    }), 202


@connectivity_bp.route("/disconnect/<machine_id>", methods=["POST"])
@roles_required(
    Role.PLATFORM_ADMIN,
    Role.ORG_ADMIN,
    Role.MAINTENANCE_MANAGER,
    Role.MAINTENANCE_ENGINEER
)
def terminate_connection(machine_id: str):
    """Gracefully terminate OPC UA connection and release resources."""
    machine = db.session.get(Machine, machine_id)
    if not machine or machine.organization_id != g.current_org_id:
        return jsonify({"error": "Not Found", "message": "Equipment not found."}), 404

    manager = GatewayManager.remove(machine_id)
    if not manager:
        return jsonify({
            "message": "No active gateway found for this equipment.",
            "state": ConnectionState.DISCONNECTED.value
        }), 200

    manager.stop_background_worker()
    update_machine_db_status(machine_id, ConnectionState.DISCONNECTED)

    return jsonify({
        "message": f"OPC UA connection gracefully disconnected for {machine.equipment_name}.",
        "state": ConnectionState.DISCONNECTED.value
    }), 200


# =============================================================================
# PHASE 4, STEP 5: AUTOMATIC OPC UA TAG DISCOVERY ENDPOINTS
# =============================================================================

from app.modules.connectivity.discovery import TagDiscoveryService
from app.modules.connectivity.opcua_client import SecureOPCUAClient
import asyncio


connectors_bp = Blueprint("connectors", __name__, url_prefix="/connectors")


async def _run_discovery_browse(client: SecureOPCUAClient, parent_node_id: str = None, depth: int = 3, max_nodes: int = 150):
    service = TagDiscoveryService(max_nodes_per_request=max_nodes, max_browse_depth=depth)
    if parent_node_id:
        return await service.browse_children(client, parent_node_id, max_nodes=max_nodes)
    return await service.browse_root(client, max_depth=depth, max_nodes=max_nodes)


async def _run_discovery_metadata(client: SecureOPCUAClient, node_id: str):
    service = TagDiscoveryService()
    return await service.get_node_metadata(client, node_id)


async def _run_discovery_search(client: SecureOPCUAClient, query: str):
    service = TagDiscoveryService()
    return await service.search_discovered_tags(client, query)


def _get_or_create_client(machine_id: str, endpoint_url: str = None) -> tuple[SecureOPCUAClient, bool]:
    """Helper to reuse active manager client or construct a temporary client for discovery."""
    manager = GatewayManager.get(machine_id)
    if manager and manager.get_state() == ConnectionState.CONNECTED:
        return manager.client, False

    # Otherwise, construct a client from endpoint_url
    target_url = endpoint_url or "opc.tcp://127.0.0.1:48401/pharmapredict/server/"
    config = ConnectionConfig(
        endpoint_url=target_url,
        timeout_sec=3.5,
        user_auth_type=UserAuthType.ANONYMOUS,
        auto_trust_unknown=True,
    )
    return SecureOPCUAClient(config), True


@connectivity_bp.route("/tags/<machine_id>", methods=["GET"])
@connectors_bp.route("/<machine_id>/tags", methods=["GET"])
@login_required
def list_discovered_tags(machine_id: str):
    """Discover available OPC UA address space tags for a machine (Requirement 6)."""
    machine = db.session.get(Machine, machine_id)
    if not machine or machine.organization_id != g.current_org_id:
        return jsonify({"error": "Not Found", "message": "Equipment not found or access denied."}), 404

    endpoint_url = request.args.get("endpoint_url")
    parent_node_id = request.args.get("parent_node_id")
    try:
        depth = int(request.args.get("depth", 3))
        max_nodes = int(request.args.get("max_nodes", 100))
    except ValueError:
        depth, max_nodes = 3, 100

    client, is_temp = _get_or_create_client(machine_id, endpoint_url)

    async def _discover():
        if is_temp:
            await client.connect()
        try:
            return await _run_discovery_browse(client, parent_node_id=parent_node_id, depth=depth, max_nodes=max_nodes)
        finally:
            if is_temp:
                await client.disconnect()

    try:
        tags = asyncio.run(_discover())
        return jsonify({
            "machine_id": machine_id,
            "count": len(tags),
            "tags": [t.to_dict() for t in tags],
        }), 200
    except Exception as e:
        logger.error(f"Discovery failed for machine {machine_id}: {e}")
        return jsonify({
            "error": "Discovery Error",
            "message": f"Could not discover OPC UA tags: {e}"
        }), 502


@connectivity_bp.route("/tags/<machine_id>/metadata", methods=["GET"])
@connectors_bp.route("/<machine_id>/tags/metadata", methods=["GET"])
@login_required
def get_tag_metadata(machine_id: str):
    """Retrieve full metadata for a specific NodeId."""
    machine = db.session.get(Machine, machine_id)
    if not machine or machine.organization_id != g.current_org_id:
        return jsonify({"error": "Not Found", "message": "Equipment not found or access denied."}), 404

    node_id = request.args.get("node_id")
    if not node_id:
        return jsonify({"error": "Validation Error", "message": "Query parameter node_id is required."}), 400

    endpoint_url = request.args.get("endpoint_url")
    client, is_temp = _get_or_create_client(machine_id, endpoint_url)

    async def _fetch():
        if is_temp:
            await client.connect()
        try:
            return await _run_discovery_metadata(client, node_id)
        finally:
            if is_temp:
                await client.disconnect()

    try:
        tag = asyncio.run(_fetch())
        if not tag:
            return jsonify({"error": "Not Found", "message": f"NodeId '{node_id}' not found."}), 404
        return jsonify({"metadata": tag.to_dict()}), 200
    except Exception as e:
        return jsonify({"error": "Metadata Error", "message": str(e)}), 502


@connectivity_bp.route("/tags/<machine_id>/search", methods=["POST"])
@connectors_bp.route("/<machine_id>/tags/search", methods=["POST"])
@login_required
def search_tags(machine_id: str):
    """Search discovered tags for matching signals."""
    machine = db.session.get(Machine, machine_id)
    if not machine or machine.organization_id != g.current_org_id:
        return jsonify({"error": "Not Found", "message": "Equipment not found or access denied."}), 404

    data = request.get_json(silent=True) or {}
    query = data.get("query", "").strip()
    if not query:
        return jsonify({"error": "Validation Error", "message": "Search query is required."}), 400

    endpoint_url = data.get("endpoint_url")
    client, is_temp = _get_or_create_client(machine_id, endpoint_url)

    async def _search():
        if is_temp:
            await client.connect()
        try:
            return await _run_discovery_search(client, query)
        finally:
            if is_temp:
                await client.disconnect()

    try:
        matches = asyncio.run(_search())
        return jsonify({
            "machine_id": machine_id,
            "query": query,
            "count": len(matches),
            "tags": [m.to_dict() for m in matches],
        }), 200
    except Exception as e:
        return jsonify({"error": "Search Error", "message": str(e)}), 502

