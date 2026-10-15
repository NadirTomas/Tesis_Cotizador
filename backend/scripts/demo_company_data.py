"""Datos ficticios de demostración para scripts/seed_demo_company.py.

Todo lo de acá es inventado: razones sociales, CUIT (bloque 30-0000xxxx, que no
corresponde a ningún contribuyente), teléfonos 555-01xx y correos @example.com.
Los precios son de demostración, NO precios de mercado.

Las piezas se generan como DXF reales (ezdxf) con entidades que el análisis del
sistema entiende (LWPOLYLINE cerrada + CIRCLE); no se usan arcos/bulge porque
analyze_dxf/extract_piece_polygon no los interpretan.
"""
from __future__ import annotations

import io
import math

import ezdxf

# ── Clientes ──────────────────────────────────────────────────────────────────
# (nombre, cuit, teléfono, email, dirección, notas)
CLIENTS = [
    ("Metalúrgica del Centro S.R.L.", "30-00000101-4", "+54 351 555-0101", "compras@metalurgicadelcentro.example.com", "Av. Colón 1250, Córdoba", "Cliente histórico. Paga a 30 días."),
    ("Taller Industrial Norte", "30-00000102-2", "+54 381 555-0102", "contacto@tallernorte.example.com", "Ruta 9 km 1310, Tucumán", "Retira en el taller."),
    ("Estructuras del Sur S.A.", "30-00000103-0", "+54 291 555-0103", "obras@estructurasdelsur.example.com", "Parque Industrial, Bahía Blanca", "Proyectos de obra, pedidos grandes."),
    ("Aceros Córdoba S.A.", "30-00000104-9", "+54 351 555-0104", "ventas@acerosco.example.com", "Av. Circunvalación 4500, Córdoba", None),
    ("Fabricaciones Delta S.R.L.", "30-00000105-7", "+54 11 5550-0105", "pedidos@fabricacionesdelta.example.com", "Zárate, Buenos Aires", "Series repetitivas de piezas chicas."),
    ("Industrias Horizonte S.A.", "30-00000106-5", "+54 341 555-0106", "compras@horizonte.example.com", "San Lorenzo, Santa Fe", "Entregas parciales programadas."),
    ("Mecanizados San Martín", "30-00000107-3", "+54 261 555-0107", "info@mecanizadossm.example.com", "Godoy Cruz, Mendoza", None),
    ("Carpintería Metálica Los Andes", "30-00000108-1", "+54 261 555-0108", "losandes@example.com", "Luján de Cuyo, Mendoza", None),
    ("Agroindustrial Pampeana S.A.", "30-00000109-0", "+54 2302 55-0109", "mantenimiento@agropampeana.example.com", "General Pico, La Pampa", "Repuestos para maquinaria agrícola."),
    ("Equipos Frigoríficos del Litoral", "30-00000110-4", "+54 343 555-0110", "proyectos@frigolitoral.example.com", "Paraná, Entre Ríos", "Trabaja principalmente en acero inoxidable."),
    ("Talleres Unidos Rosario", "30-00000111-2", "+54 341 555-0111", None, "Av. Pellegrini 2210, Rosario", "Pide por teléfono."),
    ("Cerrajería y Portones Belgrano", None, "+54 11 5550-0112", "belgrano.portones@example.com", "Belgrano, CABA", "Consumidor final / monotributo."),
    ("Montajes Industriales Patagonia", "30-00000113-8", "+54 299 555-0113", "logistica@montajespatagonia.example.com", "Neuquén Capital", "Requiere remito firmado en cada entrega."),
    ("Silos y Tolvas Cuyo S.R.L.", "30-00000114-6", "+54 264 555-0114", "ventas@silosycuyo.example.com", "San Juan Capital", None),
    ("Maquinarias Agrícolas Ferreyra", "30-00000115-4", "+54 3564 55-0115", "taller@maqferreyra.example.com", "San Francisco, Córdoba", None),
    ("Muebles Metálicos Urbanos", "30-00000116-2", "+54 11 5550-0116", "diseno@mmurbanos.example.com", "San Martín, Buenos Aires", "Mobiliario de diseño en chapa."),
    ("Gastronomía Inox S.R.L.", "30-00000117-0", "+54 351 555-0117", "cocinas@gastroinox.example.com", "Nueva Córdoba, Córdoba", "Mesadas y campanas en inoxidable."),
    ("Construcciones Metálicas Atlántica", "30-00000118-9", "+54 223 555-0118", "obras@cmatlantica.example.com", "Mar del Plata, Buenos Aires", None),
    ("Herrería Artística Rivadavia", None, "+54 11 5550-0119", None, "Rivadavia 3300, CABA", "Pieza decorativa, pocos cortes."),
    ("Transportes y Acoples Mediterráneo", "30-00000120-0", "+54 351 555-0120", "repuestos@acoplesmed.example.com", "Villa María, Córdoba", None),
]

