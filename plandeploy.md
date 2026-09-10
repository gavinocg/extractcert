# Plan de despliegue a producción

Destino: servidor app `192.168.1.113` (Ubuntu 24.04, Apache con 6 sitios productivos
que **no se tocan**) + MariaDB separada `192.168.1.114` (BD `db_extract_py` ya
importada). Exposición: subdominio `extractcert.rpcayambe.gob.ec` con vhost nuevo
restringido a `192.168.1.0/24`.

## Fase 1 — Compilar en local
1. `cd frontend && npm run build` (genera `dist/` con `pdfjs-wasm` incluido).
2. Verificar `dist/index.html` y `dist/pdfjs-wasm/jbig2.wasm`.
3. Empaquetar excluyendo: `backend/.venv`, `backend/.env`, `frontend/node_modules`,
   `__pycache__`, `storage/tmp/*`.

## Fase 2 — Servidor 192.168.1.113 (SSH gcarranco + sudo)
4. Subir el paquete a `/opt/extractcert`, crear usuario dedicado `extractcert`.
5. `python3 -m venv backend/.venv && backend/.venv/bin/pip install -r backend/requirements.txt`.
6. Crear `backend/.env` (no copiar el local):
   `DATABASE_URL=mysql+pymysql://usr_extractcert:***@192.168.1.114:3306/db_extract_py`,
   `SECRET_KEY` nuevo aleatorio, `DEFAULT_RAIZ_ORIGEN/REPO` con las rutas Linux finales.
7. Probar conexión a la BD desde el servidor antes de arrancar.
8. Unit systemd `extractcert` (1 worker por la RAM de 1 GB) + `enable/start`;
   verificar API en `127.0.0.1:8000` (`/docs`).

## Fase 3 — Apache (sitio nuevo, existentes intactos)
9. Vhost `extractcert.rpcayambe.gob.ec` como proxy reverso a `127.0.0.1:8000`
   con `Require ip 192.168.1.0/24`.
10. `apachectl configtest` y reload **solo** si pasa.
11. El subdominio debe resolver en LAN a `192.168.1.113`.

## Fase 4 — Post-despliegue
12. Login `admin`, cambiar la clave y actualizar rutas Windows clonadas en `/config`.
13. Prueba funcional punta a punta (extraer, preview, guardar, errores).
14. `ufw allow 80,443/tcp`; HTTPS con certbot si aplica.

## Rollback
- App: `systemctl stop extractcert`, quitar el vhost nuevo, `configtest` + reload.
- BD: solo se añadió uso sobre `db_extract_py` existente; no se crea ni borra nada.
- El resto de servicios queda intacto.

Artefactos listos en `deploy/`: `extractcert.service`, `.env.example`,
`MIGRATION_CHECKLIST.md`, `webhook.py`, `deploy-prod.sh`,
`extractcert-webhook.service`, `extractcert-deploy.{service,timer}`.

## Despliegue continuo dev -> prod -> servidor
Cada push a `prod` despliega solo:

1. **Flujo de release (en local)**: merge `dev` -> `main` -> `prod`.
   Luego **reemplazo limpio** de `dist/` (un `add` normal acumula bundles
   viejos y deja `index.html` desactualizado):
   `git checkout prod`, `git rm -rq frontend/dist`, borrar `frontend/dist`,
   `node node_modules/vite/bin/vite.js build` en `frontend/` (vía node
   directo, no el shim `.bin`), copiar el `dist/` fresco, `git add -f
   frontend/dist`, commit y `git push origin prod`.
2. **GitHub -> servidor**: webhook `https://extractcert.rpcayambe.gob.ec/hooks/deploy`
   (evento push, secreto HMAC en repo Settings > Webhooks). Apache proxifica
   `/hooks/deploy` a `127.0.0.1:9000` sin restricción de IP; el receptor
   `webhook.py` verifica firma y rama `refs/heads/prod`, responde 202 y
   ejecuta `deploy-prod.sh` en fondo.
3. **`deploy-prod.sh`**: fetch, fast-forward, `pip install` si cambió
   `requirements.txt`, restart, healthcheck (`/` y `/docs`), rollback al
   commit previo ante fallo.
4. **Respaldo**: timer `extractcert-deploy.timer` cada 30 min por si un
   webhook no llega. `/opt/extractcert` es repo git en rama `prod`
   (`.env`, `.venv` y `storage/` sin versionar, se conservan).
