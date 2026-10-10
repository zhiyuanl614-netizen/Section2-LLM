#!/usr/bin/env sh
set -eu
HERE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PLATFORM_ROOT="$HERE/platform"
RELEASE_ID="B001-v1.2-text-scope-preview-20261010"
export PLATFORM_RELEASE_DIR="${PLATFORM_RELEASE_DIR:-$PLATFORM_ROOT/data/releases/$RELEASE_ID}"
export PLATFORM_HOST="${PLATFORM_HOST:-127.0.0.1}"
export PLATFORM_PORT="${PLATFORM_PORT:-8765}"
exec python3 "$HERE/launcher.py" "$@"
