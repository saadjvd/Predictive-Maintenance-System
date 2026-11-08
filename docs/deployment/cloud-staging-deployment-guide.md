# PharmaPredict AI — Cloud Staging Deployment Runbook

**Document Reference:** SOP-PHARMAPREDICT-DEPLOY-001<br/>
**Version:** 1.2.0 (Permanent Zero-Cost Staging Architecture — Neon PostgreSQL)<br/>
**Target Architecture:** Cloudflare Workers (Full-Stack Next.js 16 via OpenNext) + Render (Docker Flask Backend, Free Tier) + Neon (PostgreSQL 16, Permanent Free Tier) + Edge Gateway (On-Premises OT)<br/>
**Status:** Approved for Controlled Staging  

---

## 1. Architecture & Security Topography

```
┌─────────────────────────────────────────────────────────────┐
│                 CLOUDFLARE WORKERS (Frontend)               │
│                                                             │
│   Full-Stack Next.js 16 Web UI (React 19, Tailwind CSS)     │
│   - Packaged via @opennextjs/cloudflare for Edge Worker     │
│   - Supports App Router, Dynamic Route (/dashboard/equipment/│
│     [id]), and Server Functions                             │
│   - Reverse-proxies /api/* to Render backend (Same-Origin)  │
│   - Note: Cloudflare Pages is only used if static export    │
│     (`output: 'export'`) is explicitly selected             │
│   - Domain: https://<your-project>.workers.dev              │
└──────────────────────────────┬──────────────────────────────┘
                               │ HTTPS / TLS 1.3
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                    RENDER (Web Service)                     │
│                                                             │
│   Flask 3.1 Gunicorn WSGI in Docker (python:3.12-slim)      │
│   - Plan: Free ($0.00/mo, 512 MB RAM, ~0.1 shared vCPU)     │
│   - Non-root user `appuser` (UID 10001)                     │
│   - Dynamic port binding: $PORT (Render default 10000)      │
│   - Single worker safety: GUNICORN_WORKERS=1                │
│   - Container Entrypoint Migration: `entrypoint.sh` executes│
│     `python scripts/deploy_migrations.py` before Gunicorn   │
│   - Liveness Probe: /health/live (Zero DB I/O; preserves    │
│     Neon scale-to-zero)                                     │
│   - Readiness Probe: /health/ready (Full dependency check)  │
└───────────────────────┬───────────────────────────────┬─────┘
                        │ TLS (sslmode=require)         │ Optional TLS
                        ▼                               ▼
┌──────────────────────────────────────┐  ┌───────────────────┐
│     NEON POSTGRESQL (Serverless)     │  │   RENDER REDIS    │
│                                      │  │ (or Redis Cloud)  │
│ - Managed PostgreSQL 16 (Serverless) │  │                   │
│ - Permanent Free Plan ($0.00/mo)     │  │ - Optional cache  │
│ - 1.0 GB Storage (Schema: ~12 MB)    │  │ - Thread-safe pool│
│ - 100 Compute Unit (CU) hours / mo   │  │                   │
│ - Scale-to-Zero after 5 min idle     │  │                   │
│ - No credit card required            │  │                   │
│ - Standard indexed signal_readings   │  │                   │
└──────────────────────────────────────┘  └───────────────────┘
                        ▲
                        │ Outbound HTTPS / TLS 1.3 Push
┌───────────────────────┴─────────────────────────────────────┐
│             ON-PREMISES INDUSTRIAL EDGE GATEWAY             │
│                                                             │
│ - Plant LAN / OT Network (Purdue Model Level 2/3)           │
│ - AsyncIO SecureOPCUAClient (Strictly READ-ONLY)            │
│ - BoundedGatewayBuffer: In-memory queue (5,000 items) +     │
│   50 MB Local JSONL Overflow (`gateway_overflow.jsonl`)     │
│ - Future Specification: P10-EDGE-001 SQLite Durable Queue   │
│ - Outbound only: NO open inbound ports to factory network   │
└─────────────────────────────────────────────────────────────┘
```

> [!IMPORTANT]
> **Industrial Safety Notice:** Deploying PharmaPredict AI to a cloud staging environment validates cloud software integration, APIs, models, and UI. It **does NOT** constitute physical factory commissioning. Factory commissioning requires on-premises edge gateway qualification, network segregation, and GAMP 5 / 21 CFR Part 11 validation.

---

## 2. Gunicorn Concurrency & Background Task Safety

The repository audit identified that industrial machine monitoring sessions (`ActiveMachinePipeline`), OPC UA subscription listeners, and batch buffer dispatchers execute as **in-process asyncio event loops and background threads** (`MonitoringLifecycleManager` and `GatewayManager`).