# ── Materiales y configuración de máquina ─────────────────────────────────────
# key: (nombre, tipo, aleación, espesor, ancho, alto, costo chapa ARS [ficticio],
#       velocidad mm/min, costo máquina ARS/h, setup min, % mano de obra, kerf, separación)
MATERIALS = {
    "acero_1_5": ("Acero al carbono SAE 1010 – 1,5 mm", "Acero al carbono", "SAE 1010", 1.5, 1250, 2500, 55000, 12000, 38000, 8, 30, 0.15, 3),
    "acero_2": ("Acero al carbono SAE 1010 – 2 mm", "Acero al carbono", "SAE 1010", 2.0, 1250, 2500, 73000, 9000, 38000, 8, 30, 0.15, 3),
    "acero_3": ("Acero al carbono SAE 1010 – 3 mm", "Acero al carbono", "SAE 1010", 3.0, 1500, 3000, 158000, 5500, 42000, 10, 30, 0.20, 4),
    "acero_4_75": ("Acero al carbono SAE 1010 – 4,75 mm (3/16\")", "Acero al carbono", "SAE 1010", 4.75, 1500, 3000, 250000, 2800, 46000, 12, 30, 0.25, 5),
    "acero_6_35": ("Acero al carbono SAE 1010 – 6,35 mm (1/4\")", "Acero al carbono", "SAE 1010", 6.35, 1500, 3000, 335000, 1600, 52000, 12, 30, 0.30, 6),
    "inox_1_5": ("Acero inoxidable AISI 304 – 1,5 mm", "Acero inoxidable", "AISI 304", 1.5, 1250, 2500, 210000, 7000, 40000, 10, 30, 0.15, 3),
    "inox_2": ("Acero inoxidable AISI 304 – 2 mm", "Acero inoxidable", "AISI 304", 2.0, 1250, 2500, 280000, 5000, 40000, 10, 30, 0.18, 3),
    "inox_3": ("Acero inoxidable AISI 304 – 3 mm", "Acero inoxidable", "AISI 304", 3.0, 1500, 3000, 640000, 2600, 44000, 12, 30, 0.22, 4),
    "alu_2": ("Aluminio 5052 – 2 mm", "Aluminio", "5052-H32", 2.0, 1000, 2000, 95000, 6500, 40000, 10, 30, 0.20, 3),
    "galv_1_25": ("Chapa galvanizada – 1,25 mm", "Chapa galvanizada", "Z275", 1.25, 1250, 2500, 62000, 11000, 38000, 8, 30, 0.15, 3),
}

# ── Piezas ────────────────────────────────────────────────────────────────────
# key: (nombre, descripción, material, spec_de_geometría)
# spec: dict con "kind" y parámetros (mm). Ver build_dxf().
def _corners(w, h, inset, d):
    return [(inset, inset, d), (w - inset, inset, d), (inset, h - inset, d), (w - inset, h - inset, d)]


def _row(n, x0, x1, y, d):
    step = (x1 - x0) / (n - 1)
    return [(x0 + i * step, y, d) for i in range(n)]


