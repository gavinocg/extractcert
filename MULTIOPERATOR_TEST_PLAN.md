# Informe y plan de pruebas multioperador

## Alcance implementado

- Varios operadores y supervisores activos por lote.
- Inventario persistente por PDF (`lote_documentos`).
- Reserva exclusiva por documento con lease de 10 minutos.
- Heartbeat cada 4 minutos mientras se extrae o edita un error.
- Recuperacion automatica de leases vencidos.
- Guardado idempotente mediante UUID por operacion.
- Extracciones y reextracciones versionadas sin sobreescribir versiones anteriores.
- Auditoria por autor, paginas, fecha, tipo y archivo de cada version.
- Deteccion de reemplazo del PDF original por tamano y fecha de modificacion.
- Finalizacion bloqueada mientras haya pendientes o leases activos.
- Productividad atribuida al autor real de cada version.

## Modelo de trabajo

Los miembros de un lote comparten su inventario. Un PDF solo puede ser reservado por una persona a la vez. Los demas usuarios ven `En uso por ...` y no pueden iniciar acciones hasta que se libere o expire el lease.

## Preparacion

1. Crear dos operadores de prueba activos con correo.
2. Crear una carpeta final con al menos 10 PDF pequenos.
3. Asignar el mismo lote a ambos operadores.
4. Abrir sesiones separadas en dos navegadores o perfiles privados.
5. Mantener abierta la Bandeja supervision en una tercera sesion de Supervisor.

## Casos de aceptacion

### 0. Vista previa movil

1. Abrir un PDF desde un telefono o tablet.
2. Seleccionar paginas y abrir la vista previa final.
3. Pellizcar con dos dedos para acercar y alejar.
4. Arrastrar con un dedo el documento ampliado.
5. Probar los botones `-` y `+`.

Resultado esperado: zoom fluido entre 25% y 200%, desplazamiento sin mover la pagina web y comportamiento de escritorio sin cambios.

### 1. Asignacion multiple

1. Seleccionar dos responsables en `Asignar`.
2. Confirmar la asignacion.
3. Verificar que ambos aparecen en Supervisión y reciben correo.
4. Iniciar sesion con ambos y confirmar que el lote aparece en Pendientes.

Resultado esperado: ambos ven el lote y el mismo total de documentos.

### 2. Reserva exclusiva

1. Operador A abre un PDF pendiente.
2. Operador B actualiza la bandeja.
3. Operador B intenta abrir el mismo PDF.

Resultado esperado: B ve `En uso por A`; el backend responde 409 si intenta reclamarlo directamente.

### 3. Trabajo paralelo

1. A abre PDF 1.
2. B abre PDF 2.
3. Ambos previsualizan y guardan.

Resultado esperado: ambos guardados finalizan, se crean archivos versionados distintos y el avance aumenta en dos.

### 4. Doble clic y retry

1. Guardar una extracción y simular doble clic o repetir la misma solicitud con igual idempotency key.

Resultado esperado: se devuelve la misma version; no aparece un segundo archivo ni una segunda fila.

### 5. Dos pestanas de la misma cuenta

1. Abrir el mismo PDF en una pestana.
2. Intentar abrirlo en otra pestana con la misma cuenta.

Resultado esperado: la segunda pestana recibe conflicto y no invalida el trabajo de la primera.

### 6. Heartbeat

1. Mantener abierto un modal por mas de 10 minutos.
2. Confirmar en otra sesion que el documento sigue reservado.
3. Guardar desde el primer modal.

Resultado esperado: el heartbeat renueva el lease y el guardado funciona.

### 7. Lease abandonado

1. Reclamar un PDF y cerrar forzosamente el navegador sin liberar.
2. Esperar mas de 10 minutos.
3. Reclamarlo desde otro operador.

Resultado esperado: el segundo operador recupera el documento.

### 8. Error concurrente

1. A abre un PDF y registra un error.
2. B intenta modificarlo mientras A mantiene la reserva.

Resultado esperado: B no puede modificarlo. Tras guardar A, el documento queda en error y el lease se libera.

### 9. Reextraccion versionada

1. Abrir un PDF completado.
2. Crear una nueva version con otro rango de paginas.
3. Consultar historial/archivado.

Resultado esperado: la nueva version queda vigente; la version anterior permanece fisicamente y en auditoria.

### 10. Cambio externo del original

1. Completar un PDF.
2. Sustituir el original por otro archivo con igual nombre y diferente contenido/tamano.
3. Actualizar la bandeja.

Resultado esperado: vuelve a pendiente y requiere procesamiento nuevo.

### 11. Retiro de un miembro

1. A mantiene un documento reservado.
2. Supervisor elimina a A de los responsables del lote.

Resultado esperado: el lease de A se libera y A ya no puede guardar; otro miembro puede reclamarlo.

### 12. Finalizacion segura

1. Completar todos los PDF entre ambos operadores.
2. Mantener una reextraccion abierta e intentar notificar.

Resultado esperado: notificacion rechazada mientras exista lease activo. Al cerrar/guardar, se permite notificar y archivar.

## Evidencia tecnica esperada

- Una fila activa por miembro en `lote_operadores`.
- Una fila por PDF en `lote_documentos`.
- Un unico lease vigente por documento.
- Una fila por version en `extraccion_versiones`.
- Rutas fisicas con estructura `lote-{id}/documento-{id}/v{n}/archivo.pdf`.
- Ninguna idempotency key duplicada.
- Cero documentos `procesando` con lease vencido despues de reconciliar.

## Criterio de aprobacion

Todos los casos deben completarse sin errores 500, archivos duplicados, sobreescritura de versiones, perdida de autor, avance duplicado ni finalizacion con operaciones activas.
