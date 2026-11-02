#!/usr/bin/env bash
set -euo pipefail
exec /usr/bin/python3.12 -I -B /home/dave/source/repos/ArcadeAI/Robotron/tools/power_recovery/mame_with_roles.py "$@"
