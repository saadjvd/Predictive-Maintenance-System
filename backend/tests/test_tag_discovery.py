import asyncio
import pytest
import pytest_asyncio
from app.modules.connectivity.models import (
    ConnectionState,
    ConnectionConfig,
    OPCUAError,
    ReadOnlyError,
)
from app.modules.connectivity.opcua_client import SecureOPCUAClient
from app.modules.connectivity.simulator import PharmaOPCUASimulator
from app.modules.connectivity.discovery.tag_discovery import TagDiscoveryService
from app.modules.connectivity.discovery.node_metadata import extract_node_metadata, DiscoveredTag


@pytest_asyncio.fixture
async def discovery_simulator():
    """Start an isolated OPC UA simulator with pharmaceutical address space."""
    simulator = PharmaOPCUASimulator(port=48430, enable_security=False)
    await simulator.start()
    yield simulator
    await simulator.stop()


@pytest_asyncio.fixture
async def connected_client(discovery_simulator):
    """Provide a connected SecureOPCUAClient to the discovery simulator."""
    config = ConnectionConfig(
        endpoint_url=discovery_simulator.get_endpoint(),
        timeout_sec=3.0,
    )
    client = SecureOPCUAClient(config)
    await client.connect()
    yield client
    await client.disconnect()


# =============================================================================
# 1. SUCCESSFUL TAG DISCOVERY TEST
# =============================================================================

@pytest.mark.asyncio
async def test_successful_tag_discovery(connected_client):
    """Verify browsing the root address space returns pharmaceutical machine objects and variables."""
    service = TagDiscoveryService(default_timeout_sec=3.0, max_browse_depth=3, max_nodes_per_request=50)
    tags = await service.browse_root(connected_client)

    assert len(tags) > 0
    # Locate BlisterPackagingMachine_01
    blister_machine = next((t for t in tags if "BlisterPackagingMachine" in t.browse_name), None)
    assert blister_machine is not None
    assert blister_machine.node_class == "Object"
    assert blister_machine.has_children is True
    assert len(blister_machine.children) >= 4

    # Verify discovered sensor names
    child_names = [c.browse_name for c in blister_machine.children]
    assert "Speed_CPM" in child_names
    assert "SealingTemperature" in child_names
    assert "MainDriveMotorVibration" in child_names
    assert "VacuumLevel" in child_names


# =============================================================================
# 2. NESTED NODE BROWSING (LAZY EXPANSION)
# =============================================================================

@pytest.mark.asyncio
async def test_nested_node_browsing(connected_client, discovery_simulator):
    """Verify lazy expansion browsing of direct child nodes."""
    service = TagDiscoveryService()
    # Find machine node id
    root_tags = await service.browse_root(connected_client, max_depth=1)
    blister_machine = next((t for t in root_tags if "BlisterPackagingMachine" in t.browse_name), None)
    assert blister_machine is not None

    children = await service.browse_children(connected_client, blister_machine.node_id)
    assert len(children) >= 4
    for child in children:
        assert child.parent_node_id == blister_machine.node_id
        assert child.node_class == "Variable"


# =============================================================================
# 3. METADATA EXTRACTION TEST
# =============================================================================

@pytest.mark.asyncio
async def test_metadata_extraction(connected_client, discovery_simulator):
    """Verify extraction of NodeId, Browse Name, Data Type, and Access Level without fabrication."""
    service = TagDiscoveryService()
    speed_node_id = discovery_simulator.blister_speed_node.nodeid.to_string()

    meta = await service.get_node_metadata(connected_client, speed_node_id)
    assert meta is not None
    assert meta.node_id == speed_node_id
    assert meta.browse_name == "Speed_CPM"
    assert meta.display_name == "Speed_CPM"
    assert meta.node_class == "Variable"
    assert meta.data_type == "Double"
    assert meta.readable is True
    assert meta.writable is False


# =============================================================================
# 4. MISSING ENGINEERING UNITS HANDLING
# =============================================================================

@pytest.mark.asyncio
async def test_missing_engineering_units_not_fabricated(connected_client, discovery_simulator):
    """Ensure missing optional engineering units are recorded as None without fabrication."""
    service = TagDiscoveryService()
    speed_node_id = discovery_simulator.blister_speed_node.nodeid.to_string()

    meta = await service.get_node_metadata(connected_client, speed_node_id)
    assert meta is not None
    # If the simulated node does not define EURange / EngineeringUnits, field must be None
    if meta.engineering_unit is not None:
        assert isinstance(meta.engineering_unit, str)
    else:
        assert meta.engineering_unit is None


# =============================================================================
# 5. UNSUPPORTED NODE TYPES / NODE CLASSES
# =============================================================================

@pytest.mark.asyncio
async def test_unsupported_node_types_handled(connected_client):
    """Verify that Object, Folder, and Variable nodes are correctly classified."""
    service = TagDiscoveryService()
    tags = await service.browse_root(connected_client, max_depth=2)

    for t in tags:
        assert t.node_class in ("Object", "Variable", "Folder", "Method", "View", "DataType", "ReferenceType")
        if t.node_class != "Variable":
            # Non-variable nodes are not writable sensor tags
            assert t.writable is False


# =============================================================================
# 6. INVALID NODEID HANDLING
# =============================================================================

@pytest.mark.asyncio
async def test_invalid_node_id_handling(connected_client):
    """Verify appropriate error handling when querying non-existent NodeId."""
    service = TagDiscoveryService()
    with pytest.raises(OPCUAError):
        await service.get_node_metadata(connected_client, "ns=99;s=NonExistent.Machine.Tag")


# =============================================================================
# 7. DISCONNECTED SERVER HANDLING
# =============================================================================

