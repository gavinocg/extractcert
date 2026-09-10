"""Prueba de integración del backend ExtractCert (sube uvicorn en subproceso).
Uso: python tools/integration_test.py
"""
import os
import subprocess
import sys
import time
import urllib.parse

import httpx

BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
PY = os.path.join(BACKEND, ".venv", "Scripts", "python.exe")
ORIGEN = "C:/Users/TI/Desktop/EntregaDocs"
CARPETA = ORIGEN + "/2026/AGOSTO 2026/03-08-2026"
PDF = CARPETA + "/2337926.pdf"
BASE = "http://127.0.0.1:8077"


def main():
    proc = subprocess.Popen(
        [PY, "-m", "uvicorn", "app.main:app", "--app-dir", BACKEND,
         "--host", "127.0.0.1", "--port", "8077"],
        stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT,
    )
    try:
        # espera a que arranque
        for _ in range(40):
            try:
                httpx.get(BASE + "/api/auth/me")
                break
            except Exception:
                time.sleep(0.25)
        else:
            raise SystemExit("No arrancó el servidor")

        c = httpx.Client(base_url=BASE, timeout=20)

        # --- sin sesión debe dar 401
        r = c.get("/api/auth/me")
        assert r.status_code == 401, f"me sin sesión: {r.status_code} {r.text}"
        print("ok  me sin sesión -> 401")

        # --- login
        r = c.post("/api/auth/login", json={"username": "admin", "password": "Admin123"})
        assert r.status_code == 200, f"login: {r.status_code} {r.text}"
        u = r.json()["user"]
        assert u["rol"] == "administrador"
        print("ok  login admin")

        csrf = c.cookies.get("csrf_token")
        h = {"X-CSRF-Token": csrf}

        r = c.get("/api/auth/me")
        assert r.status_code == 200 and r.json()["username"] == "admin"
        print("ok  /me")

        # --- tree raíz
        r = c.get("/api/tree")
        assert r.status_code == 200
        data = r.json()
        assert "2026" in data["dirs"], data
        print("ok  tree raíz dirs=", data["dirs"])

        # --- tree carpeta + dashboard
        r = c.get("/api/tree", params={"path": CARPETA})
        assert r.status_code == 200 and PDF.split("/")[-1] in r.json()["pdfs"]
        print("ok  tree carpeta")

        # --- confinamiento: no se permite salir de la raíz de origen
        padre = ORIGEN.rsplit("/", 1)[0]
        r = c.get("/api/tree", params={"path": padre})
        assert r.status_code == 400, f"escape de raíz: {r.status_code} {r.text}"
        r = c.get("/api/pdf/original", params={"ruta": ORIGEN + "/../C:/Windows/notepad.exe"})
        assert r.status_code in (400, 403, 404), f"escape pdf: {r.status_code} {r.text}"
        print("ok  confinamiento de rutas")

        r = c.get("/api/dashboard", params={"path": CARPETA})
        assert r.status_code == 200
        d = r.json()
        print(f"ok  dashboard pendientes={len(d['pendientes'])} realizados={len(d['realizados'])}")

        # --- preview
        r = c.post("/api/extracciones/preview", json={"ruta": PDF, "inicio": 1, "fin": 2}, headers=h)
        assert r.status_code == 200, f"preview: {r.status_code} {r.text}"
        pv = r.json()
        assert pv["paginas"] == 2
        print("ok  preview", pv["url"])

        # --- servir temp
        url = BASE + pv["url"]
        r = c.get(url)
        assert r.status_code == 200, f"temp: {r.status_code} {r.text}"
        assert r.headers["content-type"] == "application/pdf"
        assert len(r.content) > 1000
        print("ok  pdf temp bytes=", len(r.content))

        # --- guardar (nueva)
        r = c.post("/api/extracciones/guardar",
                   json={"ruta": PDF, "inicio": 1, "fin": 2, "reextra": 0}, headers=h)
        assert r.status_code == 200, f"guardar: {r.status_code} {r.text}"
        g = r.json()
        print("ok  guardar ->", g["nombre"], g["estado"])

        # --- re-extracción
        r = c.post("/api/extracciones/guardar",
                   json={"ruta": PDF, "inicio": 1, "fin": 1,
                         "reextra": 1, "extraccion_id": g["extraccion_id"]}, headers=h)
        assert r.status_code == 200, f"reextra: {r.status_code} {r.text}"
        r2 = r.json()
        assert r2["estado"] == "rehecho" and r2["destino"] == g["destino"]
        print("ok  re-extracción -> rehecho, destino igual")

        # --- servir extraído
        r = c.get("/api/pdf/extraido", params={"ruta": r2["destino"]})
        assert r.status_code == 200
        print("ok  pdf extraido bytes=", len(r.content))

        # --- historial
        r = c.get("/api/historial")
        assert r.status_code == 200
        hist = r.json()["registros"]
        assert any(x["id"] == g["extraccion_id"] for x in hist)
        print("ok  historial registros=", len(hist))

        # --- historial paginado
        r = c.get("/api/historial", params={"pagina": 1, "tam": 1})
        assert r.status_code == 200
        p = r.json()
        assert p["tam"] == 1 and len(p["registros"]) <= 1
        assert p["total"] >= len(hist) and p["pagina"] == 1
        r = c.get("/api/historial", params={"pagina": 99999, "tam": 20})
        assert r.status_code == 200 and r.json()["registros"] == []
        print("ok  historial paginado")

        # --- dashboard paginado (realizados)
        r = c.get("/api/dashboard", params={"path": CARPETA, "pagina": 1, "tam": 1})
        assert r.status_code == 200
        d = r.json()
        assert "total_realizados" in d and d["tam"] == 1
        assert len(d["realizados"]) <= 1
        print("ok  dashboard paginado total_realizados=", d["total_realizados"])

        # --- settings GET/PUT
        r = c.get("/api/settings")
        s = r.json()
        assert s["raiz_origen"] == ORIGEN.replace("\\", "/")
        r = c.put("/api/settings", json={"raiz_origen": s["raiz_origen"], "raiz_repo": s["raiz_repo"]}, headers=h)
        assert r.status_code == 200
        print("ok  settings")

        # --- usuarios (admin): listar, crear, editar, eliminar
        r = c.get("/api/usuarios")
        assert r.status_code == 200
        print("ok  usuarios listar")

        r = c.post("/api/usuarios", json={"username": "tmp_test", "rol": "usuario", "password": "123456"}, headers=h)
        assert r.status_code == 200, f"crear: {r.status_code} {r.text}"
        uid = r.json()["id"]
        r = c.put(f"/api/usuarios/{uid}", json={"username": "tmp_test2", "rol": "usuario"}, headers=h)
        assert r.status_code == 200
        r = c.delete(f"/api/usuarios/{uid}", headers=h)
        assert r.status_code == 200
        print("ok  usuarios crear/editar/eliminar")

        # --- CSRF: mutación sin token debe fallar 403
        r = c.post("/api/extracciones/preview", json={"ruta": PDF, "inicio": 1, "fin": 2})
        assert r.status_code == 403, f"csrf: {r.status_code}"
        print("ok  csrf -> 403")

        print("\n=== TODAS LAS PRUEBAS OK ===")
        # limpiar artefacto de prueba
        destino = r2["destino"]
        if os.path.exists(destino):
            os.remove(destino)
        c.post("/api/historial")  # no-op
        with httpx.Client(base_url=BASE, timeout=10) as c2:
            pass
        from sqlalchemy import text
        sys.path.insert(0, BACKEND)
        from app.db.database import SessionLocal
        from app.db.models import Extraccion
        db = SessionLocal()
        db.query(Extraccion).filter(Extraccion.original_path == PDF).delete()
        db.commit()
        db.close()
        print("ok  limpieza de datos de prueba")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    main()