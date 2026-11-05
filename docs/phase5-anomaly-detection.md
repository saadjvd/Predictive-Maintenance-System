# PharmaPredict AI — Phase 5: Data Quality, Equipment Baselines & AI-Powered Anomaly Detection

**Status:** Completed & 100% Verified  
**Date:** November 1, 2026  
**Author:** Agent 2 (Senior ML Engineer, Industrial IoT Architect, Flask Backend Developer)  
**Regression Test Status:** 101 / 101 Tests Passing (100% Pass Rate)

---

## 1. Executive Summary & Architecture

Phase 5 elevates PharmaPredict AI from an industrial continuous telemetry collector into an intelligent pharmaceutical condition-monitoring system.

```
Industrial Sensor Readings (TimescaleDB / OPC UA)
                       ↓
         [ 1. Data Quality Gate ]
  (Checks: Bad Quality Codes, Nulls, NaNs, Stale TS, Gaps, Implausible Limits, Frozen Sensors)
                       ↓ (If GOOD/SUSPECT; If BAD/STALE: Alarms Suppressed)
     [ 2. Machine Operating Context Classifier ]
  (Classifies IDLE, STARTUP, RUNNING, HIGH_LOAD, SHUTDOWN, CLEANING with Confidence)
                       ↓
      ┌────────────────┴────────────────┐
      ↓                                 ↓
[ 3. Statistical Detector ]   [ 4. ML Isolation Forest ]
- Baseline Profile Envelope    - Multivariate Feature Matrix
- Z-Score Deviation (>3.0)     - Rolling stats, Diff, Scaling
- Robust MAD Score (>3.5)      - Joblib Artifact Persistence
- Percentile Boundary (p5-p95) - Normalized Feature Contribution
      └────────────────┬────────────────┘
                       ↓
        [ 5. Anomaly Decision Engine ]
  (Context-aware synthesis, composite score 0.0-1.0, severity: INFO/WARNING/CRITICAL)
                       ↓
        [ 6. Anomaly Event & Evidence ]
  (Signal-level evidence items, expected vs observed values, transparent audit trail)
                       ↓
        [ 7. Equipment Alert Workflow ]
  (Deduplication, 15-min cooldown, acknowledgment dialog, audit trail in AlertHistory)
                       ↓
     [ 8. Next.js Condition Monitoring UI ]
  (Condition Cards, Anomaly Feed, Baseline Envelopes, Alert Acknowledgment Modal)
```

---

## 2. Strict Scope Boundaries & Governance

To maintain regulatory trust in pharmaceutical environments (GxP / 21 CFR Part 11), Phase 5 strictly enforces:
- **NO Artificial Failure Probabilities:** Isolation Forest anomaly scores are never represented as machine breakdown percentages.
- **NO Remaining Useful Life (RUL) Estimation:** RUL predictions require dedicated degradation models (reserved for future phases).
- **NO Automated Machine Shutdown:** PharmaPredict AI does not write PLC stop commands; condition alerts guide maintenance teams.
- **NO Early Agentic Execution:** LangGraph/LangChain agentic workflows are reserved for Phase 6.

---

## 3. Core Engine Components

### 3.1 Data Quality Gate (`backend/app/modules/data_quality/engine.py`)
Assesses incoming and time-series sensor readings against 13 industrial data quality criteria:
1. Source OPC UA quality code (`Good`, `Uncertain`, `Bad`).
2. Missing / null values in raw or normalized readings.
3. Non-computable values (`NaN`, `Infinity`).
4. Stale timestamps (telemetry age exceeding 6x sampling interval).
5. Future timestamps (> 5 minutes ahead of server clock).
6. Out-of-order time-series sequences.
7. Physically implausible thresholds by dimension (e.g. Temperature outside [-50°C, 350°C], Speed outside [0, 15000 RPM]).
8. Sudden non-physical signal spikes (> 2.5x max dynamic step limit).
9. Suspiciously constant / frozen dynamic signals (zero variance across 20+ readings for vibration/temp/current).
10. Gaps in continuous sampling intervals.
11. Data type compatibility verification.
12. Multi-sensor consistency checks.
13. Automatic alarm suppression when data quality is degraded (`QualityState.BAD` or `QualityState.STALE`).

