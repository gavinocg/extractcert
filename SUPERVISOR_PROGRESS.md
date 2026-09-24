# Implementacion del rol Supervisor

Fecha de inicio: 2026-09-24

## Decisiones funcionales

- Un lote es una carpeta final que contiene archivos PDF.
- El contenido del lote es dinamico: nuevos PDFs modifican el total y el avance.
- Existe un operador activo por lote.
- La reasignacion conserva el avance y genera historial.
- El 100% se alcanza cuando no quedan pendientes; los errores revisados cuentan como procesados.
- La finalizacion se notifica al supervisor responsable y a los administradores activos.
- Los supervisores ven todo el repositorio y tambien pueden procesar PDFs.

## Avance por fases

| Fase | Estado | Verificacion |
|---|---|---|
| 1. Migraciones y registro | Completada | Revision local `20260924_01` aplicada |
| 2. Modelos, roles y correo | Completada | ORM importado y esquema inspeccionado |
| 3. Autorizacion, metricas y API | Completada | Pruebas de metricas y build correctos |
| 4. Notificaciones por correo | Completada | Registro persistente e idempotencia implementados |
| 5. Frontend | Completada | TypeScript y build Vite correctos |
| 6. Pruebas integrales | Completada | Backend 11/11; frontend 11/11 |
| 7. Documentacion y despliegue | Completada | README, env y deploy actualizados |

## Componentes implementados

- Rol Supervisor y correo unico opcional en usuarios.
- Lotes dinamicos por carpeta final, asignacion activa e historial de reasignaciones.
- Bandeja restringida para operadores y supervision global para Supervisor/Administrador.
- Autorizacion backend aplicada a carpetas, PDFs, extracciones y errores.
- Recalculo dinamico de realizados, errores, pendientes y porcentaje sin doble conteo.
- Correo HTML de asignacion, reasignacion y finalizacion con auditoria de resultados.
- Pantalla Asignar con navegacion jerarquica, busqueda de operador y total de PDFs.
- Boton Notificar finalizacion habilitado unicamente sin pendientes.

## Verificaciones 2026-09-24

- `alembic current`: `20260924_01 (head)`.
- `python -m pytest -q`: 11 pruebas aprobadas.
- `npm test`: 11 pruebas aprobadas.
- `npm run build`: build de produccion aprobado.
- Usuarios locales pendientes de correo: 5. Deben completarse desde Administracion de usuarios.

## Ampliacion SMTP

- Se agregaron los submenus `General` y `SMTP` dentro de Configuracion.
- SMTP permite administrar servidor, puerto, usuario, clave, remitente y TLS.
- La clave configurada no se devuelve al navegador y un campo vacio conserva la existente.
- El servicio de correo consulta la configuracion persistida sin requerir reinicio.
- Verificacion: backend 12/12, frontend 11/11 y build de produccion aprobado.

## Correccion de reasignacion

- Se identifico que la reasignacion se guardaba, pero el registro de correo excedia los 30 caracteres de `notificaciones.tipo` y devolvia 500.
- La revision `20260924_02` amplia el campo a 100 caracteres.
- El registro de correo ahora captura fallos de auditoria sin invalidar una asignacion ya confirmada.

## Prueba SMTP

- Configuracion SMTP incluye un destinatario de prueba y el boton `+ Probar envio`.
- La prueba usa los valores actuales del formulario y conserva la clave almacenada si se deja vacia.
- El endpoint de prueba esta restringido a administradores y protegido con CSRF.

## Plan de correccion de regresiones

| Fase | Alcance | Estado |
|---|---|---|
| 1 | Temporales por usuario, contactos, historial y reglas de usuarios asignados | Completada |
| 2 | Bloqueo de reasignaciones e idempotencia concurrente de correos | Completada |
| 3 | SMTP atomico, escape HTML y confinamiento por ruta real | Completada |
| 4 | Navegacion de operador, filtros asincronos y responsive | Completada |
| 5 | Pruebas de regresion, migraciones y build final | Completada |

### Resultado

- Los PDF temporales se identifican por usuario y rechazan accesos cruzados.
- Solo Supervisor y Administrador modifican contactos; los operadores conservan lectura para reportes.
- Supervisor obtiene historial global y filtro por operador.
- Usuarios con actividad no se eliminan; operadores con lotes deben reasignarlos antes de cambiar rol o estado.
- Asignaciones usan bloqueo de base de datos y repetir el mismo operador no altera historial ni notificaciones.
- Notificaciones tienen unicidad SQL por lote, evento y destinatario, con reclamo atomico para reintentos.
- SMTP se guarda en una transaccion y la clave queda cifrada con `SECRET_KEY`.
- Correos de errores escapan contenido HTML y las rutas validan la ubicacion real tras resolver enlaces.
- La navegacion de operador no ofrece subir fuera del lote; asignacion ignora respuestas HTTP obsoletas.
- Sidebar y tabla de usuarios cuentan con comportamiento responsive.
- Base local migrada a `20260924_03 (head)`; secreto SMTP existente convertido a formato cifrado.
- Verificacion: backend 12/12, frontend 11/11 y build de produccion aprobado.

