# PharmaPredict AI — Phase 7: LangGraph Multi-Agent Intelligence, RAG & Decision Support

## 1. Executive Summary

Phase 7 elevates PharmaPredict AI from an equipment condition monitoring and failure prediction platform into an intelligent, autonomous decision-support system tailored for regulated pharmaceutical manufacturing environments.

Using **LangGraph**, **LangChain**, and **RAG (Retrieval-Augmented Generation)**, the platform coordinates seven specialized industrial agents into a stateful, conditional diagnostic workflow. The system investigates machine anomalies, cross-references technical standard operating procedures (SOPs) and OEM equipment manuals, identifies probable physical root causes, evaluates deterministic safety protocols (LOTO, cleanroom containment, electrical isolation), and generates auditable diagnostic dossiers for human maintenance engineers.

In strict alignment with **FDA 21 CFR Part 11**, **GAMP 5 Category 4**, and **OSHA 1910.147**, all generated recommendations require human engineer authorization before work orders are staged. AI agents are strictly isolated to **read-only industrial boundaries** and possess zero automated write access to PLCs or equipment actuators.

---

## 2. Multi-Agent Architecture (LangGraph Workflow)

The diagnostic workflow is modeled as a compiled stateful DAG (`StateGraph(DiagnosticState)`) with memory checkpointing (`MemorySaver`) and audit trail synchronization to PostgreSQL.

```
                  ┌────────────────────────┐
                  │         START          │
                  └───────────┬────────────┘
                              │
                              ▼
                  ┌────────────────────────┐
                  │ 1. Data Quality Agent  │
                  └───────────┬────────────┘
                              │
                [Reliable?]  ─┴─  [Unreliable?]
               /                               \
              ▼                                 ▼
┌───────────────────────────┐       ┌───────────────────────┐
│ 2. Condition Monitor Agent│       │                       │
└─────────────┬─────────────┘       │                       │
              │                     │                       │
         [Abnormal?]  [Normal?]     │                       │
        /                      \    │                       │
       ▼                        ▼   │                       │
┌───────────────────────────┐   │   │                       │
│ 3. Failure Predict Agent  │   │   │                       │
└─────────────┬─────────────┘   │   │                       │
              │                 │   │                       │
              ▼                 │   │                       │
┌───────────────────────────┐   │   │                       │
│ 4. Root Cause Agent (RAG) │   │   │                       │
└─────────────┬─────────────┘   │   │                       │
              │                 │   │                       │
         [Hypotheses?]          │   │                       │
        /             \         │   │                       │
       ▼               ▼        │   │                       │
┌──────────────┐       │        │   │                       │
│ 5. Maint Rec │       │        │   │                       │
└──────┬───────┘       │        │   │                       │
       │               │        │   │                       │
       ▼               │        │   │                       │
┌──────────────┐       │        │   │                       │
│ 6. Compliance│       │        │   │                       │
└──────┬───────┘       │        │   │                       │
       │               │        │   │                       │
       └───────┬───────┴────────┴───┤
               ▼                    │
      ┌─────────────────┐           │
      │ 7. Report Agent │◄──────────┘
      └────────┬────────┘
               │
               ▼
      ┌─────────────────┐
      │       END       │
      └─────────────────┘
```

### Conditional Routing Rules
1. **Data Quality Gate:** If telemetry quality is compromised or sensor noise exceeds thresholds, deep analytical execution is aborted immediately, jumping directly to Agent 7 with an untrusted-telemetry warning.
2. **Normal Baseline Bypass:** If operational signals are within normal 3-sigma statistical envelopes and anomaly score is $< 0.20$, the pipeline skips predictive modeling and root-cause analysis, producing a healthy baseline verification report.
3. **No-Hypothesis Bypass:** If technical RAG retrieval yields zero matching failure mechanisms, recommendation generation is bypassed to prevent AI hallucination.

---

## 3. The Seven Specialized Industrial Agents

