# Módulo de Remitos (MVP)

Documentación técnica del módulo de remitos de entrega de CotizaLaser. Complementa a `PROJECT_CONTEXT.md` (estado actual) y `PROJECT_MEMORY.md` (decisiones e historia).

## 1. Objetivo

Permitir que una empresa genere, consulte, imprima y gestione **remitos de entrega** asociados a cotizaciones, con **entregas parciales y completas**, sobre los datos reales del sistema. Flujo:

```
Cotización aceptada → Remito en borrador (siempre) ──[corte confirmado]──> Emitido → entrega parcial o completa → historial
                                                                     └→ anulado (con motivo)
```

**Regla obligatoria (confirmada con el negocio):** un remito **no puede emitirse** si el corte de sus piezas no está confirmado. Preparar borradores no lo exige.

No incluye facturación electrónica ni integración con ARCA, ni modifica costos, reglas de stock o estados de cotización.

## 2. Funcionalidades implementadas

- Crear remito (borrador) desde una cotización aceptada, eligiendo cuánto se entrega de cada ítem.
- Editar o eliminar un borrador; emitirlo (asigna número y pasa a contar como entrega).
- Anular un remito emitido (solo OWNER) con motivo obligatorio; el documento no se borra.
- Estado de entrega por cotización: cantidad total, entregada y pendiente, por ítem y global (`NONE` / `PARTIAL` / `COMPLETE`).
- Historial de remitos por cotización y listado general con búsqueda, filtro por estado y paginación.
- PDF imprimible (sin costos ni márgenes) con espacio de firma de quien entrega y de quien recibe.
- Eventos de auditoría en el historial de la cotización al emitir y anular.

## 3. Modelo de datos

Migración `b9c0d1e2f3a4` (solo agrega tablas; no toca datos existentes).

| Tabla | Propósito |
|---|---|
| `delivery_notes` | Cabecera. `company_id`, `quotation_id`, `client_id`, `number` (nullable hasta emitir), `status` (`DRAFT`/`ISSUED`/`VOIDED`), `issue_date`, `notes`, **foto** (`quotation_number`, `client_name`, `client_tax_id`, `client_address`), auditoría de emisión (`issued_at/by`), de anulación (`voided_at/by`, `void_reason`), `created_by_id`, `created_at`, `updated_at`. |
| `delivery_note_items` | Líneas. `quotation_item_id` (referencia a la línea exacta de la cotización), `piece_id`, **foto** (`piece_name`, `piece_description`), `quantity`, `unit` (`un`). |
| `document_sequences` | Contador consecutivo por `(company_id, doc_type)`. Hoy solo `DELIVERY_NOTE`. |

Restricciones en base de datos (la red de seguridad aunque falle la validación de aplicación):
`UNIQUE(company_id, number)`, `CHECK(status IN (...))`, `CHECK(quantity > 0)`, `UNIQUE(delivery_note_id, quotation_item_id)` (un ítem una sola vez por remito), FKs sin cascada hacia cotización/ítem (un ítem con remitos no puede borrarse).

**Foto histórica.** Cliente, número de cotización y datos de pieza se copian al crear el borrador y se **vuelven a copiar al emitir**; desde ese momento el documento no cambia aunque se edite el cliente o la pieza. No se duplican costos ni datos de la cotización.

## 4. Numeración

Formato `R-000001`, consecutivo **por empresa**. El número se asigna **al emitir** (los borradores no tienen número), así no quedan huecos por borradores descartados.

`next_sequence_number()` ejecuta `UPDATE document_sequences SET last_number = last_number + 1 ... RETURNING`: el UPDATE bloquea la fila del contador hasta el fin de la transacción, de modo que dos emisiones simultáneas se serializan (no se calcula `MAX(numero)+1`). Si la transacción se revierte, el contador se revierte. La primera emisión de una empresa crea el contador; si dos la crean a la vez, el índice único rechaza a una y reintenta. `UNIQUE(company_id, number)` respalda todo.

## 5. Reglas de negocio

