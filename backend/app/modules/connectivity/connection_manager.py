import asyncio
import threading
import logging
from typing import Optional, Dict, Any, Callable
from datetime import datetime, timezone

from app.modules.connectivity.models import (
    ConnectionState,
    ConnectionConfig,
    ConnectionHealth,
    OPCUAError,
    ReadOnlyError,
)
from app.modules.connectivity.opcua_client import SecureOPCUAClient

logger = logging.getLogger(__name__)


class ConnectionLifecycleManager:
    """Manages the full lifecycle of a secure OPC UA connection.
    
    Responsibilities:
    - Bounded automatic reconnection with exponential backoff (Requirement 8)
    - Periodic health monitoring & heartbeats (Requirement 7)
    - Thread-isolated async event loop separate from Flask handlers (Requirement 11)
    - Status publishing to Flask backend and listeners (Requirement 10)
    """

    def __init__(self, config: ConnectionConfig, machine_id: Optional[str] = None):
        self.config = config
        self.machine_id = machine_id
        self.client = SecureOPCUAClient(config)
        self._reconnect_attempts: int = 0
        self._is_running: bool = False
        self._should_reconnect: bool = True
        self._monitor_task: Optional[asyncio.Task] = None
        self._reconnect_task: Optional[asyncio.Task] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._worker_thread: Optional[threading.Thread] = None
        self._status_callbacks: list[Callable[[str, ConnectionState, Optional[str]], None]] = []

        # Wire up client state transitions
        self.client.add_state_listener(self._on_client_state_changed)

    def register_status_callback(self, cb: Callable[[str, ConnectionState, Optional[str]], None]) -> None:
        """Register a callback for machine status publishing."""
        if cb not in self._status_callbacks:
            self._status_callbacks.append(cb)

    def _on_client_state_changed(self, new_state: ConnectionState, error_msg: Optional[str]) -> None:
        """Broadcast state transition to registered backend status publishers."""
        logger.info(
            f"[OPCUA-Manager] Machine={self.machine_id} transitioned to {new_state.value}. Error={error_msg}"
        )
        for cb in list(self._status_callbacks):
            try:
                cb(self.machine_id or "unknown", new_state, error_msg)
            except Exception as e:
                logger.error(f"Error in status callback: {e}")

    # =========================================================================
    # DEDICATED WORKER THREAD ISOLATION (Requirement 11)
    # =========================================================================

    def start_background_worker(self) -> None:
        """Launch isolated worker thread with its own asyncio loop for OPC UA operations."""
        if self._worker_thread and self._worker_thread.is_alive():
            return

        self._is_running = True
        self._loop = asyncio.new_event_loop()
        started_event = threading.Event()

        def _runner():
            asyncio.set_event_loop(self._loop)
            self._loop.call_soon(started_event.set)
            try:
                self._loop.run_forever()
            finally:
                self._loop.close()

        self._worker_thread = threading.Thread(
            target=_runner,
            daemon=True,
            name=f"OPCUA-Worker-{self.machine_id or 'default'}"
        )
        self._worker_thread.start()
        started_event.wait(timeout=3.0)

    def _run_event_loop(self) -> None:
        """Run the dedicated asyncio event loop on the worker thread."""
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_forever()
        finally:
            self._loop.close()

    def stop_background_worker(self) -> None:
        """Stop the background worker thread and cancel pending tasks."""
        self._is_running = False
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._worker_thread:
            self._worker_thread.join(timeout=3.0)
            self._worker_thread = None

    # =========================================================================
    # ASYNCHRONOUS LIFECYCLE METHODS
    # =========================================================================

    async def connect_and_start_monitoring(self) -> bool:
        """Connect to the server and begin the periodic health monitor."""
        self._should_reconnect = True
        self._reconnect_attempts = 0
        try:
            success = await self.client.connect()
            if success:
                self._start_health_monitor()
                return True
            return False
        except Exception as e:
            logger.warning(f"[OPCUA-Manager] Initial connect failed: {e}. Initiating bounded reconnection.")
            self._trigger_reconnect()
            raise

    async def disconnect_and_stop(self) -> None:
        """Gracefully disconnect, stop monitor, and halt reconnection."""
        self._should_reconnect = False
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            self._monitor_task = None

        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
            self._reconnect_task = None

        await self.client.disconnect()

    def _start_health_monitor(self) -> None:
        """Launch background health monitoring loop."""
        if self._monitor_task and not self._monitor_task.done():
            return
        self._monitor_task = asyncio.create_task(self._health_monitor_loop())

    async def _health_monitor_loop(self) -> None:
        """Periodic heartbeat loop that detects server drops."""
        while self._is_running and self.client.get_state() == ConnectionState.CONNECTED:
            try:
                await asyncio.sleep(self.config.health_check_interval_sec)
                health = await self.client.check_health()
                if not health.is_healthy:
                    logger.warning(f"[OPCUA-Manager] Health check failed: {health.error_message}")
                    if self._should_reconnect:
                        self._trigger_reconnect()
                    break
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[OPCUA-Manager] Unexpected error in health monitor loop: {e}")
                if self._should_reconnect:
                    self._trigger_reconnect()
                break

    # =========================================================================
    # BOUNDED EXPONENTIAL BACKOFF RECONNECTION (Requirement 8)
    # =========================================================================

    def _trigger_reconnect(self) -> None:
        """Schedule the bounded reconnection task if not already in progress."""
        if not self._should_reconnect:
            return
        if self._reconnect_task and not self._reconnect_task.done():
            return
        self._reconnect_task = asyncio.create_task(self._bounded_reconnect_loop())

    async def _bounded_reconnect_loop(self) -> None:
        """Execute bounded exponential backoff reconnection.
        
        Formula: delay = min(initial_backoff * (backoff_factor ** attempt), max_backoff)
        Stops after max_reconnect_attempts, transitioning to ERROR.
        """
        while self._should_reconnect and self._reconnect_attempts < self.config.max_reconnect_attempts:
            self._reconnect_attempts += 1
            delay = min(
                self.config.initial_backoff_sec * (self.config.backoff_factor ** (self._reconnect_attempts - 1)),
                self.config.max_backoff_sec
            )

            self.client.set_state(
                ConnectionState.RECONNECTING,
                f"Reconnection attempt {self._reconnect_attempts}/{self.config.max_reconnect_attempts} in {delay:.1f}s"
            )

            logger.info(
                f"[OPCUA-Manager] Reconnecting attempt {self._reconnect_attempts}/{self.config.max_reconnect_attempts} in {delay:.1f}s..."
            )
            try:
                await asyncio.sleep(delay)
                connected = await self.client.connect()
                if connected:
                    logger.info("[OPCUA-Manager] Reconnected successfully!")
                    self._reconnect_attempts = 0
                    self._start_health_monitor()
                    return
            except asyncio.CancelledError:
                return
            except Exception as e:
                logger.warning(f"[OPCUA-Manager] Reconnect attempt {self._reconnect_attempts} failed: {e}")

        # If max attempts exceeded, enter ERROR state and stop thrashing network
        final_err = (
            f"Exceeded maximum reconnection attempts ({self.config.max_reconnect_attempts}). "
            f"Halting automatic reconnection to prevent server denial-of-service."
        )
        logger.error(f"[OPCUA-Manager] {final_err}")
        self.client.set_state(ConnectionState.ERROR, final_err)

    # =========================================================================
    # CONVENIENCE PASS-THROUGHS
    # =========================================================================

    def get_state(self) -> ConnectionState:
        return self.client.get_state()

    async def check_health(self) -> ConnectionHealth:
        health = await self.client.check_health()
        health.reconnect_attempts = self._reconnect_attempts
        return health

    async def read_value(self, node_id: str) -> Any:
        return await self.client.read_value(node_id)


# =============================================================================
# SINGLETON GLOBAL GATEWAY REGISTRY
# =============================================================================

class GatewayManager:
    """Central registry of active OPC UA connections indexed by machine ID."""
    _connections: Dict[str, ConnectionLifecycleManager] = {}
    _lock = threading.Lock()

    @classmethod
    def register(cls, machine_id: str, manager: ConnectionLifecycleManager) -> None:
        with cls._lock:
            cls._connections[machine_id] = manager

    @classmethod
    def get(cls, machine_id: str) -> Optional[ConnectionLifecycleManager]:
        with cls._lock:
            return cls._connections.get(machine_id)

    @classmethod
    def remove(cls, machine_id: str) -> Optional[ConnectionLifecycleManager]:
        with cls._lock:
            return cls._connections.pop(machine_id, None)

    @classmethod
    def all_connections(cls) -> Dict[str, ConnectionLifecycleManager]:
        with cls._lock:
            return dict(cls._connections)

    @classmethod
    def clear(cls) -> None:
        """Clear all connections and stop all background worker threads."""
        with cls._lock:
            for mgr in list(cls._connections.values()):
                try:
                    mgr.stop_background_worker()
                except Exception:
                    pass
            cls._connections.clear()

