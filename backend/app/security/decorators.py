from functools import wraps
from flask import request, jsonify, g
from app.security.session import get_user_session
from app.models.user import Role


def get_token_from_request() -> str | None:
    """Extract session token from Authorization header or cookie."""
    # 1. Explicit Authorization header (takes precedence for programmatic / test clients)
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:].strip()

    # 2. Direct session token header
    custom_header = request.headers.get("X-Session-Token")
    if custom_header:
        return custom_header.strip()

    # 3. HttpOnly cookie (for standard browser navigation)
    token = request.cookies.get("pharma_session")
    if token:
        return token

    return None


def login_required(f):
    """Ensure the request is authenticated with an active session."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = get_token_from_request()
        if not token:
            return jsonify({
                "error": "Unauthorized",
                "message": "Authentication required. Please sign in."
            }), 401

        session = get_user_session(token)
        if not session or not session.user or not session.user.is_active:
            return jsonify({
                "error": "Unauthorized",
                "message": "Session has expired or is invalid. Please sign in again."
            }), 401

        # Check tenant status
        if session.user.organization and session.user.organization.status != "active":
            return jsonify({
                "error": "Forbidden",
                "message": "Organization account is suspended or inactive."
            }), 403

        g.current_user = session.user
        g.current_session = session
        g.current_org_id = session.user.organization_id
        return f(*args, **kwargs)

    return decorated_function


def roles_required(*allowed_roles):
    """Ensure the authenticated user has at least one of the specified roles."""
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            user = g.current_user
            org_id = g.current_org_id

            has_permission = False
            for role in allowed_roles:
                if user.has_role(role, org_id):
                    has_permission = True
                    break

            if not has_permission:
                return jsonify({
                    "error": "Forbidden",
                    "message": "Insufficient permissions. Required role: " + ", ".join(allowed_roles)
                }), 403

            return f(*args, **kwargs)
        return decorated_function
    return decorator

