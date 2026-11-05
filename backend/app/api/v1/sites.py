from flask import Blueprint, jsonify, g
from app.models.tenant import Site
from app.security import login_required

sites_bp = Blueprint("sites", __name__, url_prefix="/sites")


@sites_bp.route("", methods=["GET"])
@login_required
def get_sites():
    """
    List all manufacturing sites / facilities belonging to the user's active organization.
    Multi-tenant isolation enforced: strictly filters by organization_id == g.current_org_id.
    """
    sites = Site.query.filter_by(organization_id=g.current_org_id).order_by(Site.name).all()
    return jsonify({
        "sites": [site.to_dict() for site in sites],
        "count": len(sites)
    }), 200

