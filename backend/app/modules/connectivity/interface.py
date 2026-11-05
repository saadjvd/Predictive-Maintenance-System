from abc import ABC, abstractmethod
from typing import Callable, Any, Optional, Dict
from app.modules.connectivity.models import ConnectionState, ConnectionHealth, ReadOnlyError


StateListener = Callable[[ConnectionState, Optional[str]], None]


class BaseConnector(ABC):
    """Abstract interface for all industrial protocol connectors (OPC UA, Modbus, MQTT)."""

    @abstractmethod
    async def connect(self) -> bool:
        """Asynchronously connect to industrial server/gateway."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Asynchronously disconnect and release all network resources."""
        pass

    @abstractmethod
    def get_state(self) -> ConnectionState:
        """Return the current connection state."""
        pass

    @abstractmethod
    async def check_health(self) -> ConnectionHealth:
        """Execute a heartbeat check and return connection health metrics."""
        pass

    @abstractmethod
    def add_state_listener(self, listener: StateListener) -> None:
        """Register a callback for connection state transitions."""
        pass

    @abstractmethod
    def remove_state_listener(self, listener: StateListener) -> None:
        """Unregister a state transition callback."""
        pass

    @abstractmethod
    async def read_value(self, node_id: str) -> Any:
        """Read a single telemetry value from a node."""
        pass

    # =========================================================================
    # MANDATORY READ-ONLY ENFORCEMENT (Requirement 12)
    # =========================================================================

    async def write_value(self, node_id: str, value: Any) -> None:
        """Strictly disallow write operations on industrial equipment."""
        raise ReadOnlyError("OPC UA write operations are strictly disallowed. PharmaPredict AI is read-only.")

    async def write_attribute(self, node_id: str, attribute: Any, value: Any) -> None:
        """Strictly disallow attribute modification on industrial equipment."""
        raise ReadOnlyError("OPC UA write operations are strictly disallowed. PharmaPredict AI is read-only.")

