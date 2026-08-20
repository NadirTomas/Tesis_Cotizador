from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.client import Client
from app.models.company_member import CompanyMember
from app.schemas.client import ClientCreate, ClientRead, ClientUpdate
from app.services.company_guard import get_current_company


router = APIRouter(prefix="/clients", tags=["clients"])


@router.post("/", response_model=ClientRead)
def create_client(
    payload: ClientCreate,
    db: Session = Depends(get_db),
    member: CompanyMember = Depends(get_current_company),
):
    client = Client(**payload.dict())
    client.company_id = member.company_id
    client.created_by_id = member.user_id
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


@router.get("/", response_model=list[ClientRead])
def list_clients(
    db: Session = Depends(get_db),
    member: CompanyMember = Depends(get_current_company),
):
    return (
        db.query(Client)
        .filter(Client.company_id == member.company_id, Client.active.is_(True))
        .all()
    )


@router.get("/{client_id}", response_model=ClientRead)
def get_client(
    client_id: int,
    db: Session = Depends(get_db),
    member: CompanyMember = Depends(get_current_company),
):
    client = (
        db.query(Client)
        .filter(
            Client.id == client_id,
            Client.company_id == member.company_id,
            Client.active.is_(True),
        )
        .first()
    )
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


@router.put("/{client_id}", response_model=ClientRead)
def update_client(
    client_id: int,
    payload: ClientUpdate,
    db: Session = Depends(get_db),
    member: CompanyMember = Depends(get_current_company),
):
    client = (
        db.query(Client)
        .filter(Client.id == client_id, Client.company_id == member.company_id)
        .first()
    )
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    update_data = payload.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(client, key, value)
    db.commit()
    db.refresh(client)
    return client


@router.delete("/{client_id}", response_model=ClientRead)
def deactivate_client(
    client_id: int,
    db: Session = Depends(get_db),
    member: CompanyMember = Depends(get_current_company),
):
    client = (
        db.query(Client)
        .filter(Client.id == client_id, Client.company_id == member.company_id)
        .first()
    )
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    client.active = False
    db.commit()
    db.refresh(client)
    return client
