# PROJECT_MEMORY.md

> Memoria histórica y de decisiones de CotizaLaser.
>
> Este archivo explica cómo llegó el proyecto a su estado actual, por qué se tomaron decisiones importantes y qué contexto no debe perderse entre sesiones.
>
> Para conocer el estado técnico actual usar `PROJECT_CONTEXT.md`.
> Para conocer las reglas de trabajo usar `CLAUDE.md`.
>
> Repositorio canónico: `NadirTomas/Tesis_Cotizador`, rama `main`.
>
> No almacenar secretos en este archivo.

Última actualización: agosto de 2026 (cierre de la pasada de hardening post-auditoría).

## Cómo usar esta memoria

1. Leer `CLAUDE.md`.
2. Leer `PROJECT_CONTEXT.md`.
3. Leer este archivo.
4. Verificar `git status` y los últimos commits — el código real siempre gana.
5. Nunca asumir que esta memoria describe mejor el presente que el código actual.
6. Si algo figura acá como histórico o como idea futura, comprobar en el código si eventualmente se implementó.
7. Actualizar este archivo cuando haya una decisión importante, no por cada commit chico.

---

## 1. Repositorios y fuente de verdad

**Actual/canónico**: `NadirTomas/Tesis_Cotizador`, rama `main`. Es el sistema principal — no una copia académica de un proyecto real aparte. En algún momento previo a agosto de 2026 existió trabajo relacionado en `NadirTomas/CotizaLaser`; ese repositorio es **histórico/obsoleto** y no debe usarse como fuente de verdad. El historial de `main` en este repo *comienza* con un MVP ya bastante armado (ver §5) — no incluye la etapa de diseño/prototipado más temprana, que probablemente vivió en ese repositorio anterior.

Orden de prioridad para determinar comportamiento actual: **código de `main` → migraciones → tests → contratos → `PROJECT_CONTEXT.md` → esta memoria**. Este archivo es para contexto histórico, nunca para sobreescribir el estado real del código.

---

## 2. Contexto del proyecto

CotizaLaser nace para asistir el proceso de cotización de un taller de corte láser de fibra. La empresa tomada como caso de estudio es **Cortesar S.A.** (corte láser / trabajos metalúrgicos y fabricación de piezas).

Proceso manual que se buscó reemplazar:

```
cliente envía consulta/pieza (normalmente un DXF)
→ análisis con herramientas CAD
→ mediciones de longitud/área a mano
→ estimación de tiempo de máquina
→ cálculo de material + máquina + margen
→ presupuesto armado a mano
→ envío al cliente
```

Objetivo: un proceso más rápido, repetible, auditable, menos dependiente de cálculos "a ojo", y usable por distintos empleados de distintas empresas sobre la misma plataforma. **CotizaLaser no controla físicamente la máquina de corte** — no es CAM, no manda instrucciones a un CNC, no reemplaza AutoCAD. Es cotización + análisis DXF + planificación + stock asociado al corte + trazabilidad (ver §20 para el alcance explícito).

### Contexto de tesis

CotizaLaser es el proyecto usado para la tesis/trabajo final de Analista en Sistemas. Nadir y Hernán concentran principalmente la programación/desarrollo; el resto del equipo participa sobre todo en relevamiento, documentación, testing y material académico (según lo documentado — no hay registro de tareas individuales más específicas para no inventarlas).

Punto importante para no perder: el desarrollo técnico real avanzó más rápido que la narrativa académica. `Tesis_Cotizador` terminó siendo el repositorio principal del sistema real, no solo el de la entrega de tesis — ver §19 para cómo se concilian ambos calendarios.

---

## 3. Evolución histórica

El historial completo de `main` son 35 commits (agosto de 2026). Se agrupan por hito, no commit por commit.

### Etapa inicial — MVP de cotización (19/08, `47e9c88`)

El primer commit del repo ya trae, de una: FastAPI + React + SQLite, modelos `Material`/`MachineConfig`/`Client`/`Piece`/`Quotation`/`QuotationItem`, análisis DXF (`dxf_analysis.py`, ya con fallback de 3 niveles), motor de costeo, generación de PDF (`pdf_generator.py`, ~570 líneas), nesting en grilla simple, y las 16 páginas de frontend que en gran medida siguen existiendo hoy. Es un MVP funcional desde el arranque de este historial, no un esqueleto vacío.

Correcciones inmediatas de estabilización (mismo día): endpoints GET/DELETE faltantes y la migración baseline que hacía fallar `alembic upgrade head` contra una base vacía (`bb2b409`); flags `has_dxf`/`has_preview` mal calculados, **ítems de cotización huérfanos por hacer `commit()` antes de calcular el costo** (si `MachineConfig` faltaba, quedaba una fila en cero sin que el usuario se enterara — pasó a `flush()` + rollback explícito), y ruteo SPA roto al refrescar una URL interna (`c8e3ef7`); `pdf_generator.py`/nesting rotos porque las piezas/logo habían migrado de filesystem a bytes en la DB y el código todavía leía paths viejos (`4cb8c0c`); sesión expirada sin manejar y nesting sin header de auth (`90d68cb`).

