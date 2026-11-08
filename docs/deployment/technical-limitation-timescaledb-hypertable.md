# PharmaPredict AI — Technical Limitation & Future Production Parity

**Document Reference:** TL-PHARMAPREDICT-TIMESCALEDB-001  
**Category:** Database Architecture & Time-Series Data Modeling  
**Associated Release:** Cloud Staging (Phase 10 — Enterprise Productization)  
**Date:** November 2026  
**Status:** Approved Technical Limitation (Option A Selected)

---

## 1. Executive Summary

During the cloud staging readiness verification for PharmaPredict AI on PostgreSQL 16 with the TimescaleDB extension (Tiger Cloud), an architectural limitation was identified regarding the conversion of the primary telemetry table (`signal_readings`) into a native TimescaleDB hypertable.

By explicit decision of the technical authority, **Option A (Standard Indexed PostgreSQL Table)** was approved for the zero-cost cloud staging deployment. This document records the technical limitation, explains why it occurs, confirms the functional safety of the current staging deployment, and defines the future Phase 10 production-parity implementation plan (Option B).

---

## 2. Root Cause Analysis

### 2.1 Schema Definition in `0001_initial_schema.py`
In Alembic migration revision `0001_initial_schema.py` (lines 1044–1082):
```python
op.create_table('signal_readings',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('event_id', sa.String(length=128), nullable=False),
    sa.Column('organization_id', sa.String(length=36), nullable=False),
    sa.Column('machine_id', sa.String(length=36), nullable=False),
    sa.Column('signal_id', sa.String(length=36), nullable=False),
    sa.Column('source_timestamp', sa.DateTime(timezone=True), nullable=False),
    ...
    sa.PrimaryKeyConstraint('id')
)
with op.batch_alter_table('signal_readings', schema=None) as batch_op:
    batch_op.create_index('ix_signal_readings_event_id', ['event_id'], unique=True)
    ...
```

### 2.2 TimescaleDB Hypertable Partitioning Constraint
TimescaleDB partitions hypertable data into underlying chunks based on a time column (`source_timestamp`). To guarantee uniqueness across all distributed or time-partitioned chunks without requiring an expensive cross-chunk scan on every insert, **TimescaleDB enforces a strict rule**:
> *Every unique index and primary key on a hypertable must include all partitioning columns.*

Because `signal_readings` defines `PRIMARY KEY (id)` and `UNIQUE INDEX ix_signal_readings_event_id (event_id)` without `source_timestamp`, executing `SELECT create_hypertable('signal_readings', 'source_timestamp');` raises:
```text
ERROR: cannot create a unique index without the column "source_timestamp" (used in partitioning)
HINT: If you're creating a hypertable on a table with a primary key, ensure the partitioning column is part of the primary or composite key.
```

### 2.3 Migration Exception Handling
In `0001_initial_schema.py` (lines 1094–1105), the hypertable conversion is enclosed in an exception handler:
```sql
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
        BEGIN
            PERFORM create_hypertable('signal_readings', 'source_timestamp', if_not_exists => TRUE, migrate_data => TRUE);
        EXCEPTION WHEN OTHERS THEN
            RAISE NOTICE 'TimescaleDB hypertable conversion skipped: %', SQLERRM;
        END;
    END IF;
END $$;
```
The exception is caught, a PostgreSQL `NOTICE` is emitted, and the migration proceeds to completion (exit code 0). Consequently:
- **TimescaleDB Extension Status:** `INSTALLED` and `AVAILABLE`.
- **`signal_readings` Architecture Status:** `STANDARD POSTGRESQL TABLE` (Not a hypertable).

---

## 3. Staging Impact & Functional Verification

### 3.1 Verification Findings
- **Data Integrity:** All 57 tables, 213 indexes, and foreign keys are created successfully.
- **ORM Compatibility:** The SQLAlchemy model `SignalReading` operates seamlessly. All existing queries filter by `signal_id`, `machine_id`, `organization_id`, and `source_timestamp`, all of which are covered by existing composite B-tree indexes:
  - `ix_readings_machine_time` (`machine_id`, `source_timestamp`)
  - `ix_readings_signal_time` (`signal_id`, `source_timestamp`)
  - `ix_readings_org_time` (`organization_id`, `source_timestamp`)
- **Storage Metrics:** The entire 57-table schema occupies **12.0 MB** in PostgreSQL 16. On Tiger Cloud's 750 MiB permanent free tier, this leaves **738.0 MiB (98.4% free space)**.
- **Zero Cost:** No paid compute, storage add-ons, or upgrades are needed.

### 3.2 Explicit Disclaimers
1. TimescaleDB extension availability is distinct from hypertable status: while the extension is loaded, `signal_readings` is **not** a hypertable.
2. Native TimescaleDB time-series chunk partitioning, chunk exclusion, and continuous aggregates are **inactive** for `signal_readings` in staging.
3. Native columnar compression (`timescaledb.compress`) is **inactive** for `signal_readings` in staging.

---

## 4. Future Phase 10 Production-Parity Task (Option B Implementation Plan)

For high-volume multi-site enterprise production (Issue #71 / P10-F02), `signal_readings` will ingest hundreds of thousands of readings daily, making hypertable chunking and 90%+ columnar compression advantageous.

### Required Task Specification
- **Task ID:** `P10-DB-002`
- **Title:** `feat(db): enable TimescaleDB hypertable partitioning with composite primary key`
- **Target Branch:** Future PR targeting `phase/10-enterprise-productization`

### Implementation Steps:
1. **Schema Migration (`backend/migrations/versions/0002_timescaledb_hypertable_composite_pk.py`):**
   - Alter `signal_readings` primary key from `(id)` to composite `(id, source_timestamp)`.
   - Drop unique index `ix_signal_readings_event_id` on `(event_id)`.
   - Recreate composite unique index `ix_signal_readings_event_time` on `(event_id, source_timestamp)`.
   - Execute `SELECT create_hypertable('signal_readings', 'source_timestamp', if_not_exists => TRUE, migrate_data => TRUE);`.
   - Configure chunk time interval: `SELECT set_chunk_time_interval('signal_readings', INTERVAL '7 days');`.
   - Enable compression policy:
     ```sql
     ALTER TABLE signal_readings SET (
         timescaledb.compress,
         timescaledb.compress_segmentby = 'organization_id,machine_id,signal_id',
         timescaledb.compress_orderby = 'source_timestamp DESC'
     );
     SELECT add_compression_policy('signal_readings', INTERVAL '30 days');
     ```
2. **SQLAlchemy ORM Model Update (`backend/app/models/monitoring.py`):**
   ```python
   id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
   source_timestamp = db.Column(db.DateTime(timezone=True), primary_key=True, nullable=False, index=True)
   ```
3. **Automated Migration & Regression Test:**
   - Execute migration test verifying `SELECT hypertable_name FROM timescaledb_information.hypertables;` returns `'signal_readings'`.
   - Verify all unit and integration tests in `backend/tests/` pass without regression.
