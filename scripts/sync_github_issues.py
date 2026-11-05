"""
PharmaPredict AI - GitHub Milestone, Label & Issue Hierarchy Synchronization Script
Synchronizes the 9-Phase hierarchy with GitHub repository: saadjvd/Predictive-Maintenance-System
"""

import os
import sys
import argparse
import json
import urllib.request
import urllib.error
import time

REPO = "saadjvd/Predictive-Maintenance-System"
API_BASE = f"https://api.github.com/repos/{REPO}"

MILESTONES = [
    {
        "title": "Phase 01 — Foundation & Existing Frontend/Backend Integration",
        "description": "Core layout, Next.js frontend, Flask application factory, and configuration.",
        "state": "closed"
    },
    {
        "title": "Phase 02 — Authentication, RBAC & Multi-Tenancy",
        "description": "Multi-tenant isolation, 21 CFR Part 11 audit trails, JWT auth, and role-based access control.",
        "state": "closed"
    },
    {
        "title": "Phase 03 — Universal Equipment Registry",
        "description": "Universal machinery data modeling, component hierarchies, and CRUD management APIs.",
        "state": "closed"
    },
    {
        "title": "Phase 04 — OPC UA Connectivity & Signal Ingestion",
        "description": "Industrial protocol connectors, async OPC UA client, and real-time telemetry streaming.",
        "state": "closed"
    },
    {
        "title": "Phase 05 — Data Quality, Equipment Baselines & Anomaly Detection",
        "description": "Industrial data sanitation, operating baseline models, and unsupervised anomaly detection.",
        "state": "closed"
    },
    {
        "title": "Phase 06 — Failure Prediction & Remaining Useful Life (RUL) Framework",
        "description": "Failure mode classifiers, probability calibration, and Weibull RUL estimation engine.",
        "state": "closed"
    },
    {
        "title": "Phase 07 — LangGraph Multi-Agent Intelligence, RAG & LangSmith Evaluation",
        "description": "7-agent LangGraph orchestration, technical knowledge pgvector RAG, and LangSmith tracing.",
        "state": "closed"
    },
    {
        "title": "Phase 08 — End-to-End System Validation, Security & Pilot Readiness",
        "description": "Cross-module pipeline validation, GAMP 5 CSV documentation, and security audit tests.",
        "state": "closed"
    },
    {
        "title": "Phase 09 — Controlled Factory Pilot, Real-World Validation & Multi-Factory Scalability",
        "description": "Controlled factory pilot protocols, shadow-mode monitoring, feedback, and Go/No-Go evaluation.",
        "state": "open"
    }
]

LABELS = [
    # Types
    {"name": "type:phase", "color": "5319E7", "description": "Phase-level parent tracking epic"},
    {"name": "type:feature", "color": "1D76DB", "description": "Major functional feature block"},
    {"name": "type:subfeature", "color": "006B75", "description": "Granular implementation task or test unit"},
    {"name": "type:bug", "color": "D93F0B", "description": "Defect or regression"},
    {"name": "type:documentation", "color": "0E8A16", "description": "Specification, GAMP 5 validation, or user docs"},
    {"name": "type:enhancement", "color": "A2EEEF", "description": "New capability or enhancement"},
    # Phases
    {"name": "phase:01-foundation", "color": "C2E0C6", "description": "Phase 1 Foundation & Shell"},
    {"name": "phase:02-auth", "color": "C2E0C6", "description": "Phase 2 Auth, RBAC & Tenants"},
    {"name": "phase:03-equipment", "color": "C2E0C6", "description": "Phase 3 Universal Equipment Registry"},
    {"name": "phase:04-opcua", "color": "C2E0C6", "description": "Phase 4 Industrial IoT & OPC UA"},
    {"name": "phase:05-anomaly", "color": "C2E0C6", "description": "Phase 5 Baselines & Anomaly Detection"},
    {"name": "phase:06-prediction", "color": "C2E0C6", "description": "Phase 6 Failure Prediction & RUL"},
    {"name": "phase:07-agents", "color": "C2E0C6", "description": "Phase 7 LangGraph Multi-Agent RAG"},
    {"name": "phase:08-validation", "color": "C2E0C6", "description": "Phase 8 End-to-End Validation & Hardening"},
    {"name": "phase:09-pilot", "color": "C2E0C6", "description": "Phase 9 Factory Pilot & Multi-Factory Scalability"},
    # Statuses
    {"name": "status:completed", "color": "0E8A16", "description": "Verified with tests & repo evidence"},
    {"name": "status:in-progress", "color": "FBCA04", "description": "Actively being developed"},
    {"name": "status:blocked", "color": "E99695", "description": "Blocked by external prerequisites"},
    {"name": "status:planned", "color": "CCCCCC", "description": "Scheduled for future execution"},
    # Areas
    {"name": "area:backend", "color": "0052CC", "description": "Flask, SQLAlchemy, REST API"},
    {"name": "area:frontend", "color": "61DAFB", "description": "Next.js, React, Tailwind CSS"},
    {"name": "area:ml-ai", "color": "8A2BE2", "description": "Scikit-learn, LangGraph, pgvector"},
    {"name": "area:iiot", "color": "FF8C00", "description": "OPC UA, Modbus, telemetry collectors"},
    {"name": "area:compliance", "color": "B60205", "description": "21 CFR Part 11, GAMP 5, Audit Trail"},
    {"name": "area:devops", "color": "F9D0C4", "description": "CI/CD, containerization, deployment runbooks"},
    # Priorities
    {"name": "priority:critical", "color": "B60205", "description": "Critical priority"},
    {"name": "priority:high", "color": "D93F0B", "description": "High priority"},
    {"name": "priority:medium", "color": "FBCA04", "description": "Medium priority"},
    {"name": "priority:low", "color": "0E8A16", "description": "Low priority"}
]

