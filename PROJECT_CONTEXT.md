# PROJECT_CONTEXT.md

## Mantenimiento del archivo

Este archivo debe mantenerse actualizado.

Reglas:
- Cada cambio importante en el sistema debe reflejarse aquí
- No reescribir todo el archivo, solo modificar lo necesario
- Mantener consistencia con el estado real del proyecto
- No inventar funcionalidades

> Reescrito por completo el 2026-08-25 tras una auditoría integral de `main`, y actualizado el mismo día tras una segunda pasada de hardening autónomo (validación en Postgres real, fixes de concurrencia, cobertura de tests de DXF/costeo/PDF/E2E, alineación de contratos frontend↔backend, CI). La versión previa a la auditoría (7 de abril) describía una arquitectura previa a multiempresa/stock/nesting real y ya no era confiable como fuente de verdad. Repositorio canónico: `NadirTomas/Tesis_Cotizador`, rama `main`. Nombre funcional del sistema: **CotizaLaser**. El repositorio `NadirTomas/CotizaLaser` es obsoleto y no debe usarse como referencia.

## 1. Estado actual

Sistema en desarrollo activo, multiempresa, deployado en Railway con PostgreSQL. Cubre el flujo completo: cliente → material/máquina → pieza DXF → cotización → aceptación → reserva de stock → confirmación de corte → retazo, con auditoría de eventos, PDF on-demand, y aislamiento de datos por empresa verificado endpoint por endpoint. Los dos hallazgos críticos/altos de la auditoría (borrado de cotizaciones roto en Postgres, carrera cancelación/confirm-cut) están corregidos y validados contra Postgres real, no solo SQLite — ver §7.

**Deploy Railway** (proyecto `Tesis_Cotizador`, 3 servicios en el mismo environment `production`):
- Frontend: `frontend-production-ebde2.up.railway.app`
- Backend: `tesiscotizador-production.up.railway.app`
- Postgres: red privada (`postgres.railway.internal`), proxy TCP solo bajo demanda
- Para crear el primer usuario: `POST /auth/register`, luego crear una empresa con `POST /companies/` (el creador queda como OWNER) o vincularse a una existente por invitación

**CI**: `.github/workflows/ci.yml` corre en cada push/PR a `main` — backend contra SQLite, backend contra un service container de Postgres real (alembic upgrade head desde vacío + los tests de integración que antes se saltaban sin una DB real), y frontend (vitest + tsc + build). No hace deploy — Railway sigue auto-desplegando por su cuenta.

---

## 2. Tecnologías

### Backend
| Tecnología | Notas |
|---|---|
| Python | FastAPI |
| SQLAlchemy | ORM |
| PostgreSQL | Base de datos de producción (Railway, imagen `postgres-ssl:18`). SQLite solo como fallback local |
| Alembic | Migraciones — corre `alembic upgrade head` en cada arranque del backend en Railway |
| Pydantic v2 / pydantic-settings | Validación y configuración |
| Shapely | Geometría real (polígonos con huecos, colocación, retazos) para el motor de stock |
| ezdxf | Análisis de archivos DXF |
| ReportLab | Generación de PDF |
| PyJWT + bcrypt | Auth JWT HS256 (tokens de 7 días, sin revocación) + hash de passwords (cost 12) |
| slowapi | Rate limiting |
| psycopg2-binary | Driver PostgreSQL |
| pytest + httpx | Testing (corre contra SQLite; ver nota de concurrencia en §9) |

### Frontend
| Tecnología | Versión |
|---|---|
| React | 19.2 |
| TypeScript | 5.9 |
| Vite | 7 |
| React Router | 7 |
| Material UI (MUI) | 7 |
| Vitest + React Testing Library | Testing (cobertura mínima, ver §8) |

---

## 3. Estructura real

