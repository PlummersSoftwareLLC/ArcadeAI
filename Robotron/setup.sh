#!/usr/bin/env bash
# Install dependencies only. Never install, enable, or start a service here.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
PYTHON_BIN="${ROBOTRON_SETUP_PYTHON:-python3}"
"$PYTHON_BIN" -c 'import sys; assert sys.version_info >= (3, 11), "Python 3.11+ required"'
if [[ ! -x .venv/bin/python ]]; then
    "$PYTHON_BIN" -m venv .venv
fi
.venv/bin/python -m pip install --upgrade pip
torch_args=()
if [[ -n "${ROBOTRON_TORCH_INDEX:-}" ]]; then
    torch_args+=(--index-url "$ROBOTRON_TORCH_INDEX")
fi
.venv/bin/python -m pip install 'torch==2.13.0' "${torch_args[@]}"
.venv/bin/python -m pip install 'numpy>=2.0' pillow aiohttp aiortc
.venv/bin/python -m pip freeze > Robotron/requirements-local.lock
printf 'Environment ready. No services installed or started. See Robotron/MIGRATION.md.\n'
