"""Reemplaza los datos operativos de UNA empresa por un set ficticio de demostración.

Herramienta administrativa, de ejecución explícita: nunca se invoca al arrancar la
aplicación ni desde una migración Alembic. Por defecto hace un DRY-RUN (valida el
dataset, inspecciona la base en modo lectura y muestra un resumen); recién con
--apply borra y vuelve a poblar.

Qué toca (solo filas con company_id = --company-id):
    borra:  delivery_note_items, delivery_notes, stock_movements, stock_reservations,
            stock_sheets, quotation_events, quotation_items, quotations,
            machine_configs, pieces, materials, clients, document_sequences
    crea:   todo lo anterior otra vez, usando los endpoints reales de la API en proceso
            (TestClient), de modo que cálculos, estados, reservas, cortes y remitos
            pasan por la lógica de negocio real y no por INSERT directos.
    NO toca: companies, users, company_members (usuarios, roles, credenciales),
            otras empresas, esquema, secuencias globales (*_id_seq).

Las fechas históricas se logran parcheando el reloj del proceso (core.clock y el
reloj de remitos) durante cada paso y re-fechando después created_at/updated_at de las
filas recién creadas de ESTA empresa. No se modifica ninguna validación ni código de
producción.

Uso (rehearsal, base temporal local):
    set DATABASE_URL=postgresql://postgres:test@localhost:55433/restore_test
    set SECRET_KEY=lo-que-sea-para-el-ensayo
    python -m scripts.seed_demo_company --company-id 1 --expect-company-name TesisCervantes
    python -m scripts.seed_demo_company --company-id 1 --expect-company-name TesisCervantes --apply

Uso (base remota, p. ej. Railway; exige --allow-remote y el token de confirmación):
    railway run --service Postgres python -m scripts.seed_demo_company ^
        --db-env-var DATABASE_PUBLIC_URL --company-id 1 --expect-company-name TesisCervantes ^
        --apply --allow-remote --confirm-token BORRAR-Y-REEMPLAZAR-EMPRESA-1
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import logging
import os
import sys
import tempfile
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from scripts import demo_company_data as data  # noqa: E402

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
SEED_VERSION = 1


class SeedError(RuntimeError):
    pass


def _fail(msg: str) -> None:
    raise SeedError(msg)


# ── Cronograma (puro, sin base de datos) ──────────────────────────────────────
def ordered_quotations() -> list[dict]:
    return sorted(data.QUOTATIONS, key=lambda q: -q["days_ago"])


def step_time(anchor: date, q: dict, offset_days: int, slot: int) -> datetime:
    issue = anchor - timedelta(days=q["days_ago"])
    return datetime.combine(issue + timedelta(days=offset_days), datetime.min.time()) + timedelta(hours=9, minutes=30 + 11 * slot)


def schedule(anchor: date, q: dict) -> list[tuple[tuple, datetime]]:
    """Cada paso del flujo con su instante histórico (create=0, luego los pasos del flujo)."""
    day_index = {"send": 1, "accept": 1, "cancel": 1, "reserve": 2, "cut": 2, "release": 2,
                 "dn": 3, "issue": 2, "void": 2}
    return [
        (step, step_time(anchor, q, step[day_index[step[0]]], slot))
        for slot, step in enumerate(q["flow"], start=1)
    ]


# ── Validación del dataset (sin base de datos) ────────────────────────────────
def validate_dataset(anchor: date, now: datetime | None = None) -> dict:
    from shapely.geometry import box

    from app.services.dxf_analysis import analyze_dxf, extract_piece_polygon

    now = now or datetime.now()
    problems: list[str] = []
    pieces_info: dict[str, dict] = {}

    for key, (name, desc, mat_key, spec) in data.PIECES.items():
        if mat_key not in data.MATERIALS:
            problems.append(f"{key}: material inexistente {mat_key}")
            continue
        raw = data.build_dxf(spec)
        with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as tmp:
            tmp.write(raw)
            path = tmp.name
        try:
            length, area = analyze_dxf(path)
            poly = extract_piece_polygon(path)
        except Exception as exc:  # pragma: no cover - dataset roto
            problems.append(f"{key}: DXF inválido ({exc})")
            continue
        finally:
            Path(path).unlink(missing_ok=True)
        if not poly.is_valid or poly.area <= 0 or area <= 0 or length <= 0:
            problems.append(f"{key}: geometría inválida")
        minx, miny, maxx, maxy = poly.bounds
        w, h = maxx - minx, maxy - miny
        m = data.MATERIALS[mat_key]
        sheet = box(0, 0, m[4], m[5])
        if not (max(w, h) <= max(m[4], m[5]) - 20 and min(w, h) <= min(m[4], m[5]) - 20):
            problems.append(f"{key}: no entra en la chapa de {mat_key}")
        if abs(poly.area - area) > 1e-6 * max(area, 1):
            problems.append(f"{key}: area_mm2 de analyze_dxf difiere del polígono")
        pieces_info[key] = {"length": length, "area": area, "w": w, "h": h, "bytes": len(raw), "sheet_ok": sheet.area > 0}

    issue_times: list[tuple[datetime, str]] = []
    for q in ordered_quotations():
        state, accepted = "draft", False
        issued_qty: dict[int, int] = {}
        drafts: dict[str, list[tuple[int, int]]] = {}
        for item in q["items"]:
            if item[0] not in data.PIECES:
                problems.append(f"{q['key']}: pieza inexistente {item[0]}")
        if q["client"] >= len(data.CLIENTS):
            problems.append(f"{q['key']}: cliente inexistente")
        if q["cur"] == "USD" and not q["fx"]:
            problems.append(f"{q['key']}: USD sin tipo de cambio")
        last = -1
        reserved: dict[int, str] = {}
        for step, when in schedule(anchor, q):
            op = step[0]
            offset = (when.date() - (anchor - timedelta(days=q["days_ago"]))).days
            if offset < last:
                problems.append(f"{q['key']}: pasos fuera de orden ({op})")
            last = offset
            if when > now:
                problems.append(f"{q['key']}: paso {op} en el futuro")
            if op == "send":
                if state != "draft":
                    problems.append(f"{q['key']}: send desde {state}")
                state = "sent"
            elif op == "accept":
                if state != "sent":
                    problems.append(f"{q['key']}: accept desde {state}")
                state = "accepted"
            elif op == "cancel":
                if state == "cancelled":
                    problems.append(f"{q['key']}: cancel repetido")
                if "CONSUMED" in reserved.values():
                    problems.append(f"{q['key']}: cancel con corte ya confirmado")
                reserved = {i: ("RELEASED" if s == "ACTIVE" else s) for i, s in reserved.items()}
                state = "cancelled"
            elif op == "reserve":
                if state != "accepted":
                    problems.append(f"{q['key']}: reserve sin aceptar")
                reserved[step[1]] = "ACTIVE"
            elif op == "release":
                if reserved.get(step[1]) != "ACTIVE":
                    problems.append(f"{q['key']}: release sin reserva activa")
                reserved[step[1]] = "RELEASED"
            elif op == "cut":
                if reserved.get(step[1]) != "ACTIVE":
                    problems.append(f"{q['key']}: cut sin reserva activa")
                reserved[step[1]] = "CONSUMED"
            elif op == "dn":
                drafts[step[1]] = step[2]
            elif op == "issue":
                for idx, qty in drafts[step[1]]:
                    if reserved.get(idx) != "CONSUMED":
                        problems.append(f"{q['key']}: remito {step[1]} incluye ítem {idx} sin corte")
                    issued_qty[idx] = issued_qty.get(idx, 0) + qty
                    if issued_qty[idx] > q["items"][idx][1]:
                        problems.append(f"{q['key']}: remito {step[1]} excede lo cotizado")
                issue_times.append((when, step[1]))
            elif op == "void":
                for idx, qty in drafts[step[1]]:
                    issued_qty[idx] -= qty
        if any(v for v in reserved.values() if v == "ACTIVE") and state == "cancelled":
            problems.append(f"{q['key']}: cancelada con reserva activa")
    times = [t for t, _ in issue_times]
    if times != sorted(times):
        problems.append("Los remitos no se emiten en orden cronológico (la numeración quedaría desordenada)")
    keys = [k for _, k in issue_times]
    if len(set(keys)) != len(keys):
        problems.append("Claves de remito repetidas")

    planned_cuts = sum(1 for q in data.QUOTATIONS for s in q["flow"] if s[0] == "cut")
    planned_res = sum(1 for q in data.QUOTATIONS for s in q["flow"] if s[0] == "reserve")
    dn_all = [s for q in data.QUOTATIONS for s in q["flow"] if s[0] == "dn"]
    summary = {
        "clients": len(data.CLIENTS),
        "materials": len(data.MATERIALS),
        "machine_configs": len(data.MATERIALS),
        "pieces": len(data.PIECES),
        "stock_full_sheets": sum(v[0] for v in data.STOCK.values()),
        "stock_manual_remnants": sum(len(v[1]) for v in data.STOCK.values()) + 1,
        "quotations": len(data.QUOTATIONS),
        "quotation_items": sum(len(q["items"]) for q in data.QUOTATIONS),
        "reservations": planned_res,
        "cut_confirmations": planned_cuts,
        "delivery_notes": len(dn_all),
        "delivery_notes_issued_or_voided": sum(1 for q in data.QUOTATIONS for s in q["flow"] if s[0] == "issue"),
    }
    return {"problems": problems, "pieces": pieces_info, "summary": summary}


# ── Acceso a base ─────────────────────────────────────────────────────────────
def describe_target(url: str) -> tuple[str, bool]:
    parsed = urlparse(url)
    if url.startswith("sqlite"):
        return "sqlite (archivo local)", True
    host = parsed.hostname or ""
    return f"{host}:{parsed.port or 5432}/{(parsed.path or '/').lstrip('/')}", host in LOCAL_HOSTS


COMPANY_TABLES_ORDER = [  # orden de borrado respetando FKs
    ("delivery_note_items", "delivery_note_id IN (SELECT id FROM delivery_notes WHERE company_id = :c)"),
    ("delivery_notes", "company_id = :c"),
    ("stock_movements", "company_id = :c"),
    ("stock_reservations", "company_id = :c"),
    ("stock_sheets", "company_id = :c AND stock_type = 'REMNANT'"),
    ("stock_sheets", "company_id = :c"),
    ("quotation_events", "quotation_id IN (SELECT id FROM quotations WHERE company_id = :c)"),
    ("quotation_items", "quotation_id IN (SELECT id FROM quotations WHERE company_id = :c)"),
    ("quotations", "company_id = :c"),
    ("machine_configs", "company_id = :c"),
    ("pieces", "company_id = :c"),
    ("materials", "company_id = :c"),
    ("clients", "company_id = :c"),
    ("document_sequences", "company_id = :c"),
]

INVENTORY_TABLES = {
    "clients": "company_id = :c",
    "materials": "company_id = :c",
    "machine_configs": "company_id = :c",
    "pieces": "company_id = :c",
    "quotations": "company_id = :c",
    "quotation_items": "quotation_id IN (SELECT id FROM quotations WHERE company_id = :c)",
    "quotation_events": "quotation_id IN (SELECT id FROM quotations WHERE company_id = :c)",
    "stock_sheets": "company_id = :c",
    "stock_reservations": "company_id = :c",
    "stock_movements": "company_id = :c",
    "delivery_notes": "company_id = :c",
    "delivery_note_items": "delivery_note_id IN (SELECT id FROM delivery_notes WHERE company_id = :c)",
    "document_sequences": "company_id = :c",
}

# Tablas con company_id propio o derivable, para comprobar que NADA ajeno cambió.
FOREIGN_FINGERPRINT = {
    "clients": "company_id <> :c",
    "materials": "company_id <> :c",
    "machine_configs": "company_id <> :c",
    "pieces": "company_id <> :c",
    "quotations": "company_id <> :c",
    "quotation_items": "quotation_id IN (SELECT id FROM quotations WHERE company_id <> :c)",
    "quotation_events": "quotation_id IN (SELECT id FROM quotations WHERE company_id <> :c)",
    "stock_sheets": "company_id <> :c",
    "stock_reservations": "company_id <> :c",
    "stock_movements": "company_id <> :c",
    "delivery_notes": "company_id <> :c",
    "delivery_note_items": "delivery_note_id IN (SELECT id FROM delivery_notes WHERE company_id <> :c)",
    "document_sequences": "company_id <> :c",
    "companies": "id <> :c",
    "company_members": "company_id <> :c",
}


def inventory(conn, company_id: int) -> dict[str, int]:
    from sqlalchemy import text

    return {
        t: conn.execute(text(f"SELECT count(*) FROM {t} WHERE {where}"), {"c": company_id}).scalar()
        for t, where in INVENTORY_TABLES.items()
    }


def fingerprint(conn, company_id: int) -> dict[str, str]:
    """md5 de las filas de todo lo que NO es de la empresa objetivo (+ usuarios completos)."""
    from sqlalchemy import text

    out = {}
    for t, where in FOREIGN_FINGERPRINT.items():
        rows = conn.execute(text(f"SELECT x::text FROM {t} x WHERE {where} ORDER BY id"), {"c": company_id}).scalars().all()
        out[t] = f"{len(rows)}:{hashlib.md5(chr(10).join(rows).encode()).hexdigest()}"
    rows = conn.execute(text("SELECT x::text FROM users x ORDER BY id")).scalars().all()
    out["users"] = f"{len(rows)}:{hashlib.md5(chr(10).join(rows).encode()).hexdigest()}"
    rows = conn.execute(
        text("SELECT x::text FROM company_members x WHERE company_id = :c ORDER BY id"), {"c": company_id}
    ).scalars().all()
    out["company_members(target)"] = f"{len(rows)}:{hashlib.md5(chr(10).join(rows).encode()).hexdigest()}"
    rows = conn.execute(text("SELECT x::text FROM companies x WHERE id = :c"), {"c": company_id}).scalars().all()
    out["companies(target)"] = f"{len(rows)}:{hashlib.md5(chr(10).join(rows).encode()).hexdigest()}"
    return out


def preflight(conn, company_id: int, expect_name: str) -> dict:
    from sqlalchemy import text

    row = conn.execute(
        text("SELECT id, company_name, is_active FROM companies WHERE id = :c"), {"c": company_id}
    ).first()
    if not row:
        _fail(f"No existe la empresa con id {company_id}.")
    if row.company_name != expect_name:
        _fail(f"La empresa {company_id} se llama '{row.company_name}', no '{expect_name}'. Abortado.")
    if not row.is_active:
        _fail("La empresa está inactiva.")
    dup = conn.execute(
        text("SELECT count(*) FROM companies WHERE company_name = :n"), {"n": expect_name}
    ).scalar()
    members = conn.execute(
        text(
            "SELECT cm.user_id, cm.role FROM company_members cm JOIN users u ON u.id = cm.user_id "
            "WHERE cm.company_id = :c AND cm.is_active AND u.is_active ORDER BY cm.id"
        ),
        {"c": company_id},
    ).all()
    owners = [m.user_id for m in members if m.role == "owner"]
    staff = [m.user_id for m in members if m.role != "owner"]
    if not owners:
        _fail("La empresa no tiene un OWNER activo; no hay con quién actuar.")
    head = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    code_head = ScriptDirectory.from_config(Config(str(BACKEND_DIR / "alembic.ini"))).get_current_head()
    if head != code_head:
        _fail(f"Alembic de la base ({head}) distinto del head del código ({code_head}). Migrá primero.")
    return {"name": row.company_name, "duplicates": dup, "owners": owners, "staff": staff, "alembic": head}


def wipe(conn, company_id: int) -> dict[str, int]:
    from sqlalchemy import text

    deleted: dict[str, int] = {}
    for table, where in COMPANY_TABLES_ORDER:
        res = conn.execute(text(f"DELETE FROM {table} WHERE {where}"), {"c": company_id})
        deleted[table] = deleted.get(table, 0) + (res.rowcount or 0)
    return deleted


# ── Siembra vía API real ──────────────────────────────────────────────────────
class Seeder:
    def __init__(self, company_id: int, owners: list[int], staff: list[int], anchor: date, engine):
        from fastapi.testclient import TestClient

        from app.main import app
        from app.services.auth_guard import get_current_user

        self.company_id = company_id
        self.owners = owners
        self.staff = staff or owners
        self.anchor = anchor
        self.engine = engine
        self.app = app
        self.get_current_user = get_current_user
        self.client = TestClient(app, raise_server_exceptions=False)
        for name in ("", "httpx", "slowapi", "app"):
            logging.getLogger(name).setLevel(logging.WARNING)
        self.actor = owners[0]
        app.dependency_overrides[get_current_user] = lambda: self.actor
        self._reset_limiters()
        self.ids: dict[str, dict] = {"clients": [], "materials": {}, "pieces": {}, "quotations": {}, "items": {}, "res": {}, "dn": {}}
        self.stock_codes: dict[int, str] = {}

    def close(self):
        self.app.dependency_overrides.pop(self.get_current_user, None)

    @staticmethod
    def _reset_limiters():
        from app.api.v1 import routes_auth, routes_pieces
        from app.main import limiter as main_limiter

        for lim in (main_limiter, routes_auth.limiter, routes_pieces.limiter):
            lim.reset()

    def call(self, method: str, url: str, actor: int, expect=(200, 201, 204), **kw):
        self.actor = actor
        headers = {"X-Company-Id": str(self.company_id), "Authorization": "Bearer seed"}
        res = self.client.request(method, url, headers=headers, **kw)
        if res.status_code not in expect:
            raise SeedError(f"{method} {url} -> {res.status_code}: {res.text[:300]}")
        return res

    # ---- re-fechado -------------------------------------------------------
    _STAMP = {
        "clients": ("company_id = :c", True),
        "materials": ("company_id = :c", True),
        "machine_configs": ("company_id = :c", True),
        "pieces": ("company_id = :c", True),
        "quotations": ("company_id = :c", True),
        "quotation_items": ("quotation_id IN (SELECT id FROM quotations WHERE company_id = :c)", True),
        "quotation_events": ("quotation_id IN (SELECT id FROM quotations WHERE company_id = :c)", False),
        "stock_sheets": ("company_id = :c", True),
        "stock_reservations": ("company_id = :c", False),
        "stock_movements": ("company_id = :c", False),
        "delivery_notes": ("company_id = :c", True),
    }

    def snapshot(self) -> dict[str, int]:
        from sqlalchemy import text

        with self.engine.connect() as conn:
            return {t: conn.execute(text(f"SELECT coalesce(max(id),0) FROM {t}")).scalar() for t in self._STAMP}

    def stamp(self, snap: dict[str, int], when: datetime) -> None:
        from sqlalchemy import text

        with self.engine.begin() as conn:
            for table, (where, has_updated) in self._STAMP.items():
                ids = conn.execute(
                    text(f"SELECT id FROM {table} WHERE id > :s AND {where} ORDER BY id"),
                    {"s": snap[table], "c": self.company_id},
                ).scalars().all()
                for k, row_id in enumerate(ids):
                    at = when + timedelta(seconds=k)
                    sets = "created_at = :at" + (", updated_at = :at" if has_updated else "")
                    conn.execute(text(f"UPDATE {table} SET {sets} WHERE id = :i"), {"at": at, "i": row_id})

    def touch(self, table: str, row_id: int, when: datetime) -> None:
        from sqlalchemy import text

        with self.engine.begin() as conn:
            conn.execute(text(f"UPDATE {table} SET updated_at = :at WHERE id = :i"), {"at": when, "i": row_id})

    @contextmanager
    def at(self, when: datetime):
        from app.core import clock
        from app.services import delivery_notes as dn_service

        original = (clock.business_today, dn_service._naive_business_now)
        clock.business_today = lambda: when.date()
        dn_service._naive_business_now = lambda: when
        snap = self.snapshot()
        try:
            yield
        finally:
            clock.business_today, dn_service._naive_business_now = original
            self.stamp(snap, when)

    # ---- fases -------------------------------------------------------------
    def seed_catalog(self):
        base = self.anchor - timedelta(days=165)
        when = datetime.combine(base, datetime.min.time()) + timedelta(hours=10)
        owner = self.owners[0]
        with self.at(when):
            for name, cuit, phone, email, address, notes in data.CLIENTS:
                body = {"name": name, "cuit_cuil": cuit, "phone": phone, "email": email, "address": address, "notes": notes}
                r =self.call("POST", "/clients/", self.staff[0], json=body).json()
                self.ids["clients"].append(r["id"])
        when += timedelta(days=1)
        with self.at(when):
            for key, m in data.MATERIALS.items():
                name, mtype, alloy, th, w, h, cost = m[:7]
                r = self.call("POST", "/materials/", owner, json={
                    "name": name, "material_type": mtype, "alloy": alloy, "thickness_mm": th,
                    "sheet_width_mm": w, "sheet_height_mm": h, "sheet_cost_ars": cost}).json()
                self.ids["materials"][key] = r["id"]
        when += timedelta(hours=1)
        with self.at(when):
            for key, m in data.MATERIALS.items():
                speed, cost_h, setup, labor, kerf, spacing = m[7:]
                self.call("POST", "/machine-configs/", owner, json={
                    "material_id": self.ids["materials"][key], "cut_speed_mm_min": speed,
                    "machine_cost_per_hour_ars": cost_h, "setup_time_min": setup, "labor_percent": labor,
                    "kerf_mm": kerf, "minimum_spacing_mm": spacing})
        when += timedelta(days=1)
        with self.at(when):
            for key, (name, desc, mat_key, spec) in data.PIECES.items():
                raw = data.build_dxf(spec)
                r = self.call("POST", "/pieces/", self.staff[0], data={
                    "name": name, "description": desc, "material_id": str(self.ids["materials"][mat_key])},
                    files={"file": (f"{key}_{name.lower().replace(' ', '_')}.dxf", io.BytesIO(raw), "application/dxf")}).json()
                self.ids["pieces"][key] = r["id"]

    def seed_stock(self):
        base = self.anchor - timedelta(days=160)
        when = datetime.combine(base, datetime.min.time()) + timedelta(hours=11)
        owner = self.owners[0]
        with self.at(when):
            for key, (fulls, remnants) in data.STOCK.items():
                m = data.MATERIALS[key]
                mid = self.ids["materials"][key]
                for _ in range(fulls):
                    self.call("POST", "/stock", owner, json={"material_id": mid, "stock_type": "FULL_SHEET",
                                                              "width_mm": m[4], "height_mm": m[5]})
                for w, h in remnants:
                    self.call("POST", "/stock", owner, json={"material_id": mid, "stock_type": "REMNANT",
                                                              "width_mm": w, "height_mm": h})
            key, (w, h) = data.STOCK_DISCARD
            r = self.call("POST", "/stock", owner, json={"material_id": self.ids["materials"][key],
                                                          "stock_type": "REMNANT", "width_mm": w, "height_mm": h}).json()
        with self.at(when + timedelta(days=3)):
            self.call("PATCH", f"/stock/{r['id']}/discard", owner)
            self.ids["discarded_stock"] = r["id"]
        self.touch("stock_sheets", r["id"], when + timedelta(days=3))

    def seed_quotations(self):
        for n, q in enumerate(ordered_quotations()):
            owner = self.owners[n % len(self.owners)]
            staff = self.staff[n % len(self.staff)]
            issue_day = self.anchor - timedelta(days=q["days_ago"])
            created_at = datetime.combine(issue_day, datetime.min.time()) + timedelta(hours=9, minutes=15)
            # due_date NO se envía al crear: mientras la cotización es borrador, un vencimiento
            # histórico la hace candidata a _auto_expire (que corre en la app en vivo al listar
            # cotizaciones) y la cancelaría en medio de la siembra. Se fija al enviarla (run_step).
            body = {
                "client_id": self.ids["clients"][q["client"]],
                "issue_date": issue_day.isoformat(),
                "due_date": None,
                "currency": q["cur"],
                "exchange_rate": q["fx"],
                "notes": q["note"],
            }
            with self.at(created_at):
                r = self.call("POST", "/quotations/", owner, json=body).json()
                qid = r["id"]
                self.ids["quotations"][q["key"]] = qid
                items = []
                for piece_key, qty, margin in q["items"]:
                    mat_key = data.PIECES[piece_key][2]
                    it = self.call("POST", "/quotation-items/", owner, json={
                        "quotation_id": qid, "piece_id": self.ids["pieces"][piece_key],
                        "material_id": self.ids["materials"][mat_key], "quantity": qty, "margin_percent": margin}).json()
                    items.append(it["id"])
                self.ids["items"][q["key"]] = items
            self.touch("quotations", qid, created_at + timedelta(minutes=5))
            for step, when in schedule(self.anchor, q):
                self.run_step(q, qid, step, when, owner, staff)

    def run_step(self, q, qid, step, when, owner, staff):
        op = step[0]
        items = self.ids["items"][q["key"]]
        touched_sheets: set[int] = set()
        with self.at(when):
            if op in ("send", "accept", "cancel"):
                target = {"send": "sent", "accept": "accepted", "cancel": "cancelled"}[op]
                self.call("PATCH", f"/quotations/{qid}/status", owner, json={"status": target})
                if op == "cancel":
                    from sqlalchemy import text

                    with self.engine.connect() as conn:
                        touched_sheets.update(conn.execute(
                            text("SELECT stock_sheet_id FROM stock_reservations WHERE quotation_id = :q"), {"q": qid}).scalars())
            elif op == "reserve":
                idx = step[1]
                piece_key, qty, _ = q["items"][idx]
                mid = self.ids["materials"][data.PIECES[piece_key][2]]
                recs = self.call("POST", "/stock/recommendations", staff,
                                 json={"piece_id": self.ids["pieces"][piece_key], "material_id": mid}).json()
                best = recs[0]
                r = self.call("POST", f"/stock/{best['stock_sheet_id']}/reserve", staff, json={
                    "piece_id": self.ids["pieces"][piece_key], "material_id": mid, "quotation_id": qid,
                    "quotation_item_id": items[idx]}).json()
                self.ids["res"][(q["key"], idx)] = r["id"]
                touched_sheets.add(best["stock_sheet_id"])
            elif op in ("cut", "release"):
                idx = step[1]
                rid = self.ids["res"][(q["key"], idx)]
                path = "confirm-cut" if op == "cut" else "release"
                res = self.call("POST", f"/stock/reservations/{rid}/{path}", staff).json()
                touched_sheets.add(res["stock_sheet_id"])
            elif op == "dn":
                key = step[1]
                lines = [{"quotation_item_id": items[i], "quantity": n} for i, n in step[2]]
                notes = "Retira personal del cliente." if sum(ord(c) for c in key) % 2 else "Entrega en planta del cliente."
                r = self.call("POST", "/delivery-notes/", staff, json={"quotation_id": qid, "notes": notes, "items": lines}).json()
                self.ids["dn"][key] = r["id"]
            elif op == "issue":
                self.call("POST", f"/delivery-notes/{self.ids['dn'][step[1]]}/issue", staff)
            elif op == "void":
                self.call("POST", f"/delivery-notes/{self.ids['dn'][step[1]]}/void", owner, json={"reason": step[3]})
        if op == "send":
            from sqlalchemy import text

            due = datetime.combine(self.anchor - timedelta(days=q["days_ago"]) + timedelta(days=30), datetime.min.time())
            with self.engine.begin() as conn:
                conn.execute(text("UPDATE quotations SET due_date = :d WHERE id = :q AND status <> 'draft'"), {"d": due, "q": qid})
        self.touch("quotations", qid, when)
        for sid in touched_sheets:
            self.touch("stock_sheets", sid, when)
        if op in ("issue", "void"):
            self.touch("delivery_notes", self.ids["dn"][step[1]], when)

    def run_all(self):
        self.seed_catalog()
        self.seed_stock()
        self.seed_quotations()


# ── Verificación posterior (solo lectura) ─────────────────────────────────────
def verify(engine, client, company_id: int, owner_id: int) -> list[tuple[bool, str]]:
    import math

    from sqlalchemy import text

    from app.models.machine_config import MachineConfig
    from app.models.material import Material
    from app.services.quotation_calculator import compute_item_costs

    results: list[tuple[bool, str]] = []

    def check(ok: bool, msg: str):
        results.append((bool(ok), msg))

    c = {"c": company_id}
    with engine.connect() as conn:
        q = lambda sql, **p: conn.execute(text(sql), {**c, **p})  # noqa: E731
        inv = inventory(conn, company_id)
        check(inv["clients"] == len(data.CLIENTS), f"{inv['clients']} clientes")
        check(inv["materials"] == len(data.MATERIALS) == inv["machine_configs"], f"{inv['materials']} materiales con {inv['machine_configs']} configuraciones")
        check(inv["pieces"] == len(data.PIECES), f"{inv['pieces']} piezas")
        check(inv["quotations"] == len(data.QUOTATIONS), f"{inv['quotations']} cotizaciones, {inv['quotation_items']} ítems")

        # cálculos: recomputar con la fórmula real y comparar
        bad = 0
        rows = q("""SELECT qi.id, qi.quantity, qi.margin_percent, qi.cost_material_ars, qi.cost_machine_ars, qi.cost_labor_ars,
                           qi.unit_price_ars, qi.total_price_ars, p.area_mm2, p.length_cut_mm, qi.material_id
                    FROM quotation_items qi JOIN quotations qt ON qt.id = qi.quotation_id
                    JOIN pieces p ON p.id = qi.piece_id WHERE qt.company_id = :c""").all()
        from sqlalchemy.orm import Session

        with Session(engine) as s:
            for r in rows:
                mat = s.get(Material, r.material_id)
                mc = s.query(MachineConfig).filter(MachineConfig.material_id == r.material_id, MachineConfig.active.is_(True)).first()
                exp = compute_item_costs(r.area_mm2, r.length_cut_mm, mat, mc, r.quantity, r.margin_percent)
                vals = (r.cost_material_ars, r.cost_machine_ars, r.cost_labor_ars, r.unit_price_ars, r.total_price_ars)
                want = (exp.cost_material_ars, exp.cost_machine_ars, exp.cost_labor_ars, exp.unit_price_ars, exp.total_price_ars)
                if not all(math.isfinite(v) and v >= 0 for v in vals) or not all(math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9) for a, b in zip(vals, want)):
                    bad += 1
        check(bad == 0 and rows, f"{len(rows)} ítems: costos coinciden con la fórmula real y son finitos ({bad} con diferencias)")
        diff = q("""SELECT count(*) FROM quotations qt WHERE qt.company_id = :c AND abs(qt.total_ars -
                    coalesce((SELECT sum(total_price_ars) FROM quotation_items WHERE quotation_id = qt.id),0)) > 0.005""").scalar()
        check(diff == 0, f"totales de cotización = suma de ítems ({diff} con diferencia)")
        usd = q("""SELECT count(*) FROM quotations WHERE company_id = :c AND currency = 'USD' AND
                   (exchange_rate IS NULL OR abs(total_usd - total_ars/exchange_rate) > 0.005)""").scalar()
        check(usd == 0, f"cotizaciones USD con tipo de cambio guardado y total_usd coherente ({usd} con error)")
        st = dict(q("SELECT status, count(*) FROM quotations WHERE company_id = :c GROUP BY 1").all())
        check(set(st) <= {"draft", "sent", "accepted", "cancelled"} and len(st) == 4, f"estados de cotización: {st}")

        # stock
        neg = q("SELECT count(*) FROM stock_sheets WHERE company_id = :c AND (remaining_area_mm2 < 0 OR remaining_area_mm2 > original_area_mm2)").scalar()
        check(neg == 0, f"sin stock negativo ni saldo mayor al original ({neg})")
        sheets = {r.status: r.n for r in q("SELECT status, count(*) n FROM stock_sheets WHERE company_id = :c GROUP BY 1")}
        res = {r.status: r.n for r in q("SELECT status, count(*) n FROM stock_reservations WHERE company_id = :c GROUP BY 1")}
        check(sheets.get("RESERVED", 0) == res.get("ACTIVE", 0), f"chapas RESERVED ({sheets.get('RESERVED', 0)}) = reservas ACTIVE ({res.get('ACTIVE', 0)})")
        consumed_ok = q("""SELECT count(*) FROM stock_sheets s WHERE s.company_id = :c AND s.status = 'CONSUMED'
                           AND NOT EXISTS (SELECT 1 FROM stock_reservations r WHERE r.stock_sheet_id = s.id AND r.status = 'CONSUMED')""").scalar()
        check(consumed_ok == 0 and sheets.get("CONSUMED", 0) == res.get("CONSUMED", 0), f"chapas CONSUMED ({sheets.get('CONSUMED', 0)}) = reservas CONSUMED ({res.get('CONSUMED', 0)})")
        zero_rem = q("SELECT count(*) FROM stock_sheets WHERE company_id = :c AND status = 'CONSUMED' AND remaining_area_mm2 <> 0").scalar()
        check(zero_rem == 0, "chapas consumidas con saldo 0")
        # movimientos: el último movimiento de cada chapa coincide con su estado
        mism = q("""SELECT count(*) FROM stock_sheets s WHERE s.company_id = :c AND s.status <> (
                      CASE (SELECT movement_type FROM stock_movements m WHERE m.stock_sheet_id = s.id ORDER BY m.id DESC LIMIT 1)
                        WHEN 'CREATED' THEN 'AVAILABLE' WHEN 'REMNANT_CREATED' THEN 'AVAILABLE' WHEN 'RELEASED' THEN 'AVAILABLE'
                        WHEN 'RESERVED' THEN 'RESERVED' WHEN 'CONSUMED' THEN 'CONSUMED' WHEN 'DISCARDED' THEN 'DISCARDED' END)""").scalar()
        check(mism == 0, f"estado de cada chapa coincide con su último movimiento ({mism} inconsistentes)")
        no_mov = q("SELECT count(*) FROM stock_sheets s WHERE s.company_id = :c AND NOT EXISTS (SELECT 1 FROM stock_movements m WHERE m.stock_sheet_id = s.id)").scalar()
        check(no_mov == 0, f"toda chapa tiene al menos un movimiento ({no_mov} sin)")
        mt = dict(q("SELECT movement_type, count(*) FROM stock_movements WHERE company_id = :c GROUP BY 1").all())
        check(mt.get("RESERVED", 0) == sum(res.values()) and mt.get("CONSUMED", 0) == res.get("CONSUMED", 0), f"movimientos: {mt}")
        dup_act = q("SELECT count(*) FROM (SELECT stock_sheet_id FROM stock_reservations WHERE company_id = :c AND status='ACTIVE' GROUP BY 1 HAVING count(*) > 1) t").scalar()
        check(dup_act == 0, "a lo sumo una reserva ACTIVE por chapa")
        cancelled_active = q("""SELECT count(*) FROM stock_reservations r JOIN quotations qt ON qt.id = r.quotation_id
                                WHERE r.company_id = :c AND r.status = 'ACTIVE' AND qt.status <> 'accepted'""").scalar()
        check(cancelled_active == 0, "reservas ACTIVE solo en cotizaciones aceptadas")

        # remitos
        dn = {r.status: r.n for r in q("SELECT status, count(*) n FROM delivery_notes WHERE company_id = :c GROUP BY 1")}
        check(set(dn) == {"DRAFT", "ISSUED", "VOIDED"}, f"remitos por estado: {dn}")
        nums = [r.number for r in q("SELECT number FROM delivery_notes WHERE company_id = :c AND number IS NOT NULL ORDER BY id")]
        check(len(nums) == len(set(nums)) and sorted(nums) == [f"R-{i:06d}" for i in range(1, len(nums) + 1)], f"numeración consecutiva sin repetir ({len(nums)} numerados)")
        lastn = q("SELECT last_number FROM document_sequences WHERE company_id = :c AND doc_type = 'DELIVERY_NOTE'").scalar()
        check(lastn == len(nums), f"contador de remitos = {lastn}")
        over = q("""SELECT count(*) FROM quotation_items qi JOIN quotations qt ON qt.id = qi.quotation_id
                    WHERE qt.company_id = :c AND qi.quantity < coalesce((SELECT sum(di.quantity) FROM delivery_note_items di
                      JOIN delivery_notes d ON d.id = di.delivery_note_id WHERE di.quotation_item_id = qi.id AND d.status = 'ISSUED'),0)""").scalar()
        check(over == 0, f"entregado ≤ cotizado en todos los ítems ({over} excedidos)")
        uncut = q("""SELECT count(*) FROM delivery_note_items di JOIN delivery_notes d ON d.id = di.delivery_note_id
                     WHERE d.company_id = :c AND d.status IN ('ISSUED','VOIDED') AND NOT EXISTS (
                       SELECT 1 FROM stock_reservations r WHERE r.quotation_item_id = di.quotation_item_id AND r.status = 'CONSUMED')""").scalar()
        check(uncut == 0, f"todo remito emitido/anulado tiene corte confirmado ({uncut} sin)")

        # sin referencias cruzadas
        cross = 0
        for sql in (
            "SELECT count(*) FROM quotations q JOIN clients c ON c.id=q.client_id WHERE q.company_id=:c AND c.company_id<>:c",
            "SELECT count(*) FROM quotation_items i JOIN quotations q ON q.id=i.quotation_id JOIN pieces p ON p.id=i.piece_id WHERE q.company_id=:c AND p.company_id<>:c",
            "SELECT count(*) FROM quotation_items i JOIN quotations q ON q.id=i.quotation_id JOIN materials m ON m.id=i.material_id WHERE q.company_id=:c AND m.company_id<>:c",
            "SELECT count(*) FROM stock_sheets s JOIN materials m ON m.id=s.material_id WHERE s.company_id=:c AND m.company_id<>:c",
            "SELECT count(*) FROM stock_reservations r JOIN stock_sheets s ON s.id=r.stock_sheet_id WHERE r.company_id=:c AND s.company_id<>:c",
            "SELECT count(*) FROM delivery_notes d JOIN quotations q ON q.id=d.quotation_id WHERE d.company_id=:c AND q.company_id<>:c",
        ):
            cross += q(sql).scalar()
        check(cross == 0, f"referencias cruzadas entre empresas: {cross}")
        future = q("""SELECT count(*) FROM (SELECT created_at FROM quotations WHERE company_id=:c UNION ALL SELECT created_at FROM stock_movements WHERE company_id=:c
                      UNION ALL SELECT created_at FROM delivery_notes WHERE company_id=:c) t WHERE created_at > now() + interval '1 day'""").scalar()
        check(future == 0, "ninguna fecha en el futuro")
        stale = sum(q(f"SELECT count(*) FROM {t} WHERE {w} AND updated_at > now() - interval '1 day'").scalar() for t, w in (
            ("quotations", "company_id = :c"), ("stock_sheets", "company_id = :c"), ("delivery_notes", "company_id = :c"),
            ("clients", "company_id = :c"), ("pieces", "company_id = :c"), ("materials", "company_id = :c"),
            ("quotation_items", "quotation_id IN (SELECT id FROM quotations WHERE company_id = :c)")))
        check(stale == 0, f"ninguna fila con updated_at de 'hoy' sin re-fechar ({stale})")

    # PDFs vía API real
    headers = {"X-Company-Id": str(company_id), "Authorization": "Bearer seed"}
    with engine.connect() as conn:
        issued = conn.execute(text("SELECT id, status FROM delivery_notes WHERE company_id = :c AND status IN ('ISSUED','VOIDED','DRAFT') ORDER BY id"), c).all()
        qids = conn.execute(text("SELECT id FROM quotations WHERE company_id = :c ORDER BY id"), c).scalars().all()
    bad_pdf = [i for i, _ in issued if not _pdf_ok(client.get(f"/delivery-notes/{i}/pdf", headers=headers))]
    check(not bad_pdf, f"{len(issued)} PDFs de remitos válidos ({bad_pdf} con error)")
    bad_q = [i for i in qids if not _pdf_ok(client.get(f"/quotations/{i}/pdf", headers=headers))]
    check(not bad_q, f"{len(qids)} PDFs de cotizaciones válidos ({bad_q} con error)")
    return results


def _pdf_ok(res) -> bool:
    return res.status_code == 200 and res.headers.get("content-type", "").startswith("application/pdf") and res.content[:4] == b"%PDF"


# ── Catálogo de escenarios ────────────────────────────────────────────────────
def build_catalog(engine, client, company_id: int, seeder: Seeder | None, company_name: str) -> str:
    from sqlalchemy import text

    headers = {"X-Company-Id": str(company_id), "Authorization": "Bearer seed"}
    lines = [f"# Catálogo de demostración — {company_name} (company_id={company_id})", "",
             "Generado por `scripts/seed_demo_company.py` (datos ficticios, semilla v%d)." % SEED_VERSION, ""]
    with engine.connect() as conn:
        qs = {r.id: r for r in conn.execute(text(
            "SELECT q.id, q.number, q.status, q.total_ars, q.currency, q.total_usd, c.name client, q.issue_date::date d, q.notes "
            "FROM quotations q JOIN clients c ON c.id = q.client_id WHERE q.company_id = :c ORDER BY q.id"), {"c": company_id})}
        notes = {r.id: r for r in conn.execute(text(
            "SELECT id, number, status, quotation_id, total_units FROM (SELECT d.id, d.number, d.status, d.quotation_id, "
            "(SELECT coalesce(sum(quantity),0) FROM delivery_note_items WHERE delivery_note_id = d.id) total_units FROM delivery_notes d WHERE d.company_id = :c) t ORDER BY id"), {"c": company_id})}
    by_q: dict[int, list] = {}
    for n in notes.values():
        by_q.setdefault(n.quotation_id, []).append(n)

    def section(title, key):
        qid = seeder.ids["quotations"][key] if seeder else None
        if qid is None:
            return
        q = qs[qid]
        status = client.get(f"/delivery-notes/quotation/{qid}/status", headers=headers).json() if q.status == "accepted" else None
        lines.append(f"## {title}")
        lines.append(f"- Cotización **{q.number}** (id {qid}) · {q.client} · estado `{q.status}` · {q.d} · total ARS {q.total_ars:,.2f}"
                     + (f" / USD {q.total_usd:,.2f}" if q.currency == 'USD' else ""))
        lines.append(f"- {q.notes}")
        if status:
            for it in status["items"]:
                lines.append(f"  - {it['piece_name']}: cotizado {it['quoted']}, entregado {it['delivered']}, pendiente {it['pending']}, corte {'confirmado' if it['cut_confirmed'] else 'SIN confirmar'}")
        for n in by_q.get(qid, []):
            lines.append(f"  - Remito id {n.id} · {n.number or '(borrador, sin número)'} · `{n.status}` · {n.total_units} un")
        lines.append("")

    if seeder:
        scen = {q["scenario"]: q["key"] for q in data.QUOTATIONS if q["scenario"]}
        section("Escenario A — Cotización pendiente (enviada)", scen["A"])
        section("Escenario B — Aceptada sin corte", scen["B"])
        section("Escenario C — Corte parcial por ítems", scen["C"])
        section("Escenario D — Entrega parcial (100 un: 40 + 35, pendiente 25)", scen["D"])
        section("Escenario E — Remito anulado", scen["E"])
    lines += ["## Todas las cotizaciones", "", "| N° | id | Cliente | Estado | Fecha | Total ARS |", "|---|---|---|---|---|---|"]
    for q in qs.values():
        lines.append(f"| {q.number} | {q.id} | {q.client} | {q.status} | {q.d} | {q.total_ars:,.2f} |")
    lines += ["", "## Remitos", "", "| id | Número | Estado | Cotización | Unidades |", "|---|---|---|---|---|"]
    for n in notes.values():
        lines.append(f"| {n.id} | {n.number or '—'} | {n.status} | {qs[n.quotation_id].number} | {n.total_units} |")
    return "\n".join(lines) + "\n"


# ── CLI ───────────────────────────────────────────────────────────────────────
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Reemplaza los datos operativos de UNA empresa por un set de demostración.")
    ap.add_argument("--company-id", type=int, required=True)
    ap.add_argument("--expect-company-name", required=True, help="Nombre exacto esperado de la empresa (doble verificación).")
    ap.add_argument("--db-env-var", default="DATABASE_URL", help="Variable de entorno con la URL de la base (nunca se imprime).")
    ap.add_argument("--apply", action="store_true", help="Ejecuta el borrado y la siembra. Sin esto: dry-run de solo lectura.")
    ap.add_argument("--allow-remote", action="store_true", help="Permite una base que no sea localhost.")
    ap.add_argument("--confirm-token", default="", help="BORRAR-Y-REEMPLAZAR-EMPRESA-<id>, requerido con --allow-remote --apply.")
    ap.add_argument("--anchor-date", default=None, help="Fecha de 'hoy' para el cronograma (YYYY-MM-DD). Default: hoy.")
    ap.add_argument("--catalog-out", default=None, help="Ruta del catálogo Markdown a generar.")
    ap.add_argument("--verify-only", action="store_true", help="Solo corre las verificaciones sobre lo ya sembrado (lectura).")
    args = ap.parse_args(argv)

    url = os.environ.get(args.db_env_var)
    if not url:
        print(f"Falta la variable de entorno {args.db_env_var}.", file=sys.stderr)
        return 2
    os.environ["DATABASE_URL"] = url
    if not os.environ.get("SECRET_KEY"):
        print("Falta SECRET_KEY en el entorno (la config de la app la exige; en el ensayo puede ser cualquier valor).", file=sys.stderr)
        return 2

    target, is_local = describe_target(url)
    print(f"Base destino : {target}  ({'local' if is_local else 'REMOTA'})")
    print(f"Empresa      : id={args.company_id}  nombre esperado='{args.expect_company_name}'")
    print(f"Modo         : {'APPLY' if args.apply else 'verify-only' if args.verify_only else 'dry-run (solo lectura)'}")
    if args.apply and not is_local:
        if not args.allow_remote or args.confirm_token != f"BORRAR-Y-REEMPLAZAR-EMPRESA-{args.company_id}":
            print("Base remota: requiere --allow-remote y --confirm-token BORRAR-Y-REEMPLAZAR-EMPRESA-<id>.", file=sys.stderr)
            return 2
    if not url.startswith("postgresql") and not url.startswith("postgres"):
        print("Este script está pensado para PostgreSQL.", file=sys.stderr)
        return 2

    from app.db.session import engine  # importa la app recién ahora (necesita DATABASE_URL)

    logging.getLogger().setLevel(logging.WARNING)

    anchor = date.fromisoformat(args.anchor_date) if args.anchor_date else date.today()
    ds = validate_dataset(anchor)
    s = ds["summary"]
    print("\n== Dataset ==")
    for k, v in s.items():
        print(f"  {k}: {v}")
    if ds["problems"]:
        print("\nPROBLEMAS EN EL DATASET:", *ds["problems"], sep="\n  - ")
        return 1
    print("  validación del dataset: OK (DXF analizados, polígonos válidos, flujos coherentes)")

    try:
        with engine.connect() as conn:
            conn.exec_driver_sql("SET TRANSACTION READ ONLY")
            info = preflight(conn, args.company_id, args.expect_company_name)
            inv = inventory(conn, args.company_id)
            fp_before = fingerprint(conn, args.company_id)
        print(f"\n== Empresa == '{info['name']}' · homónimas: {info['duplicates']} · alembic {info['alembic']}")
        print(f"  owners activos: {info['owners']} · empleados activos: {info['staff']}")
        print("== Datos actuales que se eliminarían ==")
        for t, n in inv.items():
            print(f"  {t}: {n}")

        if args.verify_only:
            from fastapi.testclient import TestClient
            from app.main import app
            from app.services.auth_guard import get_current_user

            app.dependency_overrides[get_current_user] = lambda: info["owners"][0]
            results = verify(engine, TestClient(app), args.company_id, info["owners"][0])
            for ok, msg in results:
                print(("  OK   " if ok else "  FAIL ") + msg)
            return 0 if all(ok for ok, _ in results) else 1

        if not args.apply:
            print("\nDRY-RUN: no se modificó nada. Agregá --apply para borrar y sembrar.")
            return 0

        if info["duplicates"] != 1:
            _fail(f"Hay {info['duplicates']} empresas con ese nombre; se identifica por id pero se aborta por prudencia.")

        # 1) borrado en una sola transacción
        with engine.begin() as conn:
            deleted = wipe(conn, args.company_id)
            left = inventory(conn, args.company_id)
            if any(left.values()):
                raise SeedError(f"El borrado dejó filas: {left}")
        print("\n== Borrado OK ==", {k: v for k, v in deleted.items() if v})

        # 2) siembra con la lógica real
        seeder = Seeder(args.company_id, info["owners"], info["staff"], anchor, engine)
        try:
            seeder.run_all()
        except Exception as exc:
            seeder.close()
            print(f"\nERROR durante la siembra: {exc}\nLa empresa quedó parcialmente poblada: restaurá con el procedimiento de recuperación.")
            return 1

        # 3) verificación y comparación con el estado previo
        results = verify(engine, seeder.client, args.company_id, info["owners"][0])
        with engine.connect() as conn:
            fp_after = fingerprint(conn, args.company_id)
            after_inv = inventory(conn, args.company_id)
        results.append((fp_before == fp_after, "empresas ajenas, usuarios, roles y la propia empresa: sin ningún cambio"))
        print("\n== Creado ==")
        for t, n in after_inv.items():
            print(f"  {t}: {n}")
        print("\n== Verificación ==")
        for ok, msg in results:
            print(("  OK   " if ok else "  FAIL ") + msg)
        if fp_before != fp_after:
            print("  diferencias:", {k: (fp_before.get(k), fp_after.get(k)) for k in fp_before if fp_before.get(k) != fp_after.get(k)})
        catalog = build_catalog(engine, seeder.client, args.company_id, seeder, info["name"])
        if args.catalog_out:
            Path(args.catalog_out).write_text(catalog, encoding="utf-8")
            print(f"\nCatálogo escrito en {args.catalog_out}")
        seeder.close()
        return 0 if all(ok for ok, _ in results) else 1
    except SeedError as exc:
        print(f"\nABORTADO: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