```
Tesis_Cotizador/
├── CLAUDE.md
├── PROJECT_CONTEXT.md
├── backend/
│   ├── alembic/
│   │   ├── env.py
│   │   ├── alembic.ini
│   │   └── versions/            ← 15 migraciones, un solo head (a8b9c0d1e2f3), cadena lineal.
│   │                               Validado end-to-end contra Postgres real: upgrade desde
│   │                               vacío completo, downgrade/upgrade de las 3 últimas sin
│   │                               pérdida de datos ni constraints/índices duplicados.
│   │                               (Contra SQLite la cadena completa NO corre —
│   │                               ad4a02af2953, de abril, nunca fue compatible con SQLite;
│   │                               no se tocó, es anterior y ajeno a este trabajo — usar
│   │                               siempre Postgres para validar la cadena completa).
│   │                               Nota: las fechas de archivo NO reflejan el orden real de
│   │                               aplicación — el historial pre-multiempresa fue colapsado
│   │                               detrás de un baseline_schema fechado en agosto. Alembic
│   │                               ordena por revision/down_revision, no por fecha; esto no
│   │                               afecta el funcionamiento, solo puede confundir al leer.
│   ├── app/
│   │   ├── api/v1/
│   │   │   ├── routes_health.py
│   │   │   ├── routes_auth.py
│   │   │   ├── routes_companies.py       ← empresas, miembros, roles, logo
│   │   │   ├── routes_admin.py           ← alta de empresa gateada por X-Admin-Secret
│   │   │   ├── routes_clients.py
│   │   │   ├── routes_materials.py
│   │   │   ├── routes_machine_configs.py
│   │   │   ├── routes_pieces.py
│   │   │   ├── routes_quotations.py
│   │   │   ├── routes_quotation_items.py
│   │   │   ├── routes_nesting.py         ← nesting de planificación (bin-packing rectangular)
│   │   │   └── routes_stock.py           ← stock físico real: chapas, retazos, reservas, movimientos
│   │   ├── core/config.py
│   │   ├── db/{session,init_db}.py
│   │   ├── models/
│   │   │   ├── user.py, company.py, company_member.py
│   │   │   ├── client.py, material.py, machine_config.py, piece.py
│   │   │   ├── quotation.py, quotation_item.py, quotation_event.py
│   │   │   └── stock_sheet.py, stock_reservation.py, stock_movement.py
│   │   ├── schemas/                       ← un archivo por modelo, mismo listado que arriba
│   │   ├── services/
│   │   │   ├── auth.py, company_guard.py
│   │   │   ├── dxf_analysis.py           ← analyze_dxf / get_bounding_box / extract_piece_polygon
│   │   │   ├── dxf_preview.py
│   │   │   ├── quotation_calculator.py
│   │   │   ├── quotation_events.py
│   │   │   ├── pdf_generator.py
│   │   │   ├── nesting.py                ← MaxRects-BSSF, bounding box, no persiste
│   │   │   ├── geometry.py
│   │   │   ├── stock_placement.py        ← find_placement / occupied_geometry_at (polígono real)
│   │   │   ├── stock_recommendation.py
│   │   │   ├── stock_cut.py              ← compute_remnants
│   │   │   └── stock_reservations.py     ← release_reservation
│   │   └── main.py
│   ├── tests/                             ← 22 archivos (detalle en §8)
│   ├── requirements.txt
│   └── railway.toml                       ← startCommand: alembic upgrade head && uvicorn ...
├── .github/workflows/ci.yml               ← backend (SQLite + Postgres real), frontend
└── frontend/
    └── src/
        ├── pages/                          ← 16 páginas, todas lazy-loaded
        │   ├── LoginPage, SelectCompanyPage, CreateCompanyPage, CompanyPage, EmployeesPage
        │   ├── ClientsPage, MaterialsPage, MachineConfigsPage, PiecesPage
        │   ├── QuotationsPage, QuotationDetailPage, QuoteFromCadWizardPage
        │   ├── NestingPage, StockPage, StockDetailPage
        │   └── HomePage
        ├── context/AuthContext.tsx          ← token/company en localStorage, refresh silencioso 6h
        ├── layouts/MainLayout.tsx            ← drawer permanente (desktop) / temporal (mobile)
        ├── services/                         ← un archivo por dominio, ver §10 sobre contratos
        │   ├── apiClient.ts, auth.ts, companies.ts
        │   ├── clients.ts, materials.ts, machineConfigs.ts, pieces.ts
        │   ├── quotations.ts, nesting.ts, stock.ts
        │   └── errorReporting.ts             ← observabilidad, manda errores no capturados al backend
        ├── hooks/usePaginatedList.ts          ← paginación 100% client-side, usada en todos los listados
        ├── theme/theme.ts                     ← MUI dark industrial, acento naranja #FF6B00
        ├── config/api.ts                      ← fallback local http://localhost:8000, prod usa VITE_API_BASE_URL
        └── App.tsx                            ← ProtectedRoute → RequireCompany → MainLayout;
                                                   RequireOwner adicional en /employees
```

