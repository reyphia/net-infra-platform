# Deployment

## Docker Compose (recommended for a single management host)

```bash
cp .env.example .env
# fill in SECRET_KEY and ENCRYPTION_KEY -- see comments in .env.example
docker compose up --build
```

The backend needs to reach real devices on your network (ARP table, ICMP,
SNMP, SSH) from wherever it runs. `docker-compose.yml` uses
`network_mode: host` for the backend service for this reason -- the
container shares the host's network namespace, so `ip neighbor show`,
`ping`, and outbound SNMP/SSH all behave exactly as they would running the
backend directly on the host. This is the simplest correct choice for a
tool whose entire purpose is real network I/O.

If host networking isn't appropriate for your environment (e.g. you're
running this on a jump host inside a container platform that disallows it),
run the backend as a normal bridged service and instead route the *traffic
that needs to reach the target network* through your platform's usual
mechanism (a macvlan network, a routed bridge, or simply running the backend
process directly on a host with the right routes/interfaces) -- discovery
and driver connections both just need outbound L3 reachability plus, for
ARP/local-segment discovery specifically, an interface that's actually on
that L2 segment.

## Standalone executable (PyInstaller)

`backend/run.py` + `backend/net-infra-platform.spec` package the backend
and the built frontend into one process via PyInstaller. This is what
`scripts/build_release_linux.sh` / `build_release_windows.ps1` produce.
Key behavior, all real and covered by `run.py`:

- First run auto-generates `SECRET_KEY` / `ENCRYPTION_KEY` and persists
  them to `data/keys.env` next to the executable -- no manual key-generation
  step required for a "download and double-click" experience.
- SQLite DB, config backups, and the SSH known_hosts store all live under
  `data/` next to the executable (override with `NET_INFRA_DATA_DIR`).
- The frontend is served from the same process (`app.core.fsutil.
  resolve_frontend_dist_path()` locates the bundled `frontend_dist/`
  directory), with SPA-fallback routing so client-side routes survive a
  hard refresh.
- A background thread polls `/health` and opens the default browser once
  the server is actually accepting connections (`NET_INFRA_OPEN_BROWSER=false`
  to disable).

To build one yourself without the release scripts:
```bash
cd frontend && npm install && npm run build && cd ..
cd backend && pip install -e ".[dev]" pyinstaller
pyinstaller net-infra-platform.spec --noconfirm
./dist/net-infra-platform/net-infra-platform   # or .exe on Windows
```

## Local development (no Docker)

```bash
# backend
cd backend
pip install -e ".[dev]"
cp ../.env.example .env   # fill in SECRET_KEY / ENCRYPTION_KEY
alembic upgrade head       # or rely on auto-create in ENVIRONMENT=development
uvicorn app.main:app --reload

# frontend
cd frontend
npm install
npm run dev   # proxies /api to http://localhost:8000, see vite.config.ts
```

## Database

SQLite works out of the box (`DATABASE_URL=sqlite+aiosqlite:///./data/platform.db`).
For a multi-operator deployment, point `DATABASE_URL` at PostgreSQL instead
(`postgresql+asyncpg://user:pass@host/db`) and run `alembic upgrade head` --
no application code changes are required; every query goes through
SQLAlchemy's async ORM.

## Backups directory

Configuration backups are written to `CONFIG_BACKUP_DIR` (default
`./data/backups`), one subdirectory per device, `chmod 600`. Back this
directory up as part of your normal operational backup process -- it is the
only copy of pre-change configuration used for rollback.
