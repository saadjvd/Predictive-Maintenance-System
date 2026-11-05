import logging
import math
from typing import Dict, Any, List, Optional, Tuple
from app.models.signal_mapping import (
    MachineSignal,
    SignalDefinition,
    ValidationStatus,
)
from app.modules.signal_mapping.unit_converter import (
    UnitNormalizer,
    IncompatibleUnitError,
    UnsupportedUnitError,
)
from app.modules.connectivity.opcua_client import SecureOPCUAClient

logger = logging.getLogger(__name__)

NUMERIC_OPCUA_TYPES = {
    "Double", "Float", "Int16", "Int32", "Int64",
    "UInt16", "UInt32", "UInt64", "Byte", "SByte",
    "Number", "Integer",
}

BOOLEAN_OPCUA_TYPES = {"Boolean", "Bool"}

STRING_OPCUA_TYPES = {"String", "LocalizedText", "ByteString", "Guid"}


class ValidationCheckResult:
    def __init__(self, check_name: str):
        self.check_name = check_name
        self.passed = True
        self.severity = "INFO"  # INFO, WARNING, ERROR
        self.message = "Check passed"
        self.details: Dict[str, Any] = {}

    def fail(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.passed = False
        self.severity = "ERROR"
        self.message = message
        if details:
            self.details = details

    def warn(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.passed = True
        self.severity = "WARNING"
        self.message = message
        if details:
            self.details = details

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "severity": self.severity,
            "message": self.message,
            "details": self.details,
        }


class SignalValidator:
    """Universal industrial signal validation engine implementing 7 mandatory checks:
    1. Node existence & readability (Variable NodeClass, readable, non-cyclic)
    2. Data type compatibility
    3. Engineering unit validation & physical dimension preservation
    4. Scaling factor & offset sanity
    5. Sampling interval bounds
    6. Duplicate node assignment detection
    7. Strictly read-only live sample acquisition & conversion
    """

    @classmethod
    def check_data_type_compatibility(
        cls, expected_type: str, source_type: Optional[str]
    ) -> ValidationCheckResult:
        res = ValidationCheckResult("data_type_compatibility")
        if not source_type:
            res.warn("Source data type not provided by tag metadata; runtime type mismatch may occur.")
            return res

        exp = (expected_type or "").strip()
        src = (source_type or "").strip()

        # Numeric mapping
        if exp in ("Double", "Float", "Int16", "Int32", "Int64"):
            if src not in NUMERIC_OPCUA_TYPES:
                res.fail(
                    f"Incompatible data type: expected numeric '{exp}', but source node provides '{src}'."
                )
                return res

        # Boolean mapping
        elif exp in ("Boolean", "Bool"):
            if src not in BOOLEAN_OPCUA_TYPES:
                res.fail(
                    f"Incompatible data type: expected boolean '{exp}', but source node provides '{src}'."
                )
                return res

        # String / Text mapping
        elif exp in ("String", "Text"):
            if src not in STRING_OPCUA_TYPES:
                res.warn(
                    f"Source node data type '{src}' will be stringified for expected type '{exp}'."
                )

        res.message = f"Data type '{src}' is compatible with target '{exp}'."
        return res

    @classmethod
    def check_unit_compatibility(
        cls,
        expected_unit: Optional[str],
        source_unit: Optional[str],
        normalized_unit: Optional[str],
        dimension: Optional[str],
    ) -> ValidationCheckResult:
        res = ValidationCheckResult("unit_compatibility")

        target_unit = normalized_unit or expected_unit

        # If no units specified, flag warning
        if not source_unit and not target_unit:
            res.warn("No engineering units specified for source or target signal.")
            return res

        if not source_unit and target_unit:
            res.warn(
                f"Source node has no engineering unit. Values will be treated as '{target_unit}' directly."
            )
            return res

        if source_unit and not target_unit:
            res.message = f"Raw unit '{source_unit}' accepted without normalization."
            return res

        # Both units present: verify dimension compatibility
        try:
            dim_src = UnitNormalizer.get_dimension(source_unit)
            dim_tgt = UnitNormalizer.get_dimension(target_unit)

            if dim_src and dim_tgt and dim_src != dim_tgt:
                res.fail(
                    f"Incompatible physical dimensions: cannot convert '{source_unit}' ({dim_src}) to '{target_unit}' ({dim_tgt}). "
                    f"Acceleration (g) and velocity (mm/s) must not be cross-converted."
                )
                return res

            if not UnitNormalizer.are_compatible(source_unit, target_unit):
                # If neither is in known table but strings differ
                if source_unit.strip().lower() != target_unit.strip().lower():
                    res.warn(
                        f"Custom or uncalibrated unit pair ('{source_unit}' -> '{target_unit}'). Ensure scaling factor accounts for conversion."
                    )
                    return res

            res.message = f"Unit conversion from '{source_unit}' to '{target_unit}' is physically valid."
        except IncompatibleUnitError as e:
            res.fail(str(e))
        except Exception as e:
            res.warn(f"Unit verification warning: {e}")

        return res

    @classmethod
    def check_scaling(cls, scaling_factor: float, offset: float) -> ValidationCheckResult:
        res = ValidationCheckResult("scaling_validation")
        try:
            factor = float(scaling_factor)
            offs = float(offset)
        except (ValueError, TypeError):
            res.fail("Scaling factor and offset must be valid numeric values.")
            return res

        if math.isclose(factor, 0.0, abs_tol=1e-9):
            res.fail("Scaling factor cannot be zero (would cause signal extinction).")
            return res

        if not math.isfinite(factor) or not math.isfinite(offs):
            res.fail("Scaling factor and offset must be finite numbers.")
            return res

        res.message = f"Scaling factor {factor} and offset {offs} are valid."
        return res

    @classmethod
    def check_sampling_interval(cls, interval_ms: int) -> ValidationCheckResult:
        res = ValidationCheckResult("sampling_interval")
        if interval_ms is None or interval_ms <= 0:
            res.fail("Sampling interval must be a positive integer in milliseconds.")
            return res

        if interval_ms < 50:
            res.fail(f"Sampling interval {interval_ms}ms is below the minimum allowed limit (50ms).")
            return res

        if interval_ms > 3600000:  # 1 hour
            res.fail(f"Sampling interval {interval_ms}ms exceeds maximum allowed limit (3600000ms).")
            return res

        if interval_ms < 100:
            res.warn(
                f"Sampling interval {interval_ms}ms is very fast and may place high load on PLC and network."
            )
            return res

        res.message = f"Sampling interval {interval_ms}ms is within valid bounds."
        return res

    @classmethod
    def check_duplicate_mapping(
        cls,
        machine_signals: List[MachineSignal],
        current_signal_id: Optional[str],
        source_node_id: str,
    ) -> ValidationCheckResult:
        res = ValidationCheckResult("duplicate_mapping")
        duplicates = [
            s for s in machine_signals
            if s.source_node_id.strip() == source_node_id.strip()
            and s.id != current_signal_id
            and s.enabled
        ]
        if duplicates:
            other_names = [s.custom_name or s.source_browse_name or s.id for s in duplicates]
            res.fail(
                f"Duplicate mapping conflict: NodeId '{source_node_id}' is already mapped to {len(duplicates)} other active signal(s): {', '.join(other_names)}."
            )
            return res

        res.message = "NodeId is uniquely assigned on this equipment."
        return res

    @classmethod
    async def validate_node_and_read_sample(
        cls,
        client: Optional[SecureOPCUAClient],
        source_node_id: str,
        expected_type: str,
        scaling_factor: float,
        offset: float,
        source_unit: Optional[str],
        target_unit: Optional[str],
    ) -> Tuple[ValidationCheckResult, ValidationCheckResult, Optional[Dict[str, Any]]]:
        """Perform Node inspection (check 1) and Live Sample acquisition (check 7).
        STRICT READ-ONLY: Never invokes write_value or call_method.
        """
        node_res = ValidationCheckResult("node_validation")
        sample_res = ValidationCheckResult("live_sample_reading")

        if not client or not client.is_connected():
            node_res.warn("OPC UA client is offline. Static node checks passed; live verification skipped.")
            sample_res.warn("Live sample verification skipped because OPC UA client is not connected.")
            return node_res, sample_res, None

        try:
            from asyncua import ua
            opc_node = client.client.get_node(source_node_id)

            # Check node class
            node_class = await opc_node.read_node_class()
            if node_class != ua.NodeClass.Variable:
                node_res.fail(
                    f"Node class is '{node_class.name}'. Only Variable nodes can be mapped as signals (Methods, Objects, and Views cannot)."
                )
                sample_res.fail("Cannot sample value from non-variable node.")
                return node_res, sample_res, None

            # Check access level (read permission)
            try:
                access_level = await opc_node.read_attribute(ua.AttributeIds.AccessLevel)
                val_access = access_level.Value.Value if access_level and access_level.Value else 0
                # Bit 0 of AccessLevel is CurrentRead
                if not (val_access & 0x01):
                    node_res.fail(f"NodeId '{source_node_id}' does not have read access permissions (AccessLevel={val_access}).")
                    sample_res.fail("Read permission denied on OPC UA node.")
                    return node_res, sample_res, None
            except Exception:
                # Some servers might not expose AccessLevel attribute directly
                pass

            node_res.message = f"NodeId '{source_node_id}' exists, is a Variable, and is readable."

            # Check 7: Read live data value (STRICTLY READ-ONLY)
            data_value = await opc_node.read_data_value()
            if not data_value:
                sample_res.fail(f"Failed to read DataValue from node '{source_node_id}'.")
                return node_res, sample_res, None

            raw_val = data_value.Value.Value if data_value.Value else None
            status_code = data_value.StatusCode
            ts = data_value.SourceTimestamp or data_value.ServerTimestamp

            # Check quality
            is_good = status_code.is_good() if hasattr(status_code, "is_good") else True
            quality_str = "Good" if is_good else f"Bad ({status_code.name if hasattr(status_code, 'name') else status_code})"

            if not is_good:
                sample_res.fail(f"OPC UA returned bad status code: {quality_str}")
                return node_res, sample_res, {
                    "raw_value": str(raw_val),
                    "quality": quality_str,
                    "status_code": str(status_code),
                }

            # Apply scaling
            normalized_val = raw_val
            if isinstance(raw_val, (int, float)):
                scaled = (float(raw_val) * float(scaling_factor)) + float(offset)
                # Apply unit conversion if needed
                if source_unit and target_unit and source_unit.strip().lower() != target_unit.strip().lower():
                    try:
                        normalized_val = UnitNormalizer.convert(scaled, source_unit, target_unit)
                    except Exception as e:
                        sample_res.warn(f"Scaled value calculated ({scaled}), but unit conversion failed: {e}")
                        normalized_val = scaled
                else:
                    normalized_val = scaled

            sample_reading = {
                "raw_value": raw_val,
                "normalized_value": normalized_val,
                "scaling_applied": {
                    "factor": scaling_factor,
                    "offset": offset,
                },
                "source_unit": source_unit,
                "normalized_unit": target_unit,
                "quality": quality_str,
                "timestamp": ts.isoformat() if ts else None,
            }

            sample_res.message = f"Live sample read successfully: raw={raw_val}, normalized={normalized_val} ({target_unit or ''}). Quality: {quality_str}."
            sample_res.details = sample_reading
            return node_res, sample_res, sample_reading

        except Exception as e:
            logger.warning(f"Error reading OPC UA node '{source_node_id}': {e}")
            node_res.fail(f"Error accessing NodeId '{source_node_id}': {str(e)}")
            sample_res.fail(f"Failed to sample live value: {str(e)}")
            return node_res, sample_res, None

    @classmethod
    async def validate_signal(
        cls,
        signal: MachineSignal,
        client: Optional[SecureOPCUAClient] = None,
        existing_signals: Optional[List[MachineSignal]] = None,
    ) -> Tuple[str, Dict[str, Any], List[str], List[str], Optional[Dict[str, Any]]]:
        """Execute all 7 validation checks on a machine signal.
        Returns:
            (status, checks_dict, error_messages, warning_messages, sample_reading)
        """
        definition: SignalDefinition = signal.signal_definition
        expected_type = definition.expected_data_type if definition else "Double"
        standard_unit = definition.standard_unit if definition else None
        dimension = definition.measurement_dimension if definition else None

        checks: Dict[str, Any] = {}
        errors: List[str] = []
        warnings: List[str] = []

        # Check 2: Data type compatibility
        chk2 = cls.check_data_type_compatibility(expected_type, signal.source_data_type)
        checks[chk2.check_name] = chk2.to_dict()
        if not chk2.passed:
            errors.append(chk2.message)
        elif chk2.severity == "WARNING":
            warnings.append(chk2.message)

        # Check 3: Unit compatibility
        target_unit = signal.normalized_unit or standard_unit
        chk3 = cls.check_unit_compatibility(target_unit, signal.source_unit, signal.normalized_unit, dimension)
        checks[chk3.check_name] = chk3.to_dict()
        if not chk3.passed:
            errors.append(chk3.message)
        elif chk3.severity == "WARNING":
            warnings.append(chk3.message)

        # Check 4: Scaling validation
        chk4 = cls.check_scaling(signal.scaling_factor, signal.offset)
        checks[chk4.check_name] = chk4.to_dict()
        if not chk4.passed:
            errors.append(chk4.message)
        elif chk4.severity == "WARNING":
            warnings.append(chk4.message)

        # Check 5: Sampling interval validation
        chk5 = cls.check_sampling_interval(signal.sampling_interval_ms)
        checks[chk5.check_name] = chk5.to_dict()
        if not chk5.passed:
            errors.append(chk5.message)
        elif chk5.severity == "WARNING":
            warnings.append(chk5.message)

        # Check 6: Duplicate mapping validation
        if existing_signals is not None:
            chk6 = cls.check_duplicate_mapping(existing_signals, signal.id, signal.source_node_id)
            checks[chk6.check_name] = chk6.to_dict()
            if not chk6.passed:
                errors.append(chk6.message)
            elif chk6.severity == "WARNING":
                warnings.append(chk6.message)

        # Checks 1 & 7: Node validation & live sample reading
        chk1, chk7, sample_reading = await cls.validate_node_and_read_sample(
            client=client,
            source_node_id=signal.source_node_id,
            expected_type=expected_type,
            scaling_factor=signal.scaling_factor,
            offset=signal.offset,
            source_unit=signal.source_unit,
            target_unit=target_unit,
        )
        checks[chk1.check_name] = chk1.to_dict()
        if not chk1.passed:
            errors.append(chk1.message)
        elif chk1.severity == "WARNING":
            warnings.append(chk1.message)

        checks[chk7.check_name] = chk7.to_dict()
        if not chk7.passed:
            errors.append(chk7.message)
        elif chk7.severity == "WARNING":
            warnings.append(chk7.message)

        # Determine overall status
        if errors:
            status = ValidationStatus.INVALID
        elif warnings:
            status = ValidationStatus.WARNING
        else:
            status = ValidationStatus.VALID

        return status, checks, errors, warnings, sample_reading

