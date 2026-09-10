#!/usr/bin/env bash
# Despliega la rama prod: fast-forward, deps si cambiaron, restart,
# healthcheck y rollback al commit previo ante fallo.
# Lo invoca el webhook y el timer de respaldo. El servidor nunca commitea.
set -euo pipefail

APP_DIR=/opt/extractcert
BRANCH=prod
URL=http://127.0.0.1:8000/
VENV="$APP_DIR/backend/.venv/bin"

cd "$APP_DIR"
git fetch -q origin "$BRANCH"
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse FETCH_HEAD)
[ "$LOCAL" = "$REMOTE" ] && { echo "sin cambios"; exit 0; }

PREV="$LOCAL"
logger -t extractcert-deploy "desplegando $PREV -> $REMOTE"
git reset -q --hard "$REMOTE"
chown -R extractcert:extractcert "$APP_DIR/backend/storage" 2>/dev/null || true

if git diff --name-only "$PREV" "$REMOTE" | grep -q backend/requirements.txt; then
  logger -t extractcert-deploy "requirements cambió, reinstalando deps"
  sudo -u extractcert "$VENV/pip" install -q -r "$APP_DIR/backend/requirements.txt"
fi

systemctl restart extractcert
sleep 12
if curl -sf -m 15 "$URL" -o /dev/null && curl -sf -m 15 "${URL}docs" -o /dev/null; then
  logger -t extractcert-deploy "deploy OK $REMOTE"
else
  logger -t extractcert-deploy "deploy FALLO, rollback a $PREV"
  git reset -q --hard "$PREV"
  systemctl restart extractcert
  exit 1
fi
