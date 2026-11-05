"""PharmaPredict AI — Phase 9 Factory Pilot & Real-World Validation Test Battery.

Validates:
1. Pilot creation in DRAFT status with automated GAMP 5 readiness checklist initialization.
2. Equipment enrollment into pilots in strict read-only SHADOW MODE.
3. Multi-tenant boundary isolation across distinct organizations.
4. GAMP 5 equipment readiness evaluation and checklist progress calculation.
5. Strict safety gate: Activation blocked without verified Engineering & IT/OT Security approvals.
6. Multi-department digital approvals with 21 CFR Part 11 cryptographic signature tokens.
7. Authorized activation and shadow-mode status verification.
8. Certified engineer feedback recording and reference truth labeling (TRUE_POSITIVE, FALSE_POSITIVE).
9. Empirical pilot KPI calculation (precision, uptime, safety adherence).
10. Candidate model offline validation and version rollback.
11. Multi-factory scalability and concurrent tenant isolation.
12. Executive Go/No-Go pilot audit report generation.
"""
import uuid
import pytest
from datetime import datetime, timezone, timedelta

from app import create_app
from app.extensions import db
from app.models.tenant import Organization, Site
from app.models.user import User, Role, UserRoleAssignment
from app.models.equipment import Machine, EquipmentCategory
from app.models.diagnostic import DiagnosticSession
from app.models.condition import AnomalyEvent
from app.models.pilot import (
    FactoryPilot,
    PilotEquipment,
    PilotApproval,
    PilotReadinessCheck,
    PilotEngineerFeedback,
    PilotModelEvaluation,
    PilotReport,
    PilotLifecycleStatus,
    MonitoringMode,
    PilotApprovalType,
    ApprovalDecision,
    ReadinessCheckStatus,
    EngineerFeedbackAssessment,
    GoNoGoRecommendation,
)
from app.modules.pilots.services import PilotService
from tests.test_equipment import setup_equipment_test_data, get_auth_token


@pytest.fixture(scope="module")
def app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture(scope="module")
def client(app):
    return app.test_client()


@pytest.fixture(scope="module")
def pilot_data(app):
    with app.app_context():
        data = setup_equipment_test_data(app)
        data["org_id"] = data["org_a_id"]

        # Ensure manager user has engineer/manager role
        user = User.query.filter_by(email="manager@getzpharma.com").first()
        if user:
            role_maint = Role.query.filter_by(name=Role.MAINTENANCE_MANAGER).first()
            if role_maint and not user.has_role(Role.MAINTENANCE_MANAGER, data["org_id"]):
                db.session.add(UserRoleAssignment(user_id=user.id, role_id=role_maint.id, organization_id=data["org_id"]))
                db.session.commit()
        data["user_id"] = user.id if user else None

        # Create production test machine
        machine = Machine(
            organization_id=data["org_a_id"],
            site_id=data["site_a1_id"],
            production_area_id=data["area_osd_id"],
            production_line_id=data["line_1_id"],
            category_id=data["cat_blister_id"],
            asset_code="PILOT-UHL-01",
            equipment_name="Uhlmann Blister Packaging Pilot Machine",
            criticality="Critical",
        )
        db.session.add(machine)
        db.session.flush()

        # Create a mock diagnostic session for feedback tests
        diag = DiagnosticSession(
            organization_id=data["org_a_id"],
            machine_id=machine.id,
            status="COMPLETED",
            current_stage="COMPLETED",
        )
        db.session.add(diag)
        db.session.commit()

        data["machine_id"] = machine.id
        data["diagnostic_session_id"] = diag.id
        return data


# =============================================================================
# TEST 1 & 2: PILOT CREATION & EQUIPMENT ENROLLMENT
# =============================================================================

def test_pilot_creation_and_checklist_init(app, pilot_data):
    """Test 1: Creates a factory pilot in DRAFT and verifies standard readiness checks are generated."""
    with app.app_context():
        pilot_dict = PilotService.create_pilot(
            organization_id=pilot_data["org_id"],
            site_id=pilot_data["site_a1_id"],
            pilot_name="Getz Site 1 Blister Packaging Shadow Pilot",
            description="12-week controlled pilot evaluating AI anomaly detection on Uhlmann packaging line.",
            objectives="Zero batch disruption, evaluate bearing failure predictions in shadow mode.",
            monitoring_mode="SHADOW",
            responsible_engineer_id=pilot_data["user_id"],
        )

        assert pilot_dict["id"] is not None
        assert pilot_dict["status"] == PilotLifecycleStatus.DRAFT.value
        assert pilot_dict["monitoring_mode"] == MonitoringMode.SHADOW.value

        # Verify automated GAMP 5 readiness checklist initialization
        details = PilotService.get_pilot_details(pilot_dict["id"], pilot_data["org_id"])
        checks = details["readiness_checks"]
        assert len(checks) >= 15
        categories = {c["check_category"] for c in checks}
        assert "REGISTRATION" in categories
        assert "CONNECTIVITY" in categories
        assert "DATA_QUALITY" in categories
        assert "BASELINES" in categories
        assert "SECURITY" in categories
        assert "QA" in categories