1. Solo se emiten remitos de cotizaciones en estado `accepted` (se revalida al emitir).
1b. **Corte confirmado obligatorio para emitir** (ver §5.1). Un borrador sí puede existir, consultarse y modificarse sin corte confirmado; no se puede emitir, no consume numeración y no cuenta como entrega.
2. Cantidad por línea: entero > 0 (validación Pydantic, servicio y `CHECK` en DB). No hay líneas en cero ni remitos vacíos.
3. Por ítem: `entregado + a entregar ≤ cotizado`. **Solo los remitos `ISSUED` cuentan como entregados**; los borradores no.
4. Los ítems deben pertenecer a la cotización del remito; la cotización debe ser de la empresa autenticada. El `company_id` y el cliente nunca vienen del frontend (se toman del contexto autenticado y de la cotización).
5. Un remito emitido o anulado es de **solo lectura** (409 ante cualquier modificación). Un borrador sí se puede editar o borrar.
6. Anular: solo un remito `ISSUED`, solo OWNER, motivo obligatorio (3–500 caracteres). Registra quién y cuándo; las cantidades vuelven a quedar pendientes; el número anulado no se reutiliza.
7. **Guardas sobre funcionalidades existentes** (únicas modificaciones fuera del módulo):
   - No se puede **cancelar** una cotización con remitos emitidos (409: anular primero). No se cambia ningún estado de cotización automáticamente.
   - No se puede **eliminar un ítem** referenciado por algún remito (409).

### 5.1 Cómo se detecta que el corte está confirmado

No hay bandera nueva ni estado duplicado: se reutiliza el flujo de stock existente (reservar material → confirmar corte). Un **ítem de la cotización tiene el corte confirmado** si existe una `StockReservation` de esa cotización, de la misma empresa, con `status = 'CONSUMED'` y `quotation_item_id` igual al ítem (`delivery_notes._cut_confirmed_item_ids`). Es la misma definición que ya usa `QuotationDetailPage` para mostrar "cortado".

- **Alcance (regla definitiva para el MVP):** al emitir se exige el corte confirmado **únicamente de los ítems incluidos en el remito**; no se exige el corte de toda la cotización. Ejemplo: A (100, cortada), B (50, sin cortar), C (20, cortada) → se puede emitir un remito de A y C; no se puede emitir uno que incluya B mientras su corte no esté confirmado.
- **Orden de validación al emitir:** estado del remito (`DRAFT`) → cotización aceptada → corte confirmado → ítems/cantidades pendientes. Todo bajo el lock de la cotización.
- **Rechazo:** HTTP 409 `No se puede emitir el remito porque el corte de la cotización todavía no fue confirmado (falta confirmar: <piezas>).` No asigna número, no crea el contador de numeración y no modifica entregas.
- **No cuentan:** reservas `ACTIVE` (reservado, sin cortar), `RELEASED`, reservas de otra cotización o empresa, ni reservas `CONSUMED` sin `quotation_item_id` (no se puede atribuir a un ítem; no se asume).
- **Concurrencia:** `CONSUMED` es un estado terminal (nada lo revierte), por lo que lo leído bajo el lock de la cotización no puede dejar de ser cierto después de emitir. Si `confirm-cut` y la emisión corren a la vez, el resultado es o bien emitido con corte `CONSUMED`, o bien 409 con el borrador intacto y emitible después (verificado contra Postgres real).
- **Interacciones:** una cotización con corte confirmado no puede cancelarse (regla de stock existente, sin cambios); cancelar una cotización con remitos emitidos ya estaba bloqueado. Los ítems no se editan en `accepted`.
- **Límite del modelo (importante):** la reserva/corte es **por ítem, no por unidad**. Un ítem de 100 piezas tiene una única reserva; el sistema no puede saber cuántas de las 100 se cortaron. Por eso "corte confirmado" significa "el corte del ítem fue confirmado" y **no** prueba que toda la cantidad esté producida: la cantidad entregada sigue siendo responsabilidad del usuario (se limita solo por lo cotizado y lo ya entregado).

## 6. Permisos

Se reutiliza `get_current_company` / `require_owner`: cualquier miembro activo crea, edita, emite y consulta (igual que las cotizaciones); **anular es solo OWNER** (acción correctiva con efecto sobre entregas, como los demás cambios de configuración y descarte de stock). Aislamiento por empresa: un recurso de otra empresa responde 404.

## 7. Flujo

1. Detalle de una cotización aceptada → panel **Entregas** (cotizado / entregado / pendiente) → **Generar remito**.
2. Formulario: cliente y cantidades cotizadas/entregadas/pendientes en solo lectura; el usuario carga "Entregar ahora" y observaciones.
3. **Vista previa y emitir** → confirmación → crea el borrador y lo emite (o **Guardar borrador**). Si alguna pieza elegida no tiene el corte confirmado, el formulario muestra un aviso, la columna *Corte* indica "Sin confirmar" y **Vista previa y emitir** queda deshabilitado; **Guardar borrador** sigue disponible. El estado se recarga al volver a la pestaña (después de confirmar el corte en la cotización).
4. Detalle del remito: PDF, y según estado: editar / eliminar / emitir (borrador; deshabilitado con aviso y enlace a la cotización mientras falte confirmar el corte) o anular (emitido, OWNER).