| Agent Node | Class Name | Core Responsibility | Failure Mode / Boundary Check |
|---|---|---|---|
| **1. Data Quality** | `DataQualityAgent` | Validates sensor freshness, flatlines, range violations, and OPC UA quality codes. | Aborts workflow if telemetry validity ratio $< 0.70$. |
| **2. Condition Monitoring** | `ConditionMonitoringAgent` | Synthesizes current health score, anomaly severity, and baseline deviations. | Categorizes condition state into `NORMAL`, `WARNING`, `CRITICAL`. |
| **3. Failure Prediction** | `FailurePredictionAgent` | Retrieves validated Weibull survival RUL and calibrated supervised probability. | **Zero-Hallucination:** Returns `PREDICTION_UNAVAILABLE` when eligibility criteria are not met. Never invents probabilities. |
| **4. Root Cause Analysis** | `RootCauseAnalysisAgent` | Vector similarity retrieval across technical manuals, SOPs, and historical confirmed failure logs. | Cross-references observed sensor symptoms against cited technical documents. |
| **5. Maintenance Recommendation** | `MaintenanceRecommendationAgent` | Formulates specific physical intervention steps, component targeting, and priority. | Enforces `requires_engineer_approval = True` on all outputs. |
| **6. Compliance & Safety** | `ComplianceSafetyAgent` | Deterministic safety rule engine: OSHA LOTO, NFPA 70E Arc-Flash, Cleanroom Class C / ISO 7. | **Hard-Block:** Prohibits automated PLC write commands (`write plc`, `remote start`, etc.). |
| **7. Reporting** | `ReportingAgent` | Compiles comprehensive, auditable diagnostic dossier separating observations from hypotheses. | Appends mandatory FDA 21 CFR Part 11 disclaimer and technical limitations. |

---

## 4. RAG Pipeline & Multi-Tenant Knowledge Architecture

Pharmaceutical plants require air-gap compatibility and strict isolation of proprietary recipes and maintenance manuals:

### 4.1 Embedding Generation (`EmbeddingProvider`)
- **Default Air-Gapped Mode:** Deterministic 128-dimensional semantic hash projection vector normalized via L2 norm. Operates with zero network latency, zero external API keys, and 100% reproducibility across offline factory nodes.
- **Cloud LLM Mode:** Pluggable integration with `text-embedding-3-small` when `OPENAI_API_KEY` is present.

### 4.2 Security & Multi-Tenant Isolation (`TechnicalKnowledgeStore`)
- **Tenant Filtering:** Standard pharmaceutical SOPs (`is_standard = True`) are accessible across all tenants. Proprietary plant manuals (`is_standard = False`) are strictly filtered by `organization_id == user_organization_id` before similarity calculation.
- **Prompt Injection Defense (`KnowledgeSecurityFilter`):** Documents and user queries pass through regex-based adversarial sanitization neutralizing instructions such as `ignore previous instructions`, `system: override`, and delimiter breakouts before vectorization or LLM prompt formatting.

---

## 5. Human-in-the-Loop Review & Work Order Authorization

To comply with pharmaceutical Good Automated Manufacturing Practice (GAMP 5):

```
AI Recommendation (PENDING_REVIEW)
           │
     ┌─────┴──────────────────┐
     ▼                        ▼
[Engineer Approves]     [Engineer Rejects]
     │                        │
     ├─ Requires Notes        ├─ Mandatory Justification
     ├─ Optional Tech Assign  ├─ Preserved in Audit Log
     ├─ Target Due Date       └─ Status: REJECTED
     ▼
Work Order Reference Generated (e.g. WO-BLIST-E489A1)
Status: APPROVED
```

1. **Authorization Action:** Human engineer reviews recommendation, assigns technician and maintenance shift window, and authorizes execution. The backend generates a unique work order reference and writes an immutable audit record in `recommendation_approvals`.
2. **Rejection Action:** Human engineer provides a mandatory GMP justification reason (e.g., *“Component replaced 24 hours prior; discrepancy traced to sensor zero-offset”*).

---

