# Build a standalone Overwatch.exe with PyInstaller. Run on Windows.
#   powershell -ExecutionPolicy Bypass -File build.ps1
# Output: dist\Overwatch.exe (single file, tray app)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Need($code, $msg) { if ($LASTEXITCODE -ne 0) { Write-Error $msg; exit $code } }

# 1. Build venv
$venv = Join-Path $PSScriptRoot "build-venv"
$venvPy = Join-Path $venv "Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    Write-Host "Creating build venv..."
    py -3 -m venv $venv 2>$null
    if ($LASTEXITCODE -ne 0) { python -m venv $venv }
    Need 1 "Failed to create venv"
}

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
