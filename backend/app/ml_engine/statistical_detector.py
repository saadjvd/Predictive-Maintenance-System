import math
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone


class StatisticalAnomalyResult:
    """Outcome of statistical anomaly detection check for a single reading."""
    def __init__(
        self,
        is_anomalous: bool,
        severity: str,
        detection_method: str,
        deviation_score: float,
        expected_value: float,
        observed_value: float,
        summary: str,
        evidence: Dict[str, Any],
    ):
        self.is_anomalous = is_anomalous
        self.severity = severity
        self.detection_method = detection_method
        self.deviation_score = deviation_score
        self.expected_value = expected_value
        self.observed_value = observed_value
        self.summary = summary
        self.evidence = evidence

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_anomalous": self.is_anomalous,
            "severity": self.severity,
            "detection_method": self.detection_method,
            "deviation_score": round(self.deviation_score, 4),
            "expected_value": round(self.expected_value, 4),
            "observed_value": round(self.observed_value, 4),
            "summary": self.summary,
            "evidence": self.evidence,
        }


class StatisticalAnomalyDetector:
    """Deterministic, explainable statistical detector using approved baseline envelopes."""

    @classmethod
    def evaluate_measurement(
        cls,
        observed_value: float,
        baseline_stats: Dict[str, Any],
        signal_name: str,
        unit: str = "",
        zscore_threshold: float = 3.0,
        mad_threshold: float = 3.5,
    ) -> Optional[StatisticalAnomalyResult]:
        """Assess observed value against baseline statistics via Z-Score, MAD, and Percentiles."""
        if observed_value is None or not baseline_stats:
            return None

        mean = baseline_stats.get("mean")
        std = baseline_stats.get("std", 0.0)
        median = baseline_stats.get("median", mean)
        mad = baseline_stats.get("mad", std)
        min_b = baseline_stats.get("min", -float("inf"))
        max_b = baseline_stats.get("max", float("inf"))
        p5 = baseline_stats.get("p5", min_b)
        p95 = baseline_stats.get("p95", max_b)

        # 1. Z-Score Deviation
        z_score = 0.0
        if std and std > 1e-6:
            z_score = abs(observed_value - mean) / std

        # 2. Robust MAD Deviation
        mad_score = 0.0
        if mad and mad > 1e-6:
            # Scale factor 0.6745 aligns MAD with standard normal distribution
            mad_score = 0.6745 * abs(observed_value - median) / mad

        # Determine anomaly
        is_anom = False
        method = "BASELINE_STATISTICAL"
        sev = "INFO"
        score = max(z_score, mad_score)

        if z_score >= zscore_threshold * 1.5 or mad_score >= mad_threshold * 1.5:
            is_anom = True
            sev = "CRITICAL"
            method = "ZSCORE_EXTREME" if z_score > mad_score else "MAD_EXTREME"
        elif z_score >= zscore_threshold or mad_score >= mad_threshold:
            is_anom = True
            sev = "WARNING"
            method = "ZSCORE_ELEVATED" if z_score > mad_score else "MAD_ELEVATED"
        elif (observed_value < p5 or observed_value > p95) and score >= 2.0:
            is_anom = True
            sev = "INFO"
            method = "PERCENTILE_BOUNDARY"

        if not is_anom:
            return None

        unit_str = f" {unit}" if unit else ""
        direction = "elevated above" if observed_value > (mean or median) else "depressed below"
        summary = (
            f"{signal_name} observed at {observed_value:.2f}{unit_str} is {direction} "
            f"approved baseline mean ({mean:.2f}{unit_str}) by {score:.2f} sigma."
        )

        return StatisticalAnomalyResult(
            is_anomalous=True,
            severity=sev,
            detection_method=method,
            deviation_score=score,
            expected_value=mean if mean is not None else median,
            observed_value=observed_value,
            summary=summary,
            evidence={
                "z_score": round(z_score, 2),
                "mad_score": round(mad_score, 2),
                "baseline_mean": mean,
                "baseline_median": median,
                "baseline_std": std,
                "baseline_p5": p5,
                "baseline_p95": p95,
            },
        )

