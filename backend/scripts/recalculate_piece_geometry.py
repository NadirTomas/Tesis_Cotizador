"""
Recalcula Piece.area_mm2 / Piece.length_cut_mm reprocesando el dxf_data ya
guardado con la implementación ACTUAL de analyze_dxf() (fix de agujeros y
CIRCLE del commit 134425d, 2026-08-26). Contexto completo en
PROJECT_MEMORY.md, sección "Historia del DXF".

Por defecto corre en modo dry-run: NO escribe nada en la base, solo
reporta qué cambiaría. Requiere --apply explícito para persistir.

Política sobre cotizaciones (no negociable, ver tests):
  - draft:     se recalcula el QuotationItem con calculate_quotation_item()
               real (misma fórmula que usa la app), solo si la pieza
               cambió de verdad y la cotización SIGUE en draft en el
               momento exacto de persistir (guard contra carrera).
  - sent / accepted / cancelled: la Piece se corrige, el QuotationItem
               NUNCA se toca — sus columnas de costo quedan
               bit-a-bit idénticas.

Uso:
    python -m scripts.recalculate_piece_geometry                  # dry-run, todas las empresas
    python -m scripts.recalculate_piece_geometry --company-id 3   # dry-run acotado a una empresa
    python -m scripts.recalculate_piece_geometry --apply          # aplica de verdad
    python -m scripts.recalculate_piece_geometry --apply --company-id 3
"""
from __future__ import annotations

import argparse
import math
import sys
import tempfile
from pathlib import Path
from typing import Optional

from sqlalchemy import update as sa_update
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.piece import Piece
from app.models.quotation import Quotation
from app.models.quotation_item import QuotationItem
from app.services.dxf_analysis import analyze_dxf
from app.services.quotation_calculator import (
    calculate_quotation_item,
    compute_item_costs,
    fetch_item_costing_context,
)

# Tolerancia para decidir si un valor "cambió" — evita que ruido de punto
# flotante (distinto orden de suma entre el cálculo viejo y el nuevo,
# aunque la geometría sea idéntica) dispare un "cambio" espurio y rompa
# la idempotencia de una segunda corrida.
_REL_TOL = 1e-6
_ABS_TOL = 1e-6


def _values_differ(old: Optional[float], new: Optional[float]) -> bool:
    old = old or 0.0
    new = new or 0.0
    return not math.isclose(old, new, rel_tol=_REL_TOL, abs_tol=_ABS_TOL)


def _pct_diff(old: Optional[float], new: Optional[float]) -> Optional[float]:
    old = old or 0.0
    new = new or 0.0
    if old == 0:
        return None if new == 0 else math.inf
    return (new - old) / old * 100.0


def _fmt_pct(pct: Optional[float]) -> str:
    if pct is None:
        return "0.00%"
    if math.isinf(pct):
        return "+inf% (antes $0)"
    return f"{pct:+.2f}%"


def _analyze_piece_dxf(piece: Piece) -> tuple[float, float]:
    """Reanaliza el DXF ya guardado con analyze_dxf() real — misma función que usa upload-dxf."""
    with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as tmp:
        tmp.write(piece.dxf_data)
        tmp_path = tmp.name
    try:
        return analyze_dxf(tmp_path)
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def _quotation_still_draft(db: Session, quotation_id: int) -> bool:
    """
    Guard atómico contra la carrera dry-run/scan -> apply: alguien puede
    enviar/aceptar la cotización en el medio. UPDATE condicional
    (WHERE status='draft') con rowcount, mismo patrón que ya usa el resto
    del código (reserve/confirm-cut/release) para invariantes bajo
    concurrencia real — no un SELECT-luego-escribir.
    """
    result = db.execute(
        sa_update(Quotation)
        .where(Quotation.id == quotation_id, Quotation.status == "draft")
        .values(status="draft")
    )
    return result.rowcount > 0


