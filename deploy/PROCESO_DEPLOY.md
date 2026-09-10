# Proceso de deploy: dev -> main -> prod -> servidor

Cada push a `prod` despliega automáticamente en
`https://extractcert.rpcayambe.gob.ec/` vía webhook + `deploy-prod.sh`
(ver `plandeploy.md`). Este documento describe el flujo completo,
incluidas las trampas ya encontradas.

## Ramas
- `dev`: trabajo diario.
- `main`: integración estable.
- `prod`: lo que corre en producción. Incluye `frontend/dist/` commiteado
  (ignorado en las demás ramas). **Nunca se commitea directo en `prod`**,
  solo merges + release de `dist/`.

## Release paso a paso (en local, rama dev)

```powershell
# 0. Todo commiteado en dev y checks en verde
#    (tsc, Vitest, pytest según lo tocado)

# 1. Integrar a main
git checkout main
git merge --ff-only dev
git push origin main

# 2. Llevar a prod (merge, NUNCA fast-forward si divergió por dist/)
git checkout prod
git merge --no-ff -m "Merge main a prod" main

# 3. Reemplazo LIMPIO de dist/ (obligatorio: un add normal acumula
#    bundles viejos y deja index.html apuntando al bundle anterior)
git rm -rq frontend/dist
Remove-Item -Recurse -Force frontend/dist
cd frontend
node node_modules/vite/bin/vite.js build   # vía node directo, NO el shim .bin
cd ..
git add -f frontend/dist

# 4. Verificar que index.html apunta al bundle nuevo
Select-String -Path frontend/dist/index.html -Pattern 'assets/index-.*\.js'

# 5. Commit + push (dispara el webhook -> auto-deploy)
git commit -m "Release prod con build actualizado"
git push origin prod
git checkout dev
```

## Qué hace el servidor al recibir el push
1. GitHub POST a `/hooks/deploy` (firma HMAC + solo `refs/heads/prod`).
2. `webhook.py` responde 202 y ejecuta `deploy/deploy-prod.sh`:
   fetch, fast-forward (`reset --hard`), `chown storage/`,
   `pip install` si cambió `requirements.txt`, restart,
   healthcheck (`/` y `/docs`) y rollback automático ante fallo.
3. Timer `extractcert-deploy` cada 30 min como respaldo.

## Verificación post-deploy
```powershell
# Desde cualquier máquina con plink: cola del deploy
# journalctl -t extractcert-deploy --since -5min
# Bundle servido (debe coincidir con dist/index.html local):
# curl -sk https://extractcert.rpcayambe.gob.ec/ | grep index-
```
En el navegador: recarga fuerte (`Ctrl+F5`) para soltar `index.html` cacheado.

## Rollback manual
- Auto: el script revierte solo ante healthcheck fallido.
- Manual: en el servidor `git -C /opt/extractcert reset --hard <SHA-anterior>`
  y `systemctl restart extractcert`; o `git revert` en `prod` + push
  (dispara un deploy que revierte).

## Troubleshooting conocido
- **No se ven los cambios**: 99% caché de navegador (`Ctrl+F5`) o `dist/`
  mezclado (rehacer el paso 3 limpio).
- **Delivery GitHub 403**: el `Require ip` bloquea; solo `/hooks/deploy`
  está abierto. Revisar `sites-available/extractcert-le-ssl.conf`.
- **Delivery timeout**: el receptor tarda ~15s en responder si el deploy
  corre; GitHub reintenta solo manual (Redeliver). El timer de 30 min
  cubre como respaldo.
- **`git checkout prod` se queja de dist/**: borrar `frontend/dist` local
  antes de cambiar de rama (en `main`/`dev` está ignorado).
- **Build vacío vía `.bin\vite`**: usar `node node_modules/vite/bin/vite.js build`.
- **Comillas/espacios vía plink**: consultas SQL en base64, rutas con `%20`,
  evitar `$(...)`, pipes con patrones sin comillas.
