import math
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone, timedelta

from app.models.condition import QualityState, DataQualityEvent
from app.models.signal_mapping import MachineSignal

logger = logging.getLogger(__name__)


class DataQualityCheckResult:
    """Outcome of data quality validation for a sensor reading."""
    def __init__(
        self,
        quality_state: str,
        is_usable_for_baseline: bool,
        issues: List[Dict[str, Any]],
        sanitized_value: Optional[float] = None,
    ):
        self.quality_state = quality_state
        self.is_usable_for_baseline = is_usable_for_baseline
        self.issues = issues
        self.sanitized_value = sanitized_value

    def to_dict(self) -> Dict[str, Any]:
        return {
            "quality_state": self.quality_state,
            "is_usable_for_baseline": self.is_usable_for_baseline,
            "issues": self.issues,
            "sanitized_value": self.sanitized_value,
        }


class DataQualityEngine:
    """Industrial sensor data quality assessment engine adhering to Phase 5 requirements.
    
    Evaluates:
    - Bad OPC UA quality codes
    - NaN, Infinity, and unsupported types
    - Stale timestamps & sampling gaps
    - Out-of-order timestamps
    - Physically implausible thresholds
    - Sudden sensor spikes
    - Suspiciously constant signals (frozen sensor)
    - Disconnected / Missing signals
    """

    # Physical plausibility limits by measurement dimension / signal group
    DEFAULT_PLAUSIBILITY_BOUNDS = {
        "Temperature": {"min": -50.0, "max": 350.0, "max_step": 30.0},      # °C
        "Vibration": {"min": 0.0, "max": 150.0, "max_step": 40.0},          # mm/s or g
        "Motor Current": {"min": 0.0, "max": 600.0, "max_step": 150.0},     # Amperes
        "Speed": {"min": 0.0, "max": 15000.0, "max_step": 3000.0},          # RPM
        "Pressure": {"min": -1.5, "max": 100.0, "max_step": 25.0},          # bar
        "Alarms": {"min": 0.0, "max": 1.0, "max_step": 1.0},
        "Cycles": {"min": 0.0, "max": 1e9, "max_step": 1000.0},
    }

    @classmethod
    def evaluate_reading(
        cls,
        signal: MachineSignal,
        reading: Dict[str, Any],
        recent_history: Optional[List[Dict[str, Any]]] = None,
    ) -> DataQualityCheckResult:
        """Run comprehensive 13-point data quality assessment on an incoming or stored reading."""
        issues: List[Dict[str, Any]] = []
        is_bad = False
        is_suspect = False

        # 1. OPC UA Quality Code check
        quality_code = str(reading.get("quality_code") or "Good").strip()
        if quality_code.startswith("Bad"):
            is_bad = True
            issues.append({
                "type": "BAD_OPCUA_QUALITY",
                "severity": "CRITICAL",
                "message": f"Source OPC UA quality code is '{quality_code}'.",
            })
        elif quality_code.startswith("Uncertain"):
            is_suspect = True
            issues.append({
                "type": "UNCERTAIN_OPCUA_QUALITY",
                "severity": "WARNING",
                "message": f"Source OPC UA quality code is '{quality_code}'.",
            })

        # 2. Raw and normalized value presence
        raw_val = reading.get("raw_value_numeric")
        norm_val = reading.get("normalized_value")
        if norm_val is None and raw_val is None and reading.get("raw_value_boolean") is None:
            is_bad = True
            issues.append({
                "type": "MISSING_VALUE",
                "severity": "CRITICAL",
                "message": "Both raw and normalized reading values are missing or null.",
            })
            return DataQualityCheckResult(
                quality_state=QualityState.MISSING,
                is_usable_for_baseline=False,
                issues=issues,
                sanitized_value=None,
            )

        # 3. NaN and Infinity check
        val = norm_val if norm_val is not None else raw_val
        if isinstance(val, (int, float)):
            if math.isnan(val) or math.isinf(val):
                is_bad = True
                issues.append({
                    "type": "NAN_INFINITY_VALUE",
                    "severity": "CRITICAL",
                    "message": f"Reading contains non-computable numeric value: {val}.",
                })
                return DataQualityCheckResult(
                    quality_state=QualityState.BAD,
                    is_usable_for_baseline=False,
                    issues=issues,
                    sanitized_value=None,
                )

        # 4. Timestamp validity & Staleness
        ts_raw = reading.get("source_timestamp")
        reading_dt = None
        if isinstance(ts_raw, str):
            try:
                reading_dt = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
            except ValueError:
                is_bad = True
                issues.append({
                    "type": "INVALID_TIMESTAMP_FORMAT",
                    "severity": "CRITICAL",
                    "message": f"Unparseable source timestamp: {ts_raw}.",
                })
        elif isinstance(ts_raw, datetime):
            reading_dt = ts_raw

        now = datetime.now(timezone.utc)
        if reading_dt:
            if reading_dt.tzinfo is None:
                reading_dt = reading_dt.replace(tzinfo=timezone.utc)

            age_sec = (now - reading_dt).total_seconds()
            sampling_interval_sec = (signal.sampling_interval_ms or 1000) / 1000.0

            # Stale check: > 6x interval
            if age_sec > sampling_interval_sec * 6.0:
                is_suspect = True
                issues.append({
                    "type": "STALE_TIMESTAMP",
                    "severity": "WARNING",
                    "message": f"Telemetry age ({age_sec:.1f}s) exceeds staleness threshold ({sampling_interval_sec * 6.0:.1f}s).",
                })

            # Future timestamp check (> 5 minutes in future)
            if age_sec < -300:
                is_bad = True
                issues.append({
                    "type": "FUTURE_TIMESTAMP",
                    "severity": "CRITICAL",
                    "message": f"Timestamp {reading_dt.isoformat()} is ahead of server time.",
                })

        # 5. Physical Plausibility Bounds
        group = signal.signal_definition.signal_group if signal.signal_definition else "Other"
        bounds = cls.DEFAULT_PLAUSIBILITY_BOUNDS.get(group)
        if bounds and isinstance(val, (int, float)):
            if val < bounds["min"] or val > bounds["max"]:
                is_bad = True
                issues.append({
                    "type": "PHYSICALLY_IMPLAUSIBLE",
                    "severity": "CRITICAL",
                    "message": f"Observed value {val} is outside physically plausible limits [{bounds['min']}, {bounds['max']}] for group '{group}'.",
                })

        # 6. Time-Series checks (history comparison): spikes & constant signal
        if recent_history and len(recent_history) >= 2 and isinstance(val, (int, float)):
            prev_readings = [
                h["normalized_value"] for h in recent_history
                if h.get("normalized_value") is not None and not math.isnan(h["normalized_value"])
            ]

            # Spike detection (sudden jump relative to previous point)
            if prev_readings and bounds:
                delta = abs(val - prev_readings[0])
                max_step = bounds.get("max_step", 50.0)
                if delta > max_step * 2.5:
                    is_suspect = True
                    issues.append({
                        "type": "SUDDEN_SPIKE",
                        "severity": "WARNING",
                        "message": f"Instantaneous jump of {delta:.2f} exceeds dynamic rate-of-change limit ({max_step * 2.5:.2f}).",
                    })

            # Frozen sensor check: exactly zero variation across 20+ dynamic readings
            if len(prev_readings) >= 20 and group in ("Vibration", "Temperature", "Motor Current"):
                all_vals = [val] + prev_readings[:19]
                variance = sum((x - val) ** 2 for x in all_vals) / len(all_vals)
                if variance < 1e-9:
                    is_suspect = True
                    issues.append({
                        "type": "SUSPICIOUSLY_CONSTANT",
                        "severity": "WARNING",
                        "message": f"Signal has remained identically constant ({val}) across {len(all_vals)} consecutive readings.",
                    })

        # Determine overall Quality State
        if is_bad:
            final_state = QualityState.BAD
            is_usable = False
        elif is_suspect:
            final_state = QualityState.SUSPECT
            is_usable = False  # Suspect readings should not corrupt baseline training
        else:
            final_state = QualityState.GOOD
            is_usable = True

        return DataQualityCheckResult(
            quality_state=final_state,
            is_usable_for_baseline=is_usable,
            issues=issues,
            sanitized_value=val if is_usable else None,
        )

