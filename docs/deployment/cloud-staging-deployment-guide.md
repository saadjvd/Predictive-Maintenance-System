# PharmaPredict AI — Cloud Staging Deployment Runbook

**Document Reference:** SOP-PHARMAPREDICT-DEPLOY-001  
**Version:** 1.1.0 (Zero-Cost Cloud Staging Architecture)  
**Target Architecture:** Cloudflare Workers (Full-Stack Next.js 16 via OpenNext) + Render (Docker Flask Backend, Free Tier) + Tiger Cloud (PostgreSQL 16 + TimescaleDB, Permanent Free) + Edge Gateway (On-Premises OT)  
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
│   - Health Probes: /health/live, /health/ready, /health/sys │
└───────────────────────┬───────────────────────────────┬─────┘
                        │ TLS (sslmode=require)         │ Optional TLS
                        ▼                               ▼
┌──────────────────────────────────────┐  ┌───────────────────┐
│     TIGER CLOUD (TimescaleDB)        │  │   RENDER REDIS    │
│                                      │  │ (or Redis Cloud)  │
│ - Managed PostgreSQL 16              │  │                   │
│ - Permanent Free Tier ($0.00/mo)     │  │ - Optional cache  │
│ - timescaledb extension pre-loaded   │  │ - Thread-safe pool│
│ - signal_readings standard table     │  │                   │
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

## 3. Database Migration Runbook (Tiger Cloud / TimescaleDB)

Migrations are governed by Alembic and Flask-Migrate via [`backend/migrations/versions/0001_initial_schema.py`](../../backend/migrations/versions/0001_initial_schema.py) (57 tables, dialect-aware TimescaleDB hypertable setup).

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

## 4. Environment Variables Matrix

### 4.1 Render Backend Service (Flask)

| Variable | Required | Staging Value / Format | Purpose |
|:---|:---:|:---|:---|
| `FLASK_ENV` | Yes | `staging` | Activates StagingConfig with secret validation |
| `APP_NAME` | Yes | `PharmaPredict AI` | Application branding |
| `APP_VERSION`| Yes | `1.0.0` | Version identifier |
| `GUNICORN_WORKERS` | Yes | `1` | Enforces single-worker in-memory thread safety |
| `GUNICORN_THREADS` | Yes | `4` | Enables multi-threaded concurrent request handling |
| `SECRET_KEY` | Yes | Auto-generated by Render ($\ge 32$ chars) | Session encryption & token signing |
| `DATABASE_URL`| Yes | `postgresql://tsdbadmin:<PWD>@<HOST>:<PORT>/tsdb?sslmode=require` | Connection to Tiger Cloud TimescaleDB |
| `ENFORCE_MIGRATION_CHECK` | Yes | `true` | Refuses startup if migrations are missing |
| `AUTO_MIGRATE` | Yes | `false` | Disables startup migrations (handled in entrypoint) |
| `CORS_ORIGINS`| Yes | `https://<your-project>.workers.dev,http://localhost:3000` | Whitelisted frontend origins |
| `REDIS_URL` | No | `rediss://...` or omit | Optional telemetry cache (probe reports OK if unset) |

### 4.2 Cloudflare Workers Frontend (Next.js 16)

| Variable | Required | Staging Value / Format | Purpose |
|:---|:---:|:---|:---|
| `NEXT_PUBLIC_API_URL` | Yes | `https://<your-render-app>.onrender.com/api/v1` | Points frontend directly to Render REST API |
| `NEXT_PUBLIC_APP_NAME`| No | `PharmaPredict AI (Staging)` | Staging header banner |

---

## 5. Step-by-Step Cloud Staging Deployment Guide

