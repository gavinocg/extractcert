# Checklist de migración segura (servidores compartidos en producción)

> Principio: solo **añadir** (usuario, unit, site, BD+usuario). Nunca editar ni
> reiniciar servicios existentes sin respaldo y ventana de mantenimiento.

## 0. Accesos e info necesaria (para quien ejecute la migración)
- [ ] SSH (usuario + clave/llave) a ambos servidores, con sudo.
- [ ] IP del servidor MariaDB y credencial root/admin temporal.
- [ ] Dominio o subdominio para la app (ej. `extract.midominio.local`) y DNS apuntando al servidor app.
- [ ] Rutas de origen y repo en el servidor app (local, NFS o CIFS).
- [ ] Puertos en uso: `ss -tlnp` en el servidor app (si el 8000 está ocupado, cambiar `APP_PORT` en `deploy.sh` y `__PUERTO__` en nginx).

## 1. MariaDB (solo añade, no toca lo existente)
- [ ] Respaldo previo: `mysqldump --all-databases` (o al menos las BDs críticas).
- [ ] Crear BD + usuario **solo** para la app (ver pasos en el chat):
      `db_extract_py` + `'extract'@'%'` con GRANT **solo** sobre esa BD.
- [ ] Abrir 3306 **solo** hacia la IP del servidor app.
- [ ] Probar conexión desde el servidor app.

## 2. Servidor app (con routes de escape)
- [ ] Respaldo de nginx: `cp -r /etc/nginx/sites-enabled /tmp/nginx-sites-backup`.
- [ ] Ejecutar `deploy/deploy.sh` con `APP_DOMAIN` y `APP_PORT` definidos.
- [ ] El script valida `nginx -t` **antes** de recargar: si falla, no toca nada.
- [ ] Verificar: `systemctl status extractcert`, `/docs`, login `admin/Admin123`.
- [ ] **Cambiar la clave admin** y ajustar rutas en `/config`.
- [ ] `ufw allow 80,443/tcp`.

## 3. Rollback (si algo falla)
- [ ] App: `systemctl stop extractcert`, `rm /etc/nginx/sites-enabled/extractcert`, `nginx -t && systemctl reload nginx`.
- [ ] BD: `DROP USER 'extract'@'%'; DROP DATABASE db_extract_py;` (solo lo creado).
- [ ] Nada más queda modificado: el resto de servicios sigue intacto.

## 4. Post-migración
- [ ] HTTPS (certbot) si es accesible por nombre público.
- [ ] Cron de `mysqldump db_extract_py` + copia del repo destino.
- [ ] Rotar la clave del usuario `extract` periódicamente.
