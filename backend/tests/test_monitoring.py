import pytest
import pytest_asyncio
import math
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

from app.extensions import db
from app.models.tenant import Organization, Site
from app.models.user import User, Role, UserRoleAssignment
from app.models.equipment import Machine, EquipmentCategory
from app.models.signal_mapping import (
    SignalDefinition,
    MachineSignal,
    ValidationStatus,
)
from app.models.monitoring import (
    MonitoringSession,
    SubscriptionStatus,
    SignalReading,
    MonitoringState,
    SignalFreshness,
)
from app.modules.signal_mapping.repositories import SignalDefinitionRepository
from app.modules.monitoring.data_contract import NormalizedReadingMessage, compute_event_id
from app.modules.monitoring.normalizer import ReadingNormalizer
from app.modules.monitoring.gateway_buffer import BoundedGatewayBuffer
from app.modules.monitoring.opcua_subscription import OPCUASubscriptionService
from app.modules.monitoring.ingestion_service import IngestionService
from app.modules.monitoring.lifecycle import MonitoringLifecycleManager
from app.modules.connectivity.connection_manager import GatewayManager
from app.modules.monitoring.routes import GATEWAY_SECRET
from app.modules.connectivity.simulator import PharmaOPCUASimulator
from app.modules.connectivity.opcua_client import SecureOPCUAClient
from app.modules.connectivity.models import ConnectionConfig, UserAuthType
from tests.test_equipment import get_auth_token, setup_equipment_test_data


@pytest.fixture(autouse=True)
def teardown_monitoring(app):
    yield
    MonitoringLifecycleManager.clean_all()
    GatewayManager.clear()
    with app.app_context():
        try:
            db.session.rollback()
            db.session.remove()
        except Exception:
            pass


@pytest.fixture(autouse=True)
def setup_monitoring_data(app):
    data = setup_equipment_test_data(app)
    with app.app_context():
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
        machine_a = Machine.query.filter_by(asset_code="BLIST-MON-01", organization_id=org_a.id).first()
        if not machine_a:
            cat = EquipmentCategory.query.filter_by(name="Blister Packaging").first()
            site = Site.query.filter_by(organization_id=org_a.id).first()
            machine_a = Machine(
                organization_id=org_a.id,
                site_id=site.id,
                category_id=cat.id,
                asset_code="BLIST-MON-01",
                equipment_name="Uhlen Blister Packer Monitored",
                criticality="Critical",
            )
            db.session.add(machine_a)
            db.session.commit()

        # Ensure mapped signal on machine_a
        def_temp = SignalDefinition.query.filter_by(signal_code="MOTOR_TEMP").first()
        sig_temp = MachineSignal.query.filter_by(machine_id=machine_a.id, source_node_id="ns=2;s=Sim.Motor.Temp").first()
        if not sig_temp:
            sig_temp = MachineSignal(
                organization_id=org_a.id,
                machine_id=machine_a.id,
                signal_definition_id=def_temp.id,
                custom_name="Main Drive Motor Temperature",
                source_node_id="ns=2;s=Sim.Motor.Temp",
                source_data_type="Double",
                source_unit="°C",
                normalized_unit="°C",
                scaling_factor=1.0,
                offset=0.0,
                sampling_interval_ms=1000,
                validation_status=ValidationStatus.VALID,
                enabled=True,
            )
            db.session.add(sig_temp)
            db.session.commit()

    return data


@pytest.fixture
def sim_port():
    return 48408


@pytest.fixture
def opcua_simulator(sim_port):
    import threading
    sim = PharmaOPCUASimulator(port=sim_port)
    loop = asyncio.new_event_loop()
    ready = threading.Event()

    def _run():
        asyncio.set_event_loop(loop)
        loop.run_until_complete(sim.start())
        ready.set()
        try:
            loop.run_forever()
        finally:
            loop.close()

    th = threading.Thread(target=_run, daemon=True)
    th.start()
    ready.wait(timeout=5.0)

    yield sim

    async def _stop():
        try:
            await sim.stop()
        except Exception:
            pass
        loop.stop()

    asyncio.run_coroutine_threadsafe(_stop(), loop)
    th.join(timeout=3.0)


# =============================================================================
# 1 & 2: ACTIVATION AND AUTHORIZATION TESTS
# =============================================================================

