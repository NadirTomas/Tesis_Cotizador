from dataclasses import dataclass

from pydantic import BaseModel

EPS = 1e-6


class NestingItemInput(BaseModel):
    piece_id: int
    label: str
    width_mm: float
    height_mm: float
    quantity: int


class Placement(BaseModel):
    piece_id: int
    piece_label: str
    x: float
    y: float
    width_mm: float
    height_mm: float
    rotated: bool


class SheetLayout(BaseModel):
    placements: list[Placement]
    utilization_pct: float


class NestingResult(BaseModel):
    sheets: list[SheetLayout]
    total_sheets: int
    total_pieces_requested: int
    total_pieces_placed: int
    overall_utilization_pct: float
    sheet_width_mm: float
    sheet_height_mm: float
    margin_mm: float


@dataclass
class _FreeRect:
    x: float
    y: float
    w: float
    h: float


def _overlaps(fr: _FreeRect, px: float, py: float, pw: float, ph: float) -> bool:
    return px < fr.x + fr.w - EPS and px + pw > fr.x + EPS and py < fr.y + fr.h - EPS and py + ph > fr.y + EPS


def _contains(outer: _FreeRect, inner: _FreeRect) -> bool:
    return (
        inner.x >= outer.x - EPS
        and inner.y >= outer.y - EPS
        and inner.x + inner.w <= outer.x + outer.w + EPS
        and inner.y + inner.h <= outer.y + outer.h + EPS
    )


def _rect_equal(a: _FreeRect, b: _FreeRect) -> bool:
    return abs(a.x - b.x) < EPS and abs(a.y - b.y) < EPS and abs(a.w - b.w) < EPS and abs(a.h - b.h) < EPS


def _split_free_rects(free_rects: list[_FreeRect], px: float, py: float, pw: float, ph: float) -> list[_FreeRect]:
    split: list[_FreeRect] = []
    for fr in free_rects:
        if not _overlaps(fr, px, py, pw, ph):
            split.append(fr)
            continue
        if px > fr.x + EPS:
            split.append(_FreeRect(fr.x, fr.y, px - fr.x, fr.h))
        if px + pw < fr.x + fr.w - EPS:
            split.append(_FreeRect(px + pw, fr.y, fr.x + fr.w - (px + pw), fr.h))
        if py > fr.y + EPS:
            split.append(_FreeRect(fr.x, fr.y, fr.w, py - fr.y))
        if py + ph < fr.y + fr.h - EPS:
            split.append(_FreeRect(fr.x, py + ph, fr.w, fr.y + fr.h - (py + ph)))

    split = [r for r in split if r.w > EPS and r.h > EPS]

    pruned: list[_FreeRect] = []
    for i, r in enumerate(split):
        dominated = False
        for j, other in enumerate(split):
            if i == j or not _contains(other, r):
                continue
            if _rect_equal(r, other):
                if j < i:
                    dominated = True
                    break
                continue
            dominated = True
            break
        if not dominated:
            pruned.append(r)
    return pruned


def _find_best_placement(cand: dict, free_rects: list[_FreeRect], allow_rotation: bool, margin_mm: float):
    orientations = [(cand["w"], cand["h"], False)]
    if allow_rotation and abs(cand["w"] - cand["h"]) > EPS:
        orientations.append((cand["h"], cand["w"], True))

    best = None
    for fr in free_rects:
        for w, h, rotated in orientations:
            cell_w, cell_h = w + margin_mm, h + margin_mm
            if cell_w <= fr.w + EPS and cell_h <= fr.h + EPS:
                leftover_w = fr.w - cell_w
                leftover_h = fr.h - cell_h
                score = (min(leftover_w, leftover_h), max(leftover_w, leftover_h))
                if best is None or score < best[0]:
                    best = (score, fr.x, fr.y, w, h, rotated)
    if best is None:
        return None
    _, x, y, w, h, rotated = best
    return x, y, w, h, rotated


def pack_pieces(
    items: list[NestingItemInput],
    sheet_w: float,
    sheet_h: float,
    margin_mm: float = 5.0,
    allow_rotation: bool = True,
) -> NestingResult:
    """
    Empaqueta piezas de distinto tamaño y cantidad en tantas chapas como haga
    falta, usando MaxRects — Best Short Side Fit, con rotación 90 grados
    opcional. El margen se trata como espacio reservado a la derecha/abajo de
    cada pieza (mismo criterio que usaba el packer anterior de grilla).
    """
    total_requested = sum(item.quantity for item in items)
    usable_w = sheet_w - 2 * margin_mm
    usable_h = sheet_h - 2 * margin_mm

    if usable_w <= 0 or usable_h <= 0 or total_requested == 0:
        return NestingResult(
            sheets=[],
            total_sheets=0,
            total_pieces_requested=total_requested,
            total_pieces_placed=0,
            overall_utilization_pct=0.0,
            sheet_width_mm=sheet_w,
            sheet_height_mm=sheet_h,
            margin_mm=margin_mm,
        )

    queue: list[dict] = []
    unplaced = 0
    for item in items:
        cell_w, cell_h = item.width_mm + margin_mm, item.height_mm + margin_mm
        fits_normal = cell_w <= usable_w + EPS and cell_h <= usable_h + EPS
        fits_rotated = allow_rotation and cell_h <= usable_w + EPS and cell_w <= usable_h + EPS
        if not fits_normal and not fits_rotated:
            unplaced += item.quantity
            continue
        for _ in range(item.quantity):
            queue.append({"piece_id": item.piece_id, "label": item.label, "w": item.width_mm, "h": item.height_mm})

    queue.sort(key=lambda p: max(p["w"], p["h"]), reverse=True)

    sheets: list[SheetLayout] = []
    while queue:
        free_rects = [_FreeRect(0.0, 0.0, usable_w, usable_h)]
        placements: list[Placement] = []
        progress = True
        while queue and free_rects and progress:
            progress = False
            for idx, cand in enumerate(queue):
                found = _find_best_placement(cand, free_rects, allow_rotation, margin_mm)
                if found is None:
                    continue
                x, y, w, h, rotated = found
                placements.append(
                    Placement(
                        piece_id=cand["piece_id"],
                        piece_label=cand["label"],
                        x=round(x + margin_mm, 2),
                        y=round(y + margin_mm, 2),
                        width_mm=round(w, 2),
                        height_mm=round(h, 2),
                        rotated=rotated,
                    )
                )
                free_rects = _split_free_rects(free_rects, x, y, w + margin_mm, h + margin_mm)
                queue.pop(idx)
                progress = True
                break

        if not placements:
            unplaced += len(queue)
            break

        sheet_area = sheet_w * sheet_h
        used_area = sum(p.width_mm * p.height_mm for p in placements)
        utilization = round(used_area / sheet_area * 100, 1) if sheet_area > 0 else 0.0
        sheets.append(SheetLayout(placements=placements, utilization_pct=utilization))

    total_placed = total_requested - unplaced
    overall_area = sum(p.width_mm * p.height_mm for sheet in sheets for p in sheet.placements)
    overall_utilization = (
        round(overall_area / (sheet_w * sheet_h * len(sheets)) * 100, 1) if sheets else 0.0
    )

    return NestingResult(
        sheets=sheets,
        total_sheets=len(sheets),
        total_pieces_requested=total_requested,
        total_pieces_placed=total_placed,
        overall_utilization_pct=overall_utilization,
        sheet_width_mm=sheet_w,
        sheet_height_mm=sheet_h,
        margin_mm=margin_mm,
    )
