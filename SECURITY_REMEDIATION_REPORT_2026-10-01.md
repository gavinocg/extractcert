# Informe de remediacion de seguridad - ExtractCert

Fecha: 2026-10-01  
Pentest base: `PENTEST_REPORT_2026-10-01.md`  
Produccion validada: `https://extractcert.rpcayambe.gob.ec`

## Resumen

Se implementaron y desplegaron las remediaciones tecnicas del pentest en autenticacion, sesiones, dependencias, webhook, despliegue, HTTP, SMTP, correo y procesamiento PDF. Las pruebas y auditorias automatizadas finalizaron sin vulnerabilidades conocidas en las dependencias.

Quedan dos acciones externas que requieren acceso a proveedores y no pueden completarse desde el servidor:

1. Activar HSTS en la zona Cloudflare. Cloudflare reemplaza el header seguro del origen por `Strict-Transport-Security: max-age=0`.
2. Rotar la credencial SMTP en el proveedor y actualizarla en Configuracion. No es posible generar una credencial valida del proveedor desde la aplicacion.

## Cambios implementados

### Autenticacion y sesiones

- Rate limiting de login por IP+cuenta, IP global y cuenta global.
- Ventana de 5 minutos, respuesta 429 y `Retry-After`.
- Memoria de rate limiting acotada.
- Respuesta uniforme para usuario inexistente, inactivo o clave incorrecta.
- Hash ficticio para reducir diferencias temporales de enumeracion.
- Registro de login exitoso, login fallido y logout.
- Logout protegido por CSRF e invalidacion mediante `token_version`.
- Comparacion CSRF en tiempo constante.
- Validacion de `Origin` cuando el navegador lo proporciona.
- Sesion predeterminada reducida de 8 horas a 60 minutos.

### Configuracion segura y bootstrap

- Produccion rechaza `SECRET_KEY` predeterminada, corta o trivial.
- Produccion exige `APP_URL` HTTPS.
- `ENVIRONMENT=production` configurado en el servidor.
- Eliminada la contraseña administrativa fija.
- Bootstrap opcional mediante `ADMIN_BOOTSTRAP_PASSWORD` segura.
- Si no existe Administrador en produccion y no hay secreto bootstrap, el arranque falla de forma segura.
- Cualquier reset administrativo obliga cambio en el siguiente inicio, aunque la clave elegida sea libre por requisito funcional.

### Dependencias

- FastAPI `0.142.2`.
- Starlette `1.7.0`.
- cryptography `50.0.2`.
- python-multipart `0.0.32`.
- PyJWT `2.15.1`.
- Vite `8.3.2`.
- Vitest `4.1.11`.
- nanoid `3.3.19`.
- `pip-audit`: sin vulnerabilidades conocidas.
- `npm audit`: 0 vulnerabilidades.

### HTTP y superficie publica

- CSP aplicada y validada externamente.
- `X-Frame-Options: DENY`.
- `X-Content-Type-Options: nosniff`.
- `Referrer-Policy: same-origin`.
- `Permissions-Policy` restrictiva.
- HSTS configurado en origen.
- `TrustedHostMiddleware` para dominio, localhost y loopback.
- API sensible con `Cache-Control: private, no-store`.
- HTML con `no-cache` y assets hash con cache inmutable.
- `/docs`, `/redoc` y `/openapi.json` responden 404 en produccion.
- Nuevo `/healthz` para healthcheck.
- Settings de rutas restringido a Administrador.

### Webhook y despliegue

