import logging
from typing import Dict, Any, Optional, Tuple
from app.models.condition import OperatingState

logger = logging.getLogger(__name__)


class OperatingStateClassifier:
    """Classifies machine operating regime based on multi-sensor telemetry rules."""

    @classmethod
    def classify_state(
        cls,
        signals_map: Dict[str, Any],
        plc_state_tag: Optional[str] = None,
    ) -> Tuple[str, float, str, Dict[str, Any]]:
        """Classify machine operational state.
        
        Returns:
            (state, confidence, determination_method, supporting_signals)
        """
        # 1. Direct explicit PLC state tag if available
        if plc_state_tag:
            tag_upper = str(plc_state_tag).strip().upper()
            if tag_upper in OperatingState.ALL_STATES:
                return tag_upper, 1.0, "PLC_EXPLICIT_TAG", {"plc_state": tag_upper}

        # 2. Extract key telemetry variables
        speed = signals_map.get("ROTATIONAL_SPEED") or signals_map.get("LINE_SPEED") or signals_map.get("SPEED")
        current = signals_map.get("MOTOR_CURRENT")
        vibration = signals_map.get("MOTOR_VIBRATION") or signals_map.get("BEARING_VIBRATION")
        temp = signals_map.get("MOTOR_TEMP") or signals_map.get("SEALING_TEMP")

        speed_val = float(speed["normalized_value"]) if speed and speed.get("normalized_value") is not None else None
        current_val = float(current["normalized_value"]) if current and current.get("normalized_value") is not None else None
        vib_val = float(vibration["normalized_value"]) if vibration and vibration.get("normalized_value") is not None else None
        temp_val = float(temp["normalized_value"]) if temp and temp.get("normalized_value") is not None else None

        supporting = {
            "speed": speed_val,
            "current": current_val,
            "vibration": vib_val,
            "temp": temp_val,
        }

        # 3. Rule-based classification
        if speed_val is not None:
            # IDLE: Speed <= 5 RPM or m/min
            if speed_val <= 5.0:
                if current_val is not None and current_val > 5.0 and temp_val is not None and temp_val > 60.0:
                    return OperatingState.CLEANING, 0.85, "RULE_THERMAL_CLEANING", supporting
                return OperatingState.IDLE, 0.95, "RULE_SPEED_ZERO", supporting

            # STARTUP: Speed between 5 and 60% of nominal (e.g. < 120 RPM)
            if speed_val < 120.0:
                return OperatingState.STARTUP, 0.85, "RULE_ACCELERATION_STARTUP", supporting

            # HIGH LOAD: Speed nominal and current > 45A or vibration > 3.5 mm/s
            if (current_val is not None and current_val > 45.0) or (vib_val is not None and vib_val > 3.5):
                return OperatingState.HIGH_LOAD, 0.90, "RULE_HEAVY_LOAD_DRAW", supporting

            # RUNNING: Steady nominal speed
            return OperatingState.RUNNING, 0.95, "RULE_NOMINAL_SPEED_RUNNING", supporting

        # Fallback if no speed sensor, inspect motor current
        if current_val is not None:
            if current_val <= 1.0:
                return OperatingState.IDLE, 0.80, "RULE_CURRENT_ZERO", supporting
            elif current_val > 45.0:
                return OperatingState.HIGH_LOAD, 0.80, "RULE_CURRENT_PEAK", supporting
            else:
                return OperatingState.RUNNING, 0.80, "RULE_CURRENT_ACTIVE", supporting

        return OperatingState.UNKNOWN, 0.30, "INSUFFICIENT_SIGNALS", supporting

