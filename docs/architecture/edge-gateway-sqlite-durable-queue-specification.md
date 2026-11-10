# PharmaPredict AI — Edge Gateway SQLite Durable Queue Specification

**Document Reference:** SPEC-PHARMAPREDICT-EDGE-001  
**Task ID:** `P10-EDGE-001`  
**Title:** Durable SQLite-Backed Store-and-Forward Engine for Industrial OT Telemetry  
**GAMP 5 Category:** Category 5 (Custom Automation Software)  
**21 CFR Part 11 / Data Integrity Scope:** Complete ALCOA+ Audit Trail & Zero-Data-Loss Ingestion  
**Status:** Approved Engineering Specification (Pending Implementation & Hardware Test)  

---

## 1. Problem Statement & Current Deficiencies

The staging architecture audit identified that the existing edge telemetry buffering implementation in [`backend/app/modules/monitoring/gateway_buffer.py`](../../backend/app/modules/monitoring/gateway_buffer.py) (`BoundedGatewayBuffer`) has significant limitations for industrial production environments:

1. **Volatile In-Memory Queue:** The primary queue uses an in-memory `collections.deque` (capacity: 5,000 items). If the edge gateway host crashes, loses power, or restarts, all readings in RAM are permanently lost.
2. **Non-Transactional Disk Fallback:** The overflow mechanism appends unindexed JSON lines to a flat file (`gateway_overflow.jsonl`). Flat text files do not provide ACID crash guarantees, atomic transaction commits, or single-item acknowledgement, and risk file corruption upon sudden power loss.
3. **Limited Storage Ceiling:** At a typical industrial sampling rate of 10 readings/second (~200 bytes per reading $\approx$ 2 KB/s $\approx$ 172.8 MB/day), the hardcoded 50 MB disk ceiling is reached in approximately 7 hours. Once filled, subsequent incoming readings are irrevocably dropped.
4. **Current Verification Status:**
   - 24-hour continuous backend outage recovery: **NOT VERIFIED**.
   - Zero telemetry loss under sustained network disconnection: **NOT VERIFIED**.
   - Durable cross-restart queue persistence: **PARTIALLY VERIFIED** (RAM lost; JSONL recovered only if intact).

---

## 2. Target Architecture: SQLite-Backed Durable Store-and-Forward Engine

To guarantee zero data loss and compliance with 21 CFR Part 11 and GAMP 5 principles, the edge gateway buffering subsystem will be re-engineered around an embedded, ACID-compliant **SQLite database** running in **Write-Ahead Logging (WAL)** mode.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                  ON-PREMISES INDUSTRIAL EDGE GATEWAY                    │
│                                                                         │
│   OPC UA Client (AsyncIO) ──► Validation & Range Check ──► Normalizer   │
└───────────────────────────────────────────────────┬─────────────────────┘
                                                    │
                                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│               SQLITE DURABLE QUEUE ENGINE (`P10-EDGE-001`)              │
│                                                                         │
│   PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;                   │
│                                                                         │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │ Table: `telemetry_spool_queue`                                  │   │
│   │  - id: INTEGER PRIMARY KEY AUTOINCREMENT                        │   │
│   │  - event_id: TEXT UNIQUE NOT NULL                               │   │
│   │  - machine_id: TEXT NOT NULL                                    │   │
│   │  - signal_id: TEXT NOT NULL                                     │   │
│   │  - payload_json: TEXT NOT NULL                                  │   │
│   │  - status: TEXT ('pending', 'in_flight', 'acknowledged')        │   │
│   │  - retry_count: INTEGER DEFAULT 0                               │   │
│   │  - next_retry_at: REAL NOT NULL                                 │   │
│   │  - created_at: REAL NOT NULL                                    │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│   Indexes:                                                              │
│    - `idx_queue_status_retry`: (status, next_retry_at)                  │
│    - `idx_queue_event_id`: (event_id)                                   │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │
                                    │ Outbound HTTPS Batch Push
                                    │ (Lease-based transactional ACK)
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│              CLOUD BACKEND INGESTION (Render / Tiger Cloud)             │
│                                                                         │
│   HTTP POST /api/v1/monitoring/telemetry/batch                          │
│   - Returns: HTTP 200 { "processed": 50, "failed": [] }                 │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Detailed Technical Requirements