## 6. REST API Endpoints

### 6.1 Equipment Diagnostics
- `POST /api/v1/diagnostics/start` — Initiates an automated multi-agent diagnostic run for an equipment asset.
- `GET /api/v1/diagnostics/sessions` — Lists recent diagnostic sessions filtered by machine.
- `GET /api/v1/diagnostics/<id>` — Retrieves full session details including executions, recommendations, and report.
- `GET /api/v1/diagnostics/<id>/status` — Lightweight polling status endpoint.
- `GET /api/v1/diagnostics/<id>/report` — Retrieves synthesized GMP diagnostic report.
- `GET /api/v1/diagnostics/<id>/agent-executions` — Retrieves step-by-step logs and execution times for all 7 agents.
- `POST /api/v1/diagnostics/<id>/review` — Human engineer sign-off on overall diagnostic session.

### 6.2 Maintenance Recommendations
- `GET /api/v1/maintenance/recommendations` — Lists recommendations filtered by machine, priority, and approval status.
- `GET /api/v1/maintenance/recommendations/<id>` — Retrieves single recommendation with approval history.
- `POST /api/v1/maintenance/recommendations/<id>/approve` — Authorizes recommendation and generates work order stub.
- `POST /api/v1/maintenance/recommendations/<id>/reject` — Rejects recommendation with mandatory justification.

### 6.3 Technical Knowledge & SOPs
- `GET /api/v1/knowledge/documents` — Lists accessible technical documents and SOPs.
- `POST /api/v1/knowledge/documents` — Indexes and vectorizes a new technical manual or SOP.
- `GET /api/v1/knowledge/documents/<id>` — Retrieves document chunks and vector metadata.
- `POST /api/v1/knowledge/retrieve-test` — Tests semantic vector similarity search against technical documents.

---

## 7. Verification Test Suite Results

The comprehensive test suite in `backend/tests/test_phase7_langgraph.py` validates all Phase 7 components under automated CI conditions:

```
backend/tests/test_phase7_langgraph.py::test_data_quality_agent PASSED                   [  6%]
backend/tests/test_phase7_langgraph.py::test_condition_monitoring_agent PASSED           [ 13%]
backend/tests/test_phase7_langgraph.py::test_failure_prediction_agent_respects_eligibility PASSED [ 20%]
backend/tests/test_phase7_langgraph.py::test_compliance_safety_agent_enforces_loto_and_blocks_actuation PASSED [ 26%]
backend/tests/test_phase7_langgraph.py::test_reporting_agent_generates_explainable_report PASSED [ 33%]
backend/tests/test_phase7_langgraph.py::test_routing_aborts_on_unreliable_data PASSED    [ 40%]
backend/tests/test_phase7_langgraph.py::test_routing_bypasses_deep_analysis_on_normal_baseline PASSED [ 46%]
backend/tests/test_phase7_langgraph.py::test_rag_chunking_and_deterministic_embeddings PASSED [ 53%]
backend/tests/test_phase7_langgraph.py::test_rag_prompt_injection_sanitization PASSED   [ 60%]
backend/tests/test_phase7_langgraph.py::test_rag_multi_tenant_isolation PASSED          [ 66%]
backend/tests/test_phase7_langgraph.py::test_recommendation_approval_workflow PASSED    [ 73%]
backend/tests/test_phase7_langgraph.py::test_evaluators_safety_and_grounding PASSED      [ 80%]
backend/tests/test_phase7_langgraph.py::test_langsmith_client_offline_fallback PASSED   [ 86%]
backend/tests/test_phase7_langgraph.py::test_diagnostic_api_flow PASSED                 [ 93%]
backend/tests/test_phase7_langgraph.py::test_knowledge_api_flow PASSED                  [100%]

============================= 15 passed in 1.13s ==============================
```

Combined Regression Suite (Phases 5, 6, and 7): **33 / 33 passed** (0 failures, 0 regressions).
TypeScript Compilation (`tsc --noEmit`): **Clean (0 errors)**.

