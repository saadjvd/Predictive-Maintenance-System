import os
import json
import uuid
import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta

from app import create_app
from app.extensions import db
from app.models.tenant import Organization, Site
from app.models.equipment import Machine, EquipmentCategory
from app.models.signal_mapping import MachineSignal, SignalDefinition
from app.models.monitoring import SignalReading
from app.models.condition import (
    BaselineProfile,
    BaselineVersion,
    BaselineLifecycle,
    AnomalyEvent,
    AnomalySeverity,
)
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
from tests.test_equipment import setup_equipment_test_data, get_auth_token
from app.modules.signal_mapping.repositories import SignalDefinitionRepository
from app.ml_engine.prediction.failure_modes import FailureModeCatalog
from app.ml_engine.prediction.predictive_features import PredictiveFeatureExtractor
from app.ml_engine.prediction.dataset_builder import PredictiveDatasetBuilder
from app.ml_engine.prediction.probability_calibrator import ProbabilityCalibrator
from app.ml_engine.prediction.failure_classifier import FailureClassifierWrapper
from app.ml_engine.prediction.rul_estimator import WeibullSurvivalRUL
from app.ml_engine.prediction.eligibility_engine import ModelEligibilityEngine
from app.ml_engine.prediction.prediction_pipeline import PredictionPipeline
from app.modules.predictions.services import PredictionService


@pytest.fixture(scope="module")
def app():
    """Create Flask application instance for test module."""
    flask_app = create_app("testing")
    with flask_app.app_context():
        db.create_all()
        yield flask_app
        db.session.remove()


@pytest.fixture(scope="module")
def client(app):
    return app.test_client()


