from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.company import Company
from app.models.company_member import CompanyMember, CompanyRole
from app.services.auth_guard import get_current_user


def get_current_company(
    x_company_id: int = Header(..., alias="X-Company-Id"),
    current_user: int = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CompanyMember:
    """
    Resuelve la empresa activa a partir del header X-Company-Id, validando
    que el usuario autenticado sea efectivamente miembro activo de esa
    empresa Y que la empresa en sí siga activa. El company_id que manda el
    frontend nunca se confía por sí solo.

    Hoy no existe ningún endpoint que ponga Company.is_active en False (no
    hay "dar de baja una empresa" implementado) — este chequeo es
    defensivo/preventivo, mismo criterio que ya se aplica a User.is_active
    y CompanyMember.is_active en este mismo módulo, para que el día que se
    agregue esa funcionalidad ya bloquee acceso sin tener que acordarse de
    tocar este guard.
    """
    member = (
        db.query(CompanyMember)
        .join(Company, Company.id == CompanyMember.company_id)
        .filter(
            CompanyMember.company_id == x_company_id,
            CompanyMember.user_id == current_user,
            CompanyMember.is_active.is_(True),
            Company.is_active.is_(True),
        )
        .first()
    )
    if not member:
        raise HTTPException(status_code=403, detail="No pertenecés a esta empresa")
    return member


def require_owner(member: CompanyMember = Depends(get_current_company)) -> CompanyMember:
    if member.role != CompanyRole.OWNER.value:
        raise HTTPException(status_code=403, detail="Esta acción requiere rol OWNER")
    return member