PIECES = {
    "p01": ("Soporte de motor", "Base de apoyo para motor eléctrico de 4 kW, 4 agujeros de fijación y ranura central de ventilación.", "acero_3",
            {"kind": "plate", "w": 220, "h": 160, "r": 8, "holes": _corners(220, 160, 20, 12), "slots": [(110, 80, 90, 16)]}),
    "p02": ("Placa de montaje", "Placa de montaje general 300 x 200 con 4 agujeros pasantes.", "acero_2",
            {"kind": "plate", "w": 300, "h": 200, "r": 0, "holes": _corners(300, 200, 25, 10)}),
    "p03": ("Base estructural", "Base para columna metálica, 6 agujeros de anclaje.", "acero_6_35",
            {"kind": "plate", "w": 500, "h": 350, "r": 0, "holes": _corners(500, 350, 30, 18) + [(250, 30, 18), (250, 320, 18)]}),
    "p04": ("Refuerzo lateral", "Cartela triangular de refuerzo para estructura soldada.", "acero_4_75",
            {"kind": "gusset", "a": 180, "b": 180, "hole": (45, 45, 14)}),
    "p05": ("Brida metálica DN50", "Brida de cañería DN50, 4 agujeros en circunferencia primitiva.", "acero_6_35",
            {"kind": "flange", "od": 165, "id": 62, "n": 4, "pcd": 125, "bolt": 18}),
    "p06": ("Escuadra industrial", "Escuadra de unión en L (desarrollo plano), 2 agujeros por pata.", "acero_3",
            {"kind": "lshape", "a": 150, "b": 150, "t": 45, "holes": [(22, 30, 9), (22, 120, 9), (30, 22, 9), (120, 22, 9)]}),
    "p07": ("Tapa de gabinete", "Tapa frontal de gabinete eléctrico con 4 fijaciones y rejilla de ventilación.", "acero_1_5",
            {"kind": "plate", "w": 400, "h": 300, "r": 10, "holes": _corners(400, 300, 15, 6), "slots": [(200, 110 + i * 24, 140, 8) for i in range(4)]}),
    "p08": ("Soporte de rodamiento", "Soporte para rodamiento con agujero central Ø45 y 2 fijaciones.", "acero_4_75",
            {"kind": "plate", "w": 120, "h": 100, "r": 12, "holes": [(60, 50, 45), (14, 50, 9), (106, 50, 9)]}),
    "p09": ("Brida ciega Ø200", "Brida ciega de 8 agujeros para tapa de recipiente.", "acero_4_75",
            {"kind": "flange", "od": 200, "id": 0, "n": 8, "pcd": 160, "bolt": 14}),
    "p10": ("Arandela especial", "Arandela de gran diámetro para unión abulonada.", "acero_3",
            {"kind": "flange", "od": 80, "id": 30, "n": 0, "pcd": 0, "bolt": 0}),
    "p11": ("Bandeja de acero inoxidable", "Bandeja plana para cocina industrial, 4 agujeros de fijación.", "inox_1_5",
            {"kind": "plate", "w": 350, "h": 250, "r": 15, "holes": _corners(350, 250, 18, 8)}),
    "p12": ("Panel frontal inoxidable", "Panel frontal de equipo con ranura de acceso.", "inox_2",
            {"kind": "plate", "w": 500, "h": 300, "r": 6, "holes": _corners(500, 300, 15, 7), "slots": [(250, 150, 220, 30)]}),
    "p13": ("Soporte de campana", "Cartela de soporte para campana extractora.", "inox_2",
            {"kind": "gusset", "a": 220, "b": 140, "hole": (40, 40, 12)}),
    "p14": ("Placa base inoxidable", "Placa base de columna de mesada, 4 agujeros Ø12.", "inox_3",
            {"kind": "plate", "w": 250, "h": 250, "r": 0, "holes": _corners(250, 250, 30, 12)}),
    "p15": ("Brida inoxidable DN40", "Brida de acero inoxidable para línea de proceso.", "inox_3",
            {"kind": "flange", "od": 150, "id": 50, "n": 4, "pcd": 110, "bolt": 16}),
    "p16": ("Tapa de registro", "Tapa circular de registro con 6 fijaciones.", "alu_2",
            {"kind": "flange", "od": 250, "id": 0, "n": 6, "pcd": 220, "bolt": 6}),
    "p17": ("Panel de aluminio ranurado", "Panel decorativo con 3 ranuras largas.", "alu_2",
            {"kind": "plate", "w": 600, "h": 400, "r": 20, "holes": [], "slots": [(300, 110 + i * 90, 400, 22) for i in range(3)]}),
    "p18": ("Perfil U desplegado", "Desarrollo plano de perfil U con muescas de plegado.", "galv_1_25",
            {"kind": "unotch", "w": 500, "h": 120, "notch": 25}),
    "p19": ("Tapa de conducto", "Tapa cuadrada para conducto de ventilación.", "galv_1_25",
            {"kind": "plate", "w": 300, "h": 300, "r": 0, "holes": _corners(300, 300, 15, 6)}),
    "p20": ("Chasis lateral", "Lateral de chasis de equipo con ranuras de ventilación.", "acero_1_5",
            {"kind": "plate", "w": 450, "h": 350, "r": 10, "holes": _corners(450, 350, 15, 8), "slots": [(225, 100 + i * 50, 200, 12) for i in range(4)]}),
    "p21": ("Bisagra industrial", "Bisagra plana de 2 agujeros para puertas de gabinete.", "acero_3",
            {"kind": "plate", "w": 100, "h": 60, "r": 8, "holes": [(20, 30, 10), (80, 30, 10)]}),
    "p22": ("Soporte de estantería", "Escuadra de soporte para estantería metálica.", "acero_2",
            {"kind": "lshape", "a": 200, "b": 120, "t": 40, "holes": [(20, 60, 8), (20, 100, 8), (100, 20, 8)]}),
    "p23": ("Gancho de izaje", "Placa de izaje con agujero principal Ø50.", "acero_6_35",
            {"kind": "plate", "w": 160, "h": 120, "r": 25, "holes": [(80, 60, 50)]}),
    "p24": ("Escudo protector", "Protector de transmisión, 4 fijaciones.", "acero_2",
            {"kind": "plate", "w": 500, "h": 250, "r": 12, "holes": _corners(500, 250, 18, 9)}),
    "p25": ("Placa de anclaje", "Placa de anclaje para columna, 4 agujeros Ø16.", "acero_4_75",
            {"kind": "plate", "w": 200, "h": 200, "r": 0, "holes": _corners(200, 200, 25, 16)}),
    "p26": ("Soporte de cañería", "Abrazadera plana de soporte de cañería.", "acero_2",
            {"kind": "plate", "w": 140, "h": 50, "r": 10, "holes": [(20, 25, 9), (120, 25, 9)]}),
    "p27": ("Rejilla de ventilación", "Rejilla con 8 ranuras para gabinete.", "acero_1_5",
            {"kind": "plate", "w": 300, "h": 200, "r": 6, "holes": [], "slots": [(150, 25 + i * 21, 200, 9) for i in range(8)]}),
    "p28": ("Separador Ø60", "Disco separador con agujero central Ø20.", "acero_3",
            {"kind": "flange", "od": 60, "id": 20, "n": 0, "pcd": 0, "bolt": 0}),
    "p29": ("Pletina de unión", "Pletina de empalme con 6 agujeros alineados.", "acero_3",
            {"kind": "plate", "w": 400, "h": 60, "r": 0, "holes": _row(6, 30, 370, 30, 10)}),
    "p30": ("Marco de puerta de gabinete", "Marco con ventana central 400 x 300.", "acero_1_5",
            {"kind": "plate", "w": 500, "h": 400, "r": 10, "holes": _corners(500, 400, 12, 6), "window": (50, 50, 450, 350)}),
}

