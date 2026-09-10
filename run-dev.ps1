# ExtractCert - entorno de desarrollo local (Laragon/Windows)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"
$py = Join-Path $backend ".venv\Scripts\python.exe"

if (-not (Test-Path $py)) {
    Write-Host "No existe el venv. Creando..." -ForegroundColor Yellow
    & python -m venv (Join-Path $backend ".venv")
    & (Join-Path $backend ".venv\Scripts\python.exe") -m pip install -r (Join-Path $backend "requirements.txt")
}

Write-Host "Arrancando backend (FastAPI) en http://127.0.0.1:8000 ..." -ForegroundColor Green
Start-Process -FilePath $py -ArgumentList "-m","uvicorn","app.main:app","--app-dir",$backend,"--host","127.0.0.1","--port","8000","--reload" -WorkingDirectory $backend -WindowStyle Normal

Write-Host "Arrancando frontend (Vite) en http://localhost:5173 ..." -ForegroundColor Green
Start-Process -FilePath "npm" -ArgumentList "run","dev" -WorkingDirectory $frontend -WindowStyle Normal

Start-Sleep -Seconds 3
Start-Process "http://localhost:5173"
Write-Host "Listo. Cierra las ventanas para detener."