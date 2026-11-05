import math
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone, timedelta
import numpy as np
import pandas as pd


class PredictiveFeatureExtractor:
    """Extracts temporal, statistical, baseline-deviation, and operational predictive features."""

    @classmethod
    def calculate_trend_slope(cls, timestamps: List[float], values: List[float]) -> float:
        """Calculates linear slope (delta per hour) over time series."""
        if len(values) < 2:
            return 0.0
        try:
            x = np.array(timestamps, dtype=np.float64)
            y = np.array(values, dtype=np.float64)
            # Normalize x to hours from start
            x_hours = (x - x[0]) / 3600.0
            if np.max(x_hours) - np.min(x_hours) < 1e-6:
                return 0.0
            slope, _ = np.polyfit(x_hours, y, 1)
            return float(slope)
        except Exception:
            return 0.0

    @classmethod
    def extract_window_features(
        cls,
        readings_df: pd.DataFrame,
        baseline_envelopes: Optional[Dict[str, Dict[str, float]]] = None,
        recent_anomalies: Optional[List[Dict[str, Any]]] = None,
        operating_hours: float = 0.0,
    ) -> Dict[str, float]:
        """
        Extracts predictive features from a window of sensor readings.
        readings_df must contain ['source_timestamp', 'signal_name', 'normalized_value'].
        Returns flat dict of named features suitable for ML models.
        """
        features: Dict[str, float] = {}
        baseline_envelopes = baseline_envelopes or {}

        if readings_df.empty or "signal_name" not in readings_df.columns:
            features["operational_hours"] = float(operating_hours)
            features["recent_anomaly_count"] = float(len(recent_anomalies or []))
            return features

        # Ensure numeric values and datetime index
        df = readings_df.copy()
        df["normalized_value"] = pd.to_numeric(df["normalized_value"], errors="coerce")
        df = df.dropna(subset=["normalized_value"])
        if df.empty:
            features["operational_hours"] = float(operating_hours)
            features["recent_anomaly_count"] = float(len(recent_anomalies or []))
            return features

        df["source_timestamp"] = pd.to_datetime(df["source_timestamp"])
        df = df.sort_values("source_timestamp")

        # Group by signal name to compute per-signal statistical & trend features
        signals = df["signal_name"].unique()
        for sig in signals:
            sig_df = df[df["signal_name"] == sig]
            vals = sig_df["normalized_value"].values
            ts = sig_df["source_timestamp"].astype("int64").values // 10**9  # unix epoch in seconds

            if len(vals) == 0:
                continue

            # Basic statistics
            mean_val = float(np.mean(vals))
            max_val = float(np.max(vals))
            min_val = float(np.min(vals))
            std_val = float(np.std(vals)) if len(vals) > 1 else 0.0
            latest_val = float(vals[-1])
            p95_val = float(np.percentile(vals, 95))

            features[f"{sig}__latest"] = latest_val
            features[f"{sig}__mean"] = mean_val
            features[f"{sig}__max"] = max_val
            features[f"{sig}__std"] = std_val
            features[f"{sig}__p95"] = p95_val
            features[f"{sig}__p2p"] = max_val - min_val  # peak to peak

            # Trend slope (rate of change per hour)
            slope = cls.calculate_trend_slope(list(ts), list(vals))
            features[f"{sig}__slope_per_hour"] = slope

            # Deviation from approved baseline
            base = baseline_envelopes.get(sig)
            if base:
                b_mean = base.get("mean", mean_val)
                b_std = base.get("std", 1.0)
                if b_std < 1e-6:
                    b_std = 1.0
                z_dev = abs(latest_val - b_mean) / b_std
                features[f"{sig}__baseline_z_score"] = float(z_dev)
            else:
                features[f"{sig}__baseline_z_score"] = 0.0

        # Cross-signal interaction features where available
        speed_val = features.get("Speed_CPM__latest") or features.get("Rotational Speed__latest") or features.get("ROTATIONAL_SPEED__latest")
        current_val = features.get("Motor Current__latest") or features.get("MOTOR_CURRENT__latest")
        vib_val = features.get("MainDriveMotorVibration__latest") or features.get("Motor Vibration Velocity__latest") or features.get("MOTOR_VIBRATION__latest")

        if speed_val and current_val and speed_val > 1.0:
            features["current_to_speed_ratio"] = float(current_val / speed_val)
        else:
            features["current_to_speed_ratio"] = 0.0

        if speed_val and vib_val and speed_val > 1.0:
            features["vibration_to_speed_ratio"] = float(vib_val / speed_val)
        else:
            features["vibration_to_speed_ratio"] = 0.0

        # Equipment Usage features
        features["operational_hours"] = float(operating_hours)

        # Anomaly history features from Phase 5
        anom_list = recent_anomalies or []
        features["recent_anomaly_count"] = float(len(anom_list))
        critical_anom = sum(1 for a in anom_list if a.get("severity") == "CRITICAL")
        features["recent_critical_anomaly_count"] = float(critical_anom)
        max_anom_score = max([a.get("anomaly_score", 0.0) for a in anom_list], default=0.0)
        features["max_recent_anomaly_score"] = float(max_anom_score)

        return features

    @classmethod
    def align_feature_vector(
        cls,
        extracted_features: Dict[str, float],
        expected_feature_names: List[str],
    ) -> np.ndarray:
        """
        Converts extracted features dict into a 1D numpy array ordered by expected_feature_names.
        Fills missing features with 0.0.
        """
        vector = [float(extracted_features.get(f, 0.0)) for f in expected_feature_names]
        return np.array([vector], dtype=np.float64)