def test_equipment_assignment_to_pilot(app, pilot_data):
    """Test 2: Enrolls production equipment in pilot, enforcing SHADOW mode."""
    with app.app_context():
        pilot = PilotService.list_pilots(pilot_data["org_id"], limit=1)[0]
        results = PilotService.assign_equipment(
            pilot_id=pilot["id"],
            organization_id=pilot_data["org_id"],
            machine_ids=[pilot_data["machine_id"]],
            monitoring_mode="SHADOW",
        )

        assert len(results) == 1
        assert results[0]["machine_id"] == pilot_data["machine_id"]
        assert results[0]["monitoring_mode"] == "SHADOW"
        assert results[0]["is_active"] is True


# =============================================================================
# TEST 3: MULTI-TENANT ISOLATION
# =============================================================================

def test_cross_tenant_pilot_isolation(app, pilot_data):
    """Test 3: Confirms Org B cannot view or modify Org A's factory pilot."""
    with app.app_context():
        pilot_a = PilotService.list_pilots(pilot_data["org_id"], limit=1)[0]
        org_b_id = pilot_data["org_b_id"]

        # Attempt to access Org A's pilot with Org B's identifier
        with pytest.raises(ValueError, match="not found for this organization"):
            PilotService.get_pilot_details(pilot_a["id"], org_b_id)

        # Attempt to update Org A's pilot under Org B
        with pytest.raises(ValueError, match="not found"):
            PilotService.update_pilot(pilot_a["id"], org_b_id, pilot_name="Compromised Name")


# =============================================================================
# TEST 4 & 5: READINESS REVIEW & STRICT APPROVAL GATE
# =============================================================================

def test_readiness_review_evaluation(app, pilot_data):
    """Test 4: Updates readiness checklist items and verifies review progress calculation."""
    with app.app_context():
        pilot = PilotService.list_pilots(pilot_data["org_id"], limit=1)[0]
        details = PilotService.get_pilot_details(pilot["id"], pilot_data["org_id"])
        checks = details["readiness_checks"]

        # Satisfy first 3 checks
        for c in checks[:3]:
            PilotService.update_readiness_check(
                pilot_id=pilot["id"],
                check_id=c["id"],
                organization_id=pilot_data["org_id"],
                status=ReadinessCheckStatus.SATISFIED.value,
                evidence_summary="Verified and documented in site plant register.",
                reviewer_id=pilot_data["user_id"],
            )

        review = PilotService.perform_readiness_review(pilot["id"], pilot_data["org_id"], pilot_data["user_id"])
        assert review["satisfied_checks"] >= 3
        assert review["readiness_percentage"] > 0.0
        assert review["is_ready_for_approval"] is False  # not all checks satisfied yet


def test_activation_blocked_without_approvals(app, pilot_data):
    """Test 5: CRITICAL GATE: Verifies pilot CANNOT be activated without verified Engineering & Security sign-offs."""
    with app.app_context():
        pilot = PilotService.list_pilots(pilot_data["org_id"], limit=1)[0]

        # Attempt activation without approvals
        with pytest.raises(PermissionError, match="Pilot activation BLOCKED: Missing mandatory site authorization"):
            PilotService.activate_pilot(pilot["id"], pilot_data["org_id"], pilot_data["user_id"])


# =============================================================================
# TEST 6 & 7: MULTI-DEPARTMENT APPROVALS & AUTHORIZED ACTIVATION
# =============================================================================

