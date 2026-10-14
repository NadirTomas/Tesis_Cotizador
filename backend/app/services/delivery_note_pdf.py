"""PDF imprimible del remito de entrega.

Reutiliza paleta, estilos y bloque de logo de pdf_generator. Nunca incluye
costos, márgenes ni fórmulas: solo piezas y cantidades entregadas. El estado
del documento se ve en el PDF: un borrador no se confunde con un remito
emitido (marca de agua + leyenda) y un remito anulado queda marcado."""

import io
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.delivery_note import DRAFT, VOIDED, DeliveryNote
from app.services.pdf_generator import (
    ACCENT,
    LIGHT_GRAY,
    MARGIN,
    MID_GRAY,
    TEXT_DARK,
    TEXT_GRAY,
    USABLE_W,
    _fmt_date,
    _styles,
    build_company_logo,
)

_STATUS_WATERMARK = {DRAFT: "BORRADOR", VOIDED: "ANULADO"}
_DANGER = colors.HexColor("#B91C1C")
_HEADER_BG = colors.HexColor("#E6E6EA")


def _numbered_canvas_factory(label: str):
    """Canvas que dibuja en cada hoja la identificación del documento y "Hoja i de n"
    (si las hojas se separan, cada una sigue identificando a qué remito pertenece)."""

    class _NumberedCanvas(rl_canvas.Canvas):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._saved_pages: list[dict] = []

        def showPage(self):
            self._saved_pages.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            total = len(self._saved_pages)
            for state in self._saved_pages:
                self.__dict__.update(state)
                self._draw_footer(total)
                super().showPage()
            super().save()

        def _draw_footer(self, total: int):
            self.setFont("Helvetica", 7.5)
            self.setFillColor(TEXT_GRAY)
            y = 9 * mm
            self.drawString(MARGIN, y, label)
            self.drawRightString(A4[0] - MARGIN, y, f"Hoja {self._pageNumber} de {total}")

    return _NumberedCanvas


def _p(text: str | None, style) -> Paragraph:
    return Paragraph(escape(text) if text else "—", style)


def _watermark(text: str | None):
    def draw(canvas, doc):
        if not text:
            return
        canvas.saveState()
        canvas.setFont("Helvetica-Bold", 90)
        canvas.setFillColor(colors.Color(0.85, 0.2, 0.2, alpha=0.12))
        canvas.translate(A4[0] / 2, A4[1] / 2)
        canvas.rotate(40)
        canvas.drawCentredString(0, 0, text)
        canvas.restoreState()

    return draw


def _signature_block(title: str, extra_line: str | None, S) -> Table:
    rows = [
        [Paragraph(f"<b>{escape(title)}</b>", S["field_value"])],
        [Spacer(1, 16 * mm)],
        [HRFlowable(width="100%", thickness=0.6, color=TEXT_GRAY)],
        [Paragraph("Firma", S["field_label"])],
        [Spacer(1, 5 * mm)],
        [HRFlowable(width="100%", thickness=0.6, color=TEXT_GRAY)],
        [Paragraph("Aclaración", S["field_label"])],
    ]
    if extra_line:
        rows += [
            [Spacer(1, 5 * mm)],
            [HRFlowable(width="100%", thickness=0.6, color=TEXT_GRAY)],
            [Paragraph(extra_line, S["field_label"])],
        ]
    table = Table(rows, colWidths=[USABLE_W / 2 - 8 * mm])
    table.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]))
    return table


