import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta

from app.extensions import db
from app.models.equipment import Machine
from app.models.signal_mapping import MachineSignal
from app.models.monitoring import SignalReading
from app.models.condition import (
    BaselineProfile,
    BaselineVersion,
    BaselineLifecycle,
    OperatingState,
)
from app.modules.baselines.builder import BaselineStatsCalculator

logger = logging.getLogger(__name__)


class BaselineService:
    """Manages creation, statistical calculation, and approval lifecycle of operating baselines."""

    MIN_BASELINE_SAMPLES = 10

    @classmethod
    def build_machine_baselines(
        cls,
        machine_id: str,
        organization_id: str,
        user_id: Optional[str] = None,
        operating_state: str = OperatingState.RUNNING,
        lookback_hours: int = 168,  # Default 7 days
    ) -> Dict[str, Any]:
        """Generate candidate statistical baseline profiles across all mapped signals."""
        machine = db.session.get(Machine, machine_id)
        if not machine or machine.organization_id != organization_id:
            raise ValueError("Equipment asset not found or access denied.")

        signals = MachineSignal.query.filter_by(
            machine_id=machine_id, organization_id=organization_id, enabled=True
        ).all()

        if not signals:
            raise ValueError("No active mapped signals found for baseline calculation.")

        now = datetime.now(timezone.utc)
        start_time = now - timedelta(hours=lookback_hours)

        profiles_created = 0
        profiles_updated = 0
        skipped_signals = []
        result_profiles = []

        for sig in signals:
            # Query clean readings (excluding bad quality codes or nulls)
            readings = (
                SignalReading.query.filter_by(signal_id=sig.id, machine_id=machine_id)
                .filter(SignalReading.source_timestamp >= start_time)
                .filter(SignalReading.quality_code.in_(["Good", "GOOD", "good", "Good_LocalOverride"]))
                .all()
            )

            values = [
                r.normalized_value for r in readings
                if r.normalized_value is not None
            ]

            if len(values) < cls.MIN_BASELINE_SAMPLES:
                skipped_signals.append({
                    "signal_id": sig.id,
                    "signal_name": sig.custom_name or sig.signal_code,
                    "reason": f"Insufficient clean samples ({len(values)} < {cls.MIN_BASELINE_SAMPLES})",
                })
                continue

            stats = BaselineStatsCalculator.calculate_statistics(values)
            if not stats:
                continue

            # Find or create BaselineProfile
            profile = BaselineProfile.query.filter_by(
                machine_id=machine_id,
                signal_id=sig.id,
                operating_state=operating_state,
            ).first()

            if not profile:
                profile = BaselineProfile(
                    organization_id=organization_id,
                    machine_id=machine_id,
                    component_id=sig.component_id,
                    signal_id=sig.id,
                    name=f"{sig.custom_name or sig.signal_code} - {operating_state} Baseline",
                    operating_state=operating_state,
                    lifecycle_status=BaselineLifecycle.CANDIDATE,
                )
                db.session.add(profile)
                db.session.flush()
                profiles_created += 1
            else:
                profile.lifecycle_status = BaselineLifecycle.CANDIDATE
                profiles_updated += 1

            # Next version number
            latest_v = (
                BaselineVersion.query.filter_by(profile_id=profile.id)
                .order_by(BaselineVersion.version_number.desc())
                .first()
            )
            v_num = (latest_v.version_number + 1) if latest_v else 1

            # Create immutable candidate version
            version = BaselineVersion(
                profile_id=profile.id,
                version_number=v_num,
                sample_count=stats["sample_count"],
                training_start_time=start_time,
                training_end_time=now,
                mean=stats["mean"],
                median=stats["median"],
                std=stats["std"],
                min_value=stats["min"],
                max_value=stats["max"],
                p5=stats["p5"],
                p25=stats["p25"],
                p75=stats["p75"],
                p95=stats["p95"],
                iqr=stats["iqr"],
                mad=stats["mad"],
                variability=stats["variability"],
                validation_status="VALID",
                validation_notes=f"Calculated from {stats['sample_count']} quality-validated measurements.",
                created_by=user_id,
            )
            db.session.add(version)
            result_profiles.append(profile.id)

        db.session.commit()

        return {
            "machine_id": machine_id,
            "machine_name": machine.equipment_name,
            "operating_state": operating_state,
            "profiles_created": profiles_created,
            "profiles_updated": profiles_updated,
            "total_candidates_ready": len(result_profiles),
            "skipped_signals": skipped_signals,
            "calculated_at": now.isoformat(),
        }

    @classmethod
    def approve_baseline(
        cls, profile_id: str, version_id: str, organization_id: str, user_id: str
    ) -> Dict[str, Any]:
        """Approve a candidate baseline version and transition profile to ACTIVE state."""
        profile = db.session.get(BaselineProfile, profile_id)
        if not profile or profile.organization_id != organization_id:
            raise ValueError("Baseline profile not found or access denied.")

        version = db.session.get(BaselineVersion, version_id)
        if not version or version.profile_id != profile_id:
            raise ValueError("Baseline version not found for this profile.")

        now = datetime.now(timezone.utc)
        version.approved_by = user_id
        version.approved_at = now
        version.validation_status = "APPROVED"

        profile.active_version_number = version.version_number
        profile.lifecycle_status = BaselineLifecycle.ACTIVE
        profile.updated_at = now

        db.session.commit()

        return {
            "message": "Baseline version successfully approved and activated.",
            "profile_id": profile.id,
            "version_number": version.version_number,
            "lifecycle_status": profile.lifecycle_status,
            "approved_at": now.isoformat(),
        }

    @classmethod
    def get_machine_baselines(
        cls, machine_id: str, organization_id: str
    ) -> List[Dict[str, Any]]:
        """Retrieve all baseline profiles and their active/candidate versions for a machine."""
        profiles = (
            BaselineProfile.query.filter_by(
                machine_id=machine_id, organization_id=organization_id
            )
            .order_by(BaselineProfile.name.asc())
            .all()
        )

        results = []
        for p in profiles:
            p_dict = p.to_dict()
            # Attach active version details
            active_version = None
            if p.active_version_number:
                active_version = BaselineVersion.query.filter_by(
                    profile_id=p.id, version_number=p.active_version_number
                ).first()

            latest_version = (
                BaselineVersion.query.filter_by(profile_id=p.id)
                .order_by(BaselineVersion.version_number.desc())
                .first()
            )

            p_dict["active_version"] = active_version.to_dict() if active_version else None
            p_dict["latest_candidate_version"] = latest_version.to_dict() if latest_version else None
            p_dict["signal_name"] = p.signal.custom_name if p.signal else None
            p_dict["normalized_unit"] = p.signal.normalized_unit if p.signal else None
            results.append(p_dict)

        return results

