from math import floor

from pydantic import BaseModel


class NestingPosition(BaseModel):
    x: float
    y: float


class NestingResult(BaseModel):
    positions: list[NestingPosition]
    pieces_fit: int
    pieces_per_row: int
    rows: int
    utilization_pct: float
    piece_width_mm: float
    piece_height_mm: float
    sheet_width_mm: float
    sheet_height_mm: float
    margin_mm: float


def calculate_nesting(
    piece_w: float,
    piece_h: float,
    sheet_w: float,
    sheet_h: float,
    margin_mm: float = 5.0,
) -> NestingResult:
    """
    Calcula un layout de grilla simple (sin rotación).
    Cada pieza ocupa una celda de (piece_w + margin) x (piece_h + margin).
    El margen también aplica en los bordes de la chapa.
    """
    if piece_w <= 0 or piece_h <= 0 or sheet_w <= 0 or sheet_h <= 0:
        return NestingResult(
            positions=[],
            pieces_fit=0,
            pieces_per_row=0,
            rows=0,
            utilization_pct=0.0,
            piece_width_mm=piece_w,
            piece_height_mm=piece_h,
            sheet_width_mm=sheet_w,
            sheet_height_mm=sheet_h,
            margin_mm=margin_mm,
        )

    cell_w = piece_w + margin_mm
    cell_h = piece_h + margin_mm

    per_row = max(0, floor((sheet_w - margin_mm) / cell_w))
    rows = max(0, floor((sheet_h - margin_mm) / cell_h))
    total = per_row * rows

    positions: list[NestingPosition] = []
    for row in range(rows):
        for col in range(per_row):
            positions.append(NestingPosition(
                x=margin_mm + col * cell_w,
                y=margin_mm + row * cell_h,
            ))

    used_area = total * piece_w * piece_h
    sheet_area = sheet_w * sheet_h
    utilization_pct = round(used_area / sheet_area * 100, 1) if sheet_area > 0 else 0.0

    return NestingResult(
        positions=positions,
        pieces_fit=total,
        pieces_per_row=per_row,
        rows=rows,
        utilization_pct=utilization_pct,
        piece_width_mm=piece_w,
        piece_height_mm=piece_h,
        sheet_width_mm=sheet_w,
        sheet_height_mm=sheet_h,
        margin_mm=margin_mm,
    )