def generate_delivery_note_pdf(db: Session, note_id: int, company_id: int) -> bytes:
    note = (
        db.query(DeliveryNote)
        .filter(DeliveryNote.id == note_id, DeliveryNote.company_id == company_id)
        .first()
    )
    if not note:
        raise ValueError("Delivery note not found")
    company = db.query(Company).filter(Company.id == company_id).first()
    company_name = company.company_name if company else "CotizaLaser"
    S = _styles()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=MARGIN,
        title=f"Remito {note.number}" if note.number else "Remito (borrador)",
    )
    story = []

    # ── Encabezado ───────────────────────────────────────────────────────────
    logo = build_company_logo(company, company_name, S, USABLE_W * 0.38)
    right_header = [
        Paragraph("<b>REMITO</b>", S["doc_number"]),
        Paragraph(escape(note.number) if note.number else "SIN NÚMERO (borrador)", S["doc_number"]),
        Spacer(1, 3),
        Paragraph(f"Fecha de emisión: <b>{_fmt_date(note.issue_date)}</b>", S["doc_meta"]),
        Paragraph(f"Cotización de origen: <b>{escape(note.quotation_number)}</b>", S["doc_meta"]),
    ]
    header = Table([[logo, right_header]], colWidths=[USABLE_W * 0.45, USABLE_W * 0.55])
    header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story += [header, Spacer(1, 5 * mm), HRFlowable(width="100%", thickness=0.5, color=MID_GRAY, spaceAfter=4 * mm)]

    # ── Leyenda de estado ────────────────────────────────────────────────────
    if note.status == DRAFT:
        banner = "BORRADOR — documento sin validez: todavía no fue emitido."
    elif note.status == VOIDED:
        banner = f"ANULADO el {_fmt_date(note.voided_at)}. Motivo: {note.void_reason or '—'}"
    else:
        banner = None
    if banner:
        box = Table([[Paragraph(f'<font color="#B91C1C"><b>{escape(banner)}</b></font>', S["field_value"])]], colWidths=[USABLE_W])
        box.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 1, _DANGER),
            ("TEXTCOLOR", (0, 0), (-1, -1), _DANGER),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ]))
        story += [box, Spacer(1, 4 * mm)]

    # ── Partes ───────────────────────────────────────────────────────────────
    def _party(title: str, rows: list[tuple[str, str | None]]) -> list:
        cells = [Paragraph(title, S["section_label"])]
        for label, value in rows:
            if value:
                cells.append(Paragraph(f"<b>{escape(label)}:</b> {escape(value)}", S["field_value"]))
        return cells

    client_cells = _party("ENTREGADO A", [
        ("Cliente", note.client_name),
        ("CUIT/CUIL", note.client_tax_id),
        ("Dirección", note.client_address),
    ])
    issuer_cells = _party("EMITIDO POR", [
        ("Empresa", (company.legal_name or company.company_name) if company else company_name),
        ("CUIT", company.cuit if company else None),
        ("Dirección", company.address if company else None),
        ("Teléfono", company.phone if company else None),
    ])
    half = USABLE_W / 2
    parties = Table([[client_cells, issuer_cells]], colWidths=[half, half])
    parties.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story += [parties, Spacer(1, 6 * mm)]

    # ── Detalle ──────────────────────────────────────────────────────────────
    data = [[
        Paragraph("Pieza", S["table_header"]),
        Paragraph("Descripción", S["table_header"]),
        Paragraph("Cantidad", S["table_header_right"]),
        Paragraph("Unidad", S["table_header_center"]),
    ]]
    for line in note.items:
        data.append([
            _p(line.piece_name, S["table_cell"]),
            _p(line.piece_description, S["table_cell"]),
            Paragraph(str(line.quantity), S["table_cell_right"]),
            Paragraph(escape(line.unit or "un"), S["table_cell_center"]),
        ])
    total_units = sum(line.quantity for line in note.items)
    data.append([
        Paragraph("<b>Total de unidades</b>", S["table_cell"]),
        "",
        Paragraph(f"<b>{total_units}</b>", S["table_cell_right"]),
        "",
    ])
    detail = Table(data, colWidths=[USABLE_W * 0.34, USABLE_W * 0.38, USABLE_W * 0.14, USABLE_W * 0.14], repeatRows=1)
    detail.setStyle(TableStyle([
        # Los estilos "table_header" del PDF de cotización tienen texto OSCURO: el fondo del encabezado debe ser claro.
        ("BACKGROUND", (0, 0), (-1, 0), _HEADER_BG),
        ("LINEBELOW", (0, 0), (-1, 0), 1, TEXT_DARK),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, LIGHT_GRAY]),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, MID_GRAY),
        ("LINEABOVE", (0, -1), (-1, -1), 0.8, ACCENT),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story += [detail, Spacer(1, 6 * mm)]

    # ── Observaciones ────────────────────────────────────────────────────────
    if note.notes:
        story += [
            Paragraph("OBSERVACIONES", S["section_label"]),
            Paragraph(escape(note.notes).replace("\n", "<br/>"), S["field_value"]),
            Spacer(1, 6 * mm),
        ]

    # ── Firmas ───────────────────────────────────────────────────────────────
    signatures = Table(
        [[_signature_block("ENTREGA", None, S), _signature_block("RECIBE (conformidad)", "Fecha de recepción", S)]],
        colWidths=[half, half],
    )
    signatures.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story += [Spacer(1, 4 * mm), signatures]

    watermark = _watermark(_STATUS_WATERMARK.get(note.status))
    footer = f"Remito {note.number} · Cotización {note.quotation_number}" if note.number else f"Remito (borrador) · Cotización {note.quotation_number}"
    doc.build(story, onFirstPage=watermark, onLaterPages=watermark, canvasmaker=_numbered_canvas_factory(footer))
    return buffer.getvalue()