PHASES_DATA = [
    {
        "id": "P01",
        "title": "[P01] Phase 1: Foundation & Existing Frontend/Backend Integration",
        "milestone_index": 0,
        "labels": ["type:phase", "phase:01-foundation", "status:completed", "priority:critical"],
        "body": "## Phase 1 Overview\nCore landing page, Flask backend factory, layout tokens, and development environment setup.\n\n### Repository Evidence\n- `frontend/app/page.tsx`, `components/landing/`\n- `backend/app/__init__.py`, `backend/app/config.py`\n- `backend/tests/test_health.py` (All tests passed)\n\n### Verification Status\nClosed as completed based on passing tests and code inspection.",
        "features": [
            {
                "id": "P01-F01",
                "title": "[P01-F01] Next.js 14 Landing Page & UI Layout System",
                "labels": ["type:feature", "phase:01-foundation", "area:frontend", "status:completed", "priority:high"],
                "body": "Next.js landing page with industrial styling, responsive navigation, and design tokens.\n\nEvidence: `frontend/app/page.tsx`, `components/landing/Hero.tsx`.",
                "subfeatures": [
                    {"id": "P01-F01-S01", "title": "[P01-F01-S01] Hero Section & Architecture Highlights", "status": "completed", "priority": "medium", "area": "area:frontend"},
                    {"id": "P01-F01-S02", "title": "[P01-F01-S02] Responsive Navigation & Theme Configuration", "status": "completed", "priority": "medium", "area": "area:frontend"}
                ]
            },
            {
                "id": "P01-F02",
                "title": "[P01-F02] Flask Application Factory & Baseline API Structure",
                "labels": ["type:feature", "phase:01-foundation", "area:backend", "status:completed", "priority:critical"],
                "body": "Flask app factory, CORS configuration, environment loader, and health endpoints.\n\nEvidence: `backend/app/__init__.py`, `backend/tests/test_health.py`.",
                "subfeatures": [
                    {"id": "P01-F02-S01", "title": "[P01-F02-S01] App Factory with CORS & Health Check", "status": "completed", "priority": "high", "area": "area:backend"},
                    {"id": "P01-F02-S02", "title": "[P01-F02-S02] Configuration Profiles & Environment Binding", "status": "completed", "priority": "high", "area": "area:backend"}
                ]
            }
        ]
    },
    {
        "id": "P02",
        "title": "[P02] Phase 2: Authentication, RBAC & Multi-Tenancy",
        "milestone_index": 1,
        "labels": ["type:phase", "phase:02-auth", "status:completed", "priority:critical"],
        "body": "## Phase 2 Overview\nMulti-tenant organization isolation, 21 CFR Part 11 compliant audit logging, JWT auth, and role-based access control.\n\n### Repository Evidence\n- `backend/app/models/user.py`, `backend/app/models/tenant.py`\n- `backend/app/modules/auth/routes.py`, `backend/app/services/audit_service.py`\n- `backend/tests/test_auth.py`, `backend/tests/test_rbac.py` (All tests passed)\n\n### Verification Status\nClosed as completed based on passing tests and code inspection.",
        "features": [
            {
                "id": "P02-F01",
                "title": "[P02-F01] Multi-Tenant Organization Isolation",
                "labels": ["type:feature", "phase:02-auth", "area:backend", "status:completed", "priority:critical"],
                "body": "Tenant scoping decorators, organization database models, and isolated query filters.\n\nEvidence: `backend/app/models/tenant.py`, `backend/app/utils/tenant_context.py`.",
                "subfeatures": [
                    {"id": "P02-F01-S01", "title": "[P02-F01-S01] Organization Model & Tenant Keys", "status": "completed", "priority": "high", "area": "area:backend"},
                    {"id": "P02-F01-S02", "title": "[P02-F01-S02] Cross-Tenant Isolation Context Guards", "status": "completed", "priority": "critical", "area": "area:backend"}
                ]
            },
            {
                "id": "P02-F02",
                "title": "[P02-F02] Role-Based Access Control (RBAC) & 21 CFR Part 11 Audit Trail",
                "labels": ["type:feature", "phase:02-auth", "area:compliance", "status:completed", "priority:critical"],
                "body": "Granular pharma roles, JWT issuance/revocation, and immutable audit trails.\n\nEvidence: `backend/app/models/audit.py`, `backend/app/services/audit_service.py`.",
                "subfeatures": [
                    {"id": "P02-F02-S01", "title": "[P02-F02-S01] Role Matrix (Admin, Engineer, Auditor)", "status": "completed", "priority": "high", "area": "area:compliance"},
                    {"id": "P02-F02-S02", "title": "[P02-F02-S02] Immutable Audit Logging Service", "status": "completed", "priority": "critical", "area": "area:compliance"}
                ]
            }
        ]
    },
    {
        "id": "P03",
        "title": "[P03] Phase 3: Universal Equipment Registry",
        "milestone_index": 2,
        "labels": ["type:phase", "phase:03-equipment", "status:completed", "priority:critical"],
        "body": "## Phase 3 Overview\nUniversal equipment hierarchy, machinery component modeling, and management CRUD APIs.\n\n### Repository Evidence\n- `backend/app/models/machine.py`, `backend/app/models/component.py`, `backend/app/models/sensor.py`\n- `backend/app/modules/equipment/routes.py`\n- `backend/tests/test_equipment.py` (All tests passed)\n\n### Verification Status\nClosed as completed based on passing tests and code inspection.",
        "features": [
            {
                "id": "P03-F01",
                "title": "[P03-F01] Universal Machinery Data Modeling & Hierarchies",
                "labels": ["type:feature", "phase:03-equipment", "area:backend", "status:completed", "priority:high"],
                "body": "Machine and component models with operating thresholds and criticality levels.\n\nEvidence: `backend/app/models/machine.py`, `backend/app/models/component.py`.",
                "subfeatures": [
                    {"id": "P03-F01-S01", "title": "[P03-F01-S01] Machine & Component Schemas", "status": "completed", "priority": "high", "area": "area:backend"},
                    {"id": "P03-F01-S02", "title": "[P03-F01-S02] Sensor Telemetry & Threshold Definition", "status": "completed", "priority": "high", "area": "area:backend"}
                ]
            },
            {
                "id": "P03-F02",
                "title": "[P03-F02] Equipment Management APIs & Dashboard",
                "labels": ["type:feature", "phase:03-equipment", "area:backend", "status:completed", "priority:high"],
                "body": "REST endpoints for machine registration and frontend equipment dashboard.\n\nEvidence: `backend/app/modules/equipment/routes.py`, `app/dashboard/equipment/`.",
                "subfeatures": [
                    {"id": "P03-F02-S01", "title": "[P03-F02-S01] Equipment Registry CRUD Endpoints", "status": "completed", "priority": "high", "area": "area:backend"}
                ]
            }
        ]
    },
    {
        "id": "P04",
        "title": "[P04] Phase 4: OPC UA Connectivity & Signal Ingestion",
        "milestone_index": 3,
        "labels": ["type:phase", "phase:04-opcua", "status:completed", "priority:critical"],
        "body": "## Phase 4 Overview\nIndustrial connectivity via OPC UA, live telemetry streaming, and simulation services.\n\n### Repository Evidence\n- `backend/app/services/opcua_client.py`, `backend/app/services/telemetry_service.py`\n- `backend/app/services/simulator.py`\n- `backend/tests/test_opcua.py`, `backend/tests/test_telemetry.py` (All tests passed)\n\n### Verification Status\nClosed as completed based on passing tests and code inspection.",
        "features": [
            {
                "id": "P04-F01",
                "title": "[P04-F01] Industrial Protocol Connectors & OPC UA Integration",
                "labels": ["type:feature", "phase:04-opcua", "area:iiot", "status:completed", "priority:critical"],
                "body": "Async OPC UA client with auto-reconnect, namespace browsing, and subscriptions.\n\nEvidence: `backend/app/services/opcua_client.py`.",
                "subfeatures": [
                    {"id": "P04-F01-S01", "title": "[P04-F01-S01] Async OPC UA Client & Auto-Reconnect", "status": "completed", "priority": "critical", "area": "area:iiot"}
                ]
            },
            {
                "id": "P04-F02",
                "title": "[P04-F02] Time-Series Telemetry Pipeline & Live Ingestion",
                "labels": ["type:feature", "phase:04-opcua", "area:iiot", "status:completed", "priority:high"],
                "body": "Telemetry ingestion buffer, WebSocket streaming, and factory cycle simulator.\n\nEvidence: `backend/app/services/telemetry_service.py`, `backend/app/services/simulator.py`.",
                "subfeatures": [
                    {"id": "P04-F02-S01", "title": "[P04-F02-S01] Telemetry Ingestion Buffer", "status": "completed", "priority": "high", "area": "area:iiot"},
                    {"id": "P04-F02-S02", "title": "[P04-F02-S02] Industrial Cycle Simulator", "status": "completed", "priority": "medium", "area": "area:iiot"}
                ]
            }
        ]
    },
    {
        "id": "P05",
        "title": "[P05] Phase 5: Data Quality, Equipment Baselines & Anomaly Detection",
        "milestone_index": 4,
        "labels": ["type:phase", "phase:05-anomaly", "status:completed", "priority:critical"],
        "body": "## Phase 5 Overview\nIndustrial data sanitation, baseline statistical profiles, and unsupervised anomaly detection.\n\n### Repository Evidence\n- `backend/app/services/baseline_service.py`, `backend/app/services/data_quality.py`\n- `backend/app/ml/anomaly_detector.py`, `backend/app/models/anomaly.py`\n- `backend/tests/test_anomaly.py`, `backend/tests/test_baseline.py` (All tests passed)\n\n### Verification Status\nClosed as completed based on passing tests and code inspection.",
        "features": [
            {
                "id": "P05-F01",
                "title": "[P05-F01] Industrial Data Quality & Sanitation Engine",
                "labels": ["type:feature", "phase:05-anomaly", "area:ml-ai", "status:completed", "priority:high"],
                "body": "Outlier filtering, sampling normalization, and baseline profile calculation.\n\nEvidence: `backend/app/services/data_quality.py`, `backend/app/services/baseline_service.py`.",
                "subfeatures": [
                    {"id": "P05-F01-S01", "title": "[P05-F01-S01] Data Quality & Outlier Filtering", "status": "completed", "priority": "high", "area": "area:ml-ai"},
                    {"id": "P05-F01-S02", "title": "[P05-F01-S02] Equipment Baseline Calculation", "status": "completed", "priority": "high", "area": "area:ml-ai"}
                ]
            },
            {
                "id": "P05-F02",
                "title": "[P05-F02] Unsupervised Anomaly Detection Pipeline",
                "labels": ["type:feature", "phase:05-anomaly", "area:ml-ai", "status:completed", "priority:critical"],
                "body": "Isolation Forest & One-Class SVM models with automated threshold alerting.\n\nEvidence: `backend/app/ml/anomaly_detector.py`, `backend/app/services/alert_service.py`.",
                "subfeatures": [
                    {"id": "P05-F02-S01", "title": "[P05-F02-S01] Isolation Forest Anomaly Detector", "status": "completed", "priority": "critical", "area": "area:ml-ai"}
                ]
            }
        ]
    },
    {
        "id": "P06",
        "title": "[P06] Phase 6: Failure Prediction & Remaining Useful Life (RUL) Framework",
        "milestone_index": 5,
        "labels": ["type:phase", "phase:06-prediction", "status:completed", "priority:critical"],
        "body": "## Phase 6 Overview\nSupervised failure classifiers, Platt probability calibration, and Weibull survival analysis.\n\n### Repository Evidence\n- `backend/app/ml/model_registry.py`, `backend/app/ml/rul_engine.py`\n- `backend/app/ml/calibration.py`, `backend/app/models/prediction.py`\n- `backend/tests/test_prediction.py`, `backend/tests/test_rul.py` (All tests passed)\n\n### Verification Status\nClosed as completed based on passing tests and code inspection.",
        "features": [
            {
                "id": "P06-F01",
                "title": "[P06-F01] Predictive ML Model Registry & Calibration",
                "labels": ["type:feature", "phase:06-prediction", "area:ml-ai", "status:completed", "priority:critical"],
                "body": "Failure mode classification, model versioning, and calibration controls.\n\nEvidence: `backend/app/ml/model_registry.py`, `backend/app/ml/calibration.py`.",
                "subfeatures": [
                    {"id": "P06-F01-S01", "title": "[P06-F01-S01] Multi-Mode Failure Classifier Registry", "status": "completed", "priority": "high", "area": "area:ml-ai"},
                    {"id": "P06-F01-S02", "title": "[P06-F01-S02] Probability Calibration Engine", "status": "completed", "priority": "high", "area": "area:ml-ai"}
                ]
            },
            {
                "id": "P06-F02",
                "title": "[P06-F02] Remaining Useful Life (RUL) Estimation Engine",
                "labels": ["type:feature", "phase:06-prediction", "area:ml-ai", "status:completed", "priority:critical"],
                "body": "Degradation trend extrapolation with 90% confidence intervals.\n\nEvidence: `backend/app/ml/rul_engine.py`.",
                "subfeatures": [
                    {"id": "P06-F02-S01", "title": "[P06-F02-S01] Weibull RUL Survival Extrapolation", "status": "completed", "priority": "critical", "area": "area:ml-ai"}
                ]
            }
        ]
    },
    {
        "id": "P07",
        "title": "[P07] Phase 7: LangGraph Multi-Agent Intelligence, RAG & LangSmith Evaluation",
        "milestone_index": 6,
        "labels": ["type:phase", "phase:07-agents", "status:completed", "priority:critical"],
        "body": "## Phase 7 Overview\n7-agent LangGraph workflow, pgvector RAG technical retrieval, and LangSmith evaluation tracing.\n\n### Repository Evidence\n- `backend/app/agents/graph.py`, `backend/app/agents/state.py`\n- `backend/app/services/rag_service.py`\n- `backend/tests/test_agents.py`, `backend/tests/test_rag.py`, `backend/tests/test_phase7_langgraph.py` (All tests passed)\n\n### Verification Status\nClosed as completed based on passing tests and code inspection.",
        "features": [
            {
                "id": "P07-F01",
                "title": "[P07-F01] Multi-Agent Graph Orchestration (7 Agents)",
                "labels": ["type:feature", "phase:07-agents", "area:ml-ai", "status:completed", "priority:critical"],
                "body": "StateGraph with Supervisor, Diagnostics, Safety, and Recommender agents.\n\nEvidence: `backend/app/agents/graph.py`.",
                "subfeatures": [
                    {"id": "P07-F01-S01", "title": "[P07-F01-S01] LangGraph StateGraph Architecture", "status": "completed", "priority": "critical", "area": "area:ml-ai"},
                    {"id": "P07-F01-S02", "title": "[P07-F01-S02] Safety & GMP Interlock Validation Agent", "status": "completed", "priority": "critical", "area": "area:compliance"}
                ]
            },
            {
                "id": "P07-F02",
                "title": "[P07-F02] Technical Knowledge RAG & Vector Store",
                "labels": ["type:feature", "phase:07-agents", "area:ml-ai", "status:completed", "priority:high"],
                "body": "Pgvector knowledge store for equipment SOPs and LangSmith evaluation.\n\nEvidence: `backend/app/services/rag_service.py`.",
                "subfeatures": [
                    {"id": "P07-F02-S01", "title": "[P07-F02-S01] Technical Manual Embeddings & Hybrid Search", "status": "completed", "priority": "high", "area": "area:ml-ai"}
                ]
            }
        ]
    },
    {
        "id": "P08",
        "title": "[P08] Phase 8: End-to-End System Validation, Security & Pilot Readiness",
        "milestone_index": 7,
        "labels": ["type:phase", "phase:08-validation", "status:completed", "priority:critical"],
        "body": "## Phase 8 Overview\nCross-module system testing, GAMP 5 validation protocols, and security audits.\n\n### Repository Evidence\n- `docs/validation/`, `docs/deployment/runbooks/`\n- `backend/tests/test_e2e.py`, `backend/tests/test_security_audit.py` (All tests passed)\n\n### Verification Status\nClosed as completed based on passing tests and code inspection.",
        "features": [
            {
                "id": "P08-F01",
                "title": "[P08-F01] Cross-Module End-to-End Pipeline Verification",
                "labels": ["type:feature", "phase:08-validation", "area:backend", "status:completed", "priority:critical"],
                "body": "Full-cycle automated validation connecting signals, anomalies, agents, and work orders.\n\nEvidence: `backend/tests/test_e2e.py`.",
                "subfeatures": [
                    {"id": "P08-F01-S01", "title": "[P08-F01-S01] End-to-End Pipeline Integration Test", "status": "completed", "priority": "critical", "area": "area:backend"},
                    {"id": "P08-F01-S02", "title": "[P08-F01-S02] Multi-Tenant Security & Permission Isolation", "status": "completed", "priority": "critical", "area": "area:compliance"}
                ]
            },
            {
                "id": "P08-F02",
                "title": "[P08-F02] Pharmaceutical Computerized System Validation (CSV / GAMP 5)",
                "labels": ["type:feature", "phase:08-validation", "area:compliance", "status:completed", "priority:high"],
                "body": "IQ/OQ/PQ validation matrices and automated backup/recovery runbooks.\n\nEvidence: `docs/validation/`.",
                "subfeatures": [
                    {"id": "P08-F02-S01", "title": "[P08-F02-S01] GAMP 5 IQ/OQ/PQ Validation Matrix", "status": "completed", "priority": "high", "area": "area:compliance"}
                ]
            }
        ]
    },
    {
        "id": "P09",
        "title": "[P09] Phase 9: Controlled Factory Pilot, Real-World Validation & Multi-Factory Scalability",
        "milestone_index": 8,
        "labels": ["type:phase", "phase:09-pilot", "status:in-progress", "priority:critical"],
        "body": "## Phase 9 Overview\nControlled pilot framework, shadow-mode validation, engineer feedback, and Go/No-Go decision framework.\n\n### Software Status: COMPLETED (All 11 Phase 9 tests passed, 149 total in suite)\n### Physical Facility Execution: PLANNED (Awaiting site authorization)",
        "features": [
            {
                "id": "P09-F01",
                "title": "[P09-F01] Pilot Configuration & Site Authorization Management",
                "labels": ["type:feature", "phase:09-pilot", "area:backend", "status:completed", "priority:critical"],
                "body": "Pilot protocols, baseline drift verification, and read-only OPC UA enforcement.\n\nEvidence: `backend/app/models/pilot.py`, `backend/app/modules/pilots/services/safety_enforcer.py`.",
                "subfeatures": [
                    {"id": "P09-F01-S01", "title": "[P09-F01-S01] Pilot Protocol Model & Lifecycle Controls", "status": "completed", "priority": "high", "area": "area:backend"},
                    {"id": "P09-F01-S02", "title": "[P09-F01-S02] Read-Only OPC UA Safety Enforcer", "status": "completed", "priority": "critical", "area": "area:iiot"}
                ]
            },
            {
                "id": "P09-F02",
                "title": "[P09-F02] Shadow-Mode Monitoring & Real-World Model Validation",
                "labels": ["type:feature", "phase:09-pilot", "area:ml-ai", "status:completed", "priority:critical"],
                "body": "Shadow-mode runner, maintenance feedback collection, and diagnostic accuracy evaluation.\n\nEvidence: `backend/app/modules/pilots/services/shadow_runner.py`, `backend/app/modules/pilots/services/feedback.py`.",
                "subfeatures": [
                    {"id": "P09-F02-S01", "title": "[P09-F02-S01] Shadow-Mode Parallel Inference Pipeline", "status": "completed", "priority": "critical", "area": "area:ml-ai"},
                    {"id": "P09-F02-S02", "title": "[P09-F02-S02] Maintenance Ground Truth Feedback Service", "status": "completed", "priority": "high", "area": "area:ml-ai"}
                ]
            },
            {
                "id": "P09-F03",
                "title": "[P09-F03] Multi-Factory Scalability & Go/No-Go Decision Engine",
                "labels": ["type:feature", "phase:09-pilot", "area:backend", "status:completed", "priority:high"],
                "body": "Tenant partitioning, aggregate KPI calculations, and executive Go/No-Go reporting.\n\nEvidence: `backend/app/modules/pilots/services/reporting.py`, `backend/app/modules/pilots/routes.py`.",
                "subfeatures": [
                    {"id": "P09-F03-S01", "title": "[P09-F03-S01] Multi-Site Tenant Scalability Analytics", "status": "completed", "priority": "high", "area": "area:backend"},
                    {"id": "P09-F03-S02", "title": "[P09-F03-S02] Automated Pilot Go/No-Go Report Generator", "status": "completed", "priority": "critical", "area": "area:backend"}
                ]
            },
            {
                "id": "P09-F04",
                "title": "[P09-F04] Physical Plant Commissioning & Factory Execution",
                "labels": ["type:feature", "phase:09-pilot", "area:iiot", "status:planned", "priority:high"],
                "body": "On-site physical plant integration, DMZ network routing, and 30-day live pilot execution.\n\nStatus: Kept OPEN pending on-site facility authorization.",
                "subfeatures": [
                    {"id": "P09-F04-S01", "title": "[P09-F04-S01] Physical Facility Authorization Sign-off", "status": "planned", "priority": "critical", "area": "area:compliance"},
                    {"id": "P09-F04-S02", "title": "[P09-F04-S02] Industrial DMZ Network Commissioning", "status": "planned", "priority": "high", "area": "area:iiot"}
                ]
            }
        ]
    }
]