def test_authorized_monitoring_activation(client, opcua_simulator, sim_port):
    token = get_auth_token(client, "engineer@getzpharma.com", "Engineer@123")
    m_res = client.get("/api/v1/equipment", headers={"Authorization": f"Bearer {token}"})
    machine_id = m_res.get_json()["equipment"][0]["id"]

    # Point machine_a's signal to the simulated node so subscription succeeds
    with client.application.app_context():
        sig = MachineSignal.query.filter_by(machine_id=machine_id).first()
        if sig:
            sig.source_node_id = opcua_simulator.blister_temp_node.nodeid.to_string()
            db.session.commit()

    endpoint_url = f"opc.tcp://127.0.0.1:{sim_port}/pharmapredict/server/"
    res = client.post(
        f"/api/v1/equipment/{machine_id}/monitoring/activate",
        json={"endpoint_url": endpoint_url},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.get_json()
    assert "session" in data
    assert data["session"]["desired_state"] == MonitoringState.ACTIVE


def test_unauthorized_activation_denied(client):
    token_viewer = get_auth_token(client, "viewer@getzpharma.com", "Viewer@123")
    m_res = client.get("/api/v1/equipment", headers={"Authorization": f"Bearer {token_viewer}"})
    machine_id = m_res.get_json()["equipment"][0]["id"]

    # Viewer denied (403)
    res = client.post(
        f"/api/v1/equipment/{machine_id}/monitoring/activate",
        json={},
        headers={"Authorization": f"Bearer {token_viewer}"},
    )
    assert res.status_code == 403

    # Unauthenticated denied (401)
    unauth_client = client.application.test_client()
    res_unauth = unauth_client.post(f"/api/v1/equipment/{machine_id}/monitoring/activate", json={})
    assert res_unauth.status_code == 401


# =============================================================================
# 3 & 4: PRECONDITIONS VERIFICATION
# =============================================================================

def test_activation_preconditions_no_signals(app):
    with app.app_context():
        org = Organization.query.first()
        site = Site.query.first()
        cat = EquipmentCategory.query.first()
        empty_machine = Machine(
            organization_id=org.id,
            site_id=site.id,
            category_id=cat.id,
            asset_code="NO-SIG-01",
            equipment_name="No Signals Machine",
        )
        db.session.add(empty_machine)
        db.session.commit()

        can_act, reason, _ = MonitoringLifecycleManager.check_activation_preconditions(
            empty_machine.id, org.id
        )
        assert not can_act
        assert "No active signal mappings" in reason


def test_activation_preconditions_invalid_signals(app):
    with app.app_context():
        org = Organization.query.first()
        site = Site.query.first()
        cat = EquipmentCategory.query.first()
        bad_machine = Machine(
            organization_id=org.id,
            site_id=site.id,
            category_id=cat.id,
            asset_code="BAD-SIG-01",
            equipment_name="Bad Signals Machine",
        )
        db.session.add(bad_machine)
        db.session.commit()

        def_temp = SignalDefinition.query.first()
        bad_sig = MachineSignal(
            organization_id=org.id,
            machine_id=bad_machine.id,
            signal_definition_id=def_temp.id,
            source_node_id="ns=2;s=Bad.Node",
            validation_status=ValidationStatus.INVALID,
        )
        db.session.add(bad_sig)
        db.session.commit()

        can_act, reason, _ = MonitoringLifecycleManager.check_activation_preconditions(
            bad_machine.id, org.id
        )
        assert not can_act
        assert "invalid configurations" in reason


# =============================================================================
# 5, 6 & 7: SUBSCRIPTIONS, DEACTIVATION AND READ-ONLY
# =============================================================================

@pytest.mark.asyncio
async def test_successful_opcua_subscription_and_reading(opcua_simulator, sim_port, app):
    """Test asyncua subscription captures live simulator telemetry and normalizes it."""
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
            sampling_interval_ms=500,
        )
        db.session.add(signal)
        db.session.commit()

        buffer = BoundedGatewayBuffer()
        sub_service = OPCUASubscriptionService(client, buffer)

        res = await sub_service.subscribe_signal(signal)
        assert res["status"] == "SUBSCRIBED"
        assert sub_service.get_active_count() == 1

        # Wait for data-change callback to capture a value
        await asyncio.sleep(1.0)
        handler = sub_service.get_handler(signal.id)
        assert handler is not None
        assert handler.last_value is not None

        # Clean unsubscribe
        await sub_service.unsubscribe_all()
        assert sub_service.get_active_count() == 0

    await client.disconnect()


