# PharmaPredict AI — Cloud Staging Deployment Runbook

**Document Reference:** SOP-PHARMAPREDICT-DEPLOY-001  
**Version:** 1.0.0 (Cloud Staging Release)  
**Target Architecture:** Vercel (Frontend) + Render (Docker Flask Backend) + Tiger Cloud (PostgreSQL 16 + TimescaleDB) + Edge Gateway (On-Premises OT)  
**Status:** Approved for Controlled Staging  

---

## 1. Architecture & Security Topography

```
┌─────────────────────────────────────────────────────────────┐
│                      VERCEL (Frontend)                      │
│                                                             │
│   Next.js 16 Web UI (React 19, Tailwind CSS, Three.js)      │
│   - Connects to Render Backend via NEXT_PUBLIC_API_URL      │
│   - Domain: https://<your-project>.vercel.app               │
└──────────────────────────────┬──────────────────────────────┘
                               │ HTTPS / TLS 1.3
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                    RENDER (Web Service)                     │
│                                                             │
│   Flask 3.1 Gunicorn WSGI in Docker (python:3.12-slim)      │
│   - Non-root user `appuser` (UID 10001)                     │
│   - Dynamic port binding: $PORT (Render default 10000)      │
│   - Single worker safety: GUNICORN_WORKERS=1                │
│   - Pre-Deploy Migration: python scripts/deploy_migrations.py│
│   - Health Probes: /health/live, /health/ready, /health/sys │
└───────────────────────┬───────────────────────────────┬─────┘
                        │ TLS (sslmode=require)         │ Optional TLS
                        ▼                               ▼
┌──────────────────────────────────────┐  ┌───────────────────┐
│     TIGER CLOUD (TimescaleDB)        │  │   RENDER REDIS    │
│                                      │  │ (or Redis Cloud)  │
│ - Managed PostgreSQL 16              │  │                   │
│ - timescaledb extension pre-loaded   │  │ - Optional cache  │
│ - signal_readings hypertable         │  │ - Thread-safe pool│
└──────────────────────────────────────┘  └───────────────────┘
                        ▲
                        │ Outbound HTTPS / TLS 1.3 Push
┌───────────────────────┴─────────────────────────────────────┐
│             ON-PREMISES INDUSTRIAL EDGE GATEWAY             │
│                                                             │
│ - Plant LAN / OT Network (Purdue Model Level 2/3)           │
│ - AsyncIO SecureOPCUAClient (Strictly READ-ONLY)            │
│ - 24-Hour Bounded Local SQLite Buffer                       │
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

### Safe Pre-Deployment Migration Runner:
The project provides [`backend/scripts/deploy_migrations.py`](../../backend/scripts/deploy_migrations.py). It:
1. Validates database connectivity before touching schema.
2. Inspects schema status via `check_migration_status(app)`.
3. If already `up_to_date`, logs status and exits code 0.
4. If `uninitialized_database` or `pending_migration`, applies `upgrade head`.
5. If `unknown_revision` or `unversioned_tables_exist`, aborts immediately with code 1 to prevent data loss.
6. Verifies final status matches target head `0001_initial_schema`.

In Render, this executes automatically via `preDeployCommand: python scripts/deploy_migrations.py`.

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
| `AUTO_MIGRATE` | Yes | `false` | Disables startup migrations (handled in pre-deploy) |
| `CORS_ORIGINS`| Yes | `https://<your-project>.vercel.app,http://localhost:3000` | Whitelisted frontend origins |
| `REDIS_URL` | No | `rediss://...` or omit | Optional telemetry cache (probe reports OK if unset) |

### 4.2 Vercel Frontend (Next.js 16)

| Variable | Required | Staging Value / Format | Purpose |
|:---|:---:|:---|:---|
| `NEXT_PUBLIC_API_URL` | Yes | `https://<your-render-app>.onrender.com/api/v1` | Points frontend directly to Render REST API |
| `NEXT_PUBLIC_APP_NAME`| No | `PharmaPredict AI (Staging)` | Staging header banner |

---

## 5. Step-by-Step Cloud Staging Deployment Guide

### Phase 1: Database Provisioning (Tiger Cloud)
1. Sign in to [Tiger Cloud / Timescale Console](https://console.cloud.timescale.com/).
2. Create a new service (e.g. `pharmapredict-staging`).
3. Select PostgreSQL 16 with TimescaleDB enabled.
4. Copy the connection string (`postgresql://tsdbadmin:...`).

### Phase 2: Backend Deployment (Render)
1. Sign in to [Render Dashboard](https://dashboard.render.com/).
2. Click **New +** -> **Blueprint**.
3. Connect the repository `Predictive-Maintenance-System` and select branch `feature/P10-cloud-staging-deployment`.
4. Render will parse [`render.yaml`](../../render.yaml).
5. Set `DATABASE_URL` to your Tiger Cloud connection URI.
6. Click **Apply**.
7. Render runs `preDeployCommand: python scripts/deploy_migrations.py`, validates migration to `0001_initial_schema`, and starts the Gunicorn web service.
8. Verify health by opening `https://<your-backend>.onrender.com/health/ready`. It will return HTTP 200 with database status `healthy`.

### Phase 3: Frontend Deployment (Vercel)
1. Sign in to [Vercel Dashboard](https://vercel.com/).
2. Click **Add New...** -> **Project**.
3. Import `Predictive-Maintenance-System`.
4. Vercel automatically detects Next.js framework settings from [`vercel.json`](../../vercel.json).
5. Under **Environment Variables**, add:
   - `NEXT_PUBLIC_API_URL`: `https://<your-backend>.onrender.com/api/v1`
6. Click **Deploy**.
7. Once deployed, copy the Vercel URL (e.g. `https://pharmapredict-staging.vercel.app`).
8. Return to Render Dashboard -> Backend Environment Variables, and update `CORS_ORIGINS` to include your Vercel URL.

---

## 6. Rollback Procedure

If an issue is detected during staging testing:

### Backend Rollback (Render):
1. In Render Dashboard -> **Deploys**, select the previous successful build.
2. Click **Rollback to this deploy**.
3. The previous container image is instantly restored.

### Database Migration Rollback:
If a migration needs to be reversed:
```bash
# In Render SSH shell or secure terminal:
python -c "from app import create_app; from flask_migrate import downgrade; app = create_app('staging'); downgrade(directory='migrations', revision='-1')"
```

### Frontend Rollback (Vercel):
1. In Vercel Dashboard -> **Deployments**, locate the prior working deployment.
2. Click the three dots `...` -> **Promote to Production**. Instant, zero-downtime rollback.

---

## 7. Cost Estimates (Informational Only)

> [!NOTE]
> All figures below are third-party vendor estimates for a small staging cluster as of late 2026. No paid resources or billing commitments are made by this repository.

| Provider | Service Tier | Estimated Cost | Notes |
|:---|:---|:---|:---|
| **Vercel** | Hobby (Free) / Pro ($20/seat/mo) | **$0.00 / month** | Hobby tier supports standard Next.js staging workloads. |
| **Render** | Web Service (Starter) | **$7.00 / month** | 512 MB RAM, 0.5 vCPU, custom Dockerfile, persistent uptime. |
| **Tiger Cloud** | Dev/Test Tier (Timescale) | **~$15.00 – $25.00 / month** | Managed TimescaleDB compute + storage. |
| **Redis** | Render Key Value / Upstash Free | **$0.00 – $7.00 / month** | Redis is optional; $0 if omitted or using Upstash free tier. |
| **Total Estimated Staging Cost** | | **~$22.00 – $32.00 / month** | Dependent on active usage and free-tier eligibility. |

