import logging
from typing import Any, Optional, Tuple
from datetime import datetime, timezone
from app.modules.signal_mapping.unit_converter import (
    UnitNormalizer,
    IncompatibleUnitError,
    UnsupportedUnitError,
)
from app.modules.monitoring.data_contract import NormalizedReadingMessage

logger = logging.getLogger(__name__)


class ReadingNormalizer:
    """Telemetry normalization pipeline adhering to Step 6 approved mappings:
    - Preserves raw values, timestamps, and OPC UA quality codes
    - Applies approved linear scaling multiplier and offset
    - Applies physical dimension preserving unit normalization
    - Correctly handles Boolean alarms, cycle counters, and discrete states
    """

    @classmethod
    def normalize(
        cls,
        organization_id: str,
        machine_id: str,
        signal_id: str,
        source_node_id: str,
        mapping_version: int,
        raw_value: Any,
        source_timestamp: Optional[datetime],
        server_timestamp: Optional[datetime],
        scaling_factor: float = 1.0,
        offset: float = 0.0,
        source_unit: Optional[str] = None,
        target_unit: Optional[str] = None,
        sampling_interval_ms: int = 1000,
        connector_id: Optional[str] = None,
        gateway_id: str = "gw-default",
        quality_code: str = "Good",
        simulator_flag: bool = True,
        sequence_id: Optional[str] = None,
    ) -> NormalizedReadingMessage:
        # 1. Format timestamp
        ts_utc = source_timestamp or server_timestamp or datetime.now(timezone.utc)
        if ts_utc.tzinfo is None:
            ts_utc = ts_utc.replace(tzinfo=timezone.utc)
        source_timestamp_iso = ts_utc.isoformat()

        server_ts_iso = None
        if server_timestamp:
            s_utc = server_timestamp if server_timestamp.tzinfo else server_timestamp.replace(tzinfo=timezone.utc)
            server_ts_iso = s_utc.isoformat()

        # 2. Extract raw representations
        raw_numeric: Optional[float] = None
        raw_boolean: Optional[bool] = None
        raw_string = str(raw_value) if raw_value is not None else None

        normalized_numeric: Optional[float] = None
        normalization_status = "NORMALIZED"

        # Check boolean
        if isinstance(raw_value, bool):
            raw_boolean = raw_value
            raw_numeric = 1.0 if raw_value else 0.0
            normalized_numeric = raw_numeric
        elif isinstance(raw_value, (int, float)):
            raw_numeric = float(raw_value)
            raw_boolean = bool(raw_value)
            try:
                # 3. Apply linear scaling
                scaled = (raw_numeric * float(scaling_factor)) + float(offset)

                # 4. Apply unit conversion if source and target units differ
                if source_unit and target_unit and source_unit.strip().lower() != target_unit.strip().lower():
                    try:
                        normalized_numeric = UnitNormalizer.convert(scaled, source_unit, target_unit)
                    except IncompatibleUnitError as e:
                        logger.warning(f"Incompatible unit conversion '{source_unit}' -> '{target_unit}': {e}")
                        normalized_numeric = scaled
                        normalization_status = "FAILED"
                    except UnsupportedUnitError as e:
                        logger.warning(f"Unsupported unit '{source_unit}' or '{target_unit}': {e}")
                        normalized_numeric = scaled
                        normalization_status = "FAILED"
                else:
                    normalized_numeric = scaled
            except Exception as e:
                logger.error(f"Error scaling reading: {e}")
                normalized_numeric = raw_numeric
                normalization_status = "FAILED"
        else:
            # String or discrete value
            normalization_status = "RAW"

        return NormalizedReadingMessage(
            organization_id=organization_id,
            machine_id=machine_id,
            signal_id=signal_id,
            source_node_id=source_node_id,
            mapping_version=mapping_version,
            source_timestamp=source_timestamp_iso,
            server_timestamp=server_ts_iso,
            source_value=raw_value,
            normalized_value=normalized_numeric,
            raw_value_numeric=raw_numeric,
            raw_value_boolean=raw_boolean,
            raw_value_string=raw_string,
            source_unit=source_unit,
            normalized_unit=target_unit,
            opcua_quality_code=quality_code,
            normalization_status=normalization_status,
            sampling_interval_ms=sampling_interval_ms,
            connector_id=connector_id,
            gateway_id=gateway_id,
            simulator_flag=simulator_flag,
            source_sequence_id=sequence_id,
        )

