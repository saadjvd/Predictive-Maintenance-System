# PharmaPredict AI — Phase 6: Implementation Audit & Architecture Plan

**Role:** Agent 2 (Senior Machine Learning Engineer, Reliability Engineer, Industrial IoT Architect, Flask Developer)  
**Date:** November 1, 2026  
**Status:** Audit Completed — Architecture Approved

---

## 1. Baseline Verification (Phases 1–5)

1. **Flask Backend & Database Connectivity:**
   - SQLite / PostgreSQL connection verified and healthy via `/api/v1/health`.
   - Multi-tenant data isolation active across all queries (`organization_id`).
   - Session & JWT token authentication with RBAC enforced (`MAINTENANCE_MANAGER`, `MAINTENANCE_ENGINEER`, `OPERATOR`, `VIEWER`).
2. **Equipment & Component Hierarchy:**
   - Universal equipment registry with machine components, parent-child component hierarchies, criticalities, and categories.
3. **OPC UA Telemetry & Continuous Monitoring (Phase 4):**
   - Simulated OPC UA industrial server, asynchronous tag discovery, universal signal mapping with unit conversion, continuous ingestion pipeline, and TimescaleDB-compatible time-series storage.
4. **Data Quality, Baselines & Anomaly Detection (Phase 5):**
   - 13-point data quality engine (`GOOD`, `SUSPECT`, `BAD`, `MISSING`, `STALE`).
   - Machine operating context classifier (`IDLE`, `STARTUP`, `RUNNING`, `HIGH_LOAD`, `SHUTDOWN`, `CLEANING`).
   - Statistical baseline profiles with versioned envelope metrics.
   - Multivariate Isolation Forest detector with explainable feature contributions.
   - Alarm deduplication and acknowledgment workflow in `AlertHistory`.
   - Full regression suite: **101 / 101 tests passing**.

---

## 2. Phase 6 Objectives & Scope Boundaries

PharmaPredict AI now extends condition monitoring into **supervised failure prediction, calibrated risk estimation, and conditional Remaining Useful Life (RUL)**.

### Strict Governance & Guardrails:
- **No Fabricated Predictions:** If a machine has insufficient verified failure records or unvalidated models, the engine must return `PREDICTION_UNAVAILABLE` with an explicit reason.
- **No Uncalibrated Probabilities:** Raw classification scores must never be passed off as failure probabilities without empirical calibration (Platt scaling / Isotonic regression) and Brier score evaluation.
- **No Pseudo-RUL:** RUL must strictly require verified degradation trajectories or survival models accounting for right-censoring; health-score-based arbitrary countdowns are strictly banned.
- **No Automated PLC Actions:** The engine generates decision-support predictive alerts; maintenance engineers remain the sole authority for maintenance work orders.
- **Scope Limit:** LangGraph multi-agent diagnostic orchestration, LangChain RAG, and LangSmith evaluation are reserved for Phase 7.

---

## 3. Phase 6 Implementation Modules

### A. Database Models (`backend/app/models/prediction.py`)
- `FailureMode`: Standard and custom failure modes linked to machine category/component.
- `FailureRecord`: Confirmed and suspected maintenance failure history with root causes and downtime.
- `PredictiveDataset`: Versioned datasets generated from aligned sensor time-series, operating states, and failure labels with temporal split tracking.
- `PredictiveModelRegistry` & `PredictiveModelVersion`: Supervised failure prediction models (`LOGISTIC_REGRESSION`, `RANDOM_FOREST`, `GRADIENT_BOOSTING`, `WEIBULL_SURVIVAL`).
- `ModelValidationResult` & `ModelCalibrationResult`: Precision, recall, F1, PR-AUC, ROC-AUC, Brier score, calibration curve metrics, and lead time.
- `EquipmentPrediction` & `PredictionEvidence`: Calibrated risk predictions for configured horizons (24h, 7d, 30d) with signal-level evidence.
- `PredictiveAlert`: Predictive alerts separate from Phase 5 anomaly alerts with review workflow.

### B. Machine Learning Engine Extension (`backend/app/ml_engine/prediction/`)
- `failure_modes.py`: Catalog of standard pharmaceutical failure modes.
- `predictive_features.py`: Temporal feature extractor (rolling aggregations, trend slopes, baseline deviations, anomaly density, operating hours).
- `dataset_builder.py`: Temporal splitting without future data leakage; class imbalance handling.
- `failure_classifier.py`: Supervised classifiers (Random Forest, Gradient Boosting, Logistic Regression).
- `probability_calibrator.py`: Platt scaling and isotonic regression with reliability analysis.
- `rul_estimator.py`: Weibull and survival analysis for conditional RUL with right-censoring.
- `eligibility_engine.py`: Machine predictive eligibility evaluator (`NOT_CONFIGURED`, `INSUFFICIENT_DATA`, `TRAINING_ELIGIBLE`, `UNDER_VALIDATION`, `PREDICTION_READY`, `DATA_QUALITY_BLOCKED`).
- `prediction_pipeline.py`: End-to-end training and inference pipeline with explainability.

### C. Backend API Routes (`backend/app/modules/predictions/`)
- Failure mode management endpoints.
- Failure records CRUD and verification workflow.
- Prediction eligibility evaluation.
- Supervised model training, validation metrics, approval, and activation.
- Calibrated prediction queries and on-demand inference.
- Predictive alerts management and acknowledgment.

### D. Frontend Predictive Intelligence (`components/equipment/predictive-tab.tsx`)
- Predictive Health Overview (Eligibility badge, Active Calibrated Risk, Failure Modes, Predictive Alerts).
- Failure Modes & Risk Horizon breakdown (24h, 7d, 30d).
- Explainable Prediction Evidence & Supporting Signal Trends.
- Predictive Alerts Review & Acknowledgment.
- Model Validation & Calibration Transparency Card.

