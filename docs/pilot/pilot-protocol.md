# PharmaPredict AI — Controlled Factory Pilot Protocol

**Document Reference:** PROTOCOL-PHARMAPREDICT-P9  
**Version:** 1.0.0  
**Effective Date:** 2026-11-01  
**Target Facility:** Getz Pharma Solid Oral Dosage Facility (Site 1, Packaging Area)  
**Target Equipment:** Uhlmann UPS 1070 Blister Packaging Machine (`PILOT-UHL-01`)  
**Deployment Classification:** GAMP 5 Category 4 / Non-GxP Direct Impact / Strict Shadow Mode

---

## 1. Protocol Objective & Ethical Principles

This protocol defines the formal requirements, technical prerequisites, and operational safeguards governing the controlled factory pilot of PharmaPredict AI.

### Guiding Principles:
1. **Zero Production Risk:** The platform connects strictly via read-only OPC UA channels. No control loops, setpoint registers, or actuators shall be modified.
2. **Parallel Operations:** Existing plant preventive maintenance routines and manual lubrication schedules remain 100% authoritative.
3. **Multi-Department Authorization:** Pilot activation requires explicit electronic signatures from Plant Engineering, IT/OT Security, and Pharmaceutical Quality Assurance.

---

## 2. Equipment Selection & Onboarding Assessment

| Evaluation Criterion | Specification | Verification Evidence | Sign-off |
|:---|:---|:---|:---:|
| **Asset Identity** | Uhlmann UPS 1070 High-Speed Blister Machine | Nameplate serial verified; asset code `PILOT-UHL-01`. | Verified |
| **Criticality** | Class A / Production Critical | Bottleneck asset on blister packaging line. | Verified |
| **PLC Interface** | Siemens S7-1500 with integrated OPC UA Server | Firmware v2.8+; standard `opc.tcp://192.168.10.50:4840`. | Verified |
| **Security Configuration** | `Basic256Sha256` + X.509 Certificate Handshake | Read-only user account (`pp_shadow_collector`). | Verified |
| **Candidate Signals** | 4 Critical Channels: Vibration RMS, Motor Temp, Current, Sealing Pressure | Wired to calibrated piezoelectric sensors & RTDs. | Verified |

---

## 3. Strict Read-Only Industrial Architecture

```
[ Uhlmann S7-1500 PLC ] 
          │ (Read-Only OPC UA Tags)
          ▼
[ Hardware Unidirectional Data Diode / Firewall ]
          │ (opc.tcp:// Port 4840)
          ▼
[ Industrial Edge Gateway (Purdue Level 3 DMZ) ]
  - Ingestion Client (AsyncIO)
  - 24-hour Local Store-and-Forward Buffer
          │ HTTPS / TLS 1.3
          ▼
[ TimescaleDB & LangGraph Diagnostic Server ]
```

### Prohibited Actions (Architecturally Blocked):
- PLC tag write operations.
- Remote motor start or emergency stop triggering.
- Automatic dispatch of CMMS work orders without manual review.
- Overwriting approved baseline parameters with transient telemetry.

---

## 4. Multi-Department Digital Sign-off Matrix

| Role | Verification Responsibility | Mandatory for Activation? |
|:---|:---|:---:|
| **Site Reliability Engineer** | Mechanical baseline verification, sensor calibration, and sampling adequacy. | **YES (Mandatory)** |
| **IT/OT Security Officer** | Network segmentation, VLAN routing, and read-only credential verification. | **YES (Mandatory)** |
| **Quality Assurance (QA)** | 21 CFR Part 11 electronic signature audit, GAMP 5 software categorization. | **YES (Mandatory)** |
| **Plant Technical Director** | Final site-level pilot authorization and resource allocation. | Recommended |

*In accordance with Phase 9 security controls, `PilotService.activate_pilot()` deterministically blocks execution with HTTP 403 if Engineering and IT/OT Security sign-offs are absent.*

