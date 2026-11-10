# PharmaPredict AI — Production Deployment Architecture

**Document Reference:** ARCH-PHARMAPREDICT-001  
**Version:** 2.0.0 (Phase 10 Enterprise Release)  
**Effective Date:** 2026-11-05  
**Deployment Target:** High-Availability On-Premises Plant Cluster, Multi-Site Edge, or Dedicated Private VPC  
**Related Issues:** #68 (P10-F01), #69 (P10-F01-S01), #70 (P10-F01-S02)

---

## 1. System Topology Overview

PharmaPredict AI follows a decoupled, resilient Edge-to-Core architectural pattern designed for high-availability industrial pharmaceutical operations across multi-site production facilities:

```
                  ┌──────────────────────────────────────────────┐
                  │          Manufacturing OT Network            │
                  │   Packaging Lines / Cleanrooms (Purdue L2)   │
                  │   [ Uhlmann Blister ]  [ Fette Tablet Press ]│
                  └──────────────────────┬───────────────────────┘
                                         │ OPC UA (Port 4840)
                                         ▼
                  ┌──────────────────────────────────────────────┐
                  │         Industrial Edge Gateway (L3)         │
                  │  - AsyncIO OPC UA Collection Service         │
                  │  - SQLite 24-hour Store-and-Forward Buffer   │
                  │  - Read-Only Unidirectional Security Enforcer│
                  └──────────────────────┬───────────────────────┘
                                         │ HTTPS / TLS 1.3 (Mutual TLS)
                                         ▼
┌────────────────────────────────────────────────────────────────────────────┐
│              Plant Enterprise Server Cluster (Purdue L4 DMZ)                │
│                                                                            │
│  ┌───────────────────────┐                    ┌─────────────────────────┐  │
│  │   NGINX Reverse Proxy │ ──(Internal Net)──►│   Flask 3.1 Backend     │  │
│  │   & TLS 1.3 Endpoint  │                    │   (Gunicorn / 4 Workers)│  │
│  └───────────┬───────────┘                    └────────────┬────────────┘  │
│              │                                             │               │
│              ▼                                             ▼               │
│  ┌───────────────────────┐                    ┌─────────────────────────┐  │
│  │   Next.js 16 Client   │                    │ PostgreSQL 16 +         │  │
│  │   Frontend Server     │                    │ TimescaleDB + pgvector  │  │
│  └───────────────────────┘                    └─────────────────────────┘  │
│                                                            │               │
│                                                            ▼               │
│                                               ┌─────────────────────────┐  │
│                                               │ Redis 7 AOF Telemetry   │  │
│                                               │ Cache & Queue Buffer    │  │
│                                               └─────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Infrastructure & Capacity Specifications

### 2.1 Hardware Requirements (Per Plant Site: 10–25 Monitored Machines)
- **Central Application Host:**
  - **CPU:** 8 vCPU (AMD EPYC or Intel Xeon 2.8GHz+)
  - **RAM:** 32 GB ECC DDR4/DDR5
  - **Storage:** 500 GB NVMe SSD in RAID 1 (for TimescaleDB time-series and WAL logs)
- **Industrial Edge Gateway (Per Production Line):**
  - **Hardware:** Advantech UNO-2484G or Dell Edge Gateway 3002
  - **CPU:** 4-Core Intel Atom / Core i3 Industrial
  - **RAM:** 8 GB RAM
  - **Storage:** 128 GB Industrial SSD (24h continuous circular telemetry buffer)
  - **Network:** Dual isolated Gigabit NICs (NIC 1: OT VLAN; NIC 2: Plant IT DMZ)

---

## 3. Database Tuning & Retention Policies

### 3.1 TimescaleDB Hypertable Configuration
- **Hypertable:** `signal_readings` partitioned on `timestamp` with 7-day chunk intervals.
- **Native Compression:**
  ```sql
  ALTER TABLE signal_readings SET (
      timescaledb.compress,
      timescaledb.compress_segmentby = 'machine_signal_id',
      timescaledb.compress_orderby = 'timestamp DESC'
  );
  -- Enable automated compression for chunks older than 14 days
  SELECT add_compression_policy('signal_readings', INTERVAL '14 days');
  ```
- **Data Retention Policy:**
  ```sql
  -- Drop raw high-frequency telemetry older than 365 days (1 year)
  SELECT add_retention_policy('signal_readings', INTERVAL '365 days');
  ```

---

## 4. Disaster Recovery & High Availability

1. **Automated Daily Backup:**
   Cron execution of `backend/scripts/database_backup_restore.py backup --output-dir /var/backups/pharmapredict --tag daily` at 02:00 UTC.
2. **Cryptographic Integrity Verification:** Automated generation of `.manifest.json` with SHA-256 hash for every backup archive to guarantee 21 CFR Part 11 ALCOA+ audit compliance.
3. **Recovery Time Objective (RTO):** $\le 30\text{ minutes}$.
4. **Recovery Point Objective (RPO):** $\le 1\text{ hour}$ (via WAL archiving).

---

## 5. Enterprise Containerization & Multi-Stage Images (Issue #69)

### 5.1 Next.js 16 Production Frontend Container
- **Base Image:** `node:20-alpine`
- **Builder Stage:** Standalone bundle compilation with pnpm (`NEXT_OUTPUT_STANDALONE=true`).
- **Runner Stage:** Hardened non-root user `nextjs` (UID 1001) in group `nodejs` (GID 1001).
- **Security:** Root filesystem read-only, non-root execution, zero elevated capabilities (`CAP_DROP=ALL`).
- **Healthcheck:** `wget --spider http://localhost:3000/` every 20 seconds.

