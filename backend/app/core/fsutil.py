"""Small filesystem helpers shared across the app."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def ensure_known_hosts_file(path: str) -> None:
    """asyncssh raises a raw FileNotFoundError (not its usual
    HostKeyNotVerifiable) if the configured known_hosts file doesn't exist
    yet -- e.g. on a brand-new install before the operator has trusted any
    host. Create an empty file so first connections get the intended,
    catchable "host key not verifiable" behavior instead of a crash.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        p.touch(mode=0o600)


def resolve_frontend_dist_path() -> Path | None:
    """Find the built frontend (`dist/`) so the backend can serve the whole
    application as a single process -- this is what makes the packaged
    executable (see scripts/build_release_*) a true single-file app rather
    than requiring a separate frontend server.

    Checked in order, first match wins:
      1. FRONTEND_DIST_PATH env var, if set -- explicit override.
      2. Next to a PyInstaller-frozen executable (`sys._MEIPASS`, the
         onefile extraction dir, or the directory containing the .exe for
         onedir builds) -- see scripts/build_release_windows.ps1 and
         backend/net-infra-platform.spec, which both copy frontend/dist
         alongside the bundled app under `frontend_dist/`.
      3. `../frontend/dist` relative to this source file -- lets a local
         `npm run build` be picked up automatically without any packaging
         step, useful when testing this feature during development.

    Returns None (never fabricates a path) if nothing is found; callers
    must treat that as "serve API only", not an error.
    """
    env_override = os.environ.get("FRONTEND_DIST_PATH")
    if env_override:
        candidate = Path(env_override)
        if (candidate / "index.html").is_file():
            return candidate

    if getattr(sys, "frozen", False):
        # PyInstaller sets sys._MEIPASS for onefile builds (temp extraction
        # dir); for onedir builds, bundled data sits next to the executable.
        meipass = getattr(sys, "_MEIPASS", None)
        for base in filter(None, [meipass, Path(sys.executable).parent]):
            candidate = Path(base) / "frontend_dist"
            if (candidate / "index.html").is_file():
                return candidate

    dev_candidate = Path(__file__).resolve().parent.parent.parent.parent / "frontend" / "dist"
    if (dev_candidate / "index.html").is_file():
        return dev_candidate

    return None

