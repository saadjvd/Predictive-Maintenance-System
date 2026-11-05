import time
import uuid
from typing import Dict, Any, List
from app.ai_engine.schemas.diagnostic_state import (
    DiagnosticState,
    MaintenanceRecommendationSchema,
    RootCauseHypothesis,
)


class MaintenanceRecommendationAgent:
    """Agent 5: Generates evidence-supported maintenance recommendations requiring human sign-off."""

    NAME = "MAINTENANCE_RECOMMENDATION_AGENT"

    @classmethod
    def execute(cls, state: DiagnosticState) -> DiagnosticState:
        t0 = time.time()
        recommendations: List[MaintenanceRecommendationSchema] = []

        # Derive priority from highest condition severity and predictive risk
        priority = "MEDIUM"
        if state.condition.severity == "CRITICAL" or state.prediction.risk_category in ("HIGH", "CRITICAL"):
            priority = "HIGH" if state.prediction.risk_category == "HIGH" else "CRITICAL"
        elif state.condition.severity == "INFO" and state.prediction.risk_category == "LOW":
            priority = "LOW"

        # Generate recommendation per hypothesis
        for hyp in state.hypotheses:
            if "bearing" in hyp.suspected_cause.lower():
                recommendations.append(
                    MaintenanceRecommendationSchema(
                        recommendation_id=str(uuid.uuid4())[:8],
                        title="Inspect and Lubricate Drive Motor Bearings",
                        suspected_issue=hyp.suspected_cause,
                        recommended_action=(
                            "Schedule visual and ultrasonic vibration inspection of drive motor bearing assembly during an approved maintenance window. "
                            "Inspect seal integrity and replenish OEM-specified synthetic food-grade grease. If raceway spalling is observed, replace bearing assembly."
                        ),
                        priority=priority,
                        component_type="Bearing / Drive Motor",
                        safety_requirements=[
                            "Mandatory Lockout/Tagout (LOTO) of primary 400V disconnect switch.",
                            "Verify zero mechanical energy and zero rotational inertia before removing protective guard.",
                            "Cleanroom Class C / ISO 7 particulate containment gowning.",
                        ],
                        supporting_evidence={
                            "hypothesis": hyp.suspected_cause,
                            "confidence": hyp.confidence_level,
                            "cited_documents": hyp.cited_documents,
                            "calibrated_risk": state.prediction.calibrated_probability,
                        },
                        requires_engineer_approval=True,
                    )
                )

            elif "thermal" in hyp.suspected_cause.lower() or "overheat" in hyp.suspected_cause.lower():
                recommendations.append(
                    MaintenanceRecommendationSchema(
                        recommendation_id=str(uuid.uuid4())[:8],
                        title="Motor Cooling System Inspection & Load Check",
                        suspected_issue=hyp.suspected_cause,
                        recommended_action=(
                            "Inspect drive motor ventilation cowl and air filter for pharmaceutical dust accumulation. "
                            "Perform infrared thermal imaging survey on stator windings and verify motor current draw against nameplate full-load amps."
                        ),
                        priority="MEDIUM",
                        component_type="Main Drive Motor",
                        safety_requirements=[
                            "Allow motor housing to cool below 45°C prior to physical contact.",
                            "Arc-flash safety glasses and voltage-rated gloves for electrical terminal box inspection.",
                            "GMP equipment cleaning logbook entry upon filter maintenance.",
                        ],
                        supporting_evidence={
                            "hypothesis": hyp.suspected_cause,
                            "confidence": hyp.confidence_level,
                            "cited_documents": hyp.cited_documents,
                        },
                        requires_engineer_approval=True,
                    )
                )

            elif "pneumatic" in hyp.suspected_cause.lower() or "pressure" in hyp.suspected_cause.lower():
                recommendations.append(
                    MaintenanceRecommendationSchema(
                        recommendation_id=str(uuid.uuid4())[:8],
                        title="Pneumatic Circuit Pressure Decay & Solenoid Seal Test",
                        suspected_issue=hyp.suspected_cause,
                        recommended_action=(
                            "Isolate pneumatic circuit and conduct 15-minute pressure decay test. "
                            "Inspect quick-release fittings and replace worn solenoid valve O-rings."
                        ),
                        priority="MEDIUM",
                        component_type="Pneumatics / Solenoid Valve Block",
                        safety_requirements=[
                            "Depressurize pneumatic accumulator and lock manual air shutoff valve in exhaust position.",
                            "Wear safety eye protection during pneumatic fitting inspection.",
                        ],
                        supporting_evidence={
                            "hypothesis": hyp.suspected_cause,
                            "confidence": hyp.confidence_level,
                            "cited_documents": hyp.cited_documents,
                        },
                        requires_engineer_approval=True,
                    )
                )

        if not recommendations:
            recommendations.append(
                MaintenanceRecommendationSchema(
                    recommendation_id=str(uuid.uuid4())[:8],
                    title="Routine Operational Baseline Verification",
                    suspected_issue="Minor telemetry baseline drift",
                    recommended_action="Conduct routine visual walkaround during shift changeover to ensure nominal lubrication and cleanliness.",
                    priority="LOW",
                    component_type="General Equipment",
                    safety_requirements=["Standard cleanroom PPE and visual observation."],
                    supporting_evidence={"summary": "Operating telemetry within acceptable operational boundaries."},
                    requires_engineer_approval=True,
                )
            )

        state.recommendations = recommendations
        state.agent_executions.append({
            "agent_name": cls.NAME,
            "status": "SUCCESS",
            "execution_time_ms": (time.time() - t0) * 1000.0,
            "summary": f"Formulated {len(recommendations)} actionable maintenance recommendation(s).",
        })

        state.current_stage = "RECOMMENDATIONS_GENERATED"
        return state

