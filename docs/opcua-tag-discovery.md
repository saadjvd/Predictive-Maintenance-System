# PharmaPredict AI — Phase 4, Step 5: Automatic OPC UA Tag Discovery

## 1. Executive Summary

Phase 4, Step 5 implements the **Universal Automatic OPC UA Tag Discovery Engine** for PharmaPredict AI. This system enables authorized pharmaceutical maintenance engineers and platform administrators to inspect connected PLC/industrial gateway address spaces, browse hierarchical machine nodes, extract rich metadata (Browse Names, Display Names, Data Types, Access Levels, and Engineering Units), search signals, and select relevant sensor variables for predictive maintenance monitoring without hardcoding NodeIds or machine-specific schemas.

---

## 2. System Architecture

```
+-------------------------------------------------------------------------+
|                  PharmaPredict AI Next.js Frontend                      |
|       (TagDiscoveryPanel, Expandable Tree, Selection Tray, Search)      |
+-------------------------------------------------------------------------+
                                    |
                           HTTPS / REST API
                                    v
+-------------------------------------------------------------------------+
|                        Flask REST API Layer                             |
|       (Role-Based Authorization, Multi-Tenant Partitioning)             |
|   GET  /api/v1/connectors/:id/tags                                      |
|   GET  /api/v1/connectors/:id/tags/metadata                             |
|   POST /api/v1/connectors/:id/tags/search                               |
+-------------------------------------------------------------------------+
                                    |
                    Authenticated Gateway Service
                                    v
+-------------------------------------------------------------------------+
|                   TagDiscoveryService (asyncua)                         |
|   - Bounded browse depth (default: 3 levels, max: 4)                    |
|   - Max nodes truncation (default: 100, max: 150)                       |
|   - Cycle protection (visited NodeId set preventing circular loops)     |
|   - Universal metadata extraction (extract_node_metadata)               |
|   - Search and live readability validation                              |
+-------------------------------------------------------------------------+
                                    |
                        Connection Lifecycle Manager
                                    v
+-------------------------------------------------------------------------+
|                     SecureOPCUAClient (Async)                           |
|   - Strict Read-Only Enforcement (ReadOnlyError on write attempts)      |
|   - Thread-isolated async worker loop                                   |
|   - Bounded exponential backoff reconnection                            |
+-------------------------------------------------------------------------+
                                    |
                          OPC UA Binary Protocol
                                    v
+-------------------------------------------------------------------------+
|                  PharmaOPCUASimulator (Simulated Equipment)             |
|   - Blister Packaging Machine 01                                        |
|     * Speed_CPM (Double, 240.0)                                         |
|     * SealingTemperature (Double, 142.5 °C)                             |
|     * MainDriveMotorVibration (Double, 1.25 mm/s)                       |
|     * VacuumLevel (Double, -85.2 kPa)                                   |
+-------------------------------------------------------------------------+
```

---

## 3. Discovered Tag Normalized Structure

Each discovered node is normalized into a consistent, JSON-serializable structure according to Phase 4 specifications:

```json
{
  "node_id": "ns=2;i=2",
  "browse_name": "Speed_CPM",
  "display_name": "Speed_CPM",
  "node_class": "Variable",
  "data_type": "Double",
  "engineering_unit": null,
  "description": null,
  "access_level": 1,
  "namespace": 2,
  "parent_node_id": "ns=2;i=1",
  "readable": true,
  "writable": false,
  "has_children": false,
  "children": []
}
```

*Note: In accordance with Rule 3, missing metadata (such as descriptions or engineering units not defined on the PLC) is retained as `null` rather than fabricated.*

---

## 4. Files Created and Modified

