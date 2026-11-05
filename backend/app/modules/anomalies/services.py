import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from app.extensions import db
from app.models.condition import (
    AnomalyEvent,
    AnomalyEvidence,
    AnomalySeverity,
    EquipmentConditionObservation,
    ConditionClassification,
    BaselineProfile,
    BaselineVersion,
    BaselineLifecycle,
    MLModelRegistry,
    MLModelVersion,
    ModelLifecycle,
    OperatingState,
    QualityState,
)
from app.models.equipment import Machine
from app.models.signal_mapping import MachineSignal
from app.models.monitoring import SignalReading
from app.ml_engine.statistical_detector import StatisticalAnomalyDetector, StatisticalAnomalyResult
from app.ml_engine.feature_engineering import FeatureEngineer
from app.ml_engine.isolation_forest_detector import IsolationForestWrapper, IsolationForestResult
from app.ml_engine.decision_engine import AnomalyDecisionEngine, AnomalyDecision
from app.modules.data_quality.services import DataQualityService
from app.modules.operating_context.services import OperatingContextService
from app.modules.alerts.services import AlertService


class AnomalyService:
    """Orchestrates industrial anomaly detection, ML model training, and evidence generation."""

    @classmethod
    def record_anomaly_event(
        cls,
        organization_id: str,
        machine_id: str,
        decision: AnomalyDecision,
        operating_state: str,
        component_id: Optional[str] = None,
    ) -> AnomalyEvent:
        """Records explainable anomaly event and triggers alert if necessary."""
        now = datetime.now(timezone.utc)

        # Look for recent active anomaly for this machine to aggregate occurrences
        fifteen_min_ago = now - timedelta(minutes=15)
        recent_anomaly = AnomalyEvent.query.filter(
            AnomalyEvent.organization_id == organization_id,
            AnomalyEvent.machine_id == machine_id,
            AnomalyEvent.status == "ACTIVE",
            AnomalyEvent.latest_detected_at >= fifteen_min_ago,
        ).first()

        if recent_anomaly:
            recent_anomaly.latest_detected_at = now
            recent_anomaly.occurrence_count += 1
            recent_anomaly.anomaly_score = max(recent_anomaly.anomaly_score, decision.anomaly_score)
            if decision.severity == AnomalySeverity.CRITICAL:
                recent_anomaly.severity = AnomalySeverity.CRITICAL
            anomaly_event = recent_anomaly
        else:
            anomaly_event = AnomalyEvent(
                organization_id=organization_id,
                machine_id=machine_id,
                component_id=component_id,
                detection_method=decision.detection_method,
                severity=decision.severity,
                operating_state=operating_state,
                status="ACTIVE",
                first_detected_at=now,
                latest_detected_at=now,
                occurrence_count=1,
                anomaly_score=decision.anomaly_score,
                affected_signals=decision.affected_signals,
                summary=decision.summary,
            )
            db.session.add(anomaly_event)
            db.session.flush()

        # Add signal-level evidence items
        for ev in decision.evidence_items:
            sig_name = ev.get("evidence", {}).get("signal_name") or ev.get("signal_name")
            if sig_name:
                signal_obj = (
                    MachineSignal.query.filter_by(organization_id=organization_id, machine_id=machine_id)
                    .filter((MachineSignal.custom_name == sig_name) | (MachineSignal.source_browse_name == sig_name))
                    .first()
                )
                if signal_obj:
                    evidence_entry = AnomalyEvidence(
                        anomaly_id=anomaly_event.id,
                        signal_id=signal_obj.id,
                        source_timestamp=now,
                        observed_value=ev.get("observed_value", 0.0),
                        baseline_expected_value=ev.get("expected_value"),
                        deviation_magnitude=ev.get("deviation_score"),
                        evidence_payload=ev,
                    )
                    db.session.add(evidence_entry)

        db.session.commit()

        # Trigger alert if warranted
        if decision.should_alert:
            AlertService.process_anomaly_alert(
                organization_id=organization_id,
                machine_id=machine_id,
                anomaly_event_id=anomaly_event.id,
                severity=decision.severity,
                component_id=component_id,
            )

        return anomaly_event

    @classmethod
    def evaluate_machine_condition(
        cls,
        organization_id: str,
        machine_id: str,
        recent_minutes: int = 15,
    ) -> Dict[str, Any]:
        """
        Runs comprehensive condition evaluation for a machine:
        1. Data Quality check
        2. Operating State determination
        3. Statistical Anomaly evaluation against active Baselines
        4. ML Isolation Forest evaluation against active Model (if active)
        5. Decision Engine synthesis
        6. EquipmentConditionObservation logging
        """
        now = datetime.now(timezone.utc)
        machine = Machine.query.filter_by(id=machine_id, organization_id=organization_id).first()
        if not machine:
            raise ValueError(f"Machine {machine_id} not found.")

        # 1. Evaluate Data Quality
        dq_eval = DataQualityService.evaluate_machine_quality(
            machine_id=machine_id,
            organization_id=organization_id,
            recent_minutes=recent_minutes,
        )

        # 2. Determine Operating Context
        op_context = OperatingContextService.evaluate_current_state(
            machine_id=machine_id,
            organization_id=organization_id,
            recent_minutes=recent_minutes,
        )
        current_state = op_context.get("current_state", OperatingState.UNKNOWN)

        # 3. Retrieve Latest Sensor Readings for Machine Signals
        signals = MachineSignal.query.filter_by(machine_id=machine_id, organization_id=organization_id).all()
        latest_readings: Dict[str, float] = {}
        sig_name_map = {}
        for sig in signals:
            sname = sig.custom_name or (sig.signal_definition.name if sig.signal_definition else sig.source_browse_name) or sig.id
            sig_name_map[sig.id] = sname
            last_r = SignalReading.query.filter_by(signal_id=sig.id).order_by(SignalReading.source_timestamp.desc()).first()
            if last_r:
                val = last_r.normalized_value if last_r.normalized_value is not None else last_r.raw_value_numeric
                if val is not None:
                    latest_readings[sname] = float(val)

        # 4. Statistical Anomaly Evaluation against active baseline profiles
        statistical_results: List[StatisticalAnomalyResult] = []
        for sig in signals:
            sname = sig_name_map.get(sig.id)
            val = latest_readings.get(sname)
            if val is None:
                continue

            # Find active baseline profile for this signal and current operating state
            prof = BaselineProfile.query.filter_by(
                machine_id=machine_id,
                signal_id=sig.id,
                operating_state=current_state,
                lifecycle_status=BaselineLifecycle.ACTIVE,
            ).first()

            if not prof:
                # Fallback to RUNNING state baseline if in normal run
                prof = BaselineProfile.query.filter_by(
                    machine_id=machine_id,
                    signal_id=sig.id,
                    operating_state=OperatingState.RUNNING,
                    lifecycle_status=BaselineLifecycle.ACTIVE,
                ).first()

            if prof and prof.active_version_number:
                b_ver = BaselineVersion.query.filter_by(
                    profile_id=prof.id,
                    version_number=prof.active_version_number,
                ).first()
                if b_ver:
                    stats = {
                        "mean": b_ver.mean,
                        "std": b_ver.std,
                        "median": b_ver.median,
                        "mad": b_ver.mad,
                        "min": b_ver.min_value,
                        "max": b_ver.max_value,
                        "p5": b_ver.p5,
                        "p95": b_ver.p95,
                    }
                    res = StatisticalAnomalyDetector.evaluate_measurement(
                        observed_value=val,
                        baseline_stats=stats,
                        signal_name=sname,
                        unit=sig.normalized_unit or sig.source_unit or "",
                    )
                    if res:
                        statistical_results.append(res)

        # 5. Machine Learning Anomaly Evaluation (Isolation Forest)
        ml_result: Optional[IsolationForestResult] = None
        ml_model_reg = MLModelRegistry.query.filter_by(
            machine_id=machine_id,
            organization_id=organization_id,
            lifecycle_status=ModelLifecycle.ACTIVE,
        ).first()

        if ml_model_reg and ml_model_reg.active_version_number:
            ml_ver = MLModelVersion.query.filter_by(
                registry_id=ml_model_reg.id,
                version_number=ml_model_reg.active_version_number,
            ).first()

            if ml_ver and ml_ver.model_artifact_path and os.path.exists(ml_ver.model_artifact_path):
                try:
                    wrapper = IsolationForestWrapper.load(ml_ver.model_artifact_path)
                    x_vector = FeatureEngineer.transform_single_vector(
                        current_values=latest_readings,
                        feature_names=wrapper.feature_names,
                        scaling_params=wrapper.scaling_params,
                    )
                    ml_result = wrapper.predict_vector(x_vector)
                except Exception as e:
                    # ML model execution error shouldn't crash pipeline
                    pass

        # 6. Synthesize Unified Anomaly Decision
        decision = AnomalyDecisionEngine.evaluate(
            data_quality_state=dq_eval.get("overall_state", QualityState.GOOD),
            data_quality_issues=dq_eval.get("issues", []),
            operating_state=current_state,
            statistical_results=statistical_results,
            ml_result=ml_result,
        )

        # 7. Record Condition Observation
        active_anom_count = len(statistical_results) + (1 if ml_result and ml_result.is_anomalous else 0)
        observation = EquipmentConditionObservation(
            organization_id=organization_id,
            machine_id=machine_id,
            condition_state=decision.condition_state,
            active_anomaly_count=active_anom_count,
            data_quality_issue_count=len(dq_eval.get("issues", [])),
            summary_reason=decision.summary,
            observed_at=now,
        )
        db.session.add(observation)
        db.session.commit()

        # 8. Record Anomaly Event if anomalous
        anomaly_event_record = None
        if decision.severity in (AnomalySeverity.CRITICAL, AnomalySeverity.WARNING) or (decision.evidence_items and decision.condition_state != ConditionClassification.NORMAL):
            anomaly_event_record = cls.record_anomaly_event(
                organization_id=organization_id,
                machine_id=machine_id,
                decision=decision,
                operating_state=current_state,
            )

        return {
            "machine_id": machine_id,
            "condition_state": decision.condition_state,
            "operating_state": current_state,
            "data_quality_state": dq_eval.get("overall_state", QualityState.GOOD),
            "anomaly_score": decision.anomaly_score,
            "severity": decision.severity,
            "summary": decision.summary,
            "affected_signals": decision.affected_signals,
            "statistical_anomalies": [r.to_dict() for r in statistical_results],
            "ml_anomaly": ml_result.to_dict() if ml_result else None,
            "active_anomaly_id": anomaly_event_record.id if anomaly_event_record else None,
            "evaluated_at": now.isoformat(),
        }

    @classmethod
    def train_machine_model(
        cls,
        organization_id: str,
        machine_id: str,
        user_id: Optional[str] = None,
        lookback_days: int = 7,
    ) -> Dict[str, Any]:
        """Trains multivariate Isolation Forest model on clean historical baseline readings."""
        machine = Machine.query.filter_by(id=machine_id, organization_id=organization_id).first()
        if not machine:
            raise ValueError(f"Machine {machine_id} not found.")

        signals = MachineSignal.query.filter_by(machine_id=machine_id, organization_id=organization_id).all()
        if not signals or len(signals) < 1:
            raise ValueError("Machine has no configured signals for ML model training.")

        sig_map = {
            s.id: (s.custom_name or (s.signal_definition.name if s.signal_definition else s.source_browse_name) or s.id)
            for s in signals
        }
        signal_names = list(sig_map.values())
        signal_ids = [s.id for s in signals]

        # Gather historical readings
        start_time = datetime.now(timezone.utc) - timedelta(days=lookback_days)
        readings = SignalReading.query.filter(
            SignalReading.signal_id.in_(signal_ids),
            SignalReading.source_timestamp >= start_time,
        ).order_by(SignalReading.source_timestamp.asc()).all()

        if len(readings) < 15:
            raise ValueError(f"Insufficient historical sensor data: {len(readings)} readings found. Minimum 15 required for ML training.")

        # Convert to dictionary format
        records = []
        for r in readings:
            val = r.normalized_value if r.normalized_value is not None else r.raw_value_numeric
            if val is not None:
                records.append({
                    "timestamp": r.source_timestamp.isoformat(),
                    "signal_name": sig_map.get(r.signal_id, "unknown"),
                    "value": float(val),
                })

        # Build feature matrix
        X, feature_names, scaling_params = FeatureEngineer.build_training_matrix(
            readings_records=records,
            signal_names=signal_names,
        )

        if len(X) < 10:
            raise ValueError(f"Feature matrix too small: {len(X)} rows after aggregation. More data points required.")

        # Train model
        wrapper = IsolationForestWrapper(contamination=0.03)
        metrics = wrapper.fit(X=X, feature_names=feature_names, scaling_params=scaling_params)

        # Get or create MLModelRegistry
        reg = MLModelRegistry.query.filter_by(machine_id=machine_id, organization_id=organization_id).first()
        if not reg:
            reg = MLModelRegistry(
                organization_id=organization_id,
                machine_id=machine_id,
                model_type="ISOLATION_FOREST",
                name=f"{machine.equipment_name} Anomaly Model",
                lifecycle_status=ModelLifecycle.ACTIVE,
                active_version_number=1,
            )
            db.session.add(reg)
            db.session.flush()

        new_version_num = (reg.active_version_number or 0) + 1

        # Save artifact
        artifact_filename = f"{organization_id}_{machine_id}_v{new_version_num}.joblib"
        artifact_path = os.path.join("backend", "artifacts", "models", artifact_filename)
        wrapper.save(artifact_path)

        # Create MLModelVersion
        now = datetime.now(timezone.utc)
        version_entry = MLModelVersion(
            registry_id=reg.id,
            version_number=new_version_num,
            feature_schema={"feature_names": feature_names},
            hyperparameters={"n_estimators": 100, "contamination": 0.03},
            model_artifact_path=artifact_path,
            training_sample_count=len(X),
            training_dataset_ref=f"Readings from last {lookback_days} days ({len(readings)} points)",
            validation_metrics=metrics,
            status=ModelLifecycle.ACTIVE,
            created_by=user_id,
            approved_by=user_id,
            approved_at=now,
        )
        db.session.add(version_entry)

        # Update registry to point to active version
        reg.active_version_number = new_version_num
        reg.lifecycle_status = ModelLifecycle.ACTIVE
        db.session.commit()

        return {
            "registry": reg.to_dict(),
            "version": version_entry.to_dict(),
            "metrics": metrics,
        }

    @classmethod
    def get_machine_anomalies(
        cls,
        organization_id: str,
        machine_id: str,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """List anomaly events for a machine."""
        query = AnomalyEvent.query.filter_by(organization_id=organization_id, machine_id=machine_id)
        if severity:
            query = query.filter_by(severity=severity)
        if status:
            query = query.filter_by(status=status)

        events = query.order_by(AnomalyEvent.latest_detected_at.desc()).limit(limit).all()
        return [e.to_dict() for e in events]

    @classmethod
    def get_anomaly_detail(cls, anomaly_id: str, organization_id: str) -> Optional[Dict[str, Any]]:
        """Get single anomaly event with evidence items."""
        event = AnomalyEvent.query.filter_by(id=anomaly_id, organization_id=organization_id).first()
        if not event:
            return None
        d = event.to_dict()
        d["evidence"] = [ev.to_dict() for ev in event.evidence_items.all()]
        return d

    @classmethod
    def get_machine_ml_models(cls, machine_id: str, organization_id: str) -> Dict[str, Any]:
        """Lists ML model registry and versions for machine."""
        reg = MLModelRegistry.query.filter_by(machine_id=machine_id, organization_id=organization_id).first()
        if not reg:
            return {"registry": None, "versions": []}
        return {
            "registry": reg.to_dict(),
            "versions": [v.to_dict() for v in reg.versions.order_by(MLModelVersion.version_number.desc()).all()],
        }
