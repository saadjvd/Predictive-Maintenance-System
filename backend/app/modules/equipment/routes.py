from flask import Blueprint, request, jsonify, g
from app.models.user import Role
from app.security import login_required, roles_required
from app.modules.equipment.repository import EquipmentRepository
from app.modules.equipment.services import EquipmentService, ValidationError

equipment_bp = Blueprint("equipment", __name__, url_prefix="/equipment")
areas_bp = Blueprint("production_areas", __name__, url_prefix="/production-areas")
lines_bp = Blueprint("production_lines", __name__, url_prefix="/production-lines")


# ==============================================================================
# EQUIPMENT ENDPOINTS
# ==============================================================================

@equipment_bp.route("", methods=["GET"])
@login_required
def list_equipment():
    """List machines with search, filtering, and pagination. Strictly tenant-scoped."""
    try:
        page = max(1, int(request.args.get("page", 1)))
        per_page = min(100, max(1, int(request.args.get("per_page", 20))))
    except ValueError:
        page, per_page = 1, 20

    items, total = EquipmentRepository.list_machines(
        org_id=g.current_org_id,
        site_id=request.args.get("site_id"),
        area_id=request.args.get("production_area_id"),
        line_id=request.args.get("production_line_id"),
        category_id=request.args.get("category_id"),
        criticality=request.args.get("criticality"),
        lifecycle_status=request.args.get("lifecycle_status"),
        connection_status=request.args.get("connection_status"),
        search=request.args.get("search"),
        page=page,
        per_page=per_page,
        sort_by=request.args.get("sort_by", "created_at"),
        sort_order=request.args.get("sort_order", "desc")
    )

    return jsonify({
        "equipment": [m.to_dict() for m in items],
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": (total + per_page - 1) // per_page
        }
    }), 200


@equipment_bp.route("/summary", methods=["GET"])
@login_required
def get_equipment_summary():
    """Returns actual real metrics from the database for the current organization."""
    summary = EquipmentRepository.get_summary(g.current_org_id)
    return jsonify(summary), 200


@equipment_bp.route("/<machine_id>", methods=["GET"])
@login_required
def get_equipment_detail(machine_id):
    """Retrieve single equipment record."""
    machine = EquipmentRepository.get_machine(machine_id, g.current_org_id)
    if not machine:
        return jsonify({"error": "Not Found", "message": "Equipment not found."}), 404

    return jsonify({"equipment": machine.to_dict()}), 200


@equipment_bp.route("", methods=["POST"])
@roles_required(
    Role.PLATFORM_ADMIN,
    Role.ORG_ADMIN,
    Role.MAINTENANCE_MANAGER
)
def create_equipment():
    """Register a new machine in the universal equipment registry."""
    data = request.get_json(silent=True) or {}
    try:
        machine = EquipmentService.create_equipment(
            org_id=g.current_org_id,
            user_id=g.current_user.id,
            data=data
        )
        return jsonify({
            "message": "Equipment registered successfully.",
            "equipment": machine.to_dict()
        }), 201
    except ValidationError as err:
        return jsonify({"error": "Validation Error", "message": err.message}), err.status_code


@equipment_bp.route("/<machine_id>", methods=["PATCH"])
@roles_required(
    Role.PLATFORM_ADMIN,
    Role.ORG_ADMIN,
    Role.MAINTENANCE_MANAGER,
    Role.MAINTENANCE_ENGINEER
)
def update_equipment(machine_id):
    """Update equipment metadata. Protected from unauthorized connection tampering."""
    data = request.get_json(silent=True) or {}
    try:
        machine = EquipmentService.update_equipment(
            machine_id=machine_id,
            org_id=g.current_org_id,
            user_id=g.current_user.id,
            data=data
        )
        return jsonify({
            "message": "Equipment updated successfully.",
            "equipment": machine.to_dict()
        }), 200
    except ValidationError as err:
        return jsonify({"error": "Validation Error", "message": err.message}), err.status_code


# ==============================================================================
# CATEGORY ENDPOINTS
# ==============================================================================

@equipment_bp.route("/categories", methods=["GET"])
@login_required
def list_categories():
    """List selectable equipment categories (system defaults + custom tenant categories)."""
    # Auto-seed standard categories if empty
    EquipmentService.ensure_default_categories()
    categories = EquipmentRepository.list_categories(g.current_org_id)
    return jsonify({
        "categories": [c.to_dict() for c in categories],
        "count": len(categories)
    }), 200


@equipment_bp.route("/categories", methods=["POST"])
@roles_required(Role.PLATFORM_ADMIN, Role.ORG_ADMIN, Role.MAINTENANCE_MANAGER)
def create_category():
    """Create a custom equipment category for the organization."""
    data = request.get_json(silent=True) or {}
    name = data.get("name")
    desc = data.get("description")
    try:
        cat = EquipmentService.create_category(g.current_org_id, name, desc)
        return jsonify({
            "message": "Custom equipment category created.",
            "category": cat.to_dict()
        }), 201
    except ValidationError as err:
        return jsonify({"error": "Validation Error", "message": err.message}), err.status_code


