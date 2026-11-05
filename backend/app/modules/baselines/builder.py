import math
import numpy as np
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone


class BaselineStatsCalculator:
    """Computes robust statistical metrics from clean sensor telemetry points."""

    @classmethod
    def calculate_statistics(cls, values: List[float]) -> Optional[Dict[str, float]]:
        """Calculate mean, median, std, min, max, percentiles, IQR, and MAD."""
        if not values or len(values) < 5:
            return None

        arr = np.array(values, dtype=np.float64)
        # Remove any lingering NaNs or Infs
        arr = arr[~np.isnan(arr) & ~np.isinf(arr)]
        if len(arr) < 5:
            return None

        mean_val = float(np.mean(arr))
        median_val = float(np.median(arr))
        std_val = float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0
        min_val = float(np.min(arr))
        max_val = float(np.max(arr))

        p5_val = float(np.percentile(arr, 5))
        p25_val = float(np.percentile(arr, 25))
        p75_val = float(np.percentile(arr, 75))
        p95_val = float(np.percentile(arr, 95))

        iqr_val = float(p75_val - p25_val)
        mad_val = float(np.median(np.abs(arr - median_val)))
        variability = float(std_val / abs(mean_val)) if abs(mean_val) > 1e-6 else std_val

        return {
            "mean": round(mean_val, 4),
            "median": round(median_val, 4),
            "std": round(std_val, 4),
            "min": round(min_val, 4),
            "max": round(max_val, 4),
            "p5": round(p5_val, 4),
            "p25": round(p25_val, 4),
            "p75": round(p75_val, 4),
            "p95": round(p95_val, 4),
            "iqr": round(iqr_val, 4),
            "mad": round(mad_val, 4),
            "variability": round(variability, 4),
            "sample_count": len(arr),
        }

