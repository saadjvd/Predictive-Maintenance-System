# PharmaPredict AI — User Requirements Specification (URS)

**Document Reference:** URS-PHARMAPREDICT-001  
**Version:** 1.0.0  
**Effective Date:** 2026-11-01  
**System Classification:** GAMP 5 Category 4 (Configured Software)  
**Regulatory Scope:** 21 CFR Part 11, EU Annex 11, ISO 13374 (Condition Monitoring and Diagnostics), OSHA 1910.147 (LOTO)

---

## 1. Introduction & Business Objective

### 1.1 Purpose
PharmaPredict AI is a cloud-edge pharmaceutical predictive maintenance and asset intelligence platform. This User Requirements Specification defines the operational, regulatory, quality, and technical requirements for deploying the platform across solid dosage, sterile fill-finish, packaging, and secondary manufacturing facilities.

### 1.2 Regulatory Context
Pharmaceutical manufacturing systems that analyze equipment critical process parameters (CPPs) and critical quality attributes (CQAs) must comply with international Good Automated Manufacturing Practice (GAMP 5) guidelines, US FDA 21 CFR Part 11, and European GMP Annex 11. PharmaPredict AI is configured software (GAMP Category 4) operating strictly as a **read-only decision support system**.

---

## 2. System Boundaries & Core Constraints

| Constraint ID | Specification | GAMP 5 / Safety Rationale |
|:---|:---|:---|
| **REQ-BOUND-01** | **Strict Read-Only OT Operation:** The system shall never issue automated write commands, tag modifications, or reset signals to PLCs, SCADA, or physical actuators. | Prevents unintended physical machine movement, cleanroom contamination, or batch disruption. |
| **REQ-BOUND-02** | **Human-in-the-Loop Authorization:** No maintenance work order, mechanical intervention, or electrical disconnection shall execute without explicit digital signature from a qualified maintenance engineer. | Enforces 21 CFR §11.100 accountability and OSHA safety compliance. |
| **REQ-BOUND-03** | **Zero Model Hallucination:** If predictive failure models lack certified training data or sufficient run-to-failure cycles, the system must return `PREDICTION_UNAVAILABLE` without fabricating probabilities or Remaining Useful Life (RUL) estimates. | Eliminates false confidence and ensures ALCOA+ data veracity. |
| **REQ-BOUND-04** | **Multi-Tenant Isolation:** Complete logical and cryptographic isolation between distinct manufacturing organizations and factory sites. | Protects proprietary drug manufacturing formulations and proprietary equipment parameters. |

---

## 3. User & Functional Requirements

### 3.1 Data Acquisition & Connectivity (ISO 13374 Level 1)
- **REQ-ACQ-01:** Connect to industrial PLCs and SCADA gateways via standard OPC UA protocols (`opc.tcp://`) supporting `Basic256Sha256` encryption and digital X.509 certificate authentication.
- **REQ-ACQ-02:** Continuous ingestion of vibration (RMS velocity, peak acceleration), temperature (motor winding, bearing casing), pressure, current, and speed at sampling rates from 1 Hz to 10 Hz.
- **REQ-ACQ-03:** Ingestion pipeline must buffer sensor readings locally at edge gateways during network interruptions for a minimum of 24 hours.

### 3.2 Data Quality & Telemetry Validation (ISO 13374 Level 2)
- **REQ-QUAL-01:** Inspect incoming telemetry for sensor flatlines, range violations, stale timestamps (>15 min lag), and bad OPC UA status codes.
- **REQ-QUAL-02:** Automatically halt deep predictive diagnostics and notify reliability engineers if telemetry quality degrades below acceptable thresholds (`is_reliable=False`).

### 3.3 Operating State & Baseline Modeling
- **REQ-BASE-01:** Distinguish machine operating states (`STOPPED`, `IDLE`, `CLEANING_CIP`, `RUNNING_PRODUCTION`) to prevent false alarms during changeovers.
- **REQ-BASE-02:** Formulate statistical baselines (mean, 3-sigma thresholds) exclusively from approved steady-state production runs.

### 3.4 Condition Monitoring & Anomaly Detection (ISO 13374 Level 3)
- **REQ-ANOM-01:** Perform dual-layer anomaly detection combining statistical Z-score/IQR thresholds with unsupervised machine learning (Isolation Forest).
- **REQ-ANOM-02:** Classify anomalies into deterministic severity levels (`INFO`, `WARNING`, `CRITICAL`) with root-cause signal attribution.

### 3.5 Failure Prediction & Remaining Useful Life (ISO 13374 Level 4)
- **REQ-PRED-01:** Provide component-specific failure mode risk estimation (e.g., bearing fatigue, thermal breakdown) using calibrated probability algorithms.
- **REQ-PRED-02:** Estimate Remaining Useful Life (RUL) operating hours with 90% confidence intervals only when validated Weibull survival models or gradient boosted trees exist.
- **REQ-PRED-03:** Enforce model lifecycle governance (DRAFT -> TRAINING -> VALIDATED -> DEPRECATED) with automated test benchmark criteria.

### 3.6 Multi-Agent Diagnostic Orchestration & RAG
- **REQ-AI-01:** Multi-agent diagnostic pipeline orchestrated via a directed acyclic graph (DAG) comprising 7 specialized agents: Data Quality, Condition Monitoring, Failure Prediction, Root Cause Analysis, Maintenance Recommendation, Compliance & Safety, and Reporting.
- **REQ-AI-02:** Technical retrieval-augmented generation (RAG) strictly bounded to approved OEM operating manuals, SOPs, and plant engineering drawings.
- **REQ-AI-03:** Automatic filtering and neutralization of prompt injection attacks or attempts to solicit unauthorized machine control commands.

### 3.7 Safety, GMP Compliance & Approval Workflow
- **REQ-SAFE-01:** Enforce OSHA 1910.147 Lockout/Tagout (LOTO) and zero-energy state verification on all mechanical maintenance recommendations.
- **REQ-SAFE-02:** Enforce NFPA 70E Arc-Flash PPE and electrical isolation verification on electrical inspection recommendations.
- **REQ-SAFE-03:** Require Cleanroom Class C/D sanitation protocols (70% IPA disinfection) for interventions in aseptic manufacturing suites.
- **REQ-SAFE-04:** Provide full human-in-the-loop lifecycle (`PROPOSED` -> `APPROVED` / `REJECTED` -> `CONVERTED_TO_WORK_ORDER`) with immutable audit trails.

---

## 4. Regulatory & Security Requirements (21 CFR Part 11 / EU Annex 11)

- **REQ-REG-01:** Time-stamped, computer-generated, unalterable audit trails recording user identity, timestamp, previous value, new value, and reason for change.
- **REQ-REG-02:** Role-Based Access Control (RBAC) supporting distinct roles: `SUPER_ADMIN`, `ORG_ADMIN`, `RELIABILITY_ENGINEER`, `MAINTENANCE_TECH`, `OPERATOR`, and `AUDITOR`.
- **REQ-REG-03:** Electronic signatures requiring two distinct identification components (password + MFA or approval token) for critical actions.
- **REQ-REG-04:** Comprehensive database backup utility generating SHA-256 integrity manifests compliant with ALCOA+ principles (Attributable, Legible, Contemporaneous, Original, Accurate).

