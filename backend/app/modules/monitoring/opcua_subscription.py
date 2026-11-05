import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import asyncua
from asyncua import ua
from app.models.signal_mapping import MachineSignal
from app.modules.monitoring.normalizer import ReadingNormalizer
from app.modules.monitoring.gateway_buffer import BoundedGatewayBuffer
from app.modules.connectivity.opcua_client import SecureOPCUAClient

logger = logging.getLogger(__name__)


class SubscriptionNotificationHandler:
    """Asyncua subscription notification handler.
    Receives datachange_notification callbacks and dispatches normalized readings
    to the bounded gateway buffer without blocking the OPC UA subscription thread.
    """

    def __init__(
        self,
        signal: MachineSignal,
        buffer: BoundedGatewayBuffer,
        loop: asyncio.AbstractEventLoop,
    ):
        self.signal = signal
        self.buffer = buffer
        self.loop = loop
        self.last_received_at: Optional[datetime] = None
        self.revised_interval: Optional[float] = None
        self.last_value: Any = None

    def datachange_notification(self, node: asyncua.Node, val: Any, data: Any):
        """Standard asyncua data-change callback."""
        try:
            self.last_value = val
            self.last_received_at = datetime.now(timezone.utc)

            # Extract source timestamps and status code from DataValue
            source_ts = None
            server_ts = None
            quality = "Good"

            if hasattr(data, "monitored_item") and hasattr(data.monitored_item, "Value"):
                dv = data.monitored_item.Value
                source_ts = dv.SourceTimestamp
                server_ts = dv.ServerTimestamp
                if hasattr(dv, "StatusCode"):
                    is_good = dv.StatusCode.is_good() if hasattr(dv.StatusCode, "is_good") else True
                    quality = "Good" if is_good else f"Bad ({dv.StatusCode})"

            definition = self.signal.signal_definition
            target_unit = self.signal.normalized_unit or (definition.standard_unit if definition else None)

            # Normalize reading
            reading = ReadingNormalizer.normalize(
                organization_id=self.signal.organization_id,
                machine_id=self.signal.machine_id,
                signal_id=self.signal.id,
                source_node_id=self.signal.source_node_id,
                mapping_version=self.signal.mapping_version,
                raw_value=val,
                source_timestamp=source_ts,
                server_timestamp=server_ts,
                scaling_factor=self.signal.scaling_factor,
                offset=self.signal.offset,
                source_unit=self.signal.source_unit,
                target_unit=target_unit,
                sampling_interval_ms=self.signal.sampling_interval_ms,
                connector_id=self.signal.connector_id,
                gateway_id=self.buffer.gateway_id,
                quality_code=quality,
                simulator_flag=True,
            )

            # Schedule push into queue without blocking
            if self.loop and self.loop.is_running():
                asyncio.run_coroutine_threadsafe(self.buffer.push(reading), self.loop)

        except Exception as e:
            logger.error(f"[SubscriptionHandler] Error handling datachange for node {self.signal.source_node_id}: {e}")


class OPCUASubscriptionService:
    """Manages active asyncua subscriptions for validated machine signals."""

    def __init__(self, client: SecureOPCUAClient, buffer: BoundedGatewayBuffer):
        self.client = client
        self.buffer = buffer
        self._subscriptions: Dict[str, Any] = {}  # signal_id -> asyncua Subscription
        self._monitored_handles: Dict[str, Any] = {}  # signal_id -> handle
        self._handlers: Dict[str, SubscriptionNotificationHandler] = {}  # signal_id -> handler

    async def subscribe_signal(
        self, signal: MachineSignal, loop: Optional[asyncio.AbstractEventLoop] = None
    ) -> Dict[str, Any]:
        """Subscribe to a single validated signal node (STRICTLY READ-ONLY)."""
        if not self.client.is_connected():
            raise ConnectionError("Cannot subscribe: OPC UA client is not connected.")

        active_loop = loop or asyncio.get_running_loop()
        handler = SubscriptionNotificationHandler(signal, self.buffer, active_loop)

        # 1. Create subscription with signal's sampling interval
        period = max(50.0, float(signal.sampling_interval_ms))
        sub = await self.client.client.create_subscription(period, handler)

        # 2. Add monitored item (Variable node only)
        node = self.client.client.get_node(signal.source_node_id)
        node_class = await node.read_node_class()
        if node_class != ua.NodeClass.Variable:
            await sub.delete()
            raise ValueError(f"Node '{signal.source_node_id}' is {node_class.name}, not a Variable.")

        handle = await sub.subscribe_data_change(node)

        # Store references
        self._subscriptions[signal.id] = sub
        self._monitored_handles[signal.id] = handle
        self._handlers[signal.id] = handler

        revised_interval = getattr(sub, "period", period)
        handler.revised_interval = revised_interval

        logger.info(
            f"[OPCUASubscription] Subscribed to '{signal.source_node_id}' for signal {signal.id} (revised={revised_interval}ms)"
        )

        return {
            "signal_id": signal.id,
            "subscription_id": str(getattr(sub, "subscription_id", handle)),
            "status": "SUBSCRIBED",
            "revised_sampling_interval": revised_interval,
        }

    async def unsubscribe_signal(self, signal_id: str) -> bool:
        """Cancel subscription for a single signal."""
        sub = self._subscriptions.pop(signal_id, None)
        self._monitored_handles.pop(signal_id, None)
        self._handlers.pop(signal_id, None)

        if sub:
            try:
                await sub.delete()
                logger.info(f"[OPCUASubscription] Unsubscribed signal {signal_id}")
                return True
            except Exception as e:
                logger.warning(f"[OPCUASubscription] Error deleting subscription for {signal_id}: {e}")
        return False

    async def unsubscribe_all(self) -> None:
        """Cancel all active subscriptions cleanly."""
        for sig_id in list(self._subscriptions.keys()):
            await self.unsubscribe_signal(sig_id)

    def get_handler(self, signal_id: str) -> Optional[SubscriptionNotificationHandler]:
        return self._handlers.get(signal_id)

    def get_active_count(self) -> int:
        return len(self._subscriptions)