### Phase 1: Database Provisioning (Tiger Cloud)
1. Sign in to [Tiger Cloud / Timescale Console](https://console.cloud.timescale.com/).
2. Select Project `o9gkck4dhm` -> **Create Service**.
3. Select AWS `us-east-1`, Service Name: `pharmapredict-staging`.
4. Choose the **Permanent Free Tier** ($0.00/mo, 750 MiB storage, no credit card required).
5. Ensure PostgreSQL 16 with TimescaleDB enabled.
6. Retrieve connection details: Host, Port, Database (`tsdb`), and User (`tsdbadmin`). Store password securely.

### Phase 2: Backend Deployment (Render)
1. Sign in to [Render Dashboard](https://dashboard.render.com/).
2. Click **New +** -> **Blueprint**.
3. Connect repository `Predictive-Maintenance-System` and branch `phase/10-enterprise-productization`.
4. Render parses [`render.yaml`](../../render.yaml) (`plan: free`).
5. Set `DATABASE_URL` to your Tiger Cloud connection URI.
6. Click **Apply**.
7. The container starts, executes `entrypoint.sh` migration check, and launches Gunicorn.
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

## 6. Rollback Procedure

If an issue is detected during staging testing:

### Backend Rollback (Render):
1. In Render Dashboard -> **Deploys**, select the previous successful build.
2. Click **Rollback to this deploy**. The prior container image is instantly restored.

### Database Migration Rollback:
If a migration needs to be reversed:
```bash
# In Render SSH shell or secure terminal:
python -c "from app import create_app; from flask_migrate import downgrade; app = create_app('staging'); downgrade(directory='migrations', revision='-1')"
```

### Frontend Rollback (Cloudflare Workers):
1. In Cloudflare Dashboard -> **Workers & Pages** -> select service -> **Deployments**.
2. Select the prior deployment version and click **Rollback**. Instant, zero-downtime traffic switch.

---

## 7. Staging Architecture Cost Matrix (Strictly $0.00 / Zero Cost)

> [!IMPORTANT]
> **Strict Zero-Cost Deployment:** The PharmaPredict AI cloud staging environment operates entirely on genuinely free tiers. No credit card, paid trial, or automatic paid upgrade is permitted.

| Provider | Service Tier | Actual Staging Cost | Notes |
|:---|:---|:---|:---|
| **Cloudflare** | Workers (Free Plan) | **$0.00 / month** | 100,000 requests/day, unmetered bandwidth, commercial SaaS permitted under Cloudflare Self-Serve terms. |
| **Render** | Web Service (Free Plan) | **$0.00 / month** | 512 MB RAM, shared CPU, custom Dockerfile, 750 free instance hours/month. Auto-sleeps on inactivity. |
| **Tiger Cloud** | Permanent Free Tier | **$0.00 / month** | 750 MiB storage, AWS `us-east-1`, PostgreSQL 16 + TimescaleDB extension. No credit card required. |
| **Redis** | Unset / Upstash Free | **$0.00 / month** | Optional; zero cost when omitted (`/health/ready` returns HTTP 200). |
| **Total Staging Cost** | **Zero-Cost Architecture** | **$0.00 / month** | 100% free tier. No credit card or billing commitment required. |

---

## 8. Database Architecture Status & Technical Limitation Notice

- **Approved Staging Decision:** **Option A (Standard Indexed PostgreSQL Table)**.
- **TimescaleDB Extension Status:** `INSTALLED` and available on Tiger Cloud PostgreSQL 16.
- **`signal_readings` Status:** Operating as a standard, indexed PostgreSQL table (with 8 B-tree composite indexes).
- **Explicit Technical Notice:** Native TimescaleDB hypertable chunk partitioning and columnar compression are **inactive** in staging. Hypertable conversion was bypassed because `signal_readings` uses `PRIMARY KEY (id)` and `UNIQUE (event_id)`, whereas TimescaleDB requires the partitioning column (`source_timestamp`) in all unique constraints.
- **Future Production Parity Plan:** See detailed specification in [`technical-limitation-timescaledb-hypertable.md`](technical-limitation-timescaledb-hypertable.md) (Task `P10-DB-002`) for composite key migration in a future Phase 10 release.

---

## 9. OT Edge Telemetry Buffering Reality & GAMP 5 Verification Status

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
