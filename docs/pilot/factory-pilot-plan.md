# PharmaPredict AI — Controlled Factory Pilot Plan (Shadow Mode)

**Document Reference:** PILOT-PHARMAPREDICT-001  
**Version:** 1.0.0  
**Effective Date:** 2026-11-01  
**Target Facility:** Getz Pharma Solid Oral Dosage Facility (Site 1, Packaging Area)  
**Target Candidate Asset:** Uhlmann UPS 1070 Blister Packaging Machine (`BLIST-VAL-01`)  
**Deployment Mode:** Strict Non-Interfering Shadow Mode (Read-Only)

---

## 1. Pilot Purpose & Guiding Principles

The objective of this 12-week controlled factory pilot is to validate PharmaPredict AI against real-world industrial pharmaceutical operations without introducing risk to product quality, batch yields, cleanroom environmental controls, or personnel safety.

### Core Pilot Principles:
1. **Zero Batch Interruption:** PharmaPredict AI runs strictly in read-only shadow mode. No control signals, setpoint adjustments, or automated shutoff commands are transmitted to production machinery.
2. **Parallel Operations:** Existing plant preventive maintenance procedures, manual rounds, and CMMS schedules remain 100% authoritative throughout the pilot duration.
3. **Continuous Engineering Oversight:** All AI-generated alerts and recommendations are reviewed by certified site reliability engineers before any physical maintenance action is undertaken.

---

## 2. 12-Week Pilot Phased Timeline

```
Week:   1   2   3   4   5   6   7   8   9   10  11  12
        [─── Stage 1 ───]
            Site Prep & Connectivity
                [─────── Stage 2 ───────]
                    Baseline Ingestion & Telemetry Audit
                                [─────── Stage 3 ───────]
                                    Shadow Anomaly & Diagnostic Review
                                                [─── Stage 4 ───]
                                                    Final Pilot Assessment
```

### Stage 1: Site Readiness & Network Hardening (Weeks 1–2)
- Deploy industrial on-premises Edge Gateway (Dell Edge Gateway 3002 or Advantech IPC).
- Establish physical connection to Packaging Area Level 2 OT network switch via dedicated VLAN.
- Configure hardware read-only data diode or firewall blocking all outbound packets from Enterprise DMZ to OT Level 1/2.
- Configure dedicated OPC UA service account on Uhlmann PLC with read-only permissions on mapped tags (Vibration, Bearing Temperature, Drive Motor Speed, Sealing Jaw Pressure).
- Verify secure `Basic256Sha256` certificate exchange.

### Stage 2: Telemetry Ingestion & Baseline Calibration (Weeks 3–4)
- Initiate continuous 2 Hz sensor telemetry collection into TimescaleDB `signal_readings` hypertable.
- Execute automated Data Quality filtering to detect sensor noise, flatlines, or network dropouts.
- Record 300+ continuous operating hours across normal commercial blister packaging batch campaigns.
- Formulate and review steady-state statistical baselines (mean, variance, 3-sigma boundaries) across distinct operating contexts (`STOPPED`, `IDLE`, `RUNNING_PRODUCTION`).
- Plant Reliability Engineer formally approves operating baselines.

### Stage 3: Shadow Anomaly Detection & AI Diagnostic Evaluation (Weeks 5–10)
- Activate dual-layer anomaly detection (3-Sigma statistical + Isolation Forest ML).
- When anomalies are detected, the LangGraph 7-agent pipeline automatically triggers:
  1. Validates telemetry data quality.
  2. Assesses physical severity.
  3. Queries model registry for calibrated failure risk.
  4. Retrieves relevant technical SOPs and manuals via pgvector semantic RAG.
  5. Proposes maintenance action with mandatory OSHA LOTO and cleanroom PPE protocols.
  6. Compiles auditable diagnostic report.
- Daily Review Ritual: Site Reliability Engineer spends 15 minutes reviewing generated diagnostic sessions, rating accuracy (`VALID_ANOMALY`, `FALSE_POSITIVE`, `OPERATING_MODE_CHANGE`).

### Stage 4: Pilot Audit, KPI Evaluation & Transition (Weeks 11–12)
- Collate pilot metrics against quantitative success criteria.
- Conduct formal FMEA review with Quality Assurance and Plant Maintenance leadership.
- Finalize Factory Pilot Summary Report and issue production deployment recommendation.

---

## 3. Quantitative Pilot Success Criteria

| KPI Metric | Measurement Method | Target Objective | Pilot Threshold |
|:---|:---|:---:|:---:|
| **Telemetry Ingestion Uptime** | TimescaleDB timestamp continuity | $\ge 99.5\%$ | $\ge 98.0\%$ |
| **Data Quality False Alarm Suppression** | Data quality halting audit | 100% flatlines suppressed | 100% |
| **Anomaly Detection Precision** | Validated by Reliability Engineer | $\ge 85\%$ true anomalies | $\ge 75\%$ |
| **RAG SOP Retrieval Relevance** | Mean Reciprocal Rank (MRR) of cited docs | $\ge 0.85$ | $\ge 0.70$ |
| **Safety Rule Compliance** | Automated LOTO & PPE enforcement rate | **100%** | **100% (Zero Tolerance)** |
| **Production Disruption Events** | Plant deviation logbook | **0 events** | **0 events** |

---

## 4. Stakeholder Roles & Governance Matrix

| Role | Organization / Department | Pilot Responsibility |
|:---|:---|:---|
| **Pilot Sponsor** | Plant Technical Director | Overall pilot approval, resource allocation, and final sign-off. |
| **Site Reliability Engineer** | Plant Maintenance Department | Daily anomaly review, baseline sign-off, feedback logging. |
| **Lead IoT Architect** | PharmaPredict AI Team | Gateway connectivity, OPC UA tag discovery, TimescaleDB tuning. |
| **AI Validation Specialist** | PharmaPredict AI Team | LangGraph agent evaluation, RAG accuracy tracking, metric aggregation. |
| **Pharmaceutical QA Officer** | Quality Assurance Department | GAMP 5 compliance oversight, 21 CFR Part 11 audit verification. |

