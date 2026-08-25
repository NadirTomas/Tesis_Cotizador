# PROJECT_CONTEXT.md

## Mantenimiento del archivo

Este archivo debe mantenerse actualizado.

Reglas:
- Cada cambio importante en el sistema debe reflejarse aquí
- No reescribir todo el archivo, solo modificar lo necesario
- Mantener consistencia con el estado real del proyecto
- No inventar funcionalidades

> Reescrito por completo el 2026-08-25 tras una auditoría integral de `main`. La versión anterior (7 de abril) describía una arquitectura previa a multiempresa/stock/nesting real y ya no era confiable como fuente de verdad. Repositorio canónico: `NadirTomas/Tesis_Cotizador`, rama `main`. Nombre funcional del sistema: **CotizaLaser**. El repositorio `NadirTomas/CotizaLaser` es obsoleto y no debe usarse como referencia.

## 1. Estado actual

Sistema en desarrollo activo, multiempresa, deployado en Railway con PostgreSQL. Cubre el flujo completo: cliente → material/máquina → pieza DXF → cotización → aceptación → reserva de stock → confirmación de corte → retazo, con auditoría de eventos, PDF on-demand, y aislamiento de datos por empresa verificado endpoint por endpoint.

**Deploy Railway** (proyecto `Tesis_Cotizador`, 3 servicios en el mismo environment `production`):
- Frontend: `frontend-production-ebde2.up.railway.app`
- Backend: `tesiscotizador-production.up.railway.app`
- Postgres: red privada (`postgres.railway.internal`), sin proxy TCP público por defecto
- Para crear el primer usuario: `POST /auth/register`, luego crear una empresa con `POST /companies/` (el creador queda como OWNER) o vincularse a una existente por invitación

**Conocido y con bug abierto (ver §7):** `DELETE /quotations/{id}` falla siempre en Postgres para cotizaciones en `draft` por una foreign key sin cascada hacia `quotation_events`. El frontend no expone ningún control que dispare este endpoint hoy, así que no genera incidentes activos, pero está roto si se lo invoca directamente.

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
│   │   └── versions/            ← 12 migraciones, un solo head (d4e5f6a8b9c0), cadena lineal.
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
│   ├── tests/                             ← 79 tests, 13 archivos (detalle en §8)
│   ├── requirements.txt
│   └── railway.toml                       ← startCommand: alembic upgrade head && uvicorn ...
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
        └── App.tsx                            ← ProtectedRoute → RequireCompany → MainLayout;
                                                   RequireOwner adicional en /employees