@pytest.fixture(scope="module")
def seeded_env(app, client):
    """Seed test organizations, users, machines, and signals."""
    data = setup_equipment_test_data(app)
    with app.app_context():
        SignalDefinitionRepository.seed_standard_definitions()
        FailureModeCatalog.seed_standard_modes()

        # Clean existing prediction records for test isolation
        PredictiveAlert.query.delete()
        PredictionEvidence.query.delete()
        EquipmentPrediction.query.delete()
        PredictiveModelVersion.query.delete()
        PredictiveModelRegistry.query.delete()
        PredictiveDataset.query.delete()
        FailureRecord.query.delete()
        db.session.commit()

        org_a = db.session.get(Organization, data["org_a_id"])
        org_b = db.session.get(Organization, data["org_b_id"])

        # Machine A
        machine_a = Machine.query.filter_by(asset_code="MACH-PRED-A", organization_id=org_a.id).first()
        if not machine_a:
            machine_a = Machine(
                organization_id=org_a.id,
                site_id=data["site_a1_id"],
                category_id=data["cat_blister_id"],
                equipment_name="Blister Packaging Line Phase 6",
                asset_code="MACH-PRED-A",
                criticality="Critical",
                lifecycle_status="Active",
            )
            db.session.add(machine_a)

        # Machine B
        machine_b = Machine.query.filter_by(asset_code="MACH-PRED-B", organization_id=org_b.id).first()
        if not machine_b:
            machine_b = Machine(
                organization_id=org_b.id,
                site_id=data["site_b1_id"],
                category_id=data["cat_blister_id"],
                equipment_name="Tablet Press Phase 6",
                asset_code="MACH-PRED-B",
                criticality="High",
                lifecycle_status="Active",
            )
            db.session.add(machine_b)
        db.session.commit()

        # Signals for Machine A
        sig_def_speed = SignalDefinition.query.filter_by(signal_code="ROTATIONAL_SPEED").first()
        sig_def_vib = SignalDefinition.query.filter_by(signal_code="MOTOR_VIBRATION").first()

        mach_sig_speed = MachineSignal.query.filter_by(machine_id=machine_a.id, source_node_id="ns=2;s=Pred_Speed").first()
        if not mach_sig_speed:
            mach_sig_speed = MachineSignal(
                organization_id=org_a.id,
                machine_id=machine_a.id,
                signal_definition_id=sig_def_speed.id,
                source_node_id="ns=2;s=Pred_Speed",
                custom_name="Line Speed",
                enabled=True,
            )
            db.session.add(mach_sig_speed)

        mach_sig_vib = MachineSignal.query.filter_by(machine_id=machine_a.id, source_node_id="ns=2;s=Pred_Vib").first()
        if not mach_sig_vib:
            mach_sig_vib = MachineSignal(
                organization_id=org_a.id,
                machine_id=machine_a.id,
                signal_definition_id=sig_def_vib.id,
                source_node_id="ns=2;s=Pred_Vib",
                custom_name="Drive Vibration",
                enabled=True,
            )
            db.session.add(mach_sig_vib)

        db.session.commit()

        # Generate 48 hours of baseline readings for Machine A
        base_time = datetime.now(timezone.utc) - timedelta(hours=48)
        readings = []
        for i in range(100):
            ts = base_time + timedelta(minutes=i * 28)
            # Speed around 60.0, Vib around 1.2
            readings.append(SignalReading(
                event_id=str(uuid.uuid4()),
                organization_id=org_a.id,
                machine_id=machine_a.id,
                signal_id=mach_sig_speed.id,
                source_timestamp=ts,
                source_value=str(60.0 + (i % 5) * 0.5),
                normalized_value=60.0 + (i % 5) * 0.5,
                quality_code="Good",
            ))
            readings.append(SignalReading(
                event_id=str(uuid.uuid4()),
                organization_id=org_a.id,
                machine_id=machine_a.id,
                signal_id=mach_sig_vib.id,
                source_timestamp=ts,
                source_value=str(1.2 + (i % 3) * 0.1),
                normalized_value=1.2 + (i % 3) * 0.1,
                quality_code="Good",
            ))
        db.session.bulk_save_objects(readings)
        db.session.commit()

        # Generate Approved Baseline Profile for Machine A
        bp = BaselineProfile(
            organization_id=org_a.id,
            machine_id=machine_a.id,
            signal_id=mach_sig_vib.id,
            name="Vibration Running Baseline",
            operating_state="RUNNING",
            lifecycle_status=BaselineLifecycle.APPROVED,
            active_version_number=1,
        )
        db.session.add(bp)
        db.session.flush()

        bv = BaselineVersion(
            profile_id=bp.id,
            version_number=1,
            mean=1.2,
            std=0.2,
            validation_status="VALID",
        )
        db.session.add(bv)
        db.session.commit()

        tokens = {
            "org_a_admin": get_auth_token(client, "manager@getzpharma.com", "Manager@123"),
            "org_b_admin": get_auth_token(client, "manager@benchmark.com", "BenchManager@123"),
        }

        return {
            "org_a_id": org_a.id,
            "org_b_id": org_b.id,
            "machine_a_id": machine_a.id,
            "machine_b_id": machine_b.id,
            "sig_speed_id": mach_sig_speed.id,
            "sig_vib_id": mach_sig_vib.id,
            "tokens": tokens,
        }


# =============================================================================
# 1. Failure Modes Catalog & Custom Creation Tests
# =============================================================================

def test_failure_modes_catalog(app, client, seeded_env):
    """Test standard failure mode catalog querying and custom failure mode creation."""
    token_a = seeded_env["tokens"]["org_a_admin"]

    # 1. Query standard failure modes
    res = client.get("/api/v1/failure-modes", headers={"Authorization": f"Bearer {token_a}"})
    assert res.status_code == 200
    data = res.get_json()
    assert len(data) >= 5
    codes = [m["code"] for m in data]
    assert "FM_BEARING_DEGRADATION" in codes
    assert "FM_MOTOR_OVERHEATING" in codes
    assert "FM_PNEUMATIC_PRESSURE_LOSS" in codes

    # 2. Create custom failure mode
    custom_payload = {
        "code": "FM_CUSTOM_FEEDER_JAM",
        "name": "Blister Feeder Jamming",
        "component_type": "Feeder",
        "description": "Feed track obstruction causing motor stall.",
        "severity_impact": "HIGH",
    }
    res = client.post(
        "/api/v1/failure-modes",
        headers={"Authorization": f"Bearer {token_a}"},
        json=custom_payload,
    )
    assert res.status_code == 201
    created = res.get_json()
    assert created["code"] == "FM_CUSTOM_FEEDER_JAM"
    assert created["is_standard"] is False


