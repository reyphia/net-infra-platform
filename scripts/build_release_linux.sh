#!/usr/bin/env bash
# Build a Linux release of the Network Infrastructure Platform:
#   frontend (Vite build) + backend (PyInstaller onedir binary), bundled
#   into a single tarball that runs with zero install steps.
#
# Usage:
#   ./scripts/build_release_linux.sh                 # build only
#   ./scripts/build_release_linux.sh --publish        # also create+upload
#                                                       a GitHub Release
#                                                       (requires `gh` CLI,
#                                                       already logged in)
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(cat "$ROOT_DIR/VERSION")"
ARCH="$(uname -m)"
RELEASE_NAME="net-infra-platform-linux-${ARCH}-v${VERSION}"
RELEASE_DIR="$ROOT_DIR/release"
PUBLISH=false

for arg in "$@"; do
  case "$arg" in
    --publish) PUBLISH=true ;;
    *) echo "Unknown argument: $arg" >&2; exit 1 ;;
  esac
done

echo "==> Building Network Infrastructure Platform v${VERSION} for Linux (${ARCH})"

command -v python3 >/dev/null || { echo "python3 is required" >&2; exit 1; }
command -v npm >/dev/null || { echo "npm (Node.js) is required" >&2; exit 1; }

echo "==> [1/5] Building frontend"
cd "$ROOT_DIR/frontend"
npm install
npm run typecheck
npm run build

echo "==> [2/5] Setting up backend build environment"
cd "$ROOT_DIR/backend"
if [ ! -d "build-venv" ]; then
  python3 -m venv build-venv
fi
# shellcheck disable=SC1091
source build-venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -e ".[dev]"
pip install --quiet pyinstaller

echo "==> [3/5] Running backend test suite before packaging a release"
export ENCRYPTION_KEY="${ENCRYPTION_KEY:-$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')}"
export SECRET_KEY="${SECRET_KEY:-release-build-check}"
export ENVIRONMENT="test"
ruff check app tests
mypy app
pytest tests/ -q

echo "==> [4/5] Building standalone binary with PyInstaller"
rm -rf build dist
pyinstaller net-infra-platform.spec --noconfirm

echo "==> [5/5] Packaging release archive"
mkdir -p "$RELEASE_DIR"
STAGE_DIR="$RELEASE_DIR/$RELEASE_NAME"
rm -rf "$STAGE_DIR"
mkdir -p "$STAGE_DIR"
cp -r dist/net-infra-platform/. "$STAGE_DIR/"
cp "$ROOT_DIR/LICENSE" "$STAGE_DIR/"
cp "$ROOT_DIR/.env.example" "$STAGE_DIR/.env.example"

cat > "$STAGE_DIR/START-HERE.txt" << EOF
Network Infrastructure Platform v${VERSION} -- Linux (${ARCH})

QUICK START
  1. ./net-infra-platform
  2. Your browser opens automatically to http://127.0.0.1:8000
     (if it doesn't, open that URL yourself)

On first run this creates a "data" folder next to the executable with:
  - platform.db      SQLite database
  - keys.env          auto-generated SECRET_KEY / ENCRYPTION_KEY -- back
                       this up; deleting it makes existing encrypted
                       credential profiles unreadable
  - backups/          configuration backups
  - known_hosts        trusted SSH host keys

ENVIRONMENT VARIABLES (optional)
  NET_INFRA_PORT=8000          change the listen port
  NET_INFRA_HOST=127.0.0.1     change the listen address
  NET_INFRA_OPEN_BROWSER=false disable auto-opening a browser tab
  NET_INFRA_DATA_DIR=/path     use a different data directory

Full documentation: https://github.com/<your-org>/net-infrastructure-platform
EOF

chmod +x "$STAGE_DIR/net-infra-platform"

cd "$RELEASE_DIR"
tar -czf "${RELEASE_NAME}.tar.gz" "$RELEASE_NAME"
rm -rf "$STAGE_DIR"

echo ""
echo "==> Done: $RELEASE_DIR/${RELEASE_NAME}.tar.gz"
du -h "$RELEASE_DIR/${RELEASE_NAME}.tar.gz"

if [ "$PUBLISH" = true ]; then
  command -v gh >/dev/null || { echo "gh CLI not found -- install https://cli.github.com/ to use --publish" >&2; exit 1; }
  echo "==> Publishing to GitHub Releases (tag v${VERSION})"
  gh release create "v${VERSION}" "$RELEASE_DIR/${RELEASE_NAME}.tar.gz" \
    --title "v${VERSION}" \
    --notes "See CHANGELOG.md" \
    --generate-notes || \
  gh release upload "v${VERSION}" "$RELEASE_DIR/${RELEASE_NAME}.tar.gz" --clobber
fi
