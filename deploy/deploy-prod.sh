#!/usr/bin/env bash
# Despliega la rama prod: fast-forward, deps si cambiaron, restart,
# healthcheck y rollback al commit previo ante fallo.
# Lo invoca el webhook y el timer de respaldo. El servidor nunca commitea.
set -euo pipefail

APP_DIR=/opt/extractcert
BRANCH=prod
URL=http://127.0.0.1:8000/healthz
VENV="$APP_DIR/backend/.venv/bin"
LOCK_FILE=/run/lock/extractcert-deploy.lock
export GIT_CONFIG_COUNT=1
export GIT_CONFIG_KEY_0=safe.directory
export GIT_CONFIG_VALUE_0="$APP_DIR"

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  logger -t extractcert-deploy "otro despliegue está en curso"
  exit 0
fi

cd "$APP_DIR"
git fetch -q origin "$BRANCH"
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse FETCH_HEAD)
[ "$LOCAL" = "$REMOTE" ] && { echo "sin cambios"; exit 0; }

PREV="$LOCAL"
PREV_DB_REV=$(sudo -u extractcert bash -c "cd '$APP_DIR/backend' && '$VENV/alembic' current" 2>/dev/null | tail -n 1 | awk '{print $1}')
MIGRATED=0

normalize_permissions() {
  chgrp -R extractcert "$APP_DIR/backend" "$APP_DIR/frontend/dist" "$APP_DIR/deploy" 2>/dev/null || true
  chmod -R g+rX "$APP_DIR/backend" "$APP_DIR/frontend/dist" "$APP_DIR/deploy" 2>/dev/null || true
}

rollback_database() {
  [ "$MIGRATED" = "1" ] && [ -n "$PREV_DB_REV" ] || return 0
  # En MySQL el DDL puede quedar aplicado sin que Alembic alcance a sellar la
  # revisión. Completar el upgrade idempotente permite luego un downgrade real.
  sudo -u extractcert bash -c "cd '$APP_DIR/backend' && '$VENV/alembic' upgrade head" || return 1
  sudo -u extractcert bash -c "cd '$APP_DIR/backend' && '$VENV/alembic' downgrade '$PREV_DB_REV'"
}

rollback_deploy() {
  trap - ERR
  logger -t extractcert-deploy "fallo previo al healthcheck; restaurando $PREV"
  rollback_database || { logger -t extractcert-deploy "rollback DB incompleto; se conserva código nuevo para recuperación manual"; exit 1; }
  git reset -q --hard "$PREV"
  normalize_permissions
  sudo -u extractcert "$VENV/pip" install -q -r "$APP_DIR/backend/requirements.txt" || true
  systemctl restart extractcert || true
  exit 1
}
trap rollback_deploy ERR

logger -t extractcert-deploy "desplegando $PREV -> $REMOTE"
git reset -q --hard "$REMOTE"
normalize_permissions
chown -R extractcert:extractcert "$APP_DIR/backend/storage" 2>/dev/null || true

if git diff --name-only "$PREV" "$REMOTE" | grep -q backend/requirements.txt; then
  logger -t extractcert-deploy "requirements cambió, reinstalando deps"
  sudo -u extractcert "$VENV/pip" install -q -r "$APP_DIR/backend/requirements.txt"
fi

if git diff --name-only "$PREV" "$REMOTE" | grep -q '^backend/migrations/'; then
  logger -t extractcert-deploy "aplicando migraciones de base de datos"
  # Alembic/MySQL puede confirmar DDL por revisión. Desde este punto cualquier
  # fallo requiere volver explícitamente a la revisión previa conocida.
  MIGRATED=1
  sudo -u extractcert bash -c "cd '$APP_DIR/backend' && '$VENV/alembic' upgrade head"
fi

systemctl restart extractcert
OK=0
for i in $(seq 1 12); do
  sleep 10
  if curl -sf -m 10 "$URL" -o /dev/null; then
    OK=1
    break
  fi
done
if [ "$OK" = "1" ]; then
  trap - ERR
  logger -t extractcert-deploy "deploy OK $REMOTE"
else
  trap - ERR
  logger -t extractcert-deploy "deploy FALLO, rollback a $PREV"
  rollback_database || { logger -t extractcert-deploy "rollback DB incompleto; se conserva código nuevo para recuperación manual"; exit 1; }
  git reset -q --hard "$PREV"
  normalize_permissions
  sudo -u extractcert "$VENV/pip" install -q -r "$APP_DIR/backend/requirements.txt" || true
  systemctl restart extractcert
  exit 1
fi
