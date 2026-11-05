"""PharmaPredict AI — Pilot Module Repositories.

Provides multi-tenant scoped database queries and operations for factory pilots.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from app.extensions import db
from app.models.pilot import (
    FactoryPilot,
    PilotEquipment,
    PilotApproval,
    PilotReadinessCheck,
    PilotEngineerFeedback,
    PilotModelEvaluation,
    PilotAgentEvaluation,
    PilotReport,
    PilotLifecycleStatus,
    MonitoringMode,
)
from app.models.equipment import Machine


class PilotRepository:
    """Multi-tenant scoped repository for Factory Pilots."""

    @staticmethod
    def get_by_id(pilot_id: str, organization_id: str) -> Optional[FactoryPilot]:
        return FactoryPilot.query.filter_by(id=pilot_id, organization_id=organization_id).first()

    @staticmethod
    def list_pilots(
        organization_id: str,
        site_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[FactoryPilot]:
        query = FactoryPilot.query.filter_by(organization_id=organization_id)
        if site_id:
            query = query.filter_by(site_id=site_id)
        if status:
            query = query.filter_by(status=status)
        return query.order_by(FactoryPilot.created_at.desc()).offset(offset).limit(limit).all()

    @staticmethod
    def create(
        organization_id: str,
        site_id: str,
        pilot_name: str,
        description: Optional[str] = None,
        objectives: Optional[str] = None,
        monitoring_mode: str = MonitoringMode.SHADOW.value,
        planned_start_date: Optional[datetime] = None,
        planned_end_date: Optional[datetime] = None,
        evaluation_criteria: Optional[Dict[str, Any]] = None,
        target_kpis: Optional[Dict[str, Any]] = None,
        responsible_engineer_id: Optional[str] = None,
        created_by_id: Optional[str] = None,
    ) -> FactoryPilot:
        pilot = FactoryPilot(
            organization_id=organization_id,
            site_id=site_id,
            pilot_name=pilot_name,
            description=description,
            objectives=objectives,
            status=PilotLifecycleStatus.DRAFT.value,
            monitoring_mode=monitoring_mode,
            planned_start_date=planned_start_date,
            planned_end_date=planned_end_date,
            evaluation_criteria=evaluation_criteria or {},
            target_kpis=target_kpis or {},
            responsible_engineer_id=responsible_engineer_id,
            created_by_id=created_by_id,
        )
        db.session.add(pilot)
        db.session.commit()
        return pilot

    @staticmethod
    def update(pilot: FactoryPilot, **kwargs) -> FactoryPilot:
        for key, value in kwargs.items():
            if hasattr(pilot, key) and value is not None:
                setattr(pilot, key, value)
        pilot.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        return pilot

    @staticmethod
    def add_equipment(pilot_id: str, machine_id: str, monitoring_mode: str = "SHADOW") -> PilotEquipment:
        existing = PilotEquipment.query.filter_by(pilot_id=pilot_id, machine_id=machine_id).first()
        if existing:
            existing.is_active = True
            existing.monitoring_mode = monitoring_mode
            db.session.commit()
            return existing

        link = PilotEquipment(
            pilot_id=pilot_id,
            machine_id=machine_id,
            monitoring_mode=monitoring_mode,
            readiness_status="NOT_EVALUATED",
            is_active=True,
        )
        db.session.add(link)
        db.session.commit()
        return link

    @staticmethod
    def get_equipment_list(pilot_id: str) -> List[PilotEquipment]:
        return PilotEquipment.query.filter_by(pilot_id=pilot_id, is_active=True).all()

    @staticmethod
    def record_approval(
        pilot_id: str,
        approver_id: str,
        approval_type: str,
        decision: str,
        comments: Optional[str],
        signature_hash: str,
    ) -> PilotApproval:
        approval = PilotApproval(
            pilot_id=pilot_id,
            approver_id=approver_id,
            approval_type=approval_type,
            decision=decision,
            comments=comments,
            signature_hash=signature_hash,
        )
        db.session.add(approval)
        db.session.commit()
        return approval

    @staticmethod
    def get_approvals(pilot_id: str) -> List[PilotApproval]:
        return PilotApproval.query.filter_by(pilot_id=pilot_id).order_by(PilotApproval.signed_at.desc()).all()

    @staticmethod
    def create_readiness_check(
        pilot_id: str,
        check_category: str,
        check_name: str,
        description: str,
        machine_id: Optional[str] = None,
        status: str = "PENDING",
        evidence_summary: Optional[str] = None,
        reviewer_id: Optional[str] = None,
    ) -> PilotReadinessCheck:
        check = PilotReadinessCheck(
            pilot_id=pilot_id,
            machine_id=machine_id,
            check_category=check_category,
            check_name=check_name,
            description=description,
            status=status,
            evidence_summary=evidence_summary,
            reviewer_id=reviewer_id,
            reviewed_at=datetime.now(timezone.utc) if reviewer_id else None,
        )
        db.session.add(check)
        db.session.commit()
        return check

    @staticmethod
    def get_readiness_checks(pilot_id: str, machine_id: Optional[str] = None) -> List[PilotReadinessCheck]:
        query = PilotReadinessCheck.query.filter_by(pilot_id=pilot_id)
        if machine_id:
            query = query.filter_by(machine_id=machine_id)
        return query.all()

    @staticmethod
    def record_feedback(
        pilot_id: str,
        diagnostic_session_id: str,
        engineer_id: str,
        assessment: str,
        anomaly_event_id: Optional[str] = None,
        verified_root_cause: Optional[str] = None,
        inspection_findings: Optional[str] = None,
        action_taken: Optional[str] = None,
        actual_outcome: Optional[str] = None,
        comments: Optional[str] = None,
        false_alarm_flag: bool = False,
        reference_label: str = "UNVERIFIED",
    ) -> PilotEngineerFeedback:
        fb = PilotEngineerFeedback(
            pilot_id=pilot_id,
            diagnostic_session_id=diagnostic_session_id,
            anomaly_event_id=anomaly_event_id,
            engineer_id=engineer_id,
            assessment=assessment,
            verified_root_cause=verified_root_cause,
            inspection_findings=inspection_findings,
            action_taken=action_taken,
            actual_outcome=actual_outcome,
            comments=comments,
            false_alarm_flag=false_alarm_flag,
            reference_label=reference_label,
        )
        db.session.add(fb)
        db.session.commit()
        return fb

    @staticmethod
    def get_feedback_list(pilot_id: str) -> List[PilotEngineerFeedback]:
        return PilotEngineerFeedback.query.filter_by(pilot_id=pilot_id).order_by(PilotEngineerFeedback.feedback_timestamp.desc()).all()

    @staticmethod
    def record_model_evaluation(
        pilot_id: str,
        machine_id: str,
        model_name: str,
        model_version: str,
        metrics: Dict[str, Any],
        status: str = "CANDIDATE",
        evaluation_type: str = "OFFLINE_VALIDATION",
        previous_model_version: Optional[str] = None,
        evaluated_by_id: Optional[str] = None,
        approved_by_id: Optional[str] = None,
    ) -> PilotModelEvaluation:
        eval_record = PilotModelEvaluation(
            pilot_id=pilot_id,
            machine_id=machine_id,
            model_name=model_name,
            model_version=model_version,
            metrics=metrics,
            status=status,
            evaluation_type=evaluation_type,
            previous_model_version=previous_model_version,
            evaluated_by_id=evaluated_by_id,
            approved_by_id=approved_by_id,
        )
        db.session.add(eval_record)
        db.session.commit()
        return eval_record

    @staticmethod
    def get_model_evaluations(pilot_id: str) -> List[PilotModelEvaluation]:
        return PilotModelEvaluation.query.filter_by(pilot_id=pilot_id).order_by(PilotModelEvaluation.evaluated_at.desc()).all()

    @staticmethod
    def record_agent_evaluation(
        pilot_id: str,
        diagnostic_session_id: str,
        agent_name: str,
        routing_correctness: float = 1.0,
        tool_selection_accuracy: float = 1.0,
        evidence_completeness: float = 1.0,
        hypothesis_relevance: float = 1.0,
        safety_compliance_score: float = 1.0,
        evaluation_notes: Optional[str] = None,
    ) -> PilotAgentEvaluation:
        eval_record = PilotAgentEvaluation(
            pilot_id=pilot_id,
            diagnostic_session_id=diagnostic_session_id,
            agent_name=agent_name,
            routing_correctness=routing_correctness,
            tool_selection_accuracy=tool_selection_accuracy,
            evidence_completeness=evidence_completeness,
            hypothesis_relevance=hypothesis_relevance,
            safety_compliance_score=safety_compliance_score,
            evaluation_notes=evaluation_notes,
        )
        db.session.add(eval_record)
        db.session.commit()
        return eval_record

    @staticmethod
    def get_agent_evaluations(pilot_id: str) -> List[PilotAgentEvaluation]:
        return PilotAgentEvaluation.query.filter_by(pilot_id=pilot_id).order_by(PilotAgentEvaluation.evaluated_at.desc()).all()

    @staticmethod
    def create_report(
        pilot_id: str,
        report_type: str,
        executive_summary: str,
        metrics_summary: Dict[str, Any],
        go_no_go_recommendation: str,
        generated_by_id: str,
        findings_and_deviations: Optional[str] = None,
        limitations_and_disclaimers: Optional[str] = None,
    ) -> PilotReport:
        report = PilotReport(
            pilot_id=pilot_id,
            report_type=report_type,
            executive_summary=executive_summary,
            metrics_summary=metrics_summary,
            go_no_go_recommendation=go_no_go_recommendation,
            generated_by_id=generated_by_id,
            findings_and_deviations=findings_and_deviations,
            limitations_and_disclaimers=limitations_and_disclaimers,
        )
        db.session.add(report)
        db.session.commit()
        return report

    @staticmethod
    def get_reports(pilot_id: str) -> List[PilotReport]:
        return PilotReport.query.filter_by(pilot_id=pilot_id).order_by(PilotReport.generated_at.desc()).all()

