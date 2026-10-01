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
import re
import socket
import subprocess
import threading
from collections import OrderedDict
from http.server import BaseHTTPRequestHandler, HTTPServer

LISTEN = ("127.0.0.1", 9000)
SECRET_FILE = "/etc/extractcert-webhook.secret"
DEPLOY_COMMAND = ["sudo", "/bin/systemctl", "start", "extractcert-deploy.service"]
TARGET_REF = "refs/heads/prod"
MAX_BODY = 1024 * 1024
SOCKET_TIMEOUT = 10
MAX_DELIVERIES = 2048

_deliveries = OrderedDict()
_deliveries_lock = threading.Lock()
_deploy_lock = threading.Lock()


def _secret() -> bytes:
    with open(SECRET_FILE, "rb") as fh:
        return fh.read().strip()


class Handler(BaseHTTPRequestHandler):
    server_version = "ecx-hook/1"
    protocol_version = "HTTP/1.1"

    def setup(self):
        super().setup()
        self.connection.settimeout(SOCKET_TIMEOUT)

    def log_message(self, *args):
        print(*args, flush=True)

    def _send(self, code: int, body: str = ""):
        data = body.encode()
        self.send_response(code)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        if data:
            self.wfile.write(data)

    def _content_length(self):
        values = self.headers.get_all("Content-Length", [])
        if len(values) != 1 or re.fullmatch(r"[0-9]+", values[0]) is None:
            return None
        return int(values[0])

    def handle_expect_100(self):
        length = self._content_length()
        if length is None:
            self._send(400, "Content-Length inválido")
            return False
        if length > MAX_BODY:
            self._send(413, "cuerpo demasiado grande")
            return False
        self.send_response_only(100)
        self.end_headers()
        return True

    def do_GET(self):
        if self.path == "/healthz":
            self._send(200, "ok")
        else:
            self._send(404)

    def do_POST(self):
        if self.path != "/hooks/deploy":
            self._send(404)
            return
        length = self._content_length()
        if length is None:
            self._send(400, "Content-Length inválido")
            return
        if length > MAX_BODY:
            self._send(413, "cuerpo demasiado grande")
            return
        try:
            body = self.rfile.read(length)
        except (TimeoutError, socket.timeout):
            self.close_connection = True
            self._send(408, "timeout leyendo cuerpo")
            return
        if len(body) != length:
            self.close_connection = True
            self._send(400, "cuerpo incompleto")
            return
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

        delivery = self.headers.get("X-GitHub-Delivery", "")
        if not delivery or len(delivery) > 128:
            self._send(400, "X-GitHub-Delivery inválido")
            return
        with _deliveries_lock:
            if delivery in _deliveries:
                self._send(202, "entrega duplicada")
                return
            if not _deploy_lock.acquire(blocking=False):
                self._send(409, "despliegue en curso")
                return
            _deliveries[delivery] = None
            _deliveries.move_to_end(delivery)
            while len(_deliveries) > MAX_DELIVERIES:
                _deliveries.popitem(last=False)

        try:
            threading.Thread(target=_desplegar, daemon=True).start()
        except RuntimeError:
            with _deliveries_lock:
                _deliveries.pop(delivery, None)
                _deploy_lock.release()
            self._send(503, "no se pudo iniciar el despliegue")
            return
        self._send(202, "despliegue iniciado")

    def do_PUT(self):
        self._send(405)

    do_DELETE = do_PUT
    do_PATCH = do_PUT
    do_OPTIONS = do_PUT
    do_HEAD = do_PUT


def _desplegar():
    print("push a prod: ejecutando deploy", flush=True)
    try:
        r = subprocess.run(
            DEPLOY_COMMAND, capture_output=True, text=True, timeout=30
        )
        print(r.stdout[-2000:], flush=True)
        if r.returncode != 0:
            print("deploy FALLO: " + r.stderr[-2000:], flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"deploy error: {e}", flush=True)
    finally:
        _deploy_lock.release()


if __name__ == "__main__":
    if not os.path.exists(SECRET_FILE):
        raise SystemExit(f"falta {SECRET_FILE}")
    print(f"escuchando en {LISTEN[0]}:{LISTEN[1]}", flush=True)
    HTTPServer(LISTEN, Handler).serve_forever()