La UI solo evita el intento: el backend rechaza igualmente toda emisión sin corte confirmado, venga de donde venga. Las respuestas de lectura exponen el dato (`cut_confirmed` por línea y global en el estado de entrega; `cut_confirmed` y `cut_pending_pieces` en borradores).
Endpoints (`/delivery-notes`): `POST /`, `GET /`, `GET /{id}`, `PUT /{id}`, `DELETE /{id}`, `POST /{id}/issue`, `POST /{id}/void`, `GET /{id}/pdf`, `GET /quotation/{quotation_id}`, `GET /quotation/{quotation_id}/status`.

## 8. Concurrencia e integridad

La invariante "entregado ≤ cotizado" depende de una **suma sobre varias filas**, que un único UPDATE condicional no puede garantizar. Por eso emitir y anular toman un lock de fila sobre la cotización (`SELECT ... FOR NO KEY UPDATE`; SQLAlchemy lo emite solo en PostgreSQL y es inocuo en SQLite) en un orden fijo (cotización → remito) para evitar deadlocks, y **revalidan las cantidades ya con el lock tomado**. Las transiciones de estado se verifican tras bloquear el remito. Cancelar una cotización toma el mismo lock, por lo que no puede cruzarse con una emisión.

**Por qué `FOR NO KEY UPDATE` y no `FOR UPDATE`** (incidente 2026-10-14): con `FOR UPDATE`, cancelar una cotización a la vez que `confirm-cut` terminaba en *deadlock* en Postgres: `confirm-cut` inserta filas con FK hacia la cotización (`stock_movements.quotation_id`), lo que toma `FOR KEY SHARE` sobre ella, y `FOR UPDATE` lo bloquea. `FOR NO KEY UPDATE` sigue serializando entre sí a emitir/anular/cancelar, pero no choca con los chequeos de FK. Detectado al correr `test_quotation_cancel_confirm_race_postgres.py` contra Postgres real.

Verificado contra PostgreSQL 18 real (6 escenarios concurrentes, 12 repeticiones cada uno): sobreentrega con dos emisiones, doble emisión del mismo borrador, numeración concurrente (incluida la creación del contador), anulación vs. emisión, y cancelación vs. emisión. Prueba de mutación: quitando el lock, los escenarios de sobreentrega y de cancelación fallan, lo que confirma que los tests detectan la carrera.

## 9. Casos de prueba

- `tests/test_delivery_notes.py` (SQLite): creación, consulta, emisión, PDF (borrador / emitido / anulado, sin costos), entregas 40/35/25 sobre 100, historial, anulación y recuperación de pendientes, foto histórica, permisos (empleado no anula), aislamiento entre empresas, ítems ajenos, cantidades negativas/cero/decimales, sobreentrega por dos borradores, doble emisión/anulación, solo lectura, cotización no elegible o cancelada, guardas de cancelación y borrado de ítem, constraints de DB.
- `tests/test_delivery_notes_cut_rule.py` (SQLite): emitir sin corte → 409; borradores permitidos sin corte; el rechazo no asigna número ni crea el contador ni cambia entregas; emitir tras confirmar el corte (borrador creado antes o después); reservas `ACTIVE`/`RELEASED`/sin ítem/de otra cotización/de otra empresa no cuentan; cobertura parcial por ítem; la regla no se evita ni creando como emitido, ni con PUT, ni como empleado; sin regresiones en entregas parciales, sobreentrega y anulación.
- `tests/test_delivery_notes_interleavings_postgres.py` (Postgres real, **deterministas**): cada orden concurrente se reproduce pausando una operación a mitad de su transacción y esperando (en `pg_stat_activity`) a que la otra quede bloqueada por el lock real; cubre saldo final entre dos emisiones, doble emisión, numeración (incluida la creación del contador), emitir vs. anular (ambos órdenes), emitir vs. cancelar (ambos órdenes), emitir vs. confirmar corte, y que empresas distintas nunca se bloquean entre sí. Una prueba de mutación (quitar el lock) hace fallar 5 de estos 9 tests.
- `tests/test_quotation_cancel_confirm_race_postgres.py`: reestructurado (ver §11): carrera estadística que solo afirma la invariante + dos tests deterministas (gana confirmar / gana cancelar) + órdenes secuenciales.
- `tests/test_delivery_notes_concurrency_postgres.py` (Postgres real; se saltea sin `DATABASE_URL`; incluido en el CI): además de los escenarios anteriores, `confirm-cut` concurrente con la emisión y emisiones concurrentes sin corte (todas 409, sin número).
- Frontend: `deliveryNotes.test.ts` (validación de cantidades), `DeliveryNoteFormPage.test.tsx`, `DeliveryNoteDetailPage.test.tsx`.

## 10. Limitaciones conocidas

