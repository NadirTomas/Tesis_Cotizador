from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.client import Client
from app.schemas.client import ClientCreate, ClientRead, ClientUpdate
from app.services.auth_guard import get_current_user


router = APIRouter(prefix="/clients", tags=["clients"])


@router.post("/", response_model=ClientRead)
def create_client(
    payload: ClientCreate,
    db: Session = Depends(get_db),
    current_user: int = Depends(get_current_user),
):
    client = Client(**payload.dict())
    client.created_by_id = current_user
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


@router.get("/", response_model=list[ClientRead])
def list_clients(db: Session = Depends(get_db)):
    return db.query(Client).filter(Client.active.is_(True)).all()


@router.put("/{client_id}", response_model=ClientRead)
def update_client(
    client_id: int,
    payload: ClientUpdate,
    db: Session = Depends(get_db),
    current_user: int = Depends(get_current_user),
):
    client = db.query(Client).filter(Client.id == client_id).first()
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
    current_user: int = Depends(get_current_user),
):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    client.active = False
    db.commit()
    db.refresh(client)
    return client
