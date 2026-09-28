# Informe de optimizacion de rendimiento

## Objetivo

Reducir latencia, consultas repetidas, trabajo de filesystem y descargas innecesarias sin cambiar reglas funcionales, seguridad, leases, idempotencia ni versionado.

## Backend

### Sincronizacion documental

- Extracciones, errores y versiones se cargan en mapas antes del loop.
- Eliminadas consultas por documento dentro del barrido.
- Se conservan fingerprints, leases, savepoints y backfill legacy.
- Benchmark automatizado: 100 documentos requieren como maximo 7 `SELECT`.
- Antes el costo era aproximadamente `4-5 + 2N-3N` consultas.

### Lecturas agregadas

- `metricas_db` obtiene total, realizados, errores y pendientes sin tocar filesystem.
- Bandejas, contadores y productividad usan inventario persistido.
- Reconciliacion filesystem queda en dashboard, arbol, asignacion y finalizacion.
- Las mutaciones actualizan `Lote.estado` en su misma transaccion.
- Archivados se reconcilia para detectar PDF nuevos y reabrir lotes.

### Productividad

- Estadisticas agregadas en bloque para todos los operadores.
- Carga compartida por membresias activas.
- Productividad por autor real de versiones.
- Numero constante de consultas respecto a cantidad de operadores.

### Consultas y relaciones

- Eager loading de coordinador, asignador, miembros y operadores.
- Dashboard carga solo usuarios referenciados.
- Arbol reutiliza metricas ya calculadas.
- Limpieza temporal limitada a una vez cada 10 minutos por proceso.

### Indices MariaDB/MySQL

Migracion `20260928_11` agrega indices para:

- Membresias activas por operador.
- Leases por lote.
- Productividad por responsable/estado.
- Extracciones por lote, documento, usuario y fecha.
- Versiones por autor y documento.
- Errores por lote/fecha.
- Historial abierto por lote/operador.

No se eliminaron indices anteriores en esta fase para minimizar riesgo.

## Frontend

- Cancelacion de solicitudes obsoletas con `AbortController`.
- Deduplicacion de GET identicos en curso.
- Cache TTL opt-in para catalogos estables.
- Cache limpiado al cambiar sesion, login, logout o 401.
- Contadores silenciosos cada 30 segundos, al recuperar foco y por eventos.
- Heartbeat/release sin overlay global.
- `ExtraerModal` y PDF.js se descargan solo al abrir una extraccion.
- Descargas y renders PDF se cancelan al cambiar/cerrar documento.
- Debounce de zoom y resize.
- Catalogos de operadores y observaciones con cache e invalidacion.
- Requests de Dashboard, Asignar, Lotes, Historial, Errores y Archivados son cancelables.

## Medicion local

| Endpoint | Consultas SQL | Tiempo aproximado |
|---|---:|---:|
| Supervisión | 3 | 12.7 ms |
| Productividad | 4 | 9.7 ms |
| Contadores | 2 | 3.2 ms |
| Árbol, 5 carpetas con filesystem | 28 | 392 ms |

Los tiempos dependen del almacenamiento CIFS, cantidad de archivos y latencia de red.

## Verificacion

- Backend: 31 pruebas aprobadas.
- Frontend: 20 pruebas aprobadas.
- Alembic: `20260928_11 (head)`.
- Build de produccion correcto.
- `git diff --check` correcto.

## Riesgos residuales controlados

- El arbol de carpetas no materializadas conserva fallback por rutas y filesystem.
- PDFs grandes siguen limitados por CPU, red y PyMuPDF.
- Indices redundantes no se eliminan hasta observar planes reales en produccion.
- No se cachean leases, dashboard ni estados operativos por periodos prolongados.

## Siguiente nivel opcional

- `EXPLAIN ANALYZE` con cardinalidades de produccion.
- Agregacion masiva del arbol para carpetas no materializadas.
- Renderizado PDF vertical mediante `IntersectionObserver`.
- Paginacion de Archivados cuando supere cientos de registros.
