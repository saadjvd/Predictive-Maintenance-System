import os
import json
import uuid
import pytest
import numpy as np
from datetime import datetime, timezone, timedelta

from app import create_app
from app.extensions import db
from app.models.tenant import Organization, Site
from app.models.equipment import Machine, EquipmentCategory, ProductionArea, ProductionLine
from app.models.signal_mapping import MachineSignal, SignalDefinition
from app.models.monitoring import SignalReading
from app.models.condition import (
    DataQualityEvent,
    QualityState,
    MachineOperatingStateRecord,
    OperatingState,
    BaselineProfile,
    BaselineVersion,
    BaselineLifecycle,
    AnomalyEvent,
    AnomalySeverity,
    EquipmentConditionObservation,
    ConditionClassification,
    EquipmentAlert,
    AlertStatus,
    AlertHistory,
    MLModelRegistry,
    MLModelVersion,
    ModelLifecycle,
)
from app.models.user import User, Role, UserRoleAssignment
from tests.test_equipment import setup_equipment_test_data, get_auth_token

from app.ml_engine.statistical_detector import StatisticalAnomalyDetector
from app.ml_engine.feature_engineering import FeatureEngineer
from app.ml_engine.isolation_forest_detector import IsolationForestWrapper
from app.ml_engine.decision_engine import AnomalyDecisionEngine, AnomalyDecision
from app.modules.operating_context.classifier import OperatingStateClassifier
from app.modules.data_quality.engine import DataQualityEngine
from app.modules.baselines.builder import BaselineStatsCalculator
from app.modules.alerts.services import AlertService
from app.modules.anomalies.services import AnomalyService
from app.modules.condition_monitoring.services import ConditionMonitoringService
from app.modules.signal_mapping.repositories import SignalDefinitionRepository


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
    """Seed test organizations, users, and machines."""
    data = setup_equipment_test_data(app)
    with app.app_context():
        SignalDefinitionRepository.seed_standard_definitions()

        # Clean existing condition records
        AlertHistory.query.delete()
        EquipmentAlert.query.delete()
        AnomalyEvent.query.delete()
        EquipmentConditionObservation.query.delete()
        BaselineVersion.query.delete()
        BaselineProfile.query.delete()
        MLModelVersion.query.delete()
        MLModelRegistry.query.delete()
        MachineOperatingStateRecord.query.delete()
        DataQualityEvent.query.delete()
        db.session.commit()

        org_a = db.session.get(Organization, data["org_a_id"])
        org_b = db.session.get(Organization, data["org_b_id"])

        # Machine A
        machine_a = Machine.query.filter_by(asset_code="MACH-COND-A", organization_id=org_a.id).first()
        if not machine_a:
            machine_a = Machine(
                organization_id=org_a.id,
                site_id=data["site_a1_id"],
                category_id=data["cat_blister_id"],
                equipment_name="Blister Packaging Line 1",
                asset_code="MACH-COND-A",
                criticality="Critical",
                lifecycle_status="Active",
            )
            db.session.add(machine_a)

        # Machine B
        machine_b = Machine.query.filter_by(asset_code="MACH-COND-B", organization_id=org_b.id).first()
        if not machine_b:
            machine_b = Machine(
                organization_id=org_b.id,
                site_id=data["site_b1_id"],
                category_id=data["cat_blister_id"],
                equipment_name="Tablet Press B",
                asset_code="MACH-COND-B",
                criticality="High",
                lifecycle_status="Active",
            )
            db.session.add(machine_b)
        db.session.commit()

        # Signals for Machine A
        sig_def_speed = SignalDefinition.query.filter_by(signal_code="ROTATIONAL_SPEED").first()
        sig_def_vib = SignalDefinition.query.filter_by(signal_code="MOTOR_VIBRATION").first()

        mach_sig_speed = MachineSignal.query.filter_by(machine_id=machine_a.id, source_node_id="ns=2;s=Speed_CPM").first()
        if not mach_sig_speed:
            mach_sig_speed = MachineSignal(
                organization_id=org_a.id,
                machine_id=machine_a.id,
                signal_definition_id=sig_def_speed.id,
                custom_name="Speed_CPM",
                source_node_id="ns=2;s=Speed_CPM",
                source_browse_name="Speed_CPM",
                normalized_unit="cpm",
                enabled=True,
            )
            db.session.add(mach_sig_speed)

        mach_sig_vib = MachineSignal.query.filter_by(machine_id=machine_a.id, source_node_id="ns=2;s=MainDriveMotorVibration").first()
        if not mach_sig_vib:
            mach_sig_vib = MachineSignal(
                organization_id=org_a.id,
                machine_id=machine_a.id,
                signal_definition_id=sig_def_vib.id,
                custom_name="MainDriveMotorVibration",
                source_node_id="ns=2;s=MainDriveMotorVibration",
                source_browse_name="MainDriveMotorVibration",
                normalized_unit="mm/s",
                enabled=True,
            )
            db.session.add(mach_sig_vib)
        db.session.commit()

        mach_a_id = machine_a.id
        mach_b_id = machine_b.id
        speed_id = mach_sig_speed.id
        vib_id = mach_sig_vib.id

    token_a = get_auth_token(client, "manager@getzpharma.com", "Manager@123")
    token_b = get_auth_token(client, "manager@benchmark.com", "BenchManager@123")

    return {
        "org_a_id": data["org_a_id"],
        "org_b_id": data["org_b_id"],
        "token_a": token_a,
        "token_b": token_b,
        "machine_a_id": mach_a_id,
        "machine_b_id": mach_b_id,
        "sig_speed_id": speed_id,
        "sig_vib_id": vib_id,
    }


