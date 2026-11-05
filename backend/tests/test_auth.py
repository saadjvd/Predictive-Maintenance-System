from datetime import datetime, timedelta, timezone
from app.extensions import db
from app.models.tenant import Organization, Site
from app.models.user import User, Role, UserRoleAssignment, UserSession
from app.security import clear_rate_limit


def setup_test_data(app):
    """Seed test organizations, roles, and users in testing database."""
    with app.app_context():
        # Clear rate limit caches
        clear_rate_limit("127.0.0.1:test.engineer@getzpharma.com")
        clear_rate_limit("127.0.0.1:test.admin@getzpharma.com")
        clear_rate_limit("127.0.0.1:ratelimit@example.com")

        # Roles
        roles = {}
        for r_name in Role.ALL_ROLES:
            role = Role(name=r_name, description=r_name)
            db.session.add(role)
            roles[r_name] = role
        db.session.commit()

        # Org A (Getz Pharma)
        org_a = Organization(name="Getz Pharma", slug="getz-pharma", status="active")
        # Org B (Benchmark Pharma)
        org_b = Organization(name="Benchmark Pharmaceuticals", slug="benchmark-pharma", status="active")
        db.session.add_all([org_a, org_b])
        db.session.commit()

        # Sites
        site_a1 = Site(organization_id=org_a.id, name="Unit-1 Korangi", code="GP-U1")
        site_a2 = Site(organization_id=org_a.id, name="Unit-2 BFS", code="GP-U2")
        site_b1 = Site(organization_id=org_b.id, name="Sundar Plant", code="BM-SDR")
        db.session.add_all([site_a1, site_a2, site_b1])
        db.session.commit()

        # User 1: Org Admin for Org A
        user_admin = User(
            organization_id=org_a.id,
            full_name="Getz Admin",
            email="test.admin@getzpharma.com",
            is_active=True
        )
        user_admin.set_password("AdminSecure@123")
        db.session.add(user_admin)
        db.session.commit()

        assign_admin = UserRoleAssignment(
            user_id=user_admin.id,
            role_id=roles[Role.ORG_ADMIN].id,
            organization_id=org_a.id
        )
        db.session.add(assign_admin)

        # User 2: Maintenance Engineer for Org A
        user_eng = User(
            organization_id=org_a.id,
            full_name="Getz Engineer",
            email="test.engineer@getzpharma.com",
            is_active=True
        )
        user_eng.set_password("EngineerSecure@123")
        db.session.add(user_eng)
        db.session.commit()

        assign_eng = UserRoleAssignment(
            user_id=user_eng.id,
            role_id=roles[Role.MAINTENANCE_ENGINEER].id,
            organization_id=org_a.id
        )
        db.session.add(assign_eng)

        # User 3: Inactive User in Org A
        user_inactive = User(
            organization_id=org_a.id,
            full_name="Deactivated Operator",
            email="inactive@getzpharma.com",
            is_active=False
        )
        user_inactive.set_password("Inactive@123")
        db.session.add(user_inactive)

        # User 4: Engineer in Org B (Competitor Tenant)
        user_org_b = User(
            organization_id=org_b.id,
            full_name="Benchmark Engineer",
            email="engineer@benchmark.com",
            is_active=True
        )
        user_org_b.set_password("Benchmark@123")
        db.session.add(user_org_b)
        db.session.commit()

        assign_b = UserRoleAssignment(
            user_id=user_org_b.id,
            role_id=roles[Role.MAINTENANCE_ENGINEER].id,
            organization_id=org_b.id
        )
        db.session.add(assign_b)
        db.session.commit()

        return {
            "org_a": org_a,
            "org_b": org_b,
            "user_admin": user_admin,
            "user_eng": user_eng,
            "user_inactive": user_inactive,
            "user_org_b": user_org_b,
            "site_a1": site_a1,
            "site_a2": site_a2,
            "site_b1": site_b1,
        }


# 1. Valid Login
def test_valid_login(app, client):
    setup_test_data(app)
    response = client.post("/api/v1/auth/login", json={
        "email": "test.engineer@getzpharma.com",
        "password": "EngineerSecure@123"
    })
    assert response.status_code == 200
    data = response.get_json()
    assert data["message"] == "Login successful."
    assert data["user"]["email"] == "test.engineer@getzpharma.com"
    assert "session_token" in data
    assert Role.MAINTENANCE_ENGINEER in data["roles"]

    # Verify HttpOnly cookie was set
    cookies = response.headers.getlist("Set-Cookie")
    assert any("pharma_session=" in c and "HttpOnly" in c for c in cookies)


# 2. Invalid Login (Wrong password & Generic error)
def test_invalid_login_wrong_password(app, client):
    setup_test_data(app)
    response = client.post("/api/v1/auth/login", json={
        "email": "test.engineer@getzpharma.com",
        "password": "WrongPassword999"
    })
    assert response.status_code == 401
    data = response.get_json()
    assert data["message"] == "Invalid email or password."


# 3. Inactive User Login Blocked
def test_inactive_user_cannot_login(app, client):
    setup_test_data(app)
    response = client.post("/api/v1/auth/login", json={
        "email": "inactive@getzpharma.com",
        "password": "Inactive@123"
    })
    assert response.status_code == 403
    data = response.get_json()
    assert "deactivated" in data["message"].lower()


