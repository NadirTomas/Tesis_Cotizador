"""Lógica de negocio de remitos (entregas parciales/completas).

Desacoplada de HTTP: los errores se informan con DeliveryNoteError y el router
los traduce a códigos de estado. Las funciones NO hacen commit — el router
confirma o revierte la transacción completa.

Reglas centrales
- Solo los remitos ISSUED cuentan como entrega efectiva (un borrador no).
- Solo se emiten remitos de cotizaciones en estado "accepted".
- Para EMITIR (no para guardar borradores) el corte de cada ítem del remito debe estar
  confirmado: existe una StockReservation CONSUMED de esa cotización vinculada al ítem
  (mismo criterio que usa la pantalla de cotización). CONSUMED es un estado terminal:
  una vez confirmado no se revierte, así que un remito emitido nunca queda sin corte.
- Entregado + a entregar nunca puede superar lo cotizado, por ítem.
- Emitir y anular toman un lock de fila sobre la cotización: dos operaciones
  simultáneas sobre la misma cotización se serializan, y la segunda revalida
  las cantidades contra lo ya comiteado (evita la sobreentrega por carrera).
- Un remito emitido es de solo lectura; solo puede anularse (nunca se borra).
"""

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.clock import business_now
from app.models.client import Client
from app.models.delivery_note import DRAFT, ISSUED, VOIDED, DeliveryNote, DeliveryNoteItem
from app.models.piece import Piece
from app.models.quotation import Quotation
from app.models.quotation_item import QuotationItem
from app.models.stock_reservation import StockReservation
from app.services.document_numbering import (
    DELIVERY_NOTE_DOC_TYPE,
    format_delivery_note_number,
    next_sequence_number,
)
from app.services.quotation_events import log_event

ELIGIBLE_QUOTATION_STATUS = "accepted"
DEFAULT_UNIT = "un"

CUT_NOT_CONFIRMED_DETAIL = "No se puede emitir el remito porque el corte de la cotización todavía no fue confirmado"

NOT_FOUND = "not_found"
INVALID = "invalid"
CONFLICT = "conflict"


class DeliveryNoteError(Exception):
    def __init__(self, kind: str, detail: str):
        super().__init__(detail)
        self.kind = kind
        self.detail = detail


# ── helpers de acceso ────────────────────────────────────────────────────────


def _naive_business_now():
    return business_now().replace(tzinfo=None)


def _get_quotation(db: Session, company_id: int, quotation_id: int, *, lock: bool = False) -> Quotation:
    query = db.query(Quotation).filter(Quotation.id == quotation_id, Quotation.company_id == company_id)
    if lock:
        # FOR NO KEY UPDATE (no FOR UPDATE): serializa emitir/anular/cancelar sobre la misma cotización,
        # pero NO bloquea los FOR KEY SHARE que Postgres toma al insertar filas con FK hacia la cotización
        # (p. ej. confirm-cut inserta stock_movements con quotation_id). Con FOR UPDATE, cancelar vs.
        # confirm-cut terminaba en deadlock (detectado contra Postgres real).
        query = query.with_for_update(key_share=True).populate_existing()
    quotation = query.first()
    if not quotation:
        raise DeliveryNoteError(NOT_FOUND, "Cotización no encontrada")
    return quotation


def _get_note(db: Session, company_id: int, note_id: int, *, lock: bool = False) -> DeliveryNote:
    query = db.query(DeliveryNote).filter(DeliveryNote.id == note_id, DeliveryNote.company_id == company_id)
    if lock:
        query = query.with_for_update().populate_existing()
    note = query.first()
    if not note:
        raise DeliveryNoteError(NOT_FOUND, "Remito no encontrado")
    return note


def get_note(db: Session, company_id: int, note_id: int) -> DeliveryNote:
    return _get_note(db, company_id, note_id)


# ── cantidades entregadas / pendientes ───────────────────────────────────────


def _cut_confirmed_item_ids(db: Session, company_id: int, quotation_id: int) -> set[int]:
    """Ítems de la cotización con el corte confirmado: tienen una reserva de stock CONSUMED.

    Es el mismo mecanismo que ya usa QuotationDetailPage (reserva -> confirm-cut). La reserva es
    por ítem, no por unidad: el modelo no permite saber cuántas unidades del ítem se cortaron."""
    rows = (
        db.query(StockReservation.quotation_item_id)
        .filter(
            StockReservation.company_id == company_id,
            StockReservation.quotation_id == quotation_id,
            StockReservation.status == "CONSUMED",
            StockReservation.quotation_item_id.isnot(None),
        )
        .distinct()
        .all()
    )
    return {item_id for (item_id,) in rows}


