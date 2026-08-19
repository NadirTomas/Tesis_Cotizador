# CotizaLaser – Backend

Sistema de cotización para corte láser por fibra, pensado para talleres chicos/medianos.

Este backend expone una API en FastAPI que permite:

- Gestionar materiales y chapas (costo y dimensiones)
- Configurar parámetros de la máquina (velocidad, costo/hora, setup)
- Cargar piezas desde archivos DXF y calcular:
  - longitud total de corte
  - área aproximada
- Crear presupuestos (quotations) con ítems asociados
- Calcular automáticamente costos y precios
- Generar un PDF imprimible del presupuesto

---

## Tecnologías

- Python 3.11+
- FastAPI
- SQLAlchemy
- SQLite (MVP)
- Pydantic / pydantic-settings
- ezdxf (análisis DXF)
- ReportLab (generación de PDF)
- Uvicorn

---

## Estructura principal

```text
backend/
  app/
    api/
      v1/
        routes_health.py
        routes_materials.py
        routes_clients.py
        routes_machine_configs.py
        routes_pieces.py
        routes_quotations.py
        routes_quotation_items.py
    core/
      config.py          # Settings (DB, paths, etc.)
    db/
      session.py         # engine, SessionLocal, Base
      init_db.py         # creación de tablas
    models/
      material.py
      machine_config.py
      client.py
      piece.py
      company.py         # (config empresa, reservado para futuro)
      quotation.py
      quotation_item.py
    schemas/
      material.py
      client.py
      machine_config.py
      piece.py
      quotation.py
      quotation_item.py
    services/
      dxf_analysis.py    # análisis DXF (longitud y área)
      quotation_calculator.py
      pdf_generator.py
    main.py              # FastAPI app
  requirements.txt
  run_backend.bat
  run_backend.sh
  .env.example
```

---

## Configuración

Las variables de entorno se manejan con pydantic-settings desde `app/core/config.py`.

Ejemplo de `.env`:

```env
COTIZALASER_DATABASE_URL=sqlite:///./cotizalaser.db
COTIZALASER_DXF_STORAGE_DIR=data/dxf
COTIZALASER_PDF_STORAGE_DIR=data/pdfs
```

- `DATABASE_URL`: URL de conexión a la base (por defecto, SQLite local).
- `DXF_STORAGE_DIR`: carpeta donde se guardan los DXF subidos.
- `PDF_STORAGE_DIR`: carpeta donde se guardan los PDFs generados.

---

## Instalación y ejecución

Dentro de `backend/`:

```bash
# 1. Crear y activar entorno virtual (opcional pero recomendado)
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Crear tablas
python -m app.db.init_db

# 4. Levantar el servidor
# Windows:
run_backend.bat
# Linux/Mac:
./run_backend.sh
```

La API va a estar disponible en:

- Docs interactivos (Swagger): http://localhost:8000/docs
- Root: http://localhost:8000/

---

## Flujos principales

### 1. Configurar materiales y máquina

Crear materiales:

- `POST /materials`

Campos: nombre, espesor, tamaño de chapa, costo de chapa, etc.

Crear configuración de máquina por material/espesor:

- `POST /machine-configs`

---

### 2. Cargar piezas y DXF

Crear pieza:

- `POST /pieces`

Subir DXF de la pieza:

- `POST /pieces/{piece_id}/upload-dxf`

El backend:

- guarda el archivo
- calcula longitud total de corte (`length_cut_mm`)
- calcula área aproximada (`area_mm2`)

---

### 3. Crear presupuesto y sus ítems

Crear cliente:

- `POST /clients`

Crear presupuesto (Quotation):

- `POST /quotations`

Elegir cliente, fechas, moneda y tipo de cambio.

Agregar ítems:

- `POST /quotation-items`

Campos clave: `quotation_id`, `piece_id`, `material_id`, `quantity`, `margin_percent`.

El backend calcula de forma automática para cada ítem:

- costo de material (según área de la pieza y porcentaje de uso de chapa)
- costo de máquina (según longitud de corte, velocidad y costo/hora)
- costo de mano de obra (30% del costo de máquina, MVP)
- precio unitario y total

Y actualiza los totales del presupuesto:

- `quotation.total_ars`
- `quotation.total_usd` (si hay `exchange_rate` definido)

---

### 4. Generar PDF de presupuesto

- `GET /quotations/{quotation_id}/pdf`

Devuelve un PDF con:

- datos de la empresa (por ahora básicos)
- datos del cliente
- número y fechas del presupuesto
- tabla de ítems
- totales en ARS / USD
- validez del presupuesto
