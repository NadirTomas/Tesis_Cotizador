# PROJECT_CONTEXT.md

## Mantenimiento del archivo

Este archivo debe mantenerse actualizado.

Reglas:
- Cada cambio importante en el sistema debe reflejarse aquí
- No reescribir todo el archivo, solo modificar lo necesario
- Mantener consistencia con el estado real del proyecto
- No inventar funcionalidades

## 1. Estado actual

Proyecto en desarrollo activo. Backend funcional con lógica de negocio implementada, deployado en Railway con PostgreSQL. Sistema de migraciones Alembic en producción, autenticación JWT en todos los endpoints de modificación, auditoría de creador en todas las entidades. Frontend completo con integración a la API, paginación y búsqueda en todos los listados, todas las páginas principales funcionales.

**Deploy Railway:**
- Frontend: https://cotizalaser.up.railway.app
- Backend: https://backend-production-3f21c.up.railway.app
- Para crear el primer usuario: usar `/docs` → `POST /auth/register`

---

## 2. Tecnologías

### Backend
| Tecnología | Versión / Notas |
|---|---|
| Python | — |
| FastAPI | Framework HTTP |
| SQLAlchemy | ORM |
| PostgreSQL | Base de datos (Railway) |
| Pydantic / pydantic-settings | Validación y configuración |
| ezdxf | Análisis de archivos DXF |
| ReportLab | Generación de PDFs |
| Uvicorn | Servidor ASGI |
| PyJWT[crypto] | JWT (reemplaza python-jose por mantenimiento activo y sin CVEs) |
| bcrypt | Hash seguro de passwords (directo, sin passlib) |
| email-validator | Validación de emails para Pydantic |
| psycopg2-binary | Driver PostgreSQL |
| pytest + httpx | Testing |

### Frontend
| Tecnología | Versión |
|---|---|
| React | 19.2.0 |
| TypeScript | — |
| Vite | Bundler |
| React Router | v7 |
| Material UI (MUI) | v7 |
| Emotion | CSS-in-JS |

---

## 3. Estructura

```
CotizadorLaser/
├── CLAUDE.md
├── PROJECT_CONTEXT.md
├── backend/
│   ├── alembic/
│   │   ├── env.py                      ← Configurado para importar modelos y DATABASE_URL
│   │   ├── alembic.ini
│   │   ├── versions/
│   │   │   ├── f20b2e6e7788_initial_schema.py      ← File storage migration (dxf_path → dxf_data)
│   │   │   └── ad4a02af2953_add_audit_fields.py    ← Audit fields (created_at, updated_at, created_by_id)
│   │   └── script.py.mako
│   ├── app/
│   │   ├── api/v1/
│   │   │   ├── routes_health.py
│   │   │   ├── routes_auth.py
│   │   │   ├── routes_materials.py
│   │   │   ├── routes_clients.py
│   │   │   ├── routes_machine_configs.py
│   │   │   ├── routes_pieces.py
│   │   │   ├── routes_quotations.py
│   │   │   └── routes_quotation_items.py
│   │   ├── core/
│   │   │   └── config.py
│   │   ├── db/
│   │   │   ├── session.py
│   │   │   └── init_db.py
│   │   ├── models/
│   │   │   ├── material.py
│   │   │   ├── client.py
│   │   │   ├── piece.py
│   │   │   ├── machine_config.py
│   │   │   ├── quotation.py
│   │   │   ├── quotation_item.py
│   │   │   ├── company.py
│   │   │   └── user.py
│   │   ├── schemas/
│   │   │   ├── material.py
│   │   │   ├── client.py
│   │   │   ├── piece.py
│   │   │   ├── machine_config.py
│   │   │   ├── quotation.py
│   │   │   ├── quotation_item.py
│   │   │   └── auth.py
│   │   ├── services/
│   │   │   ├── dxf_analysis.py
│   │   │   ├── quotation_calculator.py
│   │   │   ├── pdf_generator.py
│   │   │   └── auth.py
│   │   ├── main.py
│   │   └── __init__.py
│   ├── data/
│   │   └── dxf/
│   ├── requirements.txt
│   ├── Procfile                        ← Incluye 'alembic upgrade head' antes de uvicorn
│   ├── railway.toml                    ← Incluye 'alembic upgrade head' en startCommand
│   └── .env.example
└── frontend/
    ├── src/
    │   ├── pages/
    │   │   ├── HomePage.tsx
    │   │   ├── LoginPage.tsx
    │   │   ├── MaterialsPage.tsx         ← con búsqueda + paginación
    │   │   ├── ClientsPage.tsx           ← con búsqueda + paginación
    │   │   ├── PiecesPage.tsx            ← con búsqueda + paginación
    │   │   ├── QuotationsPage.tsx        ← con filtros + paginación
    │   │   ├── QuotationDetailPage.tsx
    │   │   ├── MachineConfigsPage.tsx    ← con paginación
    │   │   └── QuoteFromCadWizardPage.tsx
    │   ├── hooks/
    │   │   └── usePaginatedList.ts       ← Hook reutilizable para paginación client-side
    │   ├── layouts/
    │   │   └── MainLayout.tsx           ← sidebar permanente + botón cerrar sesión
    │   ├── theme/
    │   │   └── theme.ts                 ← tema MUI dark personalizado
    │   ├── context/
    │   │   └── AuthContext.tsx          ← token en localStorage, login/logout global
    │   ├── services/
    │   │   ├── auth.ts
    │   │   ├── clients.ts
    │   │   ├── pieces.ts
    │   │   ├── materials.ts
    │   │   ├── quotations.ts
    │   │   └── machineConfigs.ts
    │   ├── config/
    │   │   └── api.ts
    │   ├── App.tsx                      ← incluye ProtectedRoute
    │   ├── index.css                    ← fuentes Google + scrollbar custom
    │   └── main.tsx                     ← ThemeProvider + CssBaseline + AuthProvider
    ├── package.json
    └── .env.example
```

