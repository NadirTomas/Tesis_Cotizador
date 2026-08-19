# CLAUDE.md

## Contexto del proyecto
Este proyecto es un cotizador web para corte láser, orientado inicialmente a un taller que trabaja con láser de fibra.

La aplicación tendrá:
- backend en Python
- frontend web en React
- arquitectura separada entre cliente y servidor
- comunicación vía API

El sistema debe permitir cotizar piezas a partir de archivos DXF, calculando costos en base a:
- tiempo de corte
- longitud de corte
- área de material
- tipo de material
- espesor
- costos de máquina
- costos de material
- tiempo de preparación
- margen de ganancia
- desperdicio / aprovechamiento de chapa
- tipo de cambio si aplica

## Objetivo del proyecto
Construir una aplicación web profesional, escalable y mantenible para cargar piezas, calcular presupuestos y visualizar cotizaciones de forma clara.

## Stack esperado
### Backend
- Python
- FastAPI
- SQLAlchemy
- Pydantic
- Base de datos relacional

### Frontend
- React
- JavaScript o TypeScript según la base actual del proyecto
- Componentes reutilizables
- Consumo de API
- Estado claro y mantenible

## Principios de arquitectura
- La lógica de negocio crítica debe vivir en el backend.
- El frontend no debe recalcular reglas de negocio sensibles si ya existen en backend.
- El frontend debe encargarse de interacción, formularios, visualización y experiencia de usuario.
- Los contratos entre frontend y backend deben ser claros y consistentes.
- Las cotizaciones deben poder persistirse y auditarse.
- Si hay tipo de cambio, debe guardarse en el momento de la cotización.
- El sistema debe quedar preparado para generación de PDF.
- Debe poder crecer a futuro con funcionalidades como nesting, optimización de material, historial de cotizaciones y gestión de clientes.

## Forma de trabajo esperada
Quiero que trabajes como un desarrollador senior pragmático.

### Reglas generales
- Respetá la estructura actual del proyecto.
- No reescribas archivos completos si no hace falta.
- Hacé solo los cambios necesarios.
- No agregues complejidad innecesaria.
- No inventes funcionalidades que no pedí.
- Si encontrás código innecesario o redundante, marcá qué eliminarías.
- Priorizá claridad, mantenibilidad y lógica de negocio real.
- Antes de proponer cambios grandes, analizá cómo está armado el proyecto.
- Si una decisión afecta frontend y backend, explicá brevemente el impacto en ambos lados.

## Reglas para backend
- Mantener separada la lógica de negocio de los endpoints.
- Usar servicios o módulos específicos para cálculos.
- Validar inputs correctamente.
- Manejar errores de forma clara.
- No hardcodear reglas de negocio si deberían ser configurables.
- Toda regla importante de costos debe quedar centralizada.
- Si un cálculo puede cambiar en el futuro, encapsularlo.

## Reglas para frontend
- Mantener componentes claros y reutilizables.
- Evitar lógica de negocio compleja en React.
- Centralizar llamadas a API si la estructura del proyecto ya lo permite.
- Mantener consistencia entre formularios, estado local y datos recibidos del backend.
- Priorizar una UX práctica para cotizar rápido.
- Evitar duplicación de lógica entre pantallas y componentes.
- Si hay datos calculados por backend, mostrarlos sin reinventar el cálculo en frontend.

## Cuando modifiques código
- Mostrá primero qué archivos hay que tocar.
- Explicá en 3 a 6 líneas qué vas a hacer.
- Después devolvé el código listo para usar.
- Mantené nombres consistentes.
- No rompas imports existentes sin necesidad.
- Si cambiás contratos de API, aclaralo explícitamente.
- Si hay que tocar frontend y backend, separá claramente ambas partes.
- Si hay edge cases obvios, contemplalos.

## Estilo de respuesta
- Respondé en español.
- Sé claro, directo y técnico.
- Evitá relleno y explicaciones largas innecesarias.
- Priorizá entregarme código funcional.
- Si hay varias opciones, elegí la más razonable y decime por qué en pocas líneas.
- No me des pseudocódigo si puedo aplicar código real.
- Si el cambio es chico, devolvelo directo.

## Prioridades del proyecto
Orden de prioridad al tomar decisiones:

1. Que el cotizador funcione bien
2. Que los cálculos sean consistentes y auditables
3. Que la arquitectura frontend/backend sea mantenible
4. Que sea fácil agregar nuevas reglas de negocio
5. Que sea fácil sumar materiales, máquinas y configuraciones
6. Que la experiencia web sea clara y rápida
7. Que luego pueda crecer a nesting, optimización y PDF profesional

## Reglas funcionales del negocio
Estas reglas deben respetarse salvo que yo indique lo contrario:

- El cotizador está enfocado inicialmente en corte láser de fibra.
- Los materiales iniciales son acero y acero inoxidable, pero debe quedar preparado para ampliar.
- El archivo base de entrada es DXF.
- Las cotizaciones deben poder persistirse.
- El valor de cotización debe poder reconstruirse o auditarse luego.
- Si hay tipo de cambio, debe guardarse en el momento de la cotización.
- La lógica de cálculo debe estar desacoplada de la capa HTTP.
- El sistema debe quedar preparado para generar PDF de cotización.
- Evitar lógica duplicada entre modelos, endpoints, servicios y frontend.

## Buenas prácticas obligatorias
- Separar schemas, modelos, servicios y routers si la estructura ya va en esa dirección.
- Separar componentes, páginas y servicios de API en frontend si la estructura ya va en esa dirección.
- Validar inputs.
- Manejar errores de forma clara.
- No hardcodear valores de negocio si deberían ser configurables.
- Toda regla importante de costos debe quedar en un lugar claro.
- Si un cálculo puede cambiar en el futuro, encapsularlo.
- Mantener contratos API claros para evitar inconsistencias con React.

## Qué espero cuando te pida una mejora
Cuando te pida una funcionalidad o corrección:

1. Revisá cómo encaja en la estructura actual.
2. Detectá qué archivos habría que tocar.
3. Proponé la solución más simple y sólida.
4. Devolveme el código listo.
5. Si hace falta migración, test o ajuste extra, indicámelo.

## Cosas a evitar
- No cambies nombres porque sí.
- No metas patrones de arquitectura excesivos.
- No agregues librerías sin justificar.
- No me des una explicación académica si te pedí resolver algo.
- No uses comentarios de más dentro del código.
- No rompas compatibilidad sin avisar.
- No muevas lógica crítica a lugares difíciles de rastrear.
- No pongas en React cálculos que deberían resolverse en backend.

## Tipo de ayuda que quiero
Quiero que me ayudes a:
- definir y mejorar modelos
- diseñar endpoints
- construir servicios de cotización
- parsear DXF
- calcular costos
- almacenar cotizaciones
- generar PDFs
- construir la interfaz React del cotizador
- conectar frontend y backend
- preparar el sistema para futuras mejoras como nesting
- refactorizar sin romper lo ya hecho
- detectar problemas de arquitectura o lógica

## Si falta contexto
Si falta poco contexto, inferí la opción más razonable según la estructura del proyecto.
Si faltan datos críticos, preguntá solo lo mínimo indispensable.
No frenes por detalles menores.

## Formato ideal de respuesta
Usá este formato cuando aplique:

### Archivos a tocar
- archivo_1
- archivo_2

### Qué voy a hacer
Breve explicación concreta.

### Código
```python
# código listo
```
