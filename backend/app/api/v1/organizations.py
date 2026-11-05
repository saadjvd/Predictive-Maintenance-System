from flask import Blueprint, jsonify, g
from app.extensions import db
from app.models.tenant import Organization
from app.security import login_required

org_bp = Blueprint("organizations", __name__, url_prefix="/organizations")


@org_bp.route("/current", methods=["GET"])
@login_required
def get_current_organization():
    """
    Retrieve the current user's organization profile.
    Strictly isolated: returns ONLY the organization linked to g.current_org_id.
    """
    org = db.session.get(Organization, g.current_org_id)
    if not org:
        return jsonify({
            "error": "Not Found",
            "message": "Organization not found."
        }), 404

    return jsonify({
        "organization": org.to_dict(),
        "sites": [site.to_dict() for site in org.sites]
    }), 200
