# PharmaPredict AI — Production Deployment Architecture

**Document Reference:** ARCH-PHARMAPREDICT-001  
**Version:** 1.0.0  
**Effective Date:** 2026-11-01  
**Deployment Target:** High-Availability On-Premises Plant Cluster or Dedicated Private VPC

---

## 1. System Topology Overview

PharmaPredict AI follows a decoupled, resilient Edge-to-Core architectural pattern designed for high-availability industrial pharmaceutical operations:

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
│  │   NGINX Reverse Proxy │ ──(Internal Net)──►│   Flask 3.0 Backend     │  │
│  │   & TLS 1.3 Endpoint  │                    │   (Gunicorn / 4 Workers)│  │
│  └───────────┬───────────┘                    └────────────┬────────────┘  │
│              │                                             │               │
│              ▼                                             ▼               │
│  ┌───────────────────────┐                    ┌─────────────────────────┐  │
│  │   Next.js 14 Client   │                    │ PostgreSQL 16 +         │  │
│  │   Frontend Server     │                    │ TimescaleDB + pgvector  │  │
│  └───────────────────────┘                    └─────────────────────────┘  │
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

