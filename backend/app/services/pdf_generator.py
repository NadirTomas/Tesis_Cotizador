import io
from pathlib import Path

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.company import CompanyConfig
from app.models.quotation import Quotation

# ─── Paleta ───────────────────────────────────────────────────────────────────
DARK       = colors.HexColor("#1A1A2E")
ACCENT     = colors.HexColor("#FF6B00")
LIGHT_GRAY = colors.HexColor("#F5F5F5")
MID_GRAY   = colors.HexColor("#CCCCCC")
TEXT_GRAY  = colors.HexColor("#555555")
TEXT_DARK  = colors.HexColor("#222222")
WHITE      = colors.white

PAGE_W, PAGE_H = A4
MARGIN   = 18 * mm
USABLE_W = PAGE_W - 2 * MARGIN

# ─── Estilos ──────────────────────────────────────────────────────────────────
def _styles():
    return {
        "logo_name": ParagraphStyle(
            "logo_name",
            fontName="Helvetica-Bold",
            fontSize=18,
            textColor=WHITE,
            alignment=1,
            spaceAfter=1,
        ),
        "logo_sub": ParagraphStyle(
            "logo_sub",
            fontName="Helvetica",
            fontSize=7,
            textColor=colors.HexColor("#AAAACC"),
            alignment=1,
        ),
        "doc_label": ParagraphStyle(
            "doc_label",
            fontName="Helvetica",
            fontSize=9,
            textColor=TEXT_GRAY,
            alignment=2,
        ),
        "doc_number": ParagraphStyle(
            "doc_number",
            fontName="Helvetica-Bold",
            fontSize=11,
            textColor=TEXT_DARK,
            alignment=2,
        ),
        "doc_meta": ParagraphStyle(
            "doc_meta",
            fontName="Helvetica",
            fontSize=8.5,
            textColor=TEXT_GRAY,
            alignment=2,
            leading=14,
        ),
        "section_label": ParagraphStyle(
            "section_label",
            fontName="Helvetica-Bold",
            fontSize=8,
            textColor=TEXT_DARK,
            spaceAfter=3,
        ),
        "field_label": ParagraphStyle(
            "field_label",
            fontName="Helvetica",
            fontSize=7.5,
            textColor=TEXT_GRAY,
        ),
        "field_value": ParagraphStyle(
            "field_value",
            fontName="Helvetica",
            fontSize=9,
            textColor=TEXT_DARK,
            leading=13,
        ),
        "field_value_bold": ParagraphStyle(
            "field_value_bold",
            fontName="Helvetica-Bold",
            fontSize=9,
            textColor=TEXT_DARK,
        ),
        "table_header": ParagraphStyle(
            "table_header",
            fontName="Helvetica-Bold",
            fontSize=7.5,
            textColor=TEXT_DARK,
            alignment=0,
        ),
        "table_header_center": ParagraphStyle(
            "table_header_center",
            fontName="Helvetica-Bold",
            fontSize=7.5,
            textColor=TEXT_DARK,
            alignment=1,
        ),
        "table_header_right": ParagraphStyle(
            "table_header_right",
            fontName="Helvetica-Bold",
            fontSize=7.5,
            textColor=TEXT_DARK,
            alignment=2,
        ),
        "table_num": ParagraphStyle(
            "table_num",
            fontName="Helvetica",
            fontSize=8.5,
            textColor=TEXT_GRAY,
            alignment=1,
        ),
        "table_cell": ParagraphStyle(
            "table_cell",
            fontName="Helvetica",
            fontSize=8.5,
            textColor=TEXT_DARK,
            leading=12,
        ),
        "table_cell_right": ParagraphStyle(
            "table_cell_right",
            fontName="Helvetica",
            fontSize=8.5,
            textColor=TEXT_DARK,
            alignment=2,
        ),
        "table_cell_center": ParagraphStyle(
            "table_cell_center",
            fontName="Helvetica",
            fontSize=8.5,
            textColor=TEXT_DARK,
            alignment=1,
        ),
        "total_label": ParagraphStyle(
            "total_label",
            fontName="Helvetica-Bold",
            fontSize=9,
            textColor=TEXT_DARK,
            alignment=2,
        ),
        "total_value": ParagraphStyle(
            "total_value",
            fontName="Helvetica-Bold",
            fontSize=10,
            textColor=TEXT_DARK,
            alignment=2,
        ),
        "total_value_accent": ParagraphStyle(
            "total_value_accent",
            fontName="Helvetica-Bold",
            fontSize=13,
            textColor=ACCENT,
            alignment=2,
        ),
        "conditions": ParagraphStyle(
            "conditions",
            fontName="Helvetica",
            fontSize=8,
            textColor=TEXT_GRAY,
            leading=13,
        ),
        "footer": ParagraphStyle(
            "footer",
            fontName="Helvetica",
            fontSize=7.5,
            textColor=TEXT_GRAY,
            alignment=1,
        ),
    }