def run(db: Session, *, apply: bool, company_id: Optional[int] = None, verbose: bool = True) -> dict:
    stats = {
        "pieces_inspected": 0,
        "pieces_unchanged": 0,
        "pieces_corrected": 0,
        "dxf_errors": 0,
        "draft_items_previewed": 0,  # filas generadas (dry-run o apply, antes del guard de carrera)
        "draft_items_recalculated": 0,  # solo apply, y solo si pasó el guard de carrera
        "historical_items_preserved": 0,
        "draft_items_protected_race": 0,
        "item_context_errors": 0,
    }
    item_rows: list[dict] = []

    def log(msg: str) -> None:
        if verbose:
            print(msg)

    query = db.query(Piece).filter(Piece.dxf_data.isnot(None))
    if company_id is not None:
        query = query.filter(Piece.company_id == company_id)

    for piece in query.order_by(Piece.id).all():
        stats["pieces_inspected"] += 1
        try:
            new_length, new_area = _analyze_piece_dxf(piece)
        except Exception as exc:  # noqa: BLE001 - loguear y seguir, un DXF corrupto no debe abortar el batch
            stats["dxf_errors"] += 1
            log(f"[ERROR] piece_id={piece.id} company_id={piece.company_id}: no se pudo analizar el DXF — {exc}")
            continue

        old_area = piece.area_mm2
        old_length = piece.length_cut_mm
        if not _values_differ(old_area, new_area) and not _values_differ(old_length, new_length):
            stats["pieces_unchanged"] += 1
            continue

        stats["pieces_corrected"] += 1
        log(
            f"[PIEZA] id={piece.id} company_id={piece.company_id} "
            f"area_mm2: {old_area} -> {new_area} | length_cut_mm: {old_length} -> {new_length}"
        )

        # Se fija en el objeto ORM (todavía sin flush/commit) para que, en
        # modo --apply, calculate_quotation_item() lea la geometría nueva.
        # En dry-run nunca se flushea (SessionLocal ya es autoflush=False)
        # y se descarta con db.rollback() al cerrar esta pieza.
        piece.area_mm2 = new_area
        piece.length_cut_mm = new_length

        items = (
            db.query(QuotationItem)
            .join(Quotation, Quotation.id == QuotationItem.quotation_id)
            .filter(QuotationItem.piece_id == piece.id)
            .all()
        )

        for item in items:
            quotation = item.quotation
            if quotation.status != "draft":
                stats["historical_items_preserved"] += 1
                continue

            try:
                _, material, machine_config = fetch_item_costing_context(db, item, piece.company_id)
            except ValueError as exc:
                stats["item_context_errors"] += 1
                log(f"  [ERROR] quotation_item_id={item.id}: no se pudo previsualizar — {exc}")
                continue

            old_unit_price = item.unit_price_ars
            old_total_price = item.total_price_ars
            new_costs = compute_item_costs(
                new_area, new_length, material, machine_config, item.quantity, item.margin_percent
            )
            abs_diff = new_costs.total_price_ars - old_total_price
            pct = _pct_diff(old_total_price, new_costs.total_price_ars)
            row = {
                "quotation_id": quotation.id,
                "quotation_number": quotation.number,
                "quotation_item_id": item.id,
                "piece_id": piece.id,
                "unit_price_old": old_unit_price,
                "unit_price_new": new_costs.unit_price_ars,
                "total_price_old": old_total_price,
                "total_price_new": new_costs.total_price_ars,
                "abs_diff": abs_diff,
                "pct_diff": pct,
            }
            item_rows.append(row)
            stats["draft_items_previewed"] += 1
            log(
                f"  [ITEM draft] quotation={row['quotation_number']} (id={row['quotation_id']}) "
                f"item_id={item.id} unit_price: {old_unit_price:.2f} -> {new_costs.unit_price_ars:.2f} "
                f"total_price: {old_total_price:.2f} -> {new_costs.total_price_ars:.2f} "
                f"(diff {abs_diff:+.2f}, {_fmt_pct(pct)})"
            )

            if apply:
                if not _quotation_still_draft(db, quotation.id):
                    stats["draft_items_protected_race"] += 1
                    log(
                        f"  [PROTEGIDO] quotation_id={quotation.id} dejó de estar en draft "
                        f"justo antes de persistir — item {item.id} NO se modifica"
                    )
                    continue
                calculate_quotation_item(db, item, piece.company_id)
                stats["draft_items_recalculated"] += 1

        if apply:
            db.flush()
            db.commit()
        else:
            db.rollback()

    return stats, item_rows


def _print_summary(stats: dict, apply: bool) -> None:
    mode = "APLICADO" if apply else "DRY-RUN (nada se escribio)"
    draft_count = stats["draft_items_recalculated"] if apply else stats["draft_items_previewed"]
    draft_label = "recalculados" if apply else "que se recalcularian"
    print("\n" + "=" * 60)
    print(f"Resumen - modo: {mode}")
    print("=" * 60)
    print(f"Piezas inspeccionadas:                  {stats['pieces_inspected']}")
    print(f"Piezas sin cambios:                     {stats['pieces_unchanged']}")
    print(f"Piezas corregidas:                      {stats['pieces_corrected']}")
    print(f"Errores de DXF:                          {stats['dxf_errors']}")
    print(f"Quotation items draft {draft_label}: {draft_count}")
    print(f"Quotation items historicos preservados: {stats['historical_items_preserved']}")
    print(f"Items protegidos por cambio de estado:  {stats['draft_items_protected_race']}")
    print(f"Errores de contexto de item:             {stats['item_context_errors']}")
    print("=" * 60)


def main() -> None:
    # Windows a veces corre con una codepage que no soporta UTF-8 (tildes,
    # "->"); forzarlo evita salida ilegible sin afectar Linux/Railway.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="Persiste los cambios. Sin esto, corre en dry-run.")
    parser.add_argument("--company-id", type=int, default=None, help="Acota el recálculo a una sola empresa.")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        stats, _ = run(db, apply=args.apply, company_id=args.company_id)
    finally:
        db.close()
    _print_summary(stats, args.apply)


if __name__ == "__main__":
    main()