## Plan de endurecimiento posterior

| Bloque | Alcance | Estado |
|---|---|---|
| 1 | Rollback de codigo, dependencias y revision Alembic ante fallos | Completado |
| 2 | Lease para asignaciones/finalizaciones y recuperacion de correos | Completado |
| 3 | Escritura compensable de extracciones | Completado |
| 4 | Usuarios, locking inicial y respuestas asincronas | Completado |
| 5 | Guards de rutas y responsive global | Completado |

### Resultado del endurecimiento

- Las revisiones `20260924_04` y `20260924_05` agregan leases recuperables y una fila estable de locking.
- Reasignacion y finalizacion se bloquean mientras SMTP procesa; leases abandonados vencen en cinco minutos.
- Repetir una asignacion al mismo operador reintenta correos fallidos sin alterar el historial.
- Extracciones usan reserva exclusiva, archivo temporal, reemplazo atomico y compensacion ante rollback.
- Username y correo duplicados devuelven conflicto controlado en lugar de error 500.
- Solo lotes activos impiden desactivar o cambiar el rol de un operador.
- Dashboard y arbol de asignacion descartan respuestas asincronas obsoletas.
- Rutas administrativas usan guards declarativos y las tablas tienen scroll tactil global en movil.
- Deploy restaura revision Alembic, codigo y dependencias si falla antes o despues del healthcheck.
- Base local validada en `20260924_05 (head)`.
- Verificacion final: backend 12/12, frontend 11/11, build Vite y sintaxis de deploy aprobados.

## Liberacion de lotes

- Supervisor y Administrador pueden liberar un lote desde Supervision y Asignar.
- Liberar cierra el historial activo, conserva el avance y elimina el operador responsable.
- La tabla de supervision reemplaza la accion Notificar por Liberar; los operadores conservan Notificar finalizacion.

## Bandejas separadas

- Supervisores activos pueden recibir lotes igual que los operadores.
- `Trabajo pendiente` muestra exclusivamente los lotes asignados al usuario autenticado.
- `Bandeja supervision` muestra solo lotes que tienen un responsable para seguimiento.
- Al liberar un lote desaparece de Supervision y permanece disponible en Asignar.

## Contadores de bandejas

- `Trabajo pendiente` fue renombrado a `Pendientes`.
- El menu muestra badges rojos con texto negro para pendientes personales y lotes de supervision bajo 100%.
- Los contadores se refrescan tras asignar, liberar, extraer, registrar errores y notificar.
- Los badges se ocultan cuando su contador es cero.
- Corregido el arbol en Windows cuando una unidad mapeada se resuelve a una ruta UNC.

## Salida de Pendientes

- Un lote al 100% permanece en Pendientes hasta ejecutar `Notificar finalizacion`.
- Desaparece unicamente al quedar en estado `notificado`.
- Si recibe nuevos PDF despues, se reabre y vuelve a aparecer automaticamente.

## Productividad de operadores

- Supervision incluye una segunda tabla con carga y productividad por operador.
- Muestra lotes, lotes completados, PDF asignados, realizados, errores, pendientes y avance.
- Incluye extracciones, paginas procesadas y promedio diario de los ultimos 30 dias.
- Supervision permite reasignar cada lote mediante un dialogo con busqueda de responsable.
- La productividad mensual y el promedio diario se calculan por cantidad de archivos PDF procesados; se elimino el indicador de paginas.

## Cierre de hallazgos criticos y regresiones

- Deploy marca el intento de migracion antes de Alembic y evita volver a codigo antiguo si no puede recuperar un DDL parcial.
- Extracciones usan lock global compartido con asignar/liberar, revalidan acceso antes del commit y no compensan despues de confirmar DB.
- Identidad unica de PDF usa lote + nombre con sensibilidad acorde al filesystem, independiente de X: o UNC.
- `processed_at` registra cada procesamiento o reextraccion para productividad mensual correcta.
- Finalizacion limpia leases sin destinatarios y recalcula metricas/asignacion despues de SMTP antes de notificar.
- Historial conserva fechas de finalizacion y notificacion al reasignar o liberar.
- Consultas LIKE escapan `%`, `_` y `\\`; metricas distinguen nombres por la semantica del filesystem.
- Errores y extracciones en vuelo se serializan con reasignacion/liberacion.
- Frontend descarta respuestas obsoletas entre bandejas, reporta fallos de correo y conserva contexto en Dashboard/Visor/Asignar.
- Migraciones locales aplicadas hasta `20260924_08 (head)` sin claves nulas ni duplicadas.
- Verificacion final: backend 16/16, frontend 11/11, build Vite, sintaxis deploy y smoke HTTP aprobados.

## Notas de despliegue

- Respaldar MariaDB antes de ejecutar migraciones.
- Completar los correos de usuarios existentes antes de asignar lotes.
- Ejecutar `alembic upgrade head` desde `backend` antes de reiniciar el servicio.
- No depender de `create_all()` para modificar tablas existentes.
