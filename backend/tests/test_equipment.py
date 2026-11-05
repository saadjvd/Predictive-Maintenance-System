import pytest
from app.extensions import db
from app.models.tenant import Organization, Site
from app.models.user import User, Role, UserRoleAssignment
from app.models.equipment import EquipmentCategory, ProductionArea, ProductionLine, Machine, MachineComponent
from app.modules.equipment.services import EquipmentService


def setup_equipment_test_data(app):
    """Seed test environment with organizations, users with different roles, sites, and categories."""
    with app.app_context():
        # Ensure default categories
        EquipmentService.ensure_default_categories()

        # Roles
        roles = {}
        for r_name in Role.ALL_ROLES:
            role = Role.query.filter_by(name=r_name).first()
            if not role:
                role = Role(name=r_name, description=r_name)
                db.session.add(role)
            roles[r_name] = role
        db.session.commit()

        # Org A (Getz Pharma)
        org_a = Organization.query.filter_by(name="Getz Pharma").first()
        if not org_a:
            org_a = Organization(name="Getz Pharma", slug="getz-pharma", status="active")
            db.session.add(org_a)
            db.session.commit()

        # Org B (Benchmark Pharma)
        org_b = Organization.query.filter_by(name="Benchmark Pharmaceuticals").first()
        if not org_b:
            org_b = Organization(name="Benchmark Pharmaceuticals", slug="benchmark-pharma", status="active")
            db.session.add(org_b)
            db.session.commit()

        # Sites for Org A
        site_a1 = Site.query.filter_by(name="Unit-1 Korangi", organization_id=org_a.id).first()
        if not site_a1:
            site_a1 = Site(organization_id=org_a.id, name="Unit-1 Korangi", code="GP-U1")
            db.session.add(site_a1)
        site_a2 = Site.query.filter_by(name="Unit-2 Sterile BFS", organization_id=org_a.id).first()
        if not site_a2:
            site_a2 = Site(organization_id=org_a.id, name="Unit-2 Sterile BFS", code="GP-U2")
            db.session.add(site_a2)

        # Site for Org B
        site_b1 = Site.query.filter_by(name="Sundar Plant", organization_id=org_b.id).first()
        if not site_b1:
            site_b1 = Site(organization_id=org_b.id, name="Sundar Plant", code="BM-SDR")
            db.session.add(site_b1)
        db.session.commit()

        # Users for Org A
        # 1. Maintenance Manager
        mgr_a = User.query.filter_by(email="manager@getzpharma.com").first()
        if not mgr_a:
            mgr_a = User(organization_id=org_a.id, full_name="Getz Manager", email="manager@getzpharma.com")
            mgr_a.set_password("Manager@123")
            db.session.add(mgr_a)
            db.session.commit()
            db.session.add(UserRoleAssignment(user_id=mgr_a.id, role_id=roles[Role.MAINTENANCE_MANAGER].id, organization_id=org_a.id))

        # 2. Viewer
        viewer_a = User.query.filter_by(email="viewer@getzpharma.com").first()
        if not viewer_a:
            viewer_a = User(organization_id=org_a.id, full_name="Getz Viewer", email="viewer@getzpharma.com")
            viewer_a.set_password("Viewer@123")
            db.session.add(viewer_a)
            db.session.commit()
            db.session.add(UserRoleAssignment(user_id=viewer_a.id, role_id=roles[Role.VIEWER].id, organization_id=org_a.id))

        # User for Org B
        user_b = User.query.filter_by(email="manager@benchmark.com").first()
        if not user_b:
            user_b = User(organization_id=org_b.id, full_name="Benchmark Manager", email="manager@benchmark.com")
            user_b.set_password("BenchManager@123")
            db.session.add(user_b)
            db.session.commit()
            db.session.add(UserRoleAssignment(user_id=user_b.id, role_id=roles[Role.MAINTENANCE_MANAGER].id, organization_id=org_b.id))

        db.session.commit()

        # Fetch Category
        cat_blister = EquipmentCategory.query.filter_by(name="Blister Packaging").first()

        # Add Area and Line for Site A1
        area_osd = ProductionArea.query.filter_by(name="OSD Formulation Area", site_id=site_a1.id).first()
        if not area_osd:
            area_osd = ProductionArea(organization_id=org_a.id, site_id=site_a1.id, name="OSD Formulation Area")
            db.session.add(area_osd)
            db.session.commit()

        line_1 = ProductionLine.query.filter_by(name="Blister Packaging Line 01", site_id=site_a1.id).first()
        if not line_1:
            line_1 = ProductionLine(
                organization_id=org_a.id,
                site_id=site_a1.id,
                production_area_id=area_osd.id,
                name="Blister Packaging Line 01",
                line_code="BPL-01"
            )
            db.session.add(line_1)
            db.session.commit()

        cat_blister_id = cat_blister.id
        site_a1_id = site_a1.id
        site_a2_id = site_a2.id
        site_b1_id = site_b1.id
        area_osd_id = area_osd.id
        line_1_id = line_1.id
        org_a_id = org_a.id
        org_b_id = org_b.id

        return {
            "org_a_id": org_a_id,
            "org_b_id": org_b_id,
            "site_a1_id": site_a1_id,
            "site_a2_id": site_a2_id,
            "site_b1_id": site_b1_id,
            "cat_blister_id": cat_blister_id,
            "area_osd_id": area_osd_id,
            "line_1_id": line_1_id,
        }


