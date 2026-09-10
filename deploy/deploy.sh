#!/usr/bin/env bash
# Despliegue de ExtractCert en servidor compartido. Idempotente y no toca
# otros servicios: solo crea /opt/extractcert, un usuario, un unit systemd
# y un site nginx nuevo (valida con nginx -t antes de recargar).
set -euo pipefail

APP_DIR=/opt/extractcert
APP_PORT=8000   # cambiar si está ocupado (ver MIGRATION_CHECKLIST.md)
APP_USER=extractcert
REPO_URL="https://github.com/gavinocg/extractcert.git"

echo "== 1. Código =="
if [ ! -d "$APP_DIR/.git" ]; then
  git clone "$REPO_URL" "$APP_DIR"
else
  git -C "$APP_DIR" pull --ff-only
fi

echo "== 2. Backend =="
python3 -m venv "$APP_DIR/backend/.venv"
"$APP_DIR/backend/.venv/bin/pip" install -r "$APP_DIR/backend/requirements.txt"
[ -f "$APP_DIR/backend/.env" ] || { echo "FALTA $APP_DIR/backend/.env (ver .env.example)"; exit 1; }
id "$APP_USER" >/dev/null 2>&1 || useradd -r -m -d "$APP_DIR" -s /usr/sbin/nologin "$APP_USER" || true
chown -R "$APP_USER:$APP_USER" "$APP_DIR/backend/storage" 2>/dev/null || true

echo "== 3. Frontend (build) =="
cd "$APP_DIR/frontend"
npm ci
npm run build

echo "== 4. systemd =="
sed "s/--port 8000/--port $APP_PORT/" /opt/extractcert/deploy/extractcert.service > /etc/systemd/system/extractcert.service
systemctl daemon-reload
systemctl enable --now extractcert
sleep 3
systemctl is-active extractcert
curl -sf "http://127.0.0.1:$APP_PORT/api/auth/me" -o /dev/null || curl -sf "http://127.0.0.1:$APP_PORT/docs" -o /dev/null
echo "API OK en puerto $APP_PORT"

echo "== 5. nginx (nuevo site, sin tocar los existentes) =="
cp /etc/nginx/sites-enabled/* /tmp/nginx-sites-backup/ 2>/dev/null || (mkdir -p /tmp/nginx-sites-backup && cp /etc/nginx/sites-enabled/* /tmp/nginx-sites-backup/)
sed -e "s/__DOMINIO__/$APP_DOMAIN/" -e "s/__PUERTO__/$APP_PORT/" /opt/extractcert/deploy/nginx-extractcert.conf > /etc/nginx/sites-available/extractcert
ln -sf /etc/nginx/sites-available/extractcert /etc/nginx/sites-enabled/extractcert
nginx -t && systemctl reload nginx

echo "== Despliegue completo =="