### Multiempresa (20/08, `5a129a5`)

Hasta acá todo era global: cualquier usuario autenticado veía todos los datos. Se introduce `Company` (reemplaza un singleton `CompanyConfig`) + `CompanyMember` con rol `owner`/`employee`, `company_id` agregado y backfillado en clientes/materiales/config de máquina/piezas/cotizaciones, `get_current_company` (valida `X-Company-Id` contra membership real, nunca confía en el valor solo) y `require_owner`. Numeración de cotizaciones pasa a ser generada por el servidor (antes era texto libre del cliente). Test suite: 13 tests nuevos (`test_multitenancy.py`, `test_roles.py`).

En el mismo día: endpoint de onboarding gateado por `X-Admin-Secret` para no tener que exponer un signup público (`99f372a`), y una primera ronda formal de "audit findings" — validaciones con `Field` en vez de dejar pasar costos mal calculados, primera versión de "una `MachineConfig` activa por material", **primer `PUT /quotation-items/{id}`** (el frontend no lo consumió hasta la pasada de hardening de agosto, ver `PROJECT_CONTEXT.md`), dejar de filtrar excepciones crudas del endpoint de DXF, rate limiting, `min_length=8` en passwords (`bd5ae87`, 21/21 tests).

### Nesting real (20/08, `3199c15`)

El nesting original repetía el bounding box de UNA pieza en una grilla uniforme — no era nesting de verdad. Se reescribe sobre MaxRects-BSSF (heurística estándar de bin-packing 2D): múltiples tipos de pieza con cantidades independientes, rotación 90° opcional, overflow a tantas chapas como haga falta. De paso se descubrió que `get_bounding_box` no tenía el mismo fallback de 3 niveles que `analyze_dxf` — cualquier DXF mínimo que ya funcionaba para costeo rompía nesting silenciosamente. 26/26 tests.

### Auditoría, refresh de sesión, observabilidad (20/08, `3cd983b`)

Cuatro mejoras independientes: refresh silencioso de sesión cada 6h (`POST /auth/refresh`); **primeros tests de frontend** (Vitest + RTL — hasta acá no había ninguno); observabilidad self-hosted sin depender de un servicio de terceros (decisión explícita del usuario, sin alta en Sentry) — handler global de excepciones con traceback completo al logger JSON, y `POST /client-errors` para que errores de JS del frontend lleguen a los mismos logs de Railway; y `QuotationEvent` como log de auditoría append-only (creado, cambio de estado, ítem agregado/editado/borrado), con endpoint de historial. 33/33 backend, 18/18 frontend nuevos.

### Stock físico (20/08, `6b2c38f`)

Capa base de inventario, **explícitamente sin nesting automático ni descuento de corte todavía** — solo el modelo. `Material` gana `material_type`/`alloy` (columnas nullable, aditivas, sin romper filas existentes). `StockSheet` (`FULL_SHEET`/`REMNANT`, estados `AVAILABLE/RESERVED/CONSUMED/DISCARDED`) con geometría GeoJSON medida server-side vía Shapely — **se decidió no incorporar PostGIS** por no ser necesario para el alcance. Códigos secuenciales `CH-####`/`R-####` por empresa. 42/42 tests.

### Motor de recomendación geométrica (20/08, `3d919bf`)

Solo análisis, ninguna mutación de stock todavía. `extract_piece_polygon()` nuevo (construye un polígono Shapely real con agujeros, distinto de `analyze_dxf`/`get_bounding_box` que siguen existiendo para costeo). `kerf_mm`/`minimum_spacing_mm` nuevos en `MachineConfig`. `find_placement()` prueba 4 rotaciones sobre una grilla acotada de posiciones. `recommend_stock_for_piece()` puntúa cada candidato compatible: `score = 0.6·utilización + 0.4·(es_retazo)` — deliberadamente simple y explicable, no "inteligente". Nota del propio commit: descubrieron en la práctica (no en teoría) que los DXF de prueba del proyecto solo pasan por el fallback manual de 3er nivel, nunca por `ezdxf.readfile` directo — ver §8. 54/54 tests.

### Integración completa inventario-cotización (20/08, `dc9bdbc`)