def get_auth_token(client, email, password):
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return res.get_json()["session_token"]


# 1. Authorized Equipment Creation
def test_authorized_equipment_creation(app, client):
    data = setup_equipment_test_data(app)
    token = get_auth_token(client, "manager@getzpharma.com", "Manager@123")

    payload = {
        "asset_code": "BLIST-01",
        "equipment_name": "Romaco Noack 623 Blister Machine",
        "category_id": data["cat_blister_id"],
        "site_id": data["site_a1_id"],
        "production_area_id": data["area_osd_id"],
        "production_line_id": data["line_1_id"],
        "manufacturer": "Romaco",
        "model": "Noack 623",
        "serial_number": "RN623-2022-9981",
        "criticality": "Critical",
        "description": "Primary high-speed blister thermoforming line"
    }

    res = client.post("/api/v1/equipment", headers={"Authorization": f"Bearer {token}"}, json=payload)
    assert res.status_code == 201
    machine = res.get_json()["equipment"]
    assert machine["asset_code"] == "BLIST-01"
    assert machine["criticality"] == "Critical"
    assert machine["connection_status"] == "Not Configured"
    assert machine["monitoring_status"] == "Not Started"
    assert machine["lifecycle_status"] == "Active"


# 2. Unauthorized Equipment Creation (Viewer Role Denied)
def test_unauthorized_equipment_creation_denied(app, client):
    data = setup_equipment_test_data(app)
    token = get_auth_token(client, "viewer@getzpharma.com", "Viewer@123")

    payload = {
        "asset_code": "VIEWER-FAIL",
        "equipment_name": "Unauthorized Machine",
        "category_id": data["cat_blister_id"],
        "site_id": data["site_a1_id"]
    }

    res = client.post("/api/v1/equipment", headers={"Authorization": f"Bearer {token}"}, json=payload)
    assert res.status_code == 403
    assert "Insufficient permissions" in res.get_json()["message"]


# 3. Missing Required Fields (Fails with 400)
def test_missing_required_fields_rejected(app, client):
    setup_equipment_test_data(app)
    token = get_auth_token(client, "manager@getzpharma.com", "Manager@123")

    # Missing category_id and site_id
    res = client.post("/api/v1/equipment", headers={"Authorization": f"Bearer {token}"}, json={
        "asset_code": "INCOMPLETE-01",
        "equipment_name": "Incomplete Machine"
    })
    assert res.status_code == 400
    assert "Missing required field" in res.get_json()["message"]


