from typing import Dict, Any, List
from datetime import datetime, timezone, timedelta
from app.models.signal_mapping import MachineSignal
from app.models.monitoring import SignalReading
from app.models.equipment import Machine


class TelemetryTools:
    """Read-only industrial telemetry querying tools for diagnostic agents."""

    @classmethod
    def get_machine_signals(cls, organization_id: str, machine_id: str) -> List[Dict[str, Any]]:
        """Returns active mapped telemetry signals for equipment."""
        signals = MachineSignal.query.filter_by(
            machine_id=machine_id,
            organization_id=organization_id,
            enabled=True,
        ).all()
        return [
            {
                "signal_id": s.id,
                "signal_code": s.signal_definition.signal_code if s.signal_definition else None,
                "name": s.custom_name or (s.signal_definition.name if s.signal_definition else "Unknown"),
                "engineering_unit": s.signal_definition.engineering_unit if s.signal_definition else None,
                "signal_group": s.signal_definition.signal_group if s.signal_definition else None,
            }
            for s in signals
        ]

    @classmethod
    def get_recent_readings_summary(
        cls,
        organization_id: str,
        machine_id: str,
        recent_minutes: int = 60,
    ) -> Dict[str, Any]:
        """Calculates latest values, mean, min, max over recent operating window."""
        machine = Machine.query.filter_by(id=machine_id, organization_id=organization_id).first()
        if not machine:
            return {"error": f"Machine '{machine_id}' not found."}

        cutoff = datetime.now(timezone.utc) - timedelta(minutes=recent_minutes)
        signals = MachineSignal.query.filter_by(machine_id=machine_id, organization_id=organization_id, enabled=True).all()
        sig_ids = [s.id for s in signals]

        readings = (
            SignalReading.query.filter(
                SignalReading.signal_id.in_(sig_ids),
                SignalReading.source_timestamp >= cutoff,
            )
            .order_by(SignalReading.source_timestamp.asc())
            .all()
        )

        signal_stats: Dict[str, Dict[str, Any]] = {}
        for s in signals:
            s_code = s.signal_definition.signal_code if s.signal_definition else s.custom_name
            sig_readings = [r.normalized_value for r in readings if r.signal_id == s.id and r.normalized_value is not None]
            if sig_readings:
                signal_stats[s_code] = {
                    "latest": round(sig_readings[-1], 2),
                    "mean": round(sum(sig_readings) / len(sig_readings), 2),
                    "min": round(min(sig_readings), 2),
                    "max": round(max(sig_readings), 2),
                    "sample_count": len(sig_readings),
                }
            else:
                signal_stats[s_code] = {"status": "NO_RECENT_SAMPLES"}

        return {
            "machine_id": machine_id,
            "equipment_name": machine.equipment_name,
            "window_minutes": recent_minutes,
            "total_readings": len(readings),
            "signal_metrics": signal_stats,
        }

