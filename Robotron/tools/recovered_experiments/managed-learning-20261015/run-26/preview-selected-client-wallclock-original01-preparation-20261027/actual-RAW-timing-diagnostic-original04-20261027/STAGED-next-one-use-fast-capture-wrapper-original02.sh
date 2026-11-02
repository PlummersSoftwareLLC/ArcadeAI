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
exec env -u LD_PRELOAD /usr/bin/python3.12 -I -B /home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/preview-selected-client-wallclock-original01-preparation-20261027/RAW-phase-timing-diagnostic-one-use-helper-original01/exec_RAW_timing_diagnostic_once_v3.py --execute --base-helper /home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/preview-selected-client-wallclock-original01-preparation-20261027/role-bound-wrapper-trial-original01/exec_role_bound_mame_v1.py --fuse-helper /home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/preview-selected-client-wallclock-original01-preparation-20261027/role-bound-wrapper-trial-original02-single-use/exec_role_bound_mame_once_v2.py --collector-source /home/dave/source/repos/ArcadeAI/Robotron/tools/quality_capacity_proposal/supervised_main_fleet_v2.py --accepted-guards /home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/preview-selected-client-wallclock-original01-preparation-20261027/posttrial-slot163-authorities-and-readonly-reconciliation-original02-guard-corrections/posttrial_slot163_output_authority_v2.py --authority /home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/preview-selected-client-wallclock-original01-preparation-20261027/actual-RAW-timing-diagnostic-original04-20261027/actual-next-one-use-capture-authority-original02.json --authority-sha256 285b44dc94c7d21d03ce58b1fae847e94f55380841916f909735f49b350328c5 --expected-source-sha256 b805703e1782f1fa0db2453fb96d6446deb25c0c719d038da170019e274f83a0 -- "$@"
