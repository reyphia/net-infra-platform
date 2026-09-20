# Contributing

Thanks for considering a contribution. This is a portfolio-grade but
genuinely functional project, and contributions should keep it that way.

## Ground rules

1. **No fake functionality.** If a feature can't be implemented for real,
   mark it `NOT IMPLEMENTED` in code and docs rather than stubbing a
   fake-success path.
2. **Never commit secrets.** `.env`, real credentials, and captured device
   configs (which may contain hashed secrets) must never be committed.
3. **Discovery code never scans beyond an explicit, operator-given scope.**
   Do not add default/implicit scanning ranges.
4. **Tests must not require live production hardware.** Use the fixtures in
   `backend/tests/fixtures/` (including the real in-process fake-SSH-device
   server) or add new ones.

## Adding a vendor driver

1. Implement `app/drivers/base.NetworkDeviceDriver` for the vendor (see
   `docs/drivers.md`).
2. Register it in `app/drivers/factory.py`.
3. Add CLI-output fixtures under `backend/tests/fixtures/cli_output/` and a
   parsing test suite mirroring `tests/unit/test_cisco_driver_parsing.py`.
4. Add at least one test against the real fake-SSH-device harness
   (`tests/integration/test_ssh_transport_real.py` shows the pattern).

## Before opening a PR

```bash
cd backend && ruff check app tests && mypy app && pytest tests/ -q
cd frontend && npm run lint && npm run typecheck && npm run build
```

All four must pass. CI enforces this on every PR.

## Reporting security issues

See [SECURITY.md](SECURITY.md) -- please do not open a public issue for a
vulnerability.
