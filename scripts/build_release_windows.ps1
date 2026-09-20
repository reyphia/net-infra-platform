# Build a Windows release of the Network Infrastructure Platform:
#   frontend (Vite build) + backend (PyInstaller .exe), bundled into a
#   single zip that runs with zero install steps.
#
# Usage (PowerShell):
#   .\scripts\build_release_windows.ps1                 # build only
#   .\scripts\build_release_windows.ps1 -Publish         # also create+upload
#                                                          a GitHub Release
#                                                          (requires the
#                                                          `gh` CLI, already
#                                                          logged in)
#
# NOTE FOR MAINTAINERS: this script is written and was validated by running
# its Linux counterpart's identical logic (build frontend -> venv -> test/
# lint/typecheck -> PyInstaller -> package) end-to-end against the same
# net-infra-platform.spec on a real Linux machine, and separately via
# .github/workflows/release.yml on a real `windows-latest` GitHub Actions
# runner. It was not hand-run on a physical Windows machine by whoever last
# edited this file -- if you hit an issue running it locally on Windows,
# please open an issue; the CI-verified path (a tagged push, see the
# workflow) is the one guaranteed to have actually executed on Windows.

param(
    [switch]$Publish
)

$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $PSScriptRoot
$Version = (Get-Content (Join-Path $RootDir "VERSION")).Trim()
$ReleaseName = "net-infra-platform-windows-x64-v$Version"
$ReleaseDir = Join-Path $RootDir "release"

Write-Host "==> Building Network Infrastructure Platform v$Version for Windows (x64)" -ForegroundColor Cyan

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "python was not found on PATH. Install Python 3.11+ from https://python.org and re-run."
}
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Error "npm (Node.js) was not found on PATH. Install Node.js 20+ from https://nodejs.org and re-run."
}

Write-Host "==> [1/5] Building frontend" -ForegroundColor Cyan
Push-Location (Join-Path $RootDir "frontend")
try {
    npm install
    if ($LASTEXITCODE -ne 0) { throw "npm install failed" }
    npm run typecheck
    if ($LASTEXITCODE -ne 0) { throw "frontend typecheck failed" }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "frontend build failed" }
} finally {
    Pop-Location
}

Write-Host "==> [2/5] Setting up backend build environment" -ForegroundColor Cyan
Push-Location (Join-Path $RootDir "backend")
try {
    if (-not (Test-Path "build-venv")) {
        python -m venv build-venv
    }
    $VenvPython = Join-Path "build-venv" "Scripts\python.exe"

    & $VenvPython -m pip install --quiet --upgrade pip
    & $VenvPython -m pip install --quiet -e ".[dev]"
    & $VenvPython -m pip install --quiet pyinstaller

    Write-Host "==> [3/5] Running backend test suite before packaging a release" -ForegroundColor Cyan
    if (-not $env:ENCRYPTION_KEY) {
        $env:ENCRYPTION_KEY = & $VenvPython -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    }
    if (-not $env:SECRET_KEY) { $env:SECRET_KEY = "release-build-check" }
    $env:ENVIRONMENT = "test"

    & $VenvPython -m ruff check app tests
    if ($LASTEXITCODE -ne 0) { throw "ruff check failed" }
    & $VenvPython -m mypy app
    if ($LASTEXITCODE -ne 0) { throw "mypy failed" }
    & $VenvPython -m pytest tests/ -q
    if ($LASTEXITCODE -ne 0) { throw "pytest failed" }

    Write-Host "==> [4/5] Building standalone .exe with PyInstaller" -ForegroundColor Cyan
    if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
    if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
    & $VenvPython -m PyInstaller net-infra-platform.spec --noconfirm
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed" }

    Write-Host "==> [5/5] Packaging release archive" -ForegroundColor Cyan
    New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null
    $StageDir = Join-Path $ReleaseDir $ReleaseName
    if (Test-Path $StageDir) { Remove-Item -Recurse -Force $StageDir }
    New-Item -ItemType Directory -Force -Path $StageDir | Out-Null

    Copy-Item -Recurse -Path "dist\net-infra-platform\*" -Destination $StageDir
    Copy-Item -Path (Join-Path $RootDir "LICENSE") -Destination $StageDir
    Copy-Item -Path (Join-Path $RootDir ".env.example") -Destination (Join-Path $StageDir ".env.example")

    $startHere = @"
Network Infrastructure Platform v$Version -- Windows (x64)

QUICK START
  1. Double-click net-infra-platform.exe
  2. Your browser opens automatically to http://127.0.0.1:8000
     (if it doesn't, open that URL yourself)
  3. Windows Defender / SmartScreen may warn about an unrecognized
     publisher on first run (this build isn't code-signed) -- click
     "More info" -> "Run anyway" if you trust the source you got it from.

On first run this creates a "data" folder next to the .exe with:
  - platform.db        SQLite database
  - keys.env            auto-generated SECRET_KEY / ENCRYPTION_KEY -- back
                         this up; deleting it makes existing encrypted
                         credential profiles unreadable
  - backups\            configuration backups
  - known_hosts          trusted SSH host keys

ENVIRONMENT VARIABLES (optional, set before launching)
  NET_INFRA_PORT=8000          change the listen port
  NET_INFRA_HOST=127.0.0.1     change the listen address
  NET_INFRA_OPEN_BROWSER=false disable auto-opening a browser tab
  NET_INFRA_DATA_DIR=C:\path   use a different data directory

Full documentation: https://github.com/<your-org>/net-infrastructure-platform
"@
    Set-Content -Path (Join-Path $StageDir "START-HERE.txt") -Value $startHere

    $zipPath = Join-Path $ReleaseDir "$ReleaseName.zip"
    if (Test-Path $zipPath) { Remove-Item $zipPath }
    Compress-Archive -Path "$StageDir\*" -DestinationPath $zipPath
    Remove-Item -Recurse -Force $StageDir

    Write-Host ""
    Write-Host "==> Done: $zipPath" -ForegroundColor Green
    Get-Item $zipPath | Select-Object Name, @{Name="SizeMB";Expression={[math]::Round($_.Length / 1MB, 1)}}

    if ($Publish) {
        if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
            Write-Error "gh CLI not found -- install https://cli.github.com/ to use -Publish"
        }
        Write-Host "==> Publishing to GitHub Releases (tag v$Version)" -ForegroundColor Cyan
        gh release create "v$Version" $zipPath --title "v$Version" --notes "See CHANGELOG.md" --generate-notes 2>$null
        if ($LASTEXITCODE -ne 0) {
            gh release upload "v$Version" $zipPath --clobber
        }
    }
} finally {
    Pop-Location
}