# ── Stock inicial ─────────────────────────────────────────────────────────────
# material -> (chapas completas, [remanentes (ancho, alto)])
STOCK = {
    "acero_1_5": (3, [(600, 400)]),
    "acero_2": (5, [(800, 500), (1000, 300), (420, 420)]),
    "acero_3": (10, [(1200, 600)]),
    "acero_4_75": (3, [(700, 700)]),
    "acero_6_35": (2, []),
    "inox_1_5": (3, [(500, 500)]),
    "inox_2": (3, [(900, 400)]),
    "inox_3": (2, []),
    "alu_2": (3, [(600, 600)]),
    "galv_1_25": (3, []),
}
# Remanente manual que se descarta (queda DISCARDED con su movimiento)
STOCK_DISCARD = ("acero_2", (300, 250))

# ── Cotizaciones ──────────────────────────────────────────────────────────────
# Pasos del flujo (d = días después de la fecha de emisión):
#   ("send", d) ("accept", d) ("cancel", d)
#   ("reserve", item, d) ("cut", item, d) ("release", item, d)
#   ("dn", clave, [(item, cantidad)], d)          crea el remito en borrador
#   ("issue", clave, d)  ("void", clave, d, motivo)
# Q(clave, cliente, hace_dias, moneda, tipo_cambio, [(pieza, cantidad, margen%)], escenario, flujo)
def Q(key, client, days_ago, items, flow, *, cur="ARS", fx=None, scenario=None, note=None):
    return dict(key=key, client=client, days_ago=days_ago, cur=cur, fx=fx, items=items, flow=flow, scenario=scenario, note=note)