---

## 4. Qué ya funciona

### Backend
- [x] CRUD completo: Materiales, Clientes, Piezas, MachineConfigs
- [x] CRUD completo: Presupuestos (Quotations) e Ítems de presupuesto
- [x] Carga y análisis de archivos DXF (`dxf_analysis.py`)
  - Calcula longitud de corte y área desde LINEs, LWPOLYLINEs y CIRCLEs
  - Fallback de lectura de texto si ezdxf falla
- [x] Motor de cálculo de costos (`quotation_calculator.py`)
  - Costo de material: `(area_pieza / area_chapa) * costo_chapa`
  - Costo de máquina: `(tiempo_corte + setup_time) / 60 * costo_hora`
  - Costo de mano de obra: 30% del costo de máquina (hardcodeado)
  - Precio unitario: `(costo_base / cantidad) * (1 + margen%)`
  - Actualización automática de totales del presupuesto
- [x] Generación de PDF (`pdf_generator.py`) con ReportLab
  - Encabezado, datos de cliente, tabla de ítems, totales ARS/USD, validez
- [x] Modelo `CompanyConfig` definido (sin endpoints expuestos aún)
- [x] Health check endpoint
- [x] Configuración vía variables de entorno (COTIZALASER_ prefix y valores default)
  - MAX_DXF_SIZE (default 10MB), MAX_LOGO_SIZE (default 5MB), LABOR_COST_PERCENT (default 30%)
- [x] Base de datos PostgreSQL en Railway, inicializada con `create_all` al arrancar
- [x] Logging estructurado en JSON para todos los eventos críticos (auth, uploads)
- [x] Rate limiting en endpoints sensibles (auth 10/min, uploads 5/min)
- [x] Autenticación JWT: `POST /auth/register` y `POST /auth/login` (bcrypt + PyJWT)
  - Emails normalizados a minúsculas para evitar duplicados y case-insensitivity
  - Bcrypt directo sin passlib (conflictos en Railway resueltos)
  - Todos los endpoints POST/PUT/DELETE requieren token JWT válido
  - GET endpoints públicos (sin autenticación)