Ata la recomendación al ciclo de vida real: aceptar una cotización **nunca** toca stock por sí sola — solo dos acciones explícitas lo hacen (`reserve`, `confirm-cut`). `StockReservation` (una `ACTIVE` por chapa a la vez — elección deliberadamente simple/segura sobre reservas concurrentes múltiples) y `StockMovement` (log append-only de 7 tipos de evento). UPDATEs condicionales (`WHERE status = 'X'`) en vez de `SELECT FOR UPDATE`, portables entre SQLite y Postgres. `stock_cut.py`: `stock_geometry.difference(pieza_ocupada)` vía Shapely, normalizando a polígonos reales y descartando fragmentos por debajo de un umbral configurable por empresa. Se encontró y arregló en el camino que `accepted → cancelled` nunca había sido una transición válida — sin eso, una reserva jamás se podía liberar por el flujo normal. Verificado a mano en el navegador, no solo con tests: crear pieza+stock → recomendación → reservar → confirmar corte → chapa `CONSUMED` + retazo con linaje correcto (`CH-0001 → R-0001 → COT-0001`). 70/70 backend, 18/18 frontend.

### Endurecimiento pre-merge y pulido (21/08)

Score de recomendación reescrito (jerarquía retazo-adecuado vs. resto, en vez de suma ponderada simple), primer índice único parcial (anti doble-reserva sobre la misma chapa), `remaining_area_mm2` se limpia al consumir (`4862fc5`). Gitignore para `test_railway.py` (credenciales de admin en texto plano — **nunca llegó a commitearse**, confirmado revisando el historial completo), gate de estado para editar/borrar ítems de cotización, `RateLimitExceeded` devolvía 500 en vez de 429, config muerta eliminada (`9e56da9`). Favicon/título dinámico por empresa (`3fa1109`). Layout responsive mobile, último commit antes de la auditoría (`73ec82e`).

### Auditoría y hardening (25/08)

Auditoría completa del sistema (documentada en `PROJECT_CONTEXT.md`, reescrito ese mismo día — `23d0716`). A partir de ahí, una pasada de hardening autónomo: fix crítico de `DELETE /quotations/{id}` (FK sin cascade) y de la carrera cancelación/confirm-cut, validados contra Postgres real con Docker (`38a9a13`, `0a9bac5`); reintento de numeración y constraint de `MachineConfig` única (`f2dfd45`); cobertura de tests para DXF y `quotation_calculator.py`, cero hasta ese momento (`c12faab`, `2fef35e`); revisión de seguridad (`38676c5`); alineación de contratos frontend↔backend — kerf/spacing, retazos, edición de ítems (`2eac36e`, `d615e87`, `7bfbfda`); E2E completo y smoke de nesting/PDF (`cd81684`, `1af29c1`); CI con GitHub Actions, antes inexistente (`b4a78ea`); documentación final (`5081b8d`). Detalle completo de cada fix en `PROJECT_CONTEXT.md` §7.

---

## 4. Decisiones de arquitectura importantes

### FastAPI + React separados
Responsabilidades desacopladas desde el día uno — nunca hubo un monolito server-rendered que migrar.

### Lógica de negocio solo en backend
React no recalcula precios ni reglas sensibles — es principio explícito de `CLAUDE.md`, respetado en la práctica (el frontend siempre muestra lo que el backend ya calculó).

### PostgreSQL como motor de producción, SQLite para dev/tests
`init_db.py` solo hace `create_all()` si la URL es SQLite; en cualquier otro caso, todo pasa por Alembic. Se aprendió en agosto que esto tiene un costo real: SQLite no reproduce todas las constraints/FK de Postgres (ver §16).

### Alembic
Schema versionado y reproducible desde el primer commit (aunque la migración baseline original estaba rota — `bb2b409` la arregló el mismo día).

### DXF/logos guardados como bytes en Postgres, no en filesystem
Se abandonó depender del filesystem efímero de Railway (que se borra en cada redeploy) — decisión tomada y corregida en la práctica cuando `pdf_generator.py`/nesting crashearon leyendo paths que ya no existían (`4cb8c0c`).

### PDF on-demand, sin persistir
`Quotation.pdf_data` existe como columna pero nunca se escribe — no hizo falta cachear, el costo de regenerar es bajo. Sigue siendo la decisión vigente.

### Multiempresa con `CompanyMember`, no con una tabla `tenant_id` genérica
Modelo explícito usuario↔empresa con rol, para que un mismo usuario pueda pertenecer a varias empresas — necesario porque el sistema es multi-cliente (Cortesar es UN caso de estudio, no el único cliente previsto).

### `X-Company-Id` nunca confiado sin validar
El frontend indica la empresa activa, pero el backend siempre valida membership real antes de usar ese valor — verificado explícitamente en la auditoría de agosto sin encontrar fugas.

### OWNER / EMPLOYEE, dos roles nomás
Modelo deliberadamente simple — se descartó un sistema de permisos granulares por no ser necesario para el alcance actual.

### GeoJSON + Shapely en vez de PostGIS
La geometría de stock (chapas, retazos, colocación) se resuelve con Shapely en la capa de aplicación; PostGIS se consideró y se descartó por ser una complejidad de infraestructura innecesaria para el volumen y las consultas reales del sistema.

### Retazos como `StockSheet` con `stock_type`, no un modelo aparte
`FULL_SHEET` y `REMNANT` comparten modelo y tabla — un retazo es, para casi todo propósito, una chapa más chica con procedencia.

