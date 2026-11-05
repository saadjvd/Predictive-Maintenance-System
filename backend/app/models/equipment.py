import uuid
from datetime import datetime, timezone
from app.extensions import db


def generate_uuid():
    return str(uuid.uuid4())


class ProductionArea(db.Model):
    __tablename__ = "production_areas"
    __table_args__ = (
        db.UniqueConstraint("site_id", "name", name="uq_site_production_area_name"),
    )

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    organization_id = db.Column(
        db.String(36),
        db.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    site_id = db.Column(
        db.String(36),
        db.ForeignKey("sites.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    organization = db.relationship("Organization")
    site = db.relationship("Site", backref=db.backref("production_areas", lazy=True, cascade="all, delete-orphan"))
    production_lines = db.relationship("ProductionLine", back_populates="production_area")
    machines = db.relationship("Machine", back_populates="production_area")

    def to_dict(self):
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "site_id": self.site_id,
            "site_name": self.site.name if self.site else None,
            "name": self.name,
            "description": self.description,
            "lines_count": len(self.production_lines) if self.production_lines else 0,
            "machines_count": len(self.machines) if self.machines else 0,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ProductionLine(db.Model):
    __tablename__ = "production_lines"
    __table_args__ = (
        db.UniqueConstraint("site_id", "name", name="uq_site_production_line_name"),
    )

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    organization_id = db.Column(
        db.String(36),
        db.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    site_id = db.Column(
        db.String(36),
        db.ForeignKey("sites.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    production_area_id = db.Column(
        db.String(36),
        db.ForeignKey("production_areas.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    name = db.Column(db.String(255), nullable=False)
    line_code = db.Column(db.String(50), nullable=True)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    organization = db.relationship("Organization")
    site = db.relationship("Site", backref=db.backref("production_lines", lazy=True, cascade="all, delete-orphan"))
    production_area = db.relationship("ProductionArea", back_populates="production_lines")
    machines = db.relationship("Machine", back_populates="production_line")

    def to_dict(self):
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "site_id": self.site_id,
            "site_name": self.site.name if self.site else None,
            "production_area_id": self.production_area_id,
            "production_area_name": self.production_area.name if self.production_area else None,
            "name": self.name,
            "line_code": self.line_code,
            "description": self.description,
            "machines_count": len(self.machines) if self.machines else 0,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class EquipmentCategory(db.Model):
    __tablename__ = "equipment_categories"

    DEFAULT_CATEGORIES = [
        ("Blister Packaging", "Packaging machinery for blister packs and thermoforming sealing"),
        ("Tablet Compression", "High-speed tablet rotary presses and compaction machines"),
        ("Capsule Filling", "Automatic and semi-automatic hard gelatin capsule fillers"),
        ("Liquid Filling", "Sterile and non-sterile liquid vial, ampoule, and bottle filling lines"),
        ("Tablet Coating", "Perforated coating pans for film and sugar coating"),
        ("Mixing & Granulation", "Rapid mixer granulators, fluid bed dryers, and blenders"),
        ("Autoclave / Sterilization", "Steam sterilizers, autoclaves, and depyrogenation tunnels"),
        ("Lyophilization", "Freeze dryers and vacuum sublimation units"),
        ("HVAC / Air Handling", "Critical pharmaceutical cleanroom AHUs, chillers, and dehumidifiers"),
        ("Compressors", "Oil-free pharmaceutical compressed air generators"),
        ("Pumps", "Sanitary WFI, purified water, and product transfer pumps"),
        ("Utility Systems", "Boilers, pure steam generators, and reverse osmosis plants"),
        ("Other / Custom Equipment", "Custom or specialized pharmaceutical manufacturing assets"),
    ]

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    organization_id = db.Column(
        db.String(36),
        db.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    is_default = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    machines = db.relationship("Machine", back_populates="category")

    def to_dict(self):
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "name": self.name,
            "description": self.description,
            "is_default": self.is_default,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Machine(db.Model):
    __tablename__ = "machines"
    __table_args__ = (
        db.UniqueConstraint("organization_id", "asset_code", name="uq_org_machine_asset_code"),
    )

    CRITICALITY_LEVELS = ["Low", "Medium", "High", "Critical"]
    LIFECYCLE_STATUSES = ["Active", "Inactive", "Under Maintenance", "Decommissioned"]
    CONNECTION_STATUSES = ["Not Configured", "Configured", "Connected", "Disconnected", "Error"]
    MONITORING_STATUSES = ["Not Started", "Pending Validation", "Active", "Suspended"]

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    organization_id = db.Column(
        db.String(36),
        db.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    site_id = db.Column(
        db.String(36),
        db.ForeignKey("sites.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )
    production_area_id = db.Column(
        db.String(36),
        db.ForeignKey("production_areas.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    production_line_id = db.Column(
        db.String(36),
        db.ForeignKey("production_lines.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    category_id = db.Column(
        db.String(36),
        db.ForeignKey("equipment_categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )
    asset_code = db.Column(db.String(100), nullable=False, index=True)
    equipment_name = db.Column(db.String(255), nullable=False)
    manufacturer = db.Column(db.String(255), nullable=True)
    model = db.Column(db.String(255), nullable=True)
    serial_number = db.Column(db.String(255), nullable=True)
    installation_date = db.Column(db.String(50), nullable=True)
    criticality = db.Column(db.String(50), default="Medium", nullable=False)
    lifecycle_status = db.Column(db.String(50), default="Active", nullable=False)
    connection_status = db.Column(db.String(50), default="Not Configured", nullable=False)
    monitoring_status = db.Column(db.String(50), default="Not Started", nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_by = db.Column(
        db.String(36),
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    organization = db.relationship("Organization")
    site = db.relationship("Site")
    production_area = db.relationship("ProductionArea", back_populates="machines")
    production_line = db.relationship("ProductionLine", back_populates="machines")
    category = db.relationship("EquipmentCategory", back_populates="machines")
    components = db.relationship("MachineComponent", back_populates="machine", cascade="all, delete-orphan")
    creator = db.relationship("User", foreign_keys=[created_by])

    def to_dict(self):
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "site_id": self.site_id,
            "site_name": self.site.name if self.site else None,
            "production_area_id": self.production_area_id,
            "production_area_name": self.production_area.name if self.production_area else None,
            "production_line_id": self.production_line_id,
            "production_line_name": self.production_line.name if self.production_line else None,
            "category_id": self.category_id,
            "category_name": self.category.name if self.category else None,
            "asset_code": self.asset_code,
            "equipment_name": self.equipment_name,
            "manufacturer": self.manufacturer,
            "model": self.model,
            "serial_number": self.serial_number,
            "installation_date": self.installation_date,
            "criticality": self.criticality,
            "lifecycle_status": self.lifecycle_status,
            "connection_status": self.connection_status,
            "monitoring_status": self.monitoring_status,
            "description": self.description,
            "created_by": self.created_by,
            "creator_name": self.creator.full_name if self.creator else None,
            "components_count": len(self.components) if self.components else 0,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class MachineComponent(db.Model):
    __tablename__ = "machine_components"

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    organization_id = db.Column(
        db.String(36),
        db.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    machine_id = db.Column(
        db.String(36),
        db.ForeignKey("machines.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    parent_component_id = db.Column(
        db.String(36),
        db.ForeignKey("machine_components.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )
    component_name = db.Column(db.String(255), nullable=False)
    component_code = db.Column(db.String(100), nullable=True)
    component_type = db.Column(db.String(100), nullable=True)  # Motor, Bearing, Gearbox, Heating Element, etc.
    manufacturer = db.Column(db.String(255), nullable=True)
    model = db.Column(db.String(255), nullable=True)
    serial_number = db.Column(db.String(255), nullable=True)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    machine = db.relationship("Machine", back_populates="components")
    parent = db.relationship("MachineComponent", remote_side=[id], backref=db.backref("subcomponents", lazy=True, cascade="all, delete-orphan"))

    def to_dict(self):
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "machine_id": self.machine_id,
            "parent_component_id": self.parent_component_id,
            "parent_component_name": self.parent.component_name if self.parent else None,
            "component_name": self.component_name,
            "component_code": self.component_code,
            "component_type": self.component_type,
            "manufacturer": self.manufacturer,
            "model": self.model,
            "serial_number": self.serial_number,
            "description": self.description,
            "subcomponents": [sub.to_dict() for sub in self.subcomponents] if self.subcomponents else [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

