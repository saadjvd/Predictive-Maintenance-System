# PharmaPredict AI — Functional Specification (FS)

**Document Reference:** FS-PHARMAPREDICT-001  
**Version:** 1.0.0  
**Effective Date:** 2026-11-01  
**Traceability:** Implements requirements defined in [URS-PHARMAPREDICT-001](file:///c:/Users/Dell/OneDrive/Desktop/AI%20SOLUTION%20PROJECT/docs/validation/urs.md)

---

## 1. System Architecture & Functional Decomposition

PharmaPredict AI is structured into modular subsystems adhering to separation of concerns:

```
[ Industrial PLCs / Sensors ]
              │ (opc.tcp:// or Simulator)
              ▼
    [ OPC UA Collector Engine ]  ───► TimescaleDB (signal_readings hypertable)
              │
              ▼
   [ Data Quality & Baselines ]  ───► Evaluates flatlines, stale tags, baseline deviations
              │
              ▼
 [ Anomaly Detection & ML ]      ───► Statistical 3-Sigma + Isolation Forest
              │
              ▼
 [ Failure Prediction & RUL ]    ───► Calibrated probabilities & Weibull hazard rates
              │
              ▼
[ LangGraph 7-Agent Engine ]     ───► StateGraph DAG, RAG SOP retrieval, Safety filtering
              │
              ▼
[ Engineer Approval & Work Order ] ──► Human-in-the-loop sign-off (21 CFR Part 11)
```

---

## 2. Detailed Functional Specifications

### 2.1 Industrial Ingestion & Telemetry Processing
- **FS-INGEST-001:** Connects to OPC UA endpoints via AsyncIO client using `opcua` library.
- **FS-INGEST-002:** Signal Mapping Engine maps physical PLC NodeIDs (`ns=2;s=Blister_Drive_Motor_Vibration`) to canonical engineering units (mm/s, °C, bar, RPM, kW).
- **FS-INGEST-003:** Ingested readings stored in TimescaleDB hypertable `signal_readings` partitioned on `timestamp` with automated retention policies.

### 2.2 Data Quality & Health Safeguards
- **FS-QUAL-001:** Flatline detection monitors signal variance over sliding 15-minute windows; variance $\sigma^2 < 10^{-6}$ flags sensor freeze.
- **FS-QUAL-002:** Range validity checks incoming floating point numbers against equipment catalog physical min/max envelopes.
- **FS-QUAL-003:** If overall machine telemetry status is `BAD`, `MISSING`, or `STALE` (>15 min lag), the multi-agent pipeline immediately terminates at the Data Quality gate (`is_reliable=False`, `stop_reason="DATA_QUALITY_UNRELIABLE"`).

### 2.3 Condition Monitoring & Anomaly Detection
- **FS-ANOM-001:** Statistical Anomaly Detection computes running Z-scores:
  $$Z_i = \frac{x_i - \mu_{\text{baseline}}}{\sigma_{\text{baseline}}}$$
  Readings exceeding $|Z_i| > 3.0$ trigger statistical warning events.
- **FS-ANOM-002:** Multi-variate machine learning detection uses scikit-learn `IsolationForest(n_estimators=100, contamination=0.05)`.
- **FS-ANOM-003:** Anomaly aggregation engine groups temporal deviations into `AnomalyEvent` entities categorized by severity (`INFO`, `WARNING`, `CRITICAL`).

### 2.4 Failure Prediction & Remaining Useful Life (RUL)
- **FS-PRED-001:** Prediction Eligibility Gate verifies whether an approved model exists in the `ModelRegistry` for the specific machine and component type.
- **FS-PRED-002:** Probability Calibration: Raw classifier probabilities are calibrated using Platt scaling / Isotonic regression:
  $$P(\text{Failure} \mid S) = \frac{1}{1 + \exp(A \cdot f(S) + B)}$$
- **FS-PRED-003:** Remaining Useful Life (RUL) is estimated via parameterized Weibull cumulative hazard function:
  $$R(t) = \exp\left( - \left(\frac{t}{\eta}\right)^\beta \right)$$
  Yielding median RUL and 90% confidence bounds ($[t_{0.05}, t_{0.95}]$).
- **FS-PRED-004:** Unvalidated assets return status `PREDICTION_UNAVAILABLE` with clear diagnostic rationale.

### 2.5 LangGraph 7-Agent Diagnostic Orchestration
- **FS-DAG-001:** Executed via `langgraph.graph.StateGraph` with state schemas defined in Pydantic:
  1. `DataQualityAgent`: Validates sensor trustworthiness.
  2. `ConditionMonitoringAgent`: Assesses physical state deviations.
  3. `FailurePredictionAgent`: Retrieves calibrated model risk scores.
  4. `RootCauseAnalysisAgent`: Formulates hypotheses via pgvector semantic RAG.
  5. `MaintenanceRecommendationAgent`: Synthesizes specific corrective procedures.
  6. `ComplianceSafetyAgent`: Validates OSHA LOTO, Arc-Flash, and cleanroom gowning rules.
  7. `ReportingAgent`: Compiles auditable diagnostic report.
- **FS-DAG-002:** Deterministic Safety Edges:
  - If data is unreliable $\rightarrow$ route directly to `reporting` (`DATA_QUALITY_UNRELIABLE`).
  - If machine is normal ($Z < 0.20$) $\rightarrow$ route directly to `reporting` (`EQUIPMENT_HEALTHY`).
  - If hypothesis is unsupported $\rightarrow$ route directly to `reporting` (`NO_HYPOTHESIS_FORMULATED`).

### 2.6 Human-in-the-Loop & Maintenance Approval
- **FS-APPR-001:** Recommendations are staged in status `PROPOSED`.
- **FS-APPR-002:** Reliability Engineers approve or reject recommendations via authenticated POST `/api/recommendations/<id>/approve`.
- **FS-APPR-003:** Conversion to CMMS maintenance work order generates immutable change-log entry linked to the engineer's digital signature and timestamp.

