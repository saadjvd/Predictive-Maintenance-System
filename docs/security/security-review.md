# PharmaPredict AI — Security Review & Threat Assessment

**Document Reference:** SEC-PHARMAPREDICT-001  
**Version:** 1.0.0  
**Effective Date:** 2026-11-01  
**Frameworks:** STRIDE Threat Modeling, OWASP API Security Top 10 (2023), ISA/IEC 62443 (Industrial Automation Cybersecurity)

---

## 1. STRIDE Threat Modeling & Countermeasures

| Threat Category | Industrial / AI Specific Risk Scenario | Engineering Countermeasure in PharmaPredict AI | Status |
|:---|:---|:---|:---:|
| **Spoofing** | Attacker impersonates plant reliability engineer to authorize unauthorized machine work order. | Strict JWT signature verification with 60-minute expiry; dual-factor re-authentication for critical approvals; X.509 certificate exchange on OPC UA endpoints. | **MITIGATED** |
| **Tampering** | Attacker modifies historical sensor readings in TimescaleDB or intercepts in-transit OPC UA telemetry. | TLS 1.3 enforced on all REST endpoints; `Basic256Sha256` encryption on OPC UA; SHA-256 integrity hashing on database backups; immutable audit log tables. | **MITIGATED** |
| **Repudiation** | Engineer claims an AI recommendation was approved automatically without human consent. | 21 CFR Part 11 compliant `recommendation_approvals` table records user ID, timestamp, approval comments, and cryptographic token. | **MITIGATED** |
| **Information Disclosure** | Multi-tenant data leakage exposing machine operational speeds or batch schedules across pharmaceutical companies. | Mandatory tenant scoping on all SQLAlchemy queries; JWT tenant claims validation; vector embedding metadata scoping (`organization_id`). Tested in Phase 8 Scenario H. | **MITIGATED** |
| **Denial of Service** | Telemetry flooding attacks on the ingestion endpoint to exhaust application database connections. | Reverse proxy rate limiting; asynchronous collection queue; connection pooling via SQLAlchemy; TimescaleDB chunk compression. | **MITIGATED** |
| **Elevation of Privilege** | Maintenance technician attempts to promote account to Organization Admin or access plant-wide settings. | Strict `@role_required` decorators across Flask endpoints verifying hierarchical role permissions; validated in Phase 2 tests. | **MITIGATED** |

---

## 2. OWASP API Security Top 10 (2023) Compliance Audit

- **API1: Broken Object Level Authorization (BOLA):** Every equipment, signal, anomaly, and recommendation endpoint enforces `organization_id` matching against the authenticated JWT principal.
- **API2: Broken Authentication:** Standardized JWT tokens with HMAC-SHA256 signatures, short expiration windows, and secure cookie storage (`HttpOnly`, `SameSite=Lax`).
- **API3: Broken Object Property Level Authorization:** Strict Pydantic and Marshmallow input schemas reject undeclared or sensitive parameters during resource creation.
- **API4: Unrestricted Resource Consumption:** Paginated query responses (`limit`, `offset`) on all time-series and diagnostic session endpoints.
- **API5: Broken Function Level Authorization:** Granular RBAC decorators (`@role_required([UserRole.RELIABILITY_ENGINEER, UserRole.ORG_ADMIN])`) protect approval and configuration APIs.
- **API6: Unrestricted Access to Sensitive Business Flows:** Recommendation approval requires explicit digital signature and cannot be batched indiscriminately.
- **API7: Server Side Request Forgery (SSRF):** OPC UA endpoint URLs are validated against approved IP white-lists; RAG vector searches operate strictly over local pgvector store without outbound arbitrary web requests.
- **API8: Security Misconfiguration:** Hardened HTTP security headers (`X-Content-Type-Options: nosniff`, `X-Frame-Options: SAMEORIGIN`, `X-XSS-Protection: 1; mode=block`) injected on all responses via `CorrelationMiddleware`.
- **API9: Improper Inventory Management:** Consolidated OpenAPI documentation and standardized `/api` routing prefix across all modules.
- **API10: Unsafe Consumption of APIs:** All third-party RAG document inputs undergo automated adversarial prompt sanitization via `KnowledgeSecurityFilter`.

---

## 3. Industrial OT Boundary Security (ISA/IEC 62443)

1. **Read-Only Physical Boundary:** PharmaPredict AI communicates with PLCs via read-only subscriptions. Physical control loops, safety relays, and emergency stops operate completely independent of the monitoring network.
2. **Network Microsegmentation:** Edge Gateways reside in a dedicated Purdue Level 3 DMZ with firewall rules preventing inbound connections from lower control levels.
3. **No Automated Control Logic:** The platform contains zero software actuators, PLC write routines, or automated reset hooks.