def test_multi_department_approvals_and_activation(app, pilot_data):
    """Test 6 & 7: Records Engineering + Security + QA approvals with 21 CFR Part 11 signatures, then activates."""
    with app.app_context():
        pilot = PilotService.list_pilots(pilot_data["org_id"], limit=1)[0]

        # 1. Engineering approval
        eng_ap = PilotService.submit_approval(
            pilot_id=pilot["id"],
            organization_id=pilot_data["org_id"],
            approver_id=pilot_data["user_id"],
            approval_type=PilotApprovalType.ENGINEERING.value,
            decision=ApprovalDecision.APPROVED.value,
            comments="Packaging line mechanical baseline verified. Ready for shadow monitoring.",
        )
        assert eng_ap["signature_hash"] is not None
        assert eng_ap["approval_type"] == "ENGINEERING"

        # 2. IT/OT Security approval
        sec_ap = PilotService.submit_approval(
            pilot_id=pilot["id"],
            organization_id=pilot_data["org_id"],
            approver_id=pilot_data["user_id"],
            approval_type=PilotApprovalType.IT_OT_SECURITY.value,
            decision=ApprovalDecision.APPROVED.value,
            comments="Read-only data diode and gateway VLAN segregation reviewed and approved.",
        )
        assert sec_ap["signature_hash"] is not None

        # 3. QA approval
        qa_ap = PilotService.submit_approval(
            pilot_id=pilot["id"],
            organization_id=pilot_data["org_id"],
            approver_id=pilot_data["user_id"],
            approval_type=PilotApprovalType.QUALITY_ASSURANCE.value,
            decision=ApprovalDecision.APPROVED.value,
            comments="GAMP 5 non-GxP direct impact decision-support protocol approved.",
        )
        assert qa_ap["signature_hash"] is not None

        # 4. Now activation must succeed!
        activation = PilotService.activate_pilot(pilot["id"], pilot_data["org_id"], pilot_data["user_id"])
        assert activation["status"] == PilotLifecycleStatus.ACTIVE.value
        assert activation["monitoring_mode"] == "SHADOW"
        assert "strict read-only SHADOW MODE" in activation["message"]


# =============================================================================
# TEST 8, 9 & 10: ENGINEER FEEDBACK & ANOMALY VALIDATION
# =============================================================================

def test_engineer_diagnostic_feedback_recording(app, pilot_data):
    """Test 8 & 9: Submits maintenance engineer feedback and computes empirical accuracy."""
    with app.app_context():
        pilot = PilotService.list_pilots(pilot_data["org_id"], limit=1)[0]

        # Submission 1: True positive anomaly
        fb1 = PilotService.submit_engineer_feedback(
            pilot_id=pilot["id"],
            organization_id=pilot_data["org_id"],
            diagnostic_session_id=pilot_data["diagnostic_session_id"],
            engineer_id=pilot_data["user_id"],
            assessment=EngineerFeedbackAssessment.ACCURATE.value,
            verified_root_cause="Drive motor outer raceway spalling confirmed via acoustic stethoprobe.",
            inspection_findings="Lubrication starvation observed on non-drive end bearing.",
            action_taken="Replenished synthetic food-grade grease during scheduled CIP window.",
            actual_outcome="Vibration velocity dropped from 4.8 mm/s to 1.9 mm/s.",
            false_alarm_flag=False,
            reference_label="TRUE_POSITIVE",
        )
        assert fb1["assessment"] == "ACCURATE"
        assert fb1["reference_label"] == "TRUE_POSITIVE"

        # Submission 2: False positive baseline transient
        fb2 = PilotService.submit_engineer_feedback(
            pilot_id=pilot["id"],
            organization_id=pilot_data["org_id"],
            diagnostic_session_id=pilot_data["diagnostic_session_id"],
            engineer_id=pilot_data["user_id"],
            assessment=EngineerFeedbackAssessment.PARTIALLY_ACCURATE.value,
            verified_root_cause="Transient blister cavity temperature overshoot during tool heat-up cycle.",
            inspection_findings="Operating state was warm-up transient, not steady state.",
            false_alarm_flag=True,
            reference_label="FALSE_POSITIVE",
        )
        assert fb2["false_alarm_flag"] is True

        # Check empirical pilot metrics
        metrics = PilotService.get_pilot_metrics(pilot["id"], pilot_data["org_id"])
        assert metrics["total_feedback_submissions"] == 2
        assert metrics["accurate_feedback_count"] == 2
        assert metrics["false_alarms_recorded"] == 1
        assert metrics["true_positives_recorded"] == 1
        assert metrics["safety_enforcement_adherence_pct"] == 100.0


# =============================================================================
# TEST 11: PREDICTIVE MODEL OFFLINE BENCHMARK & ROLLBACK
# =============================================================================