QUOTATIONS = [
    Q("Q01", 0, 138, [("p02", 20, 25), ("p06", 40, 25)],
      [("send", 1), ("accept", 3), ("reserve", 0, 4), ("reserve", 1, 5), ("cut", 0, 6), ("cut", 1, 7),
       ("dn", "D01", [(0, 20), (1, 40)], 10), ("issue", "D01", 10)],
      note="Entrega total en un solo remito."),
    Q("Q02", 1, 126, [("p01", 10, 30)],
      [("send", 1), ("accept", 2), ("reserve", 0, 3), ("cut", 0, 5),
       ("dn", "D02", [(0, 6)], 8), ("issue", "D02", 8), ("dn", "D03", [(0, 4)], 14), ("issue", "D03", 14)],
      note="Entrega total en dos remitos."),
    Q("Q03", 2, 120, [("p03", 4, 20), ("p25", 8, 20)],
      [("send", 1), ("accept", 4), ("cancel", 9)], note="Aceptada y luego cancelada por el cliente antes de producir."),
    Q("Q04", 3, 112, [("p05", 12, 30)], [("send", 1)], note="Enviada sin respuesta del cliente."),
    Q("Q05", 5, 105, [("p11", 15, 28), ("p12", 6, 28)], [
        ("send", 1), ("accept", 3), ("reserve", 0, 4), ("reserve", 1, 4), ("cut", 0, 7), ("cut", 1, 8),
        ("dn", "D04", [(0, 15)], 12), ("issue", "D04", 12)],
      cur="USD", fx=1210.0, note="Dos ítems cortados; solo uno entregado."),
    Q("Q06", 4, 98, [("p13", 10, 25)], [("send", 2), ("cancel", 12)], note="Rechazada por el cliente (precio)."),
    Q("Q07", 6, 92, [("p10", 50, 25), ("p28", 80, 25), ("p29", 30, 25)], [
        ("send", 1), ("accept", 2), ("reserve", 0, 3), ("reserve", 1, 3), ("reserve", 2, 3),
        ("cut", 0, 5), ("cut", 1, 5), ("cut", 2, 6)], note="Todo cortado, listo para entregar (sin remitos)."),
    Q("Q08", 7, 86, [("p20", 25, 22)], [("send", 1), ("accept", 2), ("reserve", 0, 3)],
      note="Aceptada, material reservado, corte pendiente."),
    Q("Q09", 8, 80, [("p14", 6, 30), ("p15", 10, 30)], [("send", 1)]),
    Q("Q10", 9, 75, [("p16", 30, 25), ("p17", 12, 25)], [
        ("send", 1), ("accept", 4), ("reserve", 0, 5), ("cut", 0, 8), ("dn", "D05", [(0, 30)], 11), ("issue", "D05", 11)],
      cur="USD", fx=1285.0, note="El panel (ítem 2) todavía no se cortó."),
    Q("Q11", 10, 70, [("p18", 40, 22), ("p19", 40, 22)], [
        ("send", 1), ("accept", 3), ("reserve", 0, 4), ("reserve", 1, 4), ("release", 0, 6), ("cancel", 9)],
      note="Aceptada y cancelada: reservas liberadas."),
    Q("Q12", 11, 66, [("p07", 30, 25)], [("send", 1)]),
    Q("Q13", 12, 62, [("p24", 12, 25), ("p26", 60, 25)], [
        ("send", 1), ("accept", 2), ("reserve", 0, 3), ("cut", 0, 5), ("dn", "D06", [(0, 12)], 7)],
      note="Remito en borrador listo para emitir (corte confirmado)."),
    Q("Q14", 13, 58, [("p08", 16, 30)], [
        ("send", 1), ("accept", 3), ("reserve", 0, 4), ("cut", 0, 6), ("dn", "D07", [(0, 16)], 9), ("issue", "D07", 9),
        ("void", "D07", 12, "Cantidad mal cargada en el remito; se rehace la entrega.")],
      note="Remito anulado: las 16 unidades vuelven a estar pendientes."),
    Q("Q15", 14, 52, [("p23", 10, 30), ("p05", 8, 30)], [("send", 1), ("cancel", 5)], cur="USD", fx=1330.0,
      note="Cancelada tras el envío."),
    Q("Q16", 15, 48, [("p22", 45, 25)], [("cancel", 3)], note="Borrador descartado."),
    Q("Q17", 16, 45, [("p29", 60, 22)], [("send", 1), ("accept", 2), ("reserve", 0, 3)],
      note="Material reservado, esperando el corte."),
    Q("Q18", 17, 41, [("p27", 20, 25)], [
        ("send", 1), ("accept", 2), ("reserve", 0, 3), ("cut", 0, 4), ("dn", "D08", [(0, 10)], 6)],
      note="Remito parcial en borrador (10 de 20)."),
    Q("Q19", 4, 36, [("p21", 100, 20)], [
        ("send", 1), ("accept", 2), ("reserve", 0, 3), ("cut", 0, 5),
        ("dn", "D09", [(0, 40)], 8), ("issue", "D09", 8), ("dn", "D10", [(0, 35)], 14), ("issue", "D10", 14)],
      scenario="D", note="ESCENARIO D: 100 unidades, remitos de 40 y 35, quedan 25 pendientes."),
    Q("Q20", 5, 29, [("p09", 60, 28)], [
        ("send", 1), ("accept", 2), ("reserve", 0, 3), ("cut", 0, 5),
        ("dn", "D11", [(0, 30)], 8), ("issue", "D11", 8),
        ("void", "D11", 10, "Remito emitido por error: la entrega se reprograma."),
        ("dn", "D12", [(0, 20)], 12), ("issue", "D12", 12)],
      scenario="E", note="ESCENARIO E: un remito anulado (30 un) y otro emitido (20 un); 40 pendientes."),
    Q("Q21", 0, 24, [("p01", 12, 25), ("p02", 30, 25), ("p29", 40, 25), ("p06", 25, 25)], [
        ("send", 1), ("accept", 2), ("reserve", 0, 3), ("reserve", 1, 3), ("cut", 0, 5), ("cut", 1, 5),
        ("reserve", 2, 6), ("dn", "D13", [(0, 12)], 8), ("issue", "D13", 8), ("dn", "D14", [(2, 20)], 9)],
      scenario="C", note="ESCENARIO C: ítems 1-2 cortados, ítem 3 reservado sin cortar, ítem 4 sin reserva."),
    Q("Q22", 2, 6, [("p03", 6, 22), ("p25", 12, 22)], [("send", 2)], scenario="A",
      note="ESCENARIO A: enviada, esperando respuesta."),
    Q("Q23", 3, 12, [("p05", 20, 25), ("p09", 10, 25)], [("send", 1), ("accept", 3)], cur="USD", fx=1420.0,
      scenario="B", note="ESCENARIO B: aceptada, sin reservas ni cortes."),
    Q("Q24", 18, 16, [("p04", 30, 25)], [], note="Borrador."),
    Q("Q25", 19, 9, [("p12", 8, 30), ("p13", 8, 30)], [], note="Borrador."),
    Q("Q26", 1, 5, [("p30", 10, 25)], [], note="Borrador."),
    Q("Q27", 6, 3, [("p27", 15, 25), ("p07", 20, 25)], [], note="Borrador."),
    Q("Q28", 9, 2, [("p17", 20, 28)], [], cur="USD", fx=1455.0, note="Borrador en dólares."),
    Q("Q29", 12, 10, [("p26", 100, 22), ("p24", 20, 22)], [("send", 1)]),
    Q("Q30", 14, 7, [("p16", 40, 25)], [("send", 1)]),
]
assert len(QUOTATIONS) == 30


