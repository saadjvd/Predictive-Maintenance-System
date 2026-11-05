import secrets
from datetime import datetime, timedelta, timezone
from flask import current_app
from app.extensions import db
from app.models.user import UserSession


def create_user_session(user_id: str, ip_address: str = None, user_agent: str = None, lifetime_hours: int = 24) -> UserSession:
    """Create a new database-backed session for a user."""
    token = secrets.token_hex(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=lifetime_hours)

    session = UserSession(
        user_id=user_id,
        session_token=token,
        ip_address=ip_address[:45] if ip_address else None,
        user_agent=user_agent[:255] if user_agent else None,
        expires_at=expires_at,
        is_revoked=False
    )
    db.session.add(session)
    db.session.commit()
    return session


def get_user_session(session_token: str) -> UserSession | None:
    """Retrieve an active, non-expired session by token."""
    if not session_token:
        return None

    session = UserSession.query.filter_by(
        session_token=session_token,
        is_revoked=False
    ).first()

    if session and session.is_valid():
        return session
    return None


def revoke_user_session(session_token: str) -> bool:
    """Revoke a session token upon logout."""
    if not session_token:
        return False

    session = UserSession.query.filter_by(session_token=session_token).first()
    if session:
        session.is_revoked = True
        db.session.commit()
        return True
    return False


def revoke_all_user_sessions(user_id: str) -> int:
    """Revoke all active sessions for a user (e.g. password reset)."""
    count = UserSession.query.filter_by(user_id=user_id, is_revoked=False).update({"is_revoked": True})
    db.session.commit()
    return count

