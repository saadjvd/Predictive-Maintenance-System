import logging
from typing import List, Dict, Any, Optional, Tuple
from app.extensions import db
from app.models.equipment import Machine
from app.models.signal_mapping import (
    SignalDefinition,
    MachineSignal,
    SignalValidationResult,
    ValidationStatus,
    SignalGroup,
)
from app.modules.signal_mapping.repositories import (
    SignalDefinitionRepository,
    MachineSignalRepository,
    ValidationResultRepository,
)
from app.modules.signal_mapping.validators import SignalValidator
from app.modules.connectivity.opcua_client import SecureOPCUAClient

logger = logging.getLogger(__name__)


class SignalMappingService:
    """Core domain service orchestrating signal mapping, versioning, and validation."""

    @classmethod
    def list_definitions(cls, organization_id: str, group: Optional[str] = None) -> List[Dict[str, Any]]:
        defs = SignalDefinitionRepository.get_definitions(organization_id, group)
        return [d.to_dict() for d in defs]

    @classmethod
    def create_custom_definition(cls, organization_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        defn = SignalDefinitionRepository.create_custom(organization_id, data)
        return defn.to_dict()

    @classmethod
    def list_signals(cls, machine_id: str, organization_id: str) -> List[Dict[str, Any]]:
        signals = MachineSignalRepository.get_signals_for_machine(machine_id, organization_id)
        return [s.to_dict() for s in signals]

    @classmethod
    def get_signal(cls, signal_id: str, organization_id: str) -> Optional[MachineSignal]:
        return MachineSignalRepository.get_by_id(signal_id, organization_id)

    @classmethod
    def create_signal(
        cls, machine_id: str, organization_id: str, data: Dict[str, Any], user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        # Validate target definition exists and is accessible
        definition = SignalDefinitionRepository.get_by_id(data["signal_definition_id"], organization_id)
        if not definition:
            raise ValueError(f"Signal definition '{data.get('signal_definition_id')}' not found or inaccessible.")

        # Check for duplicate node mapping in active version
        existing = MachineSignalRepository.find_duplicate(
            machine_id=machine_id,
            source_node_id=data["source_node_id"].strip(),
            mapping_version=1,
        )
        if existing and existing.enabled:
            raise ValueError(
                f"NodeId '{data['source_node_id']}' is already mapped to signal '{existing.custom_name or existing.id}' on this equipment."
            )

        signal = MachineSignalRepository.create_signal(
            organization_id=organization_id,
            machine_id=machine_id,
            data=data,
            user_id=user_id,
        )
        return signal.to_dict()

    @classmethod
    def bulk_create_signals(
        cls, machine_id: str, organization_id: str, items: List[Dict[str, Any]], user_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        created = []
        for item in items:
            sig = cls.create_signal(machine_id, organization_id, item, user_id=user_id)
            created.append(sig)
        return created

    @classmethod
    def update_signal(
        cls, signal_id: str, organization_id: str, data: Dict[str, Any], user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        signal = MachineSignalRepository.get_by_id(signal_id, organization_id)
        if not signal:
            raise ValueError(f"Machine signal '{signal_id}' not found.")

        # If changing source_node_id, check duplicates
        new_node_id = data.get("source_node_id", signal.source_node_id).strip()
        dup = MachineSignalRepository.find_duplicate(
            machine_id=signal.machine_id,
            source_node_id=new_node_id,
            mapping_version=signal.mapping_version + 1,
            exclude_id=signal.id,
        )
        if dup and dup.enabled:
            raise ValueError(f"NodeId '{new_node_id}' is already mapped on this equipment.")

        updated = MachineSignalRepository.update_signal(signal, data, user_id=user_id)
        return updated.to_dict()

    @classmethod
    def delete_signal(cls, signal_id: str, organization_id: str) -> None:
        signal = MachineSignalRepository.get_by_id(signal_id, organization_id)
        if not signal:
            raise ValueError(f"Machine signal '{signal_id}' not found.")
        MachineSignalRepository.delete_signal(signal)

    @classmethod
    async def validate_machine_signals(
        cls,
        machine_id: str,
        organization_id: str,
        signal_ids: Optional[List[str]] = None,
        client: Optional[SecureOPCUAClient] = None,
        user_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Validate mapped signals for an equipment asset. Strictly read-only."""
        signals = MachineSignalRepository.get_signals_for_machine(machine_id, organization_id)
        if signal_ids:
            signals = [s for s in signals if s.id in signal_ids]

        results = []
        for signal in signals:
            status, checks, errors, warnings, sample = await SignalValidator.validate_signal(
                signal=signal,
                client=client,
                existing_signals=signals,
            )

            # Update signal record status
            signal.validation_status = status
            db.session.commit()

            # Record detailed audit result
            res = ValidationResultRepository.record_result(
                machine_signal_id=signal.id,
                organization_id=organization_id,
                status=status,
                checks=checks,
                errors=errors,
                warnings=warnings,
                sample_reading=sample,
                mapping_version=signal.mapping_version,
                user_id=user_id,
            )
            results.append(res.to_dict())

        return results

    @classmethod
    def get_validation_results(
        cls, machine_id: str, organization_id: str
    ) -> List[Dict[str, Any]]:
        results = ValidationResultRepository.get_results_for_machine(machine_id, organization_id)
        return [r.to_dict() for r in results]

    @classmethod
    def get_summary(cls, machine_id: str, organization_id: str) -> Dict[str, Any]:
        signals = MachineSignalRepository.get_signals_for_machine(machine_id, organization_id)
        total = len(signals)
        valid = sum(1 for s in signals if s.validation_status == ValidationStatus.VALID)
        warning = sum(1 for s in signals if s.validation_status == ValidationStatus.WARNING)
        invalid = sum(1 for s in signals if s.validation_status == ValidationStatus.INVALID)
        pending = sum(1 for s in signals if s.validation_status == ValidationStatus.PENDING)

        group_breakdown: Dict[str, int] = {}
        for s in signals:
            grp = s.signal_definition.signal_group if s.signal_definition else "Other"
            group_breakdown[grp] = group_breakdown.get(grp, 0) + 1

        ready_for_monitoring = total > 0 and invalid == 0 and pending == 0

        return {
            "machine_id": machine_id,
            "total_signals": total,
            "valid_count": valid,
            "warning_count": warning,
            "invalid_count": invalid,
            "pending_count": pending,
            "group_breakdown": group_breakdown,
            "ready_for_monitoring": ready_for_monitoring,
        }

