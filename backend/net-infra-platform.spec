# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the standalone, double-click-and-go build.

Built and verified in CI on both `ubuntu-latest` and `windows-latest` (see
.github/workflows/release.yml) and locally via
scripts/build_release_linux.sh / build_release_windows.ps1, both of which
just run `pyinstaller net-infra-platform.spec` after building the frontend.

`console=True` is deliberate: this is a network tool, and hiding its
console window would hide real startup errors (host-key failures, port
conflicts, etc.) behind nothing -- consistent with the project's
"never hide errors" principle. Flip it to False below if you'd rather have
a windowed app on Windows once you're comfortable relying on the log file
instead.
"""
import os

from PyInstaller.utils.hooks import collect_all

frontend_dist = os.path.join(SPECPATH, "..", "frontend", "dist")

datas = [(frontend_dist, "frontend_dist")]
binaries = []
hiddenimports = ['aiosqlite', 'app.api.routes.devices', 'app.api.routes.discovery', 'app.api.routes.topology', 'app.api.routes.credentials', 'app.api.routes.configuration', 'app.api.routes.changes', 'app.api.routes.audit', 'app.api.routes.monitoring', 'app.api.routes.terminal', 'uvicorn.logging', 'uvicorn.loops.auto', 'uvicorn.protocols.http.auto', 'uvicorn.protocols.websockets.auto', 'uvicorn.lifespan.on']
for pkg in ("pysnmp", "asyncssh", "cryptography", "aiosqlite"):
    tmp_ret = collect_all(pkg)
    datas += tmp_ret[0]
    binaries += tmp_ret[1]
    hiddenimports += tmp_ret[2]


a = Analysis(
    ['run.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='net-infra-platform',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='net-infra-platform',
)
