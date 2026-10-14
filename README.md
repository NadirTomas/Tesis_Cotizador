# CotizaLaser

Cotizador web para talleres de corte láser de fibra. A partir de un archivo DXF calcula automáticamente el costo de una pieza (material, tiempo de máquina, mano de obra), arma presupuestos con historial y PDF, y gestiona el stock físico de chapas y retazos con trazabilidad completa (reserva → corte → retazo).

Proyecto de tesis de Analista en Sistemas — también pensado como producto real.

## Demo

- Frontend: https://frontend-production-ebde2.up.railway.app
- Backend (docs interactivos): https://tesiscotizador-production.up.railway.app/docs

## Stack

**Backend**: Python · FastAPI · SQLAlchemy · Alembic · PostgreSQL (SQLite en local) · Pydantic v2 · Shapely (geometría de stock) · ezdxf (análisis DXF) · ReportLab (PDF) · JWT + bcrypt.

**Frontend**: React 19 · TypeScript · Vite · React Router · Material UI.

**CI**: GitHub Actions (`.github/workflows/ci.yml`) — backend contra SQLite, backend contra un service container de Postgres real, y frontend (tests + tipos + build) en cada push/PR a `main`.

## Estructura

```
backend/    API FastAPI — ver backend/README.md para detalle de módulos
frontend/   SPA React — ver frontend/src/
PROJECT_CONTEXT.md   Estado técnico detallado y actualizado del sistema (arquitectura,
                     contratos, tests, hallazgos de auditoría, limitaciones conocidas)
CLAUDE.md            Principios de arquitectura y forma de trabajo del proyecto
```

## Multiempresa

El sistema es multi-tenant: una cuenta de usuario puede pertenecer a una o varias empresas, con rol `owner` (administra materiales, máquina, stock, empleados) o `employee` (opera el día a día: cotizar, reservar, cortar). Todo el acceso a datos se valida contra la membresía real del usuario en la empresa activa (header `X-Company-Id`) — nunca se confía en un ID que mande el frontend sin validar.

## Levantar el backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/Mac

pip install -r requirements.txt
cp .env.example .env          # completar SECRET_KEY con un valor propio
alembic upgrade head          # crea/actualiza el esquema (Postgres real o SQLite)

uvicorn app.main:app --reload
```

La API queda en `http://localhost:8000` (docs interactivos en `/docs`).

Ver `backend/.env.example` para todas las variables — la única obligatoria es `SECRET_KEY` (el backend no arranca sin ella, a propósito, sin default inseguro). `DATABASE_URL` cae a SQLite local si no se define.

## Levantar el frontend

```bash
cd frontend
npm install
cp .env.example .env   # VITE_API_BASE_URL=http://localhost:8000 por defecto
npm run dev
```

## Migraciones

Alembic maneja el esquema en Postgres (en Railway corre `alembic upgrade head` automáticamente en cada deploy). En SQLite local, `alembic upgrade head` no completa la cadena entera (una migración vieja de abril nunca fue compatible con SQLite) — para validar la cadena completa de punta a punta, usar Postgres:

```bash
docker run --rm -p 5432:5432 -e POSTGRES_PASSWORD=postgres postgres:18
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres alembic upgrade head
```

## Tests

```bash
# Backend (SQLite, rápido)
cd backend
pytest

# Backend contra Postgres real (concurrencia genuina, FK reales) —
# cada archivo corre en su propio proceso, ver el docstring de cada uno
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres pytest tests/test_postgres_hardening_integration.py
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres pytest tests/test_quotation_cancel_confirm_race_postgres.py

# Frontend
cd frontend
npx vitest run
npx tsc --noEmit
npx vite build
```

## Flujo funcional

```
login → seleccionar/crear empresa
→ cargar cliente, material, configuración de máquina
→ crear pieza e importar DXF (calcula longitud de corte y área)
→ crear cotización, agregar ítems (costo calculado automáticamente)
→ aceptar la cotización
→ recomendación de chapa disponible → reservar stock
→ confirmar corte → se genera el retazo automáticamente, con trazabilidad
  completa (chapa origen → cotización → reserva → corte → retazo)
→ generar PDF de la cotización en cualquier momento
```

El detalle completo del estado del sistema (qué está implementado, qué falta, decisiones de arquitectura y limitaciones conocidas) vive en [`PROJECT_CONTEXT.md`](./PROJECT_CONTEXT.md).

## Documentación adicional

- [Módulo de remitos](docs/MODULO_REMITOS.md): entregas parciales/completas, numeración, anulación, PDF y pruebas.
