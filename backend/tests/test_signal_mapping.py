import pytest
import pytest_asyncio
import math
from unittest.mock import MagicMock, patch
from app.extensions import db
from app.models.tenant import Organization, Site
from app.models.user import User, Role, UserRoleAssignment
from app.models.equipment import Machine, EquipmentCategory
from app.models.signal_mapping import (
    SignalDefinition,
    MachineSignal,
    SignalValidationResult,
    SignalGroup,
    ValidationStatus,
)
from app.modules.signal_mapping.repositories import SignalDefinitionRepository
from app.modules.signal_mapping.unit_converter import (
    UnitNormalizer,
    IncompatibleUnitError,
    UnsupportedUnitError,
)
from app.modules.signal_mapping.validators import SignalValidator
from app.modules.signal_mapping.services import SignalMappingService
from app.modules.connectivity.simulator import PharmaOPCUASimulator
from app.modules.connectivity.opcua_client import SecureOPCUAClient
from app.modules.connectivity.models import ConnectionConfig, UserAuthType
from tests.test_equipment import get_auth_token, setup_equipment_test_data


@pytest.fixture(autouse=True)
def setup_data(app):
    data = setup_equipment_test_data(app)
    with app.app_context():
        # Seed standard signals catalog
        SignalDefinitionRepository.seed_standard_definitions()

        eng_role = Role.query.filter_by(name=Role.MAINTENANCE_ENGINEER).first()
        org_a = db.session.get(Organization, data["org_a_id"])
        org_b = db.session.get(Organization, data["org_b_id"])

        eng_a = User.query.filter_by(email="engineer@getzpharma.com").first()
        if not eng_a:
            eng_a = User(organization_id=org_a.id, full_name="Getz Engineer", email="engineer@getzpharma.com")
            eng_a.set_password("Engineer@123")
            db.session.add(eng_a)
            db.session.commit()
            db.session.add(UserRoleAssignment(user_id=eng_a.id, role_id=eng_role.id, organization_id=org_a.id))
            db.session.commit()

        # Ensure a test machine for Org A
        machine_a = Machine.query.filter_by(asset_code="BLIST-01", organization_id=org_a.id).first()
        if not machine_a:
            cat = EquipmentCategory.query.filter_by(name="Blister Packaging").first()
            site = Site.query.filter_by(organization_id=org_a.id).first()
            machine_a = Machine(
                organization_id=org_a.id,
                site_id=site.id,
                category_id=cat.id,
                asset_code="BLIST-01",
                equipment_name="Uhlen Blister Packer B450",
                manufacturer="Uhlen Packaging",
                model="B450",
                criticality="High",
            )
            db.session.add(machine_a)
            db.session.commit()

        # Ensure a test machine for Org B
        machine_b = Machine.query.filter_by(asset_code="TAB-01", organization_id=org_b.id).first()
        if not machine_b:
            cat = EquipmentCategory.query.filter_by(name="Tablet Compression").first()
            if not cat:
                cat = EquipmentCategory(name="Tablet Compression", is_default=True)
                db.session.add(cat)
                db.session.commit()
            site_b = Site.query.filter_by(organization_id=org_b.id).first()
            machine_b = Machine(
                organization_id=org_b.id,
                site_id=site_b.id,
                category_id=cat.id,
                asset_code="TAB-01",
                equipment_name="Fette Tablet Press 2090i",
                criticality="Critical",
            )
            db.session.add(machine_b)
            db.session.commit()

    return data


@pytest.fixture
def sim_port():
    return 48404


@pytest_asyncio.fixture
async def opcua_simulator(sim_port):
    sim = PharmaOPCUASimulator(port=sim_port)
    await sim.start()
    yield sim
    await sim.stop()


