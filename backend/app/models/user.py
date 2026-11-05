import uuid
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db


def generate_uuid():
    return str(uuid.uuid4())


class Role(db.Model):
    __tablename__ = "roles"

    PLATFORM_ADMIN = "Platform Administrator"
    ORG_ADMIN = "Organization Administrator"
    MAINTENANCE_MANAGER = "Maintenance Manager"
    MAINTENANCE_ENGINEER = "Maintenance Engineer"
    VIEWER = "Viewer"

    ALL_ROLES = [
        PLATFORM_ADMIN,
        ORG_ADMIN,
        MAINTENANCE_MANAGER,
        MAINTENANCE_ENGINEER,
        VIEWER,
    ]

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    name = db.Column(db.String(50), unique=True, nullable=False, index=True)
    description = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
        }


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    organization_id = db.Column(
        db.String(36),
        db.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    full_name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    organization = db.relationship("Organization", back_populates="users")
    role_assignments = db.relationship("UserRoleAssignment", back_populates="user", cascade="all, delete-orphan")
    sessions = db.relationship("UserSession", back_populates="user", cascade="all, delete-orphan")

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def get_roles_for_org(self, org_id: str):
        return [
            assignment.role.name
            for assignment in self.role_assignments
            if assignment.organization_id == org_id
        ]

    def has_role(self, role_name: str, org_id: str) -> bool:
        roles = self.get_roles_for_org(org_id)
        # Platform Administrator has elevated authority across platform
        if Role.PLATFORM_ADMIN in roles:
            return True
        return role_name in roles

    def to_dict(self, current_org_id: str = None):
        target_org = current_org_id or self.organization_id
        roles = self.get_roles_for_org(target_org)
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "full_name": self.full_name,
            "email": self.email,
            "is_active": self.is_active,
            "roles": roles,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class UserRoleAssignment(db.Model):
    __tablename__ = "user_role_assignments"
    __table_args__ = (
        db.UniqueConstraint("user_id", "role_id", "organization_id", name="uq_user_role_org"),
    )

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role_id = db.Column(db.String(36), db.ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = db.Column(
        db.String(36),
        db.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    assigned_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    user = db.relationship("User", back_populates="role_assignments")
    role = db.relationship("Role")
    organization = db.relationship("Organization")


class UserSession(db.Model):
    __tablename__ = "user_sessions"

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    session_token = db.Column(db.String(128), unique=True, nullable=False, index=True)
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    is_revoked = db.Column(db.Boolean, default=False, nullable=False)

    user = db.relationship("User", back_populates="sessions")

    def is_valid(self) -> bool:
        if self.is_revoked:
            return False
        # Normalize timezone-aware comparison
        now = datetime.now(timezone.utc)
        expires = self.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return now < expires


class UserInvitation(db.Model):
    __tablename__ = "user_invitations"

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    organization_id = db.Column(
        db.String(36),
        db.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    role_id = db.Column(db.String(36), db.ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, index=True)
    email = db.Column(db.String(255), nullable=False, index=True)
    token = db.Column(db.String(128), unique=True, nullable=False, index=True)
    invited_by_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    is_accepted = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    organization = db.relationship("Organization", back_populates="invitations")
    role = db.relationship("Role")
    invited_by = db.relationship("User", foreign_keys=[invited_by_id])

    def is_valid(self) -> bool:
        if self.is_accepted:
            return False
        now = datetime.now(timezone.utc)
        expires = self.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return now < expires


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    organization_id = db.Column(db.String(36), nullable=True, index=True)
    user_id = db.Column(db.String(36), nullable=True, index=True)
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