# =============================================================================
# 2. Failure Records Lifecycle & Engineer Verification Tests
# =============================================================================

def test_failure_records_lifecycle(app, client, seeded_env):
    """Test failure record creation, verification transitions, and engineer review."""
    token_a = seeded_env["tokens"]["org_a_admin"]
    machine_id = seeded_env["machine_a_id"]

    fm = FailureMode.query.filter_by(code="FM_BEARING_DEGRADATION").first()

    # 1. Log unverified failure record
    started_time = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    record_payload = {
        "failure_mode_id": fm.id,
        "failure_started_at": started_time,
        "failure_description": "Excessive drive motor noise and high housing temp.",
        "observed_symptoms": ["Vibration > 4.5 mm/s", "Acoustic emission"],
        "downtime_minutes": 180.0,
    }
    res = client.post(
        f"/api/v1/equipment/{machine_id}/failure-records",
        headers={"Authorization": f"Bearer {token_a}"},
        json=record_payload,
    )
    assert res.status_code == 201
    rec = res.get_json()
    assert rec["verification_status"] == FailureVerificationStatus.UNVERIFIED
    record_id = rec["id"]

    # 2. Verify failure record by engineer
    verify_payload = {
        "verification_status": FailureVerificationStatus.CONFIRMED,
        "confirmed_root_cause": "Inner raceway micro-spalling due to bearing fatigue.",
        "maintenance_action": "Replaced drive motor bearing assembly and replenished lubricant.",
    }
    res = client.patch(
        f"/api/v1/failure-records/{record_id}/verify",
        headers={"Authorization": f"Bearer {token_a}"},
        json=verify_payload,
    )
    assert res.status_code == 200
    updated = res.get_json()
    assert updated["verification_status"] == FailureVerificationStatus.CONFIRMED
    assert updated["confirmed_root_cause"] == "Inner raceway micro-spalling due to bearing fatigue."
    assert updated["verified_by"] is not None


# =============================================================================
# 3. Dataset Builder & Temporal Splitting (No Leakage)
# =============================================================================

def test_dataset_builder_temporal_split():
    """Verify temporal sliding window feature extraction and strict temporal splitting."""
    # Generate 5 days of simulated sensor data
    base_ts = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    readings = []
    for h in range(120):
        t = base_ts + timedelta(hours=h)
        readings.append({
            "source_timestamp": t.isoformat(),
            "signal_name": "MOTOR_VIBRATION",
            "normalized_value": 1.2 + (h * 0.02) if h > 80 else 1.2,
        })
        readings.append({
            "source_timestamp": t.isoformat(),
            "signal_name": "ROTATIONAL_SPEED",
            "normalized_value": 60.0,
        })

    # Verified failure at hour 100
    failures = [{
        "failure_started_at": (base_ts + timedelta(hours=100)).isoformat(),
        "verification_status": FailureVerificationStatus.CONFIRMED,
        "failure_mode_code": "FM_BEARING_DEGRADATION",
    }]

    X, y, feature_names, meta = PredictiveDatasetBuilder.build_supervised_dataset(
        readings_records=readings,
        failure_records=failures,
        prediction_horizon_hours=24,
        observation_step_hours=4,
        feature_window_hours=12,
    )

    assert len(X) > 10
    assert len(y) == len(X)
    assert np.sum(y == 1) >= 1  # Samples within 24h of hour 100 should be positive (1)

    # Temporal split
    X_train, y_train, X_val, y_val = PredictiveDatasetBuilder.split_temporal(X, y, train_ratio=0.7)
    assert len(X_train) + len(X_val) == len(X)
    assert len(X_train) > 0 and len(X_val) > 0