```

---

## 4. Qué ya funciona

### Backend
- Auth JWT (register/login/refresh), bcrypt cost 12, tokens de 7 días
- Multiempresa completa: `Company`, `CompanyMember` (roles `owner`/`employee`, serializados en minúscula), aislamiento por `X-Company-Id` validado vía `get_current_company`/`require_owner` — **verificado endpoint por endpoint sin fugas cross-tenant**, incluyendo endpoints con múltiples IDs cruzados en un mismo payload (reservar stock, agregar ítems de cotización)
- CRUD completo: Clientes, Materiales, MachineConfig, Piezas, Cotizaciones, Ítems de cotización
- Carga y análisis de DXF: longitud de corte + área (agujeros correctamente restados, círculos correctamente contados — corregido 2026-08-25, ver §11)
- Motor de costeo (`quotation_calculator.py`, fórmula completa en §6)
- Generación de PDF on-demand (`pdf_generator.py`, ReportLab) — no se persiste, `Quotation.pdf_data` existe como columna pero nada la escribe
- Ciclo de vida de cotización con máquina de estados (`draft → sent → accepted → cancelled`, más `accepted → cancelled`) y log de auditoría append-only (`QuotationEvent`)
- Nesting de planificación: bin-packing rectangular (MaxRects-BSSF) sobre bounding box, informativo, no persiste ni reserva nada
- Stock físico real: `StockSheet` (FULL_SHEET/REMNANT), `StockReservation`, `StockMovement`; flujo completo crear → recomendar → reservar → confirmar corte → generar retazo, con geometría real (Shapely, polígonos con huecos), idempotencia verificada bajo concurrencia real de Postgres (UPDATE condicional + índice único parcial)
- Rate limiting (`slowapi`) en auth, uploads, cotizaciones, stock, admin
- Endpoint de onboarding de empresas gateado por `X-Admin-Secret`, además del alta autoservicio (`POST /companies/`)
- Observabilidad: el frontend reporta errores no capturados a `POST /client-errors`

### Frontend
- Rutas protegidas con selección de empresa activa persistida en `localStorage`
- Las 16 páginas listadas en §3, todas consumiendo la API real
- Layout responsive (drawer permanente en desktop, temporal con hamburguesa en mobile)
- Paginación y búsqueda client-side en todos los listados
- Descarga de PDF autenticada (blob manual, porque `<img>`/`window.open` no mandan headers de auth)
- Reserva/confirmación de corte de stock desde `QuotationDetailPage`, con reconstrucción de estado por ítem al recargar

---

## 5. Qué falta / gaps confirmados

### Backend
- [ ] Fix del bug crítico: cascade de `quotation_events` al borrar una cotización (§7)
- [ ] Manejo del retorno de `release_reservation` al cancelar una cotización con reservas en carrera con un `confirm-cut` (§7)
- [ ] Reintento ante colisión de `_next_number()` de cotizaciones (mismo patrón que `_next_stock_code`)
- [ ] Índice único parcial para "una `MachineConfig` activa por material" (hoy solo protegido en código de aplicación)
- [ ] Tests unitarios de `dxf_analysis.py` y `quotation_calculator.py` (cero hoy)
- [ ] Tests contra un motor que enforce foreign keys reales (Postgres, o SQLite con `PRAGMA foreign_keys=ON`) — el bug crítico de §7 era invisible en el test suite actual por esta razón
- [ ] CI/CD — no hay `.github/workflows/`, el auto-deploy de Railway no corre tests antes de producción

### Frontend
- [ ] Exponer `kerf_mm`/`minimum_spacing_mm` en `MachineConfigsPage` (el backend los usa activamente, el tipo TS ni siquiera los declara)
- [ ] Exponer `minimum_remnant_area_mm2`/`width_mm`/`height_mm` en `CompanyPage`
- [ ] Editar ítems de cotización ya creados (`PUT /quotation-items/{id}` existe y funciona en el backend; el frontend solo puede borrar y recrear)
- [ ] Paginación server-side si el volumen crece más allá de lo cómodo en memoria
- [ ] Extraer el formulario de "agregar ítem" compartido entre el wizard y el detalle de cotización (hoy duplicado)

### Decisiones de arquitectura sin resolver (no son bugs)
- Separación entre `nesting.py` (planificación rectangular, no persiste) y `stock_placement.py`/`stock_recommendation.py`/`stock_cut.py` (motor real de stock, geometría con huecos, sí persiste) — documentar como decisión consciente o unificar
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

Nota: `setup_time_min` se cobra **por unidad** (dentro del tiempo por pieza, multiplicado por `quantity`), no una sola vez por corrida — confirmar si es la regla de negocio deseada antes de asumir que es un bug.

`quotation.total_ars` se recalcula sumando **todos** los ítems cada vez que se crea/edita uno; si hay `exchange_rate` seteado, `total_usd = total_ars / exchange_rate`.

---

## 7. Bugs conocidos abiertos (severidad, ver informe de auditoría completo para detalle)

| # | Severidad | Descripción | Archivo |
|---|---|---|---|
| 1 | **CRÍTICO** | `DELETE /quotations/{id}` falla siempre en Postgres en estado `draft` — FK de `quotation_events` sin cascade | `routes_quotations.py:193-212`, `models/quotation.py` |
| 2 | **ALTO** | Cancelar cotización en carrera con `confirm-cut` de una reserva propia deja estado inconsistente sin registro | `routes_quotations.py:242-249` |
| 3 | **ALTO** | UI no expone `kerf_mm`/`minimum_spacing_mm` | `MachineConfigsPage.tsx`, `machineConfigs.ts` |
| 4 | **ALTO** | UI no expone `minimum_remnant_*` de empresa | `companies.ts`, `CompanyPage.tsx` |
| 5 | **ALTO** | No se puede editar un ítem de cotización desde la UI (endpoint backend sí existe) | `quotations.ts` |
| 6 | MEDIO | `_next_number()` sin reintento ante colisión concurrente | `routes_quotations.py:77-79` |
| 7 | MEDIO | Reactivación de `MachineConfig` sin lock, invariante "una activa" puede romperse bajo concurrencia | `routes_machine_configs.py:100-105` |

---

## 8. Tests — estado real

**Backend**: 79 tests en 13 archivos. Fuertemente concentrados en stock (42, el mejor cubierto) y control de acceso/multiempresa (16). **Cero tests** de `dxf_analysis.py`, `quotation_calculator.py` aislado, `pdf_generator.py`, o del endpoint `DELETE /quotations/{id}` (que resultó estar roto — ver §7.1). Los tests corren contra SQLite, que no enforce foreign keys por defecto: cualquier bug que dependa de ese enforcement es invisible en el suite actual.

**Frontend**: 4 archivos (`AuthContext`, `LoginPage`, `apiClient`, `usePaginatedList`) — sin cobertura de ninguna página de dominio.

**Importante**: que los tests existentes pasen no implica que el sistema esté libre de bugs de este calibre — el bug crítico de §7.1 coexistía con un suite "verde".

---

## 9. Concurrencia — verificado contra el comportamiento real de Postgres (no solo SQLite)

- **Reserva de stock** y **confirmación de corte**: protegidos correctamente en dos capas (UPDATE condicional con rowcount + índice único parcial). Verificado que el perdedor de una carrera real recibe 409, no un estado corrupto.
- **Cancelación de cotización vs. confirmación de corte concurrente**: ventana de inconsistencia real, ver bug §7.2.
- **Numeración de cotizaciones**: sin protección, ver bug §7.6.
- **Reactivación de `MachineConfig`**: sin protección, ver bug §7.7.

---

## 10. Contratos frontend ↔ backend — estado real

Verificado campo por campo (Pydantic vs. TypeScript) para Materials, MachineConfigs, Pieces, Quotations, QuotationItems, Stock, StockRecommendation, StockReservation, Company, CompanyMember. La mayoría está perfectamente alineada (Stock es el módulo mejor tipado, con unions literales exactos). Discrepancias reales encontradas: `kerf_mm`/`minimum_spacing_mm` ausentes en los tipos TS de MachineConfig, `minimum_remnant_*` ausentes en los tipos TS de Company, y `PUT /quotation-items/{id}` sin consumidor en frontend — las tres ya listadas en §7 como bugs de producto, no de tipos.

---

## 11. Historial reciente relevante

- **2026-08-25**: corregido `analyze_dxf` (sumaba área de agujeros en vez de restarla, círculos no contaban para área) — desalineaba el costo de material cotizado contra el área real descontada del stock. Backfill aplicado a las piezas existentes en producción; ninguna cotización ya emitida fue modificada. Auditoría completa del sistema realizada el mismo día (este documento es su resultado).
- **2026-08-19 al 21**: multiempresa, nesting real (bin-packing), stock físico + retazos + reservas + movimientos, auditoría de cotizaciones (`QuotationEvent`), refresh de sesión silencioso, observabilidad, layout responsive — todo el estado descrito en este documento.

---

## Notas y pendientes sin resolver

- README.md está prácticamente vacío (placeholder autogenerado) — no se usa como documentación real, este archivo es la fuente canónica.
- CLAUDE.md sigue vigente en sus principios de arquitectura/trabajo y no requiere reescritura.
- Ningún secreto ni credencial fue encontrado en el historial completo de git (`git log --all`) — el único script con credenciales de admin en texto plano (`test_railway.py`) nunca llegó a commitearse, solo existe localmente sin trackear.