### 5.2 Flask 3.1 Production Backend Container
- **Base Image:** `python:3.12-slim`
- **WSGI Server:** Gunicorn with 4 workers, 2 threads, 120s timeout, stdout/stderr structured access logging.
- **Non-Root Execution:** Dedicated system user `appuser` (UID 10001) in group `appgroup` (GID 10001).
- **Probes:** Unversioned `/health/live` and `/health/ready` verified via curl.
- **Orchestration:** Managed via `deploy/production/docker-compose.prod.yml` with persistent named volumes and dependency-ordering health checks.

---

## 6. Canonical Infrastructure Health Probes (Issue #70)

PharmaPredict AI enforces a two-tier health probe architecture:

| Endpoint | Target Audience | Semantics & Verification | Status Codes |
|:---|:---|:---|:---:|
| `GET /health/live` | Kubernetes Liveness Probe / Docker daemon | Ultra-low latency process responsiveness. Zero external I/O. | `200` |
| `GET /health/ready` | Kubernetes Readiness Probe / Load Balancer | Validates mandatory dependencies: TimescaleDB (`SELECT 1`) and Redis (`PING`). | `200` (Ready)<br>`503` (Degraded) |
| `GET /health/system` | Enterprise Ops & Monitoring Consoles | Process uptime, engine flavor, operational capability flags. All secrets/credentials masked. | `200` / `503` |
| `GET /api/v1/health` | Application Frontend & API Clients | Versioned diagnostic contract with capability catalogue and database status. | `200` / `503` |

---

## 7. Automated Database Migration & Schema Safety (Issue #70)

1. **Alembic / Flask-Migrate Governance:** Application schema versioning managed in `backend/migrations/`.
2. **Startup Verification Runner:** `app.database_migrations.verify_database_on_startup()` executes during application initialization:
   - Queries `alembic_version` in the active database.
   - Compares against script head revision.
   - In production mode (`ENFORCE_MIGRATION_CHECK=true`), fails fast with `RuntimeError` if migrations are unapplied, preventing split-brain schema mutations across replicas.
3. **Automated Migration Runner:** Optional execution via `AUTO_MIGRATE=true` for single-instance staging/CI environments.

---

## 8. Environment Profiles & Security Controls

PharmaPredict AI defines three distinct environment tiers:

1. **Development (`FLASK_ENV=development`):** Local development with hot reload, SQLite or Docker Compose TimescaleDB fallback.
2. **Staging (`FLASK_ENV=staging`):** Pre-production validation environment. Mandatory `SECRET_KEY` validation ($\ge 16$ characters) and migration check.
3. **Production (`FLASK_ENV=production`):** Strict pharmaceutical validation.
   - Rejects default dev keys; enforces cryptographically random `SECRET_KEY` ($\ge 32$ characters).
   - Prohibits SQLite; enforces PostgreSQL/TimescaleDB.
   - Enforces Secure, HttpOnly, SameSite session cookies.
   - Enforces database migration check prior to serving traffic.