# =============================================================================
# UNIT TESTS: STATISTICAL & ML ENGINE
# =============================================================================

def test_statistical_anomaly_detector_nominal():
    """Verify nominal values within envelope return None."""
    baseline_stats = {
        "mean": 100.0,
        "std": 5.0,
        "median": 100.0,
        "mad": 3.5,
        "min": 85.0,
        "max": 115.0,
        "p5": 90.0,
        "p95": 110.0,
    }
    result = StatisticalAnomalyDetector.evaluate_measurement(
        observed_value=102.0,
        baseline_stats=baseline_stats,
        signal_name="MotorSpeed",
        unit="rpm",
    )
    assert result is None


def test_statistical_anomaly_detector_critical_zscore():
    """Verify extreme deviation generates CRITICAL anomaly."""
    baseline_stats = {
        "mean": 100.0,
        "std": 5.0,
        "median": 100.0,
        "mad": 3.5,
        "min": 85.0,
        "max": 115.0,
        "p5": 90.0,
        "p95": 110.0,
    }
    # 135.0 is 7 standard deviations away
    result = StatisticalAnomalyDetector.evaluate_measurement(
        observed_value=135.0,
        baseline_stats=baseline_stats,
        signal_name="MotorSpeed",
        unit="rpm",
    )
    assert result is not None
    assert result.is_anomalous is True
    assert result.severity == AnomalySeverity.CRITICAL
    assert result.deviation_score >= 5.0
    assert "MotorSpeed" in result.summary


def test_feature_engineering_and_isolation_forest():
    """Verify multivariate feature matrix building and Isolation Forest fit/predict."""
    np.random.seed(42)
    records = []
    base_time = datetime.now(timezone.utc) - timedelta(minutes=50)

    for i in range(50):
        t = (base_time + timedelta(minutes=i)).isoformat()
        records.append({"timestamp": t, "signal_name": "Speed", "value": 240.0 + np.random.normal(0, 2)})
        records.append({"timestamp": t, "signal_name": "Vib", "value": 1.2 + np.random.normal(0, 0.1)})
        records.append({"timestamp": t, "signal_name": "Temp", "value": 140.0 + np.random.normal(0, 1)})

    X, feature_names, scaling_params = FeatureEngineer.build_training_matrix(
        readings_records=records,
        signal_names=["Speed", "Vib", "Temp"],
    )
    assert len(X) >= 40
    assert "Speed" in feature_names

    # Train Isolation Forest
    wrapper = IsolationForestWrapper(contamination=0.03, random_state=42)
    metrics = wrapper.fit(X, feature_names, scaling_params)
    assert metrics["sample_count"] == len(X)

    # In-sample nominal inference
    normal_vector = FeatureEngineer.transform_single_vector(
        current_values={"Speed": 240.5, "Vib": 1.21, "Temp": 140.2},
        feature_names=feature_names,
        scaling_params=scaling_params,
    )
    normal_res = wrapper.predict_vector(normal_vector)
    assert normal_res.severity in ("INFO", "WARNING")

    # Outlier inference (extreme vibration and temperature)
    outlier_vector = FeatureEngineer.transform_single_vector(
        current_values={"Speed": 240.0, "Vib": 8.5, "Temp": 195.0},
        feature_names=feature_names,
        scaling_params=scaling_params,
    )
    outlier_res = wrapper.predict_vector(outlier_vector)
    assert outlier_res.is_anomalous is True
    assert len(outlier_res.top_contributing_signals) > 0


