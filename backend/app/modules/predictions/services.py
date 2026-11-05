import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import pandas as pd

from app.extensions import db
from app.models.equipment import Machine, MachineComponent
from app.models.signal_mapping import MachineSignal
from app.models.monitoring import SignalReading
from app.models.condition import BaselineProfile, BaselineVersion, AnomalyEvent
from app.models.prediction import (
    FailureMode,
    FailureRecord,
    FailureVerificationStatus,
    PredictiveDataset,
    PredictiveModelRegistry,
    PredictiveModelVersion,
    PredictiveModelLifecycle,
    PredictionEligibilityState,
    PredictiveRiskCategory,
    EquipmentPrediction,
    PredictionEvidence,
    PredictiveAlert,
    PredictiveAlertStatus,
)
from app.ml_engine.prediction.failure_modes import FailureModeCatalog
from app.ml_engine.prediction.dataset_builder import PredictiveDatasetBuilder
from app.ml_engine.prediction.failure_classifier import FailureClassifierWrapper
from app.ml_engine.prediction.eligibility_engine import ModelEligibilityEngine
from app.ml_engine.prediction.prediction_pipeline import PredictionPipeline


class PredictionService:
    """Business logic for failure prediction, risk estimation, model registry & alerts."""

    # =========================================================================
    # 1. Failure Modes
    # =========================================================================

    @classmethod
    def get_failure_modes(cls, organization_id: str, category_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lists available failure modes for organization, auto-seeding standard modes if needed."""
        FailureModeCatalog.seed_standard_modes()

        query = FailureMode.query.filter(
            (FailureMode.organization_id == organization_id) | (FailureMode.is_standard == True)
        )
        if category_id:
            query = query.filter(
                (FailureMode.category_id == category_id) | (FailureMode.category_id.is_(None))
            )
        modes = query.order_by(FailureMode.is_standard.desc(), FailureMode.name.asc()).all()
        return [m.to_dict() for m in modes]

    @classmethod
    def create_failure_mode(cls, organization_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Creates a custom failure mode for an organization."""
        code = data.get("code")
        name = data.get("name")
        if not code or not name:
            raise ValueError("Failure mode 'code' and 'name' are required.")

        code = code.strip().upper()
        existing = FailureMode.query.filter_by(organization_id=organization_id, code=code).first()
        if existing:
            raise ValueError(f"Failure mode with code '{code}' already exists in your organization.")

        fm = FailureMode(
            organization_id=organization_id,
            category_id=data.get("category_id"),
            code=code,
            name=name.strip(),
            component_type=data.get("component_type"),
            description=data.get("description"),
            severity_impact=data.get("severity_impact", "HIGH"),
            evidence_requirements=data.get("evidence_requirements", {}),
            relevant_signals=data.get("relevant_signals", []),
            applicable_model_families=data.get("applicable_model_families", ["CLASSIFICATION", "SURVIVAL_RUL"]),
            is_standard=False,
        )
        db.session.add(fm)
        db.session.commit()
        return fm.to_dict()

    # =========================================================================
    # 2. Failure & Maintenance Records
    # =========================================================================

    @classmethod
    def get_failure_records(
        cls,
        organization_id: str,
        machine_id: str,
        component_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Retrieves historical failure and maintenance records for machine."""
        machine = Machine.query.filter_by(id=machine_id, organization_id=organization_id).first()
        if not machine:
            raise ValueError(f"Machine '{machine_id}' not found.")

        query = FailureRecord.query.filter_by(organization_id=organization_id, machine_id=machine_id)
        if component_id:
            query = query.filter_by(component_id=component_id)

        records = query.order_by(FailureRecord.failure_started_at.desc()).limit(limit).all()
        return [r.to_dict() for r in records]

    @classmethod
    def create_failure_record(
        cls,
        organization_id: str,
        machine_id: str,
        user_id: Optional[str],
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Logs a failure or maintenance event for machine."""
        machine = Machine.query.filter_by(id=machine_id, organization_id=organization_id).first()
        if not machine:
            raise ValueError(f"Machine '{machine_id}' not found.")

        started_at_str = data.get("failure_started_at")
        description = data.get("failure_description")
        if not started_at_str or not description:
            raise ValueError("'failure_started_at' and 'failure_description' are required.")

        try:
            started_at = datetime.fromisoformat(started_at_str.replace("Z", "+00:00"))
        except Exception as e:
            raise ValueError(f"Invalid timestamp format for failure_started_at: {str(e)}")

        verification_status = data.get("verification_status", FailureVerificationStatus.UNVERIFIED)
        if verification_status not in FailureVerificationStatus.ALL_STATUSES:
            verification_status = FailureVerificationStatus.UNVERIFIED

        rec = FailureRecord(
            organization_id=organization_id,
            machine_id=machine_id,
            component_id=data.get("component_id"),
            failure_mode_id=data.get("failure_mode_id"),
            failure_started_at=started_at,
            failure_description=description.strip(),
            observed_symptoms=data.get("observed_symptoms", []),
            confirmed_root_cause=data.get("confirmed_root_cause"),
            maintenance_action=data.get("maintenance_action"),
            downtime_minutes=float(data.get("downtime_minutes", 0.0)),
            record_source=data.get("record_source", "MANUAL"),
            verification_status=verification_status,
            verified_by=user_id if verification_status in (FailureVerificationStatus.CONFIRMED, FailureVerificationStatus.SUSPECTED) else None,
            failure_confirmed_at=datetime.now(timezone.utc) if verification_status == FailureVerificationStatus.CONFIRMED else None,
        )
        db.session.add(rec)
        db.session.commit()
        return rec.to_dict()

    @classmethod
    def verify_failure_record(
        cls,
        organization_id: str,
        record_id: str,
        user_id: str,
        status: str,
        confirmed_root_cause: Optional[str] = None,
        maintenance_action: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Updates failure record verification status with maintenance engineer verification."""
        rec = FailureRecord.query.filter_by(id=record_id, organization_id=organization_id).first()
        if not rec:
            raise ValueError(f"Failure record '{record_id}' not found.")

        if status not in FailureVerificationStatus.ALL_STATUSES:
            raise ValueError(f"Invalid verification status '{status}'. Must be one of {FailureVerificationStatus.ALL_STATUSES}")

        rec.verification_status = status
        rec.verified_by = user_id
        if confirmed_root_cause:
            rec.confirmed_root_cause = confirmed_root_cause.strip()
        if maintenance_action:
            rec.maintenance_action = maintenance_action.strip()

        if status == FailureVerificationStatus.CONFIRMED:
            rec.failure_confirmed_at = datetime.now(timezone.utc)

        rec.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        return rec.to_dict()

    # =========================================================================
    # 3. Model Eligibility
    # =========================================================================

    @classmethod
    def get_machine_eligibility(cls, organization_id: str, machine_id: str) -> Dict[str, Any]:
        """Assesses machine readiness for predictive modeling and RUL estimation."""
        machine = Machine.query.filter_by(id=machine_id, organization_id=organization_id).first()
        if not machine:
            raise ValueError(f"Machine '{machine_id}' not found.")

        return ModelEligibilityEngine.evaluate_machine_eligibility(
            organization_id=organization_id,
            machine_id=machine_id,
        )

    # =========================================================================
    # 4. Model Training & Registry
    # =========================================================================

    @classmethod
    def train_predictive_model(
        cls,
        organization_id: str,
        machine_id: str,
        user_id: Optional[str],
        failure_mode_id: str,
        algorithm: str = "RANDOM_FOREST",
        prediction_horizon_hours: int = 168,
        hyperparameters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Trains, calibrates, and registers a machine-specific failure prediction model."""
        machine = Machine.query.filter_by(id=machine_id, organization_id=organization_id).first()
        if not machine:
            raise ValueError(f"Machine '{machine_id}' not found.")

        failure_mode = FailureMode.query.filter_by(id=failure_mode_id).first()
        if not failure_mode:
            raise ValueError(f"Failure mode '{failure_mode_id}' not found.")

        # 1. Eligibility Check
        eligibility = ModelEligibilityEngine.evaluate_machine_eligibility(organization_id, machine_id)
        if not eligibility.get("can_train", False):
            reasons = "; ".join(eligibility.get("reasons", []))
            raise ValueError(f"Machine is not currently eligible for model training: {reasons}")

        # 2. Gather historical data
        signals = MachineSignal.query.filter_by(machine_id=machine_id, organization_id=organization_id, enabled=True).all()
        signal_ids = [s.id for s in signals]
        signal_map = {s.id: s for s in signals}

        # Query all historical readings for this machine
        readings = (
            SignalReading.query.filter(SignalReading.signal_id.in_(signal_ids))
            .order_by(SignalReading.source_timestamp.asc())
            .all()
        )
        if not readings:
            raise ValueError("No historical sensor readings found for machine signals.")

        readings_records = []
        for r in readings:
            sig = signal_map.get(r.signal_id)
            sig_name = (
                sig.signal_definition.signal_code
                if sig and sig.signal_definition
                else (sig.custom_name if sig else "UNKNOWN")
            )
            readings_records.append({
                "signal_name": sig_name,
                "normalized_value": r.normalized_value,
                "source_timestamp": r.source_timestamp.isoformat() if r.source_timestamp else None,
            })

        # Failure records
        failure_records = FailureRecord.query.filter_by(
            machine_id=machine_id,
            organization_id=organization_id,
        ).all()
        failure_dicts = [f.to_dict() for f in failure_records]

        # Anomaly records
        anomalies = AnomalyEvent.query.filter_by(machine_id=machine_id).all()
        anomaly_dicts = [a.to_dict() for a in anomalies]

        # Baseline envelopes
        profiles = BaselineProfile.query.filter(
            BaselineProfile.machine_id == machine_id,
            BaselineProfile.lifecycle_status.in_(["APPROVED", "ACTIVE"])
        ).all()
        baseline_map = {}
        for prof in profiles:
            sig = signal_map.get(prof.signal_id)
            sig_name = (
                sig.signal_definition.signal_code
                if sig and sig.signal_definition
                else (sig.custom_name if sig else None)
            )
            if sig_name and prof.active_version_number:
                bv = BaselineVersion.query.filter_by(
                    profile_id=prof.id,
                    version_number=prof.active_version_number,
                ).first()
                if bv and bv.mean is not None:
                    baseline_map[sig_name] = {"mean": bv.mean, "std": bv.std or 1.0}

        # 3. Build supervised dataset using sliding window (no leakage)
        X, y, feature_names, meta = PredictiveDatasetBuilder.build_supervised_dataset(
            readings_records=readings_records,
            failure_records=failure_dicts,
            prediction_horizon_hours=prediction_horizon_hours,
            observation_step_hours=6,
            feature_window_hours=24,
            baseline_envelopes=baseline_map,
            anomaly_records=anomaly_dicts,
        )

        if "error" in meta or len(X) == 0:
            raise ValueError(f"Dataset build failed: {meta.get('error', 'Unknown error')}")

        pos_count = int(np.sum(y == 1))
        if pos_count < FailureClassifierWrapper.MIN_POSITIVE_SAMPLES:
            raise ValueError(
                f"Supervised model training requires at least {FailureClassifierWrapper.MIN_POSITIVE_SAMPLES} "
                f"confirmed positive failure events within the lookback window. Found {pos_count}."
            )

        # 4. Temporal train / validation split
        X_train, y_train, X_val, y_val = PredictiveDatasetBuilder.split_temporal(X, y, train_ratio=0.75)

        # 5. Train & Calibrate Classifier
        classifier = FailureClassifierWrapper(
            algorithm=algorithm,
            prediction_horizon_hours=prediction_horizon_hours,
            hyperparameters=hyperparameters or {},
        )
        training_summary = classifier.fit_and_validate(
            X_train=X_train,
            y_train=y_train,
            X_val=X_val,
            y_val=y_val,
            feature_names=feature_names,
            calibrate=True,
        )

        # 6. Save Artifacts
        base_dir = os.path.join(os.getcwd(), "instance", "models", "predictive", machine_id)
        os.makedirs(base_dir, exist_ok=True)
        version_uuid = str(uuid.uuid4())[:8]
        model_filename = f"{failure_mode.code}_{algorithm}_{prediction_horizon_hours}h_{version_uuid}.joblib"
        calibrator_filename = f"{failure_mode.code}_{algorithm}_{prediction_horizon_hours}h_{version_uuid}_calibrator.joblib"
        model_path = os.path.join(base_dir, model_filename)
        calibrator_path = os.path.join(base_dir, calibrator_filename)

        saved_model_path, saved_cal_path = classifier.save(model_path, calibrator_path)

        # 7. Register in PredictiveModelRegistry
        registry = PredictiveModelRegistry.query.filter_by(
            organization_id=organization_id,
            machine_id=machine_id,
            failure_mode_id=failure_mode_id,
            prediction_horizon_hours=prediction_horizon_hours,
        ).first()

        if not registry:
            registry = PredictiveModelRegistry(
                organization_id=organization_id,
                machine_id=machine_id,
                failure_mode_id=failure_mode_id,
                name=f"{machine.equipment_name} - {failure_mode.name} ({prediction_horizon_hours}h)",
                model_type="FAILURE_CLASSIFICATION",
                prediction_horizon_hours=prediction_horizon_hours,
                lifecycle_status=PredictiveModelLifecycle.UNDER_VALIDATION,
            )
            db.session.add(registry)
            db.session.flush()
        else:
            registry.lifecycle_status = PredictiveModelLifecycle.UNDER_VALIDATION

        # Compute next version number
        latest_version = (
            PredictiveModelVersion.query.filter_by(registry_id=registry.id)
            .order_by(PredictiveModelVersion.version_number.desc())
            .first()
        )
        next_version = (latest_version.version_number + 1) if latest_version else 1

        version_obj = PredictiveModelVersion(
            registry_id=registry.id,
            version_number=next_version,
            algorithm=algorithm,
            prediction_horizon_hours=prediction_horizon_hours,
            feature_schema={"features": feature_names},
            hyperparameters=hyperparameters or {},
            model_artifact_path=saved_model_path,
            calibrator_artifact_path=saved_cal_path,
            training_sample_count=len(X_train),
            positive_sample_count=int(np.sum(y_train == 1)),
            validation_metrics=training_summary.get("validation_metrics", {}),
            calibration_metrics=training_summary.get("calibration_metrics", {}),
            is_calibrated=training_summary.get("is_calibrated", False),
            status=PredictiveModelLifecycle.UNDER_VALIDATION,
            created_by=user_id,
        )
        db.session.add(version_obj)
        db.session.commit()

        return {
            "registry": registry.to_dict(),
            "version": version_obj.to_dict(),
            "training_summary": training_summary,
        }

    # =========================================================================
    # 5. Model Lifecycle (Approve, Activate)
    # =========================================================================

    @classmethod
    def get_predictive_models(cls, organization_id: str, machine_id: str) -> List[Dict[str, Any]]:
        """Lists model registries and versions for a machine."""
        machine = Machine.query.filter_by(id=machine_id, organization_id=organization_id).first()
        if not machine:
            raise ValueError(f"Machine '{machine_id}' not found.")

        registries = PredictiveModelRegistry.query.filter_by(
            organization_id=organization_id,
            machine_id=machine_id,
        ).all()

        results = []
        for reg in registries:
            reg_dict = reg.to_dict()
            versions = PredictiveModelVersion.query.filter_by(registry_id=reg.id).order_by(PredictiveModelVersion.version_number.desc()).all()
            reg_dict["versions"] = [v.to_dict() for v in versions]
            results.append(reg_dict)
        return results

    @classmethod
    def approve_model_version(cls, organization_id: str, version_id: str, user_id: str) -> Dict[str, Any]:
        """Approves a validated model version for deployment."""
        version = PredictiveModelVersion.query.filter_by(id=version_id).first()
        if not version:
            raise ValueError(f"Model version '{version_id}' not found.")

        registry = PredictiveModelRegistry.query.filter_by(
            id=version.registry_id,
            organization_id=organization_id,
        ).first()
        if not registry:
            raise ValueError("Unauthorized or model registry does not exist.")

        version.status = PredictiveModelLifecycle.APPROVED
        version.approved_by = user_id
        version.approved_at = datetime.now(timezone.utc)
        registry.lifecycle_status = PredictiveModelLifecycle.APPROVED

        db.session.commit()
        return version.to_dict()

    @classmethod
    def activate_model_version(cls, organization_id: str, version_id: str, user_id: str) -> Dict[str, Any]:
        """Activates an approved model version for live inference."""
        version = PredictiveModelVersion.query.filter_by(id=version_id).first()
        if not version:
            raise ValueError(f"Model version '{version_id}' not found.")

        registry = PredictiveModelRegistry.query.filter_by(
            id=version.registry_id,
            organization_id=organization_id,
        ).first()
        if not registry:
            raise ValueError("Unauthorized or model registry does not exist.")

        if version.status not in (PredictiveModelLifecycle.APPROVED, PredictiveModelLifecycle.ACTIVE):
            raise ValueError(f"Cannot activate model version with status '{version.status}'. Must be APPROVED first.")

        # Demote previous active versions in this registry
        all_versions = PredictiveModelVersion.query.filter_by(registry_id=registry.id).all()
        for v in all_versions:
            if v.id == version.id:
                v.status = PredictiveModelLifecycle.ACTIVE
            elif v.status == PredictiveModelLifecycle.ACTIVE:
                v.status = PredictiveModelLifecycle.RETIRED

        registry.active_version_number = version.version_number
        registry.lifecycle_status = PredictiveModelLifecycle.ACTIVE
        registry.updated_at = datetime.now(timezone.utc)

        db.session.commit()
        return {
            "registry": registry.to_dict(),
            "active_version": version.to_dict(),
        }

    # =========================================================================
    # 6. Prediction Inference & Queries
    # =========================================================================

    @classmethod
    def evaluate_predictions(cls, organization_id: str, machine_id: str) -> List[Dict[str, Any]]:
        """Executes live prediction pipeline for machine."""
        machine = Machine.query.filter_by(id=machine_id, organization_id=organization_id).first()
        if not machine:
            raise ValueError(f"Machine '{machine_id}' not found.")

        return PredictionPipeline.evaluate_machine_predictions(
            organization_id=organization_id,
            machine_id=machine_id,
        )

    @classmethod
    def get_equipment_predictions(
        cls,
        organization_id: str,
        machine_id: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Retrieves historical predictions for equipment."""
        machine = Machine.query.filter_by(id=machine_id, organization_id=organization_id).first()
        if not machine:
            raise ValueError(f"Machine '{machine_id}' not found.")

        predictions = (
            EquipmentPrediction.query.filter_by(
                organization_id=organization_id,
                machine_id=machine_id,
            )
            .order_by(EquipmentPrediction.evaluated_at.desc())
            .limit(limit)
            .all()
        )
        return [p.to_dict() for p in predictions]

    @classmethod
    def get_prediction_detail(cls, organization_id: str, prediction_id: str) -> Dict[str, Any]:
        """Retrieves prediction snapshot with feature evidence items."""
        pred = EquipmentPrediction.query.filter_by(
            id=prediction_id,
            organization_id=organization_id,
        ).first()
        if not pred:
            raise ValueError(f"Prediction '{prediction_id}' not found.")

        pred_dict = pred.to_dict()
        evidence = PredictionEvidence.query.filter_by(prediction_id=pred.id).all()
        pred_dict["evidence"] = [e.to_dict() for e in evidence]
        return pred_dict

    # =========================================================================
    # 7. Predictive Alerts
    # =========================================================================

    @classmethod
    def get_predictive_alerts(
        cls,
        organization_id: str,
        machine_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Lists actionable predictive alerts."""
        query = PredictiveAlert.query.filter_by(organization_id=organization_id)
        if machine_id:
            query = query.filter_by(machine_id=machine_id)
        if status:
            query = query.filter_by(status=status)

        alerts = query.order_by(PredictiveAlert.last_detected_at.desc()).limit(limit).all()
        return [a.to_dict() for a in alerts]

    @classmethod
    def review_predictive_alert(
        cls,
        organization_id: str,
        alert_id: str,
        user_id: str,
        new_status: str,
        engineer_notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Allows reliability/maintenance engineers to review, acknowledge, or resolve alerts."""
        alert = PredictiveAlert.query.filter_by(id=alert_id, organization_id=organization_id).first()
        if not alert:
            raise ValueError(f"Predictive alert '{alert_id}' not found.")

        valid_statuses = [
            PredictiveAlertStatus.OPEN,
            PredictiveAlertStatus.ACKNOWLEDGED,
            PredictiveAlertStatus.UNDER_INVESTIGATION,
            PredictiveAlertStatus.RESOLVED,
            PredictiveAlertStatus.DISMISSED,
        ]
        if new_status not in valid_statuses:
            raise ValueError(f"Invalid alert status '{new_status}'. Must be one of {valid_statuses}")

        alert.status = new_status
        alert.reviewed_by = user_id
        alert.reviewed_at = datetime.now(timezone.utc)
        if engineer_notes:
            alert.engineer_review_notes = engineer_notes.strip()

        db.session.commit()
        return alert.to_dict()
