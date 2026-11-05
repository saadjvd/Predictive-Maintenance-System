# PharmaPredict AI — Phase 4, Step 6: Universal Signal Mapping & Validation

## Overview

The Universal Signal Mapping & Validation engine converts raw discovered OPC UA tags from diverse pharmaceutical machinery (such as blister packaging, tablet compression, capsule filling, and vial sealing equipment) into standardized, machine-agnostic predictive maintenance signals.

The system ensures:
1. **Manufacturer-Independent Taxonomy**: Uniform signal grouping across equipment makes and models.
2. **Dimensionally Sound Engineering Units**: Strictly disallows cross-dimensional conversions (e.g. vibration acceleration `g` vs velocity `mm/s`).
3. **Audit-Grade Verification**: 7-check automated validation engine executing strictly read-only inspection.
4. **Configuration Version Control**: Modifying a signal automatically increments `mapping_version` and resets validation status to `PENDING`.
5. **Multi-Tenant Isolation**: Tenant data boundaries enforced via organization scope on all definitions, mappings, and validation audits.

---

## Architecture & Data Flow

```
OPC UA Server (Edge / PLC)
    │
    ▼ (Step 5)
Automatic Tag Discovery
    │
    ▼ (Step 6)
Universal Signal Mapping Wizard
    ├── Group Assignment (Temperature, Vibration, Speed, Pressure, Current, Alarms, Cycles)
    ├── Standardized Signal Definition Catalog (or Tenant-Custom Definition)
    ├── Dimension-Safe Engineering Unit Normalizer
    ├── Linear Scaling Calibration (Multiplier & Offset)
    └── Sampling Interval Rate Configuration
    │
    ▼
Database Persistence
    ├── SignalDefinition (Catalog)
    ├── MachineSignal (Mapped Tag, versioned)
    └── SignalValidationResult (Audit Log)
    │
    ▼
7-Check Automated Validation Engine
    ├── 1. Node Class & Readability (Variable class, non-cyclic, read-allowed)
    ├── 2. Data Type Compatibility (Double, Float, Boolean, Int32)
    ├── 3. Unit Dimensional Compatibility (Dimension preservation check)
    ├── 4. Scaling Factor & Offset Bounds (Factor ≠ 0, finite floats)
    ├── 5. Sampling Interval Range (50ms – 3,600,000ms)
    ├── 6. Duplicate Assignment Protection (Unique NodeId per machine)
    └── 7. Strictly Read-Only Live Telemetry Sampling (Quality check & conversion)
    │
    ▼
Monitoring Readiness Assessment
    └── Ready for Monitoring (Step 7) when Total Signals > 0, Invalid = 0, Pending = 0
```

---

## Standardized Signal Groups & Default Catalog

| Signal Code | Standard Name | Group | Expected Type | Unit | Dimension | Description |
|---|---|---|---|---|---|---|
| `MOTOR_TEMP` | Motor Temperature | Temperature | Double | °C | `temperature` | Drive motor casing / stator temperature |
| `BEARING_TEMP` | Bearing Temperature | Temperature | Double | °C | `temperature` | Shaft / housing temperature |
| `SEALING_TEMP` | Sealing Temperature | Temperature | Double | °C | `temperature` | Blister / pouch thermal sealing station |
| `MOTOR_VIBRATION` | Motor Vibration Velocity | Vibration | Double | mm/s | `velocity` | Overall RMS vibration velocity |
| `BEARING_VIBRATION` | Bearing Vibration Acceleration | Vibration | Double | g | `acceleration` | High-frequency peak acceleration |
| `MOTOR_CURRENT` | Motor Current | Motor Current | Double | A | `electric_current` | Operating current draw in Amperes |
| `ROTATIONAL_SPEED` | Rotational Speed | Speed | Double | RPM | `rotational_speed` | Turret / shaft rotational velocity |
| `LINE_SPEED` | Line Speed | Speed | Double | m/s | `velocity` | Conveyor linear feed speed |
| `VACUUM_LEVEL` | Vacuum Level | Pressure | Double | bar | `pressure` | Forming / blister pocket vacuum |
| `LINE_PRESSURE` | Hydraulic / Pneumatic Line Pressure | Pressure | Double | bar | `pressure` | Main system operating line pressure |
| `FAULT_ALARM` | Machine Fault Alarm | Alarms | Boolean | Boolean | `discrete` | General trip or error flag |
| `EMERGENCY_STOP` | Emergency Stop Status | Alarms | Boolean | Boolean | `discrete` | Safety circuit status |
| `CYCLE_COUNTER` | Machine Cycle Counter | Cycles | Int32 | Count | `count` | Cumulative stroke / cycle counter |
| `PRODUCTION_COUNT` | Production Batch Count | Cycles | Int32 | Count | `count` | Units produced in active batch |

