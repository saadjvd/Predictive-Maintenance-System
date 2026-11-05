import uuid
from datetime import datetime, timezone
from app.extensions import db


def generate_uuid():
    return str(uuid.uuid4())


class Organization(db.Model):
    __tablename__ = "organizations"

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    name = db.Column(db.String(255), unique=True, nullable=False, index=True)
    slug = db.Column(db.String(255), unique=True, nullable=False, index=True)
    status = db.Column(db.String(50), nullable=False, default="active")  # active, suspended, pending
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    sites = db.relationship("Site", back_populates="organization", cascade="all, delete-orphan")
    users = db.relationship("User", back_populates="organization", cascade="all, delete-orphan")
    invitations = db.relationship("UserInvitation", back_populates="organization", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "status": self.status,
            "site_count": len(self.sites) if self.sites else 0,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Site(db.Model):
    __tablename__ = "sites"

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    organization_id = db.Column(
        db.String(36),
        db.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    name = db.Column(db.String(255), nullable=False)
    location = db.Column(db.String(255), nullable=True)
    code = db.Column(db.String(50), nullable=True)
    status = db.Column(db.String(50), nullable=False, default="active")
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    organization = db.relationship("Organization", back_populates="sites")

    def to_dict(self):
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "name": self.name,
            "location": self.location,
            "code": self.code,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

