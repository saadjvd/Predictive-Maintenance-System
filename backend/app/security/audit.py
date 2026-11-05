import json
from flask import request
from app.extensions import db
from app.models.user import AuditLog


def log_audit_event(action: str, organization_id: str = None, user_id: str = None, details: dict = None):
    """Record an audit trail event for security and compliance."""
    try:
        ip_address = request.remote_addr if request else None
        details_str = json.dumps(details) if isinstance(details, dict) else str(details or "")

        log = AuditLog(
            action=action,
            organization_id=organization_id,
            user_id=user_id,
            details=details_str,
            ip_address=ip_address
        )
        db.session.add(log)
        db.session.commit()
    except Exception:
        db.session.rollback()