def test_standard_definitions_seeded(client):
    token = get_auth_token(client, "manager@getzpharma.com", "Manager@123")
    res = client.get("/api/v1/signals/definitions", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["count"] >= 10
    codes = [d["signal_code"] for d in data["definitions"]]
    assert "MOTOR_TEMP" in codes
    assert "MOTOR_VIBRATION" in codes
    assert "BEARING_VIBRATION" in codes
    assert "ROTATIONAL_SPEED" in codes
    assert "FAULT_ALARM" in codes
    assert "CYCLE_COUNTER" in codes


def test_custom_signal_definition_creation(client):
    token = get_auth_token(client, "engineer@getzpharma.com", "Engineer@123")
    payload = {
        "signal_code": "CUSTOM_HOPPER_LEVEL",
        "name": "Powder Hopper Fill Level",
        "signal_group": "Pressure",
        "expected_data_type": "Float",
        "standard_unit": "bar",
        "measurement_dimension": "pressure",
        "description": "Custom ultrasonic level sensor.",
    }
    res = client.post("/api/v1/signals/definitions", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 201
    data = res.get_json()
    assert data["definition"]["signal_code"] == "CUSTOM_HOPPER_LEVEL"
    assert data["definition"]["is_custom"] is True


def test_duplicate_custom_signal_code_rejected(client):
    token = get_auth_token(client, "engineer@getzpharma.com", "Engineer@123")
    payload = {
        "signal_code": "CUSTOM_HOPPER_LEVEL_DUP",
        "name": "Duplicate Hopper",
        "signal_group": "Pressure",
        "expected_data_type": "Float",
    }
    res1 = client.post("/api/v1/signals/definitions", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert res1.status_code == 201

    res2 = client.post("/api/v1/signals/definitions", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert res2.status_code == 400
    assert "already exists" in res2.get_json()["message"]


def test_unit_converter_physical_dimensions():
    # Valid conversions
    assert math.isclose(UnitNormalizer.convert(100.0, "°C", "°F"), 212.0)
    assert math.isclose(UnitNormalizer.convert(212.0, "°F", "°C"), 100.0)
    assert math.isclose(UnitNormalizer.convert(1.0, "bar", "psi"), 14.5038, rel_tol=1e-3)
    assert math.isclose(UnitNormalizer.convert(1.0, "m/s", "mm/s"), 1000.0)

    # Incompatible dimensions must raise IncompatibleUnitError
    with pytest.raises(IncompatibleUnitError):
        UnitNormalizer.convert(1.5, "g", "mm/s")

    with pytest.raises(IncompatibleUnitError):
        UnitNormalizer.convert(50.0, "°C", "bar")

    with pytest.raises(UnsupportedUnitError):
        UnitNormalizer.convert(10.0, "unknown_unit_xyz", "°C")


def test_valid_signal_mapping_creation_and_multiple_sensors(client):
    token = get_auth_token(client, "engineer@getzpharma.com", "Engineer@123")

    # Get a machine
    m_res = client.get("/api/v1/equipment", headers={"Authorization": f"Bearer {token}"})
    machine = m_res.get_json()["equipment"][0]
    machine_id = machine["id"]

    # Get definition for MOTOR_TEMP
    defs_res = client.get("/api/v1/signals/definitions", headers={"Authorization": f"Bearer {token}"})
    motor_temp_def = next(d for d in defs_res.get_json()["definitions"] if d["signal_code"] == "MOTOR_TEMP")

    # Map Sensor 1: Drive Motor Temperature
    payload1 = {
        "signal_definition_id": motor_temp_def["id"],
        "custom_name": "Drive Motor 1 Temperature",
        "source_node_id": "ns=2;s=Machine1.DriveMotor.Temperature",
        "source_browse_name": "DriveMotor_Temp",
        "source_data_type": "Double",
        "source_unit": "°C",
        "normalized_unit": "°C",
        "scaling_factor": 1.0,
        "offset": 0.0,
        "sampling_interval_ms": 1000,
    }
    res1 = client.post(f"/api/v1/equipment/{machine_id}/signals", json=payload1, headers={"Authorization": f"Bearer {token}"})
    assert res1.status_code == 201
    sig1 = res1.get_json()["signals"][0]
    assert sig1["mapping_version"] == 1
    assert sig1["validation_status"] == ValidationStatus.PENDING

    # Map Sensor 2: Secondary Feeder Motor Temperature (same group, multi-sensor support)
    payload2 = {
        "signal_definition_id": motor_temp_def["id"],
        "custom_name": "Feeder Motor 2 Temperature",
        "source_node_id": "ns=2;s=Machine1.FeederMotor.Temperature",
        "source_browse_name": "FeederMotor_Temp",
        "source_data_type": "Double",
        "source_unit": "°C",
        "normalized_unit": "°C",
        "scaling_factor": 1.0,
        "offset": 0.0,
        "sampling_interval_ms": 1000,
    }
    res2 = client.post(f"/api/v1/equipment/{machine_id}/signals", json=payload2, headers={"Authorization": f"Bearer {token}"})
    assert res2.status_code == 201


def test_duplicate_node_id_mapping_rejected(client):
    token = get_auth_token(client, "engineer@getzpharma.com", "Engineer@123")
    m_res = client.get("/api/v1/equipment", headers={"Authorization": f"Bearer {token}"})
    machine_id = m_res.get_json()["equipment"][0]["id"]

    defs_res = client.get("/api/v1/signals/definitions", headers={"Authorization": f"Bearer {token}"})
    motor_temp_def = next(d for d in defs_res.get_json()["definitions"] if d["signal_code"] == "MOTOR_TEMP")

    payload = {
        "signal_definition_id": motor_temp_def["id"],
        "source_node_id": "ns=2;s=Machine1.DuplicateCheck.Node",
    }
    res1 = client.post(f"/api/v1/equipment/{machine_id}/signals", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert res1.status_code == 201

    res2 = client.post(f"/api/v1/equipment/{machine_id}/signals", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert res2.status_code == 400
    assert "already mapped" in res2.get_json()["message"]


def test_data_type_mismatch_check():
    # Double expecting Boolean source -> Fails
    chk_num_bool = SignalValidator.check_data_type_compatibility("Double", "Boolean")
    assert not chk_num_bool.passed
    assert chk_num_bool.severity == "ERROR"

    # Boolean expecting Float source -> Fails
    chk_bool_float = SignalValidator.check_data_type_compatibility("Boolean", "Float")
    assert not chk_bool_float.passed

    # Double expecting Float source -> Passes (numeric compatibility)
    chk_double_float = SignalValidator.check_data_type_compatibility("Double", "Float")
    assert chk_double_float.passed


def test_scaling_validation():
    # Zero scaling factor -> Fails
    chk_zero = SignalValidator.check_scaling(0.0, 0.0)
    assert not chk_zero.passed
    assert "cannot be zero" in chk_zero.message

    # Infinite scaling factor -> Fails
    chk_inf = SignalValidator.check_scaling(float("inf"), 0.0)
    assert not chk_inf.passed

    # Valid scaling -> Passes
    chk_valid = SignalValidator.check_scaling(0.1, -5.0)
    assert chk_valid.passed


def test_sampling_interval_validation():
    # Below 50ms -> Fails
    chk_low = SignalValidator.check_sampling_interval(20)
    assert not chk_low.passed

    # Fast (60ms) -> Warns
    chk_warn = SignalValidator.check_sampling_interval(60)
    assert chk_warn.passed
    assert chk_warn.severity == "WARNING"

    # Normal 1000ms -> Passes
    chk_normal = SignalValidator.check_sampling_interval(1000)
    assert chk_normal.passed
    assert chk_normal.severity == "INFO"


def test_signal_update_bumps_version_and_resets_validation(client):
    token = get_auth_token(client, "engineer@getzpharma.com", "Engineer@123")
    m_res = client.get("/api/v1/equipment", headers={"Authorization": f"Bearer {token}"})
    machine_id = m_res.get_json()["equipment"][0]["id"]

    # Create signal to update
    defs_res = client.get("/api/v1/signals/definitions", headers={"Authorization": f"Bearer {token}"})
    def_id = defs_res.get_json()["definitions"][0]["id"]

    c_res = client.post(
        f"/api/v1/equipment/{machine_id}/signals",
        json={"signal_definition_id": def_id, "source_node_id": "ns=2;s=Machine1.UpdateTest.Node"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert c_res.status_code == 201
    signal = c_res.get_json()["signals"][0]
    initial_version = signal["mapping_version"]

    # Update scaling factor
    patch_res = client.patch(
        f"/api/v1/equipment/{machine_id}/signals/{signal['id']}",
        json={"scaling_factor": 1.5, "custom_name": "Updated Sensor Name"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert patch_res.status_code == 200
    updated = patch_res.get_json()["signal"]
    assert updated["mapping_version"] == initial_version + 1
    assert updated["validation_status"] == ValidationStatus.PENDING
    assert updated["scaling_factor"] == 1.5
    assert updated["signal_name"] == "Updated Sensor Name"


def test_signal_deletion(client):
    token = get_auth_token(client, "engineer@getzpharma.com", "Engineer@123")
    m_res = client.get("/api/v1/equipment", headers={"Authorization": f"Bearer {token}"})
    machine_id = m_res.get_json()["equipment"][0]["id"]

    # Create temporary signal to delete
    defs_res = client.get("/api/v1/signals/definitions", headers={"Authorization": f"Bearer {token}"})
    def_id = defs_res.get_json()["definitions"][0]["id"]

    create_res = client.post(
        f"/api/v1/equipment/{machine_id}/signals",
        json={"signal_definition_id": def_id, "source_node_id": "ns=2;s=Temp.DeleteMe"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_res.status_code == 201
    created_id = create_res.get_json()["signals"][0]["id"]

    # Delete
    del_res = client.delete(
        f"/api/v1/equipment/{machine_id}/signals/{created_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert del_res.status_code == 200

    # Verify not found
    sigs_res = client.get(f"/api/v1/equipment/{machine_id}/signals", headers={"Authorization": f"Bearer {token}"})
    ids = [s["id"] for s in sigs_res.get_json()["signals"]]
    assert created_id not in ids


@pytest.mark.asyncio
async def test_live_sample_reading_and_scaling(opcua_simulator, sim_port, app):
    """Validate signal against live OPC UA simulator, verifying read-only scaling and unit conversion."""
    endpoint_url = f"opc.tcp://127.0.0.1:{sim_port}/pharmapredict/server/"
    config = ConnectionConfig(
        endpoint_url=endpoint_url,
        timeout_sec=3.0,
        user_auth_type=UserAuthType.ANONYMOUS,
        auto_trust_unknown=True,
    )
    client = SecureOPCUAClient(config)
    await client.connect()

    with app.app_context():
        SignalDefinitionRepository.seed_standard_definitions()
        machine = Machine.query.first()
        def_temp = SignalDefinition.query.filter_by(signal_code="MOTOR_TEMP").first()

        # Create signal mapped to simulator temperature node
        node_id_str = opcua_simulator.blister_temp_node.nodeid.to_string()
        signal = MachineSignal(
            organization_id=machine.organization_id,
            machine_id=machine.id,
            signal_definition_id=def_temp.id,
            custom_name="Live Motor Temp",
            source_node_id=node_id_str,
            source_browse_name="Temperature",
            source_data_type="Double",
            source_unit="°C",
            normalized_unit="°C",
            scaling_factor=1.0,
            offset=0.0,
            sampling_interval_ms=1000,
            mapping_version=1,
            validation_status=ValidationStatus.PENDING,
        )
        db.session.add(signal)
        db.session.commit()

        # Run validation
        status, checks, errors, warnings, sample = await SignalValidator.validate_signal(
            signal=signal,
            client=client,
            existing_signals=[signal],
        )

        assert status == ValidationStatus.VALID
        assert len(errors) == 0
        assert sample is not None
        assert sample["quality"] == "Good"
        assert sample["raw_value"] > 0
        assert sample["normalized_value"] == sample["raw_value"]

    await client.disconnect()


@pytest.mark.asyncio
async def test_strict_read_only_enforcement(opcua_simulator, sim_port, app):
    """Verify that mapping and validation never call write_value or call_method on OPC UA server."""
    endpoint_url = f"opc.tcp://127.0.0.1:{sim_port}/pharmapredict/server/"
    config = ConnectionConfig(
        endpoint_url=endpoint_url,
        timeout_sec=3.0,
        user_auth_type=UserAuthType.ANONYMOUS,
        auto_trust_unknown=True,
    )
    client = SecureOPCUAClient(config)
    await client.connect()

    with app.app_context():
        SignalDefinitionRepository.seed_standard_definitions()
        machine = Machine.query.first()
        def_temp = SignalDefinition.query.filter_by(signal_code="MOTOR_TEMP").first()
        node_id_str = opcua_simulator.blister_temp_node.nodeid.to_string()
        signal = MachineSignal(
            organization_id=machine.organization_id,
            machine_id=machine.id,
            signal_definition_id=def_temp.id,
            source_node_id=node_id_str,
            source_data_type="Double",
            source_unit="°C",
            normalized_unit="°C",
            scaling_factor=1.0,
            offset=0.0,
            sampling_interval_ms=1000,
        )
        db.session.add(signal)
        db.session.commit()

        raw_node = client.client.get_node(signal.source_node_id)
        raw_node.write_value = MagicMock(side_effect=RuntimeError("OPC UA write attempt detected!"))
        raw_node.call_method = MagicMock(side_effect=RuntimeError("OPC UA call method detected!"))

        with patch.object(client.client, "get_node", return_value=raw_node):
            status, checks, errors, warnings, sample = await SignalValidator.validate_signal(
                signal=signal,
                client=client,
                existing_signals=[signal],
            )

        assert status == ValidationStatus.VALID
        raw_node.write_value.assert_not_called()
        raw_node.call_method.assert_not_called()

    await client.disconnect()


def test_mapping_summary_endpoint(client):
    token = get_auth_token(client, "engineer@getzpharma.com", "Engineer@123")
    m_res = client.get("/api/v1/equipment", headers={"Authorization": f"Bearer {token}"})
    machine_id = m_res.get_json()["equipment"][0]["id"]

    res = client.get(f"/api/v1/equipment/{machine_id}/signals/mapping-summary", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    summary = res.get_json()
    assert "total_signals" in summary
    assert "valid_count" in summary
    assert "ready_for_monitoring" in summary
    assert isinstance(summary["group_breakdown"], dict)


def test_cross_organization_signal_isolation(client):
    token_a = get_auth_token(client, "engineer@getzpharma.com", "Engineer@123")
    token_b = get_auth_token(client, "manager@benchmark.com", "BenchManager@123")

    m_res = client.get("/api/v1/equipment", headers={"Authorization": f"Bearer {token_a}"})
    machine_id = m_res.get_json()["equipment"][0]["id"]

    cross_res = client.get(f"/api/v1/equipment/{machine_id}/signals", headers={"Authorization": f"Bearer {token_b}"})
    assert cross_res.status_code == 404
    assert "not found" in cross_res.get_json()["message"].lower()


def test_role_permission_enforcement(client):
    token_viewer = get_auth_token(client, "viewer@getzpharma.com", "Viewer@123")
    m_res = client.get("/api/v1/equipment", headers={"Authorization": f"Bearer {token_viewer}"})
    machine_id = m_res.get_json()["equipment"][0]["id"]

    defs_res = client.get("/api/v1/signals/definitions", headers={"Authorization": f"Bearer {token_viewer}"})
    def_id = defs_res.get_json()["definitions"][0]["id"]

    # Viewer can read signals
    read_res = client.get(f"/api/v1/equipment/{machine_id}/signals", headers={"Authorization": f"Bearer {token_viewer}"})
    assert read_res.status_code == 200

    # Viewer is denied creating signal mappings (403)
    create_res = client.post(
        f"/api/v1/equipment/{machine_id}/signals",
        json={"signal_definition_id": def_id, "source_node_id": "ns=2;s=Viewer.Denied"},
        headers={"Authorization": f"Bearer {token_viewer}"},
    )
    assert create_res.status_code == 403


def test_unauthenticated_signal_mapping_access_denied(client):
    res = client.get("/api/v1/signals/definitions")
    assert res.status_code == 401

    res2 = client.get("/api/v1/equipment/some-fake-id/signals")
    assert res2.status_code == 401


def test_incompatible_dimensions_validation_fails():
    # Source unit is mm/s (velocity), normalized_unit is g (acceleration)
    chk = SignalValidator.check_unit_compatibility(
        expected_unit="g",
        source_unit="mm/s",
        normalized_unit="g",
        dimension="acceleration",
    )
    assert not chk.passed
    assert chk.severity == "ERROR"
    assert "Incompatible physical dimensions" in chk.message


def test_missing_source_unit_produces_warning_status():
    chk = SignalValidator.check_unit_compatibility(
        expected_unit="°C",
        source_unit=None,
        normalized_unit="°C",
        dimension="temperature",
    )
    assert chk.passed
    assert chk.severity == "WARNING"


@pytest.mark.asyncio
async def test_non_variable_node_validation_fails(opcua_simulator, sim_port, app):
    """Attempting to validate an Object node as a telemetry signal fails with INVALID."""
    endpoint_url = f"opc.tcp://127.0.0.1:{sim_port}/pharmapredict/server/"
    config = ConnectionConfig(
        endpoint_url=endpoint_url,
        timeout_sec=3.0,
        user_auth_type=UserAuthType.ANONYMOUS,
        auto_trust_unknown=True,
    )
    client = SecureOPCUAClient(config)
    await client.connect()

    with app.app_context():
        # ns=0;i=85 is ObjectsFolder in OPC UA standard address space
        node_res, sample_res, _ = await SignalValidator.validate_node_and_read_sample(
            client=client,
            source_node_id="ns=0;i=85",
            expected_type="Double",
            scaling_factor=1.0,
            offset=0.0,
            source_unit="°C",
            target_unit="°C",
        )
        assert not node_res.passed
        assert "Only Variable nodes can be mapped" in node_res.message

    await client.disconnect()


def test_signal_validation_and_audit_history_endpoint(opcua_simulator, sim_port, client):
    token = get_auth_token(client, "engineer@getzpharma.com", "Engineer@123")
    m_res = client.get("/api/v1/equipment", headers={"Authorization": f"Bearer {token}"})
    machine_id = m_res.get_json()["equipment"][0]["id"]

    node_id_str = opcua_simulator.blister_temp_node.nodeid.to_string()
    defs_res = client.get("/api/v1/signals/definitions", headers={"Authorization": f"Bearer {token}"})
    def_id = next(d["id"] for d in defs_res.get_json()["definitions"] if d["signal_code"] == "MOTOR_TEMP")

    # Create mapping
    client.post(
        f"/api/v1/equipment/{machine_id}/signals",
        json={
            "signal_definition_id": def_id,
            "source_node_id": node_id_str,
            "source_data_type": "Double",
            "source_unit": "°C",
            "normalized_unit": "°C",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    # Validate via REST API
    endpoint_url = f"opc.tcp://127.0.0.1:{sim_port}/pharmapredict/server/"
    val_res = client.post(
        f"/api/v1/equipment/{machine_id}/signals/validate",
        json={"endpoint_url": endpoint_url},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert val_res.status_code == 200
    val_data = val_res.get_json()
    assert val_data["count"] >= 1
    assert "summary" in val_data

    # Query audit history
    hist_res = client.get(
        f"/api/v1/equipment/{machine_id}/signals/validation-results",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert hist_res.status_code == 200
    hist_data = hist_res.get_json()
    assert hist_data["count"] >= 1
    assert hist_data["results"][0]["validation_status"] in ("VALID", "WARNING")