# 4. Duplicate Asset Code within Organization (Fails with 409)
def test_duplicate_asset_code_rejected(app, client):
    data = setup_equipment_test_data(app)
    token = get_auth_token(client, "manager@getzpharma.com", "Manager@123")

    payload = {
        "asset_code": "DUP-CODE",
        "equipment_name": "First Unit",
        "category_id": data["cat_blister_id"],
        "site_id": data["site_a1_id"]
    }
    res1 = client.post("/api/v1/equipment", headers={"Authorization": f"Bearer {token}"}, json=payload)
    assert res1.status_code == 201

    # Second creation with identical asset_code in Org A
    res2 = client.post("/api/v1/equipment", headers={"Authorization": f"Bearer {token}"}, json=payload)
    assert res2.status_code == 409
    assert "already exists" in res2.get_json()["message"]


# 5. Custom Category Creation
def test_custom_category_creation(app, client):
    setup_equipment_test_data(app)
    token = get_auth_token(client, "manager@getzpharma.com", "Manager@123")

    res = client.post("/api/v1/equipment/categories", headers={"Authorization": f"Bearer {token}"}, json={
        "name": "Laser Inspection System",
        "description": "High-speed camera and laser tablet surface inspection"
    })
    assert res.status_code == 201
    cat = res.get_json()["category"]
    assert cat["name"] == "Laser Inspection System"
    assert cat["is_default"] is False


# 6. Equipment Filtering & 7. Equipment Pagination
def test_equipment_filtering_and_pagination(app, client):
    data = setup_equipment_test_data(app)
    token = get_auth_token(client, "manager@getzpharma.com", "Manager@123")

    # Create 3 machines with different criticalities
    for i in range(1, 4):
        crit = "Critical" if i == 1 else "Low"
        client.post("/api/v1/equipment", headers={"Authorization": f"Bearer {token}"}, json={
            "asset_code": f"PAG-{i}",
            "equipment_name": f"Packaging Unit {i}",
            "category_id": data["cat_blister_id"],
            "site_id": data["site_a1_id"],
            "criticality": crit
        })

    # Test filtering by criticality="Critical"
    crit_res = client.get("/api/v1/equipment?criticality=Critical", headers={"Authorization": f"Bearer {token}"})
    assert crit_res.status_code == 200
    crit_items = crit_res.get_json()["equipment"]
    assert all(m["criticality"] == "Critical" for m in crit_items)

    # Test pagination (per_page=2)
    page_res = client.get("/api/v1/equipment?per_page=2&page=1", headers={"Authorization": f"Bearer {token}"})
    assert page_res.status_code == 200
    pdata = page_res.get_json()
    assert len(pdata["equipment"]) <= 2
    assert pdata["pagination"]["page"] == 1
    assert pdata["pagination"]["per_page"] == 2


# 8. Editing Equipment Information
def test_editing_equipment_information(app, client):
    data = setup_equipment_test_data(app)
    token = get_auth_token(client, "manager@getzpharma.com", "Manager@123")

    create_res = client.post("/api/v1/equipment", headers={"Authorization": f"Bearer {token}"}, json={
        "asset_code": "EDIT-ME",
        "equipment_name": "Original Name",
        "category_id": data["cat_blister_id"],
        "site_id": data["site_a1_id"],
        "criticality": "Medium"
    })
    m_id = create_res.get_json()["equipment"]["id"]

    # Update name, manufacturer, and criticality
    patch_res = client.patch(f"/api/v1/equipment/{m_id}", headers={"Authorization": f"Bearer {token}"}, json={
        "equipment_name": "Renamed Packaging Machine",
        "manufacturer": "Fette Compacting",
        "criticality": "High"
    })
    assert patch_res.status_code == 200
    updated = patch_res.get_json()["equipment"]
    assert updated["equipment_name"] == "Renamed Packaging Machine"
    assert updated["manufacturer"] == "Fette Compacting"
    assert updated["criticality"] == "High"