### Una `StockReservation` `ACTIVE` por chapa
Se descartó permitir múltiples piezas reservadas simultáneamente sobre una misma chapa en esta versión — es el enfoque simple y seguro, no el más expresivo posible.

### UPDATE condicional (`WHERE status = '...'`) en vez de `SELECT FOR UPDATE`
Elegido explícitamente por portabilidad entre SQLite (tests) y Postgres (producción), sin locking dialect-specific. Validado después contra concurrencia real de Postgres en la pasada de hardening (ver §16) — el patrón resultó correcto, no solo portable.

### Nesting separado del motor real de stock
`nesting.py` (bin-packing rectangular sobre bounding box) y `stock_placement.py`/`stock_recommendation.py`/`stock_cut.py` (geometría real con agujeros, sí persiste) son dos motores distintos, sin código compartido. Es una separación **deliberada y documentada** (planificación *what-if* vs. trazabilidad de inventario real), no una duplicación accidental — confirmado explícitamente en la auditoría de agosto, no se unificaron.

---

## 5. Reglas de negocio conocidas

**Cotizaciones**: estados `draft → sent → accepted → cancelled` (+ `draft/sent → cancelled`, y `accepted → cancelled` agregado en `dc9bdbc` para poder liberar reservas). Crear/editar ítems: solo `draft`. Borrar ítems: `draft` y `accepted` (dar de baja una pieza puntual de un trabajo ya aprobado, libera su reserva si tenía). `DELETE` de la cotización completa: solo `draft`.

**Stock — permisos**: crear/editar/descartar chapas requiere OWNER; consultar, pedir recomendación, reservar y confirmar corte están abiertos a cualquier rol de la empresa (uso del día a día). Verificar siempre contra `routes_stock.py` antes de asumir, los permisos por acción no son simétricos.

**Aceptar una cotización NO reserva ni consume stock por sí sola** — son dos acciones explícitas y separadas (`reserve`, `confirm-cut`). Es una regla fundamental repetida en varios commits, nunca se relajó.

**Flujo físico**: `AVAILABLE → (reserve) → RESERVED → (confirm-cut) → CONSUMED`, y `CONSUMED` genera `REMNANT`s en `AVAILABLE` cuando el fragmento supera los umbrales configurados.

**Retazos**: se conservan solo si superan `minimum_remnant_area_mm2` (y opcionalmente ancho/alto mínimo) configurados por empresa — configurable desde la UI desde la pasada de hardening de agosto.

**Tipo de cambio**: se guarda en la cotización al momento de crearla, para conservar auditabilidad histórica aunque el tipo de cambio real cambie después.

**Material**: `material_type`/`alloy`/`thickness_mm` definen la granularidad real (una fila de `Material` = un espesor/config de costeo).

**`MachineConfig`**: una activa por material/empresa — protegida en aplicación desde `bd5ae87`, y en la base de datos (índice único parcial) desde la pasada de hardening de agosto.

**Kerf y separación mínima**: usados en la geometría real de colocación/recomendación de stock, no en el costeo (`quotation_calculator.py` no los usa, solo `stock_placement.py`).

---

## 6. Motor de costos

Fuente de verdad real: `backend/app/services/quotation_calculator.py`.

```
costo_material = (piece.area_mm2 / (sheet_width_mm * sheet_height_mm)) * sheet_cost_ars * quantity
tiempo_por_unidad_h = (piece.length_cut_mm / cut_speed_mm_min + setup_time_min) / 60
costo_maquina = tiempo_por_unidad_h * machine_cost_per_hour_ars * quantity
costo_labor = costo_maquina * (labor_percent / 100)
unit_price = ((costo_material + costo_maquina + costo_labor) / quantity) * (1 + margin_percent / 100)
total_price = unit_price * quantity
total_usd = total_ars / exchange_rate   (si exchange_rate está seteado y es > 0; si no, 0)
```

### Pendiente de decisión de negocio: `setup_time_min`

Hoy se cobra **por unidad** (dentro del tiempo por pieza, antes de multiplicar por `quantity`), no una sola vez por corrida. Este comportamiento está preservado y testeado explícitamente (`test_setup_time_is_charged_once_per_unit_not_once_per_job`, agosto de 2026) para que no se cambie por accidente en una refactorización futura — pero **sigue sin validar con Cortesar** si la interpretación correcta es por unidad, por lote, o por trabajo/corrida completa. No elegir automáticamente; es una decisión comercial, no técnica.

---

## 7. Historia del DXF

`dxf_analysis.py` es, junto con el motor de costos, el módulo que más incidentes generó.

**Arquitectura de lectura, desde el primer commit**: tres niveles de fallback — `ezdxf.readfile()` directo, `ezdxf.recover.readfile()` si falla, y un parser manual línea por línea de los códigos de grupo DXF si ambos fallan. Se descubrió en la práctica (commit `3d919bf`, agosto) que los DXF de prueba del propio proyecto (generados a mano, sin subclase `AcDbPolyline`) **nunca pasan por los dos primeros niveles** — siempre caen al parser manual. Esto no se supo por diseño, se encontró corriendo el código real.

