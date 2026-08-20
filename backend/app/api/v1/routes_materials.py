from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.company_member import CompanyMember
from app.services.company_guard import get_current_company, require_owner
from app.models.material import Material
from app.schemas.material import MaterialCreate, MaterialRead, MaterialUpdate


router = APIRouter(prefix="/materials", tags=["materials"])


@router.post("/", response_model=MaterialRead)
def create_material(
    payload: MaterialCreate,
    db: Session = Depends(get_db),
    member: CompanyMember = Depends(require_owner),
):
    material = Material(**payload.dict())
    material.company_id = member.company_id
    material.created_by_id = member.user_id
    db.add(material)
    db.commit()
    db.refresh(material)
    return material


@router.get("/", response_model=list[MaterialRead])
def list_materials(
    db: Session = Depends(get_db),
    member: CompanyMember = Depends(get_current_company),
):
    return (
        db.query(Material)
        .filter(Material.company_id == member.company_id, Material.active.is_(True))
        .all()
    )


@router.get("/{material_id}", response_model=MaterialRead)
def get_material(
    material_id: int,
    db: Session = Depends(get_db),
    member: CompanyMember = Depends(get_current_company),
):
    material = (
        db.query(Material)
        .filter(
            Material.id == material_id,
            Material.company_id == member.company_id,
            Material.active.is_(True),
        )
        .first()
    )
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")
    return material


@router.put("/{material_id}", response_model=MaterialRead)
def update_material(
    material_id: int,
    payload: MaterialUpdate,
    db: Session = Depends(get_db),
    member: CompanyMember = Depends(require_owner),
):
    material = (
        db.query(Material)
        .filter(Material.id == material_id, Material.company_id == member.company_id)
        .first()
    )
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")
    update_data = payload.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(material, key, value)
    db.commit()
    db.refresh(material)
    return material


@router.delete("/{material_id}", response_model=MaterialRead)
def deactivate_material(
    material_id: int,
    db: Session = Depends(get_db),
    member: CompanyMember = Depends(require_owner),
):
    material = (
        db.query(Material)
        .filter(Material.id == material_id, Material.company_id == member.company_id)
        .first()
    )
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")
    material.active = False
    db.commit()
    db.refresh(material)
    return material
