"""
Carga datos de prueba realistas.
Limpia los datos existentes antes de insertar.
Ejecutar con: venv/Scripts/python seed_data.py
"""
from datetime import datetime, timedelta
from pathlib import Path

from app.db.session import SessionLocal
from app.models.client import Client
from app.models.company import CompanyConfig
from app.models.machine_config import MachineConfig
from app.models.material import Material
from app.models.piece import Piece
from app.models.quotation import Quotation
from app.models.quotation_item import QuotationItem
from app.services.dxf_analysis import analyze_dxf
from app.services.dxf_preview import generate_dxf_preview
from app.services.quotation_calculator import calculate_quotation_item

db = SessionLocal()

# ─── Limpiar datos existentes ─────────────────────────────────────────────────
print("Limpiando datos existentes...")
db.query(QuotationItem).delete()
db.query(Quotation).delete()
db.query(Piece).delete()
db.query(MachineConfig).delete()
db.query(Material).delete()
db.query(Client).delete()
db.query(CompanyConfig).delete()
db.commit()

# ─── 1. Empresa ───────────────────────────────────────────────────────────────
print("Cargando empresa...")
company = CompanyConfig(
    company_name="MetalCorte SRL",
    legal_name="MetalCorte Servicios Industriales SRL",
    cuit="30-71234567-8",
    address="Av. Industrial 1450, Parque Industrial Oeste, Córdoba",
    phone="+54 351 456-7890",
    email="ventas@metalcorte.com.ar",
)
db.add(company)
db.commit()

# ─── 2. Materiales ────────────────────────────────────────────────────────────
print("Cargando materiales...")
materials_data = [
    dict(name="Acero SAE 1010 3mm",    thickness_mm=3.0,  sheet_width_mm=1500, sheet_height_mm=3000, sheet_cost_ars=85000),
    dict(name="Acero SAE 1010 5mm",    thickness_mm=5.0,  sheet_width_mm=1500, sheet_height_mm=3000, sheet_cost_ars=138000),
    dict(name="Acero SAE 1010 10mm",   thickness_mm=10.0, sheet_width_mm=1500, sheet_height_mm=3000, sheet_cost_ars=265000),
    dict(name="Inoxidable AISI 304 2mm", thickness_mm=2.0, sheet_width_mm=1000, sheet_height_mm=2000, sheet_cost_ars=210000),
    dict(name="Inoxidable AISI 304 3mm", thickness_mm=3.0, sheet_width_mm=1000, sheet_height_mm=2000, sheet_cost_ars=310000),
]
mats = {}
for m in materials_data:
    obj = Material(**m)
    db.add(obj)
    db.flush()
    mats[m["name"]] = obj
db.commit()

# ─── 3. Configuraciones de máquina ───────────────────────────────────────────
print("Cargando configuraciones de máquina...")
configs_data = [
    dict(material=mats["Acero SAE 1010 3mm"],      cut_speed_mm_min=3500, machine_cost_per_hour_ars=18000, setup_time_min=10, labor_percent=30),
    dict(material=mats["Acero SAE 1010 5mm"],      cut_speed_mm_min=2200, machine_cost_per_hour_ars=18000, setup_time_min=12, labor_percent=30),
    dict(material=mats["Acero SAE 1010 10mm"],     cut_speed_mm_min=900,  machine_cost_per_hour_ars=18000, setup_time_min=15, labor_percent=35),
    dict(material=mats["Inoxidable AISI 304 2mm"], cut_speed_mm_min=2800, machine_cost_per_hour_ars=22000, setup_time_min=12, labor_percent=40),
    dict(material=mats["Inoxidable AISI 304 3mm"], cut_speed_mm_min=1800, machine_cost_per_hour_ars=22000, setup_time_min=15, labor_percent=40),
]
machine_configs = {}
for c in configs_data:
    mat = c.pop("material")
    obj = MachineConfig(material_id=mat.id, **c)
    db.add(obj)
    db.flush()
    machine_configs[mat.id] = obj
db.commit()

# ─── 4. Clientes ─────────────────────────────────────────────────────────────
print("Cargando clientes...")
clients_data = [
    dict(name="Talleres Rodríguez SA",      cuit_cuil="30-65432100-9", phone="+54 11 4521-3300", email="compras@talleresrodriguez.com.ar", address="Ruta 8 km 42, Luján, Buenos Aires"),
    dict(name="Construcciones Villalba",    cuit_cuil="20-28374650-5", phone="+54 351 477-2200", email="villalba.obra@gmail.com",           address="Calle Los Aromos 234, Córdoba"),
    dict(name="Industrias Norpatagónica",   cuit_cuil="30-70123456-1", phone="+54 299 443-8800", email="compras@norpatagonicaind.com.ar",   address="Parque Industrial, Neuquén"),
    dict(name="Agro Mecánica El Pampero",   cuit_cuil="20-31456789-2", phone="+54 2324 45-6700", email="elmampero.mec@hotmail.com",         address="Av. San Martín 890, Junín, Buenos Aires"),
    dict(name="Mantenimiento Industrial MR",cuit_cuil="30-69871234-7", phone="+54 341 480-5500", email="mr.mantenimiento@gmail.com",        address="Av. Circunvalación 3400, Rosario"),
]
clients = []
for c in clients_data:
    obj = Client(**c)
    db.add(obj)
    db.flush()
    clients.append(obj)
db.commit()

# ─── 5. Piezas con DXF ───────────────────────────────────────────────────────
print("Cargando piezas y generando previews...")