### Worker Safety Principles:
1. **Single Worker in Staging (`GUNICORN_WORKERS=1`):**
   - Running multiple Gunicorn OS worker processes (`workers > 1`) causes in-memory split-brain state: an activation request handled by Worker 1 starts the thread in Worker 1's memory space, but subsequent status or deactivation requests routed to Worker 2/3 cannot observe or stop it.
   - For cloud staging, the backend **must run with 1 worker process and 4 concurrent threads** (`GUNICORN_WORKERS=1`, `GUNICORN_THREADS=4`).
2. **Future Production Decoupling:**
   - For multi-instance, auto-scaling production deployments, background monitoring ingestion will be decoupled into a dedicated persistent background worker process (Celery / RQ / standalone edge daemon) backed by Redis distributed locking.

---

## 3. Database Migration Runbook (Neon PostgreSQL 16)

Migrations are governed by Alembic and Flask-Migrate via [`backend/migrations/versions/0001_initial_schema.py`](../../backend/migrations/versions/0001_initial_schema.py) (57 tables, 213 indexes).

### Conditional Dialect & Extension Handling:
* The initial schema migration contains defensive extension detection:
  ```python
  bind = op.get_bind()
  if bind.dialect.name == 'postgresql':
      has_timescale = bind.execute(sa.text("SELECT 1 FROM pg_available_extensions WHERE name = 'timescaledb'")).scalar()
      if has_timescale:
          ...
  ```
* On Neon PostgreSQL 16, `timescaledb` is not in `pg_available_extensions`. Alembic detects this, bypasses hypertable conversion cleanly, and creates `signal_readings` as a standard, indexed PostgreSQL table (Option A).
* The TimescaleDB conditional logic remains 100% intact for future hybrid or self-hosted enterprise deployments.

### Safe Container Startup Migration Execution:
The project provides [`backend/scripts/deploy_migrations.py`](../../backend/scripts/deploy_migrations.py).
Because Render's Free tier (`plan: free`) rejects the `preDeployCommand` Blueprint property, migration execution is embedded directly in [`backend/entrypoint.sh`](../../backend/entrypoint.sh) inside the Docker image:
1. Validates database connectivity before touching schema.
2. Inspects schema status via `check_migration_status(app)`.
3. If already `up_to_date`, logs status and continues to WSGI startup.
4. If `uninitialized_database` or `pending_migration`, applies `upgrade head`.
5. If `unknown_revision` or `unversioned_tables_exist`, aborts immediately with code 1 to prevent data loss.
6. Verifies final status matches target head `0001_initial_schema`.

---

## 4. Health Checks & Database Scale-to-Zero Preservation

Neon's serverless architecture automatically suspends compute after **5 minutes of inactivity**, consuming zero compute units (0 CU) while idle.

### Audit Findings on Scale-to-Zero Compatibility:
1. **Liveness Probe (`/health/live`):**
   * Configured as Render's container health check (`healthCheckPath: /health/live`).
   * Executes **zero database or network I/O**; returns in `< 1 ms`.
   * **Result:** Periodic Render liveness checks do **not** wake up or keep Neon alive, preserving your 100 monthly CU-hour quota.
2. **Readiness Probe (`/health/ready`):**
   * Executes `SELECT 1` against PostgreSQL to confirm transaction readiness.
   * Only probed during initial container startup and on-demand diagnostic checks.
3. **Connection Pooling & Pre-Ping (`backend/app/config.py`):**
   * Configured with `SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}`.
   * Does not run background heartbeat pings. Pings occur only upon active checkout (when a user request arrives).
   * When Neon wakes up from scale-to-zero (~500 ms wake-up latency), `pool_pre_ping` transparently tests the connection and reconnects, preventing `OperationalError: SSL connection has been closed unexpectedly`.

---

## 5. Environment Variables Matrix

### 5.1 Render Backend Service (Flask)