**Tres consumidores, tres contratos**: `analyze_dxf()` (longitud + área, para costeo), `get_bounding_box()` (para nesting rectangular), `extract_piece_polygon()` (polígono Shapely real con agujeros, para stock/colocación real). Los tres coexisten porque resuelven problemas distintos — no es duplicación accidental, aunque sí implicó mantener tres parsers de fallback en paralelo.

**Incidente histórico — bounding box sin fallback completo**: `get_bounding_box()` solo tenía el primer nivel de lectura, sin recuperación; un DXF mínimo que `analyze_dxf()` ya toleraba rompía nesting silenciosamente (devolvía `(0, 0)`). Corregido en `3199c15` (agosto), alineándolo al mismo fallback de 3 niveles.

**Incidente — área con agujeros calculada mal**: `analyze_dxf()` sumaba el área de los contornos internos (agujeros) en vez de restarla, y las piezas puramente circulares (`CIRCLE`) no contaban para el área en absoluto — desalineaba el costo de material cotizado contra el área real que después se descontaba del stock (que sí usaba `extract_piece_polygon`, correcto desde el principio). Corregido en agosto de 2026 unificando ambos cálculos sobre la misma construcción de polígono con huecos, con backfill de las piezas ya existentes en producción (sin tocar cotizaciones ya emitidas). Es el bug que disparó la auditoría completa del sistema.

**Limitación conocida y vigente**: *bulge* (arcos dentro de una `LWPOLYLINE`) no se interpreta en ningún parser — los segmentos se tratan como rectos. Documentado desde `3d919bf`, nunca resuelto, no hay evidencia de que haya sido un problema real en la práctica todavía.

**Comportamiento documentado (no bug)**: si un DXF tiene varios contornos cerrados que NO están anidados (ninguno contiene al otro), solo el más grande cuenta como pieza — los demás se ignoran silenciosamente. Piezas multi-contorno separadas no están soportadas hoy; confirmado y testeado explícitamente en agosto de 2026.

---

## 8. Incidentes técnicos relevantes

Formato breve — solo los que dejaron una regla o decisión, no todos los bugs.

**Archivos en filesystem de Railway → bytes en DB.**
*Problema*: DXF/preview/logo se guardaban como paths de archivo; Railway borra el filesystem en cada redeploy.
*Causa*: diseño inicial no contempló el ciclo de vida efímero del contenedor.
*Solución*: `dxf_data`/`preview_data`/`logo_data` como `BYTEA` en Postgres.
*Qué dejó*: nunca volver a depender del filesystem local para algo persistente (ver §11).

**Orphan quotation items por commit prematuro.**
*Problema*: crear un ítem hacía `commit()` antes de calcular su costo; si el cálculo fallaba (ej. sin `MachineConfig`), quedaba una fila en cero, invisible como error para el usuario.
*Causa*: orden de operaciones — persistir antes de validar el cálculo completo.
*Solución*: `flush()` en vez de `commit()`, rollback explícito si `calculate_quotation_item` lanza.
*Qué dejó*: no comitear antes de completar un cálculo transaccional.

**Nesting sin header de Authorization.**
*Problema*: `calculateNesting()` en el frontend nunca mandaba el token — 401 en el 100% de los intentos.
*Causa*: el resto de los servicios se centralizaron en un wrapper de fetch antes que nesting existiera.
*Solución*: mismo `apiClient.ts` centralizado para todos los servicios.

**`DELETE /quotations/{id}` bloqueado por FK de `quotation_events`.**
*Problema*: toda cotización tiene al menos un evento `"created"`; la FK no tenía `ON DELETE CASCADE`, así que el borrado fallaba siempre en Postgres (invisible en SQLite, que no enforce FK por defecto).
*Causa*: la relación ORM y la constraint real nunca se completaron cuando se agregó `QuotationEvent`.
*Solución*: relación ORM con cascade + migración con `ON DELETE CASCADE` real; `PRAGMA foreign_keys=ON` activado para SQLite en tests.
*Qué dejó*: no asumir que SQLite reproduce el enforcement de FK de Postgres (ver §16).

**Mismo patrón en `stock_reservations.quotation_item_id`.**
*Problema*: encontrado corrigiendo el anterior — borrar un ítem con una reserva asociada también rompía por FK.
*Solución*: `ON DELETE SET NULL` (la reserva es historial, debe sobrevivir al ítem que la originó).

