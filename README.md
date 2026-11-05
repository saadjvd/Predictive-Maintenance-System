# PharmaPredict AI

**Universal AI-Powered Predictive Maintenance Web Application for Pharmaceutical Manufacturing**

---

## Overview

PharmaPredict AI helps pharmaceutical manufacturing facilities monitor equipment conditions, detect anomalies against established baselines, investigate developing mechanical/electrical faults, and make evidence-based maintenance decisions.

The platform is machine-agnostic and universally configurable across diverse pharmaceutical manufacturing equipment:
- **Blister Packaging Machines**
- **Tablet Compression Machines**
- **Capsule Filling Machines**
- **Mixers and Granulators**
- **Liquid Filling Systems**
- **HVAC Systems & Cleanroom Utilities**

---

## Architectural Principles

1. **Human-in-the-Loop Governance:** AI diagnostic agents provide evidence-supported recommendations; qualified maintenance engineers retain exclusive authorization for work orders and machine actions.
2. **Read-Only Edge Gateway:** Industrial equipment connects exclusively through isolated, read-only edge gateways (OPC UA). Production PLCs/SCADA systems are never directly modified by or exposed to the web platform.
3. **Multi-Tenant Isolation:** Complete organization and factory boundary enforcement across every telemetry reading, equipment record, and maintenance action. No cross-tenant access is possible.

---

## Technology Stack

- **Frontend:** Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS 4, Framer Motion, Three.js / React Three Fiber, Recharts, Lucide React.
- **Backend:** Python 3.12+ (Python 3.13 verified), Flask 3, Flask-SQLAlchemy, Flask-Migrate, Flask-CORS, Pydantic, Pytest.
- **Storage:** PostgreSQL (relational) + TimescaleDB (time-series sensor data) with SQLite development fallback.
- **Security:** Secure server-side sessions, HttpOnly cookies, PBKDF2 password hashing, rate limiting, and RBAC authorization decorators.

---

## Multi-Tenancy & Role-Based Access Control (RBAC)

### Tenant Entity Model
- **`Organization`**: Isolated pharmaceutical corporate entity (e.g., Getz Pharma, Benchmark Pharmaceuticals).
- **`Site`**: Physical manufacturing plant / facility (e.g., Unit-1 Korangi, Unit-2 BFS).
- **`User`**: Team member linked to an organization.
- **`Role`**: Granular platform and operational privileges.
- **`UserRoleAssignment`**: Role binding scoped strictly to an organization.
- **`UserSession`**: Server-side session with expiration and immediate revocation capability.
- **`UserInvitation`**: Single-use, time-limited cryptographic tokens (72h) for controlled user onboarding.

### Role Hierarchy
1. **Platform Administrator:** Platform-level administration and cross-tenant configuration.
2. **Organization Administrator:** Organization settings, site management, user invitations, and role assignments.
3. **Maintenance Manager:** Equipment oversight, maintenance coordination, review, and approval workflows.
4. **Maintenance Engineer:** Equipment condition monitoring, diagnostic reviews, and maintenance documentation.
5. **Viewer:** Read-only access to authorized information.

---

## API Documentation (Phase 2 Endpoints)

| Method | Endpoint | Access | Purpose |
|---|---|---|---|
| `GET` | `/` | Public | Service discovery |
| `GET` | `/api/v1/health` | Public | Health, database connectivity, and capability registry |
| `POST` | `/api/v1/auth/login` | Public (Rate Limited) | Authenticate user, set secure HttpOnly cookie |
| `POST` | `/api/v1/auth/logout` | Authenticated | Revoke session, clear cookie |
| `GET` | `/api/v1/auth/me` | Authenticated | Retrieve current user profile, organization, and permissions |
| `POST` | `/api/v1/auth/seed` | Dev / Bootstrap Key | Idempotently seed test organizations, roles, and users |
| `GET` | `/api/v1/organizations/current` | Authenticated | Get current tenant profile and site count |
| `GET` | `/api/v1/sites` | Authenticated | List manufacturing sites for user's organization |
| `GET` | `/api/v1/users` | Admin / Manager | List team members in user's organization |
| `POST` | `/api/v1/users/invite` | Admin | Issue single-use invitation token for new member |

---

## Pre-Configured Demo Accounts (Local Dev)

Seed the development database by clicking any pre-configured profile on `/login` or by calling `POST /api/v1/auth/seed`:

| Profile | Email | Password | Organization | Role |
|---|---|---|---|---|
| **Saad Javed** | `saad.javed@pharmapredict.ai` | `PharmaPredict@2026` | Getz Pharma | Maintenance Manager |
| **Org Admin** | `admin@getzpharma.com` | `Admin@Getz2026` | Getz Pharma | Organization Administrator |
| **Benchmark Engineer** | `engineer@benchmarkpharma.com` | `Benchmark@2026` | Benchmark Pharma | Maintenance Engineer |

---

## Quickstart & Local Development

### 1. Backend Setup & Automated Tests
```powershell
# Create venv and install dependencies
uv venv backend/.venv
uv pip install -r backend/requirements.txt --python backend/.venv/Scripts/python.exe

# Run complete 15-test automated security and health suite:
pnpm run test:backend
# Or directly with pytest:
.\backend\.venv\Scripts\pytest.exe backend/tests -v
```

### 2. Start Flask Backend
```powershell
.\backend\.venv\Scripts\python.exe backend/run.py
# Server runs on http://127.0.0.1:5000
```

### 3. Start Frontend Development Server
```powershell
pnpm dev
# Frontend runs on http://localhost:3000
```
- Landing Page: `http://localhost:3000`
- Sign In Page: `http://localhost:3000/login`
- Authenticated Dashboard: `http://localhost:3000/dashboard`
- Team Management: `http://localhost:3000/dashboard/users`
- Manufacturing Sites: `http://localhost:3000/dashboard/sites`

### 4. Running with Docker Compose (Full Stack)
```bash
docker compose up -d
```
