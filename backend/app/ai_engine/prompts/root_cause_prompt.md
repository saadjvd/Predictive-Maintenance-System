# Root Cause Analysis Agent Prompt
Version: 1.0.0

Analyze the following equipment diagnostic evidence and determine plausible root causes:

### Machine Context:
- Equipment: {machine_name} (Code: {asset_code}, Category: {category_name})
- Operating State: {operating_state}
- Data Quality State: {quality_state}

### Observed Telemetry & Anomalies:
- Condition Summary: {condition_summary}
- Discrete Anomalies Detected: {anomalies}
- Baseline Deviations: {baseline_deviations}

### Validated Predictive Models & Historical Context:
- Model Prediction Status: {prediction_status}
- Validated Failure Risk: {calibrated_probability}
- Verified Historical Root Causes: {historical_root_causes}

### Retrieved Technical Documentation (SOPs & OEM Manuals):
{retrieved_documents}

### Instructions:
1. Synthesize the telemetry observations with the troubleshooting steps in the retrieved documents.
2. Formulate 1 to 3 plausible root-cause hypotheses.
3. Categorize each hypothesis status as `SUPPORTED_HYPOTHESIS`, `POSSIBLE_CAUSE`, or `INSUFFICIENT_EVIDENCE`.
4. Include specific physical verification steps for maintenance engineers.
5. Provide explicit citations to document titles, sections, and pages.