# ─── Helpers ──────────────────────────────────────────────────────────────────
def _fmt_ars(value: float) -> str:
    return f"$ {value:,.0f}".replace(",", ".")


def _fmt_num(value: float | None, decimals: int = 1) -> str:
    if value is None:
        return "—"
    return f"{value:,.{decimals}f}".replace(",", ".")


def _fmt_date(dt) -> str:
    if dt is None:
        return "—"
    return dt.strftime("%d/%m/%Y")


def _load_thumbnail(preview_data: bytes | None, size_mm: float) -> Image | None:
    """Carga una imagen preview (bytes) y la convierte a RGB para ReportLab."""
    if not preview_data:
        return None
    try:
        img = PILImage.open(io.BytesIO(preview_data))
        # Convertir RGBA → RGB con fondo blanco
        if img.mode in ("RGBA", "LA", "P"):
            background = PILImage.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            background.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
            img = background
        elif img.mode != "RGB":
            img = img.convert("RGB")

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        size_pt = size_mm * mm
        return Image(buf, width=size_pt, height=size_pt)
    except Exception:
        return None


# ─── Generador principal ──────────────────────────────────────────────────────
def generate_quotation_pdf(
    db: Session,
    quotation_id: int,
    output_dir: Path | None = None,
) -> Path:
    quotation = db.query(Quotation).filter(Quotation.id == quotation_id).first()
    if not quotation:
        raise ValueError("Quotation not found")

    company = db.query(CompanyConfig).first()
    client  = quotation.client
    items   = quotation.items

    if output_dir is None:
        settings = get_settings()
        output_dir = Path(settings.PDF_STORAGE_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"quotation_{quotation.id}.pdf"

    S = _styles()

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=MARGIN,
    )

    story = []

    # ── 1. Header ─────────────────────────────────────────────────────────────
    company_name = company.company_name if company else "CotizaLaser"

    # Logo: imagen si existe, sino caja oscura con texto
    logo_col_w = USABLE_W * 0.38
    logo_data = company.logo_data if company else None

    if logo_data:
        # Calcular dimensiones manteniendo aspecto, max ancho = logo_col_w, max alto = 18mm
        try:
            pil_img = PILImage.open(io.BytesIO(logo_data))
            img_w, img_h = pil_img.size
            max_w = logo_col_w - 8  # padding
            max_h = 18 * mm
            ratio = min(max_w / img_w, max_h / img_h)
            draw_w = img_w * ratio
            draw_h = img_h * ratio
            logo_flowable = Image(io.BytesIO(logo_data), width=draw_w, height=draw_h)
        except Exception:
            logo_flowable = Paragraph(company_name, S["logo_name"])

        logo_table = Table(
            [[logo_flowable]],
            colWidths=[logo_col_w],
        )
        logo_table.setStyle(TableStyle([
            ("TOPPADDING",    (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING",   (0, 0), (-1, -1), 0),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ]))
    else:
        # Fallback: caja oscura con texto
        logo_inner = [Paragraph(company_name, S["logo_name"])]
        if company and company.legal_name:
            logo_inner.append(Paragraph(company.legal_name, S["logo_sub"]))

        logo_table = Table(
            [logo_inner],
            colWidths=[logo_col_w],
        )
        logo_table.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), DARK),
            ("TOPPADDING",    (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ("LEFTPADDING",   (0, 0), (-1, -1), 12),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 12),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ]))

    right_header = [
        Paragraph("Número de cotización:", S["doc_label"]),
        Paragraph(quotation.number, S["doc_number"]),
        Spacer(1, 3),
        Paragraph(
            f"Fecha de emisión: <b>{_fmt_date(quotation.issue_date)}</b>",
            S["doc_meta"],
        ),
        Paragraph(
            f"Fecha de vencimiento: <b>{_fmt_date(quotation.due_date) if quotation.due_date else '—'}</b>",
            S["doc_meta"],
        ),
    ]

    header_table = Table(
        [[logo_table, right_header]],
        colWidths=[USABLE_W * 0.45, USABLE_W * 0.55],
    )
    header_table.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 6 * mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=MID_GRAY, spaceAfter=5 * mm))

    # ── 2. Preparado para / Preparado por ─────────────────────────────────────
    def _field(label: str, value: str) -> list:
        return [Paragraph(label, S["field_label"]), Paragraph(value or "—", S["field_value"])]

    # Columna izquierda: cliente
    client_rows = []
    if client:
        client_rows = [
            [Paragraph("<u>Preparado para:</u>", S["section_label"])],
            [Paragraph(client.name or "—", S["field_value_bold"])],
        ]
        if client.cuit_cuil:
            client_rows.append([Paragraph(f"CUIT/CUIL: {client.cuit_cuil}", S["field_label"])])
        if client.email:
            client_rows.append([Paragraph(f"Mail: {client.email}", S["field_label"])])
        if client.phone:
            client_rows.append([Paragraph(f"Tel: {client.phone}", S["field_label"])])
        if client.address:
            client_rows.append([Paragraph(client.address, S["field_label"])])
    else:
        client_rows = [[Paragraph("<u>Preparado para:</u>", S["section_label"])]]

    # Columna derecha: empresa
    company_rows = [
        [Paragraph("<u>Preparado por:</u>", S["section_label"])],
        [Paragraph(company_name, S["field_value_bold"])],
    ]
    if company:
        if company.legal_name:
            company_rows.append([Paragraph(company.legal_name, S["field_label"])])
        if company.cuit:
            company_rows.append([Paragraph(f"CUIT: {company.cuit}", S["field_label"])])
        if company.email:
            company_rows.append([Paragraph(f"Mail: {company.email}", S["field_label"])])
        if company.phone:
            company_rows.append([Paragraph(f"Tel: {company.phone}", S["field_label"])])
        if company.address:
            company_rows.append([Paragraph(company.address, S["field_label"])])

    # Igualar cantidad de filas para la tabla de 2 columnas
    max_rows = max(len(client_rows), len(company_rows))
    while len(client_rows) < max_rows:
        client_rows.append([Paragraph("", S["field_label"])])
    while len(company_rows) < max_rows:
        company_rows.append([Paragraph("", S["field_label"])])

    parties_data = [[client_rows[i][0], company_rows[i][0]] for i in range(max_rows)]
    half = USABLE_W / 2
    parties_table = Table(parties_data, colWidths=[half - 5, half - 5])
    parties_table.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
    ]))
    story.append(parties_table)
    story.append(Spacer(1, 4 * mm))

    # ── 2b. Método de pago ────────────────────────────────────────────────────
    if quotation.currency == "USD" and quotation.exchange_rate:
        pago_text = f"USD — Tipo de cambio: $ {quotation.exchange_rate:,.2f} ARS por USD (fijado a la fecha de emisión)"
    else:
        pago_text = "Pesos argentinos (ARS)"

    payment_table = Table(
        [[Paragraph("Método de pago:", S["field_label"]), Paragraph(pago_text, S["field_value"])]],
        colWidths=[USABLE_W * 0.22, USABLE_W * 0.78],
    )
    payment_table.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(payment_table)
    story.append(Spacer(1, 5 * mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=MID_GRAY, spaceAfter=4 * mm))

    # ── 3. Tabla de ítems ─────────────────────────────────────────────────────
    PREVIEW_SIZE = 20  # mm

    col_widths = [
        USABLE_W * 0.05,   # #
        USABLE_W * 0.12,   # Preview
        USABLE_W * 0.22,   # Nombre
        USABLE_W * 0.16,   # Material
        USABLE_W * 0.07,   # Cant.
        USABLE_W * 0.07,   # Esp.
        USABLE_W * 0.09,   # L. corte
        USABLE_W * 0.11,   # P. Unitario
        USABLE_W * 0.11,   # P. Total
    ]

    def _th(text, align="left"):
        style = {"left": S["table_header"], "center": S["table_header_center"], "right": S["table_header_right"]}[align]
        return Paragraph(text, style)

    headers = [
        _th("#",          "center"),
        _th(""),
        _th("Nombre"),
        _th("Material"),
        _th("Cant.",      "center"),
        _th("Esp.\n(mm)", "center"),
        _th("L. corte\n(mm)", "right"),
        _th("P. Unitario\n(ARS)", "right"),
        _th("P. Total\n(ARS)",    "right"),
    ]

    rows = [headers]
    for idx, item in enumerate(items, start=1):
        piece    = item.piece
        material = item.material
        thickness = f"{material.thickness_mm:.1f}" if material else "—"

        thumb = None
        if piece and piece.preview_data:
            thumb = _load_thumbnail(piece.preview_data, PREVIEW_SIZE)
        if thumb is None:
            thumb = Paragraph("", S["table_cell_center"])

        rows.append([
            Paragraph(str(idx),                                          S["table_num"]),
            thumb,
            Paragraph(piece.name if piece else "—",                      S["table_cell"]),
            Paragraph(material.name if material else "—",                S["table_cell"]),
            Paragraph(str(item.quantity),                                S["table_cell_center"]),
            Paragraph(thickness,                                         S["table_cell_center"]),
            Paragraph(_fmt_num(piece.length_cut_mm if piece else None),  S["table_cell_right"]),
            Paragraph(_fmt_ars(item.unit_price_ars),                     S["table_cell_right"]),
            Paragraph(_fmt_ars(item.total_price_ars),                    S["table_cell_right"]),
        ])

    items_table = Table(rows, colWidths=col_widths, repeatRows=1)
    items_table.setStyle(TableStyle([
        # Header: línea superior e inferior
        ("LINEABOVE",     (0, 0), (-1, 0),  0.5, MID_GRAY),
        ("LINEBELOW",     (0, 0), (-1, 0),  0.5, MID_GRAY),
        ("TOPPADDING",    (0, 0), (-1, 0),  5),
        ("BOTTOMPADDING", (0, 0), (-1, 0),  5),
        # Filas de datos
        ("LINEBELOW",     (0, 1), (-1, -1), 0.3, MID_GRAY),
        ("TOPPADDING",    (0, 1), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 6),
        # Padding general
        ("LEFTPADDING",   (0, 0), (-1, -1), 4),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        # Filas alternas muy suaves
        *[
            ("BACKGROUND", (0, i), (-1, i), LIGHT_GRAY if i % 2 == 0 else WHITE)
            for i in range(1, len(rows))
        ],
    ]))
    story.append(items_table)
    story.append(Spacer(1, 6 * mm))

    # ── 4. Totales ────────────────────────────────────────────────────────────
    totals_data = []

    if quotation.total_usd and quotation.total_usd > 0 and quotation.exchange_rate:
        totals_data.append([
            Paragraph("Total USD:", S["total_label"]),
            Paragraph(f"U$D {quotation.total_usd:,.2f}", S["total_value"]),
        ])

    totals_data.append([
        Paragraph("Total ARS:", S["total_label"]),
        Paragraph(_fmt_ars(quotation.total_ars), S["total_value_accent"]),
    ])

    totals_table = Table(
        totals_data,
        colWidths=[USABLE_W * 0.82, USABLE_W * 0.18],
    )
    totals_table.setStyle(TableStyle([
        ("ALIGN",         (0, 0), (-1, -1), "RIGHT"),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ("LINEABOVE",     (0, -1), (-1, -1), 0.5, MID_GRAY),
        ("TOPPADDING",    (0, -1), (-1, -1), 6),
    ]))
    story.append(totals_table)
    story.append(Spacer(1, 8 * mm))

    # ── 5. Condiciones ────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=MID_GRAY, spaceAfter=4 * mm))

    validity = (
        f"hasta el {_fmt_date(quotation.due_date)}"
        if quotation.due_date
        else "7 días corridos desde la fecha de emisión"
    )
    conditions_text = (
        f"<b>Validez:</b> La presente cotización tiene validez {validity}. "
        "Los precios están sujetos a cambios sin previo aviso fuera del plazo indicado.<br/>"
        "<b>Condiciones de pago:</b> A convenir.<br/>"
        "<b>Tiempos de entrega:</b> A confirmar según disponibilidad de agenda y materiales."
    )
    if quotation.notes:
        conditions_text += f"<br/><b>Observaciones:</b> {quotation.notes}"

    story.append(Paragraph(conditions_text, S["conditions"]))
    story.append(Spacer(1, 6 * mm))

    # ── 6. Footer ─────────────────────────────────────────────────────────────
    footer_parts = [company_name]
    if company:
        if company.phone:
            footer_parts.append(f"Tel: {company.phone}")
        if company.email:
            footer_parts.append(company.email)

    story.append(HRFlowable(width="100%", thickness=0.5, color=MID_GRAY, spaceAfter=3 * mm))
    story.append(Paragraph("  ·  ".join(footer_parts), S["footer"]))

    doc.build(story)
    return output_path