---

## 4. Qué ya funciona

### Backend
- Auth JWT (register/login/refresh), bcrypt cost 12, tokens de 7 días
- Multiempresa completa: `Company`, `CompanyMember` (roles `owner`/`employee`, serializados en minúscula), aislamiento por `X-Company-Id` validado vía `get_current_company`/`require_owner` — **verificado endpoint por endpoint sin fugas cross-tenant**, incluyendo endpoints con múltiples IDs cruzados en un mismo payload (reservar stock, agregar ítems de cotización). `get_current_company` también exige `Company.is_active` (defensivo: hoy no existe ningún endpoint que pueda desactivar una empresa)
- CRUD completo: Clientes, Materiales, MachineConfig, Piezas, Cotizaciones, Ítems de cotización (incluye editar cantidad/margen de un ítem ya creado, no solo crear/borrar)
- Carga y análisis de DXF: longitud de corte + área (agujeros correctamente restados, círculos correctamente contados), con cobertura de tests real (LINE/LWPOLYLINE/CIRCLE, huecos, contornos múltiples, fallback manual, DXF vacío/corrupto)
- Motor de costeo (`quotation_calculator.py`, fórmula completa en §6), con tests de la fórmula, casos borde (área/longitud en 0, sin `MachineConfig`) y defensa cross-company
- Generación de PDF on-demand (`pdf_generator.py`, ReportLab) — no se persiste, `Quotation.pdf_data` existe como columna pero nada la escribe. Verificado que tolera texto libre con caracteres especiales (`&`, `<`, comillas) sin crashear
- Ciclo de vida de cotización con máquina de estados (`draft → sent → accepted → cancelled`, más `accepted → cancelled`) y log de auditoría append-only (`QuotationEvent`). `DELETE /quotations/{id}` en `draft` cascadea correctamente items+eventos en Postgres real (ver §7, corregido)
- Numeración de cotizaciones (`COT-0001...`) con reintento ante colisión concurrente (mismo patrón que `_next_stock_code`)
- Nesting de planificación: bin-packing rectangular (MaxRects-BSSF) sobre bounding box, informativo, no persiste ni reserva nada — deliberadamente separado del motor real de stock (ver más abajo)
- Stock físico real: `StockSheet` (FULL_SHEET/REMNANT), `StockReservation`, `StockMovement`; flujo completo crear → recomendar → reservar → confirmar corte → generar retazo, con geometría real (Shapely, polígonos con huecos), idempotencia verificada bajo concurrencia REAL de Postgres (no solo teoría — ver §9)
- Cancelar una cotización nunca puede dejarla `cancelled` con una reserva ya `CONSUMED`, ni bajo carrera real con `confirm-cut` (ver §7, corregido y verificado con 25 corridas concurrentes contra Postgres)
- `MachineConfig` activa única por material protegida también a nivel de índice único parcial en DB (antes solo en código de aplicación)
- Rate limiting (`slowapi`) en auth, uploads, cotizaciones, stock, admin
- Endpoint de onboarding de empresas gateado por `X-Admin-Secret` (comparación en tiempo constante), además del alta autoservicio (`POST /companies/`)
- Observabilidad: el frontend reporta errores no capturados a `POST /client-errors`

