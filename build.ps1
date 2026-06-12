# Build a standalone Overwatch.exe with PyInstaller. Run on Windows.
#   powershell -ExecutionPolicy Bypass -File build.ps1
# Output: dist\Overwatch.exe (single file, tray app)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Need($code, $msg) { if ($LASTEXITCODE -ne 0) { Write-Error $msg; exit $code } }

# 1. Build venv
# Prefer Python 3.12 over newer versions. uvicorn[standard]'s native deps
# (httptools, websockets) often lack pre-built wheels for the very latest
# Python; targeting 3.12 avoids a source-build that needs MSVC C++ Build Tools.
$venv = Join-Path $PSScriptRoot "build-venv"
$venvPy = Join-Path $venv "Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    Write-Host "Creating build venv..."
    $created = $false
    foreach ($pyTag in @('-3.12','-3.11','-3.13','-3')) {
        py $pyTag -m venv $venv 2>$null
        if ($LASTEXITCODE -eq 0 -and (Test-Path $venvPy)) {
            Write-Host "  using py $pyTag"
            $created = $true
            break
        }
    }
    if (-not $created) { python -m venv $venv }
    Need 1 "Failed to create venv"
}
& $venvPy --version

# 2. Install deps + PyInstaller
Write-Host "Installing dependencies..."
& $venvPy -m pip install --upgrade pip | Out-Null
& $venvPy -m pip install -r requirements.txt
Need 1 "Failed to install requirements"
& $venvPy -m pip install pyinstaller
Need 1 "Failed to install pyinstaller"

# 3. Build
Write-Host "Building Overwatch.exe..."
& $venvPy -m PyInstaller --noconfirm --clean Overwatch.spec
Need 1 "PyInstaller build failed"

$out = Join-Path $PSScriptRoot "dist\Overwatch.exe"
if (Test-Path $out) {
    Write-Host "`n[OK] Built $out"
} else {
    Write-Error "Build reported success but $out is missing"
    exit 1
}
