# PharmaPredict AI — Design Specification (DS)

**Document Reference:** DS-PHARMAPREDICT-001  
**Version:** 1.0.0  
**Effective Date:** 2026-11-01  
**Traceability:** Implements requirements defined in [FS-PHARMAPREDICT-001](file:///c:/Users/Dell/OneDrive/Desktop/AI%20SOLUTION%20PROJECT/docs/validation/fs.md)

---

## 1. System Technology Stack & Architectural Boundaries

```
                      ┌────────────────────────────────────────┐
                      │    Client Tier (Browser / HMI Panel)   │
                      │  Next.js 14 / React 18 / Tailwind CSS  │
                      └───────────────────┬────────────────────┘
                                          │ HTTPS (TLS 1.3)
                                          ▼
                      ┌────────────────────────────────────────┐
                      │    Application Tier (Flask Backend)    │
                      │ Python 3.13 / Flask 3.0 / SQLAlchemy   │
                      │  - Multi-Tenant RBAC Middleware        │
                      │  - Correlation ID / Security Headers   │
                      │  - LangGraph Multi-Agent Orchestrator  │
                      └──────────────┬───────────────────┬─────┘
                                     │                   │
                     SQL / pgvector  │                   │ OPC UA (opc.tcp://)
                                     ▼                   ▼
     ┌──────────────────────────────────────┐     ┌────────────────────────┐
     │           Data Tier                  │     │ Industrial Edge Tier   │
     │ PostgreSQL 16 + TimescaleDB + pgvector│    │ OPC UA Server Gateways │
     │  - Relational Master Metadata        │     │ Edge Buffer (24h disk) │
     │  - Hypertables: signal_readings      │     │ Read-Only Security Tap │
     │  - Vector Embeddings: 384-dim SOPs   │     └────────────────────────┘
     └──────────────────────────────────────┘
```

---

## 2. Database Schema & Data Models

### 2.1 Multi-Tenant Hierarchy
- `organizations`: Multi-tenant boundary root (`id`, `name`, `slug`, `tier`, `is_active`).
- `sites`: Physical plant locations (`id`, `organization_id`, `name`, `country`, `timezone`).
- `production_areas`: Manufacturing suites/cleanrooms (`id`, `site_id`, `name`, `cleanroom_class`).
- `production_lines`: Packaging/formulation lines (`id`, `production_area_id`, `name`).
- `machines`: Universal equipment registry (`id`, `asset_code`, `equipment_name`, `criticality`).
- `machine_components`: Physical component tree (`id`, `machine_id`, `component_name`, `component_type`).

### 2.2 Telemetry & Time-Series (TimescaleDB)
- `signal_readings`: Hypertable partitioned on `timestamp`:
  - `time`: TIMESTAMPTZ (chunk interval: 7 days)
  - `machine_signal_id`: UUID (Foreign key)
  - `numeric_value`: DOUBLE PRECISION
  - `quality_code`: VARCHAR(32) (GOOD, BAD, UNCERTAIN)
  - `metadata`: JSONB

### 2.3 Diagnostic Sessions & LangGraph Entities
- `diagnostic_sessions`: Audit record of full agent executions (`id`, `machine_id`, `status`, `current_stage`, `session_metadata`).
- `agent_executions`: Fine-grained per-agent execution logs (`id`, `diagnostic_session_id`, `agent_name`, `status`, `duration_ms`, `summary`).
- `knowledge_documents`: Technical manuals and SOP chunks with pgvector embeddings (`id`, `title`, `document_type`, `content`, `embedding`).
- `maintenance_recommendations`: Action items requiring human approval (`id`, `diagnostic_session_id`, `title`, `priority`, `compliance_state`, `requires_engineer_approval`).
- `recommendation_approvals`: 21 CFR Part 11 electronic signature trail (`id`, `recommendation_id`, `user_id`, `approval_action`, `comments`, `signed_at`).
- `diagnostic_reports`: Formatted executive and engineering diagnostic reports (`id`, `diagnostic_session_id`, `executive_summary`, `condition_summary`, `prediction_summary`).

---

## 3. Network Zones & Security Architecture (Purdue Enterprise Model)

| Purdue Level | Network Zone | System Components | Security Controls |
|:---|:---|:---|:---|
| **Level 0/1** | Physical Process | Sensors, Transducers, Actuators | Hardware interlocks, galvanic isolation. |
| **Level 2** | Area Control | PLCs, HMIs, OPC UA Servers | Read-only OPC UA user accounts, disabled write tags. |
| **Level 3** | Plant Operations | Edge Ingestion Gateway, Edge Buffer | Industrial firewall, mutual TLS, read-only data diode. |
| **Level 4** | Enterprise DMZ | Flask API, TimescaleDB, Next.js Web | Reverse proxy (NGINX), JWT authentication, RBAC, WAF. |

---

## 4. Cryptography, Audit & Data Integrity Standards

1. **In-Transit Security:** All REST endpoints and OPC UA channels communicate over TLS 1.3 / Basic256Sha256 with strong cipher suites (`TLS_AES_256_GCM_SHA384`).
2. **At-Rest Encryption:** AES-256 database volume encryption for PostgreSQL and TimescaleDB partitions.
3. **Audit Trails (21 CFR §11.10):** All changes to machine configurations, baseline thresholds, model approvals, and maintenance decisions append immutable records with user ID and UTC timestamp.
4. **Disaster Recovery:** Automated backup script (`database_backup_restore.py`) computes cryptographic SHA-256 manifests ensuring ALCOA+ compliance.

