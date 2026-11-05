import asyncio
import os
import pytest
import pytest_asyncio
from app.modules.connectivity.models import (
    ConnectionState,
    ConnectionConfig,
    SecurityPolicy,
    SecurityMode,
    UserAuthType,
    OPCUAError,
    ReadOnlyError,
    AuthenticationError,
    UntrustedCertificateError,
    ConnectionTimeoutError,
)
from app.modules.connectivity.opcua_client import SecureOPCUAClient
from app.modules.connectivity.connection_manager import ConnectionLifecycleManager
from app.modules.connectivity.simulator import PharmaOPCUASimulator


@pytest_asyncio.fixture
async def opcua_simulator():
    """Spin up an isolated pharmaceutical OPC UA simulator for testing."""
    simulator = PharmaOPCUASimulator(
        port=48420,
        enable_security=False,
        valid_users={"pharma_operator": "OperatorPass123!"}
    )
    await simulator.start()
    yield simulator
    await simulator.stop()


@pytest_asyncio.fixture
async def secure_opcua_simulator():
    """Spin up an encrypted pharmaceutical OPC UA simulator with X.509 certificates."""
    test_cert_dir = os.path.join(os.path.dirname(__file__), ".test_certs")
    simulator = PharmaOPCUASimulator(
        port=48421,
        enable_security=True,
        cert_dir=test_cert_dir,
        valid_users={"pharma_operator": "OperatorPass123!"}
    )
    await simulator.start()
    yield simulator
    await simulator.stop()


# =============================================================================
# 1. SUCCESSFUL CONNECTION TEST
# =============================================================================

@pytest.mark.asyncio
async def test_successful_connection(opcua_simulator):
    """Verify clean asynchronous connection and reading telemetry values."""
    config = ConnectionConfig(
        endpoint_url=opcua_simulator.get_endpoint(),
        timeout_sec=4.0,
        security_policy=SecurityPolicy.NONE,
        security_mode=SecurityMode.NONE,
        user_auth_type=UserAuthType.ANONYMOUS,
    )
    client = SecureOPCUAClient(config)
    assert client.get_state() == ConnectionState.DISCONNECTED

    connected = await client.connect()
    assert connected is True
    assert client.get_state() == ConnectionState.CONNECTED

    # Verify read operation from simulated node
    speed_node_id = opcua_simulator.blister_speed_node.nodeid.to_string()
    val = await client.read_value(speed_node_id)
    assert val == 240.0

    # Verify health check
    health = await client.check_health()
    assert health.is_healthy is True
    assert health.latency_ms is not None
    assert health.latency_ms >= 0.0

    await client.disconnect()
    assert client.get_state() == ConnectionState.DISCONNECTED


# =============================================================================
# 2. INVALID ENDPOINT TEST
# =============================================================================

@pytest.mark.asyncio
async def test_invalid_endpoint():
    """Verify handling of invalid or non-existent OPC UA endpoint."""
    config = ConnectionConfig(
        endpoint_url="opc.tcp://127.0.0.1:49991/nonexistent/server/",
        timeout_sec=1.5,
    )
    client = SecureOPCUAClient(config)

    with pytest.raises((ConnectionTimeoutError, OPCUAError)):
        await client.connect()

    assert client.get_state() == ConnectionState.ERROR


# =============================================================================
# 3. WRONG CREDENTIALS TEST
# =============================================================================

@pytest.mark.asyncio
async def test_wrong_credentials(opcua_simulator):
    """Verify rejection when user provides incorrect credentials."""
    config = ConnectionConfig(
        endpoint_url=opcua_simulator.get_endpoint(),
        timeout_sec=3.0,
        user_auth_type=UserAuthType.USERNAME,
        username="pharma_operator",
        password="COMPLETELY_WRONG_PASSWORD!",
    )
    client = SecureOPCUAClient(config)

    with pytest.raises(AuthenticationError):
        await client.connect()

    assert client.get_state() == ConnectionState.ERROR


# =============================================================================
# 4. UNTRUSTED CERTIFICATE TEST (Requirement 6)
# =============================================================================

@pytest.mark.asyncio
async def test_untrusted_certificate_rejected(secure_opcua_simulator):
    """Verify Requirement 6: Do not automatically trust unknown certificates."""
    server_fp = secure_opcua_simulator.get_server_certificate_fingerprint()
    assert server_fp is not None

    # Connect with auto_trust_unknown=False and without trusted fingerprint
    config = ConnectionConfig(
        endpoint_url=secure_opcua_simulator.get_endpoint(),
        timeout_sec=3.0,
        security_policy=SecurityPolicy.BASIC256_SHA256,
        security_mode=SecurityMode.SIGN_AND_ENCRYPT,
        auto_trust_unknown=False,
        trusted_cert_fingerprints=["00:11:22:33:44:55:66:77"],  # Mismatched fingerprint
    )
    client = SecureOPCUAClient(config)

    with pytest.raises(UntrustedCertificateError) as exc_info:
        await client.connect()

    assert "not in the trusted certificate store" in str(exc_info.value)
    assert client.get_state() == ConnectionState.ERROR

    # Now provide the genuine server fingerprint to verify trust validation passes
    trusted_config = ConnectionConfig(
        endpoint_url=secure_opcua_simulator.get_endpoint(),
        timeout_sec=4.0,
        security_policy=SecurityPolicy.BASIC256_SHA256,
        security_mode=SecurityMode.SIGN_AND_ENCRYPT,
        auto_trust_unknown=False,
        trusted_cert_fingerprints=[server_fp],
    )
    trusted_client = SecureOPCUAClient(trusted_config)
    trusted_connected = await trusted_client.connect()
    assert trusted_connected is True
    assert trusted_client.get_state() == ConnectionState.CONNECTED
    await trusted_client.disconnect()