- **El corte se confirma por ítem, no por unidad** (ver §5.1): el sistema no puede verificar que todas las unidades de un ítem estén producidas, solo que el corte del ítem fue confirmado. Tampoco existe un estado explícito "trabajo terminado" más allá de eso.
- Una reserva `CONSUMED` creada por API sin `quotation_item_id` no habilita remitos (no se puede atribuir a un ítem). La interfaz siempre envía el ítem.
- La unidad es siempre `un` (el modelo cuantifica piezas enteras).
- No hay edición de la fecha de emisión (es la fecha del negocio al emitir, zona `BUSINESS_TIMEZONE`).
- No se guarda el PDF (se genera al pedirlo, igual que las cotizaciones). Los datos de la empresa en el PDF son los actuales, no una foto.
- Un ítem referenciado por cualquier remito (incluso borrador o anulado) no puede eliminarse de la cotización.
- Una cotización `cancelled` con borradores: los borradores quedan sin poder emitirse.
- No hay recepción/firma digital ni numeración configurable (prefijo, punto de venta).

## 11. Auditoría final (2026-10-14)

Revisión técnica, funcional y visual del módulo completo. Hallazgos corregidos con prueba de regresión:

| Hallazgo | Severidad | Corrección |
|---|---|---|
| El encabezado de la tabla del PDF era **invisible** (texto oscuro sobre fondo oscuro); los tests de texto no lo detectaban, solo la inspección visual. | Alto | Encabezado claro; verificado renderizando el PDF. |
| Las hojas 2..n de un PDF multipágina **no identificaban el documento** (sin número ni "Hoja i de n"). | Medio | Pie en cada hoja: `Remito R-… · Cotización COT-… — Hoja i de n`. Test con 51 líneas. |
| `update_draft` no capturaba `IntegrityError` en el `flush` (un ítem eliminado en simultáneo daba 500). | Medio | Responde 409 como `create_draft`. |
| `test_quotation_cancel_confirm_race_postgres.py` fallaba ~50 % de las corridas (también en `HEAD`): su última aserción exigía que ganaran *ambos* lados de una carrera que decide el scheduler. | Medio | Reestructurado (ver abajo). 10/10 corridas en verde. |
| Leyenda de estado del PDF sin color de alerta. | Bajo | Texto en rojo. |
| Doble clic en emitir/guardar/anular. | Bajo | El botón ya se deshabilitaba; se agregó además un guard síncrono. |

**Test intermitente.** La propiedad de negocio es "una cotización nunca queda `cancelled` con su stock `CONSUMED`". Cada corrida de la carrera ya la verificaba; la aserción final dependía del scheduler. Ahora: (1) la carrera de 25 corridas conserva todas las invariantes y ya no exige un resultado concreto; (2) dos tests deterministas fuerzan cada rama real (confirmar gana mientras cancelar espera el lock de la reserva; cancelar gana mientras confirmar espera) usando `tests/_pg_sync.py`; (3) los dos órdenes secuenciales. Cobertura mayor que antes: las dos ramas ahora se ejercitan siempre.

**Orden de locks (verificado).** Emitir/anular: cotización (`FOR NO KEY UPDATE`) → remito → contador de numeración. Cancelar cotización: cotización → reservas → stock. Confirmar corte: reserva → stock → (FK `KEY SHARE` sobre la cotización, no bloqueado por `NO KEY UPDATE`). No existe un ciclo posible entre ellos. Cada empresa tiene su propia fila de cotización y de contador, por lo que no se bloquean entre sí (verificado).

**Verificación visual del PDF** (renderizado real, 9 casos: borrador, emitido, anulado, una pieza, 45 piezas, descripciones largas, cliente de nombre largo, observaciones de 1000 caracteres, sin logo): márgenes, alineación, logo, ajuste de texto y firmas correctos; multipágina con encabezado de tabla repetido y fila de total junto a las últimas filas; sin costos ni datos financieros. Una hoja de firmas puede quedar sola en la última página (es legible y está identificada).

**Frontend verificado en el navegador** (Postgres real): aceptar cotización → confirmar el corte de un ítem desde la interfaz → el panel de entregas se actualiza solo → remito con una pieza sin corte (emisión bloqueada, la API directa responde 409 y no asigna número) → editar el borrador → emitir → PDF (200, `application/pdf`) → anular con motivo → cantidades otra vez pendientes → reemisión con número nuevo (`R-000002`). Tema oscuro y vista móvil revisados.

**Mejoras futuras opcionales (no necesarias para el MVP):** paginación server-side del listado; en móvil, que "Entregar ahora" no quede fuera de pantalla (hoy la tabla hace scroll horizontal, como el resto de las tablas); el botón principal deshabilitado conserva color naranja en tema oscuro (comportamiento del tema global); confirmación de corte por unidad (requiere cambiar el modelo de stock).

