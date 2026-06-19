#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LUA_SCRIPT="$SCRIPT_DIR/Scripts/main.lua"
export TEMPEST_SERVER_HOST="${TEMPEST_SERVER_HOST:-127.0.0.1}"
export TEMPEST_SERVER_PORT="${TEMPEST_SERVER_PORT:-9999}"
EXPLICIT_SOCKET_ADDRESS=""
EXPLICIT_SERVER_HOST=""
EXPLICIT_SERVER_PORT=""

usage() {
    echo "Usage: $0 [COUNT] [--socket-address HOST:PORT] [--server-host HOST] [--server-port PORT] [-kill]"
    echo "  COUNT              Number of MAME instances to launch (default: 1)"
    echo "  --socket-address   Override Lua socket target directly"
    echo "  --server-host      Override TEMPEST_SERVER_HOST"
    echo "  --server-port      Override TEMPEST_SERVER_PORT"
    echo "  -kill              Kill all running MAME instances"
}

if [[ "${1:-}" == "-kill" ]]; then
    echo "Killing all running MAME instances..."
    pids=$(ps ax | grep '[m]ame.*tempest1' | awk '{print $1}')
    if [[ -n "$pids" ]]; then
        echo "$pids" | xargs kill -9
        echo "Killed PIDs: $(echo $pids | tr '\n' ' ')"
    else
        echo "No MAME instances found."
    fi
    exit 0
fi

COUNT="1"
COUNT_SET=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --socket-address)
            if [[ $# -lt 2 ]]; then
                echo "error: --socket-address requires HOST:PORT" >&2
                usage >&2
                exit 2
            fi
            EXPLICIT_SOCKET_ADDRESS="$2"
            shift 2
            ;;
        --socket-address=*)
            EXPLICIT_SOCKET_ADDRESS="${1#*=}"
            shift
            ;;
        --server-host)
            if [[ $# -lt 2 ]]; then
                echo "error: --server-host requires HOST" >&2
                usage >&2
                exit 2
            fi
            EXPLICIT_SERVER_HOST="$2"
            shift 2
            ;;
        --server-host=*)
            EXPLICIT_SERVER_HOST="${1#*=}"
            shift
            ;;
        --server-port)
            if [[ $# -lt 2 ]]; then
                echo "error: --server-port requires PORT" >&2
                usage >&2
                exit 2
            fi
            EXPLICIT_SERVER_PORT="$2"
            shift 2
            ;;
        --server-port=*)
            EXPLICIT_SERVER_PORT="${1#*=}"
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            if [[ "$COUNT_SET" -eq 1 ]]; then
                echo "error: multiple COUNT values provided" >&2
                usage >&2
                exit 1
            fi
            COUNT="$1"
            COUNT_SET=1
            shift
            ;;
    esac
done

if [[ -n "$EXPLICIT_SERVER_HOST" ]]; then
    export TEMPEST_SERVER_HOST="$EXPLICIT_SERVER_HOST"
fi
if [[ -n "$EXPLICIT_SERVER_PORT" ]]; then
    export TEMPEST_SERVER_PORT="$EXPLICIT_SERVER_PORT"
fi
if [[ -n "$EXPLICIT_SOCKET_ADDRESS" ]]; then
    export TEMPEST_SOCKET_ADDRESS="$EXPLICIT_SOCKET_ADDRESS"
fi

if ! [[ "$COUNT" =~ ^[0-9]+$ ]] || [[ "$COUNT" -lt 1 ]]; then
    usage
    exit 1
fi

SOUND_FLAG=""
VIDEO_FLAG=""
if [[ "$COUNT" -gt 1 ]]; then
    SOUND_FLAG="-sound none"
    VIDEO_FLAG="-video none"
fi

echo "Launching $COUNT MAME instance(s)..."
echo "Connecting MAME Lua clients to ${TEMPEST_SERVER_HOST}:${TEMPEST_SERVER_PORT}"
if [[ -n "${TEMPEST_SOCKET_ADDRESS:-}" ]]; then
    echo "Socket target override: ${TEMPEST_SOCKET_ADDRESS}"
fi
for i in $(seq 1 "$COUNT"); do
    mame tempest1 $VIDEO_FLAG -nothrottle $SOUND_FLAG -skip_gameinfo -autoboot_script "$LUA_SCRIPT" &
    echo "  Started instance $i (PID $!)"
done
echo "All instances launched."
