from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone, timedelta
import numpy as np
import pandas as pd

from app.extensions import db
from app.models.equipment import Machine, MachineComponent
from app.models.signal_mapping import MachineSignal
from app.models.monitoring import SignalReading
from app.models.condition import BaselineProfile, BaselineVersion, AnomalyEvent
from app.models.prediction import (
    EquipmentPrediction,
    PredictionEvidence,
    PredictiveAlert,
    PredictiveRiskCategory,
    PredictiveAlertStatus,
    PredictiveModelRegistry,
    PredictiveModelVersion,
    PredictiveModelLifecycle,
    PredictionEligibilityState,
    FailureRecord,
    FailureVerificationStatus,
    FailureMode,
)
from app.ml_engine.prediction.predictive_features import PredictiveFeatureExtractor
from app.ml_engine.prediction.failure_classifier import FailureClassifierWrapper
from app.ml_engine.prediction.rul_estimator import WeibullSurvivalRUL
from app.ml_engine.prediction.eligibility_engine import ModelEligibilityEngine


class PredictionPipeline:
    """End-to-end execution pipeline for machine failure risk & RUL estimation."""

    COOLDOWN_HOURS = 12

    @classmethod
    def evaluate_machine_predictions(
        cls,
        organization_id: str,
        machine_id: str,
    ) -> List[Dict[str, Any]]:
        """
        Executes calibrated risk and conditional RUL inference for all active model families of a machine.
        If machine lacks eligible models or data, generates transparent fallback prediction record.
        """
        # 1. Evaluate eligibility
        eligibility = ModelEligibilityEngine.evaluate_machine_eligibility(
            organization_id=organization_id,
            machine_id=machine_id,
        )

        state = eligibility.get("eligibility_state", PredictionEligibilityState.NOT_CONFIGURED)
        results = []

        # Find active model registries
        active_registries = (
            PredictiveModelRegistry.query.filter_by(
                organization_id=organization_id,
                machine_id=machine_id,
                lifecycle_status=PredictiveModelLifecycle.ACTIVE,
            ).all()
        )

        if not active_registries or not eligibility.get("can_predict", False):
            # Fallback prediction explanation per failure mode or general fallback
            modes = FailureMode.query.filter(
                (FailureMode.organization_id == organization_id) | (FailureMode.is_standard == True)
            ).limit(3).all()

            # If no active model or blocked by DQ / insufficient data, record/return explicit unavailable status
            explanation = "; ".join(eligibility.get("reasons", ["Predictive model not active or calibrated."]))
            for fm in modes:
                prediction_obj = EquipmentPrediction(
                    organization_id=organization_id,
                    machine_id=machine_id,
                    failure_mode_id=fm.id,
                    prediction_horizon_hours=168,
                    status=state,
                    calibrated_probability=None,
                    uncalibrated_score=None,
                    risk_category=PredictiveRiskCategory.LOW,
                    rul_hours=None,
                    rul_confidence_lower=None,
                    rul_confidence_upper=None,
                    rul_method=None,
                    rationale=f"Prediction unavailable for {fm.name}: {explanation}",
                    evaluated_at=datetime.now(timezone.utc),
                )
                db.session.add(prediction_obj)
                db.session.commit()
                results.append(prediction_obj.to_dict())

            return results

        # 2. Extract recent sensor data for feature calculation (last 24 hours)
        now_utc = datetime.now(timezone.utc)
        start_time = now_utc - timedelta(hours=24)

        signals = MachineSignal.query.filter_by(
            machine_id=machine_id,
            organization_id=organization_id,
            enabled=True,
        ).all()
        signal_map = {s.id: s for s in signals}

        readings = (
            SignalReading.query.filter(
                SignalReading.signal_id.in_([s.id for s in signals]),
                SignalReading.source_timestamp >= start_time,
            )
            .order_by(SignalReading.source_timestamp.asc())
            .all()
        )

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

        readings_df = pd.DataFrame(readings_records) if readings_records else pd.DataFrame()

        # Retrieve approved baseline envelopes
        profiles = BaselineProfile.query.filter(
            BaselineProfile.machine_id == machine_id,
            BaselineProfile.lifecycle_status.in_(["APPROVED", "ACTIVE"])
        ).all()
        baseline_map: Dict[str, Dict[str, float]] = {}
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

        # Retrieve recent anomalies
        recent_anomalies = (
            AnomalyEvent.query.filter(
                AnomalyEvent.machine_id == machine_id,
                AnomalyEvent.first_detected_at >= start_time,
            ).all()
        )
        anom_list = [{"severity": a.severity, "type": a.anomaly_type} for a in recent_anomalies]

        # Extract features
        extracted_features = PredictiveFeatureExtractor.extract_window_features(
            readings_df=readings_df,
            baseline_envelopes=baseline_map,
            recent_anomalies=anom_list,
            operating_hours=24.0,
        )

        # 3. Evaluate conditional RUL from historical records
        failure_records = FailureRecord.query.filter_by(
            machine_id=machine_id,
            organization_id=organization_id,
        ).all()

        confirmed_records = [
            f for f in failure_records
            if f.verification_status in (FailureVerificationStatus.CONFIRMED, FailureVerificationStatus.SUSPECTED)
        ]

        # 4. Predict for each active model
        for reg in active_registries:
            active_version = None
            if reg.active_version_number is not None:
                active_version = PredictiveModelVersion.query.filter_by(
                    registry_id=reg.id,
                    version_number=reg.active_version_number,
                ).first()

            if not active_version or not active_version.model_artifact_path:
                continue

            try:
                classifier = FailureClassifierWrapper.load(
                    model_path=active_version.model_artifact_path,
                    calibrator_path=active_version.calibrator_artifact_path,
                )
            except Exception as e:
                continue

            # Align feature vector to model schema
            feature_vector = np.zeros((1, len(classifier.feature_names)), dtype=np.float64)
            for i, fname in enumerate(classifier.feature_names):
                feature_vector[0, i] = extracted_features.get(fname, 0.0)

            # Predict calibrated probability
            calibrated_prob, raw_score, contributions = classifier.predict_risk(feature_vector)

            # Map to risk category
            if calibrated_prob < 0.15:
                risk_cat = PredictiveRiskCategory.LOW
            elif calibrated_prob < 0.40:
                risk_cat = PredictiveRiskCategory.MEDIUM
            elif calibrated_prob < 0.70:
                risk_cat = PredictiveRiskCategory.HIGH
            else:
                risk_cat = PredictiveRiskCategory.CRITICAL

            # Calculate conditional RUL
            rul_res = WeibullSurvivalRUL.estimate_conditional_rul(
                failure_records=failure_records,
                current_operating_hours=120.0,
            )

            # Formulate explainable rationale
            fm_name = reg.failure_mode.name if reg.failure_mode else "Equipment Degradation"
            top_feats = sorted(contributions.items(), key=lambda x: x[1], reverse=True)[:3]
            feat_desc = ", ".join([f"{k} (weight {v:.2f})" for k, v in top_feats]) if top_feats else "Telemetry within normal parameters"

            rationale = (
                f"Calibrated failure risk for {fm_name} is {calibrated_prob*100:.1f}% ({risk_cat}) "
                f"over a {reg.prediction_horizon_hours}h horizon. Primary drivers: {feat_desc}."
            )
            if rul_res.is_available and rul_res.rul_hours is not None:
                rationale += f" Conditional RUL estimate: {rul_res.rul_hours:.1f} hours [{rul_res.confidence_lower:.1f}h - {rul_res.confidence_upper:.1f}h]."
            else:
                rationale += f" RUL is unavailable ({rul_res.rationale})."

            # Create prediction record
            prediction_obj = EquipmentPrediction(
                organization_id=organization_id,
                machine_id=machine_id,
                component_id=reg.component_id,
                failure_mode_id=reg.failure_mode_id,
                model_version_id=active_version.id,
                prediction_horizon_hours=reg.prediction_horizon_hours,
                status=PredictionEligibilityState.PREDICTION_READY,
                calibrated_probability=calibrated_prob,
                uncalibrated_score=raw_score,
                risk_category=risk_cat,
                rul_hours=rul_res.rul_hours if rul_res.is_available else None,
                rul_confidence_lower=rul_res.confidence_lower if rul_res.is_available else None,
                rul_confidence_upper=rul_res.confidence_upper if rul_res.is_available else None,
                rul_method=rul_res.method if rul_res.is_available else None,
                rationale=rationale,
                evaluated_at=now_utc,
            )
            db.session.add(prediction_obj)
            db.session.flush()

            # Add evidence items
            for fname, score in top_feats:
                sig_id = None
                for s in signals:
                    s_code = (
                        s.signal_definition.signal_code
                        if s.signal_definition
                        else s.custom_name
                    )
                    if s_code and s_code in fname:
                        sig_id = s.id
                        break

                ev_obj = PredictionEvidence(
                    prediction_id=prediction_obj.id,
                    signal_id=sig_id,
                    feature_name=fname,
                    feature_value=float(extracted_features.get(fname, 0.0)),
                    baseline_expected_value=baseline_map.get(fname.split("__")[0], {}).get("mean") if "__" in fname else None,
                    contribution_score=float(score),
                    evidence_details={"raw_weight": float(score)},
                )
                db.session.add(ev_obj)

            # Check Predictive Alert Triggering (HIGH or CRITICAL risk)
            if risk_cat in (PredictiveRiskCategory.HIGH, PredictiveRiskCategory.CRITICAL):
                cls._manage_predictive_alert(
                    organization_id=organization_id,
                    machine_id=machine_id,
                    component_id=reg.component_id,
                    failure_mode_id=reg.failure_mode_id,
                    prediction_id=prediction_obj.id,
                    prediction_horizon_hours=reg.prediction_horizon_hours,
                    calibrated_risk=calibrated_prob,
                    risk_category=risk_cat,
                    now_utc=now_utc,
                )

            db.session.commit()
            results.append(prediction_obj.to_dict())

        return results

    @classmethod
    def _manage_predictive_alert(
        cls,
        organization_id: str,
        machine_id: str,
        component_id: Optional[str],
        failure_mode_id: str,
        prediction_id: str,
        prediction_horizon_hours: int,
        calibrated_risk: float,
        risk_category: str,
        now_utc: datetime,
    ) -> None:
        """Manages deduplication and cooldown for actionable predictive alerts."""
        # Find any existing open alert for this machine & failure mode
        existing_alert = PredictiveAlert.query.filter_by(
            organization_id=organization_id,
            machine_id=machine_id,
            failure_mode_id=failure_mode_id,
            status=PredictiveAlertStatus.OPEN,
        ).first()

        if existing_alert:
            # Update last detected timestamp and latest risk
            existing_alert.last_detected_at = now_utc
            existing_alert.calibrated_risk = calibrated_risk
            existing_alert.risk_category = risk_category
            existing_alert.prediction_id = prediction_id
            return

        # Check cooldown from recently dismissed/resolved alert
        recent_alert = (
            PredictiveAlert.query.filter_by(
                organization_id=organization_id,
                machine_id=machine_id,
                failure_mode_id=failure_mode_id,
            )
            .order_by(PredictiveAlert.updated_at.desc())
            .first()
        )

        if recent_alert and recent_alert.cooldown_until:
            cd = recent_alert.cooldown_until
            if cd.tzinfo is None:
                cd = cd.replace(tzinfo=timezone.utc)
            if now_utc < cd:
                # Under cooldown; suppress alert duplicate
                return

        new_alert = PredictiveAlert(
            organization_id=organization_id,
            machine_id=machine_id,
            component_id=component_id,
            failure_mode_id=failure_mode_id,
            prediction_id=prediction_id,
            prediction_horizon_hours=prediction_horizon_hours,
            calibrated_risk=calibrated_risk,
            risk_category=risk_category,
            status=PredictiveAlertStatus.OPEN,
            first_detected_at=now_utc,
            last_detected_at=now_utc,
            cooldown_until=now_utc + timedelta(hours=cls.COOLDOWN_HOURS),
        )
        db.session.add(new_alert)
