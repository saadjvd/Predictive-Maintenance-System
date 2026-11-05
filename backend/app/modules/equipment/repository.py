from sqlalchemy import or_, and_, func
from app.extensions import db
from app.models.equipment import (
    Machine,
    MachineComponent,
    EquipmentCategory,
    ProductionArea,
    ProductionLine,
)
from app.models.tenant import Site


class EquipmentRepository:
    """Repository handling tenant-isolated queries for equipment and assets."""

    @staticmethod
    def get_machine(machine_id: str, org_id: str) -> Machine | None:
        return Machine.query.filter_by(id=machine_id, organization_id=org_id).first()

    @staticmethod
    def get_machine_by_asset_code(asset_code: str, org_id: str) -> Machine | None:
        return Machine.query.filter_by(asset_code=asset_code, organization_id=org_id).first()

    @staticmethod
    def list_machines(
        org_id: str,
        site_id: str = None,
        area_id: str = None,
        line_id: str = None,
        category_id: str = None,
        criticality: str = None,
        lifecycle_status: str = None,
        connection_status: str = None,
        search: str = None,
        page: int = 1,
        per_page: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "desc"
    ) -> tuple[list[Machine], int]:
        query = Machine.query.filter_by(organization_id=org_id)

        if site_id:
            query = query.filter_by(site_id=site_id)
        if area_id:
            query = query.filter_by(production_area_id=area_id)
        if line_id:
            query = query.filter_by(production_line_id=line_id)
        if category_id:
            query = query.filter_by(category_id=category_id)
        if criticality:
            query = query.filter_by(criticality=criticality)
        if lifecycle_status:
            query = query.filter_by(lifecycle_status=lifecycle_status)
        if connection_status:
            query = query.filter_by(connection_status=connection_status)

        if search:
            search_term = f"%{search.strip()}%"
            query = query.filter(
                or_(
                    Machine.equipment_name.ilike(search_term),
                    Machine.asset_code.ilike(search_term),
                    Machine.manufacturer.ilike(search_term),
                    Machine.model.ilike(search_term),
                    Machine.serial_number.ilike(search_term)
                )
            )

        total = query.count()

        # Sorting
        sort_col = getattr(Machine, sort_by, Machine.created_at)
        if sort_order.lower() == "asc":
            query = query.order_by(sort_col.asc())
        else:
            query = query.order_by(sort_col.desc())

        # Pagination
        items = query.offset((page - 1) * per_page).limit(per_page).all()
        return items, total

    @staticmethod
    def get_summary(org_id: str) -> dict:
        """Calculate real equipment metrics from actual database records."""
        base_query = Machine.query.filter_by(organization_id=org_id)

        total = base_query.count()
        active = base_query.filter_by(lifecycle_status="Active").count()
        high_criticality = base_query.filter(
            Machine.criticality.in_(["High", "Critical"])
        ).count()
        connected = base_query.filter_by(connection_status="Connected").count()
        under_maintenance = base_query.filter_by(lifecycle_status="Under Maintenance").count()

        return {
            "total_equipment": total,
            "active_equipment": active,
            "high_criticality_equipment": high_criticality,
            "connected_equipment": connected,
            "under_maintenance_equipment": under_maintenance,
        }

    # Categories
    @staticmethod
    def list_categories(org_id: str) -> list[EquipmentCategory]:
        # Return default/global categories + org custom categories
        return EquipmentCategory.query.filter(
            or_(
                EquipmentCategory.is_default == True,
                EquipmentCategory.organization_id == None,
                EquipmentCategory.organization_id == org_id
            )
        ).order_by(EquipmentCategory.name.asc()).all()

    @staticmethod
    def get_category(category_id: str, org_id: str) -> EquipmentCategory | None:
        return EquipmentCategory.query.filter(
            EquipmentCategory.id == category_id,
            or_(
                EquipmentCategory.is_default == True,
                EquipmentCategory.organization_id == None,
                EquipmentCategory.organization_id == org_id
            )
        ).first()

    @staticmethod
    def get_category_by_name(name: str, org_id: str) -> EquipmentCategory | None:
        return EquipmentCategory.query.filter(
            func.lower(EquipmentCategory.name) == name.strip().lower(),
            or_(
                EquipmentCategory.is_default == True,
                EquipmentCategory.organization_id == None,
                EquipmentCategory.organization_id == org_id
            )
        ).first()

    @staticmethod
    def create_category(name: str, description: str, org_id: str) -> EquipmentCategory:
        cat = EquipmentCategory(
            organization_id=org_id,
            name=name.strip(),
            description=description,
            is_default=False
        )
        db.session.add(cat)
        db.session.commit()
        return cat

    # Components
    @staticmethod
    def list_components(machine_id: str, org_id: str) -> list[MachineComponent]:
        return MachineComponent.query.filter_by(
            machine_id=machine_id,
            organization_id=org_id,
            parent_component_id=None
        ).order_by(MachineComponent.component_name.asc()).all()

    @staticmethod
    def get_component(component_id: str, org_id: str) -> MachineComponent | None:
        return MachineComponent.query.filter_by(id=component_id, organization_id=org_id).first()

    # Areas
    @staticmethod
    def list_production_areas(org_id: str, site_id: str = None) -> list[ProductionArea]:
        q = ProductionArea.query.filter_by(organization_id=org_id)
        if site_id:
            q = q.filter_by(site_id=site_id)
        return q.order_by(ProductionArea.name.asc()).all()

    @staticmethod
    def get_production_area(area_id: str, org_id: str) -> ProductionArea | None:
        return ProductionArea.query.filter_by(id=area_id, organization_id=org_id).first()

    # Lines
    @staticmethod
    def list_production_lines(org_id: str, site_id: str = None, area_id: str = None) -> list[ProductionLine]:
        q = ProductionLine.query.filter_by(organization_id=org_id)
        if site_id:
            q = q.filter_by(site_id=site_id)
        if area_id:
            q = q.filter_by(production_area_id=area_id)
        return q.order_by(ProductionLine.name.asc()).all()

    @staticmethod
    def get_production_line(line_id: str, org_id: str) -> ProductionLine | None:
        return ProductionLine.query.filter_by(id=line_id, organization_id=org_id).first()

