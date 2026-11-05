import hashlib
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import Optional, Any, Dict


def compute_event_id(
    machine_id: str,
    signal_id: str,
    source_timestamp_iso: str,
    source_value: Any,
    sequence_id: Optional[str] = None,
) -> str:
    """Generate a stable deduplication identifier for an ingestion event."""
    raw = f"{machine_id}:{signal_id}:{source_timestamp_iso}:{source_value}:{sequence_id or ''}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass
class NormalizedReadingMessage:
    """Versioned internal data contract for sensor telemetry readings.
    Adheres strictly to Phase 4, Step 7 contract requirements.
    """
    organization_id: str
    machine_id: str
    signal_id: str
    source_node_id: str
    mapping_version: int
    source_timestamp: str  # ISO 8601 string
    source_value: Any
    normalized_value: Optional[float] = None
    raw_value_numeric: Optional[float] = None
    raw_value_boolean: Optional[bool] = None
    raw_value_string: Optional[str] = None
    source_unit: Optional[str] = None
    normalized_unit: Optional[str] = None
    opcua_quality_code: str = "Good"
    normalization_status: str = "NORMALIZED"  # NORMALIZED, RAW, FAILED
    sampling_interval_ms: int = 1000
    connector_id: Optional[str] = None
    gateway_id: str = "gw-default"
    server_timestamp: Optional[str] = None
    gateway_received_at: Optional[str] = None
    ingestion_timestamp: Optional[str] = None
    source_sequence_id: Optional[str] = None
    simulator_flag: bool = True
    event_id: Optional[str] = None

    def __post_init__(self):
        if not self.gateway_received_at:
            self.gateway_received_at = datetime.now(timezone.utc).isoformat()
        if not self.event_id:
            self.event_id = compute_event_id(
                machine_id=self.machine_id,
                signal_id=self.signal_id,
                source_timestamp_iso=self.source_timestamp,
                source_value=self.source_value,
                sequence_id=self.source_sequence_id,
            )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