# ── Geometría DXF ─────────────────────────────────────────────────────────────
def _rounded_rect_points(w, h, r, n=6):
    if r <= 0:
        return [(0, 0), (w, 0), (w, h), (0, h)]
    pts = []
    for cx, cy, a0 in ((w - r, r, -90), (w - r, h - r, 0), (r, h - r, 90), (r, r, 180)):
        for i in range(n + 1):
            a = math.radians(a0 + 90 * i / n)
            pts.append((round(cx + r * math.cos(a), 3), round(cy + r * math.sin(a), 3)))
    return pts


def _slot_points(cx, cy, length, width, n=6):
    r = width / 2
    half = max(length / 2 - r, 0.0)
    pts = []
    for i in range(n + 1):
        a = math.radians(-90 + 180 * i / n)
        pts.append((round(cx + half + r * math.cos(a), 3), round(cy + r * math.sin(a), 3)))
    for i in range(n + 1):
        a = math.radians(90 + 180 * i / n)
        pts.append((round(cx - half + r * math.cos(a), 3), round(cy + r * math.sin(a), 3)))
    return pts


def build_dxf(spec: dict) -> bytes:
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    kind = spec["kind"]
    if kind == "plate":
        msp.add_lwpolyline(_rounded_rect_points(spec["w"], spec["h"], spec.get("r", 0)), close=True)
        for x, y, d in spec.get("holes", []):
            msp.add_circle((x, y), radius=d / 2)
        for cx, cy, length, width in spec.get("slots", []):
            msp.add_lwpolyline(_slot_points(cx, cy, length, width), close=True)
        if "window" in spec:
            x0, y0, x1, y1 = spec["window"]
            msp.add_lwpolyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], close=True)
    elif kind == "flange":
        c = spec["od"] / 2
        msp.add_circle((c, c), radius=c)
        if spec["id"]:
            msp.add_circle((c, c), radius=spec["id"] / 2)
        for i in range(spec["n"]):
            a = 2 * math.pi * i / spec["n"]
            msp.add_circle((round(c + spec["pcd"] / 2 * math.cos(a), 3), round(c + spec["pcd"] / 2 * math.sin(a), 3)), radius=spec["bolt"] / 2)
    elif kind == "lshape":
        a, b, t = spec["a"], spec["b"], spec["t"]
        msp.add_lwpolyline([(0, 0), (a, 0), (a, t), (t, t), (t, b), (0, b)], close=True)
        for x, y, d in spec["holes"]:
            # solo agujeros que caen dentro de las patas de la L
            if (y <= t and x <= a) or (x <= t and y <= b):
                msp.add_circle((x, y), radius=d / 2)
    elif kind == "gusset":
        a, b = spec["a"], spec["b"]
        msp.add_lwpolyline([(0, 0), (a, 0), (0, b)], close=True)
        x, y, d = spec["hole"]
        msp.add_circle((x, y), radius=d / 2)
    elif kind == "unotch":
        w, h, n = spec["w"], spec["h"], spec["notch"]
        msp.add_lwpolyline([(0, 0), (w, 0), (w, h), (w - 60, h), (w - 60, h - n), (60, h - n), (60, h), (0, h)], close=True)
    else:
        raise ValueError(f"Tipo de geometría desconocido: {kind}")
    buf = io.StringIO()
    doc.write(buf)
    return buf.getvalue().encode("utf-8")