def test_predictive_model_offline_validation_and_rollback(app, pilot_data):
    """Test 11: Validates candidate model benchmark and rollback to previous version."""
    with app.app_context():
        pilot = PilotService.list_pilots(pilot_data["org_id"], limit=1)[0]

        # Record candidate model evaluation
        eval_rec = PilotService.evaluate_model_offline(
            pilot_id=pilot["id"],
            organization_id=pilot_data["org_id"],
            machine_id=pilot_data["machine_id"],
            model_name="blister_bearing_xgboost",
            model_version="v2.1.0-CANDIDATE",
            metrics={"precision": 0.88, "recall": 0.84, "pr_auc": 0.91, "f1": 0.86},
            status="CANDIDATE",
            previous_model_version="v1.0.0-PROD",
            evaluated_by_id=pilot_data["user_id"],
        )
        assert eval_rec["status"] == "CANDIDATE"
        assert eval_rec["model_version"] == "v2.1.0-CANDIDATE"

        # Execute controlled rollback
        rb = PilotService.rollback_model(
            pilot_id=pilot["id"],
            evaluation_id=eval_rec["id"],
            organization_id=pilot_data["org_id"],
            user_id=pilot_data["user_id"],
        )
        assert rb["status"] == "ROLLED_BACK"
        assert rb["active_version"] == "v1.0.0-PROD"


# =============================================================================
# TEST 12: MULTI-FACTORY SCALABILITY & CONCURRENT TENANT ISOLATION
# =============================================================================

def test_multi_factory_concurrent_scalability(app, pilot_data):
    """Test 12: Concurrently creates and manages pilots across multiple factories with strict tenant boundaries."""
    with app.app_context():
        # Factory 1 (Org A, Site 1)
        pilot_site1 = PilotService.create_pilot(
            organization_id=pilot_data["org_a_id"],
            site_id=pilot_data["site_a1_id"],
            pilot_name="Factory 1 - Solid Dose Shadow Pilot",
        )

        # Factory 2 (Org A, Site 2)
        pilot_site2 = PilotService.create_pilot(
            organization_id=pilot_data["org_a_id"],
            site_id=pilot_data["site_a2_id"],
            pilot_name="Factory 2 - Liquid Parenteral Pilot",
        )

        # Factory 3 (Org B, Site 1) - Competing manufacturer
        pilot_org_b = PilotService.create_pilot(
            organization_id=pilot_data["org_b_id"],
            site_id=pilot_data["site_b1_id"],
            pilot_name="Org B Factory 1 Pilot",
        )

        # Verify Org A queries retrieve ONLY Org A pilots
        org_a_pilots = PilotService.list_pilots(pilot_data["org_a_id"])
        org_a_ids = [p["id"] for p in org_a_pilots]
        assert pilot_site1["id"] in org_a_ids
        assert pilot_site2["id"] in org_a_ids
        assert pilot_org_b["id"] not in org_a_ids

        # Verify Org B queries retrieve ONLY Org B pilots
        org_b_pilots = PilotService.list_pilots(pilot_data["org_b_id"])
        org_b_ids = [p["id"] for p in org_b_pilots]
        assert pilot_org_b["id"] in org_b_ids
        assert pilot_site1["id"] not in org_b_ids
        assert pilot_site2["id"] not in org_b_ids


# =============================================================================
# TEST 13: GO/NO-GO EXECUTIVE PILOT AUDIT REPORT
# =============================================================================

def test_executive_pilot_report_generation(app, pilot_data):
    """Test 13: Generates auditable executive pilot report with Go/No-Go determination."""
    with app.app_context():
        pilot = PilotService.list_pilots(pilot_data["org_id"], limit=1)[0]
        report = PilotService.generate_pilot_report(
            pilot_id=pilot["id"],
            organization_id=pilot_data["org_id"],
            user_id=pilot_data["user_id"],
            report_type="FINAL_PILOT_REPORT",
        )

        assert report["id"] is not None
        assert report["go_no_go_recommendation"] == GoNoGoRecommendation.GO.value
        assert "Zero production machine batch interruptions observed" in report["executive_summary"]
        assert report["metrics_summary"]["accuracy_percentage"] >= 75.0
        assert report["metrics_summary"]["batch_disruptions_count"] == 0


# =============================================================================
# TEST 14: PAUSE & COMPLETION LIFECYCLE
# =============================================================================

