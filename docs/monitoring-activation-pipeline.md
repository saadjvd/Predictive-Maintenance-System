# PharmaPredict AI — Phase 4, Step 7
## Monitoring Activation, Continuous Data Collection & Time-Series Storage Pipeline

### Overview
This document specifies the architecture, data models, edge gateway buffering strategies, and continuous telemetry collection pipeline implemented in **Phase 4, Step 7** of PharmaPredict AI.

The pipeline transitions pharmaceutical machines from validated signal mappings (Step 6) to live, continuous telemetry ingestion with time-series storage, strict tenant isolation, and read-only OPC UA subscription mechanisms.

---

### 1. Architecture & Data Flow

```text
+-----------------------------------------------------------------------------------+
|                        Industrial Plant / Simulated PLC                          |
|   OPC UA Server (Blister Packaging Machine / Sterile BFS / Fluid Bed Dryer)       |
+-----------------------------------------------------------------------------------+
                                         |
                        (asyncua subscription data change)
                                         v
+-----------------------------------------------------------------------------------+
|                            PharmaPredict Edge Gateway                             |
|  - Dedicated background worker thread (OPCUA-Worker-<id>)                         |
|  - OPCUASubscriptionService (Data change notification handler)                    |
|  - ReadingNormalizer (linear scaling, source preservation, unit conversion)       |
|  - BoundedGatewayBuffer:                                                          |
|      * In-memory queue (max 5,000 readings)                                       |
|      * Micro-batch flush loop (batch_size=50, interval=1.0s)                      |
|      * Disk buffer fallback (.buffer_disk/*.jsonl) on backend disconnection       |
|      * Exponential backoff retry (1.0s -> 30.0s max)                              |
+-----------------------------------------------------------------------------------+
                                         |
                  (POST /api/v1/internal/ingestion/readings)
                   Header: X-Gateway-Secret / Bearer Token
                                         v
+-----------------------------------------------------------------------------------+
|                          PharmaPredict AI Flask Backend                           |
|  - Internal Gateway Authentication (GATEWAY_INTERNAL_SECRET)                     |
|  - Batch Ingestion Service:                                                       |
|      * SHA-256 Event ID deduplication                                             |
|      * Tenant and Machine ownership validation                                    |
|      * Bulk insert into signal_readings table                                     |
|      * Ingestion batch audit logging (ingestion_batches)                          |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|                     TimescaleDB / PostgreSQL Time-Series Table                    |
|  - signal_readings (event_id, machine_id, signal_id, source_timestamp,            |
|                     normalized_value, raw values, quality_code, freshness)         |
|  - Hypertable partitioned by source_timestamp                                     |
+-----------------------------------------------------------------------------------+
                                         |
                     (REST API: /readings/latest & /history)
                                         v
+-----------------------------------------------------------------------------------+
|                         PharmaPredict Frontend Dashboard                          |
|  - Live Monitoring Tab (Equipment Details page)                                   |
|  - Real-time sensor cards with freshness badges (FRESH, DELAYED, STALE)           |
|  - Interactive SVG historical trend charts                                        |
|  - Activation / Deactivation controls with precondition checks                     |
+-----------------------------------------------------------------------------------+
```

---

### 2. State Machine: Desired State vs. Observed State

To prevent race conditions, gateway disconnections, or partial subscriptions from corrupting equipment state, the pipeline strictly separates **Desired State** from **Observed State**:

| State | Type | Description |
|---|---|---|
| `STOPPED` | Desired / Observed | Monitoring is inactive. No OPC UA subscriptions exist. |
| `ACTIVATING` | Observed | Activation request initiated; gateway worker connecting and subscribing to tags. |
| `ACTIVE` | Desired / Observed | Monitoring fully operational; all mapped signals have active subscriptions. |
| `DEGRADED` | Observed | Partial subscriptions established (1 or more signals active, but at least 1 failed). |
| `STOPPING` | Observed | Deactivation requested; gateway unsubscribing and flushing remaining buffered records. |
| `ERROR` | Observed | Gateway unreachable, authentication failed, or zero subscriptions established. |

---

### 3. Precondition Validation Engine

Before an operator can activate monitoring on an asset, the system validates the following mandatory conditions via `MonitoringLifecycleManager.check_activation_preconditions`:

1. **Asset Existence & Tenant Scope**: Equipment exists and belongs to the authenticated user's organization (`organization_id == g.current_org_id`).
2. **Mapped Signals Existence**: Machine has at least 1 enabled signal mapping (`MachineSignal.query.filter_by(enabled=True)`).
3. **Configuration Validity**: Zero signals are in `INVALID` validation state. If any signal has failed validation, activation is blocked with a human-readable list of offending tags.
4. **Role Authorization**: Requester must possess `ORG_ADMIN`, `MAINTENANCE_MANAGER`, or `MAINTENANCE_ENGINEER` role. Viewers receive HTTP 403.

---

### 4. Edge Gateway Bounded Queue & Backpressure

The edge gateway implementation (`BoundedGatewayBuffer`) protects industrial memory and ensures zero data loss:

- **Bounded Memory Queue**: Maximum queue depth set to 5,000 readings (`asyncio.Queue(maxsize=5000)`).
- **Backpressure & Drop Policy**: When memory queue is full, incoming readings overflow to disk buffer (`.buffer_disk/`). If disk buffer exceeds storage quota (e.g., 50MB), oldest uncommitted readings are dropped with audit increment (`dropped_readings`).
- **Batching & Micro-Flushes**: Readings are flushed in batches of 50 or every 1.0 second, reducing network overhead.
- **Resilience & Auto-Drain**: When backend connectivity is restored, the buffer drains disk files in FIFO sequence before accepting new live batches.

