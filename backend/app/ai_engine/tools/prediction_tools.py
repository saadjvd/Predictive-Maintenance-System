from typing import Dict, Any, List
from app.models.prediction import (
    EquipmentPrediction,
    PredictionEvidence,
    PredictiveModelRegistry,
    PredictiveModelLifecycle,
)
from app.modules.predictions.services import PredictionService
from app.ml_engine.prediction.eligibility_engine import ModelEligibilityEngine


class PredictionTools:
    """Read-only failure prediction and RUL estimation tools for diagnostic agents."""

    @classmethod
    def get_prediction_eligibility(cls, organization_id: str, machine_id: str) -> Dict[str, Any]:
        """Checks whether machine meets requirements for calibrated failure prediction."""
        return ModelEligibilityEngine.evaluate_machine_eligibility(
            organization_id=organization_id,
            machine_id=machine_id,
        )

    @classmethod
    def get_latest_validated_predictions(
        cls,
        organization_id: str,
        machine_id: str,
    ) -> List[Dict[str, Any]]:
        """
        Retrieves latest validated predictions and RUL calculations.
        If models are uncalibrated or data inadequate, returns PREDICTION_UNAVAILABLE.
        """
        # Check eligibility first
        eligibility = cls.get_prediction_eligibility(organization_id, machine_id)
        if not eligibility.get("can_predict", False):
            return [
                {
                    "status": "PREDICTION_UNAVAILABLE",
                    "calibrated_probability": None,
                    "risk_category": "LOW",
                    "rul_hours": None,
                    "rationale": "; ".join(eligibility.get("reasons", ["Predictive model not available."])),
                    "evidence": [],
                }
            ]

        # Retrieve latest predictions
        preds = (
            EquipmentPrediction.query.filter_by(
                organization_id=organization_id,
                machine_id=machine_id,
            )
            .order_by(EquipmentPrediction.evaluated_at.desc())
            .limit(3)
            .all()
        )

        results = []
        for p in preds:
            p_dict = p.to_dict()
            evidence = PredictionEvidence.query.filter_by(prediction_id=p.id).all()
            p_dict["evidence"] = [e.to_dict() for e in evidence]
            results.append(p_dict)

        return results

