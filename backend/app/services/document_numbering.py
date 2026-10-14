from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.document_sequence import DocumentSequence

DELIVERY_NOTE_DOC_TYPE = "DELIVERY_NOTE"
DELIVERY_NOTE_PREFIX = "R-"


def next_sequence_number(db: Session, company_id: int, doc_type: str) -> int:
    """Devuelve el próximo número consecutivo para (empresa, tipo de documento).

    No hace commit: el incremento queda dentro de la transacción del llamador.
    El UPDATE ... RETURNING toma el lock de la fila del contador, así que dos
    transacciones concurrentes se serializan (la segunda espera y recién
    entonces incrementa el valor ya comiteado) en vez de leer el mismo
    "último número" — a diferencia de MAX(numero)+1, que no es seguro.
    Si la transacción se revierte, el contador se revierte con ella."""
    for _ in range(3):
        row = db.execute(
            update(DocumentSequence)
            .where(DocumentSequence.company_id == company_id, DocumentSequence.doc_type == doc_type)
            .values(last_number=DocumentSequence.last_number + 1)
            .returning(DocumentSequence.last_number)
        ).first()
        if row is not None:
            return row[0]
        # Primera emisión de la empresa: se crea el contador. Si otra
        # transacción lo creó en simultáneo, el índice único lo rechaza y se
        # reintenta el UPDATE (ya existe).
        try:
            with db.begin_nested():
                db.add(DocumentSequence(company_id=company_id, doc_type=doc_type, last_number=0))
        except IntegrityError:
            continue
    raise RuntimeError("No se pudo obtener el número de documento")


def format_delivery_note_number(n: int) -> str:
    return f"{DELIVERY_NOTE_PREFIX}{n:06d}"