| Variable | Required | Staging Value / Format | Purpose |
|:---|:---:|:---|:---|
| `FLASK_ENV` | Yes | `staging` | Activates StagingConfig with secret validation |
| `APP_NAME` | Yes | `PharmaPredict AI` | Application branding |
| `APP_VERSION`| Yes | `1.0.0` | Version identifier |
| `GUNICORN_WORKERS` | Yes | `1` | Enforces single-worker in-memory thread safety |
| `GUNICORN_THREADS` | Yes | `4` | Enables multi-threaded concurrent request handling |
| `SECRET_KEY` | Yes | Auto-generated by Render ($\ge 32$ chars) | Session encryption & token signing |
| `DATABASE_URL`| Yes | `postgresql://<user>:<pwd>@<endpoint>.us-east-1.aws.neon.tech/neondb?sslmode=require` | Connection to Neon PostgreSQL 16 (Direct or Pooled) |
| `ENFORCE_MIGRATION_CHECK` | Yes | `true` | Refuses startup if migrations are missing |
| `AUTO_MIGRATE` | Yes | `false` | Disables startup migrations (handled in entrypoint) |
| `CORS_ORIGINS`| Yes | `https://<your-project>.workers.dev,http://localhost:3000` | Whitelisted frontend origins |
| `REDIS_URL` | No | `rediss://...` or omit | Optional telemetry cache (probe reports OK if unset) |

### 5.2 Cloudflare Workers Frontend (Next.js 16)

| Variable | Required | Staging Value / Format | Purpose |
|:---|:---:|:---|:---|
| `NEXT_PUBLIC_API_URL` | Yes | `https://<your-render-app>.onrender.com/api/v1` | Points frontend directly to Render REST API |
| `NEXT_PUBLIC_APP_NAME`| No | `PharmaPredict AI (Staging)` | Staging header banner |

---

## 6. Step-by-Step Cloud Staging Deployment Guide

