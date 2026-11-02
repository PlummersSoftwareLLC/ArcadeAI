#!/usr/bin/env bash
# Opt-in wrapper: preload the readiness helper into MAME only, including respawns.
set -euo pipefail
: "${ROBOTRON_SOCKET_WAIT_LIBRARY:?Set the absolute library path from build_socket_wait.py}"
: "${ROBOTRON_SOCKET_WAIT_US:?Set a readiness interval between 100 and 10000 microseconds}"
if [[ "$ROBOTRON_SOCKET_WAIT_LIBRARY" != /* || ! -f "$ROBOTRON_SOCKET_WAIT_LIBRARY" || "$ROBOTRON_SOCKET_WAIT_LIBRARY" == *[[:space:]:]* ]]; then
    echo 'Expected an existing absolute library path without whitespace or colons' >&2
    exit 2
fi
if [[ ! "$ROBOTRON_SOCKET_WAIT_US" =~ ^([1-9][0-9]{2,3}|10000)$ ]]; then
    echo 'Readiness interval must be between 100 and 10000 microseconds' >&2
    exit 2
fi
exec env -u LD_PRELOAD /usr/bin/python3.12 -I -B /home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/preview-selected-client-wallclock-original01-preparation-20261027/role-bound-wrapper-trial-original02-single-use/exec_role_bound_mame_once_v2.py --execute --base-helper /home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/preview-selected-client-wallclock-original01-preparation-20261027/role-bound-wrapper-trial-original01/exec_role_bound_mame_v1.py --permit /home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/preview-selected-client-wallclock-original01-preparation-20261027/role-bound-wrapper-trial-original02-single-use/STAGED_ONLY-slot163-single-use-permit.json --permit-sha256 53602056471bed91cb4e4a88e8d2b22ff6c946adb901c66e794d1ab01e1d615b --expected-source-sha256 b5fdc64b6777e6db2541f7c535be2fc49e47f5b565dcd714086cdb33d6041723 -- "$@"
