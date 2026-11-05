# Maintenance Recommendation Agent Prompt
Version: 1.0.0

Formulate actionable, evidence-backed maintenance recommendations based on the root-cause hypotheses:

### Equipment:
- Machine: {machine_name}
- Root-Cause Hypotheses: {hypotheses}
- Predictive Risk Level: {risk_category} (Horizon: {prediction_horizon})

### Required Output Structure:
For each recommendation, specify:
1. Title and component affected.
2. Exact inspection or corrective procedure (e.g., check motor-gearbox alignment with dial gauge, replenish synthetic grease per OEM spec).
3. Priority level (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`).
4. Required physical safety precautions (LOTO, arc-flash PPE, sterile area sanitization).
5. Explicit note stating that this recommendation requires maintenance supervisor authorization before work order creation.