# =============================================================================
# 4. Insufficient Data Rejection
# =============================================================================

def test_insufficient_data_rejection(app, seeded_env):
    """Verify training is strictly rejected when verified failure samples < 3."""
    with app.app_context():
        classifier = FailureClassifierWrapper()
        X_dummy = np.zeros((20, 5))
        y_insufficient = np.array([0]*18 + [1]*2)  # Only 2 positive samples

        with pytest.raises(ValueError) as excinfo:
            classifier.fit_and_validate(
                X_train=X_dummy,
                y_train=y_insufficient,
                X_val=X_dummy[:5],
                y_val=y_insufficient[:5],
                feature_names=["f1", "f2", "f3", "f4", "f5"],
            )
        assert "Insufficient historical failure labels" in str(excinfo.value)


# =============================================================================
# 5. Supervised Classifier Training & Probability Calibration
# =============================================================================

def test_supervised_classifier_training_and_calibration():
    """Verify supervised model training, Platt/Isotonic calibration, and Brier score evaluation."""
    np.random.seed(42)
    n_train = 60
    n_val = 30

    # Synthetic features: 5 features, feature 0 is strongly predictive
    X_train = np.random.randn(n_train, 5)
    y_train = (X_train[:, 0] > 0.4).astype(int)
    # Ensure at least 5 positive samples
    y_train[:5] = 1

    X_val = np.random.randn(n_val, 5)
    y_val = (X_val[:, 0] > 0.4).astype(int)
    y_val[:3] = 1

    feature_names = ["vib__p95", "vib__slope", "speed__mean", "temp__max", "anom_count"]

    classifier = FailureClassifierWrapper(algorithm="RANDOM_FOREST", prediction_horizon_hours=168)
    summary = classifier.fit_and_validate(
        X_train=X_train,
        y_train=y_train,
        X_val=X_val,
        y_val=y_val,
        feature_names=feature_names,
        calibrate=True,
    )

    assert "validation_metrics" in summary
    assert "calibration_metrics" in summary
    assert summary["calibration_metrics"]["brier_score"] < 0.35
    assert classifier.is_calibrated is True

    # Test single-vector prediction
    sample_vec = np.array([[2.5, 0.4, 60.0, 75.0, 3.0]])
    cal_prob, raw_prob, contributions = classifier.predict_risk(sample_vec)
    assert 0.0 <= cal_prob <= 1.0
    assert 0.0 <= raw_prob <= 1.0
    assert len(contributions) == 5


# =============================================================================
# 6. Weibull Survival RUL Estimation
# =============================================================================

def test_weibull_survival_rul():
    """Verify parametric Weibull survival analysis and conditional RUL bounds."""
    # Case 1: Adequate failure records (>= 3 confirmed failures)
    failure_records = [
        {"verification_status": "CONFIRMED", "downtime_minutes": 60, "failure_started_at": "2026-01-01T00:00:00Z"},
        {"verification_status": "CONFIRMED", "downtime_minutes": 90, "failure_started_at": "2026-01-10T00:00:00Z"},
        {"verification_status": "CONFIRMED", "downtime_minutes": 120, "failure_started_at": "2026-01-20T00:00:00Z"},
        {"verification_status": "PREVENTIVE_MAINTENANCE", "downtime_minutes": 30, "failure_started_at": "2026-01-25T00:00:00Z"},
    ]

    res = WeibullSurvivalRUL.estimate_conditional_rul(
        failure_records=failure_records,
        current_operating_hours=100.0,
    )
    assert res.is_available is True
    assert res.rul_hours is not None
    assert res.confidence_lower is not None
    assert res.confidence_upper is not None
    assert res.confidence_lower <= res.rul_hours <= res.confidence_upper

    # Case 2: Insufficient failure records (< 3) -> Must return RUL_UNAVAILABLE
    res_insufficient = WeibullSurvivalRUL.estimate_conditional_rul(
        failure_records=failure_records[:2],
        current_operating_hours=50.0,
    )
    assert res_insufficient.is_available is False
    assert res_insufficient.rul_hours is None
    assert "UNAVAILABLE" in res_insufficient.rationale