### Frontend
- Rutas protegidas con selección de empresa activa persistida en `localStorage`
- Las 16 páginas listadas en §3, todas consumiendo la API real
- Layout responsive (drawer permanente en desktop, temporal con hamburguesa en mobile)
- Paginación y búsqueda client-side en todos los listados
- Descarga de PDF autenticada (blob manual, porque `<img>`/`window.open` no mandan headers de auth)
- Reserva/confirmación de corte de stock desde `QuotationDetailPage`, con reconstrucción de estado por ítem al recargar
- `MachineConfigsPage` expone `kerf_mm`/`minimum_spacing_mm` (validación `>=0`, textos de ayuda)
- `CompanyPage` expone `minimum_remnant_area_mm2`/`width_mm`/`height_mm` (solo OWNER, con equivalencia informativa para el área)
- `QuotationDetailPage` permite editar cantidad/margen de un ítem ya creado (solo en `draft`, mismo gate que agregar), sin perder `created_at` ni duplicar el ítem
- Fallback de `VITE_API_BASE_URL` apunta a `localhost:8000` (antes, un dominio de Railway ya inexistente)

---

## 5. Qué falta / gaps confirmados

### Backend
- [ ] Tests contra un motor que enforce foreign keys reales para el resto de la suite (hoy solo los 2 archivos Postgres-only lo hacen explícitamente; SQLite ya tiene `PRAGMA foreign_keys=ON` activado globalmente en `db/session.py`, así que esto ya mejoró de forma transversal)
- [ ] Persistencia/cache de `Quotation.pdf_data` — hoy la columna existe pero nunca se escribe (decisión de producto, no un bug: el diseño on-demand actual funciona bien)

### Frontend
- [ ] Paginación server-side si el volumen crece más allá de lo cómodo en memoria
- [ ] Extraer el formulario de "agregar ítem" compartido entre el wizard y el detalle de cotización (hoy duplicado) — el diálogo de edición de ítem se hizo aparte, deliberadamente, porque los campos editables son un subconjunto distinto (sin pieza/material/recomendación de stock)
- [ ] Sin tests de componente para páginas de dominio (no hay ningún precedente en el repo de test de página/formulario CRUD; se dejó así en vez de inventar un framework nuevo solo para esta pasada de hardening)

### Decisiones de arquitectura sin resolver (no son bugs)
- Separación entre `nesting.py` (planificación rectangular, no persiste) y `stock_placement.py`/`stock_recommendation.py`/`stock_cut.py` (motor real de stock, geometría con huecos, sí persiste) — **decisión consciente, documentada**: son dos problemas distintos (planificación *what-if* vs. trazabilidad de inventario real), no una duplicación accidental. No se unificaron en esta pasada.
- Trazabilidad de corte: hoy una `StockReservation` cubre un ítem completo (independiente de su `quantity`), no cada unidad física cortada

---

## 6. Motor de costeo — fórmula real (`quotation_calculator.py`)

```
costo_material = (piece.area_mm2 / (material.sheet_width_mm * material.sheet_height_mm)) * material.sheet_cost_ars * quantity
tiempo_por_pieza_h = (piece.length_cut_mm / machine_config.cut_speed_mm_min + machine_config.setup_time_min) / 60
costo_maquina = tiempo_por_pieza_h * machine_config.machine_cost_per_hour_ars * quantity
costo_labor = costo_maquina * (machine_config.labor_percent / 100)
unit_price = ((costo_material + costo_maquina + costo_labor) / quantity) * (1 + margin_percent / 100)
total_price = unit_price * quantity
```

Nota: `setup_time_min` se cobra **por unidad** (dentro del tiempo por pieza, multiplicado por `quantity`), no una sola vez por corrida. **Comportamiento actual documentado y testeado tal cual está (`test_setup_time_is_charged_once_per_unit_not_once_per_job`), no modificado.** Pendiente de validación con Cortesar: confirmar si `setup_time_min` corresponde por unidad, por lote/tipo de pieza, o por trabajo completo.

`quotation.total_ars` se recalcula sumando **todos** los ítems cada vez que se crea/edita uno; si hay `exchange_rate` seteado, `total_usd = total_ars / exchange_rate`.

---

