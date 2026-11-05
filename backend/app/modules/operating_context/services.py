import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from app.extensions import db
from app.models.equipment import Machine
from app.models.monitoring import SignalReading
from app.models.signal_mapping import MachineSignal
from app.models.condition import MachineOperatingStateRecord, OperatingState
from app.modules.operating_context.classifier import OperatingStateClassifier

logger = logging.getLogger(__name__)


class OperatingContextService:
    """Manages operating state detection, persistence, and querying."""

    @classmethod
    def get_current_operating_context(
        cls, machine_id: str, organization_id: str, recent_minutes: int = 15
    ) -> Dict[str, Any]:
        """Classify and return current machine operating regime from latest readings."""
        machine = db.session.get(Machine, machine_id)
        if not machine or machine.organization_id != organization_id:
            raise ValueError("Equipment not found or access denied.")

        signals = MachineSignal.query.filter_by(
            machine_id=machine_id, organization_id=organization_id, enabled=True
        ).all()

        signals_map: Dict[str, Any] = {}
        for sig in signals:
            latest = (
                SignalReading.query.filter_by(signal_id=sig.id, machine_id=machine_id)
                .order_by(SignalReading.source_timestamp.desc())
                .first()
            )
            if latest:
                code = sig.signal_definition.signal_code if sig.signal_definition else (sig.custom_name or "")
                signals_map[code] = latest.to_dict()

        state, conf, method, supporting = OperatingStateClassifier.classify_state(signals_map)

        # Check existing current state record
        current_rec = (
            MachineOperatingStateRecord.query.filter_by(
                machine_id=machine_id, organization_id=organization_id, is_current=True
            ).first()
        )

        now = datetime.now(timezone.utc)
        if not current_rec or current_rec.operating_state != state:
            if current_rec:
                current_rec.is_current = False
                current_rec.ended_at = now

            new_rec = MachineOperatingStateRecord(
                organization_id=organization_id,
                machine_id=machine_id,
                operating_state=state,
                confidence=conf,
                determination_method=method,
                supporting_signals=supporting,
                started_at=now,
                is_current=True,
            )
            db.session.add(new_rec)
            db.session.commit()
            record_dict = new_rec.to_dict()
        else:
            record_dict = current_rec.to_dict()

        return {
            "machine_id": machine_id,
            "machine_name": machine.equipment_name,
            "current_state": state,
            "confidence": conf,
            "determination_method": method,
            "supporting_signals": supporting,
            "record": record_dict,
            "evaluated_at": now.isoformat(),
        }

    evaluate_current_state = get_current_operating_context