# =============================================================================
# 7. Model Eligibility Engine
# =============================================================================

def test_eligibility_engine(app, seeded_env):
    """Verify eligibility state transitions based on signals, data quality, and failure history."""
    with app.app_context():
        org_id = seeded_env["org_a_id"]
        mach_id = seeded_env["machine_a_id"]

        # Machine A currently has signals & history, but only 1 verified failure -> INSUFFICIENT_DATA
        eligibility = ModelEligibilityEngine.evaluate_machine_eligibility(org_id, mach_id)
        assert eligibility["eligibility_state"] == PredictionEligibilityState.INSUFFICIENT_DATA
        assert eligibility["can_predict"] is False
        assert eligibility["can_train"] is False

        # Add 2 more confirmed failure records so count reaches 3
        fm = FailureMode.query.first()
        f2 = FailureRecord(
            organization_id=org_id,
            machine_id=mach_id,
            failure_mode_id=fm.id,
            failure_started_at=datetime.now(timezone.utc) - timedelta(days=10),
            failure_description="Second failure test record",
            verification_status=FailureVerificationStatus.CONFIRMED,
        )
        f3 = FailureRecord(
            organization_id=org_id,
            machine_id=mach_id,
            failure_mode_id=fm.id,
            failure_started_at=datetime.now(timezone.utc) - timedelta(days=5),
            failure_description="Third failure test record",
            verification_status=FailureVerificationStatus.CONFIRMED,
        )
        db.session.add_all([f2, f3])
        db.session.commit()

        # Re-evaluate: Now reaches 3 confirmed failures -> TRAINING_ELIGIBLE
        eligibility_updated = ModelEligibilityEngine.evaluate_machine_eligibility(org_id, mach_id)
        assert eligibility_updated["eligibility_state"] == PredictionEligibilityState.TRAINING_ELIGIBLE
        assert eligibility_updated["can_train"] is True


# =============================================================================
# 8. Model Governance Lifecycle (Approve & Activate)
# =============================================================================

def test_model_governance_lifecycle(app, seeded_env):
    """Test model version approval and activation state machine."""
    with app.app_context():
        org_id = seeded_env["org_a_id"]
        mach_id = seeded_env["machine_a_id"]
        fm = FailureMode.query.first()

        # 1. Create registry & version in UNDER_VALIDATION
        reg = PredictiveModelRegistry(
            organization_id=org_id,
            machine_id=mach_id,
            failure_mode_id=fm.id,
            name="Test Model Lifecycle Registry",
            lifecycle_status=PredictiveModelLifecycle.UNDER_VALIDATION,
        )
        db.session.add(reg)
        db.session.flush()

        v1 = PredictiveModelVersion(
            registry_id=reg.id,
            version_number=1,
            algorithm="RANDOM_FOREST",
            feature_schema={"features": ["f1"]},
            hyperparameters={},
            status=PredictiveModelLifecycle.UNDER_VALIDATION,
        )
        db.session.add(v1)
        db.session.commit()

        # 2. Cannot activate unapproved model
        with pytest.raises(ValueError):
            PredictionService.activate_model_version(org_id, v1.id, "user-123")

        # 3. Approve model
        approved = PredictionService.approve_model_version(org_id, v1.id, "user-123")
        assert approved["status"] == PredictiveModelLifecycle.APPROVED

        # 4. Activate model
        activated = PredictionService.activate_model_version(org_id, v1.id, "user-123")
        assert activated["registry"]["lifecycle_status"] == PredictiveModelLifecycle.ACTIVE
        assert activated["registry"]["active_version_number"] == 1


