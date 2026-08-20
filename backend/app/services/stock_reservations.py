from sqlalchemy.orm import Session

from app.models.stock_movement import StockMovement
from app.models.stock_reservation import StockReservation
from app.models.stock_sheet import StockSheet


def release_reservation(db: Session, reservation: StockReservation, released_by_id: int | None) -> bool:
    """
    Libera una reserva ACTIVE: la marca RELEASED y devuelve el stock a
    AVAILABLE, sin tocar su geometría. UPDATE condicional (mismo patrón que
    el resto de las transiciones de stock) — si la reserva ya no está ACTIVE
    (liberada o consumida por otra operación), no hace nada y devuelve False.
    No commitea: el caller decide cuándo cerrar la transacción.
    """
    updated_res = (
        db.query(StockReservation)
        .filter(StockReservation.id == reservation.id, StockReservation.status == "ACTIVE")
        .update({"status": "RELEASED"})
    )
    if updated_res == 0:
        return False

    db.query(StockSheet).filter(
        StockSheet.id == reservation.stock_sheet_id, StockSheet.status == "RESERVED"
    ).update({"status": "AVAILABLE"})

    db.add(
        StockMovement(
            company_id=reservation.company_id,
            stock_sheet_id=reservation.stock_sheet_id,
            movement_type="RELEASED",
            quotation_id=reservation.quotation_id,
            created_by_id=released_by_id,
            details={"reservation_id": reservation.id},
        )
    )
    return True