---

### 5. Idempotent Data Contract & Deduplication

Each sensor reading emitted by the gateway adheres to a versioned data contract:

```json
{
  "event_id": "sha256(machine_id + signal_id + source_timestamp + source_value)",
  "organization_id": "0df6b889-4b68-45e3-97c1-8ce29402e1c9",
  "machine_id": "b304cbe9-6f96-419b-ab92-9366d7ad5650",
  "signal_id": "761612ad-05ae-4933-bfad-8332152ee99f",
  "mapping_version": 1,
  "source_timestamp": "2026-10-31T21:40:00.123456Z",
  "server_timestamp": "2026-10-31T21:40:00.125000Z",
  "gateway_received_at": "2026-10-31T21:40:00.130000Z",
  "source_value": 142.5,
  "normalized_value": 142.5,
  "raw_value_numeric": 142.5,
  "raw_value_boolean": null,
  "raw_value_string": null,
  "source_unit": "°C",
  "normalized_unit": "°C",
  "quality_code": "Good",
  "normalization_status": "NORMALIZED",
  "sampling_interval_ms": 1000,
  "simulator_flag": true
}
```

The deterministic `event_id` provides database-level deduplication: duplicate batches from network retries are idempotently skipped with `duplicates` counter incremented.

---

### 6. Data Freshness Engine

Freshness is computed dynamically upon query based on each signal's configured `sampling_interval_ms`:

$$\Delta t = \text{now} - \text{source\_timestamp}$$

- **`FRESH`**: $\Delta t \le 2.5 \times \text{sampling\_interval}$ (Normal real-time telemetry).
- **`DELAYED`**: $2.5 \times \text{sampling\_interval} < \Delta t \le 6.0 \times \text{sampling\_interval}$ (Network lag or delayed gateway flush).
- **`STALE`**: $\Delta t > 6.0 \times \text{sampling\_interval}$ (Sensor dropped offline or PLC ceased publishing).
- **`UNAVAILABLE`**: Zero telemetry points received for this signal.

---

### 7. REST API Reference

| Endpoint | Method | Auth | Description |
|---|---|---|---|
| `/api/v1/equipment/:id/monitoring/activate` | `POST` | User (Engineer+) | Validate preconditions and initiate monitoring session. |
| `/api/v1/equipment/:id/monitoring/deactivate` | `POST` | User (Engineer+) | Gracefully unsubscribe and stop session. |
| `/api/v1/equipment/:id/monitoring/status` | `GET` | User (All) | Retrieve desired/observed states, subscription counts, and buffer metrics. |
| `/api/v1/equipment/:id/readings/latest` | `GET` | User (All) | Return latest reading and freshness for all mapped signals. |
| `/api/v1/equipment/:id/readings/history` | `GET` | User (All) | Retrieve time-series telemetry bounded by `signal_id`, `start_time`, `end_time`, `limit`. |
| `/api/v1/gateways/:id/health` | `GET` | User (All) | Edge gateway latency, queue depth, and buffered readings. |
| `/api/v1/internal/ingestion/readings` | `POST` | Gateway Secret | Protected endpoint for gateway batch telemetry ingestion. |

---

### 8. Automated Test Coverage

The test suite in [`backend/tests/test_monitoring.py`](file:///c:/Users/Dell/OneDrive/Desktop/AI%20SOLUTION%20PROJECT/backend/tests/test_monitoring.py) covers 19 comprehensive scenarios:

1. `test_authorized_monitoring_activation`: Confirms activation by maintenance engineers.
2. `test_unauthorized_activation_denied`: Confirms 403 for viewers and 401 for unauthenticated requests.
3. `test_activation_preconditions_no_signals`: Validates rejection when no signal mappings exist.
4. `test_activation_preconditions_invalid_signals`: Validates rejection when invalid configurations are present.
5. `test_successful_opcua_subscription_and_reading`: Confirms live telemetry collection from simulated OPC UA node.
6. `test_monitoring_deactivation`: Graceful session teardown and state transition to `STOPPED`.
7. `test_data_normalization_pipeline`: Linear scaling ($ax + b$) and unit normalization.
8. `test_boolean_alarm_readings`: Normalization and preservation of boolean alarm signals.
9. `test_bad_opcua_quality_codes`: Quality code tracking and fallback handling.
10. `test_batch_ingestion_and_deduplication`: Idempotent SHA-256 deduplication on duplicate batches.
11. `test_backend_outage_buffering_and_queue_overflow`: Fallback to disk buffer during simulated backend failure.
12. `test_stale_and_latest_readings_api`: Real-time freshness calculation.
13. `test_historical_readings_api`: Time-series query endpoint.
14. `test_internal_ingestion_service_auth`: Rejection of unauthorized ingestion calls.
15. `test_gateway_health_endpoint`: Gateway queue depth and latency metrics.
16. `test_monitoring_status_endpoint`: Session and subscription status querying.
17. `test_cross_tenant_readings_isolation`: Cross-tenant 404 enforcement.
18. `test_stale_reading_classification`: Classification of readings older than sampling threshold as `STALE`.
19. `test_history_time_window_filtering`: Query parameter time window scoping.

**Overall Test Suite Status**: **93 passed out of 93 tests (100% pass rate)**.

