from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.company_member import CompanyMember
from app.services.company_guard import get_current_company, require_owner
from app.models.machine_config import MachineConfig
from app.schemas.machine_config import (
    MachineConfigCreate,
    MachineConfigRead,
    MachineConfigUpdate,
)
from app.services.lookups import get_active_material


router = APIRouter(prefix="/machine-configs", tags=["machine-configs"])

_DUPLICATE_ACTIVE_CONFIG_DETAIL = "Ya existe una configuración de máquina activa para este material"


def _has_active_config(db: Session, material_id: int, company_id: int, exclude_id: int | None = None) -> bool:
    query = db.query(MachineConfig).filter(
        MachineConfig.material_id == material_id,
        MachineConfig.company_id == company_id,
        MachineConfig.active.is_(True),
    )
    if exclude_id is not None:
        query = query.filter(MachineConfig.id != exclude_id)
    return query.first() is not None


@router.post("/", response_model=MachineConfigRead)
def create_machine_config(
    payload: MachineConfigCreate,
    db: Session = Depends(get_db),
    member: CompanyMember = Depends(require_owner),
):
    material = get_active_material(db, payload.material_id, member.company_id)
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")
    if _has_active_config(db, payload.material_id, member.company_id):
        raise HTTPException(status_code=400, detail=_DUPLICATE_ACTIVE_CONFIG_DETAIL)
    config = MachineConfig(**payload.dict())
    config.company_id = member.company_id
    config.created_by_id = member.user_id
    db.add(config)
    try:
        db.commit()
    except IntegrityError:
        # El chequeo de arriba es lectura-luego-escritura, sin lock: una
        # segunda request casi simultánea pudo pasar la misma validación
        # antes de que esta comiteara. El índice único parcial
        # (uq_machine_configs_active_per_material) es la red de seguridad
        # real — sin este catch, la que pierde la carrera vería un 500
        # genérico en vez del mismo error de dominio que ya devuelve el
        # chequeo de arriba.
        db.rollback()
        raise HTTPException(status_code=400, detail=_DUPLICATE_ACTIVE_CONFIG_DETAIL)
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
    if update_data.get("active") is True and not config.active:
        if _has_active_config(db, config.material_id, member.company_id, exclude_id=config.id):
            raise HTTPException(status_code=400, detail=_DUPLICATE_ACTIVE_CONFIG_DETAIL)
    for key, value in update_data.items():
        setattr(config, key, value)
    try:
        db.commit()
    except IntegrityError:
        # Misma carrera que en create_machine_config: dos reactivaciones
        # del mismo material casi simultáneas pueden pasar ambas el
        # chequeo de arriba antes de que ninguna comitee.
        db.rollback()
        raise HTTPException(status_code=400, detail=_DUPLICATE_ACTIVE_CONFIG_DETAIL)
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