# 9. Equipment-Component Relationships
def test_component_relationship(app, client):
    data = setup_equipment_test_data(app)
    token = get_auth_token(client, "manager@getzpharma.com", "Manager@123")

    create_res = client.post("/api/v1/equipment", headers={"Authorization": f"Bearer {token}"}, json={
        "asset_code": "COMP-MCH",
        "equipment_name": "Machine for Components",
        "category_id": data["cat_blister_id"],
        "site_id": data["site_a1_id"]
    })
    m_id = create_res.get_json()["equipment"]["id"]

    # Add parent component: Drive Assembly
    p_comp = client.post(f"/api/v1/equipment/{m_id}/components", headers={"Authorization": f"Bearer {token}"}, json={
        "component_name": "Main Drive Assembly",
        "component_type": "Drive"
    })
    assert p_comp.status_code == 201
    parent_id = p_comp.get_json()["component"]["id"]

    # Add child subcomponent: Motor
    c_comp = client.post(f"/api/v1/equipment/{m_id}/components", headers={"Authorization": f"Bearer {token}"}, json={
        "component_name": "Induction Motor 15kW",
        "component_type": "Motor",
        "parent_component_id": parent_id
    })
    assert c_comp.status_code == 201

    # List components
    list_res = client.get(f"/api/v1/equipment/{m_id}/components", headers={"Authorization": f"Bearer {token}"})
    assert list_res.status_code == 200
    comps = list_res.get_json()["components"]
    assert len(comps) == 1
    assert comps[0]["component_name"] == "Main Drive Assembly"
    assert len(comps[0]["subcomponents"]) == 1
    assert comps[0]["subcomponents"][0]["component_name"] == "Induction Motor 15kW"


# 10. Invalid Component Hierarchies (Cycle Prevention)
def test_cyclic_component_hierarchy_prevented(app, client):
    data = setup_equipment_test_data(app)
    token = get_auth_token(client, "manager@getzpharma.com", "Manager@123")

    create_res = client.post("/api/v1/equipment", headers={"Authorization": f"Bearer {token}"}, json={
        "asset_code": "CYCLE-MCH",
        "equipment_name": "Cycle Test Machine",
        "category_id": data["cat_blister_id"],
        "site_id": data["site_a1_id"]
    })
    m_id = create_res.get_json()["equipment"]["id"]

    # Comp 1
    c1 = client.post(f"/api/v1/equipment/{m_id}/components", headers={"Authorization": f"Bearer {token}"}, json={
        "component_name": "Comp 1"
    }).get_json()["component"]

    # Comp 2 with parent Comp 1
    c2 = client.post(f"/api/v1/equipment/{m_id}/components", headers={"Authorization": f"Bearer {token}"}, json={
        "component_name": "Comp 2",
        "parent_component_id": c1["id"]
    }).get_json()["component"]

    # Attempt to set Comp 1's parent to Comp 1 (self-parent)
    self_res = client.patch(f"/api/v1/equipment/components/{c1['id']}", headers={"Authorization": f"Bearer {token}"}, json={
        "parent_component_id": c1["id"]
    })
    assert self_res.status_code == 400

    # Attempt to set Comp 1's parent to Comp 2 (descendant cycle)
    cycle_res = client.patch(f"/api/v1/equipment/components/{c1['id']}", headers={"Authorization": f"Bearer {token}"}, json={
        "parent_component_id": c2["id"]
    })
    assert cycle_res.status_code == 400
    assert "Cyclic" in cycle_res.get_json()["message"]


