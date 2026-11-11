#!/usr/bin/env bash
# See README.md. Needs git, cargo (rustup), and Python 3.11 or later.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python="${PYTHON:-python3}"
if ! "$python" -c 'import sys; sys.exit(sys.version_info < (3, 11))' 2>/dev/null; then
  echo "error: the harness needs Python 3.11 or later; set PYTHON to one" >&2
  exit 2
fi
exec "$python" "$here/harness.py" e2e "$@"