- Cuerpo maximo de webhook: 1 MiB.
- Validacion estricta de `Content-Length`.
- Timeout de lectura.
- Metodos no permitidos rechazados.
- Deduplicacion acotada de `X-GitHub-Delivery`.
- Un solo despliegue concurrente en webhook.
- `flock` en el script para excluir webhook/timer simultaneos.
- Webhook ejecutado como usuario `extractcert`, no root.
- Regla sudo exacta: solo puede iniciar `extractcert-deploy.service`.
- Secreto webhook `0640 root:extractcert`.
- Sudoers `0440 root:root` y validado con `visudo`.
- Hardening systemd para aplicacion y webhook.
- Vhost Apache versionado con limite del webhook y `RequestReadTimeout`.
- Normalizacion automatica de grupo/permisos tras cada `git reset` y rollback.
- Healthcheck de deploy migrado de `/docs` a `/healthz`.

### SMTP y correo

- Prueba SMTP limitada al host guardado.
- La contraseña guardada no se reutiliza al cambiar host o usuario.
- Validacion DNS/IP y bloqueo de destinos no globales para hosts nuevos.
- Errores SMTP genericos para el cliente y detalle solo en logs.
- Destinatarios adicionales limitados a dominios configurados.
- Produccion permite adicionales bajo `rpcayambe.gob.ec`.
- Cuota de 10 reportes por usuario/hora.
- Auditoria de envios exitosos y logging de fallos.
- Rutas absolutas retiradas de los correos de errores.

### PDF y archivos

- Limite predeterminado de PDF: 250 MiB.
- Limite predeterminado: 5000 paginas por documento.
- Limite predeterminado: 500 paginas por extraccion y orden personalizado.
- Errores internos de PDF permanecen genericos para apertura.
- Se mantienen confinamiento de rutas, membresia, leases y reserva exclusiva de nombres.

## Validacion

- Backend: 73 pruebas aprobadas.
- Webhook: 3 pruebas aprobadas.
- Frontend: 23 pruebas aprobadas.
- Build Vite correcto.
- `pip-audit`: sin vulnerabilidades conocidas.
- `npm audit`: 0 vulnerabilidades.
- `bash -n deploy/deploy-prod.sh`: correcto.
- `py_compile deploy/webhook.py`: correcto.
- Apache `configtest`: `Syntax OK`.
- Produccion `/`: 200.
- Produccion `/healthz`: 200.
- Produccion `/docs`: 404.
- Produccion `/openapi.json`: 404.
- Produccion `/api/usuarios` anonimo: 401.
- Servicios `extractcert`, `extractcert-webhook` y Apache: activos.
- Webhook confirmado con `User=extractcert`, `ProtectSystem=strict`, `ProtectHome=yes` y `PrivateTmp=yes`.

## Incidentes durante implementacion

La primera activacion del hardening encontro archivos nuevos creados con modo 600 por el webhook root anterior. FastAPI no pudo leer temporalmente `main.py`/`__init__.py`. Se restauro el servicio y se implemento una correccion permanente en `deploy-prod.sh` que normaliza grupo y lectura/ejecucion para `backend`, `frontend/dist` y `deploy` despues de cada reset o rollback. Los despliegues posteriores se validaron con servicio saludable.

## Riesgos residuales y acciones externas

### Cloudflare HSTS

El origen emite `max-age=31536000`, pero la respuesta publica sigue mostrando `max-age=0` por configuracion de Cloudflare. Debe habilitarse HSTS en el panel/API de la zona. No activar `includeSubDomains` hasta verificar todos los subdominios.

### Credencial SMTP

Debe rotarse en el proveedor de correo y actualizarse mediante Configuracion > SMTP. El archivo de produccion mantiene permisos 600 y el secreto persistido se cifra, pero una rotacion real requiere emitir una nueva credencial externa.

### Rate limiting perimetral

El backend ya limita IP y cuenta. Se recomienda mantener una regla adicional de Cloudflare para `/api/auth/login` y `/hooks/deploy`, porque el proxy dispone de la IP publica autentica y puede absorber trafico antes de llegar al servidor.

## Estado final

Los hallazgos explotables desde codigo/servidor quedaron corregidos o mitigados. Los dos pendientes externos estan identificados y no requieren cambios adicionales en el repositorio.