# 11. Cross-Organization Access Denial
def test_cross_org_access_denial(app, client):
    data = setup_equipment_test_data(app)
    token_a = get_auth_token(client, "manager@getzpharma.com", "Manager@123")
    token_b = get_auth_token(client, "manager@benchmark.com", "BenchManager@123")

    # Manager A creates machine in Org A
    create_res = client.post("/api/v1/equipment", headers={"Authorization": f"Bearer {token_a}"}, json={
        "asset_code": "SECRET-ORGA",
        "equipment_name": "Getz Proprietary Line",
        "category_id": data["cat_blister_id"],
        "site_id": data["site_a1_id"]
    })
    assert create_res.status_code == 201, create_res.get_json()
    m_id = create_res.get_json()["equipment"]["id"]

    # Manager B attempts to GET machine in Org A -> must return 404
    get_res = client.get(f"/api/v1/equipment/{m_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert get_res.status_code == 404

    # Manager B attempts to PATCH machine in Org A -> must return 404
    patch_res = client.patch(f"/api/v1/equipment/{m_id}", headers={"Authorization": f"Bearer {token_b}"}, json={
        "equipment_name": "Hacked Machine"
    })
    assert patch_res.status_code == 404


# 12. Cross-Site Hierarchy Validation
def test_cross_site_hierarchy_rejected(app, client):
    data = setup_equipment_test_data(app)
    token = get_auth_token(client, "manager@getzpharma.com", "Manager@123")

    # Attempt to create equipment with Site A2 (BFS) but Area belonging to Site A1 (OSD)
    res = client.post("/api/v1/equipment", headers={"Authorization": f"Bearer {token}"}, json={
        "asset_code": "MISMATCH-01",
        "equipment_name": "Mismatched Site Machine",
        "category_id": data["cat_blister_id"],
        "site_id": data["site_a2_id"],
        "production_area_id": data["area_osd_id"]  # Belongs to site_a1!
    })
    assert res.status_code == 400
    assert "selected site" in res.get_json()["message"]


# 13. Viewer Read-Only Restrictions
def test_viewer_read_only_access(app, client):
    setup_equipment_test_data(app)
    token_viewer = get_auth_token(client, "viewer@getzpharma.com", "Viewer@123")

    # Viewer CAN read equipment list
    list_res = client.get("/api/v1/equipment", headers={"Authorization": f"Bearer {token_viewer}"})
    assert list_res.status_code == 200

    # Viewer CAN read summary
    sum_res = client.get("/api/v1/equipment/summary", headers={"Authorization": f"Bearer {token_viewer}"})
    assert sum_res.status_code == 200

    # Viewer CANNOT create categories
    cat_res = client.post("/api/v1/equipment/categories", headers={"Authorization": f"Bearer {token_viewer}"}, json={
        "name": "Viewer Custom Cat"
    })
    assert cat_res.status_code == 403


# 14. Connection-Status Protection
def test_connection_status_protection(app, client):
    data = setup_equipment_test_data(app)
    token = get_auth_token(client, "manager@getzpharma.com", "Manager@123")

    create_res = client.post("/api/v1/equipment", headers={"Authorization": f"Bearer {token}"}, json={
        "asset_code": "SPOOF-TEST",
        "equipment_name": "Spoof Machine",
        "category_id": data["cat_blister_id"],
        "site_id": data["site_a1_id"]
    })
    m_id = create_res.get_json()["equipment"]["id"]

    # Attempt to spoof connection_status="Connected" and monitoring_status="Active"
    client.patch(f"/api/v1/equipment/{m_id}", headers={"Authorization": f"Bearer {token}"}, json={
        "connection_status": "Connected",
        "monitoring_status": "Active"
    })

    # Retrieve machine and verify statuses remained protected
    chk_res = client.get(f"/api/v1/equipment/{m_id}", headers={"Authorization": f"Bearer {token}"})
    mach = chk_res.get_json()["equipment"]
    assert mach["connection_status"] == "Not Configured"
    assert mach["monitoring_status"] == "Not Started"


# 15. Equipment Decommissioning Rules
def test_equipment_decommissioning(app, client):
    data = setup_equipment_test_data(app)
    token = get_auth_token(client, "manager@getzpharma.com", "Manager@123")

    create_res = client.post("/api/v1/equipment", headers={"Authorization": f"Bearer {token}"}, json={
        "asset_code": "DECOM-01",
        "equipment_name": "Machine to Decommission",
        "category_id": data["cat_blister_id"],
        "site_id": data["site_a1_id"]
    })
    m_id = create_res.get_json()["equipment"]["id"]

    # Update lifecycle to Decommissioned
    patch_res = client.patch(f"/api/v1/equipment/{m_id}", headers={"Authorization": f"Bearer {token}"}, json={
        "lifecycle_status": "Decommissioned"
    })
    assert patch_res.status_code == 200
    assert patch_res.get_json()["equipment"]["lifecycle_status"] == "Decommissioned"
