from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.auth_guard import get_current_user
from app.models.material import Material
from app.schemas.material import MaterialCreate, MaterialRead, MaterialUpdate


router = APIRouter(prefix="/materials", tags=["materials"])


@router.post("/", response_model=MaterialRead)
def create_material(
    payload: MaterialCreate,
    db: Session = Depends(get_db),
    current_user: int = Depends(get_current_user),
):
    material = Material(**payload.dict())
    material.created_by_id = current_user
    db.add(material)
    db.commit()
    db.refresh(material)
    return material


@router.get("/", response_model=list[MaterialRead])
def list_materials(db: Session = Depends(get_db)):
    return db.query(Material).filter(Material.active.is_(True)).all()


@router.get("/{material_id}", response_model=MaterialRead)
def get_material(material_id: int, db: Session = Depends(get_db)):
    material = (
        db.query(Material)
        .filter(Material.id == material_id, Material.active.is_(True))
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
    current_user: int = Depends(get_current_user),
):
    material = db.query(Material).filter(Material.id == material_id).first()
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
    current_user: int = Depends(get_current_user),
):
    material = db.query(Material).filter(Material.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")
    material.active = False
    db.commit()
    db.refresh(material)
    return material
