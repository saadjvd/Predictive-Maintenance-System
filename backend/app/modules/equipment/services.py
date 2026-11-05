from datetime import datetime, timezone
from app.extensions import db
from app.models.equipment import (
    Machine,
    MachineComponent,
    EquipmentCategory,
    ProductionArea,
    ProductionLine,
)
from app.models.tenant import Site
from app.modules.equipment.repository import EquipmentRepository
from app.security import log_audit_event


class ValidationError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class EquipmentService:
    @staticmethod
    def ensure_default_categories():
        """Ensure standard default equipment categories are seeded in the database."""
        for name, desc in EquipmentCategory.DEFAULT_CATEGORIES:
            existing = EquipmentCategory.query.filter_by(name=name, is_default=True).first()
            if not existing:
                cat = EquipmentCategory(
                    name=name,
                    description=desc,
                    is_default=True,
                    organization_id=None
                )
                db.session.add(cat)
        db.session.commit()

    @staticmethod
    def create_equipment(org_id: str, user_id: str, data: dict) -> Machine:
        # 1. Required field checks
        required = ["asset_code", "equipment_name", "category_id", "site_id"]
        for field in required:
            val = data.get(field)
            if not val or not str(val).strip():
                raise ValidationError(f"Missing required field: {field}", 400)

        asset_code = data["asset_code"].strip().upper()
        equipment_name = data["equipment_name"].strip()
        category_id = data["category_id"]
        site_id = data["site_id"]

        # 2. Check asset code uniqueness within organization
        existing = EquipmentRepository.get_machine_by_asset_code(asset_code, org_id)
        if existing:
            raise ValidationError(f"An equipment asset with code '{asset_code}' already exists in your organization.", 409)

        # 3. Validate Site belongs to active Organization
        site = Site.query.filter_by(id=site_id, organization_id=org_id).first()
        if not site:
            raise ValidationError("Specified factory / site does not exist or does not belong to your organization.", 403)

        # 4. Validate Production Area belongs to Site
        production_area_id = data.get("production_area_id")
        if production_area_id:
            area = ProductionArea.query.filter_by(id=production_area_id, site_id=site_id, organization_id=org_id).first()
            if not area:
                raise ValidationError("Specified production area does not exist or does not belong to the selected site.", 400)

        # 5. Validate Production Line belongs to Site (and Area if specified)
        production_line_id = data.get("production_line_id")
        if production_line_id:
            line = ProductionLine.query.filter_by(id=production_line_id, site_id=site_id, organization_id=org_id).first()
            if not line:
                raise ValidationError("Specified production line does not exist or does not belong to the selected site.", 400)
            if production_area_id and line.production_area_id and line.production_area_id != production_area_id:
                raise ValidationError("Specified production line does not belong to the selected production area.", 400)

        # 6. Validate Category exists and is available to Org
        category = EquipmentRepository.get_category(category_id, org_id)
        if not category:
            raise ValidationError("Specified equipment category does not exist.", 400)

        # 7. Validate Criticality
        criticality = data.get("criticality", "Medium")
        if criticality not in Machine.CRITICALITY_LEVELS:
            raise ValidationError(f"Invalid criticality. Must be one of: {', '.join(Machine.CRITICALITY_LEVELS)}", 400)

        # 8. Protection: Connection & Monitoring status cannot be spoofed at creation
        machine = Machine(
            organization_id=org_id,
            site_id=site_id,
            production_area_id=production_area_id,
            production_line_id=production_line_id,
            category_id=category_id,
            asset_code=asset_code,
            equipment_name=equipment_name,
            manufacturer=(data.get("manufacturer") or "").strip() or None,
            model=(data.get("model") or "").strip() or None,
            serial_number=(data.get("serial_number") or "").strip() or None,
            installation_date=data.get("installation_date"),
            criticality=criticality,
            lifecycle_status="Active",
            connection_status="Not Configured",  # Strictly protected default
            monitoring_status="Not Started",     # Strictly protected default
            description=(data.get("description") or "").strip() or None,
            created_by=user_id
        )

        db.session.add(machine)
        db.session.commit()

        log_audit_event(
            action="equipment_created",
            organization_id=org_id,
            user_id=user_id,
            details={"machine_id": machine.id, "asset_code": machine.asset_code, "name": machine.equipment_name}
        )

        return machine

    @staticmethod
    def update_equipment(machine_id: str, org_id: str, user_id: str, data: dict) -> Machine:
        machine = EquipmentRepository.get_machine(machine_id, org_id)
        if not machine:
            raise ValidationError("Equipment not found.", 404)

        # Check for asset code modification
        if "asset_code" in data:
            new_code = data["asset_code"].strip().upper()
            if new_code != machine.asset_code:
                existing = EquipmentRepository.get_machine_by_asset_code(new_code, org_id)
                if existing and existing.id != machine.id:
                    raise ValidationError(f"Asset code '{new_code}' is already assigned to another machine.", 409)
                machine.asset_code = new_code

        if "equipment_name" in data and data["equipment_name"]:
            machine.equipment_name = data["equipment_name"].strip()

        if "category_id" in data:
            cat = EquipmentRepository.get_category(data["category_id"], org_id)
            if not cat:
                raise ValidationError("Specified equipment category does not exist.", 400)
            machine.category_id = cat.id

        if "site_id" in data:
            new_site = Site.query.filter_by(id=data["site_id"], organization_id=org_id).first()
            if not new_site:
                raise ValidationError("Specified site does not belong to your organization.", 403)
            machine.site_id = new_site.id

        if "production_area_id" in data:
            area_id = data["production_area_id"]
            if area_id:
                area = ProductionArea.query.filter_by(id=area_id, site_id=machine.site_id, organization_id=org_id).first()
                if not area:
                    raise ValidationError("Production area does not belong to the assigned site.", 400)
            machine.production_area_id = area_id

        if "production_line_id" in data:
            line_id = data["production_line_id"]
            if line_id:
                line = ProductionLine.query.filter_by(id=line_id, site_id=machine.site_id, organization_id=org_id).first()
                if not line:
                    raise ValidationError("Production line does not belong to the assigned site.", 400)
            machine.production_line_id = line_id

        if "criticality" in data:
            crit = data["criticality"]
            if crit not in Machine.CRITICALITY_LEVELS:
                raise ValidationError(f"Invalid criticality. Must be one of: {', '.join(Machine.CRITICALITY_LEVELS)}", 400)
            machine.criticality = crit

        if "lifecycle_status" in data:
            life = data["lifecycle_status"]
            if life not in Machine.LIFECYCLE_STATUSES:
                raise ValidationError(f"Invalid lifecycle status. Must be one of: {', '.join(Machine.LIFECYCLE_STATUSES)}", 400)
            machine.lifecycle_status = life

        # PROTECTED: Ignore any unauthorized attempts to directly manipulate connection_status or monitoring_status
        # These are exclusively modified by edge gateway workflows in Phase 4 / 5.

        for field in ["manufacturer", "model", "serial_number", "installation_date", "description"]:
            if field in data:
                machine.__setattr__(field, data[field])

        db.session.commit()

        log_audit_event(
            action="equipment_updated",
            organization_id=org_id,
            user_id=user_id,
            details={"machine_id": machine.id, "asset_code": machine.asset_code}
        )

        return machine

    @staticmethod
    def add_component(machine_id: str, org_id: str, user_id: str, data: dict) -> MachineComponent:
        machine = EquipmentRepository.get_machine(machine_id, org_id)
        if not machine:
            raise ValidationError("Machine not found.", 404)

        name = data.get("component_name")
        if not name or not name.strip():
            raise ValidationError("Component name is required.", 400)

        parent_id = data.get("parent_component_id")
        if parent_id:
            parent = EquipmentRepository.get_component(parent_id, org_id)
            if not parent or parent.machine_id != machine_id:
                raise ValidationError("Parent component does not exist on this machine.", 400)

        component = MachineComponent(
            organization_id=org_id,
            machine_id=machine_id,
            parent_component_id=parent_id,
            component_name=name.strip(),
            component_code=data.get("component_code"),
            component_type=data.get("component_type"),
            manufacturer=data.get("manufacturer"),
            model=data.get("model"),
            serial_number=data.get("serial_number"),
            description=data.get("description")
        )

        db.session.add(component)
        db.session.commit()

        log_audit_event(
            action="component_added",
            organization_id=org_id,
            user_id=user_id,
            details={"component_id": component.id, "machine_id": machine_id}
        )

        return component

    @staticmethod
    def update_component(component_id: str, org_id: str, user_id: str, data: dict) -> MachineComponent:
        component = EquipmentRepository.get_component(component_id, org_id)
        if not component:
            raise ValidationError("Component not found.", 404)

        if "parent_component_id" in data:
            new_parent_id = data["parent_component_id"]
            if new_parent_id == component.id:
                raise ValidationError("A component cannot be its own parent (cyclic hierarchy prevented).", 400)

            if new_parent_id:
                # Cycle check: traverse descendants to ensure new parent is not inside component's subtree
                curr = EquipmentRepository.get_component(new_parent_id, org_id)
                visited = set()
                while curr:
                    if curr.id == component.id:
                        raise ValidationError("Cyclic component hierarchy detected. Cannot set a descendant as parent.", 400)
                    if curr.id in visited:
                        break
                    visited.add(curr.id)
                    curr = EquipmentRepository.get_component(curr.parent_component_id, org_id) if curr.parent_component_id else None

                component.parent_component_id = new_parent_id
            else:
                component.parent_component_id = None

        for field in ["component_name", "component_code", "component_type", "manufacturer", "model", "serial_number", "description"]:
            if field in data:
                component.__setattr__(field, data[field])

        db.session.commit()
        return component

    @staticmethod
    def create_category(org_id: str, name: str, description: str = None) -> EquipmentCategory:
        if not name or not name.strip():
            raise ValidationError("Category name is required.", 400)

        existing = EquipmentRepository.get_category_by_name(name, org_id)
        if existing:
            raise ValidationError(f"Category '{name.strip()}' already exists.", 409)

        return EquipmentRepository.create_category(name, description, org_id)

    @staticmethod
    def create_production_area(org_id: str, site_id: str, name: str, description: str = None) -> ProductionArea:
        if not name or not name.strip():
            raise ValidationError("Production area name is required.", 400)

        site = Site.query.filter_by(id=site_id, organization_id=org_id).first()
        if not site:
            raise ValidationError("Site does not exist or does not belong to your organization.", 403)

        existing = ProductionArea.query.filter_by(site_id=site_id, name=name.strip()).first()
        if existing:
            raise ValidationError(f"Production area '{name.strip()}' already exists for this site.", 409)

        area = ProductionArea(
            organization_id=org_id,
            site_id=site_id,
            name=name.strip(),
            description=description
        )
        db.session.add(area)
        db.session.commit()
        return area

    @staticmethod
    def create_production_line(
        org_id: str,
        site_id: str,
        name: str,
        line_code: str = None,
        production_area_id: str = None,
        description: str = None
    ) -> ProductionLine:
        if not name or not name.strip():
            raise ValidationError("Production line name is required.", 400)

        site = Site.query.filter_by(id=site_id, organization_id=org_id).first()
        if not site:
            raise ValidationError("Site does not exist or does not belong to your organization.", 403)

        if production_area_id:
            area = ProductionArea.query.filter_by(id=production_area_id, site_id=site_id, organization_id=org_id).first()
            if not area:
                raise ValidationError("Production area does not belong to the selected site.", 400)

        existing = ProductionLine.query.filter_by(site_id=site_id, name=name.strip()).first()
        if existing:
            raise ValidationError(f"Production line '{name.strip()}' already exists for this site.", 409)

        line = ProductionLine(
            organization_id=org_id,
            site_id=site_id,
            production_area_id=production_area_id,
            name=name.strip(),
            line_code=line_code.strip() if line_code else None,
            description=description
        )
        db.session.add(line)
        db.session.commit()
        return line