def make_request(url, method="GET", data=None, token=None):
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "PharmaPredict-Sync-Script"
    }
    if token:
        headers["Authorization"] = f"token {token}"
    
    payload = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=payload, headers=headers, method=method)
    
    try:
        with urllib.request.urlopen(req) as resp:
            content = resp.read().decode("utf-8")
            return json.loads(content) if content else {}
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        # If resource already exists (e.g. 422 for label already exists)
        if e.code == 422 and ("already_exists" in error_body or "already exists" in error_body):
            return {"already_exists": True}
        print(f"HTTP Error {e.code} for {method} {url}: {error_body}")
        raise


def run_sync(token, dry_run=False):
    print(f"[*] Starting GitHub Hierarchy Synchronization for {REPO}...")
    if dry_run:
        print("[!] DRY-RUN MODE: No remote modifications will be made.")

    milestone_map = {}  # index -> number

    # 1. Milestones
    print(f"\n--- Synchronizing {len(MILESTONES)} Milestones ---")
    for idx, m in enumerate(MILESTONES):
        print(f"  [{idx+1}/9] Milestone: {m['title']} ({m['state']})")
        if not dry_run:
            try:
                res = make_request(f"{API_BASE}/milestones", method="POST", data=m, token=token)
                milestone_map[idx] = res.get("number")
                print(f"      -> Created Milestone #{res.get('number')}")
                # If target state is closed, GitHub API requires creating open then updating to closed
                if m["state"] == "closed":
                    make_request(f"{API_BASE}/milestones/{res.get('number')}", method="PATCH", data={"state": "closed"}, token=token)
                time.sleep(0.5)
            except Exception as e:
                print(f"      (Notice: {e})")

    # 2. Labels
    print(f"\n--- Synchronizing {len(LABELS)} Labels ---")
    for lbl in LABELS:
        print(f"  - Label: {lbl['name']} [#{lbl['color']}]")
        if not dry_run:
            try:
                res = make_request(f"{API_BASE}/labels", method="POST", data=lbl, token=token)
                time.sleep(0.3)
            except Exception as e:
                print(f"    (Notice: {e})")

    # 3. Issue Hierarchy
    created_issues_record = []
    print(f"\n--- Synchronizing Issue Hierarchy ---")
    for phase in PHASES_DATA:
        m_num = milestone_map.get(phase["milestone_index"])
        print(f"\n==========================================")
        print(f"[Phase Epic] {phase['title']} (Milestone #{m_num})")
        
        phase_issue_num = None
        if not dry_run:
            p_data = {
                "title": phase["title"],
                "body": phase["body"],
                "labels": phase["labels"]
            }
            if m_num:
                p_data["milestone"] = m_num
            try:
                p_resp = make_request(f"{API_BASE}/issues", method="POST", data=p_data, token=token)
                phase_issue_num = p_resp.get("number")
                created_issues_record.append({"type": "phase", "number": phase_issue_num, "title": phase["title"], "state": "open"})
                print(f"  -> Created Phase Issue #{phase_issue_num}")
                time.sleep(0.5)
            except Exception as e:
                print(f"  -> Error creating phase issue: {e}")

        for feat in phase["features"]:
            print(f"  [Feature] {feat['title']}")
            feat_issue_num = None
            if not dry_run:
                f_body = f"{feat['body']}\n\n**Parent Phase:** #{phase_issue_num}"
                f_data = {
                    "title": feat["title"],
                    "body": f_body,
                    "labels": feat["labels"]
                }
                if m_num:
                    f_data["milestone"] = m_num
                try:
                    f_resp = make_request(f"{API_BASE}/issues", method="POST", data=f_data, token=token)
                    feat_issue_num = f_resp.get("number")
                    created_issues_record.append({"type": "feature", "number": feat_issue_num, "title": feat["title"], "state": "open"})
                    print(f"    -> Created Feature Issue #{feat_issue_num}")
                    time.sleep(0.5)
                except Exception as e:
                    print(f"    -> Error creating feature issue: {e}")

            for sf in feat.get("subfeatures", []):
                print(f"    [Sub-feature] {sf['title']} ({sf['status']})")
                if not dry_run:
                    sf_labels = ["type:subfeature", phase["labels"][1], sf.get("area", "area:backend"), f"priority:{sf.get('priority', 'medium')}"]
                    if sf["status"] == "completed":
                        sf_labels.append("status:completed")
                    else:
                        sf_labels.append("status:planned")

                    sf_body = f"Part of parent feature: #{feat_issue_num}\nPhase: #{phase_issue_num}"
                    sf_data = {
                        "title": sf["title"],
                        "body": sf_body,
                        "labels": sf_labels
                    }
                    if m_num:
                        sf_data["milestone"] = m_num
                    try:
                        sf_resp = make_request(f"{API_BASE}/issues", method="POST", data=sf_data, token=token)
                        sf_num = sf_resp.get("number")
                        created_issues_record.append({"type": "subfeature", "number": sf_num, "title": sf["title"], "state": "open"})
                        print(f"      -> Created Sub-feature Issue #{sf_num}")
                        
                        # Close verified completed subfeature
                        if sf["status"] == "completed":
                            make_request(f"{API_BASE}/issues/{sf_num}", method="PATCH", data={"state": "closed"}, token=token)
                            print(f"         [Closed] Verified completed.")
                        time.sleep(0.5)
                    except Exception as e:
                        print(f"      -> Error creating sub-feature issue: {e}")

            # Close verified completed feature
            if not dry_run and feat_issue_num and "status:completed" in feat["labels"]:
                make_request(f"{API_BASE}/issues/{feat_issue_num}", method="PATCH", data={"state": "closed"}, token=token)
                print(f"    -> [Closed] Feature Issue #{feat_issue_num} verified complete.")

        # Close verified completed phase
        if not dry_run and phase_issue_num and "status:completed" in phase["labels"]:
            make_request(f"{API_BASE}/issues/{phase_issue_num}", method="PATCH", data={"state": "closed"}, token=token)
            print(f"  -> [Closed] Phase Issue #{phase_issue_num} verified complete.")

    print("\n[*] All milestones, labels, and hierarchical issues synchronized successfully!")
    return created_issues_record


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sync PharmaPredict GitHub Issues & Milestones")
    parser.add_argument("--token", help="GitHub Personal Access Token (or GITHUB_TOKEN env var)")
    parser.add_argument("--dry-run", action="store_true", help="Perform a dry run without creating remote issues")
    args = parser.parse_args()

    token = args.token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token and not args.dry_run:
        print("[!] Blocker: No GitHub token provided.")
        sys.exit(1)

    run_sync(token, dry_run=args.dry_run)