### 3.2 Operating Context Classifier (`backend/app/modules/operating_context/classifier.py`)
Classifies operating regimes based on multi-sensor states:
- `IDLE`: Turret speed ≤ 5 RPM, motor current ≤ 5 A, temperature ≤ 60°C.
- `STARTUP`: Low initial speed (5–60 RPM) with rising motor current.
- `RUNNING`: Turret speed > 60 RPM, nominal vibration (0.5–2.5 mm/s), nominal temperature (80–150°C).
- `HIGH_LOAD`: Speed > 80 RPM with elevated current (> 25 A) or vibration (> 3.5 mm/s).
- `SHUTDOWN`: Deceleration from running speed to 0 RPM.
- `CLEANING`: Zero turret speed with wash-cycle temperature/flow patterns.

### 3.3 Equipment Baseline Engine (`backend/app/modules/baselines/builder.py`)
Calculates statistical operating envelopes from clean historical telemetry:
- **Metrics:** Sample count, Mean, Standard Deviation, Median, Min, Max, 5th percentile (p5), 25th percentile (p25), 75th percentile (p75), 95th percentile (p95), Interquartile Range (IQR), Median Absolute Deviation (MAD), and Variability.
- **Versioning:** Profiles are versioned and require authorization before activation (`COLLECTING` → `CANDIDATE` → `VALIDATING` → `APPROVED` → `ACTIVE`).

### 3.4 Statistical Anomaly Detector (`backend/app/ml_engine/statistical_detector.py`)
- Evaluates individual telemetry readings against active approved baseline profiles.
- Computes standard Z-Score: $|x - \mu| / \sigma$.
- Computes robust MAD Score: $0.6745 \times |x - \text{median}| / \text{MAD}$.
- Evaluates Percentile boundaries ($x < p5$ or $x > p95$).
- Assigns severity: `INFO` (deviation ≥ 2.0), `WARNING` (deviation ≥ 3.0), `CRITICAL` (deviation ≥ 4.5).

### 3.5 Machine Learning Engine (`backend/app/ml_engine/`)
- **Feature Engineering:** Builds aligned wide multivariate matrix with rolling mean, rolling std, and rate of change (first difference), with Z-standardization.
- **Isolation Forest Wrapper:** Unsupervised ensemble of isolation trees trained on normal operating baseline data (`contamination=0.03`).
- **Explainability:** Calculates normalized feature contributions to pinpoint which signals caused the anomaly.
- **Artifact Persistence:** Model weights, feature names, and scaling parameters are serialized to disk (`backend/artifacts/models/`) via `joblib`.

### 3.6 Operational Alert Workflow (`backend/app/modules/alerts/services.py`)
- **Deduplication:** Prevents alarm fatigue by aggregating occurrences of ongoing anomalies.
- **Cooldown:** Enforces a 15-minute cooldown window between new alerts on the same machine.
- **Lifecycle:** `OPEN` → `ACKNOWLEDGED` → `UNDER_INVESTIGATION` → `RESOLVED` → `CLOSED`.
- **Audit Trail:** Every status transition, note, and engineer identity is permanently logged in `AlertHistory`.

---

