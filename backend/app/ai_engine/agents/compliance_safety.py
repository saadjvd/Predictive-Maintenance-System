import time
from typing import Dict, Any, List
from app.ai_engine.schemas.diagnostic_state import (
    DiagnosticState,
    ComplianceSafetyAssessment,
    MaintenanceRecommendationSchema,
)


class ComplianceSafetyAgent:
    """Agent 6: Compliance & Safety Agent.
    
    Applies deterministic safety rules, LOTO requirements, cleanroom GMP protocols,
    and enforces strict read-only industrial boundaries.
    """

    NAME = "COMPLIANCE_SAFETY_AGENT"

    @classmethod
    def execute(cls, state: DiagnosticState) -> DiagnosticState:
        t0 = time.time()
        safety_notes: List[str] = []
        blocked_reasons: List[str] = []
        loto_required = False
        electrical_isolation_required = False
        cleanroom_ppe_required = False
        gmp_change_control_required = False

        # Read-only industrial boundary check
        forbidden_action_keywords = [
            "start motor", "stop plc", "write tag", "modify setpoint", 
            "actuate cylinder", "override interlock", "bypass safety",
            "remote start", "remote reset"
        ]

        # Audit each recommendation
        overall_blocked = False
        requires_extra_approval = False

        for rec in state.recommendations:
            rec_text = f"{rec.title} {rec.recommended_action}".lower()

            # Rule 1: Zero-tolerance check for direct machine control commands
            if any(keyword in rec_text for keyword in forbidden_action_keywords):
                rec.compliance_state = "BLOCKED"
                blocked_reasons.append(
                    f"Recommendation '{rec.title}' proposes direct machine manipulation or automated write, violating strict read-only safety boundary."
                )
                overall_blocked = True
                continue

            # Rule 2: Mechanical intervention requires LOTO & Zero-Energy State
            if any(k in rec_text for k in ["bearing", "motor", "shaft", "belt", "punch", "cutter", "cylinder", "jaw"]):
                loto_required = True
                if not any("loto" in req.lower() or "lockout" in req.lower() for req in rec.safety_requirements):
                    rec.safety_requirements.append("Mandatory Lockout/Tagout (LOTO) of primary energy disconnects (OSHA 1910.147).")
                if not any("zero" in req.lower() for req in rec.safety_requirements):
                    rec.safety_requirements.append("Verify zero residual mechanical, hydraulic, and kinetic energy before accessing moving assemblies.")

            # Rule 3: Electrical inspections require electrical isolation & Arc-Flash PPE
            if any(k in rec_text for k in ["electrical", "wiring", "terminal", "stator", "drive", "inverter", "400v", "230v"]):
                electrical_isolation_required = True
                if not any("arc-flash" in req.lower() or "voltage" in req.lower() for req in rec.safety_requirements):
                    rec.safety_requirements.append("Qualified electrical personnel only; NFPA 70E Arc-Flash PPE & verified zero voltage test required.")

            # Rule 4: Cleanroom & GMP Area Compliance
            cleanroom_ppe_required = True
            if not any("cleanroom" in req.lower() or "gmp" in req.lower() or "sterile" in req.lower() for req in rec.safety_requirements):
                rec.safety_requirements.append("Cleanroom Class C / ISO 7 protocol: Complete sanitization of tools with 70% IPA and sterile gowning.")

            # Rule 5: Part replacement / modification requires GMP Change Control
            if any(k in rec_text for k in ["replace", "retrofit", "modify", "recalibrate", "reconfigure"]):
                gmp_change_control_required = True
                requires_extra_approval = True
                rec.safety_requirements.append("GMP Change Control evaluation required prior to permanent component replacement (21 CFR Part 211).")

            # Check recommendation approval requirement
            rec.requires_engineer_approval = True
            rec.compliance_state = "ALLOWED_FOR_REVIEW"

        # General safety notes
        if loto_required:
            safety_notes.append("LOTO mandatory: Mechanical or drive components require physical energy isolation and padlock verification.")
        if electrical_isolation_required:
            safety_notes.append("Electrical safety: Ensure NFPA 70E compliance and calibrated multi-meter verification.")
        if cleanroom_ppe_required:
            safety_notes.append("Cleanroom environmental control: Contain particulate generation and record entry in GMP equipment logbook.")
        if gmp_change_control_required:
            safety_notes.append("Regulatory compliance: Component change or calibration requires Quality Assurance change control sign-off.")

        # Determine overall state
        if overall_blocked:
            comp_state = "BLOCKED"
        elif requires_extra_approval or state.condition.severity == "CRITICAL":
            comp_state = "REQUIRES_ADDITIONAL_APPROVAL"
        else:
            comp_state = "ALLOWED_FOR_REVIEW"

        duration = time.time() - t0
        state.compliance = ComplianceSafetyAssessment(
            compliance_state=comp_state,
            deterministic_checks_passed=(not overall_blocked),
            loto_required=loto_required,
            electrical_isolation_required=electrical_isolation_required,
            cleanroom_ppe_required=cleanroom_ppe_required,
            gmp_change_control_required=gmp_change_control_required,
            safety_notes=safety_notes,
            blocked_reasons=blocked_reasons,
        )

        state.agent_executions.append({
            "agent_name": cls.NAME,
            "status": "COMPLETED",
            "duration_ms": round(duration * 1000, 2),
            "summary": f"Compliance state: {comp_state}. Blocked: {len(blocked_reasons)} items. LOTO required: {loto_required}.",
            "details": {
                "compliance_state": comp_state,
                "loto_required": loto_required,
                "cleanroom_ppe": cleanroom_ppe_required,
                "blocked_count": len(blocked_reasons),
            }
        })
        return state