def test_operating_state_classification():
    """Verify operating context classification rules."""
    # Running state
    state, conf, method, supporting = OperatingStateClassifier.classify_state({
        "SPEED": {"normalized_value": 240.0},
        "MOTOR_VIBRATION": {"normalized_value": 1.5},
        "SEALING_TEMP": {"normalized_value": 140.0},
    })
    assert state == OperatingState.RUNNING
    assert conf >= 0.7

    # Idle state
    state_idle, conf_idle, _, _ = OperatingStateClassifier.classify_state({
        "SPEED": {"normalized_value": 0.0},
        "MOTOR_CURRENT": {"normalized_value": 0.1},
    })
    assert state_idle == OperatingState.IDLE
    assert conf_idle >= 0.8


def test_data_quality_suppression_in_decision_engine():
    """Verify AnomalyDecisionEngine suppresses alarms when data quality is BAD."""
    stat_critical = StatisticalAnomalyDetector.evaluate_measurement(
        observed_value=500.0,
        baseline_stats={"mean": 100.0, "std": 5.0, "median": 100.0, "mad": 3.0, "min": 80, "max": 120, "p5": 90, "p95": 110},
        signal_name="Speed",
    )

    decision = AnomalyDecisionEngine.evaluate(
        data_quality_state=QualityState.STALE,
        data_quality_issues=[{"issue_type": "DATA_STALE", "signal_name": "Speed"}],
        operating_state=OperatingState.RUNNING,
        statistical_results=[stat_critical],
    )

    # Should suppress alert because data is stale
    assert decision.should_alert is False
    assert decision.condition_state == ConditionClassification.MONITORING_UNAVAILABLE
    assert "suppressed" in decision.summary.lower()


# =============================================================================
# INTEGRATION TESTS: DATABASE & REST APIS
# =============================================================================

def test_baseline_building_and_approval(client, seeded_env, app):
    """Test candidate baseline calculation and version approval via API."""
    with app.app_context():
        # Insert 30 readings for Machine A Speed signal
        now = datetime.now(timezone.utc)
        for i in range(30):
            r = SignalReading(
                event_id=f"evt-test-base-{i}-{uuid.uuid4()}",
                organization_id=seeded_env["org_a_id"],
                machine_id=seeded_env["machine_a_id"],
                signal_id=seeded_env["sig_speed_id"],
                source_timestamp=now - timedelta(minutes=30 - i),
                normalized_value=240.0 + (i % 5),
                quality_code="Good",
                simulator_flag=True,
            )
            db.session.add(r)
        db.session.commit()

    # Build baselines via POST
    headers = {"Authorization": f"Bearer {seeded_env['token_a']}"}
    res = client.post(
        f"/api/v1/equipment/{seeded_env['machine_a_id']}/baselines/build",
        headers=headers,
        json={"lookback_hours": 24, "operating_state": "RUNNING"},
    )
    assert res.status_code == 201
    data = res.get_json()
    assert data["total_candidates_ready"] >= 1

    # Verify baseline profile was created
    with app.app_context():
        profile = BaselineProfile.query.filter_by(
            machine_id=seeded_env["machine_a_id"],
            signal_id=seeded_env["sig_speed_id"],
        ).first()
        assert profile is not None

        # Check version stats
        ver = BaselineVersion.query.filter_by(profile_id=profile.id).order_by(BaselineVersion.version_number.desc()).first()
        assert ver is not None
        assert ver.mean is not None
        assert 239.0 <= ver.mean <= 245.0
        prof_id = profile.id
        ver_id = ver.id

    # Test baseline approval API
    appr_res = client.post(
        f"/api/v1/baselines/{prof_id}/approve",
        headers=headers,
        json={"version_id": ver_id, "notes": "Approved in automated test suite"},
    )
    assert appr_res.status_code == 200
    assert appr_res.get_json()["lifecycle_status"] == "ACTIVE"


