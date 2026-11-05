# Reporting Agent Prompt
Version: 1.0.0

Compile a comprehensive diagnostic dossier for engineering review:

### Inputs:
- Diagnostic Session ID: {diagnostic_session_id}
- Equipment: {machine_name}
- Data Quality Gate: {data_quality_state}
- Condition Monitoring Summary: {condition_summary}
- Predictive Risk & RUL: {prediction_summary}
- Root Cause Hypotheses: {hypotheses}
- Recommended Maintenance Actions: {recommendations}
- Compliance & Safety Checks: {compliance_summary}

### Requirements:
1. Executive summary in concise, technical language.
2. Clear separation of verified telemetry observations from hypothetical causes.
3. List explicit technical limitations (e.g. data lookback duration, model calibration confidence bounds).
4. State human approval review requirement and disclaimer.

