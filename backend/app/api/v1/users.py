import secrets
from datetime import datetime, timedelta, timezone
from flask import Blueprint, request, jsonify, g
from app.extensions import db
from app.models.user import User, Role, UserRoleAssignment, UserInvitation
from app.security import roles_required, log_audit_event

users_bp = Blueprint("users", __name__, url_prefix="/users")


@users_bp.route("", methods=["GET"])
@roles_required(
    Role.PLATFORM_ADMIN,
    Role.ORG_ADMIN,
    Role.MAINTENANCE_MANAGER
)
def list_users():
    """
    List all team members belonging to the current organization.
    Multi-tenant isolation enforced: strictly filters by organization_id == g.current_org_id.
    """
    users = User.query.filter_by(organization_id=g.current_org_id).order_by(User.full_name).all()
    return jsonify({
        "users": [user.to_dict(g.current_org_id) for user in users],
        "count": len(users)
    }), 200


@users_bp.route("/invite", methods=["POST"])
@roles_required(Role.PLATFORM_ADMIN, Role.ORG_ADMIN)
def invite_user():
    """
    Invite a new user to the organization with a designated role.
    Generates a secure, time-limited, single-use invitation token.
    """
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    role_name = (data.get("role_name") or "").strip()

    if not email or not role_name:
        return jsonify({
            "error": "Bad Request",
            "message": "Both email and role_name are required."
        }), 400

    if role_name not in Role.ALL_ROLES:
        return jsonify({
            "error": "Bad Request",
            "message": f"Invalid role specified. Must be one of: {', '.join(Role.ALL_ROLES)}"
        }), 400

    # Ensure role exists in database
    role = Role.query.filter_by(name=role_name).first()
    if not role:
        return jsonify({
            "error": "Not Found",
            "message": "Requested role does not exist."
        }), 404

    # Check if a user with this email already exists in this organization
    existing_user = User.query.filter_by(email=email).first()
    if existing_user and existing_user.organization_id == g.current_org_id:
        return jsonify({
            "error": "Conflict",
            "message": "A user with this email address already belongs to this organization."
        }), 409

    # Generate single-use invitation token (72-hour validity)
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=72)

    invitation = UserInvitation(
        organization_id=g.current_org_id,
        role_id=role.id,
        email=email,
        token=token,
        invited_by_id=g.current_user.id,
        expires_at=expires_at,
        is_accepted=False
    )
    db.session.add(invitation)
    db.session.commit()

    log_audit_event(
        action="user_invitation_created",
        organization_id=g.current_org_id,
        user_id=g.current_user.id,
        details={"invited_email": email, "role": role_name}
    )

    # In development mode, return the invitation token and simulated redemption URL directly
    dev_invite_url = f"/accept-invitation?token={token}"

    return jsonify({
        "message": f"Invitation created successfully for {email}.",
        "invitation": {
            "id": invitation.id,
            "email": invitation.email,
            "role": role.name,
            "expires_at": invitation.expires_at.isoformat(),
            "token": token,
            "invitation_url": dev_invite_url,
            "note": "Email delivery is not yet configured. Use invitation_url to accept."
        }
    }), 201