def get_note_cut_status(db: Session, note: DeliveryNote) -> tuple[bool, list[str]]:
    """(corte confirmado para todas las líneas del remito, nombres de las piezas que faltan)."""
    confirmed = _cut_confirmed_item_ids(db, note.company_id, note.quotation_id)
    missing = [line.piece_name for line in note.items if line.quotation_item_id not in confirmed]
    return (len(missing) == 0, missing)


def _delivered_by_item(db: Session, quotation_id: int) -> dict[int, int]:
    """Cantidad efectivamente entregada por ítem: solo remitos ISSUED."""
    rows = (
        db.query(DeliveryNoteItem.quotation_item_id, func.coalesce(func.sum(DeliveryNoteItem.quantity), 0))
        .join(DeliveryNote, DeliveryNote.id == DeliveryNoteItem.delivery_note_id)
        .filter(DeliveryNote.quotation_id == quotation_id, DeliveryNote.status == ISSUED)
        .group_by(DeliveryNoteItem.quotation_item_id)
        .all()
    )
    return {item_id: int(total) for item_id, total in rows}


def get_delivery_status(db: Session, company_id: int, quotation_id: int) -> dict:
    quotation = _get_quotation(db, company_id, quotation_id)
    delivered = _delivered_by_item(db, quotation.id)
    cut_confirmed_ids = _cut_confirmed_item_ids(db, company_id, quotation.id)
    lines = []
    for item in sorted(quotation.items, key=lambda i: i.id):
        piece = item.piece
        done = delivered.get(item.id, 0)
        lines.append(
            {
                "quotation_item_id": item.id,
                "piece_id": item.piece_id,
                "piece_name": piece.name if piece else f"Pieza #{item.piece_id}",
                "piece_description": piece.description if piece else None,
                "unit": DEFAULT_UNIT,
                "quoted": item.quantity,
                "delivered": done,
                "pending": max(item.quantity - done, 0),
                "cut_confirmed": item.id in cut_confirmed_ids,
            }
        )
    total_quoted = sum(line["quoted"] for line in lines)
    total_delivered = sum(line["delivered"] for line in lines)
    total_pending = sum(line["pending"] for line in lines)
    if total_delivered == 0:
        state = "NONE"
    elif total_pending == 0:
        state = "COMPLETE"
    else:
        state = "PARTIAL"
    eligible = quotation.status == ELIGIBLE_QUOTATION_STATUS
    return {
        "quotation_id": quotation.id,
        "quotation_number": quotation.number,
        "quotation_status": quotation.status,
        "client_name": quotation.client.name,
        "cut_confirmed": bool(lines) and all(line["cut_confirmed"] for line in lines),
        "eligible": eligible,
        "ineligible_reason": None if eligible else "Solo se pueden generar remitos de cotizaciones aceptadas.",
        "state": state,
        "total_quoted": total_quoted,
        "total_delivered": total_delivered,
        "total_pending": total_pending,
        "items": lines,
    }


def has_issued_delivery_notes(db: Session, quotation_id: int) -> bool:
    return (
        db.query(DeliveryNote.id)
        .filter(DeliveryNote.quotation_id == quotation_id, DeliveryNote.status == ISSUED)
        .first()
        is not None
    )


def quotation_item_is_referenced(db: Session, quotation_item_id: int) -> bool:
    return db.query(DeliveryNoteItem.id).filter(DeliveryNoteItem.quotation_item_id == quotation_item_id).first() is not None


# ── validación de líneas ─────────────────────────────────────────────────────