# =============================================================================
# 9. Predictive Alert Workflow & Deduplication
# =============================================================================

def test_predictive_alert_workflow(app, client, seeded_env):
    """Test predictive alert generation, cooldown deduplication, and engineer review."""
    with app.app_context():
        org_id = seeded_env["org_a_id"]
        mach_id = seeded_env["machine_a_id"]
        fm = FailureMode.query.first()

        # Create dummy prediction
        pred = EquipmentPrediction(
            organization_id=org_id,
            machine_id=mach_id,
            failure_mode_id=fm.id,
            calibrated_probability=0.78,
            risk_category=PredictiveRiskCategory.CRITICAL,
            rationale="Critical motor bearing degradation risk.",
            evaluated_at=datetime.now(timezone.utc),
        )
        db.session.add(pred)
        db.session.flush()

        # Trigger alert via internal manager
        now_utc = datetime.now(timezone.utc)
        PredictionPipeline._manage_predictive_alert(
            organization_id=org_id,
            machine_id=mach_id,
            component_id=None,
            failure_mode_id=fm.id,
            prediction_id=pred.id,
            prediction_horizon_hours=168,
            calibrated_risk=0.78,
            risk_category=PredictiveRiskCategory.CRITICAL,
            now_utc=now_utc,
        )
        db.session.commit()

        # Verify alert exists
        alert = PredictiveAlert.query.filter_by(machine_id=mach_id, failure_mode_id=fm.id).first()
        assert alert is not None
        assert alert.status == PredictiveAlertStatus.OPEN
        assert alert.risk_category == PredictiveRiskCategory.CRITICAL
        alert_id = alert.id

        # Trigger again immediately -> Should update last_detected_at without creating second alert
        PredictionPipeline._manage_predictive_alert(
            organization_id=org_id,
            machine_id=mach_id,
            component_id=None,
            failure_mode_id=fm.id,
            prediction_id=pred.id,
            prediction_horizon_hours=168,
            calibrated_risk=0.82,
            risk_category=PredictiveRiskCategory.CRITICAL,
            now_utc=now_utc + timedelta(minutes=15),
        )
        db.session.commit()

        open_alerts = PredictiveAlert.query.filter_by(machine_id=mach_id, failure_mode_id=fm.id, status=PredictiveAlertStatus.OPEN).all()
        assert len(open_alerts) == 1
        assert open_alerts[0].calibrated_risk == 0.82

    # Review alert via REST API
    token_a = seeded_env["tokens"]["org_a_admin"]
    review_res = client.post(
        f"/api/v1/predictive-alerts/{alert_id}/review",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "status": PredictiveAlertStatus.ACKNOWLEDGED,
            "engineer_review_notes": "Work order WO-9081 scheduled for bearing inspection during changeover.",
        },
    )
    assert review_res.status_code == 200
    rev_data = review_res.get_json()
    assert rev_data["status"] == PredictiveAlertStatus.ACKNOWLEDGED
    assert "WO-9081" in rev_data["engineer_review_notes"]


# =============================================================================
# 10. Multi-Tenant Isolation
# =============================================================================

def test_tenant_isolation(app, client, seeded_env):
    """Verify strict tenant isolation across failure records and predictions."""
    token_b = seeded_env["tokens"]["org_b_admin"]
    mach_a_id = seeded_env["machine_a_id"]

    # Tenant B tries to access Tenant A's failure records -> 404
    res = client.get(
        f"/api/v1/equipment/{mach_a_id}/failure-records",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert res.status_code == 404

    # Tenant B tries to evaluate predictions for Tenant A's machine -> 404 or 400
    res = client.post(
        f"/api/v1/equipment/{mach_a_id}/predictions/evaluate",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert res.status_code in (400, 404)