# =============================================================================
# 5. SERVER SHUTDOWN DETECTION TEST
# =============================================================================

@pytest.mark.asyncio
async def test_server_shutdown_detection(opcua_simulator):
    """Verify health monitor detects server termination."""
    config = ConnectionConfig(
        endpoint_url=opcua_simulator.get_endpoint(),
        timeout_sec=2.0,
    )
    client = SecureOPCUAClient(config)
    await client.connect()
    assert client.get_state() == ConnectionState.CONNECTED

    # Abruptly stop the server
    await opcua_simulator.stop()

    # Health check should now fail and transition state to ERROR
    health = await client.check_health()
    assert health.is_healthy is False
    assert client.get_state() == ConnectionState.ERROR


# =============================================================================
# 6. BOUNDED EXPONENTIAL BACKOFF AUTOMATIC RECONNECTION TEST (Requirement 8)
# =============================================================================

@pytest.mark.asyncio
async def test_bounded_reconnection_backoff():
    """Verify bounded automatic reconnection with exponential backoff."""
    config = ConnectionConfig(
        endpoint_url="opc.tcp://127.0.0.1:48425/offline/server/",
        timeout_sec=0.2,
        initial_backoff_sec=0.05,
        backoff_factor=1.5,
        max_backoff_sec=0.2,
        max_reconnect_attempts=3,  # Bounded to 3 attempts
    )
    manager = ConnectionLifecycleManager(config=config, machine_id="test-machine-01")

    # Initial connect will fail and trigger bounded reconnection loop
    with pytest.raises(Exception):
        await manager.connect_and_start_monitoring()

    assert manager.get_state() in (ConnectionState.CONNECTING, ConnectionState.RECONNECTING, ConnectionState.ERROR)

    # Wait for the bounded backoff loop to finish all 3 attempts
    await asyncio.sleep(1.8)

    # Reconnection attempts should be bounded, halting at ERROR state
    assert manager._reconnect_attempts >= 3
    assert manager.get_state() == ConnectionState.ERROR
    assert "Exceeded maximum reconnection attempts" in (manager.client._last_error or "")


# =============================================================================
# 7. GRACEFUL DISCONNECTION TEST
# =============================================================================

@pytest.mark.asyncio
async def test_graceful_disconnection(opcua_simulator):
    """Verify clean resource cleanup and state transition on disconnect."""
    config = ConnectionConfig(
        endpoint_url=opcua_simulator.get_endpoint(),
        timeout_sec=3.0,
    )
    client = SecureOPCUAClient(config)
    await client.connect()
    assert client.get_state() == ConnectionState.CONNECTED

    await client.disconnect()
    assert client.get_state() == ConnectionState.DISCONNECTED

    # Reading after disconnect must be rejected
    speed_node_id = opcua_simulator.blister_speed_node.nodeid.to_string()
    with pytest.raises(OPCUAError) as exc_info:
        await client.read_value(speed_node_id)

    assert "client is DISCONNECTED" in str(exc_info.value)


# =============================================================================
# 8. NO WRITE OPERATIONS TEST (Requirement 12)
# =============================================================================

@pytest.mark.asyncio
async def test_no_write_operations(opcua_simulator):
    """Verify Requirement 12: Write operations are strictly prohibited."""
    config = ConnectionConfig(
        endpoint_url=opcua_simulator.get_endpoint(),
        timeout_sec=3.0,
    )
    client = SecureOPCUAClient(config)
    await client.connect()

    speed_node_id = opcua_simulator.blister_speed_node.nodeid.to_string()

    # 1. Attempt write_value
    with pytest.raises(ReadOnlyError) as exc1:
        await client.write_value(speed_node_id, 999.0)
    assert "write operations are strictly disallowed" in str(exc1.value)

    # 2. Attempt write_attribute
    with pytest.raises(ReadOnlyError) as exc2:
        await client.write_attribute(speed_node_id, 13, 999.0)
    assert "write operations are strictly disallowed" in str(exc2.value)

    # 3. Attempt set_value
    with pytest.raises(ReadOnlyError) as exc3:
        await client.set_value(speed_node_id, 999.0)
    assert "write operations are strictly disallowed" in str(exc3.value)

    # Verify that the value on the simulator was NOT modified
    current_val = await client.read_value(speed_node_id)
    assert current_val == 240.0

    await client.disconnect()