DXF_DIR = Path("data/dxf")
pieces_data = [
    dict(name="Bracket soporte 100x50",    dxf_file="bracket_100x50.dxf",  material=mats["Acero SAE 1010 3mm"],        description="Soporte de montaje estándar"),
    dict(name="Panel lateral 200x120",     dxf_file="panel_200x120.dxf",   material=mats["Acero SAE 1010 5mm"],        description="Panel de carcasa con ranura central"),
    dict(name="Disco centrífugo D80",      dxf_file="disco_d80.dxf",       material=mats["Inoxidable AISI 304 3mm"],   description="Disco para acople de bomba"),
    dict(name="Bracket soporte 100x50 SS", dxf_file="bracket_100x50.dxf",  material=mats["Inoxidable AISI 304 2mm"],   description="Versión inoxidable del soporte"),
    dict(name="Panel reforzado 200x120",   dxf_file="panel_200x120.dxf",   material=mats["Acero SAE 1010 10mm"],       description="Panel estructural reforzado"),
]

pieces = []
for p in pieces_data:
    dxf_path = DXF_DIR / p["dxf_file"]
    mat = p["material"]

    obj = Piece(
        name=p["name"],
        description=p["description"],
        material_id=mat.id,
    )
    db.add(obj)
    db.flush()

    if dxf_path.exists():
        # Análisis DXF
        length_cut_mm, area_mm2 = analyze_dxf(str(dxf_path))
        # Guardar DXF con nombre por pieza
        import shutil
        dest_dxf = DXF_DIR / f"piece_{obj.id}.dxf"
        shutil.copy(dxf_path, dest_dxf)
        obj.dxf_path = str(dest_dxf)
        obj.length_cut_mm = length_cut_mm
        obj.area_mm2 = area_mm2

        # Preview PNG
        try:
            preview_path = DXF_DIR / f"piece_{obj.id}_preview.png"
            generate_dxf_preview(str(dest_dxf), str(preview_path))
            obj.preview_path = str(preview_path)
            print(f"  Preview generada: {obj.name}")
        except Exception as e:
            print(f"  Preview fallida para {obj.name}: {e}")

    db.commit()
    db.refresh(obj)
    pieces.append(obj)

# ─── 6. Cotizaciones ─────────────────────────────────────────────────────────
print("Cargando cotizaciones...")

now = datetime.now()

quotations_data = [
    dict(
        number="COT-2026-001",
        client=clients[0],  # Talleres Rodríguez
        issue_date=now - timedelta(days=5),
        due_date=now + timedelta(days=2),
        currency="ARS",
        exchange_rate=None,
        notes="Urgente para línea de producción.",
        items=[
            dict(piece=pieces[0], material=mats["Acero SAE 1010 3mm"],  quantity=20, margin_percent=25),
            dict(piece=pieces[1], material=mats["Acero SAE 1010 5mm"],  quantity=10, margin_percent=25),
        ],
    ),
    dict(
        number="COT-2026-002",
        client=clients[1],  # Construcciones Villalba
        issue_date=now - timedelta(days=2),
        due_date=now + timedelta(days=5),
        currency="ARS",
        exchange_rate=None,
        notes=None,
        items=[
            dict(piece=pieces[2], material=mats["Inoxidable AISI 304 3mm"], quantity=4, margin_percent=30),
            dict(piece=pieces[3], material=mats["Inoxidable AISI 304 2mm"], quantity=8, margin_percent=30),
        ],
    ),
    dict(
        number="COT-2026-003",
        client=clients[2],  # Industrias Norpatagónica
        issue_date=now,
        due_date=now + timedelta(days=7),
        currency="USD",
        exchange_rate=1180.0,
        notes="Cotización en USD según acuerdo previo. Tipo de cambio fijado al día de emisión.",
        items=[
            dict(piece=pieces[4], material=mats["Acero SAE 1010 10mm"], quantity=6,  margin_percent=35),
            dict(piece=pieces[0], material=mats["Acero SAE 1010 3mm"],  quantity=50, margin_percent=20),
            dict(piece=pieces[2], material=mats["Inoxidable AISI 304 3mm"], quantity=3, margin_percent=40),
        ],
    ),
]

for qd in quotations_data:
    client = qd["client"]
    q = Quotation(
        number=qd["number"],
        client_id=client.id,
        issue_date=qd["issue_date"],
        due_date=qd["due_date"],
        currency=qd["currency"],
        exchange_rate=qd["exchange_rate"],
        notes=qd["notes"],
        status="draft",
        total_ars=0.0,
        total_usd=0.0,
    )
    db.add(q)
    db.flush()

    for item_data in qd["items"]:
        item = QuotationItem(
            quotation_id=q.id,
            piece_id=item_data["piece"].id,
            material_id=item_data["material"].id,
            quantity=item_data["quantity"],
            margin_percent=item_data["margin_percent"],
            cost_material_ars=0,
            cost_machine_ars=0,
            cost_labor_ars=0,
            unit_price_ars=0,
            total_price_ars=0,
        )
        db.add(item)
        db.flush()
        calculate_quotation_item(db, item)

    db.refresh(q)
    print(f"  {q.number} — Total ARS: ${q.total_ars:,.0f}")

db.commit()

# ─── 7. Generar PDFs ─────────────────────────────────────────────────────────
print("\nGenerando PDFs...")
from app.services.pdf_generator import generate_quotation_pdf

all_quotations = db.query(Quotation).all()
for q in all_quotations:
    path = generate_quotation_pdf(db, q.id, output_dir=Path("data/pdfs"))
    print(f"  PDF: {path}")

db.close()
print("\nListo. Datos cargados correctamente.")
