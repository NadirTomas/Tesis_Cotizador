from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.company_member import CompanyMember
from app.services.company_guard import get_current_company, require_owner
from app.models.machine_config import MachineConfig
from app.models.material import Material
from app.schemas.machine_config import (
    MachineConfigCreate,
    MachineConfigRead,
    MachineConfigUpdate,
)


router = APIRouter(prefix="/machine-configs", tags=["machine-configs"])


def _get_active_material(db: Session, material_id: int, company_id: int) -> Material | None:
    return (
        db.query(Material)
        .filter(
            Material.id == material_id,
            Material.company_id == company_id,
            Material.active.is_(True),
        )
        .first()
    )


@router.post("/", response_model=MachineConfigRead)
def create_machine_config(
    payload: MachineConfigCreate,
    db: Session = Depends(get_db),
    member: CompanyMember = Depends(require_owner),
):
    material = _get_active_material(db, payload.material_id, member.company_id)
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")
    config = MachineConfig(**payload.dict())
    config.company_id = member.company_id
    config.created_by_id = member.user_id
    db.add(config)
    db.commit()
    db.refresh(config)
    return config


@router.get("/", response_model=list[MachineConfigRead])
def list_machine_configs(
    db: Session = Depends(get_db),
    member: CompanyMember = Depends(get_current_company),
):
    return (
        db.query(MachineConfig)
        .filter(MachineConfig.company_id == member.company_id, MachineConfig.active.is_(True))
        .all()
    )


@router.get("/{config_id}", response_model=MachineConfigRead)
def get_machine_config(
    config_id: int,
    db: Session = Depends(get_db),
    member: CompanyMember = Depends(get_current_company),
):
    config = (
        db.query(MachineConfig)
        .filter(
            MachineConfig.id == config_id,
            MachineConfig.company_id == member.company_id,
            MachineConfig.active.is_(True),
        )
        .first()
    )
    if not config:
        raise HTTPException(status_code=404, detail="Machine config not found")
    return config


@router.put("/{config_id}", response_model=MachineConfigRead)
def update_machine_config(
    config_id: int,
    payload: MachineConfigUpdate,
    db: Session = Depends(get_db),
    member: CompanyMember = Depends(require_owner),
):
    config = (
        db.query(MachineConfig)
        .filter(MachineConfig.id == config_id, MachineConfig.company_id == member.company_id)
        .first()
    )
    if not config:
        raise HTTPException(status_code=404, detail="Machine config not found")
    update_data = payload.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(config, key, value)
    db.commit()
    db.refresh(config)
    return config


@router.delete("/{config_id}", response_model=MachineConfigRead)
def deactivate_machine_config(
    config_id: int,
    db: Session = Depends(get_db),
    member: CompanyMember = Depends(require_owner),
):
    config = (
        db.query(MachineConfig)
        .filter(MachineConfig.id == config_id, MachineConfig.company_id == member.company_id)
        .first()
    )
    if not config:
        raise HTTPException(status_code=404, detail="Machine config not found")
    config.active = False
    db.commit()
    db.refresh(config)
    return config
