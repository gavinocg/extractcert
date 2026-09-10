# ExtractCert

Sistema web para extraer rangos de páginas de certificados en PDF (LAN).
Backend **FastAPI (Python)** + frontend **React + Vite + Tailwind**, BD **MySQL**.

## Carpetas
- `backend/` — API FastAPI (`app/`), venv, `requirements.txt`, `storage/tmp` (previsualizaciones).
- `frontend/` — SPA React (Vite), `src/`, build → `dist/`.
- `tools/integration_test.py` — pruebas de integración del backend (levanta uvicorn y valida el flujo).

## Desarrollo local (Windows/Laragon)
Requisitos previos: MySQL en Laragon (ya existe la BD `db_extract_py`), Python 3, Node 20+.

```powershell
cd C:\laragon\www\extractcert
.\start.ps1        # recomendado (arranque + control)
# o, simple:
.\run-dev.ps1      # arranca ambos en ventanas normales
```
- API: http://127.0.0.1:8000  (docs en `/docs`)
- SPA: http://localhost:5173  (Vite proxifica `/api` → 8000)

Primer arranque crea el venv, instala dependencias y (vía `app/main.py`) crea las tablas
y siembra el usuario `admin` / `Admin123` y las settings por defecto.

### `start.ps1` (lanzador / controlador silencioso)
Levanta backend + frontend **sin ventanas adicionales** (procesos ocultos), espera a que
respondan los puertos, abre el navegador en la SPA y deja un menú de control:

```
1) Detener          -> apaga backend + frontend y cierra la ventana
2) Reiniciar        -> apaga y vuelve a levantar todo
3) Cerrar ventana   -> deja los servidores corriendo y cierra esta ventana
```

- Si los puertos 8000/5173 ya están activos, no los duplica: entra directo al menú.
- Guarda los PIDs de los procesos raíz en `%TEMP%\ExtractCert\*.pid` para poder detenerlos después
  (o `taskkill /PID <pid> /T /F`).
- "Detener"/"Reiniciar" matan también lo que escuche en 8000/5173 por defecto (compatible IPv4/IPv6
  — Vite escucha en `::1`), aunque el servidor se haya levantado fuera del script.

> Nota: la opción **1) Detener** apaga todo por diseño; si la usas y luego la app da
> "Failed to fetch", relanza con `.\start.ps1`.

### Sin script
```bash
# backend
backend\.venv\Scripts\uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
# frontend
cd frontend && npm run dev
```

## Variables de entorno (`backend/.env`)
- `DATABASE_URL=mysql+pymysql://root:@localhost:3306/db_extract_py`
- `SECRET_KEY` (cambiar en producción)
- `DEFAULT_RAIZ_ORIGEN`, `DEFAULT_RAIZ_REPO` (el admin puede cambiarlas por la web en /config)

## API principal
- `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me`
- `GET /api/tree?path=`, `GET /api/dashboard?path=&pagina=&tam=` (realizados paginados)
- `GET /api/pdf/{original|extraido|temp}?ruta=`
- `POST /api/extracciones/preview`, `POST /api/extracciones/guardar`
- `GET /api/historial?usuario=&pagina=&tam=` (paginado), `CRUD /api/usuarios`, `GET/PUT /api/settings`

Auth por cookie httpOnly (JWT) + doble envío CSRF (`X-CSRF-Token`).

## Visor de PDF (pdf.js v6 + WASM)
Los certificados escaneados usan imágenes **JBIG2**, que pdf.js v6 solo decodifica con WebAssembly.
- Los binarios se sirven desde `frontend/public/pdfjs-wasm/` (jbig2.wasm, openjpeg.wasm, …),
  copiados desde `node_modules/pdfjs-dist/wasm/`.
- El visor los carga con `getDocument({ data, wasmUrl: '/pdfjs-wasm/' })` en
  `frontend/src/components/PdfViewer.tsx`; el PDF se trae con `fetch(..., credentials:'include')`.
- Si al previsualizar el PDF sale en blanco con errores del tipo
  `Ensure that the wasmUrl API parameter is provided` / `JBig2 failed to initialize`:
  verifica que exista `frontend/public/pdfjs-wasm/jbig2.wasm` o vuelve a copiarlo
  (`Copy-Item node_modules/pdfjs-dist/wasm/* public/pdfjs-wasm/` desde `frontend/`).
- En producción el build ya incluye esos assets (`dist/pdfjs-wasm/`).

## Producción (Ubuntu 24.04 LAMP)
1. `cd frontend && npm install && npm run build` (genera `frontend/dist`).
2. FastAPI ya sirve `frontend/dist` (StaticFiles montado al final). Ejecutar con uvicorn/gunicorn bajo systemd.
3. nginx: proxy `/api` → `127.0.0.1:8000`; el resto lo sirve FastAPI (SPA).
4. `.env` con credenciales MySQL y rutas `/mnt/...` (origen/repo).
5. Bloquear acceso web a `storage/`.

## Probar backend
```bash
# unitarios (contención de rutas, etc.)
cd backend && .\.venv\Scripts\python -m pytest -q
# integración (levanta uvicorn y valida el flujo completo, requiere MySQL)
backend\.venv\Scripts\python tools/integration_test.py
```

## Probar frontend (Vitest + Testing Library)
```bash
cd frontend && npm test        # una pasada
cd frontend && npm run test:watch   # modo watch
```