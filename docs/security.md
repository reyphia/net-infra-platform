# Security

## Credential handling

- Stored via `CredentialProfile` (`app/db/models.py`) with secret fields
  (`encrypted_password`, `encrypted_enable_password`, `encrypted_ssh_private_key`,
  `encrypted_snmp_community`, SNMPv3 auth/priv keys) as Fernet-encrypted
  bytes, never plaintext.
- `ENCRYPTION_KEY` is required from the environment (`app/credentials/crypto.py`
  raises `EncryptionNotConfigured` rather than falling back to plaintext or a
  default key).
- The API's `CredentialProfileOut` schema structurally excludes every secret
  field -- there is no code path that returns a stored secret from a GET/LIST
  credentials call.
- Devices reference a credential profile by ID (`default_credential_profile_id`);
  drivers/change-plan/terminal code paths resolve secrets only transiently in
  memory for the duration of a connection.

## SSH

- Host-key verification is **on by default** (`app/drivers/base.py`,
  `app/api/routes/terminal.py`). Disabling it requires
  `SSH_ALLOW_INSECURE_LAB_MODE=true`, which is logged as a warning on every
  connection it affects and surfaced to the operator in the terminal itself.
- Connect and command timeouts are configurable
  (`SSH_CONNECT_TIMEOUT_SECONDS`, `SSH_COMMAND_TIMEOUT_SECONDS`), never
  unbounded.

## Audit

- Every sensitive action (discovery, config retrieve/backup, change apply/
  rollback, terminal connect/disconnect) goes through `AuditService.record()`,
  which redacts any `detail`/`error` string that looks like it contains
  credential material (`app/audit/service.py::_redact`) before it's written
  to the database.

## Discovery scope and rate limiting

- `DiscoveryScope` (`app/discovery/scope.py`) requires an explicit CIDR list
  and rejects anything over 65,536 addresses per job.
- All network probing is bounded by an `asyncio.Semaphore` with an
  operator-configurable `max_concurrency` -- there is no unbounded-fan-out
  code path.
- TCP probing is restricted to a fixed, small set of management ports; this
  is not, and must never become, a general port scanner.

## Change safety

- `app/configuration/validation.py` blocks a denylist of destructive
  commands (`reload`, `erase`, `write erase`, `/system reset-configuration`,
  etc.) at the plan-validation stage, before any device is touched.
- Every apply is preceded by a real pre-change backup
  (`ChangePlanService._backup_device`), and `apply_plan()` requires the
  caller to supply `confirmed_by` -- there is no endpoint that applies a
  change as a side effect of validate or preview.

## What this project will not do

No credential brute-forcing, no stealth/evasive scanning, no exploitation of
discovered devices, no unauthorized-access tooling. See `CONTRIBUTING.md`.