| File | Action | Purpose |
|------|--------|---------|
| `backend/app/modules/connectivity/discovery/node_metadata.py` | **Created** | Universal `DiscoveredTag` data model and asynchronous `extract_node_metadata()` helper. |
| `backend/app/modules/connectivity/discovery/tag_discovery.py` | **Created** | `TagDiscoveryService` with `browse_root()`, `browse_children()`, `get_node_metadata()`, `search_discovered_tags()`, and `validate_readable_node()`. |
| `backend/app/modules/connectivity/discovery/__init__.py` | **Created** | Package exports for tag discovery service and models. |
| `backend/app/modules/connectivity/routes.py` | **Modified** | Added discovery endpoints under both `/connectivity/tags/...` and `/connectors/.../tags`. |
| `backend/app/api/v1/__init__.py` | **Modified** | Registered `connectors_bp` on `api_v1_bp`. |
| `lib/api-client.ts` | **Modified** | Added `DiscoveredTag` interface and `getDiscoveredTags`, `getTagMetadata`, `searchTags` methods. |
| `components/equipment/tag-discovery-panel.tsx` | **Created** | Interactive UI panel with connection status, address space tree, search bar, and signal selection tray. |
| `app/dashboard/equipment/[id]/page.tsx` | **Modified** | Added "OPC UA Tag Discovery" tab and direct discovery launch button. |
| `backend/tests/test_opcua_client.py` | **Created** | 8 automated tests for Step 4 secure OPC UA client. |
| `backend/tests/test_tag_discovery.py` | **Created** | 16 automated tests for Step 5 tag discovery service and Flask APIs. |

---

## 5. API Reference

### 5.1 Discover Root Address Space
- **Endpoint:** `GET /api/v1/connectors/:id/tags` or `GET /api/v1/connectivity/tags/:id`
- **Headers:** `Authorization: Bearer <session_token>`
- **Query Parameters:**
  - `endpoint_url` (optional): Target server URL if not using existing active gateway.
  - `depth` (optional, default: 3): Bounded recursive browse depth.
  - `max_nodes` (optional, default: 100): Node limit to prevent resource exhaustion.
- **Response:**
  ```json
  {
    "machine_id": "...",
    "count": 1,
    "tags": [ ... ]
  }
  ```

### 5.2 Node Metadata Lookup
- **Endpoint:** `GET /api/v1/connectors/:id/tags/metadata`
- **Query Parameters:**
  - `node_id`: Target NodeId (e.g. `ns=2;i=2`).
- **Response:**
  ```json
  {
    "metadata": { ... }
  }
  ```

### 5.3 Signal Search
- **Endpoint:** `POST /api/v1/connectors/:id/tags/search`
- **Request Body:**
  ```json
  {
    "query": "vibration",
    "endpoint_url": "opc.tcp://127.0.0.1:48401/pharmapredict/server/"
  }
  ```
- **Response:**
  ```json
  {
    "machine_id": "...",
    "query": "vibration",
    "count": 1,
    "tags": [ ... ]
  }
  ```

---

## 6. Verification and Test Results

The backend automated test suite verifies both Step 4 and Step 5 in full:

```
============================= test session starts =============================
collected 53 items

backend/tests/test_auth.py: 12 passed
backend/tests/test_equipment.py: 14 passed
backend/tests/test_health.py: 3 passed
backend/tests/test_opcua_client.py: 8 passed
  - test_successful_connection PASSED
  - test_invalid_endpoint PASSED
  - test_wrong_credentials PASSED
  - test_untrusted_certificate_rejected PASSED
  - test_server_shutdown_detection PASSED
  - test_bounded_reconnection_backoff PASSED
  - test_graceful_disconnection PASSED
  - test_no_write_operations PASSED

backend/tests/test_tag_discovery.py: 16 passed
  - test_successful_tag_discovery PASSED
  - test_nested_node_browsing PASSED
  - test_metadata_extraction PASSED
  - test_missing_engineering_units_not_fabricated PASSED
  - test_unsupported_node_types_handled PASSED
  - test_invalid_node_id_handling PASSED
  - test_disconnected_client_raises_error PASSED
  - test_bounded_browse_depth PASSED
  - test_max_nodes_per_request_limit PASSED
  - test_cycle_protection PASSED
  - test_search_discovered_tags PASSED
  - test_validate_readable_node PASSED
  - test_discovery_read_only_enforcement PASSED
  - test_normalized_tag_dictionary PASSED
  - test_unauthenticated_discovery_denied PASSED
  - test_cross_org_discovery_denied PASSED

============================= 53 passed in 57.41s =============================
```

Frontend typecheck:
`pnpm exec tsc --noEmit` exited with code 0 (zero errors).

---

## 7. Next Step

**Phase 4, Step 6 — Universal Signal Mapping and Validation**:
- Map discovered raw OPC UA variables to standard pharmaceutical signal archetypes (e.g., motor vibration, bearing temperature, line speed, vacuum level, hydraulic pressure).
- Configure sampling intervals and unit conversions.
- Establish initial baseline ranges and physical validation bounds.

