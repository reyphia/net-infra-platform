# Security Policy

## Scope and intent

This platform is built for authorized network administration. It does not
implement, and will not accept contributions implementing, offensive
capabilities: credential brute-forcing, stealth/evasive scanning,
unauthorized access, or exploitation of discovered devices.

## Reporting a vulnerability

If you find a security issue (credential handling, SSH host-key handling,
injection in the config-diff/validation path, authorization gaps in the
API, etc.), please open a private security advisory on the repository
rather than a public issue, and include:

- A description of the issue and its impact
- Steps to reproduce
- The affected version/commit

## Handling of secrets in this codebase

- Credential profiles are encrypted at rest with Fernet
  (`app/credentials/crypto.py`); the encryption key is never hardcoded and
  must be supplied via `ENCRYPTION_KEY`.
- The API never returns password/community/private-key fields once stored
  (see `CredentialProfileOut` in `app/api/schemas.py` -- it structurally
  cannot include them).
- Audit log entries pass through `app/audit/service._redact`, which
  withholds any detail string that looks like it contains credential
  material.
- Configuration backups are stored with their original secrets intact
  (required for restoration), but are served to the UI through
  `app/configuration/sanitize.py`, which redacts passwords, enable secrets,
  SNMP community strings, and pre-shared keys before display.
- SSH host-key verification is on by default. Disabling it
  (`SSH_ALLOW_INSECURE_LAB_MODE=true`) is an explicit, documented opt-in
  intended only for isolated lab environments -- see `docs/security.md`.