# 4. Logout Revokes Session & Clears Cookie
def test_logout_revokes_session(app, client):
    setup_test_data(app)
    # Login first
    login_res = client.post("/api/v1/auth/login", json={
        "email": "test.engineer@getzpharma.com",
        "password": "EngineerSecure@123"
    })
    token = login_res.get_json()["session_token"]

    # Call logout
    logout_res = client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert logout_res.status_code == 200

    # Attempt to access /me with revoked token should fail
    me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 401


# 5. Expired Session Rejected
def test_expired_session_rejected(app, client):
    setup_test_data(app)
    with app.app_context():
        user = User.query.filter_by(email="test.engineer@getzpharma.com").first()
        # Create an already-expired session
        expired_session = UserSession(
            user_id=user.id,
            session_token="expired_token_123456",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
            is_revoked=False
        )
        db.session.add(expired_session)
        db.session.commit()

    response = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer expired_token_123456"})
    assert response.status_code == 401


# 6. Unauthenticated API Access Rejected
def test_unauthenticated_api_access_rejected(client):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert "Authentication required" in response.get_json()["message"]


# 7. Role Permission Enforcement (Engineer cannot invite users)
def test_role_permission_enforcement(app, client):
    setup_test_data(app)
    # Login as Maintenance Engineer (lacks ORG_ADMIN)
    login_res = client.post("/api/v1/auth/login", json={
        "email": "test.engineer@getzpharma.com",
        "password": "EngineerSecure@123"
    })
    token = login_res.get_json()["session_token"]

    invite_res = client.post(
        "/api/v1/users/invite",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": "new.user@getzpharma.com", "role_name": Role.VIEWER}
    )
    assert invite_res.status_code == 403
    assert "Insufficient permissions" in invite_res.get_json()["message"]


# 8. Cross-Organization Tenant Isolation (Sites belonging to Org A cannot be seen by Org B)
def test_cross_organization_data_isolation(app, client):
    data = setup_test_data(app)
    # Login as User from Org B (Benchmark)
    login_res = client.post("/api/v1/auth/login", json={
        "email": "engineer@benchmark.com",
        "password": "Benchmark@123"
    })
    token = login_res.get_json()["session_token"]

    sites_res = client.get("/api/v1/sites", headers={"Authorization": f"Bearer {token}"})
    assert sites_res.status_code == 200
    sites = sites_res.get_json()["sites"]

    # Must only contain Org B's site (Sundar Plant)
    site_names = [s["name"] for s in sites]
    assert "Sundar Plant" in site_names
    # MUST NOT leak Org A's sites!
    assert "Unit-1 Korangi" not in site_names
    assert "Unit-2 BFS" not in site_names


# 9. Authorized User Invitation (Admin can invite)
def test_authorized_user_invitation(app, client):
    setup_test_data(app)
    # Login as Org Admin
    login_res = client.post("/api/v1/auth/login", json={
        "email": "test.admin@getzpharma.com",
        "password": "AdminSecure@123"
    })
    token = login_res.get_json()["session_token"]

    invite_res = client.post(
        "/api/v1/users/invite",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": "new.tech@getzpharma.com", "role_name": Role.MAINTENANCE_ENGINEER}
    )
    assert invite_res.status_code == 201
    invite_data = invite_res.get_json()
    assert "invitation" in invite_data
    assert invite_data["invitation"]["email"] == "new.tech@getzpharma.com"
    assert invite_data["invitation"]["role"] == Role.MAINTENANCE_ENGINEER
    assert "token" in invite_data["invitation"]


# 10. Duplicate Email Handling in Organization
def test_duplicate_user_invite_rejected(app, client):
    setup_test_data(app)
    login_res = client.post("/api/v1/auth/login", json={
        "email": "test.admin@getzpharma.com",
        "password": "AdminSecure@123"
    })
    token = login_res.get_json()["session_token"]

    # Attempt to invite an existing user in the same organization
    invite_res = client.post(
        "/api/v1/users/invite",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": "test.engineer@getzpharma.com", "role_name": Role.MAINTENANCE_ENGINEER}
    )
    assert invite_res.status_code == 409
    assert "already belongs" in invite_res.get_json()["message"]


# 11. Current Organization Endpoint Tenant Isolation
def test_current_organization_endpoint(app, client):
    setup_test_data(app)
    login_res = client.post("/api/v1/auth/login", json={
        "email": "test.engineer@getzpharma.com",
        "password": "EngineerSecure@123"
    })
    token = login_res.get_json()["session_token"]

    org_res = client.get("/api/v1/organizations/current", headers={"Authorization": f"Bearer {token}"})
    assert org_res.status_code == 200
    org_data = org_res.get_json()
    assert org_data["organization"]["name"] == "Getz Pharma"
    assert len(org_data["sites"]) == 2


# 12. Login Rate Limiting (5 failed attempts trigger 429)
def test_login_rate_limiting(app, client):
    setup_test_data(app)
    email = "ratelimit@example.com"
    # Make 5 failed attempts
    for _ in range(5):
        res = client.post("/api/v1/auth/login", json={"email": email, "password": "wrong"})
        assert res.status_code == 401

    # 6th attempt should return 429 Too Many Requests
    blocked_res = client.post("/api/v1/auth/login", json={"email": email, "password": "wrong"})
    assert blocked_res.status_code == 429
    assert "Too many failed login attempts" in blocked_res.get_json()["message"]

