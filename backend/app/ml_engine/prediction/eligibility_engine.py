from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta

from app.models.prediction import (
    PredictionEligibilityState,
    PredictiveModelRegistry,
    PredictiveModelVersion,
    PredictiveModelLifecycle,
    FailureRecord,
    FailureVerificationStatus,
    FailureMode,
)
from app.models.condition import QualityState
from app.models.signal_mapping import MachineSignal
from app.models.monitoring import SignalReading
from app.modules.data_quality.services import DataQualityService


class ModelEligibilityEngine:
    """Evaluates whether equipment qualifies for failure prediction and RUL estimation."""

    MIN_HISTORY_HOURS = 24.0
    MIN_VERIFIED_FAILURES_FOR_SUPERVISED = 3

    @classmethod
    def evaluate_machine_eligibility(
        cls,
        organization_id: str,
        machine_id: str,
    ) -> Dict[str, Any]:
        """
        Runs comprehensive multi-factor eligibility assessment.
        Returns:
            eligibility_state: str
            can_train: bool
            can_predict: bool
            can_estimate_rul: bool
            reasons: List[str]
            details: Dict[str, Any]
        """
        reasons: List[str] = []

        # 1. Check signal configuration
        signals = MachineSignal.query.filter_by(
            machine_id=machine_id,
            organization_id=organization_id,
            enabled=True,
        ).all()

        if not signals:
            return {
                "eligibility_state": PredictionEligibilityState.NOT_CONFIGURED,
                "can_train": False,
                "can_predict": False,
                "can_estimate_rul": False,
                "reasons": ["Equipment has no active mapped telemetry signals."],
                "details": {"signal_count": 0, "failure_record_count": 0},
            }

        # 2. Check live Data Quality gate
        dq_eval = DataQualityService.evaluate_machine_quality(machine_id, organization_id)
        dq_state = dq_eval.get("overall_state", QualityState.GOOD)

        if dq_state in (QualityState.BAD, QualityState.MISSING, QualityState.STALE):
            return {
                "eligibility_state": PredictionEligibilityState.DATA_QUALITY_BLOCKED,
                "can_train": False,
                "can_predict": False,
                "can_estimate_rul": False,
                "reasons": [
                    f"Sensor telemetry quality is degraded ({dq_state}). Predictive inference blocked to prevent false alarms."
                ],
                "details": {
                    "data_quality_state": dq_state,
                    "issues": dq_eval.get("issues", []),
                },
            }

        # 3. Check historical telemetry span
        signal_ids = [s.id for s in signals]
        first_r = (
            SignalReading.query.filter(SignalReading.signal_id.in_(signal_ids))
            .order_by(SignalReading.source_timestamp.asc())
            .first()
        )
        last_r = (
            SignalReading.query.filter(SignalReading.signal_id.in_(signal_ids))
            .order_by(SignalReading.source_timestamp.desc())
            .first()
        )

        history_hours = 0.0
        if first_r and last_r and first_r.source_timestamp and last_r.source_timestamp:
            t0 = first_r.source_timestamp
            t1 = last_r.source_timestamp
            if t0.tzinfo is None:
                t0 = t0.replace(tzinfo=timezone.utc)
            if t1.tzinfo is None:
                t1 = t1.replace(tzinfo=timezone.utc)
            history_hours = max((t1 - t0).total_seconds() / 3600.0, 0.0)

        # 4. Check verified failure records
        failure_records = FailureRecord.query.filter_by(
            machine_id=machine_id,
            organization_id=organization_id,
        ).all()

        verified_failures = [
            f for f in failure_records
            if f.verification_status in (FailureVerificationStatus.CONFIRMED, FailureVerificationStatus.SUSPECTED)
        ]
        unverified_count = len(failure_records) - len(verified_failures)

        # 5. Check active approved predictive models
        active_models = (
            PredictiveModelRegistry.query.filter_by(
                machine_id=machine_id,
                organization_id=organization_id,
                lifecycle_status=PredictiveModelLifecycle.ACTIVE,
            ).all()
        )

        under_val_models = (
            PredictiveModelRegistry.query.filter_by(
                machine_id=machine_id,
                organization_id=organization_id,
                lifecycle_status=PredictiveModelLifecycle.UNDER_VALIDATION,
            ).all()
        )

        # 6. Determine final state
        details = {
            "signal_count": len(signals),
            "history_hours": round(history_hours, 1),
            "verified_failure_count": len(verified_failures),
            "unverified_maintenance_count": unverified_count,
            "active_model_count": len(active_models),
            "under_validation_model_count": len(under_val_models),
            "data_quality_state": dq_state,
        }

        if active_models:
            state = PredictionEligibilityState.PREDICTION_READY
            can_predict = True
            can_train = True
            can_rul = len(verified_failures) >= cls.MIN_VERIFIED_FAILURES_FOR_SUPERVISED
            reasons.append(f"{len(active_models)} validated and approved model(s) active.")
        elif under_val_models:
            state = PredictionEligibilityState.UNDER_VALIDATION
            can_predict = False
            can_train = True
            can_rul = False
            reasons.append("Model has been trained but is currently under validation or awaiting approval.")
        elif len(verified_failures) >= cls.MIN_VERIFIED_FAILURES_FOR_SUPERVISED and history_hours >= cls.MIN_HISTORY_HOURS:
            state = PredictionEligibilityState.TRAINING_ELIGIBLE
            can_predict = False
            can_train = True
            can_rul = True
            reasons.append("Adequate verified failure history and sensor recordings exist. Ready to train predictive model.")
        else:
            state = PredictionEligibilityState.INSUFFICIENT_DATA
            can_predict = False
            can_train = False
            can_rul = False
            if len(verified_failures) < cls.MIN_VERIFIED_FAILURES_FOR_SUPERVISED:
                reasons.append(
                    f"Insufficient failure records ({len(verified_failures)}/{cls.MIN_VERIFIED_FAILURES_FOR_SUPERVISED} required). "
                    "Phase 5 Anomaly Detection remains active."
                )
            if history_hours < cls.MIN_HISTORY_HOURS:
                reasons.append(
                    f"Insufficient telemetry duration ({history_hours:.1f}h/{cls.MIN_HISTORY_HOURS}h required)."
                )

        return {
            "machine_id": machine_id,
            "eligibility_state": state,
            "can_train": can_train,
            "can_predict": can_predict,
            "can_estimate_rul": can_rul,
            "reasons": reasons,
            "details": details,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
        }

