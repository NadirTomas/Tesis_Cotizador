from sqlalchemy.orm import Session

from app.models.material import Material


def get_active_material(db: Session, material_id: int, company_id: int) -> Material | None:
    return (
        db.query(Material)
        .filter(
            Material.id == material_id,
            Material.company_id == company_id,
            Material.active.is_(True),
        )
        .first()
    )
