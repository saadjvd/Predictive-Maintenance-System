# GitHub Issue, Milestone & Branching Workflow for PharmaPredict AI

## 1. Overview
This document defines the standardized GitHub project management structure, issue taxonomy, milestone definitions, labeling conventions, and Git branching workflows for **PharmaPredict AI**.

---

## 2. Issue Taxonomy & Hierarchy

All issues in PharmaPredict AI follow a 3-tier parent-child hierarchy:

```
[Phase Milestone] (e.g., Phase 01 - Foundation)
       │
       ▼
[Phase Parent Issue] `[P01] Phase 1: Foundation & Existing Frontend/Backend Integration`
       │
       ├─► [Feature Issue] `[P01-F01] Next.js Landing Page & UI Shell`
       │         │
       │         ├─► [Sub-Feature / Task] `[P01-F01-S01] Hero Section & Architecture Highlights`
       │         └─► [Sub-Feature / Task] `[P01-F01-S02] Responsive Navigation & Theme Configuration`
       │
       └─► [Feature Issue] `[P01-F02] Flask Application Factory & Baseline API Structure`
                 │
                 ├─► [Sub-Feature / Task] `[P01-F02-S01] App Factory with CORS & Health Check`
                 └─► [Sub-Feature / Task] `[P01-F02-S02] Configuration Management & Environment Binding`
```

### Identifier Format
- **Phase Parent:** `[P{Phase}]` (e.g., `[P01]`, `[P02]`, ..., `[P09]`)
- **Feature:** `[P{Phase}-F{Feature}]` (e.g., `[P01-F01]`, `[P05-F02]`)
- **Sub-Feature / Task:** `[P{Phase}-F{Feature}-S{SubFeature}]` (e.g., `[P01-F01-S01]`, `[P09-F03-S02]`)

---

## 3. GitHub Label Matrix

| Label Category | Label Name | Description | Color |
| :--- | :--- | :--- | :--- |
| **Type** | `type:phase` | Phase-level parent tracking epic | `#5319E7` |
| | `type:feature` | Major functional feature block | `#1D76DB` |
| | `type:subfeature` | Granular implementation task or test unit | `#006B75` |
| | `type:bug` | Defect or regression | `#D93F0B` |
| | `type:documentation`| Specification, GAMP 5 validation, or user docs | `#0E8A16` |
| **Phase** | `phase:01-foundation` | Phase 1 Foundation & Shell | `#C2E0C6` |
| | `phase:02-auth` | Phase 2 Auth, RBAC & Tenants | `#C2E0C6` |
| | `phase:03-equipment` | Phase 3 Universal Equipment Registry | `#C2E0C6` |
| | `phase:04-opcua` | Phase 4 Industrial IoT & OPC UA | `#C2E0C6` |
| | `phase:05-anomaly` | Phase 5 Baselines & Anomaly Detection | `#C2E0C6` |
| | `phase:06-prediction`| Phase 6 Failure Prediction & RUL | `#C2E0C6` |
| | `phase:07-agents` | Phase 7 LangGraph Multi-Agent RAG | `#C2E0C6` |
| | `phase:08-validation`| Phase 8 End-to-End Validation & Hardening | `#C2E0C6` |
| | `phase:09-pilot` | Phase 9 Factory Pilot & Multi-Factory Scalability | `#C2E0C6` |
| **Status** | `status:completed` | Verified with tests & repo evidence | `#0E8A16` |
| | `status:in-progress`| Actively being developed | `#FBCA04` |
| | `status:blocked` | Blocked by external prerequisites | `#E99695` |
| | `status:planned` | Scheduled for future factory/cloud execution | `#CCCCCC` |
| **Area** | `area:backend` | Flask, SQLAlchemy, Celery, REST API | `#0052CC` |
| | `area:frontend` | Next.js, React, Tailwind CSS | `#61DAFB` |
| | `area:ml-ai` | Scikit-learn, XGBoost, LangGraph, pgvector | `#8A2BE2` |
| | `area:iiot` | OPC UA, Modbus, telemetry collectors | `#FF8C00` |
| | `area:compliance` | 21 CFR Part 11, GAMP 5, Audit Trail | `#B60205` |

---

## 4. GitHub Milestones

1. **Phase 01 — Foundation & Existing Frontend/Backend Integration**
2. **Phase 02 — Authentication, RBAC & Multi-Tenancy**
3. **Phase 03 — Universal Equipment Registry**
4. **Phase 04 — OPC UA Connectivity & Signal Ingestion**
5. **Phase 05 — Data Quality, Equipment Baselines & Anomaly Detection**
6. **Phase 06 — Failure Prediction & Remaining Useful Life (RUL)**
7. **Phase 07 — LangGraph Multi-Agent Intelligence & RAG**
8. **Phase 08 — End-to-End Validation & Production Readiness**
9. **Phase 09 — Controlled Factory Pilot & Multi-Factory Scalability**

---

## 5. Git Branching & Merge Strategy

- **`main`**: Production-ready, validated code branch. Protected from direct commits.
- **`develop`**: Integration branch for completed and verified features.
- **`feature/{phase}-{feature-name}`**: Feature branches cut from `develop` (e.g., `feature/p09-pilot-readiness`).
- **`bugfix/{issue-id}-{short-desc}`**: Defect remediation branches.
- **`docs/{topic}`**: Documentation updates (e.g., `docs/phase-issue-organization`).

### Commit Convention
```
feat(phase-09): add pilot telemetry ingestion and baseline drift validator (#XX)
fix(auth): enforce password history and session lockout rules (#YY)
docs(github): establish phase and issue tracking hierarchy (#ZZ)
```

---

## 6. Closing Criteria for Issues

An issue may ONLY be moved to `Closed` (`status:completed`) when:
1. **Source Code Evidence**: Implementation exists in the repository.
2. **Automated Verification**: Associated unit or integration tests pass without errors.
3. **Audit Trail Compliance**: Any critical state change adheres to GAMP 5 / 21 CFR Part 11 audit logging.
4. **No Unfulfilled Production Dependencies**: Tasks requiring physical site authorization remain `status:planned` / `Open`.