**Cancelación vs. confirm-cut, carrera real.**
*Problema*: cancelar una cotización aceptada podía, bajo carrera con un `confirm-cut` concurrente, dejarla `cancelled` con material ya `CONSUMED`, sin ningún rastro del conflicto.
*Causa*: el valor de retorno de `release_reservation()` se descartaba.
*Solución*: `release_quotation_reservations()` aborta toda la cancelación (rollback + 409) si hay conflicto; validado con 25 corridas concurrentes reales contra Postgres.
*Qué dejó*: no confiar solo en un chequeo lectura-antes-de-escribir para invariantes bajo concurrencia; el UPDATE condicional sobre la fila es la protección real.

**`MachineConfig` activa concurrente / numeración de cotizaciones concurrente.**
*Problema*: ambos protegidos solo en código de aplicación (lectura-luego-escritura), sin red de seguridad en la base.
*Solución*: índice único parcial para la primera, reintento ante colisión (mismo patrón que `_next_stock_code`) para la segunda.

**Logger crasheando con `extra={"filename": ...}`.**
*Problema*: subir un DXF con extensión inválida crasheaba el logging mismo (`filename` es un atributo reservado de `LogRecord` de Python), devolviendo un 500 en vez del 400 esperado.
*Causa*: descuido — otra línea del mismo archivo ya usaba correctamente `dxf_filename`.
*Solución*: unificado a `dxf_filename` en los dos lugares que faltaban. Encontrado escribiendo tests de DXF en agosto, no antes.

---

## 9. Migraciones

Alembic es el mecanismo canónico de schema desde el primer commit. Al cierre de la pasada de hardening de agosto de 2026: **15 migraciones, un solo head (`a8b9c0d1e2f3`), cadena lineal**. Ver `PROJECT_CONTEXT.md` para el listado completo y actualizado — acá solo el aprendizaje:

**Postgres es el único motor contra el que se valida la cadena real de producción.** SQLite tiene diferencias reales de soporte de `ALTER`/constraints (requiere modo *batch*, que reconstruye la tabla entera) y no debe considerarse un sustituto de Postgres para validar migraciones — de hecho, la cadena completa de migraciones **no corre end-to-end contra SQLite** (una migración de abril nunca fue compatible con modo batch; no se tocó por ser ajena al trabajo de agosto). Después de descubrir el bug de `DELETE /quotations/{id}` (invisible en SQLite), se agregaron tests y CI que corren explícitamente contra un container de Postgres real, no solo contra SQLite.

---

## 10. Testing — cómo evolucionó

Cobertura inicial limitada, creciendo por hito según se agregaban features: multitenancy/roles (`5a129a5`, 13 tests) → nesting real (`3199c15`, 26) → auditoría/refresh (`3cd983b`, 33) → inventario físico (`6b2c38f`, 42) → recomendación (`3d919bf`, 54) → integración completa (`dc9bdbc`, 70). En la pasada de hardening de agosto se agregó, por primera vez, cobertura dedicada de `dxf_analysis.py`, `quotation_calculator.py` y `pdf_generator.py` (los tres en cero hasta ese momento), tests de concurrencia real contra Postgres, y GitHub Actions.

**Checkpoint histórico** (no una promesa de estado futuro, verificar siempre contra el código real): al cierre del hardening de agosto de 2026, 133 tests backend + 2 archivos de integración Postgres real + 18 tests frontend.

---

## 11. Deploy y producción

Railway desde el primer commit: 3 servicios (Postgres, backend, frontend) en el mismo proyecto/environment. El backend corre `alembic upgrade head` en cada arranque. Incidentes de infraestructura resueltos en el camino: mixed content HTTPS (middleware que confía en `X-Forwarded-Proto`), CORS vía `FRONTEND_URL`, bcrypt directo en vez de `passlib` (conflictos en el entorno de Railway), y el ya mencionado paso de archivos de filesystem a bytes en DB.

**GitHub Actions verifica el código pero no despliega** — Railway sigue auto-desplegando por su cuenta al pushear a `main`. Antes de agosto de 2026 no existía ningún CI; un commit roto podía llegar a producción sin ninguna señal previa.

URLs vigentes (documentadas también en README/PROJECT_CONTEXT): frontend en `frontend-production-ebde2.up.railway.app`, backend en `tesiscotizador-production.up.railway.app`. No hay secretos en este archivo ni en ningún otro trackeado — confirmado revisando `git log --all` completo.

---

## 12. Multiempresa

```
User ↔ CompanyMember ↔ Company
```
Roles: `owner` (administra materiales, máquina, stock, empleados), `employee` (opera el día a día). `X-Company-Id` identifica la empresa activa en cada request; el backend valida membership real, que el miembro esté activo, que la empresa esté activa, y que cada recurso referenciado (`company_id` en cada query) pertenezca a esa misma empresa — incluidos los casos con varios IDs cruzados en un mismo payload (reservar stock, agregar ítems). Se hizo una auditoría explícita de aislamiento cross-tenant en agosto de 2026 y no se encontraron fugas en los endpoints revisados — sin afirmar que sea matemáticamente imposible, solo que se revisó a fondo y no apareció ninguna.

---

## 13. Stock y trazabilidad