### 3.1 Persistence Across Process Restarts
* Every received reading message must be committed to the SQLite queue in a local transaction before the OPC UA subscription handler marks it received.
* SQLite must be initialized with:
  ```sql
  PRAGMA journal_mode = WAL;
  PRAGMA synchronous = NORMAL;
  PRAGMA busy_timeout = 5000;
  PRAGMA auto_vacuum = INCREMENTAL;
  ```
* On edge process restart, the queue engine must immediately query for `status IN ('pending', 'in_flight')` and resume delivery from where it stopped.

### 3.2 Transactional Delivery Acknowledgement (Lease Mechanism)
* Delivery worker leases batches of up to $N$ items (e.g. $N=100$):
  ```sql
  UPDATE telemetry_spool_queue
  SET status = 'in_flight',
      lease_expires_at = :now + 30.0,
      retry_count = retry_count + 1
  WHERE id IN (
      SELECT id FROM telemetry_spool_queue
      WHERE (status = 'pending' OR (status = 'in_flight' AND lease_expires_at < :now))
        AND next_retry_at <= :now
      ORDER BY id ASC
      LIMIT :batch_size
  );
  ```
* If the cloud backend responds with HTTP 200 and acknowledges receipt of `event_id` list:
  ```sql
  DELETE FROM telemetry_spool_queue WHERE id IN (:acknowledged_ids);
  ```
* If the cloud backend is unreachable, times out, or returns HTTP 5xx:
  * The lease naturally expires after 30 seconds.
  * The worker applies exponential backoff with jitter to `next_retry_at`:
    $$\Delta t = \min(60.0, \Delta t_0 \times 2^{\text{retry\_count}-1}) \pm \text{jitter}$$

### 3.3 Event Deduplication
* `event_id` is generated as a deterministic UUIDv5 or high-entropy UUIDv4 at the acquisition boundary.
* SQLite enforces `event_id TEXT UNIQUE`.
* Inserting an already spooled event is an idempotent no-op (`INSERT OR IGNORE`).

### 3.4 Configurable Retention, Capacity & Watermark Alarms
* Configurable parameters via `.env`:
  * `EDGE_SPOOL_MAX_SIZE_BYTES`: Default `1 * 1024 * 1024 * 1024` (1.0 GB).
  * `EDGE_SPOOL_HIGH_WATERMARK`: Default `0.80` (80% warning alert).
  * `EDGE_SPOOL_CRITICAL_WATERMARK`: Default `0.95` (95% emergency alert).
* Watermark monitoring thread checks DB file size every 30 seconds.
* When high watermark is breached: emits high-priority OT warning via local log and edge health status.
* When critical watermark is reached: enters emergency circular buffer eviction (purges oldest acknowledged telemetry or rejects non-critical signals, emitting a GAMP 5 audit event).

---

## 4. Empirical Verification & Test Suite Requirements

To close the `NOT VERIFIED` status and achieve production qualification, the implementation must pass the following automated test suite:

| Test Case ID | Test Name | Procedure | Acceptance Criteria |
| :--- | :--- | :--- | :--- |
| `TEST-EDGE-001` | `test_gateway_restart_durability` | Spool 2,500 readings, forcefully terminate process (`kill -9`), restart gateway. | 100% (2,500/2,500) readings recovered; zero loss. |
| `TEST-EDGE-002` | `test_transactional_ack_recovery` | Dispatch batch during simulated network drop (HTTP timeout). | Readings remain spooled; retried upon network restore. |
| `TEST-EDGE-003` | `test_event_deduplication` | Attempt duplicate insertion of identical `event_id`. | Idempotent ignore; exactly 1 reading in queue. |
| `TEST-EDGE-004` | `test_simulated_24h_backend_outage` | Simulate 24 hours of 10 Hz continuous signal acquisition (864,000 readings) with backend simulated offline. | Database stores all readings within allocated storage; zero crashes; full drain upon reconnection. |
| `TEST-EDGE-005` | `test_watermark_alarms_and_eviction` | Inject data until 80% and 95% watermarks are reached. | Correct structured alerts emitted; audit log records state. |

---

## 5. Implementation Roadmap

1. **Phase 10 Sprint 2:** Implement `SQLiteSpoolQueue` in `backend/app/modules/monitoring/sqlite_spool.py`.
2. **Phase 10 Sprint 2:** Wire `SQLiteSpoolQueue` into `MonitoringLifecycleManager`.
3. **Phase 10 Sprint 3:** Execute automated test suite `tests/test_edge_sqlite_spool.py` in CI.
4. **Phase 10 Sprint 3:** Mark GAMP 5 Requirement `REQ-INGEST-RELIABILITY-001` as **VERIFIED**.