## 7. Bugs — hallazgos de la auditoría y su estado

| # | Severidad | Descripción | Estado |
|---|---|---|---|
| 1 | CRÍTICO | `DELETE /quotations/{id}` fallaba siempre en Postgres en estado `draft` — FK de `quotation_events` sin cascade | ✅ **Corregido** (relación ORM + migración `e5f6a8b9c0d1`, `ON DELETE CASCADE` real). Verificado contra Postgres real, incluida la cascada de items+eventos |
| 1b | CRÍTICO (encontrado corrigiendo #1) | Mismo patrón en `stock_reservations.quotation_item_id` — bloqueaba borrar un ítem con una reserva asociada | ✅ **Corregido** (migración `f6a8b9c0d1e2`, `ON DELETE SET NULL` — la reserva es historial, sobrevive al ítem) |
| 2 | ALTO | Cancelar cotización en carrera con `confirm-cut` de una reserva propia podía dejar estado inconsistente sin registro | ✅ **Corregido** (`release_quotation_reservations`, aborta+rollback+409 si alguna reserva está o queda `CONSUMED`). Verificado con 25 corridas concurrentes reales contra Postgres, alternando qué request gana — nunca se observó el estado prohibido |
| 3 | ALTO | UI no exponía `kerf_mm`/`minimum_spacing_mm` | ✅ **Corregido** (`MachineConfigsPage.tsx`) |
| 4 | ALTO | UI no exponía `minimum_remnant_*` de empresa | ✅ **Corregido** (`CompanyPage.tsx`) |
| 5 | ALTO | No se podía editar un ítem de cotización desde la UI | ✅ **Corregido** (`QuotationDetailPage.tsx`, gateado a `draft`) |
| 6 | MEDIO | `_next_number()` sin reintento ante colisión concurrente | ✅ **Corregido** (mismo patrón que `_next_stock_code`) |
| 7 | MEDIO | Invariante "una `MachineConfig` activa" sin protección en DB | ✅ **Corregido** (índice único parcial `uq_machine_configs_active_per_material`, migración `a8b9c0d1e2f3`) |
| 8 (nuevo) | BAJO | `routes_pieces.py` crasheaba (500 sin traceback expuesto, pero sin loguear tampoco) al subir un DXF con extensión inválida — `extra={"filename": ...}` colisiona con un atributo reservado de `LogRecord` | ✅ **Corregido**, encontrado escribiendo tests de DXF |
| 9 (nuevo) | BAJO | `_require_admin_secret` comparaba con `!=` en vez de tiempo constante | ✅ **Corregido** (`hmac.compare_digest`) |
| — | — | `Company.is_active` no se validaba en `get_current_company` | ✅ **Corregido**, defensivo — hoy no existe ningún endpoint que pueda desactivar una empresa |
| — | PENDIENTE DE NEGOCIO | `setup_time_min` por unidad vs. por corrida — comportamiento actual preservado y testeado, no se decidió unilateralmente | Ver §6, confirmar con Cortesar |

---

## 8. Tests — estado real

**Backend**: 133 tests pasando + 2 archivos que solo corren con `DATABASE_URL` apuntando a Postgres real (`test_postgres_hardening_integration.py`, `test_quotation_cancel_confirm_race_postgres.py` — documentado en cada uno cómo ejecutarlos; el CI sí los corre). 22 archivos de test en total. Cobertura nueva en esta pasada: `dxf_analysis.py` (18 tests, antes 0), `quotation_calculator.py` (13 tests, antes 0 dedicados), `pdf_generator.py` (7 tests, antes 0), `DELETE /quotations/{id}` con FK reales, la invariante cancelación/confirm-cut (SQLite secuencial + Postgres concurrente real), numeración concurrente, `MachineConfig` activa única (incluida la constraint de DB bypaseando el chequeo de aplicación), E2E completo hasta retazo+trazabilidad+PDF, y un caso de nesting que no encastra en ninguna orientación.

**SQLite ahora enforce foreign keys** (`PRAGMA foreign_keys=ON` en `db/session.py`, sin efecto en Postgres que ya las enforce siempre) — este tipo de bug (el #1/#1b de arriba) no puede volver a quedar invisible en la suite normal.

**Frontend**: 18 tests, 4 archivos (`AuthContext`, `LoginPage`, `apiClient`, `usePaginatedList`) — sin cobertura de componente de ninguna página de dominio (no hay precedente en el repo; no se inventó un framework nuevo solo para esta pasada).

---

## 9. Concurrencia — verificado contra el comportamiento real de Postgres (no solo SQLite)

- **Reserva de stock** y **confirmación de corte**: protegidos en dos capas (UPDATE condicional con rowcount + índice único parcial). Verificado que el perdedor de una carrera real recibe 409, no un estado corrupto.
- **Cancelación de cotización vs. confirmación de corte concurrente**: corregido y verificado con concurrencia real (ver §7.2) — confirmado empíricamente que `UPDATE ... WHERE status='ACTIVE'` contra la misma fila desde dos transacciones serializa correctamente bajo READ COMMITTED: la que pierde el lock espera, y al desbloquear re-evalúa su condición contra el valor ya comiteado.
- **Numeración de cotizaciones**: protegida con reintento (§7.6).
- **Reactivación de `MachineConfig`**: protegida con índice único parcial (§7.7).

---

## 10. Contratos frontend ↔ backend — estado real

Verificado campo por campo (Pydantic vs. TypeScript) para Materials, MachineConfigs, Pieces, Quotations, QuotationItems, Stock, StockRecommendation, StockReservation, Company, CompanyMember. **Alineado por completo** — las tres discrepancias reales encontradas en la auditoría (`kerf_mm`/`minimum_spacing_mm`, `minimum_remnant_*`, edición de ítems) ya se corrigieron (§7).

---

## 11. Historial reciente relevante

- **2026-08-25 (tarde)**: hardening autónomo completo tras la auditoría — todos los hallazgos CRÍTICO/ALTO/MEDIO corregidos y validados contra Postgres real (no solo SQLite), cobertura de tests agregada en DXF/costeo/PDF/E2E, contratos frontend↔backend alineados, CI agregado. Este documento es su resultado.
- **2026-08-25 (mañana)**: corregido `analyze_dxf` (sumaba área de agujeros en vez de restarla, círculos no contaban para área) — desalineaba el costo de material cotizado contra el área real descontada del stock. Backfill aplicado a las piezas existentes en producción; ninguna cotización ya emitida fue modificada. Auditoría completa del sistema.
- **2026-08-19 al 21**: multiempresa, nesting real (bin-packing), stock físico + retazos + reservas + movimientos, auditoría de cotizaciones (`QuotationEvent`), refresh de sesión silencioso, observabilidad, layout responsive.

---

## Limitaciones conocidas / decisiones pendientes

- `setup_time_min` por unidad vs. por corrida completa — pendiente de validación con Cortesar (ver §6). Comportamiento actual preservado y testeado explícitamente, no se asumió ni un lado ni el otro.
- Nesting de planificación (`nesting.py`, bin-packing rectangular sobre bounding box) queda deliberadamente separado del motor real de stock (`stock_placement.py`/`stock_recommendation.py`/`stock_cut.py`, geometría real con huecos) — son dos problemas distintos (planificación *what-if* vs. trazabilidad de inventario), no se unificaron.
- Trazabilidad de reserva de stock: hoy es por ítem de cotización, no por unidad física individual cortada (un ítem con `quantity=5` genera una sola `StockReservation`, no cinco).
- Paginación 100% client-side en todos los listados — no hay paginación server-side en ningún endpoint.
- README.md nuevo agregado en esta pasada (antes prácticamente vacío) — ver raíz del repo.
- CLAUDE.md sigue vigente en sus principios de arquitectura/trabajo y no requiere reescritura.
- Ningún secreto ni credencial fue encontrado en el historial completo de git (`git log --all`) ni en el árbol de trabajo actual — el único script con credenciales de admin en texto plano (`test_railway.py`) nunca llegó a commitearse, solo existe localmente sin trackear.