# ==============================================================================
# COMPONENT ENDPOINTS
# ==============================================================================

@equipment_bp.route("/<machine_id>/components", methods=["GET"])
@login_required
def list_components(machine_id):
    """List components and hierarchical subcomponents for a specific machine."""
    machine = EquipmentRepository.get_machine(machine_id, g.current_org_id)
    if not machine:
        return jsonify({"error": "Not Found", "message": "Equipment not found."}), 404

    components = EquipmentRepository.list_components(machine_id, g.current_org_id)
    return jsonify({
        "components": [c.to_dict() for c in components],
        "count": len(components)
    }), 200


@equipment_bp.route("/<machine_id>/components", methods=["POST"])
@roles_required(
    Role.PLATFORM_ADMIN,
    Role.ORG_ADMIN,
    Role.MAINTENANCE_MANAGER,
    Role.MAINTENANCE_ENGINEER
)
def add_component(machine_id):
    """Add a component to an equipment asset."""
    data = request.get_json(silent=True) or {}
    try:
        comp = EquipmentService.add_component(
            machine_id=machine_id,
            org_id=g.current_org_id,
            user_id=g.current_user.id,
            data=data
        )
        return jsonify({
            "message": "Component added successfully.",
            "component": comp.to_dict()
        }), 201
    except ValidationError as err:
        return jsonify({"error": "Validation Error", "message": err.message}), err.status_code


@equipment_bp.route("/components/<component_id>", methods=["PATCH"])
@roles_required(
    Role.PLATFORM_ADMIN,
    Role.ORG_ADMIN,
    Role.MAINTENANCE_MANAGER,
    Role.MAINTENANCE_ENGINEER
)
def update_component(component_id):
    """Update a component, enforcing cycle prevention in hierarchies."""
    data = request.get_json(silent=True) or {}
    try:
        comp = EquipmentService.update_component(
            component_id=component_id,
            org_id=g.current_org_id,
            user_id=g.current_user.id,
            data=data
        )
        return jsonify({
            "message": "Component updated successfully.",
            "component": comp.to_dict()
        }), 200
    except ValidationError as err:
        return jsonify({"error": "Validation Error", "message": err.message}), err.status_code


# ==============================================================================
# PRODUCTION AREAS & LINES ENDPOINTS
# ==============================================================================

@areas_bp.route("", methods=["GET"])
@login_required
def list_production_areas():
    """List production areas belonging to the user's organization."""
    site_id = request.args.get("site_id")
    areas = EquipmentRepository.list_production_areas(g.current_org_id, site_id)
    return jsonify({
        "production_areas": [a.to_dict() for a in areas],
        "count": len(areas)
    }), 200


@areas_bp.route("", methods=["POST"])
@roles_required(Role.PLATFORM_ADMIN, Role.ORG_ADMIN, Role.MAINTENANCE_MANAGER)
def create_production_area():
    """Create a new production area."""
    data = request.get_json(silent=True) or {}
    try:
        area = EquipmentService.create_production_area(
            org_id=g.current_org_id,
            site_id=data.get("site_id"),
            name=data.get("name"),
            description=data.get("description")
        )
        return jsonify({
            "message": "Production area created successfully.",
            "production_area": area.to_dict()
        }), 201
    except ValidationError as err:
        return jsonify({"error": "Validation Error", "message": err.message}), err.status_code


@lines_bp.route("", methods=["GET"])
@login_required
def list_production_lines():
    """List manufacturing lines for the user's organization."""
    lines = EquipmentRepository.list_production_lines(
        org_id=g.current_org_id,
        site_id=request.args.get("site_id"),
        area_id=request.args.get("production_area_id")
    )
    return jsonify({
        "production_lines": [l.to_dict() for l in lines],
        "count": len(lines)
    }), 200


@lines_bp.route("", methods=["POST"])
@roles_required(Role.PLATFORM_ADMIN, Role.ORG_ADMIN, Role.MAINTENANCE_MANAGER)
def create_production_line():
    """Create a new production line."""
    data = request.get_json(silent=True) or {}
    try:
        line = EquipmentService.create_production_line(
            org_id=g.current_org_id,
            site_id=data.get("site_id"),
            name=data.get("name"),
            line_code=data.get("line_code"),
            production_area_id=data.get("production_area_id"),
            description=data.get("description")
        )
        return jsonify({
            "message": "Production line created successfully.",
            "production_line": line.to_dict()
        }), 201
    except ValidationError as err:
        return jsonify({"error": "Validation Error", "message": err.message}), err.status_code