def test_condition_evaluation_and_alert_acknowledgment(client, seeded_env, app):
    """Test full condition evaluation and alert acknowledgment workflow."""
    headers = {"Authorization": f"Bearer {seeded_env['token_a']}"}

    # Seed an anomalous vibration reading (e.g. 9.8 mm/s where normal is ~1.2)
    with app.app_context():
        # First ensure a baseline exists for vibration
        prof_vib = BaselineProfile(
            organization_id=seeded_env["org_a_id"],
            machine_id=seeded_env["machine_a_id"],
            signal_id=seeded_env["sig_vib_id"],
            name="Vibration Baseline",
            operating_state=OperatingState.RUNNING,
            lifecycle_status=BaselineLifecycle.ACTIVE,
            active_version_number=1,
        )
        db.session.add(prof_vib)
        db.session.flush()

        ver_vib = BaselineVersion(
            profile_id=prof_vib.id,
            version_number=1,
            mean=1.2,
            std=0.1,
            median=1.2,
            mad=0.08,
            min_value=0.8,
            max_value=1.5,
            p5=1.0,
            p95=1.4,
            validation_status="APPROVED",
        )
        db.session.add(ver_vib)

        # Anomalous reading
        r_vib = SignalReading(
            event_id=f"evt-test-vib-anom-{uuid.uuid4()}",
            organization_id=seeded_env["org_a_id"],
            machine_id=seeded_env["machine_a_id"],
            signal_id=seeded_env["sig_vib_id"],
            source_timestamp=datetime.now(timezone.utc),
            normalized_value=9.85,
            quality_code="Good",
            simulator_flag=True,
        )
        db.session.add(r_vib)
        db.session.commit()

    # Trigger evaluation
    eval_res = client.post(
        f"/api/v1/equipment/{seeded_env['machine_a_id']}/condition/evaluate",
        headers=headers,
    )
    assert eval_res.status_code == 200
    eval_data = eval_res.get_json()["evaluation"]
    assert eval_data["condition_state"] in (ConditionClassification.CRITICAL, ConditionClassification.ATTENTION)
    assert len(eval_data["statistical_anomalies"]) > 0

    # Check alert was created
    alerts_res = client.get(
        f"/api/v1/alerts?machine_id={seeded_env['machine_a_id']}",
        headers=headers,
    )
    assert alerts_res.status_code == 200
    alerts = alerts_res.get_json()["alerts"]
    assert len(alerts) >= 1
    target_alert = alerts[0]

    # Acknowledge the alert
    ack_res = client.post(
        f"/api/v1/alerts/{target_alert['id']}/acknowledge",
        headers=headers,
        json={"notes": "Inspection scheduled for main drive motor bearing."},
    )
    assert ack_res.status_code == 200
    ack_alert = ack_res.get_json()["alert"]
    assert ack_alert["status"] == AlertStatus.ACKNOWLEDGED
    assert ack_alert["acknowledged_by"] is not None


def test_cross_tenant_isolation(client, seeded_env):
    """Verify Org B cannot access Org A condition, anomalies, or alerts."""
    headers_b = {"Authorization": f"Bearer {seeded_env['token_b']}"}

    # Org B trying to access Org A machine condition
    res = client.get(
        f"/api/v1/equipment/{seeded_env['machine_a_id']}/condition",
        headers=headers_b,
    )
    assert res.status_code == 404

    # Org B trying to access Org A anomalies
    anom_res = client.get(
        f"/api/v1/equipment/{seeded_env['machine_a_id']}/anomalies",
        headers=headers_b,
    )
    assert anom_res.status_code == 200
    assert len(anom_res.get_json()["anomalies"]) == 0