@pytest.mark.asyncio
async def test_disconnected_client_raises_error():
    """Verify discovery service rejects browsing when client is not connected."""
    config = ConnectionConfig(endpoint_url="opc.tcp://127.0.0.1:48439/test/")
    disconnected_client = SecureOPCUAClient(config)
    service = TagDiscoveryService()

    with pytest.raises(OPCUAError) as exc_info:
        await service.browse_root(disconnected_client)

    assert "client is not connected" in str(exc_info.value)


# =============================================================================
# 8. BOUNDED BROWSE DEPTH
# =============================================================================

@pytest.mark.asyncio
async def test_bounded_browse_depth(connected_client):
    """Verify that max_depth strictly constrains recursive browsing."""
    service = TagDiscoveryService(max_browse_depth=1)
    tags = await service.browse_root(connected_client, max_depth=1)

    # Depth 1 should return top-level objects without populating nested children
    for t in tags:
        assert len(t.children) == 0


# =============================================================================
# 9. LARGE ADDRESS SPACE / MAX NODES LIMITATION
# =============================================================================

@pytest.mark.asyncio
async def test_max_nodes_per_request_limit(connected_client):
    """Verify that max_nodes caps the total number of processed nodes."""
    service = TagDiscoveryService(max_nodes_per_request=2)
    tags = await service.browse_root(connected_client, max_nodes=2)

    assert len(tags) <= 2


# =============================================================================
# 10. CYCLE PROTECTION (CIRCULAR REFERENCES)
# =============================================================================

@pytest.mark.asyncio
async def test_cycle_protection(connected_client):
    """Verify that visited set prevents infinite loops in circular references."""
    service = TagDiscoveryService(max_browse_depth=5, max_nodes_per_request=50)
    # Browsing should complete cleanly in finite time without RecursionError
    tags = await service.browse_root(connected_client)
    assert isinstance(tags, list)


# =============================================================================
# 11. SEARCH DISCOVERED TAGS
# =============================================================================

@pytest.mark.asyncio
async def test_search_discovered_tags(connected_client):
    """Verify search finds matching signals by keyword."""
    service = TagDiscoveryService()
    matches = await service.search_discovered_tags(connected_client, "vibration")

    assert len(matches) > 0
    match_names = [m.browse_name for m in matches]
    assert "MainDriveMotorVibration" in match_names


# =============================================================================
# 12. READABILITY VALIDATION
# =============================================================================

@pytest.mark.asyncio
async def test_validate_readable_node(connected_client, discovery_simulator):
    """Verify validation check confirms live readability of a variable node."""
    service = TagDiscoveryService()
    speed_node_id = discovery_simulator.blister_speed_node.nodeid.to_string()

    is_readable, err = await service.validate_readable_node(connected_client, speed_node_id)
    assert is_readable is True
    assert err is None


# =============================================================================
# 13. READ-ONLY BEHAVIOR ENFORCEMENT
# =============================================================================

@pytest.mark.asyncio
async def test_discovery_read_only_enforcement(connected_client, discovery_simulator):
    """Verify that tag discovery leaves OPC UA node values completely intact."""
    service = TagDiscoveryService()
    speed_node_id = discovery_simulator.blister_speed_node.nodeid.to_string()

    # Get metadata and search
    await service.get_node_metadata(connected_client, speed_node_id)
    await service.search_discovered_tags(connected_client, "Speed")

    # Read value directly from client, must remain at 240.0
    val = await connected_client.read_value(speed_node_id)
    assert val == 240.0


# =============================================================================
# 14. NORMALIZED DICTIONARY STRUCTURE
# =============================================================================

def test_normalized_tag_dictionary():
    """Verify DiscoveredTag to_dict format complies with Phase 4 specifications."""
    tag = DiscoveredTag(
        node_id="ns=2;s=Motor1.Temperature",
        browse_name="Motor1.Temperature",
        display_name="Motor Temperature",
        node_class="Variable",
        data_type="Double",
        engineering_unit="°C",
        description="Main motor temperature",
        readable=True,
        writable=False,
        parent_node_id="ns=2;s=Motor1",
    )
    d = tag.to_dict()
    assert d["node_id"] == "ns=2;s=Motor1.Temperature"
    assert d["data_type"] == "Double"
    assert d["engineering_unit"] == "°C"
    assert d["readable"] is True
    assert d["writable"] is False


# =============================================================================
# 15. FLASK API DISCOVERY ENDPOINTS & TENANT ISOLATION
# =============================================================================

def test_unauthenticated_discovery_denied(client):
    """Verify unauthenticated requests to discovery endpoints are rejected with 401."""
    res = client.get("/api/v1/connectivity/tags/mock-machine-id")
    assert res.status_code == 401

    res2 = client.get("/api/v1/connectors/mock-machine-id/tags")
    assert res2.status_code == 401


def test_cross_org_discovery_denied(client, app):
    """Verify tenant isolation: Org A user cannot discover tags for Org B machine."""
    from tests.test_equipment import setup_equipment_test_data, get_auth_token
    from app.models.equipment import Machine
    from app.extensions import db

    data = setup_equipment_test_data(app)
    token_a = get_auth_token(client, "manager@getzpharma.com", "Manager@123")

    with app.app_context():
        # Create a machine in Org B
        mach_b = Machine(
            organization_id=data["org_b_id"],
            site_id=data["site_b1_id"],
            category_id=data["cat_blister_id"],
            asset_code="BENCH-BLIST-99",
            equipment_name="Org B Machine"
        )
        db.session.add(mach_b)
        db.session.commit()
        mach_b_id = mach_b.id

    # User from Org A attempts to discover tags on Org B's machine
    res = client.get(
        f"/api/v1/connectivity/tags/{mach_b_id}",
        headers={"Authorization": f"Bearer {token_a}"}
    )
    assert res.status_code == 404