- [x] Modelo `User` (email, hashed_password, is_active)
- [x] Middleware para confiar en `X-Forwarded-Proto` de Railway (fix HTTPS proxy)
- [x] Sistema de migraciones Alembic
  - Migraciones automáticas al arrancar (`alembic upgrade head` en startCommand)
  - Inicial migration: captura schema actual (BYTEA para files)
  - Audit migration: agrega `created_at`, `updated_at`, `created_by_id`
  - Versionamiento de schema seguro para producción
- [x] Auditoría en todas las entidades
  - Campos: `created_at`, `updated_at` (DateTime con servidor defaults)
  - Campo `created_by_id` (FK a users.id) en: Client, Material, Piece, MachineConfig, Quotation, QuotationItem, User
  - Autenticación: `get_current_user()` devuelve `user_id` (int), todos los POST/PUT guardan `created_by_id`
  - Todos los campos son nullable para compatibilidad con registros existentes

### Frontend
- [x] Rutas configuradas (`/`, `/pieces`, `/clients`, `/quotations`, `/quotations/:id`, `/materials`, `/quotes/new-from-cad`, `/login`)
- [x] Paginación client-side en todos los listados (usePaginatedList hook)
- [x] Búsqueda en: Clients, Materials, Pieces, Quotations
- [x] TablePagination en todas las páginas (10/20/50 rows per page)
- [x] Sistema de diseño: tema MUI dark en `theme/theme.ts` (naranja #FF6B00, fondo #0A0B0E, fuentes Barlow Condensed + DM Sans + JetBrains Mono)
- [x] Layout con sidebar permanente (`MainLayout.tsx`) — reemplaza AppBar; incluye nav items con indicador activo y CTA "Nueva Cotización"
- [x] `HomePage` rediseñada — CTA card destacada + 4 tarjetas de navegación con acento por sección
- [x] `LoginPage` mejorada — logo destacado con animación pulse, efectos visuales (orbs decorativos), mejor jerarquía, animaciones suaves, responsiva mobile-first
- [x] `config/api.ts` con `API_BASE_URL` configurable por env

---

## 5. Qué falta

### Backend
- [x] ✓ Migraciones con Alembic (inicial + audit fields, versionamiento production-ready)
  - Ejecutadas automáticamente en Railway con `alembic upgrade head`
  - Manejo seguro de schema en PostgreSQL sin perder datos
- [x] ✓ Endpoints para `CompanyConfig` (GET + PUT expuestos)
- [x] ✓ `labor_percent` configurable por material en `MachineConfig`
- [x] ✓ Auditoría completa (created_by_id + timestamps en todas las entidades)
- [x] ✓ Filtros y búsqueda en listados (implementados client-side en frontend)
- [x] ✓ Autenticación JWT completa (login/logout, ProtectedRoute, token en requests)
- [x] ✓ Todos los endpoints POST/PUT/DELETE requieren autenticación
- [x] ✓ Logging estructurado JSON para Railway
- [ ] Tests más completos (unitarios para servicios de cálculo)
- [ ] Paginación en endpoints GET (para futura escalabilidad; hoy client-side es suficiente)

### Frontend
- [x] Integración con la API del backend — todas las páginas consumen endpoints reales
- [x] Servicios de API creados (`services/materials.ts`, `clients.ts`, `pieces.ts`, `machineConfigs.ts`, `quotations.ts`)
- [x] `MaterialsPage` — CRUD funcional (tabla + modal crear/editar + confirmar eliminación) + búsqueda + paginación
- [x] `ClientsPage` — CRUD funcional (tabla + modal crear/editar + confirmar eliminación) + búsqueda + paginación
- [x] `PiecesPage` — funcional: tabla real, importar DXF (create → upload), nueva pieza manual, editar, eliminar + búsqueda + paginación
- [x] `QuotationsPage` — lista con cliente, fecha, estado, total ARS, acciones (ver detalle, PDF) + filtros + paginación
- [x] `QuoteFromCadWizardPage` — wizard 3 pasos: datos → agregar piezas con cálculo automático → resumen + PDF
- [x] `QuotationDetailPage` — nueva página `/quotations/:id`: ver ítems con desglose de costos, agregar ítems, descargar PDF
- [x] Formularios de creación/edición con validación básica
- [x] Manejo de errores y estados de carga en todas las páginas
- [x] Notificaciones / feedback al usuario (toasts con Snackbar)
- [x] Descarga de PDF desde frontend (window.open al endpoint del backend)
- [x] `MachineConfigsPage` — CRUD funcional en `/machine-configs`, con `labor_percent` configurable por material + paginación
- [x] `CompanyPage` — página `/company` para datos del taller (nombre, razón social, CUIT, contacto)
- [x] `CompanyConfig` — endpoints GET + PUT (singleton), usa los datos en el PDF
- [x] **Logo de empresa** — `POST /company/logo` sube y guarda en PostgreSQL (BYTEA), `GET /company/logo` sirve imagen
  - Formatos: PNG, JPG, SVG, WEBP (máximo 5MB, configurable)
  - Persistente en Railway (no se pierde en redeploy)
- [x] **DXF en DB** — `POST /pieces/{id}/upload-dxf` guarda archivo DXF y PNG preview en PostgreSQL (BYTEA)
  - Máximo 10MB por archivo DXF (configurable)
  - Persistente en Railway
- [x] **Preview de piezas DXF** — `GET /pieces/{id}/preview` sirve PNG desde DB
- [x] **PDFs de cotización** — `GET /quotations/{id}/pdf` genera en memoria y sirve sin guardar en filesystem
  - Reutiliza generator existente con tempfile
  - Sin ocupar espacio en DB
- [x] **Paginación y búsqueda** — Hook `usePaginatedList` reutilizable, busca en: clients, materials, pieces, quotations

---

## 6. Flujo actual (end-to-end esperado)

```
1. Configuración previa (admin)
   ├── Crear Material (nombre, espesor, tamaño chapa, costo ARS)
   └── Crear MachineConfig por material (velocidad mm/min, costo/hora, setup)

2. Crear Cliente
   └── Nombre, CUIT, contacto, dirección

3. Cargar Pieza
   ├── Subir archivo DXF → POST /pieces/{id}/upload-dxf
   └── Backend extrae: longitud_corte_mm, area_mm2

4. Crear Presupuesto (Quotation)
   ├── Seleccionar cliente
   ├── Definir moneda, tipo de cambio (se guarda en el momento)
   └── Fechas de emisión y vencimiento

5. Agregar Ítems al Presupuesto
   ├── Seleccionar pieza, material, cantidad, margen %
   └── Backend calcula automáticamente:
       ├── costo_material_ars
       ├── costo_machine_ars
       ├── costo_labor_ars  (30% de máquina — pendiente de hacer configurable)
       ├── unit_price_ars
       └── total_price_ars
       → Actualiza total del presupuesto

6. Generar PDF
   └── GET /quotations/{id}/pdf → descarga PDF con todos los datos
```

---

## Notas y pendientes sin resolver

### Problemas resueltos en Railway
- ✓ **Mixed Content / HTTPS**: Frontend en HTTPS redirigía al backend en HTTP
  - Solución: Middleware `TrustProxyHeadersMiddleware` que lee `X-Forwarded-Proto` header
- ✓ **CORS**: FRONTEND_URL variable seteada para permitir requests desde dominio de producción
- ✓ **Bcrypt en Railway**: `passlib` tenía conflictos con `bcrypt` moderno
  - Solución: Usar `bcrypt` directamente
- ✓ **Persistencia de archivos**: Logos/DXF/PDFs se guardaban en filesystem efímero (se pierden en redeploy)
  - Solución: Guardar en PostgreSQL como BYTEA (logos en CompanyConfig, DXF/previews en Piece)
  - PDFs: Generados on-demand en memoria (no necesitan persistencia)

### Cambios de modelo recientes (Railway-ready)
- **Piece**: dxf_path/preview_path → dxf_data (BYTEA), preview_data (BYTEA), dxf_filename
- **CompanyConfig**: logo_path → logo_data (BYTEA), logo_filename
- **Quotation**: agregó pdf_data (BYTEA, opcional, no usado hoy)

### Cambios recientes implementados (7 de abril 2026)
- ✓ **Alembic y migraciones**: Implemented two migrations
  - `f20b2e6e7788_initial_schema`: Migra file storage (dxf_path → dxf_data, etc.)
  - `ad4a02af2953_add_audit_fields`: Agrega created_at, updated_at, created_by_id
  - Configurado en railway.toml/Procfile para ejecutar automáticamente
- ✓ **Paginación client-side**: Hook usePaginatedList en todos los listados (10/20/50 rows)
- ✓ **Búsqueda/Filtros**: Implementados en ClientsPage, MaterialsPage, PiecesPage, QuotationsPage
- ✓ **Auditoría**: Todos los modelos tienen created_by_id, get_current_user devuelve int (user_id)

### Cambios recientes de seguridad
- ✓ **Autenticación JWT en endpoints**: POST/PUT/DELETE requieren bearer token (implementado en routes_pieces, routes_quotations)
- ✓ **SECRET_KEY obligatorio**: Ahora sin default inseguro, requiere variable de entorno en producción

### Pendientes de seguridad y arquitectura

**URGENTES (antes de producción):**
1. ✓ **Proteger todos los endpoints de modificación**
   - ✓ Todos los endpoints POST/PUT/DELETE en todas las rutas requieren JWT
   - ✓ Implementado en: routes_clients, routes_materials, routes_machine_configs, routes_company, routes_quotation_items, routes_nesting
   - Patrón usado: `current_user: str = Depends(get_current_user)` en todas las mutaciones

2. **Secrets management**
   - ✓ SECRET_KEY requiere env var (sin defaults inseguros)
   - ✓ Verificado y configurado en Railway Variables

3. ✓ **Logging estructurado**
   - ✓ Logs JSON de: auth (login/register attempts), DXF uploads, logo uploads
   - ✓ Formato JSON con timestamp, level, logger, message, extras (user, file_size, etc)
   - ✓ Supprimidos logs verbosos de SQLAlchemy y uvicorn
   - ✓ Configurado al startup de la app

4. ✓ **Rate limiting**
   - ✓ Implementado con `slowapi`
   - ✓ Auth endpoints: 10 requests/min por IP (brute force protection)
   - ✓ DXF upload: 5 requests/min por IP
   - ✓ Logo upload: 5 requests/min por IP

**Mejoras de arquitectura (post-MVP):**
5. ✓ **Configuración dinámica**
   - ✓ MAX_DXF_SIZE, MAX_LOGO_SIZE → env vars (defaults 10MB, 5MB)
   - ✓ LABOR_COST_PERCENT → env var (default 30%, pero MachineConfig permite override por material)
   - ✓ Otros defaults configurables via Settings

6. **Validaciones robustas**
   - Checks de integridad referencial
   - Prevenir cotizaciones sin cliente válido
   - Consistencia en PUT/POST

7. **Error handling**
   - Errores específicos en lugar de 500 genérico
   - Stack traces en logs pero respuestas limpias al cliente

8. ✓ **Sistema de migraciones con Alembic**
   - ✓ Alembic inicializado y configurado para PostgreSQL
   - ✓ Migraciones automáticas al arrancar (startCommand en Railway/Procfile)
   - ✓ Schema versionado y seguro para cambios en producción
   - ✓ init_db.py solo usa `create_all` en SQLite local (dev), Alembic maneja PostgreSQL

9. ✓ **Auditoría completa**
   - ✓ `created_by_id` (int FK a users.id) en todas las entidades
   - ✓ `created_at` y `updated_at` en todos los modelos (server defaults)
   - ✓ GET_CURRENT_USER devuelve user_id para rastrear creador
   - ✓ Todos los POST/PUT endpoints guardan quién hizo la acción