def _validate_lines(
    db: Session, quotation: Quotation, lines: list[tuple[int, int]], *, excess_kind: str, require_cut: bool = False
) -> list[tuple[QuotationItem, int]]:
    """Valida (quotation_item_id, cantidad) contra la cotización.

    Se llama con la cotización ya bloqueada cuando se emite, para que el
    "pendiente" refleje el estado comiteado más reciente."""
    if quotation.status != ELIGIBLE_QUOTATION_STATUS:
        raise DeliveryNoteError(CONFLICT, "Solo se pueden generar remitos de cotizaciones aceptadas.")
    if not lines:
        raise DeliveryNoteError(INVALID, "El remito debe tener al menos una línea.")

    items_by_id = {item.id: item for item in quotation.items}
    if require_cut:
        # Se evalúa ya con la cotización bloqueada (ver issue): CONSUMED no se revierte, así que
        # lo que se lee acá no puede dejar de ser cierto después de emitir.
        confirmed = _cut_confirmed_item_ids(db, quotation.company_id, quotation.id)
        missing = []
        for item_id, _quantity in lines:
            item = items_by_id.get(item_id)
            if item is not None and item.id not in confirmed:
                missing.append(item.piece.name if item.piece else f"pieza #{item.piece_id}")
        if missing:
            raise DeliveryNoteError(CONFLICT, f"{CUT_NOT_CONFIRMED_DETAIL} (falta confirmar: {', '.join(missing)}).")
    delivered = _delivered_by_item(db, quotation.id)
    seen: set[int] = set()
    resolved: list[tuple[QuotationItem, int]] = []
    for item_id, quantity in lines:
        if item_id in seen:
            raise DeliveryNoteError(INVALID, "Un ítem de la cotización no puede repetirse en el mismo remito.")
        seen.add(item_id)
        item = items_by_id.get(item_id)
        if item is None:
            raise DeliveryNoteError(INVALID, f"El ítem {item_id} no pertenece a esta cotización.")
        if not isinstance(quantity, int) or quantity <= 0:
            raise DeliveryNoteError(INVALID, "La cantidad de cada línea debe ser un entero mayor a 0.")
        pending = item.quantity - delivered.get(item.id, 0)
        if quantity > pending:
            piece = item.piece.name if item.piece else f"pieza #{item.piece_id}"
            raise DeliveryNoteError(
                excess_kind,
                f"No se puede entregar {quantity} de '{piece}': solo quedan {max(pending, 0)} pendientes.",
            )
        resolved.append((item, quantity))
    return resolved


def _apply_snapshots(note: DeliveryNote, quotation: Quotation, client: Client) -> None:
    note.quotation_number = quotation.number
    note.client_id = client.id
    note.client_name = client.name
    note.client_tax_id = client.cuit_cuil
    note.client_address = client.address


def _line_fields(item: QuotationItem, quantity: int) -> dict:
    piece: Piece | None = item.piece
    return {
        "piece_id": item.piece_id,
        "piece_name": piece.name if piece else f"Pieza #{item.piece_id}",
        "piece_description": piece.description if piece else None,
        "quantity": quantity,
        "unit": DEFAULT_UNIT,
    }


# ── casos de uso ─────────────────────────────────────────────────────────────


def create_draft(
    db: Session,
    *,
    company_id: int,
    user_id: int,
    quotation_id: int,
    notes: str | None,
    lines: list[tuple[int, int]],
) -> DeliveryNote:
    quotation = _get_quotation(db, company_id, quotation_id)
    resolved = _validate_lines(db, quotation, lines, excess_kind=INVALID)
    client = quotation.client
    note = DeliveryNote(
        company_id=company_id,
        quotation_id=quotation.id,
        client_id=client.id,
        status=DRAFT,
        notes=notes,
        created_by_id=user_id,
        quotation_number=quotation.number,
        client_name=client.name,
    )
    _apply_snapshots(note, quotation, client)
    for item, quantity in resolved:
        note.items.append(DeliveryNoteItem(quotation_item_id=item.id, **_line_fields(item, quantity)))
    db.add(note)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise DeliveryNoteError(CONFLICT, "No se pudo crear el remito: un ítem fue modificado en simultáneo.") from exc
    return note


