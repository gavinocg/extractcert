# ExtractCert - lanzador / controlador (silencioso)
# Levanta backend (uvicorn) + frontend (Vite) en segundo plano y ofrece menú:
#   1) Detener     -> apaga todo y cierra la ventana
#   2) Reiniciar   -> apaga y vuelve a levantar
#   3) Cerrar ventana -> deja los servidores corriendo y cierra esta ventana
# Para detener más tarde: elimina los .pid o matastask los PIDs indicados.

$ErrorActionPreference = "Stop"

$root    = Split-Path -Parent $MyInvocation.MyCommand.Path
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"
$py      = Join-Path $backend ".venv\Scripts\python.exe"
$portB   = 8000
$portF   = 5173

$stateDir = Join-Path $env:TEMP "ExtractCert"
New-Item -ItemType Directory -Path $stateDir -Force | Out-Null
$pidB = Join-Path $stateDir "backend.pid"
$pidF = Join-Path $stateDir "frontend.pid"

function Test-Port([int]$port) {
    foreach ($addr in @('127.0.0.1', '::1')) {
        try {
            $c = New-Object Net.Sockets.TcpClient
            $c.Connect($addr, $port)
            $c.Close()
            return $true
        } catch { }
    }
    return $false
}

function Read-Pid([string]$file) {
    if (Test-Path $file) {
        $v = (Get-Content $file -Raw).Trim()
        if ($v -match '^\d+$') { return [int]$v }
    }
    return 0
}

function Get-Running([int]$id) {
    if ($id -le 0) { return $false }
    try {
        $null = Get-Process -Id $id -ErrorAction Stop
        return $true
    } catch {
        return $false
    }
}

function Wait-Port([int]$port, [string]$nombre, [int]$timeout) {
    $sw = [Diagnostics.Stopwatch]::StartNew()
    while (-not (Test-Port $port)) {
        if ($sw.Elapsed.TotalSeconds -gt $timeout) {
            Write-Host "  $nombre NO respondio en $timeout s" -ForegroundColor Yellow
            return $false
        }
        Start-Sleep -Milliseconds 800
    }
    return $true
}

function Wait-PortClosed([int]$port, [int]$timeout) {
    $sw = [Diagnostics.Stopwatch]::StartNew()
    while (Test-Port $port) {
        if ($sw.Elapsed.TotalSeconds -gt $timeout) { return }
        Start-Sleep -Milliseconds 500
    }
}

function Start-Backend {
    Write-Host "Arrancando backend (FastAPI) en http://127.0.0.1:$portB ..." -ForegroundColor Green
    $p = Start-Process -FilePath $py `
        -ArgumentList "-m", "uvicorn", "app.main:app", "--app-dir", $backend, "--host", "127.0.0.1", "--port", "$portB", "--reload" `
        -WorkingDirectory $backend -WindowStyle Hidden -PassThru
    Set-Content -Path $pidB -Value $p.Id
}

function Start-Frontend {
    Write-Host "Arrancando frontend (Vite) en http://localhost:$portF ..." -ForegroundColor Green
    $p = Start-Process -FilePath "cmd.exe" `
        -ArgumentList "/c", "npm run dev" `
        -WorkingDirectory $frontend -WindowStyle Hidden -PassThru
    Set-Content -Path $pidF -Value $p.Id
}

function Stop-PortProcess([int]$port) {
    try {
        $conns = Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue
        foreach ($c in $conns) {
            if ($c.OwningProcess -gt 0) {
                try { & taskkill /PID $c.OwningProcess /T /F 2>$null | Out-Null } catch { }
            }
        }
    } catch { }
}

function Stop-All {
    foreach ($f in @($pidB, $pidF)) {
        $id = Read-Pid $f
        if ($id -gt 0) {
            try { & taskkill /PID $id /T /F 2>$null | Out-Null } catch { }
        }
        Remove-Item $f -Force -ErrorAction SilentlyContinue
    }
    Stop-PortProcess $portB
    Stop-PortProcess $portF
    Wait-PortClosed $portB 8
    Wait-PortClosed $portF 8
}

function Start-All {
    Start-Backend
    Start-Frontend
    $okB = Wait-Port $portB "Backend" 40
    $okF = Wait-Port $portF "Frontend" 60
    if ($okB) { Write-Host "  Backend listo  http://127.0.0.1:$portB`n" -ForegroundColor Green }
    if ($okF) { Write-Host "  Frontend listo  http://localhost:$portF`n" -ForegroundColor Green }
    if ($okF) { Start-Process "http://localhost:$portF" }
}

# ---------------------------------------------------------------- preparar venv
if (-not (Test-Path $py)) {
    Write-Host "No existe el venv. Creandolo..." -ForegroundColor Yellow
    & python -m venv (Join-Path $backend ".venv")
    & (Join-Path $backend ".venv\Scripts\python.exe") -m pip install -r (Join-Path $backend "requirements.txt")
}

$pyEx = $py
$runningB = (Get-Running (Read-Pid $pidB)) -or (Test-Port $portB)
$runningF = (Get-Running (Read-Pid $pidF)) -or (Test-Port $portF)

# ---------------------------------------------------------------- estado inicial
Write-Host "ExtractCert - control" -ForegroundColor Cyan
if ($runningB -and $runningF) {
    Write-Host "Ya hay backend y frontend corriendo; solo control." -ForegroundColor Yellow
} else {
    if ($runningB) { Write-Host "Backend ya estaba corriendo. Omito." -ForegroundColor Yellow } else { Start-Backend }
    if ($runningF) { Write-Host "Frontend ya estaba corriendo. Omito." -ForegroundColor Yellow } else { Start-Frontend }
    $null = Wait-Port $portB "Backend" 15
    $null = Wait-Port $portF "Frontend" 60
    if ((Test-Port $portF) -or (Get-Running (Read-Pid $pidF))) { Start-Process "http://localhost:$portF" }
}

# ---------------------------------------------------------------- menú
while ($true) {
    $pidBack = Read-Pid $pidB
    $pidFrom = Read-Pid $pidF
    $bRun = (Test-Port $portB)
    $fRun = (Test-Port $portF)
    Write-Host ""
    Write-Host ("  Backend  : " + $(if ($bRun) { "activo (PID $pidBack)" } else { "detenido" })) -ForegroundColor $(if ($bRun) { "Green" } else { "Red" })
    Write-Host ("  Frontend : " + $(if ($fRun) { "activo (PID $pidFrom)" } else { "detenido" })) -ForegroundColor $(if ($fRun) { "Green" } else { "Red" })
    Write-Host ""
    Write-Host "  Opciones:" -ForegroundColor Cyan
    Write-Host "   1) Detener (apaga backend + frontend y cierra)"
    Write-Host "   2) Reiniciar"
    Write-Host "   3) Cerrar ventana (deja los servidores corriendo)"
    $op = Read-Host "  Elige [1-3]"

    switch ($op.Trim()) {
        "1" { Stop-All; Write-Host "Todo detenido. Cerrando ventana." -ForegroundColor Green; break }
        "2" {
            Stop-All
            Start-All
            Write-Host "Reiniciado." -ForegroundColor Green
            continue
        }
        "3" {
            Write-Host "Servidores en segundo plano."
            Write-Host "PIDs -> backend: $(Read-Pid $pidB) / frontend: $(Read-Pid $pidF) (taskkill /PID <pid> /T /F)" -ForegroundColor DarkGray
            break
        }
        default {
            Write-Host "Opcion no valida." -ForegroundColor Yellow
            continue
        }
    }
    break
}