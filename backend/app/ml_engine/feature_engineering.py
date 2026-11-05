import math
from typing import Dict, Any, List, Tuple, Optional
import numpy as np
import pandas as pd


class FeatureEngineer:
    """Prepares and scales multivariate industrial sensor features for ML anomaly detection."""

    @classmethod
    def build_training_matrix(
        cls,
        readings_records: List[Dict[str, Any]],
        signal_names: List[str],
        window_size: int = 5,
    ) -> Tuple[np.ndarray, List[str], Dict[str, Any]]:
        """
        Converts list of reading dicts (with keys 'timestamp', 'signal_name', 'value')
        into an engineered feature matrix.
        Returns:
            X: numpy array of shape (samples, features)
            feature_names: list of feature column names
            scaling_params: mean & std for standardizing features
        """
        if not readings_records:
            return np.empty((0, 0)), [], {}

        df = pd.DataFrame(readings_records)
        if "timestamp" not in df.columns or "signal_name" not in df.columns or "value" not in df.columns:
            raise ValueError("readings_records must contain 'timestamp', 'signal_name', and 'value'")

        # Ensure valid numeric values and sort by timestamp
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df = df.dropna(subset=["value"])
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.sort_values("timestamp")

        # Pivot to wide format: index=timestamp, columns=signal_name
        wide = df.pivot_table(index="timestamp", columns="signal_name", values="value", aggfunc="last")

        # Ensure all expected signals are present
        for sig in signal_names:
            if sig not in wide.columns:
                wide[sig] = np.nan

        wide = wide[signal_names]
        # Forward-fill then backfill any remaining gaps
        wide = wide.ffill().bfill()
        wide = wide.dropna()

        if len(wide) < 3:
            return np.empty((0, 0)), [], {}

        feature_dfs = [wide.copy()]
        feature_names = list(signal_names)

        # 1. Rolling Mean & Rolling Std (if enough rows)
        if len(wide) >= window_size:
            roll_mean = wide.rolling(window=window_size, min_periods=1).mean()
            roll_mean.columns = [f"{c}_roll_mean" for c in wide.columns]
            feature_dfs.append(roll_mean)
            feature_names.extend(roll_mean.columns)

            roll_std = wide.rolling(window=window_size, min_periods=1).std().fillna(0.0)
            roll_std.columns = [f"{c}_roll_std" for c in wide.columns]
            feature_dfs.append(roll_std)
            feature_names.extend(roll_std.columns)

        # 2. Rate of Change (first difference)
        diff = wide.diff().fillna(0.0)
        diff.columns = [f"{c}_diff" for c in wide.columns]
        feature_dfs.append(diff)
        feature_names.extend(diff.columns)

        full_features = pd.concat(feature_dfs, axis=1)

        # Calculate scaling params
        means = full_features.mean().to_dict()
        stds = full_features.std().replace(0, 1.0).fillna(1.0).to_dict()

        scaling_params = {
            "means": {k: float(v) for k, v in means.items()},
            "stds": {k: float(v) for k, v in stds.items()},
        }

        # Normalize features (Z-standardization)
        normalized = (full_features - full_features.mean()) / full_features.std().replace(0, 1.0).fillna(1.0)
        X = normalized.values

        return X, feature_names, scaling_params

    @classmethod
    def transform_single_vector(
        cls,
        current_values: Dict[str, float],
        feature_names: List[str],
        scaling_params: Dict[str, Any],
        recent_history: Optional[List[Dict[str, float]]] = None,
    ) -> np.ndarray:
        """
        Transforms a current observation of multiple signals into a single feature vector
        matching feature_names and scaled by scaling_params.
        """
        means = scaling_params.get("means", {})
        stds = scaling_params.get("stds", {})

        raw_vector = []
        for name in feature_names:
            val = 0.0
            if "_roll_mean" in name:
                base_col = name.replace("_roll_mean", "")
                if recent_history and len(recent_history) > 0:
                    vals = [h.get(base_col, current_values.get(base_col, 0.0)) for h in recent_history]
                    val = float(np.mean(vals))
                else:
                    val = float(current_values.get(base_col, 0.0))
            elif "_roll_std" in name:
                base_col = name.replace("_roll_std", "")
                if recent_history and len(recent_history) > 1:
                    vals = [h.get(base_col, current_values.get(base_col, 0.0)) for h in recent_history]
                    val = float(np.std(vals))
                else:
                    val = 0.0
            elif "_diff" in name:
                base_col = name.replace("_diff", "")
                if recent_history and len(recent_history) > 0:
                    prev = recent_history[-1].get(base_col, current_values.get(base_col, 0.0))
                    val = float(current_values.get(base_col, 0.0)) - float(prev)
                else:
                    val = 0.0
            else:
                # Raw signal
                val = float(current_values.get(name, 0.0))

            # Scale
            m = means.get(name, 0.0)
            s = stds.get(name, 1.0)
            if abs(s) < 1e-6:
                s = 1.0
            scaled_val = (val - m) / s
            raw_vector.append(scaled_val)

        return np.array([raw_vector], dtype=np.float64)

