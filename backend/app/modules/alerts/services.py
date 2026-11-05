from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from app.extensions import db
from app.models.condition import (
    EquipmentAlert,
    AlertHistory,
    AlertStatus,
    AnomalySeverity,
    AnomalyEvent,
)
from app.models.equipment import Machine


class AlertService:
    """Manages operational alert creation, deduplication, cooldown, and lifecycle audit history."""

    @classmethod
    def process_anomaly_alert(
        cls,
        organization_id: str,
        machine_id: str,
        anomaly_event_id: str,
        severity: str,
        component_id: Optional[str] = None,
        cooldown_minutes: int = 15,
    ) -> EquipmentAlert:
        """
        Creates or updates an operational alert for an anomaly event.
        Deduplicates against active alerts for the machine/anomaly and respects cooldown.
        """
        now = datetime.now(timezone.utc)

        # Check for existing open or active alert for this machine & anomaly
        existing_alert = EquipmentAlert.query.filter(
            EquipmentAlert.organization_id == organization_id,
            EquipmentAlert.machine_id == machine_id,
            EquipmentAlert.anomaly_id == anomaly_event_id,
            EquipmentAlert.status.in_([AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED, AlertStatus.UNDER_INVESTIGATION]),
        ).first()

        if existing_alert:
            existing_alert.last_detected_at = now
            # Elevate severity if incoming is more severe
            if severity == AnomalySeverity.CRITICAL and existing_alert.severity != AnomalySeverity.CRITICAL:
                old_sev = existing_alert.severity
                existing_alert.severity = AnomalySeverity.CRITICAL
                history = AlertHistory(
                    alert_id=existing_alert.id,
                    changed_by=None,
                    old_status=existing_alert.status,
                    new_status=existing_alert.status,
                    note=f"Alert severity elevated from {old_sev} to CRITICAL due to continued critical anomaly detection.",
                )
                db.session.add(history)
            db.session.commit()
            return existing_alert

        # Check machine-level cooldown
        recent_alert = EquipmentAlert.query.filter(
            EquipmentAlert.organization_id == organization_id,
            EquipmentAlert.machine_id == machine_id,
            EquipmentAlert.cooldown_until > now,
        ).order_by(EquipmentAlert.last_detected_at.desc()).first()

        if recent_alert and recent_alert.status in [AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED]:
            recent_alert.last_detected_at = now
            db.session.commit()
            return recent_alert

        # Create new alert
        new_alert = EquipmentAlert(
            organization_id=organization_id,
            machine_id=machine_id,
            component_id=component_id,
            anomaly_id=anomaly_event_id,
            severity=severity,
            status=AlertStatus.OPEN,
            first_detected_at=now,
            last_detected_at=now,
            cooldown_until=now + timedelta(minutes=cooldown_minutes),
        )
        db.session.add(new_alert)
        db.session.flush()

        # Record initial history
        history = AlertHistory(
            alert_id=new_alert.id,
            changed_by=None,
            old_status=None,
            new_status=AlertStatus.OPEN,
            note=f"Alert auto-generated from anomaly detection ({severity}).",
        )
        db.session.add(history)
        db.session.commit()
        return new_alert

    @classmethod
    def acknowledge_alert(
        cls,
        alert_id: str,
        organization_id: str,
        user_id: str,
        notes: Optional[str] = None,
    ) -> EquipmentAlert:
        """Marks alert as ACKNOWLEDGED and adds audit trail."""
        alert = EquipmentAlert.query.filter_by(id=alert_id, organization_id=organization_id).first()
        if not alert:
            raise ValueError(f"Alert {alert_id} not found.")

        old_status = alert.status
        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_by = user_id
        alert.acknowledged_at = datetime.now(timezone.utc)
        if notes:
            alert.resolution_notes = (alert.resolution_notes or "") + f"\nAcknowledgment: {notes}"

        history = AlertHistory(
            alert_id=alert.id,
            changed_by=user_id,
            old_status=old_status,
            new_status=AlertStatus.ACKNOWLEDGED,
            note=notes or "Alert acknowledged by engineer.",
        )
        db.session.add(history)
        db.session.commit()
        return alert

    @classmethod
    def update_alert_status(
        cls,
        alert_id: str,
        organization_id: str,
        user_id: str,
        new_status: str,
        notes: Optional[str] = None,
    ) -> EquipmentAlert:
        """Transitions alert status (e.g. UNDER_INVESTIGATION, RESOLVED, CLOSED)."""
        valid_statuses = [
            AlertStatus.OPEN,
            AlertStatus.ACKNOWLEDGED,
            AlertStatus.UNDER_INVESTIGATION,
            AlertStatus.RESOLVED,
            AlertStatus.CLOSED,
        ]
        if new_status not in valid_statuses:
            raise ValueError(f"Invalid alert status: {new_status}. Must be one of {valid_statuses}")

        alert = EquipmentAlert.query.filter_by(id=alert_id, organization_id=organization_id).first()
        if not alert:
            raise ValueError(f"Alert {alert_id} not found.")

        old_status = alert.status
        alert.status = new_status
        if notes:
            alert.resolution_notes = (alert.resolution_notes or "") + f"\n[{new_status}]: {notes}"

        history = AlertHistory(
            alert_id=alert.id,
            changed_by=user_id,
            old_status=old_status,
            new_status=new_status,
            note=notes or f"Status changed from {old_status} to {new_status}.",
        )
        db.session.add(history)
        db.session.commit()
        return alert

    @classmethod
    def get_organization_alerts(
        cls,
        organization_id: str,
        machine_id: Optional[str] = None,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Retrieves alerts with machine and anomaly details."""
        query = EquipmentAlert.query.filter_by(organization_id=organization_id)
        if machine_id:
            query = query.filter_by(machine_id=machine_id)
        if status:
            query = query.filter_by(status=status)
        if severity:
            query = query.filter_by(severity=severity)

        alerts = query.order_by(EquipmentAlert.last_detected_at.desc()).limit(limit).all()
        results = []
        for a in alerts:
            d = a.to_dict()
            d["machine_name"] = a.machine.equipment_name if a.machine else "Unknown"
            d["anomaly_summary"] = a.anomaly.summary if a.anomaly else ""
            results.append(d)
        return results

    @classmethod
    def get_alert_detail(cls, alert_id: str, organization_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves alert with full audit history and related anomaly."""
        alert = EquipmentAlert.query.filter_by(id=alert_id, organization_id=organization_id).first()
        if not alert:
            return None

        d = alert.to_dict()
        d["machine_name"] = alert.machine.equipment_name if alert.machine else "Unknown"
        d["anomaly"] = alert.anomaly.to_dict() if alert.anomaly else None
        d["history"] = [h.to_dict() for h in alert.history.order_by(AlertHistory.created_at.asc()).all()]
        return d