---

## Unit Normalization & Dimension Safety Rules

The normalization engine (`UnitNormalizer`) strictly enforces physical dimensionality:

```python
# Allowed conversions (same physical dimension)
UnitNormalizer.convert(100.0, "°C", "°F")       # -> 212.0 °F
UnitNormalizer.convert(1.0, "bar", "psi")        # -> 14.5038 psi
UnitNormalizer.convert(1.0, "m/s", "mm/s")       # -> 1000.0 mm/s

# Disallowed conversions (cross-dimension raises IncompatibleUnitError)
UnitNormalizer.convert(1.5, "g", "mm/s")         # -> IncompatibleUnitError: Cannot convert acceleration to velocity
UnitNormalizer.convert(50.0, "°C", "bar")        # -> IncompatibleUnitError: Cannot convert temperature to pressure
```

---

## REST API Reference

All endpoints are scoped to `/api/v1` and enforce tenant isolation.

### 1. Signal Definitions Catalog
- `GET /api/v1/signals/definitions?group={group}`
  - Fetches standard catalog definitions and organization custom definitions.
- `POST /api/v1/signals/definitions`
  - Creates a custom signal definition for the active tenant organization.
  - Requires: `Organization Administrator`, `Maintenance Manager`, or `Maintenance Engineer`.

### 2. Equipment Signal Mappings
- `GET /api/v1/equipment/:machine_id/signals`
  - Lists all mapped signals for a machine.
- `POST /api/v1/equipment/:machine_id/signals`
  - Maps one or multiple OPC UA tags to standardized signals.
  - Body: single object or `{ "signals": [ ... ] }`.
- `PATCH /api/v1/equipment/:machine_id/signals/:signal_id`
  - Updates signal mapping parameters.
  - **Side-effect**: Increments `mapping_version += 1`, resets `validation_status` to `PENDING`.
- `DELETE /api/v1/equipment/:machine_id/signals/:signal_id`
  - Deletes signal mapping and cascades associated validation logs.

### 3. Signal Validation Engine
- `POST /api/v1/equipment/:machine_id/signals/validate`
  - Executes the 7 validation checks on the machine's signals.
  - Strictly read-only connection to OPC UA server or simulated server.
  - Returns validation results and summary metrics.
- `GET /api/v1/equipment/:machine_id/signals/validation-results`
  - Retrieves audit history of validation runs for the machine.
- `GET /api/v1/equipment/:machine_id/signals/mapping-summary`
  - Returns `total_signals`, `valid_count`, `warning_count`, `invalid_count`, `pending_count`, `group_breakdown`, and `ready_for_monitoring`.

---

## Verification & Automated Test Suite

Run the full automated test suite:
```bash
backend\.venv\Scripts\pytest.exe backend\tests -v
```

Summary:
- **74 tests passing** across `test_auth.py`, `test_equipment.py`, `test_health.py`, `test_opcua_client.py`, `test_tag_discovery.py`, and `test_signal_mapping.py`.
- **TypeScript compilation**: 0 errors (`pnpm exec tsc --noEmit`).

