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


def release_quotation_reservations(db: Session, quotation_id: int, released_by_id: int | None) -> bool:
    """
    Libera todas las reservas ACTIVE de una cotización como parte de su
    cancelación. Devuelve False (sin commitear nada) si la cancelación NO
    puede completarse de forma segura:

    - alguna reserva de la cotización ya está CONSUMED (se confirmó el
      corte antes de este intento de cancelación, sin necesidad de
      carrera — caso secuencial); o
    - una reserva ACTIVE fue procesada por otra operación concurrente
      entre el chequeo de arriba y el intento de liberarla (típicamente un
      confirm-cut que ganó la carrera bajo Postgres/READ COMMITTED: su
      UPDATE bloquea contra el de acá hasta que uno de los dos comitea, y
      si gana confirm-cut, el UPDATE condicional de acá afecta 0 filas).

    En ambos casos se aborta la cancelación COMPLETA, nunca solo una
    reserva — la invariante es que una cotización jamás debe quedar
    'cancelled' si alguna de sus reservas terminó (o ya estaba) CONSUMED.
    El caller es responsable de hacer rollback() si esta función devuelve
    False, y de commitear si devuelve True — no commitea acá.

    Si una reserva ACTIVE ya fue liberada por OTRA operación legítima en
    paralelo (ej. se borró el ítem de la cotización al mismo tiempo, que
    también libera su reserva — ver routes_quotation_items.py) el UPDATE
    condicional también afecta 0 filas, pero el resultado final (RELEASED)
    es el mismo que se buscaba: no es un conflicto real y no debe abortar
    la cancelación.
    """
    has_consumed = (
        db.query(StockReservation)
        .filter(StockReservation.quotation_id == quotation_id, StockReservation.status == "CONSUMED")
        .first()
        is not None
    )
    if has_consumed:
        return False

    active_reservations = (
        db.query(StockReservation)
        .filter(StockReservation.quotation_id == quotation_id, StockReservation.status == "ACTIVE")
        .all()
    )
    for reservation in active_reservations:
        if release_reservation(db, reservation, released_by_id):
            continue
        current_status = (
            db.query(StockReservation.status).filter(StockReservation.id == reservation.id).scalar()
        )
        if current_status == "RELEASED":
            continue
        return False
    return True
