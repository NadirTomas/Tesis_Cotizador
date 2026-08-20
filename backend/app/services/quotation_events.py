from sqlalchemy.orm import Session

from app.models.quotation_event import QuotationEvent


def log_event(db: Session, quotation_id: int, event_type: str, description: str, user_id: int | None) -> None:
    """
    Registra un evento de auditoría para una cotización. No commitea: se
    apoya en el commit que ya hace el endpoint que llama a esta función,
    para que el evento quede atado a la misma transacción que el cambio.
    """
    db.add(
        QuotationEvent(
            quotation_id=quotation_id,
            event_type=event_type,
            description=description,
            created_by_id=user_id,
        )
    )