def update_draft(
    db: Session,
    *,
    company_id: int,
    note_id: int,
    notes: str | None,
    notes_provided: bool,
    lines: list[tuple[int, int]] | None,
) -> DeliveryNote:
    note = _get_note(db, company_id, note_id, lock=True)
    if note.status != DRAFT:
        raise DeliveryNoteError(CONFLICT, "Un remito emitido o anulado es de solo lectura y no se puede modificar.")
    if notes_provided:
        note.notes = notes
    if lines is not None:
        quotation = _get_quotation(db, company_id, note.quotation_id)
        resolved = {item.id: (item, qty) for item, qty in _validate_lines(db, quotation, lines, excess_kind=INVALID)}
        existing = {line.quotation_item_id: line for line in note.items}
        for item_id, line in list(existing.items()):
            if item_id not in resolved:
                note.items.remove(line)
        for item_id, (item, quantity) in resolved.items():
            fields = _line_fields(item, quantity)
            if item_id in existing:
                for key, value in fields.items():
                    setattr(existing[item_id], key, value)
            else:
                note.items.append(DeliveryNoteItem(quotation_item_id=item_id, **fields))
    try:
        db.flush()
    except IntegrityError as exc:
        # Igual que create_draft: un ítem eliminado o cambiado en simultáneo no debe terminar en 500.
        db.rollback()
        raise DeliveryNoteError(CONFLICT, "No se pudo guardar el borrador: un ítem fue modificado en simultáneo.") from exc
    return note


def delete_draft(db: Session, *, company_id: int, note_id: int) -> None:
    note = _get_note(db, company_id, note_id, lock=True)
    if note.status != DRAFT:
        raise DeliveryNoteError(CONFLICT, "Solo se pueden eliminar remitos en borrador. Un remito emitido se anula, no se borra.")
    db.delete(note)
    db.flush()


def issue(db: Session, *, company_id: int, user_id: int, note_id: int) -> DeliveryNote:
    # Orden de locks fijo (cotización -> remito) para no generar deadlocks
    # entre emisiones/anulaciones concurrentes de la misma cotización.
    probe = _get_note(db, company_id, note_id)
    quotation = _get_quotation(db, company_id, probe.quotation_id, lock=True)
    note = _get_note(db, company_id, note_id, lock=True)
    if note.status != DRAFT:
        raise DeliveryNoteError(CONFLICT, "Este remito ya fue emitido o anulado; no se puede emitir de nuevo.")

    lines = [(line.quotation_item_id, line.quantity) for line in note.items]
    resolved = _validate_lines(db, quotation, lines, excess_kind=CONFLICT, require_cut=True)

    client = quotation.client
    _apply_snapshots(note, quotation, client)
    quantities = {item.id: qty for item, qty in resolved}
    for line in note.items:
        item = next(i for i, _ in resolved if i.id == line.quotation_item_id)
        for key, value in _line_fields(item, quantities[item.id]).items():
            setattr(line, key, value)

    now = _naive_business_now()
    note.number = format_delivery_note_number(next_sequence_number(db, company_id, DELIVERY_NOTE_DOC_TYPE))
    note.status = ISSUED
    note.issue_date = now
    note.issued_at = now
    note.issued_by_id = user_id
    total = sum(line.quantity for line in note.items)
    log_event(db, quotation.id, "delivery_note_issued", f"Remito {note.number} emitido ({total} unidades)", user_id)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise DeliveryNoteError(CONFLICT, "No se pudo asignar el número de remito, reintentá.") from exc
    return note


def void(db: Session, *, company_id: int, user_id: int, note_id: int, reason: str) -> DeliveryNote:
    probe = _get_note(db, company_id, note_id)
    quotation = _get_quotation(db, company_id, probe.quotation_id, lock=True)
    note = _get_note(db, company_id, note_id, lock=True)
    if note.status != ISSUED:
        raise DeliveryNoteError(CONFLICT, "Solo se puede anular un remito emitido que no esté ya anulado.")
    now = _naive_business_now()
    note.status = VOIDED
    note.voided_at = now
    note.voided_by_id = user_id
    note.void_reason = reason
    log_event(db, quotation.id, "delivery_note_voided", f"Remito {note.number} anulado: {reason}", user_id)
    db.flush()
    return note


def list_notes(
    db: Session,
    *,
    company_id: int,
    status: str | None = None,
    quotation_id: int | None = None,
) -> list[DeliveryNote]:
    query = db.query(DeliveryNote).options(selectinload(DeliveryNote.items)).filter(DeliveryNote.company_id == company_id)
    if status:
        query = query.filter(DeliveryNote.status == status)
    if quotation_id is not None:
        query = query.filter(DeliveryNote.quotation_id == quotation_id)
    return query.order_by(DeliveryNote.id.desc()).all()
