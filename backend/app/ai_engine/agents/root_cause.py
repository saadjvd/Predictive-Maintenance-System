import time
import uuid
from typing import Dict, Any, List
from app.ai_engine.schemas.diagnostic_state import DiagnosticState, RootCauseHypothesis, RetrievedEvidenceItem
from app.ai_engine.tools.maintenance_tools import MaintenanceTools
from app.ai_engine.tools.document_tools import DocumentTools
from app.models.equipment import Machine


class RootCauseAnalysisAgent:
    """Agent 4: Synthesizes telemetry anomalies, verified failure history, and RAG technical knowledge."""

    NAME = "ROOT_CAUSE_ANALYSIS_AGENT"

    @classmethod
    def execute(cls, state: DiagnosticState) -> DiagnosticState:
        t0 = time.time()
        org_id = state.organization_id
        mach_id = state.machine_id

        machine = Machine.query.filter_by(id=mach_id, organization_id=org_id).first()
        mach_name = machine.equipment_name if machine else "Pharmaceutical Equipment"
        cat_id = machine.category_id if machine else None

        # 1. Gather observed symptoms
        symptoms = []
        if state.condition.affected_signals:
            symptoms.extend([f"Abnormal {sig}" for sig in state.condition.affected_signals])
        anom_list = state.condition.active_anomalies or state.condition.anomalies or []
        for a in anom_list:
            desc = a.get("description") or a.get("summary") or a.get("anomaly_type") or "Telemetry anomaly"
            symptoms.append(desc)
            if a.get("signal_name"):
                symptoms.append(f"Abnormal {a['signal_name']}")

        if not symptoms:
            symptoms = ["Baseline operational drift", "Vibration and motor thermal inspection"]

        # 2. Retrieve technical documentation via RAG
        retrieved_docs: List[RetrievedEvidenceItem] = DocumentTools.search_technical_documentation(
            organization_id=org_id,
            machine_name=mach_name,
            category_id=cat_id,
            symptoms=symptoms,
            top_k=3,
        )
        state.retrieved_documents = retrieved_docs

        # 3. Retrieve confirmed historical root causes from CMMS / FailureRecord logs
        historical_causes = MaintenanceTools.get_confirmed_root_causes(org_id, mach_id)

        # 4. Formulate evidence-backed hypotheses
        hypotheses: List[RootCauseHypothesis] = []

        # Analyze primary signal issues
        has_vibration_issue = any("vibrat" in s.lower() for s in symptoms)
        has_thermal_issue = any("temp" in s.lower() or "overheat" in s.lower() for s in symptoms)
        has_pressure_issue = any("press" in s.lower() or "vacuum" in s.lower() for s in symptoms)

        cited_titles = [d.title for d in retrieved_docs]

        if has_vibration_issue:
            hypotheses.append(
                RootCauseHypothesis(
                    hypothesis_id=str(uuid.uuid4())[:8],
                    suspected_cause="Drive Motor Bearing Raceway Fatigue or Lubrication Starvation",
                    hypothesis_status="SUPPORTED_HYPOTHESIS",
                    confidence_level="HIGH" if state.prediction.is_available and state.prediction.calibrated_probability and state.prediction.calibrated_probability > 0.4 else "MEDIUM",
                    supporting_observations=symptoms + [f"Condition state: {state.condition.condition_state}"],
                    cited_documents=cited_titles,
                    recommended_verification_steps=[
                        "Inspect bearing housing with acoustic stethoprobe or ultrasound detector.",
                        "Check lubricant grease viscosity and contamination level.",
                        "Verify drive shaft radial and axial runout using dial indicator.",
                    ],
                    uncertainty_description="Requires mechanical physical inspection to confirm raceway spalling versus shaft misalignment.",
                )
            )

        if has_thermal_issue or not hypotheses:
            hypotheses.append(
                RootCauseHypothesis(
                    hypothesis_id=str(uuid.uuid4())[:8],
                    suspected_cause="Motor Thermal Overload due to Excessive Mechanical Drag or Ventilation Obstruction",
                    hypothesis_status="POSSIBLE_CAUSE",
                    confidence_level="MEDIUM",
                    supporting_observations=symptoms,
                    cited_documents=cited_titles,
                    recommended_verification_steps=[
                        "Inspect cooling fan cowl and air filter intake for particulate buildup.",
                        "Measure motor stator winding temperature using calibrated infrared thermometer.",
                        "Verify operating load current against motor nameplate full-load amps (FLA).",
                    ],
                    uncertainty_description="Thermal rise may be influenced by ambient cleanroom HVAC fluctuations.",
                )
            )

        if has_pressure_issue:
            hypotheses.append(
                RootCauseHypothesis(
                    hypothesis_id=str(uuid.uuid4())[:8],
                    suspected_cause="Pneumatic Actuator Supply Pressure Drop or Solenoid Valve Seal Leakage",
                    hypothesis_status="SUPPORTED_HYPOTHESIS",
                    confidence_level="MEDIUM",
                    supporting_observations=symptoms,
                    cited_documents=cited_titles,
                    recommended_verification_steps=[
                        "Perform pressure decay test on pneumatic supply manifold.",
                        "Inspect polyurethane air hoses and quick-disconnect fittings for micro-fractures.",
                    ],
                    uncertainty_description="Pressure fluctuation may originate from central factory compressed air supply.",
                )
            )

        # Integrate verified historical context if available
        if historical_causes:
            prior_cause = historical_causes[0]["root_cause"]
            hypotheses[0].uncertainty_description += f" Note: Historical maintenance log recorded prior confirmed cause: '{prior_cause}'."

        state.hypotheses = hypotheses
        state.agent_executions.append({
            "agent_name": cls.NAME,
            "status": "SUCCESS",
            "execution_time_ms": (time.time() - t0) * 1000.0,
            "summary": f"Formulated {len(hypotheses)} root-cause hypothesis(es). Retrieved {len(retrieved_docs)} technical document citation(s).",
        })

        state.current_stage = "ROOT_CAUSES_IDENTIFIED"
        return state

