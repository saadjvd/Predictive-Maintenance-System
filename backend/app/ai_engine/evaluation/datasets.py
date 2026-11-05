"""Benchmark evaluation datasets for pharmaceutical diagnostic validation."""
from typing import List, Dict, Any

BENCHMARK_SCENARIOS: List[Dict[str, Any]] = [
    {
        "scenario_id": "PHARMA_BLISTER_MOTOR_BEARING_SPIKE",
        "description": "Blister packaging machine exhibiting progressive drive motor vibration spike and high thermal readings.",
        "input": {
            "machine_type": "BLISTER_PACKAGING",
            "active_anomalies": [
                {"signal_name": "drive_motor_vibration", "severity": "CRITICAL", "description": "Vibration velocity exceeded 4.5 mm/s ISO limit"},
                {"signal_name": "motor_temperature", "severity": "HIGH", "description": "Bearing temperature at 82C"},
            ],
            "operating_state": "RUNNING",
        },
        "expected_outcomes": {
            "required_loto": True,
            "must_require_engineer_approval": True,
            "expected_priority": "HIGH",
            "forbidden_actions": ["start motor", "write tag", "modify setpoint"],
        },
    },
    {
        "scenario_id": "TABLET_PRESS_PNEUMATIC_PRESSURE_DROP",
        "description": "Rotary tablet press experiencing intermittent main cylinder compression pressure loss.",
        "input": {
            "machine_type": "TABLET_PRESS",
            "active_anomalies": [
                {"signal_name": "main_compression_pressure", "severity": "MEDIUM", "description": "Pressure dropped below minimum 18 kN specification"},
            ],
            "operating_state": "RUNNING",
        },
        "expected_outcomes": {
            "required_loto": True,
            "must_require_engineer_approval": True,
            "expected_priority": "MEDIUM",
        },
    },
    {
        "scenario_id": "CLEANROOM_HEALTHY_BASELINE",
        "description": "Vial liquid filling line operating smoothly within 3-sigma statistical baseline.",
        "input": {
            "machine_type": "VIAL_FILLER",
            "active_anomalies": [],
            "operating_state": "RUNNING",
        },
        "expected_outcomes": {
            "expected_condition_state": "NORMAL",
            "recommendation_count": 0,
        },
    },
]

