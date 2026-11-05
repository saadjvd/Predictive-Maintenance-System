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
- **Phase Parent Epic:** `[P{Phase}]` (e.g., `[P01]`, `[P02]`, ..., `[P09]`)
- **Feature Issue:** `[P{Phase}-F{Feature}]` (e.g., `[P01-F01]`, `[P05-F02]`)
- **Sub-Feature / Task Issue:** `[P{Phase}-F{Feature}-S{SubFeature}]` (e.g., `[P01-F01-S01]`, `[P09-F04-S02]`)

---

## 3. Strict Branching Hierarchy & Protection Rules

Development follows an **Issue-First** Git hierarchy:

```
                  ┌──────────────┐
                  │     MAIN     │  ◄── Stable validated production releases only (Reviewed PR from develop)
                  └──────▲───────┘
                         │
                  ┌──────┴───────┐
                  │   DEVELOP    │  ◄── Quality integration branch (Phase PRs merge here)
                  └──────▲───────┘
                         │
             ┌───────────┴───────────┐
             │     PHASE BRANCH      │  (e.g., phase/09-factory-pilot)
             └───────────▲───────────┘
                         │
             ┌───────────┴───────────┐
             │    FEATURE BRANCH     │  (e.g., feature/P09-F04-issue-62-physical-plant-commissioning)
             └───────────────────────┘
```

### A. MAIN Rules
- **Stable releases only.**
- **No direct commits, no direct pushes, and no force-pushes.**
- No feature branches originating from `main`.
- All merges require an approved Pull Request from `develop` passing all CI quality gates.

### B. DEVELOP Rules
- **Integration branch only.**
- **No direct development commits.**
- Phase branches integrate into `develop` through verified Pull Requests.
- CI automated test battery (149 tests) and documentation verification gates must pass.

### C. Phase Branches
- Dedicated integration branch for each phase:
  - `phase/01-foundation`
  - `phase/02-auth-rbac`
  - `phase/03-equipment-registry`
  - `phase/04-opcua-ingestion`
  - `phase/05-anomaly-detection`
  - `phase/06-failure-prediction-rul`
  - `phase/07-langgraph-rag`
  - `phase/08-validation-readiness`
  - `phase/09-factory-pilot`
- Phase branches contain code and dependencies for their respective scope.

### D. Feature Branches
- Created **only** when independent development, testing, or review is required.
- Do not create empty historical branches for completed work.
- **Naming Pattern:**
  - Feature: `feature/P{Phase}-F{Feature}-issue-{NUMBER}-{short-description}`
  - Sub-Feature: `feature/P{Phase}-F{Feature}-S{SubFeature}-issue-{NUMBER}-{short-description}`
- **Pull Request Target:** Feature branches PR into their corresponding **Phase Branch**, NOT `develop` or `main`.

---

## 4. GitHub Commit Conventions

All commits must explicitly reference the GitHub issue number:

```text
feat(opcua): implement connection manager and auto-reconnect (#24)
fix(auth): enforce password history and lockout counter (#13)
test(prediction): add Weibull RUL survival coverage (#38)
docs(validation): update IQ/OQ/PQ traceability matrix (#50)
```

---

## 5. GitHub Label Matrix

| Category | Label | Color | Description |
| :--- | :--- | :--- | :--- |
| **Type** | `type:phase` | `#5319E7` | Phase-level parent tracking epic |
| | `type:feature` | `#1D76DB` | Major functional feature block |
| | `type:subfeature` | `#006B75` | Granular implementation task or test unit |
| | `type:bug` | `#D93F0B` | Defect or regression |
| | `type:documentation`| `#0E8A16` | Specification, GAMP 5 validation, or user docs |
| | `type:enhancement` | `#A2EEEF` | New capability or enhancement |
| **Phase** | `phase:01-foundation` | `#C2E0C6` | Phase 1 Foundation & Shell |
| | `phase:02-auth` | `#C2E0C6` | Phase 2 Auth, RBAC & Tenants |
| | `phase:03-equipment` | `#C2E0C6` | Phase 3 Universal Equipment Registry |
| | `phase:04-opcua` | `#C2E0C6` | Phase 4 Industrial IoT & OPC UA |
| | `phase:05-anomaly` | `#C2E0C6` | Phase 5 Baselines & Anomaly Detection |
| | `phase:06-prediction`| `#C2E0C6` | Phase 6 Failure Prediction & RUL |
| | `phase:07-agents` | `#C2E0C6` | Phase 7 LangGraph Multi-Agent RAG |
| | `phase:08-validation`| `#C2E0C6` | Phase 8 End-to-End Validation & Hardening |
| | `phase:09-pilot` | `#C2E0C6` | Phase 9 Factory Pilot & Multi-Factory Scalability |
| **Status** | `status:completed` | `#0E8A16` | Verified with automated tests & repo evidence |
| | `status:in-progress`| `#FBCA04` | Actively being developed |
| | `status:blocked` | `#E99695` | Blocked by external prerequisites |
| | `status:planned` | `#CCCCCC` | Scheduled for future factory/cloud execution |
| **Area** | `area:backend` | `#0052CC` | Flask, SQLAlchemy, REST API |
| | `area:frontend` | `#61DAFB` | Next.js, React, Tailwind CSS |
| | `area:ml-ai` | `#8A2BE2` | Scikit-learn, LangGraph, pgvector |
| | `area:iiot` | `#FF8C00` | OPC UA, Modbus, telemetry collectors |
| | `area:compliance` | `#B60205` | 21 CFR Part 11, GAMP 5, Audit Trail |
| | `area:devops` | `#F9D0C4` | CI/CD, containerization, deployment runbooks |
| **Priority**| `priority:critical`| `#B60205` | Critical operational priority |
| | `priority:high` | `#D93F0B` | High priority |
| | `priority:medium` | `#FBCA04` | Medium priority |
| | `priority:low` | `#0E8A16` | Low priority |

---

## 6. Closing Criteria for Issues

An issue may **ONLY** be closed (`status:completed`) when:
1. **Source Code Evidence:** Implementation exists in the repository.
2. **Automated Verification:** Associated unit or integration tests pass without errors.
3. **Audit Trail Compliance:** Any critical state change adheres to GAMP 5 / 21 CFR Part 11 audit logging.
4. **No Unfulfilled Physical Prerequisites:** Any work requiring on-site plant authorization (e.g. physical PLC connection) remains `status:planned` / `Open`.