### Phase 1: Database Provisioning (Neon PostgreSQL 16 Free)
1. Sign in to [Neon Console](https://console.neon.tech/).
2. Click **Create Project**.
3. Configure project:
   * **Project Name:** `pharmapredict-staging`
   * **PostgreSQL Version:** `16`
   * **Region:** AWS `us-east-1` (US East, N. Virginia)
   * **Plan:** Free Plan ($0.00/mo, 1 GB storage, 100 CU-hrs, no credit card required).
4. Retrieve connection parameters (Direct or `-pooler` connection string). Ensure `sslmode=require` is appended.
5. *Note: Existing Tiger Cloud service `dot4xunwpo` remains untouched.*

### Phase 2: Backend Deployment (Render Free Web Service)
1. Sign in to [Render Dashboard](https://dashboard.render.com/).
2. Click **New +** -> **Blueprint**.
3. Connect repository `Predictive-Maintenance-System` and branch `phase/10-enterprise-productization`.
4. Render parses [`render.yaml`](../../render.yaml) (`plan: free`).
5. Under Environment Variables, set `DATABASE_URL` to your Neon PostgreSQL connection URI.
6. Click **Apply**.
7. The container starts, executes `entrypoint.sh` migration check against Neon, materializes all 57 tables, and launches Gunicorn.
8. Verify health: `https://<your-backend>.onrender.com/health/ready` returns HTTP 200 with database status `healthy`.

### Phase 3: Frontend Deployment (Cloudflare Workers via OpenNext)
1. Ensure build is executed in a Linux environment (Linux CI/CD or GitHub Actions runner).
2. Configure [`open-next.config.ts`](../../open-next.config.ts) and [`wrangler.jsonc`](../../wrangler.jsonc).
3. Run `npx opennextjs-cloudflare build` to generate the `.open-next/worker.js` bundle.
4. Deploy using Wrangler: `npx wrangler deploy`.
5. Once deployed, copy your Cloudflare Worker URL (e.g. `https://pharmapredict-frontend.<subdomain>.workers.dev`).
6. In Render Dashboard, update `CORS_ORIGINS` to whitelist the Cloudflare Worker URL.

*(Note: Cloudflare Pages is only applicable if Next.js static export `output: 'export'` is intentionally selected, which disables dynamic server rendering).*

---

## 7. Rollback & Migration Downgrade Procedure

If an issue is detected during staging testing:

### Backend Rollback (Render):
1. In Render Dashboard -> **Deploys**, select the previous successful build.
2. Click **Rollback to this deploy**. The prior container image is instantly restored.

### Database Migration Rollback (Neon):
If a migration needs to be reversed:
```bash
# In Render SSH shell or secure terminal:
python -c "from app import create_app; from flask_migrate import downgrade; app = create_app('staging'); downgrade(directory='migrations', revision='-1')"
```
*Alternatively, Neon supports instant Point-in-Time Restore (PITR) and branching: create a recovery branch in the Neon console in seconds with zero data loss.*

### Frontend Rollback (Cloudflare Workers):
1. In Cloudflare Dashboard -> **Workers & Pages** -> select service -> **Deployments**.
2. Select the prior deployment version and click **Rollback**. Instant, zero-downtime traffic switch.

---

## 8. Staging Architecture Cost Matrix (Strictly $0.00 / Zero Cost)

> [!IMPORTANT]
> **Strict Zero-Cost Deployment:** The PharmaPredict AI cloud staging environment operates entirely on genuinely free tiers. No credit card, paid trial, or automatic paid upgrade is permitted.

| Provider | Service Tier | Actual Staging Cost | Verified Limits & Safeguards |
|:---|:---|:---|:---|
| **Cloudflare** | Workers (Free Plan) | **$0.00 / month** | 100,000 requests/day, unmetered bandwidth, commercial SaaS permitted. No credit card required. |
| **Render** | Web Service (Free Plan) | **$0.00 / month** | 512 MB RAM, shared CPU, custom Dockerfile, 750 free instance hours/month. Auto-sleeps on inactivity. |
| **Neon** | PostgreSQL 16 (Free Plan) | **$0.00 / month** | 1.0 GB storage (Schema: ~12 MB = 1.2%), 100 CU-hours/mo, 5 GB egress, auto-scales to zero after 5 min. No credit card required. |
| **Redis** | Unset / Upstash Free | **$0.00 / month** | Optional; zero cost when omitted (`/health/ready` returns HTTP 200). |
| **Total Staging Cost** | **Zero-Cost Architecture** | **$0.00 / month** | **100% Permanent Free Tier. No trial expiration. Zero billing risk.** |

---

## 9. Database Architecture Status & Technical Limitation Notice

- **Approved Staging Decision:** **Option A (Standard Indexed PostgreSQL Table)** on Neon PostgreSQL.
- **TimescaleDB Extension Status:** The TimescaleDB extension (`v2.24.0`) is available and installed in the current Neon environment.
- **`signal_readings` Status:** The `signal_readings` table currently operates as a standard PostgreSQL table (with 8 B-tree composite indexes).
- **Explicit Technical Notice:** Native TimescaleDB hypertable chunk partitioning and columnar compression are **not active** in staging. Hypertable conversion was safely bypassed because `signal_readings` utilizes `PRIMARY KEY (id)` without `source_timestamp` as part of the unique constraint.
- **Future Production Parity Plan:** See detailed specification in [`technical-limitation-timescaledb-hypertable.md`](technical-limitation-timescaledb-hypertable.md) (Task `P10-DB-002`) for composite key migration in a future Phase 10 release.

---

## 10. OT Edge Telemetry Buffering Reality & GAMP 5 Verification Status

### Codebase Implementation Audit (`backend/app/modules/monitoring/gateway_buffer.py`):
1. **Buffer Architecture:**
   - The buffer is implemented by class `BoundedGatewayBuffer`.
   - Primary buffer: In-memory `collections.deque` with capacity limit `max_queue_size = 5000`.
   - Overflow / outage buffer: Flat JSONL file `gateway_overflow.jsonl` with size ceiling `max_disk_buffer_bytes = 50 MB`.
   - **Database Engine:** **It is NOT an SQLite database.** It is a raw JSONL text file on local disk.
2. **Persistence Across Gateway Restarts:**
   - In-memory `_queue` items reside exclusively in RAM. If the edge gateway process crashes or restarts, all in-memory readings are lost.
   - Only readings already flushed to `gateway_overflow.jsonl` survive a process restart.
3. **Retry & Backoff:**
   - Implemented in `_send_with_retry` (3 attempts, initial delay 0.5s, exponential factor 2.0).
4. **Capacity & 24-Hour Backend Outage Analysis:**
   - At a typical industrial sampling rate of 10 readings/second (~200 bytes/reading = 2 KB/s = ~172.8 MB/day), the 50 MB JSONL disk buffer reaches capacity in approximately 7 hours.
   - Once the 50 MB limit is reached, `_try_write_to_disk` rejects writes, and subsequent incoming readings are dropped (`_dropped_count += 1`).
5. **Empirical Verification Status:**
   - Short-term unit testing (`test_monitoring.py::test_backend_outage_buffering_and_queue_overflow`): **VERIFIED (Unit Test)**.
   - 24-hour continuous backend outage recovery: **NOT VERIFIED**.
   - Zero-telemetry-loss over 24 hours under continuous machine operation: **NOT VERIFIED**.
   - Durable cross-restart queue recovery: **PARTIALLY VERIFIED** (JSONL portion only; in-memory queue is lost).
6. **Remediation Specification:**
   - Specification [`docs/architecture/edge-gateway-sqlite-durable-queue-specification.md`](../architecture/edge-gateway-sqlite-durable-queue-specification.md) (Task `P10-EDGE-001`) defines the SQLite WAL replacement for Phase 10 Sprint 2.
