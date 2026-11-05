from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime, timezone, timedelta
import numpy as np
import pandas as pd
from app.models.prediction import FailureVerificationStatus
from app.ml_engine.prediction.predictive_features import PredictiveFeatureExtractor


class PredictiveDatasetBuilder:
    """Builds time-aligned, leak-free supervised datasets for failure risk estimation."""

    @classmethod
    def build_supervised_dataset(
        cls,
        readings_records: List[Dict[str, Any]],
        failure_records: List[Dict[str, Any]],
        prediction_horizon_hours: int = 168,
        observation_step_hours: int = 6,
        feature_window_hours: int = 24,
        baseline_envelopes: Optional[Dict[str, Dict[str, float]]] = None,
        anomaly_records: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[np.ndarray, np.ndarray, List[str], Dict[str, Any]]:
        """
        Builds feature matrix X and label vector y using temporal sliding window.
        
        Args:
            readings_records: List of dicts with 'source_timestamp', 'signal_name', 'normalized_value'
            failure_records: List of dicts with 'failure_started_at', 'verification_status', 'failure_mode_code'
            prediction_horizon_hours: Forecasting window (e.g., 24h, 168h / 7d)
            observation_step_hours: Cadence between historical observation cutoffs
            feature_window_hours: Lookback window behind each observation point
            
        Returns:
            X: 2D numpy array of features (n_samples, n_features)
            y: 1D numpy array of binary labels (0 = no failure within horizon, 1 = failure within horizon)
            feature_names: list of feature names
            metadata: sample counts, time ranges, class balance
        """
        if not readings_records:
            return np.empty((0, 0)), np.empty(0), [], {"error": "No sensor readings available."}

        df_readings = pd.DataFrame(readings_records)
        df_readings["source_timestamp"] = pd.to_datetime(df_readings["source_timestamp"])
        df_readings = df_readings.sort_values("source_timestamp")

        # Filter verified failures (exclude PM, inspection, planned shutdowns)
        valid_failure_times = []
        for fr in failure_records:
            status = fr.get("verification_status")
            if status in (FailureVerificationStatus.CONFIRMED, FailureVerificationStatus.SUSPECTED):
                f_time = fr.get("failure_started_at")
                if isinstance(f_time, str):
                    f_time = datetime.fromisoformat(f_time.replace("Z", "+00:00"))
                if f_time:
                    if f_time.tzinfo is None:
                        f_time = f_time.replace(tzinfo=timezone.utc)
                    valid_failure_times.append(f_time)

        min_time = df_readings["source_timestamp"].min()
        max_time = df_readings["source_timestamp"].max()
        horizon_delta = timedelta(hours=prediction_horizon_hours)
        lookback_delta = timedelta(hours=feature_window_hours)
        step_delta = timedelta(hours=observation_step_hours)

        # Ensure we have enough time range for lookback + horizon
        if (max_time - min_time) < (lookback_delta + timedelta(hours=12)):
            return np.empty((0, 0)), np.empty(0), [], {
                "error": f"Insufficient historical time range: {(max_time - min_time).total_seconds() / 3600:.1f}h. Minimum {feature_window_hours + 12}h required."
            }

        samples: List[Dict[str, float]] = []
        labels: List[int] = []

        # Current sliding cutoff point starts after the first feature window
        current_cutoff = min_time + lookback_delta
        # Stop sliding when cutoff + horizon exceeds max recorded time
        end_cutoff = max_time - timedelta(hours=1)

        while current_cutoff <= end_cutoff:
            window_start = current_cutoff - lookback_delta
            window_df = df_readings[
                (df_readings["source_timestamp"] >= window_start) &
                (df_readings["source_timestamp"] <= current_cutoff)
            ]

            if not window_df.empty:
                # Calculate operating hours up to current_cutoff
                op_hours = (current_cutoff - min_time).total_seconds() / 3600.0

                # Filter anomalies strictly up to current_cutoff (no future leakage!)
                recent_anoms = []
                if anomaly_records:
                    for a in anomaly_records:
                        a_time = a.get("latest_detected_at") or a.get("first_detected_at")
                        if isinstance(a_time, str):
                            a_time = datetime.fromisoformat(a_time.replace("Z", "+00:00"))
                        if a_time and window_start <= a_time <= current_cutoff:
                            recent_anoms.append(a)

                feat_dict = PredictiveFeatureExtractor.extract_window_features(
                    readings_df=window_df,
                    baseline_envelopes=baseline_envelopes,
                    recent_anomalies=recent_anoms,
                    operating_hours=op_hours,
                )

                # Determine label: did a verified failure occur in (current_cutoff, current_cutoff + horizon]?
                horizon_end = current_cutoff + horizon_delta
                has_failure = any(current_cutoff < ft <= horizon_end for ft in valid_failure_times)

                samples.append(feat_dict)
                labels.append(1 if has_failure else 0)

            current_cutoff += step_delta

        if not samples:
            return np.empty((0, 0)), np.empty(0), [], {"error": "Could not extract valid samples from time series."}

        # Consolidate feature schema across all samples
        all_feature_keys = sorted(list({k for s in samples for k in s.keys()}))
        X = np.zeros((len(samples), len(all_feature_keys)), dtype=np.float64)
        for i, s in enumerate(samples):
            for j, k in enumerate(all_feature_keys):
                X[i, j] = float(s.get(k, 0.0))

        y = np.array(labels, dtype=np.int32)
        pos_count = int(np.sum(y == 1))
        neg_count = int(np.sum(y == 0))

        metadata = {
            "sample_count": len(samples),
            "positive_sample_count": pos_count,
            "negative_sample_count": neg_count,
            "feature_count": len(all_feature_keys),
            "time_window_start": min_time.isoformat(),
            "time_window_end": max_time.isoformat(),
            "prediction_horizon_hours": prediction_horizon_hours,
            "class_balance_positive_pct": round((pos_count / len(samples)) * 100.0, 2) if len(samples) > 0 else 0.0,
        }

        return X, y, all_feature_keys, metadata

    @classmethod
    def temporal_split(
        cls,
        X: np.ndarray,
        y: np.ndarray,
        train_ratio: float = 0.75,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        Splits dataset temporally without shuffling to prevent future data leakage.
        Train on earlier samples, validate on later samples.
        """
        n_samples = len(X)
        split_idx = int(n_samples * train_ratio)

        X_train, X_val = X[:split_idx], X[split_idx:]
        y_train, y_val = y[:split_idx], y[split_idx:]

        return X_train, y_train, X_val, y_val

    # Alias for split_temporal
    split_temporal = temporal_split