## 4. REST API Endpoints

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `GET` | `/api/v1/equipment/:id/condition` | Condition summary, operational indicators, active anomalies | `login_required` |
| `POST` | `/api/v1/equipment/:id/condition/evaluate` | Trigger on-demand condition and anomaly evaluation | `login_required` |
| `GET` | `/api/v1/equipment/:id/condition/history` | Historical condition observation snapshots | `login_required` |
| `GET` | `/api/v1/equipment/:id/data-quality` | Data quality assessment & 13-point issue reports | `login_required` |
| `GET` | `/api/v1/equipment/:id/operating-context` | Operating state classification & confidence | `login_required` |
| `GET` | `/api/v1/equipment/:id/baselines` | Signal baseline profiles & active versions | `login_required` |
| `POST` | `/api/v1/equipment/:id/baselines/build` | Calculate candidate baselines from historical data | `roles_required(Manager, Engineer)` |
| `POST` | `/api/v1/baselines/:id/approve` | Authorize and activate candidate baseline version | `roles_required(Manager)` |
| `GET` | `/api/v1/equipment/:id/anomalies` | List anomaly events with filter by severity & status | `login_required` |
| `GET` | `/api/v1/anomalies/:id` | Single anomaly event with signal-level evidence | `login_required` |
| `POST` | `/api/v1/equipment/:id/ml-models/train` | Train multivariate Isolation Forest model | `login_required` |
| `GET` | `/api/v1/equipment/:id/ml-models` | List ML model registry and trained versions | `login_required` |
| `GET` | `/api/v1/alerts` | Organization equipment alerts with filters | `login_required` |
| `GET` | `/api/v1/alerts/:id` | Alert detail with full audit history | `login_required` |
| `POST` | `/api/v1/alerts/:id/acknowledge` | Acknowledge alert with engineer notes | `login_required` |
| `PATCH` | `/api/v1/alerts/:id/status` | Update alert status (`UNDER_INVESTIGATION`, `RESOLVED`, `CLOSED`) | `login_required` |

---

## 5. Frontend Condition Monitoring UI

The Condition Monitoring dashboard is integrated into the equipment detail page:
- **Location:** [`components/equipment/condition-tab.tsx`](file:///c:/Users/Dell/OneDrive/Desktop/AI%20SOLUTION%20PROJECT/components/equipment/condition-tab.tsx)
- **Equipment Detail Tab:** [`app/dashboard/equipment/[id]/page.tsx`](file:///c:/Users/Dell/OneDrive/Desktop/AI%20SOLUTION PROJECT/app/dashboard/equipment/[id]/page.tsx)
- **Features:**
  1. **4 Condition Cards:** Condition Classification (`NORMAL`, `ATTENTION`, `CRITICAL`), Operating Regime, Data Quality Gate, and Anomaly & Alert Score.
  2. **Actions:** "Evaluate Now", "Train Isolation Forest", "Build Baselines".
  3. **Anomalies Feed:** Real-time list of detected anomalies with severity badges, detection method, affected signals, and expandable evidence trails.
  4. **Baseline Envelopes Grid:** Visual cards displaying Mean, Std, Min, Max, and Percentile envelopes (p5–p95) per signal.
  5. **Alert Acknowledgment:** One-click acknowledgment modal with notes input and audit history.
  6. **ML Registry:** Version history, training sample count, and active model lifecycle.

---

## 6. Automated Test Suite Results

Test module: [`backend/tests/test_phase5_condition.py`](file:///c:/Users/Dell/OneDrive/Desktop/AI%20SOLUTION%20PROJECT/backend/tests/test_phase5_condition.py)
- `test_statistical_anomaly_detector_nominal`: PASSED
- `test_statistical_anomaly_detector_critical_zscore`: PASSED
- `test_feature_engineering_and_isolation_forest`: PASSED
- `test_operating_state_classification`: PASSED
- `test_data_quality_suppression_in_decision_engine`: PASSED
- `test_baseline_building_and_approval`: PASSED
- `test_condition_evaluation_and_alert_acknowledgment`: PASSED
- `test_cross_tenant_isolation`: PASSED

**Total Backend Test Suite:** 101 tests passed out of 101 (100% pass rate).  
**TypeScript Compilation (`pnpm exec tsc --noEmit`):** 0 errors.

