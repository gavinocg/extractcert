#!/usr/bin/env python3
"""Receptor mínimo de webhooks de GitHub (solo stdlib).

Escucha en 127.0.0.1:9000 (Apache proxifica /hooks/deploy con acceso público).
Verifica HMAC X-Hub-Signature-256 y, si el push es a refs/heads/prod,
ejecuta deploy/deploy-prod.sh en segundo plano. Responde 202 de inmediato
para no superar el timeout de GitHub.
"""
import hashlib
import hmac
import json
import os
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

LISTEN = ("127.0.0.1", 9000)
SECRET_FILE = "/etc/extractcert-webhook.secret"
DEPLOY_SCRIPT = "/opt/extractcert/deploy/deploy-prod.sh"
TARGET_REF = "refs/heads/prod"


def _secret() -> bytes:
    with open(SECRET_FILE, "rb") as fh:
        return fh.read().strip()


class Handler(BaseHTTPRequestHandler):
    server_version = "ecx-hook/1"

    def log_message(self, *args):
        print(*args, flush=True)

    def _send(self, code: int, body: str = ""):
        data = body.encode()
        self.send_response(code)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self._send(200, "ok")

    def do_POST(self):
        if self.path != "/hooks/deploy":
            self._send(404)
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            length = 0
        body = self.rfile.read(length) if length > 0 else b""
        firma = self.headers.get("X-Hub-Signature-256", "")
        esperada = "sha256=" + hmac.new(_secret(), body, hashlib.sha256).hexdigest()
        if not firma or not hmac.compare_digest(firma, esperada):
            print("firma inválida", flush=True)
            self._send(403)
            return
        if self.headers.get("X-GitHub-Event") != "push":
            self._send(202, "ignorado")
            return
        try:
            ref = json.loads(body.decode("utf-8") or "{}").get("ref", "")
        except (ValueError, UnicodeDecodeError):
            ref = ""
        if ref != TARGET_REF:
            self._send(202, "otra rama")
            return
        threading.Thread(target=_desplegar, daemon=True).start()
        self._send(202, "despliegue iniciado")


def _desplegar():
    print("push a prod: ejecutando deploy", flush=True)
    try:
        r = subprocess.run(
            ["bash", DEPLOY_SCRIPT], capture_output=True, text=True, timeout=600
        )
        print(r.stdout[-2000:], flush=True)
        if r.returncode != 0:
            print("deploy FALLO: " + r.stderr[-2000:], flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"deploy error: {e}", flush=True)


if __name__ == "__main__":
    if not os.path.exists(SECRET_FILE):
        raise SystemExit(f"falta {SECRET_FILE}")
    print(f"escuchando en {LISTEN[0]}:{LISTEN[1]}", flush=True)
    HTTPServer(LISTEN, Handler).serve_forever()