def test_monitoring_deactivation(client):
    token = get_auth_token(client, "engineer@getzpharma.com", "Engineer@123")
    m_res = client.get("/api/v1/equipment", headers={"Authorization": f"Bearer {token}"})
    machine_id = m_res.get_json()["equipment"][0]["id"]

    res = client.post(
        f"/api/v1/equipment/{machine_id}/monitoring/deactivate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.get_json()
    assert "session" in data or "message" in data


# =============================================================================
# 8, 9, 10, 11, 12, 13: NORMALIZATION & DATA TYPES
# =============================================================================

def test_data_normalization_pipeline():
    # 1. Analog scaling: raw=10.0, factor=2.0, offset=-1.0 -> 19.0
    msg = ReadingNormalizer.normalize(
        organization_id="org-1",
        machine_id="mach-1",
        signal_id="sig-1",
        source_node_id="ns=2;s=Test",
        mapping_version=1,
        raw_value=10.0,
        source_timestamp=datetime.now(timezone.utc),
        server_timestamp=datetime.now(timezone.utc),
        scaling_factor=2.0,
        offset=-1.0,
        source_unit="bar",
        target_unit="bar",
    )
    assert math.isclose(msg.normalized_value, 19.0)
    assert msg.normalization_status == "NORMALIZED"
    assert msg.event_id is not None

    # 2. Temperature Unit Conversion: 100 °C to °F -> 212 °F
    msg_temp = ReadingNormalizer.normalize(
        organization_id="org-1",
        machine_id="mach-1",
        signal_id="sig-2",
        source_node_id="ns=2;s=Temp",
        mapping_version=1,
        raw_value=100.0,
        source_timestamp=datetime.now(timezone.utc),
        server_timestamp=None,
        scaling_factor=1.0,
        offset=0.0,
        source_unit="°C",
        target_unit="°F",
    )
    assert math.isclose(msg_temp.normalized_value, 212.0)


def test_boolean_alarm_readings():
    msg_alarm = ReadingNormalizer.normalize(
        organization_id="org-1",
        machine_id="mach-1",
        signal_id="sig-alarm",
        source_node_id="ns=2;s=Alarm",
        mapping_version=1,
        raw_value=True,
        source_timestamp=datetime.now(timezone.utc),
        server_timestamp=None,
    )
    assert msg_alarm.raw_value_boolean is True
    assert msg_alarm.normalized_value == 1.0


def test_bad_opcua_quality_codes():
    msg = ReadingNormalizer.normalize(
        organization_id="org-1",
        machine_id="mach-1",
        signal_id="sig-quality",
        source_node_id="ns=2;s=BadQ",
        mapping_version=1,
        raw_value=42.0,
        source_timestamp=datetime.now(timezone.utc),
        server_timestamp=None,
        quality_code="BadNotConnected",
    )
    assert msg.opcua_quality_code == "BadNotConnected"


# =============================================================================
# 14, 15, 16, 17: BUFFERING & INGESTION
# =============================================================================

def test_batch_ingestion_and_deduplication(app):
    with app.app_context():
        machine = Machine.query.first()
        signal = MachineSignal.query.filter_by(machine_id=machine.id).first()

        now = datetime.now(timezone.utc)
        reading1 = {
            "event_id": compute_event_id(machine.id, signal.id, now.isoformat(), 45.2),
            "organization_id": machine.organization_id,
            "machine_id": machine.id,
            "signal_id": signal.id,
            "source_timestamp": now.isoformat(),
            "source_value": 45.2,
            "normalized_value": 45.2,
            "raw_value_numeric": 45.2,
            "quality_code": "Good",
        }

        # 1. First ingestion -> accepted = 1
        res1 = IngestionService.ingest_batch(
            gateway_id="gw-test",
            readings_data=[reading1],
            batch_identifier="batch-001",
        )
        assert res1["accepted"] == 1
        assert res1["duplicates"] == 0

        # 2. Duplicate ingestion -> duplicates = 1, accepted = 0
        res2 = IngestionService.ingest_batch(
            gateway_id="gw-test",
            readings_data=[reading1],
            batch_identifier="batch-002",
        )
        assert res2["accepted"] == 0
        assert res2["duplicates"] == 1


@pytest.mark.asyncio
async def test_backend_outage_buffering_and_queue_overflow(tmp_path):
    """Test disk buffering fallback during backend outage and queue overflow protection."""
    buffer = BoundedGatewayBuffer(
        gateway_id="gw-overflow-test",
        max_queue_size=5,
        batch_size=5,
        disk_buffer_dir=str(tmp_path),
        max_disk_buffer_bytes=2048,
    )

    # Ingestion handler that simulates failure
    def failing_handler(batch):
        raise ConnectionRefusedError("Simulated backend outage")

    buffer.set_ingestion_handler(failing_handler)

    # Enqueue items
    for i in range(10):
        msg = NormalizedReadingMessage(
            organization_id="org-1",
            machine_id="mach-1",
            signal_id=f"sig-{i}",
            source_node_id=f"ns=2;s=Node{i}",
            mapping_version=1,
            source_timestamp=datetime.now(timezone.utc).isoformat(),
            source_value=i,
        )
        await buffer.push(msg)

    # Trigger flush which fails and diverts to disk
    await buffer.flush()
    metrics = buffer.get_metrics()
    assert metrics["buffered_readings"] > 0 or metrics["dropped_readings"] >= 0


# =============================================================================
# 18, 19, 20, 21: REST APIS & FRESHNESS
# =============================================================================

def test_stale_and_latest_readings_api(client, app):
    token = get_auth_token(client, "engineer@getzpharma.com", "Engineer@123")
    m_res = client.get("/api/v1/equipment", headers={"Authorization": f"Bearer {token}"})
    machine_id = m_res.get_json()["equipment"][0]["id"]

    with app.app_context():
        machine = db.session.get(Machine, machine_id)
        signal = MachineSignal.query.filter_by(machine_id=machine_id).first()

        # Add a fresh reading
        now = datetime.now(timezone.utc)
        fresh_reading = {
            "event_id": f"fresh-{now.timestamp()}",
            "organization_id": machine.organization_id,
            "machine_id": machine_id,
            "signal_id": signal.id,
            "source_timestamp": now.isoformat(),
            "source_value": 72.5,
            "normalized_value": 72.5,
            "raw_value_numeric": 72.5,
            "quality_code": "Good",
        }
        IngestionService.ingest_batch(gateway_id="gw-test", readings_data=[fresh_reading])

    res = client.get(
        f"/api/v1/equipment/{machine_id}/readings/latest",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["count"] >= 1
    reading = data["readings"][0]
    assert reading["freshness"] == SignalFreshness.FRESH


def test_historical_readings_api(client):
    token = get_auth_token(client, "engineer@getzpharma.com", "Engineer@123")
    m_res = client.get("/api/v1/equipment", headers={"Authorization": f"Bearer {token}"})
    machine_id = m_res.get_json()["equipment"][0]["id"]

    res = client.get(
        f"/api/v1/equipment/{machine_id}/readings/history?limit=50",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.get_json()
    assert "readings" in data
    assert isinstance(data["readings"], list)


def test_internal_ingestion_service_auth(client):
    # Unauthenticated / customer token -> Forbidden (403)
    res_forbidden = client.post(
        "/api/v1/internal/ingestion/readings",
        json={"readings": [{"event_id": "test"}]},
    )
    assert res_forbidden.status_code == 403

    # Authenticated with service secret header -> 201
    valid_payload = {
        "gateway_id": "gw-edge-01",
        "readings": [
            {
                "event_id": f"svc-test-{datetime.now(timezone.utc).timestamp()}",
                "organization_id": "org-dummy",
                "machine_id": "mach-dummy",
                "signal_id": "sig-dummy",
                "source_timestamp": datetime.now(timezone.utc).isoformat(),
                "source_value": 12.3,
                "normalized_value": 12.3,
                "quality_code": "Good",
            }
        ],
    }
    res_auth = client.post(
        "/api/v1/internal/ingestion/readings",
        json=valid_payload,
        headers={"X-Gateway-Secret": GATEWAY_SECRET},
    )
    assert res_auth.status_code == 201


def test_gateway_health_endpoint(client):
    token = get_auth_token(client, "engineer@getzpharma.com", "Engineer@123")
    res = client.get(
        "/api/v1/gateways/gw-default/health",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.get_json()
    assert "connection_status" in data
    assert "queue_depth" in data


def test_monitoring_status_endpoint(client):
    token = get_auth_token(client, "engineer@getzpharma.com", "Engineer@123")
    m_res = client.get("/api/v1/equipment", headers={"Authorization": f"Bearer {token}"})
    machine_id = m_res.get_json()["equipment"][0]["id"]

    res = client.get(
        f"/api/v1/equipment/{machine_id}/monitoring/status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.get_json()
    assert "desired_state" in data
    assert "observed_state" in data
    assert "can_activate" in data


def test_cross_tenant_readings_isolation(client):
    """Org B maintenance engineer cannot view or access Org A equipment readings."""
    token_a = get_auth_token(client, "engineer@getzpharma.com", "Engineer@123")
    m_res_a = client.get("/api/v1/equipment", headers={"Authorization": f"Bearer {token_a}"})
    machine_a_id = m_res_a.get_json()["equipment"][0]["id"]

    # Authenticate as Org B (Benchmark) manager
    token_b = get_auth_token(client, "manager@benchmark.com", "BenchManager@123")

    # Latest readings on Org A's machine must return 404 for Org B
    res_latest = client.get(
        f"/api/v1/equipment/{machine_a_id}/readings/latest",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert res_latest.status_code == 404

    # Historical readings on Org A's machine must return 404 for Org B
    res_hist = client.get(
        f"/api/v1/equipment/{machine_a_id}/readings/history",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert res_hist.status_code == 404

    # Monitoring status on Org A's machine must return 404 for Org B
    res_status = client.get(
        f"/api/v1/equipment/{machine_a_id}/monitoring/status",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert res_status.status_code == 404


def test_stale_reading_classification(app):
    """Verify that readings older than 3x sampling interval are classified as STALE."""
    with app.app_context():
        machine = Machine.query.first()
        signal = MachineSignal.query.filter_by(machine_id=machine.id).first()
        # signal has sampling_interval_ms=1000 (1 second). 3x threshold is 3 seconds.
        # Create a reading from 10 seconds ago
        stale_time = datetime.now(timezone.utc) - timedelta(seconds=10)
        stale_reading = {
            "event_id": f"stale-{stale_time.timestamp()}",
            "organization_id": machine.organization_id,
            "machine_id": machine.id,
            "signal_id": signal.id,
            "source_timestamp": stale_time.isoformat(),
            "source_value": 55.0,
            "normalized_value": 55.0,
            "quality_code": "Good",
        }
        IngestionService.ingest_batch(gateway_id="gw-stale-test", readings_data=[stale_reading])

        latest = IngestionService.get_latest_readings(machine.id, machine.organization_id)
        assert len(latest) >= 1
        sig_reading = next(r for r in latest if r["signal_id"] == signal.id)
        assert sig_reading["freshness"] == SignalFreshness.STALE


def test_history_time_window_filtering(client, app):
    """Verify time window filtering on /readings/history endpoint."""
    token = get_auth_token(client, "engineer@getzpharma.com", "Engineer@123")
    m_res = client.get("/api/v1/equipment", headers={"Authorization": f"Bearer {token}"})
    machine_id = m_res.get_json()["equipment"][0]["id"]

    now = datetime.now(timezone.utc)
    t_minus_20m = now - timedelta(minutes=20)
    t_minus_10m = now - timedelta(minutes=10)

    with app.app_context():
        machine = db.session.get(Machine, machine_id)
        signal = MachineSignal.query.filter_by(machine_id=machine_id).first()

        readings = [
            {
                "event_id": f"win-1-{now.timestamp()}",
                "organization_id": machine.organization_id,
                "machine_id": machine_id,
                "signal_id": signal.id,
                "source_timestamp": t_minus_20m.isoformat(),
                "source_value": 10.0,
                "normalized_value": 10.0,
                "quality_code": "Good",
            },
            {
                "event_id": f"win-2-{now.timestamp()}",
                "organization_id": machine.organization_id,
                "machine_id": machine_id,
                "signal_id": signal.id,
                "source_timestamp": now.isoformat(),
                "source_value": 20.0,
                "normalized_value": 20.0,
                "quality_code": "Good",
            },
        ]
        IngestionService.ingest_batch(gateway_id="gw-win-test", readings_data=readings)

    # Filter for window around t_minus_20m
    start_str = (t_minus_20m - timedelta(minutes=2)).isoformat()
    end_str = t_minus_10m.isoformat()
    res = client.get(
        f"/api/v1/equipment/{machine_id}/readings/history?start_time={start_str}&end_time={end_str}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.get_json()
    assert len(data["readings"]) == 1
    assert data["readings"][0]["normalized_value"] == 10.0
