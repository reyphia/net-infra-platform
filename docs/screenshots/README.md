# Screenshots

This directory is where real application screenshots belong once the
platform is running against a live (or lab) environment:

- `dashboard.png`
- `topology.png`
- `device-details.png`
- `terminal.png`
- `configuration-diff.png`
- `change-management.png`
- `audit-log.png`

## How to capture them

```bash
docker compose up --build
# run a discovery job against an authorized/lab network from Settings
# then, for each page:
```

Use your browser's built-in screenshot tool, or for consistent framing:

```bash
# macOS
cmd+shift+4

# Linux (GNOME)
gnome-screenshot -w
```

No screenshots are checked into this repository yet -- generating them
requires a live or lab network to discover, which is outside what can be
committed as static assets. Placeholder/fake screenshots are deliberately
not included; see the project's "no fake functionality" principle in the
root README.