def test_pilot_pause_and_completion_lifecycle(app, pilot_data):
    """Test 14: Verifies pausing and completing an active pilot program."""
    with app.app_context():
        pilot = PilotService.list_pilots(pilot_data["org_id"], limit=1)[0]
        
        # Pause
        paused = PilotService.pause_pilot(pilot["id"], pilot_data["org_id"], pilot_data["user_id"])
        assert paused["status"] == PilotLifecycleStatus.PAUSED.value

        # Complete
        completed = PilotService.complete_pilot(pilot["id"], pilot_data["org_id"], pilot_data["user_id"])
        assert completed["status"] == PilotLifecycleStatus.COMPLETED.value
        assert completed["completed_at"] is not None


# =============================================================================
# TEST 15: REST API ENDPOINTS INTEGRATION
# =============================================================================

def test_pilot_rest_api_endpoints(app, client, pilot_data):
    """Test 15: Full REST API verification (/api/v1/pilots endpoints with auth headers)."""
    token = get_auth_token(client, "manager@getzpharma.com", "Manager@123")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # 1. POST /api/v1/pilots (Create)
    create_payload = {
        "site_id": pilot_data["site_a1_id"],
        "pilot_name": "API REST Test Pilot",
        "description": "Created via authenticated REST API endpoint.",
        "monitoring_mode": "SHADOW",
    }
    res = client.post("/api/v1/pilots", json=create_payload, headers=headers)
    assert res.status_code == 201
    pilot_id = res.get_json()["id"]

    # 2. GET /api/v1/pilots
    res = client.get("/api/v1/pilots", headers=headers)
    assert res.status_code == 200
    assert any(p["id"] == pilot_id for p in res.get_json())

    # 3. GET /api/v1/pilots/:id
    res = client.get(f"/api/v1/pilots/{pilot_id}", headers=headers)
    assert res.status_code == 200
    data = res.get_json()
    assert data["pilot_name"] == "API REST Test Pilot"
    assert len(data["readiness_checks"]) >= 15

    # 4. POST /api/v1/pilots/:id/equipment
    res = client.post(
        f"/api/v1/pilots/{pilot_id}/equipment",
        json={"machine_ids": [pilot_data["machine_id"]], "monitoring_mode": "SHADOW"},
        headers=headers,
    )
    assert res.status_code == 200

    # 5. POST /api/v1/pilots/:id/readiness-review
    res = client.post(f"/api/v1/pilots/{pilot_id}/readiness-review", headers=headers)
    assert res.status_code == 200
    assert "readiness_percentage" in res.get_json()

    # 6. POST /api/v1/pilots/:id/activate (Should be blocked without approvals!)
    res = client.post(f"/api/v1/pilots/{pilot_id}/activate", headers=headers)
    assert res.status_code == 403
    assert res.get_json()["code"] == "APPROVAL_REQUIRED"

    # 7. POST /api/v1/pilots/:id/approve (Submit Engineering + Security Approvals)
    res = client.post(
        f"/api/v1/pilots/{pilot_id}/approve",
        json={"approval_type": "ENGINEERING", "decision": "APPROVED", "comments": "Signed off via API"},
        headers=headers,
    )
    assert res.status_code == 201

    res = client.post(
        f"/api/v1/pilots/{pilot_id}/approve",
        json={"approval_type": "IT_OT_SECURITY", "decision": "APPROVED", "comments": "Security signed off via API"},
        headers=headers,
    )
    assert res.status_code == 201

    # 8. POST /api/v1/pilots/:id/activate (Should now succeed!)
    res = client.post(f"/api/v1/pilots/{pilot_id}/activate", headers=headers)
    assert res.status_code == 200
    assert res.get_json()["status"] == "ACTIVE"

    # 9. POST /api/v1/pilots/:id/feedback
    fb_payload = {
        "diagnostic_session_id": pilot_data["diagnostic_session_id"],
        "assessment": "ACCURATE",
        "verified_root_cause": "Verified bearing wear",
        "comments": "Rest API feedback test",
    }
    res = client.post(f"/api/v1/pilots/{pilot_id}/feedback", json=fb_payload, headers=headers)
    assert res.status_code == 201

    # 10. GET /api/v1/pilots/:id/metrics
    res = client.get(f"/api/v1/pilots/{pilot_id}/metrics", headers=headers)
    assert res.status_code == 200
    assert res.get_json()["total_feedback_submissions"] >= 1

    # 11. POST /api/v1/pilots/:id/report
    res = client.post(f"/api/v1/pilots/{pilot_id}/report", json={"report_type": "FINAL_PILOT_REPORT"}, headers=headers)
    assert res.status_code == 201
    assert "go_no_go_recommendation" in res.get_json()

