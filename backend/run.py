"""Standalone launcher for the packaged app (PyInstaller .exe / Linux binary).

This is NOT used by `uvicorn app.main:app --reload` during normal
development -- that path is unaffected by anything here. This file exists
so `scripts/build_release_windows.ps1` / `build_release_linux.sh` can
produce a genuine double-click-and-go executable:

  - On first run, generates SECRET_KEY / ENCRYPTION_KEY and persists them
    next to the executable (data/keys.env), so the operator never has to
    run a separate key-generation step or hand-edit a .env file.
  - Puts the SQLite database, config backups, and SSH known_hosts store in
    a `data/` directory next to the executable (a "portable app" layout),
    unless NET_INFRA_DATA_DIR is set.
  - Starts uvicorn programmatically and opens the default browser once the
    server is actually accepting connections -- no terminal-only experience
    for someone who just double-clicked an .exe.

All of this only ever touches local files the operator's own account can
already write to; nothing here requests elevated privileges.
"""
from __future__ import annotations

import os
import sys
import threading
import time
import webbrowser
from pathlib import Path


def _app_base_dir() -> Path:
    """Directory the executable itself lives in (works for both PyInstaller
    onefile and onedir builds, and for `python run.py` during local
    testing of this launcher)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _ensure_local_env(data_dir: Path) -> None:
    """Load persisted keys if present, otherwise generate and save them.
    Sets process environment variables directly (simpler and more robust
    across platforms than relying on a .env file being discovered at the
    right relative path from a frozen executable)."""
    from cryptography.fernet import Fernet

    keys_file = data_dir / "keys.env"
    values: dict[str, str] = {}

    if keys_file.is_file():
        for line in keys_file.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                key, _, value = line.partition("=")
                values[key.strip()] = value.strip()

    changed = False
    if "SECRET_KEY" not in values:
        import secrets

        values["SECRET_KEY"] = secrets.token_hex(32)
        changed = True
    if "ENCRYPTION_KEY" not in values:
        values["ENCRYPTION_KEY"] = Fernet.generate_key().decode()
        changed = True

    if changed:
        data_dir.mkdir(parents=True, exist_ok=True)
        keys_file.write_text(
            "# Auto-generated on first run. Keep this file -- deleting it\n"
            "# makes existing encrypted credential profiles unreadable.\n"
            f"SECRET_KEY={values['SECRET_KEY']}\n"
            f"ENCRYPTION_KEY={values['ENCRYPTION_KEY']}\n",
            encoding="utf-8",
        )
        try:
            os.chmod(keys_file, 0o600)
        except OSError:
            pass  # best-effort on platforms without POSIX permission bits (e.g. Windows FAT)

    for key, value in values.items():
        os.environ.setdefault(key, value)


def _open_browser_when_ready(url: str, timeout_seconds: float = 20.0) -> None:
    import urllib.error
    import urllib.request

    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"{url}/health", timeout=1)  # noqa: S310 -- fixed localhost URL, not user input
            webbrowser.open(url)
            return
        except (urllib.error.URLError, ConnectionError, OSError):
            time.sleep(0.4)


def main() -> None:
    base_dir = _app_base_dir()
    data_dir = Path(os.environ.get("NET_INFRA_DATA_DIR", base_dir / "data"))
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "backups").mkdir(exist_ok=True)

    os.environ.setdefault("ENVIRONMENT", "production")
    os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///{(data_dir / 'platform.db').as_posix()}")
    os.environ.setdefault("SSH_KNOWN_HOSTS_PATH", str(data_dir / "known_hosts"))
    os.environ.setdefault("CONFIG_BACKUP_DIR", str(data_dir / "backups"))
    # FRONTEND_DIST_PATH is intentionally left unset here: app.core.fsutil.
    # resolve_frontend_dist_path() already knows how to find the bundled
    # frontend for both frozen (sys._MEIPASS / exe dir) and dev
    # (../frontend/dist) layouts. Setting it here would risk pointing at the
    # wrong directory depending on onefile vs. onedir packaging.
    _ensure_local_env(data_dir)

    host = os.environ.get("NET_INFRA_HOST", "127.0.0.1")
    port = int(os.environ.get("NET_INFRA_PORT", "8000"))
    open_browser = os.environ.get("NET_INFRA_OPEN_BROWSER", "true").lower() != "false"

    # Imported after env vars are set: app.core.config.get_settings() and
    # app.db.session build the engine/settings singletons at import time.
    import asyncio

    import uvicorn

    from app.db.session import init_models
    from app.main import app

    asyncio.run(init_models())

    if open_browser:
        threading.Thread(
            target=_open_browser_when_ready, args=(f"http://{host}:{port}",), daemon=True
        ).start()

    print(f"\n  Network Infrastructure Platform starting -- data dir: {data_dir}")
    print(f"  Open http://{host}:{port} in your browser (opening automatically)\n")

    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
