from typing import Dict, Any, List, Optional
from app.models.condition import (
    AnomalySeverity,
    ConditionClassification,
    OperatingState,
    QualityState,
)
from app.ml_engine.statistical_detector import StatisticalAnomalyResult
from app.ml_engine.isolation_forest_detector import IsolationForestResult


class AnomalyDecision:
    """Unified anomaly decision synthesized from data quality, context, statistical, and ML checks."""
    def __init__(
        self,
        should_alert: bool,
        severity: str,
        detection_method: str,
        condition_state: str,
        summary: str,
        affected_signals: List[str],
        anomaly_score: float,
        evidence_items: List[Dict[str, Any]],
        data_quality_issues: List[str],
    ):
        self.should_alert = should_alert
        self.severity = severity
        self.detection_method = detection_method
        self.condition_state = condition_state
        self.summary = summary
        self.affected_signals = affected_signals
        self.anomaly_score = anomaly_score
        self.evidence_items = evidence_items
        self.data_quality_issues = data_quality_issues

    def to_dict(self) -> Dict[str, Any]:
        return {
            "should_alert": self.should_alert,
            "severity": self.severity,
            "detection_method": self.detection_method,
            "condition_state": self.condition_state,
            "summary": self.summary,
            "affected_signals": self.affected_signals,
            "anomaly_score": round(self.anomaly_score, 4),
            "evidence_items": self.evidence_items,
            "data_quality_issues": self.data_quality_issues,
        }


class AnomalyDecisionEngine:
    """Synthesizes all condition monitoring checks into explainable actionable decisions."""

    @classmethod
    def evaluate(
        cls,
        data_quality_state: str,
        data_quality_issues: List[Dict[str, Any]],
        operating_state: str,
        statistical_results: List[StatisticalAnomalyResult],
        ml_result: Optional[IsolationForestResult] = None,
    ) -> AnomalyDecision:
        """Evaluates multivariate condition and returns unified anomaly decision."""
        issue_names = [iss.get("issue_type", "UNKNOWN") for iss in data_quality_issues]

        # 1. Check Data Quality Gate
        if data_quality_state in (QualityState.BAD, QualityState.MISSING, QualityState.STALE):
            return AnomalyDecision(
                should_alert=False,
                severity=AnomalySeverity.INFO,
                detection_method="DATA_QUALITY_SUPPRESSION",
                condition_state=ConditionClassification.MONITORING_UNAVAILABLE,
                summary=f"Sensor data quality degraded ({data_quality_state}). Operational anomaly alarms suppressed to prevent false alarms.",
                affected_signals=[iss.get("signal_name", "all") for iss in data_quality_issues if "signal_name" in iss],
                anomaly_score=0.0,
                evidence_items=[{"source": "data_quality", "issues": issue_names}],
                data_quality_issues=issue_names,
            )

        # 2. Operating State Context Filtering
        # If machine is IDLE or SHUTDOWN, running-baseline threshold breaches are expected or non-critical
        is_idle_or_shutdown = operating_state in (OperatingState.IDLE, OperatingState.SHUTDOWN)

        # 3. Analyze Statistical Anomalies
        anomalous_stats = [r for r in statistical_results if r.is_anomalous]
        stat_criticals = [r for r in anomalous_stats if r.severity == AnomalySeverity.CRITICAL]
        stat_warnings = [r for r in anomalous_stats if r.severity == AnomalySeverity.WARNING]

        # 4. Analyze ML Anomaly Result
        ml_is_anom = ml_result.is_anomalous if ml_result else False
        ml_sev = ml_result.severity if ml_result else AnomalySeverity.INFO
        ml_score = ml_result.anomaly_score if ml_result else 0.0

        # Build list of affected signals and evidence items
        affected_signals: List[str] = []
        evidence_items: List[Dict[str, Any]] = []

        for st in anomalous_stats:
            sig = st.evidence.get("signal_name")
            if sig and sig not in affected_signals:
                affected_signals.append(sig)
            evidence_items.append(st.to_dict())

        if ml_is_anom and ml_result:
            for s in ml_result.top_contributing_signals:
                if s not in affected_signals:
                    affected_signals.append(s)
            evidence_items.append({
                "detection_method": "ISOLATION_FOREST",
                "details": ml_result.to_dict(),
            })

        # Calculate composite anomaly score
        stat_max_dev = max([r.deviation_score for r in statistical_results], default=0.0)
        # Normalize deviation to composite 0.0 - 1.0 range
        composite_score = max(min(stat_max_dev / 6.0, 1.0), ml_score)

        # 5. Determine Overall Severity & Method
        should_alert = False
        final_sev = AnomalySeverity.INFO
        method = "NORMAL"
        cond_state = ConditionClassification.NORMAL

        if stat_criticals or (ml_sev == AnomalySeverity.CRITICAL and len(stat_warnings) >= 1):
            should_alert = not is_idle_or_shutdown
            final_sev = AnomalySeverity.CRITICAL
            cond_state = ConditionClassification.CRITICAL
            method = "HYBRID_CRITICAL" if ml_is_anom and stat_criticals else ("STATISTICAL_CRITICAL" if stat_criticals else "ML_CRITICAL")
            summary = (
                f"Critical equipment condition detected during {operating_state} state: "
                f"{len(stat_criticals)} critical statistical violation(s) across {', '.join(affected_signals[:3])}."
            )
        elif stat_warnings or ml_is_anom:
            should_alert = not is_idle_or_shutdown
            final_sev = AnomalySeverity.WARNING
            cond_state = ConditionClassification.ATTENTION
            method = "HYBRID_WARNING" if ml_is_anom and stat_warnings else ("STATISTICAL_WARNING" if stat_warnings else "ML_ISOLATION_FOREST")
            summary = (
                f"Equipment behavioral deviation detected in {operating_state} state. "
                f"Signals exhibiting anomalies: {', '.join(affected_signals[:3])}."
            )
        elif anomalous_stats:
            # INFO only
            should_alert = False
            final_sev = AnomalySeverity.INFO
            cond_state = ConditionClassification.NORMAL
            method = "STATISTICAL_INFO"
            summary = f"Minor statistical deviations observed in {operating_state} state within acceptable operating limits."
        else:
            should_alert = False
            final_sev = AnomalySeverity.INFO
            cond_state = ConditionClassification.NORMAL
            method = "ALL_SIGNALS_NOMINAL"
            summary = f"All observed signals operating within validated baseline parameters ({operating_state} state)."

        if is_idle_or_shutdown and (stat_criticals or stat_warnings or ml_is_anom):
            summary += f" [Note: machine is {operating_state}; operational alert suppressed]."

        return AnomalyDecision(
            should_alert=should_alert,
            severity=final_sev,
            detection_method=method,
            condition_state=cond_state,
            summary=summary,
            affected_signals=affected_signals,
            anomaly_score=composite_score,
            evidence_items=evidence_items,
            data_quality_issues=issue_names,
        )