`StockSheet` (chapa completa o retazo, con geometría real) → `StockReservation` (vincula un stock con una cotización/pieza/ítem concretos) → `StockMovement` (historial append-only, nunca se lee para decidir estado, solo para reconstruir qué pasó).

```
CH-0001 (chapa completa)
 → reserva (StockReservation ACTIVE)
 → confirmar corte
 → CH-0001 pasa a CONSUMED
 → se generan R-0001, R-0002... (retazos AVAILABLE)
    cada uno con source_sheet_id=CH-0001 y source_quotation_id=<cotización>
 → un retazo puede volver a reservarse/cortarse más adelante, generando
   sus propios retazos hijos (la cadena de procedencia sigue creciendo)
```

`quotation_item_id` en `StockReservation` usa `SET NULL` (no cascade) al borrar el ítem que originó la reserva: la reserva es un registro de auditoría de qué pasó con una chapa física, debe sobrevivir aunque el ítem de cotización que la disparó ya no exista.

---

## 14. Concurrencia

Los tests corrieron contra SQLite desde siempre, y SQLite no reproduce el mismo comportamiento de locking/enforcement de FK que Postgres — esto dejó bugs reales invisibles durante semanas (ver §8). Después de encontrarlos, se validó explícitamente contra Postgres real (Docker local) en agosto de 2026: doble reserva sobre la misma chapa, `confirm-cut` idempotente, la carrera cancelación/confirm-cut (25 corridas reales, alternando qué request gana), numeración de cotizaciones, y reactivación de `MachineConfig`. El patrón que sostiene todo esto es el `UPDATE ... WHERE status = '...'` condicional: bajo Postgres/READ COMMITTED, dos transacciones que tocan la misma fila se serializan por el lock de fila — la que pierde espera, y al desbloquear re-evalúa su condición contra el valor ya comiteado. Confirmado empíricamente, no solo por lectura de documentación.

---

## 15. Seguridad

JWT HS256 (`SECRET_KEY` obligatorio, sin default inseguro — falla el arranque si falta) + bcrypt cost 12 desde el principio. Rate limiting (`slowapi`) en auth, uploads, cotizaciones, stock, admin. `ADMIN_SECRET` gatea el onboarding manual de empresas, comparado con `hmac.compare_digest` desde agosto de 2026 (antes, `!=`). Errores genéricos al cliente, logs estructurados en JSON server-side con el detalle real. **No se guardan en este archivo ni en ningún otro**: contraseñas, tokens, `DATABASE_URL` real, `SECRET_KEY`, `ADMIN_SECRET`. Confirmado por revisión del historial completo de git que ningún secreto real llegó a commitearse nunca.

---

## 16. Frontend / UX

React + MUI, tema oscuro industrial (acento naranja) desde el primer commit. Evolución: sidebar fijo → responsive con drawer temporal en mobile (agosto); selector/alta de empresa y gestión de empleados agregados con multiempresa; wizard de cotización + detalle con historial de eventos, reserva/confirmación de corte inline; visor de geometría de stock (chapa real + pieza superpuesta) reutilizado entre el flujo de cotización y el detalle de stock; refresh de sesión silencioso; y, en la pasada de hardening de agosto, edición de ítems de cotización y exposición de kerf/spacing/umbrales de retazo que ya existían en el backend pero no en la UI.

---

## 17. Relación entre desarrollo real y planificación académica

El desarrollo técnico real (agosto de 2026, ver §3) avanzó más rápido que lo que una entrega de tesis narra habitualmente en sprints. La documentación académica organiza las mismas funcionalidades ya existentes según el momento en que se planificaron/validaron para la entrega, sin falsear evidencia de cuándo se construyeron realmente. Líneas generales conocidas (a contrastar con los documentos de sprint del proyecto si están disponibles, antes de fijar fechas o contenido exacto):

- **Sprint 0**: relevamiento, alcance, arquitectura general.
- **Sprint 1**: base del sistema, repo de tesis, deploy inicial, multiempresa/autenticación.
- **Sprint 2**: estabilización, cotizaciones, nesting, auditoría/tests.
- **Sprint 3 y posteriores**: validación real, costos, PDF, stock/retazos, aceptación de cotización — según la documentación de tesis vigente al momento de escribir cada entrega.

---

## 18. Cosas que deliberadamente no son parte del sistema

Fuera de alcance actual, salvo que el código diga lo contrario en el futuro: diseño CAD completo (no reemplaza AutoCAD), CAM, comunicación directa con la CNC, ejecución automática del corte, contabilidad completa, ERP completo, compras/proveedores completos, facturación fiscal, producción industrial de punta a punta. CotizaLaser es cotización + análisis DXF + planificación (nesting) + stock asociado al corte + trazabilidad — nada más que eso, y está bien que sea así.

---

## 19. Ideas futuras (NO IMPLEMENTADO)

Marcadas explícitamente para que una sesión futura no asuma que ya existen:

- **NO IMPLEMENTADO**: trazabilidad de stock por unidad física individual (hoy una reserva cubre un ítem completo, independiente de su `quantity`).
- **NO IMPLEMENTADO**: nesting integrado directamente al inventario real (hoy son dos motores separados a propósito, ver §4).
- **NO IMPLEMENTADO**: paginación server-side (todo listado pagina en memoria del lado del cliente).
- **NO IMPLEMENTADO**: revocación de sesión JWT (un token emitido vive sus 7 días completos aunque se desactive al usuario).
- **NO IMPLEMENTADO**: cache/persistencia real de PDF (`Quotation.pdf_data` existe como columna, nunca se escribe).
- **NO IMPLEMENTADO**: mayor optimización geométrica de nesting (ángulos de rotación más finos que 0/90/180/270, por ejemplo — el propio código lo dejó como parámetro fácil de ampliar).
- **NO IMPLEMENTADO**: integración con sistemas externos (contabilidad, ERP, proveedores).

---

## 20. Working tree pendiente al momento de este snapshot

Al momento de escribir este archivo, `git status --short` mostraba cambios locales sin commitear, ajenos a la pasada de hardening de agosto y preservados sin tocar por instrucción explícita:

- `backend/app/services/dxf_analysis.py` — fix de área con agujeros (ver §7), pendiente de commit propio y separado.
- `frontend/src/pages/EmployeesPage.tsx`, `frontend/src/services/{apiClient,auth,nesting,stock}.ts` — cambios relacionados a manejo de errores de API (`parseErrorDetail`), anteriores a esta pasada.
- `CotizaLaser_Formulas_de_Costo.pdf` — archivo suelto sin trackear en la raíz.

Ninguno de estos forma parte del sistema estable hasta que se commiteen explícitamente. No asumir que ya están integrados.

---

## Decision log

| Decisión | Motivo | Estado |
|---|---|---|
| DXF/logos como bytes en DB | Filesystem de Railway es efímero | Vigente |
| Multiempresa (`Company`/`CompanyMember`) | Una plataforma, varias empresas aisladas | Vigente |
| OWNER/EMPLOYEE, dos roles | Modelo de permisos simple, alcanza para el caso de uso | Vigente |
| GeoJSON + Shapely, sin PostGIS | Geometría sin necesidad de infraestructura extra | Vigente |
| PDF on-demand, sin persistir | No hizo falta cachear todavía | Vigente |
| Nesting separado del motor real de stock | Planificación *what-if* vs. trazabilidad real — problemas distintos | Vigente, documentado |
| UPDATE condicional para concurrencia | Portable SQLite/Postgres, validado luego contra Postgres real | Vigente |
| Una `StockReservation` ACTIVE por chapa | Enfoque simple/seguro sobre uno más expresivo | Vigente |
| Admin-secret-gated onboarding, sin signup público | No se quiso una página de registro pública | Vigente |
| Observabilidad self-hosted, sin Sentry | Decisión explícita del usuario | Vigente |
| `setup_time_min` por unidad | Comportamiento heredado desde el motor de costeo original | **Pendiente de validar con Cortesar** |

---

## Lecciones técnicas / no volver a cometer

- No asumir que SQLite reproduce todas las FK/constraints de Postgres — validar migraciones y concurrencia contra Postgres real.
- No usar el filesystem local de un contenedor (Railway u otro) para nada que deba persistir entre deploys.
- No confiar en un `company_id` (o cualquier ID) recibido del frontend sin validar pertenencia real contra la base.
- No hacer `commit()` antes de completar un cálculo transaccional (usar `flush()` + rollback explícito ante error).
- No modificar stock automáticamente al aceptar una cotización — solo acciones explícitas del usuario tocan inventario.
- No confiar solo en un chequeo lectura-antes-de-escribir para proteger una invariante bajo concurrencia real; respaldarlo con una constraint de base de datos.
- No guardar el tipo de cambio solo de forma global — se persiste por cotización para no perder auditabilidad histórica.
- No cambiar fórmulas de costeo ni reglas comerciales sin validación real del negocio (ver `setup_time_min`, §6).
- No mezclar cambios locales ajenos a una tarea puntual dentro de sus commits.
- No modificar una migración de Alembic ya aplicada para arreglar algo en producción — crear una migración nueva siempre.

---

## Política de mantenimiento

Actualizar este archivo cuando ocurra: un cambio grande de arquitectura, una regla de negocio nueva, un incidente técnico importante, una decisión no obvia, una funcionalidad central nueva o descartada, un cambio de alcance de tesis, o un cambio de infraestructura.

No actualizarlo por: un typo, un ajuste de estilo, un refactor interno sin impacto externo, o un test menor.

Cada actualización debe ser incremental y preservar la historia anterior — no reescribir esta memoria completa salvo que esté realmente corrupta o gravemente desactualizada (como le pasó a `PROJECT_CONTEXT.md` antes de la auditoría de agosto de 2026).
