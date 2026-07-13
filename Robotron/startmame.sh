#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LUA_SCRIPT="$SCRIPT_DIR/Scripts/main.lua"
RELAY_SCRIPT="$SCRIPT_DIR/Scripts/audio_relay.py"
LOG_DIR="$SCRIPT_DIR/logs"
ROM_DIR="$SCRIPT_DIR/roms"
MAME_BIN="${MAME_BIN:-mame}"
TMP_AUDIO_GLOB="/tmp/robotron_audio_client"*.wav
TMP_AUDIO_FIFO_GLOB="/tmp/robotron_audio_client"*.fifo
AUDIO_BUFFER_BYTES="${ROBOTRON_AUDIO_BUFFER_BYTES:-20000000}"
GAME_AUDIO_ENABLED_RAW="${ROBOTRON_GAME_AUDIO_ENABLED:-1}"
GAME_AUDIO_ENABLED_NORM="$(printf '%s' "$GAME_AUDIO_ENABLED_RAW" | tr '[:upper:]' '[:lower:]')"
SKIP_UNUSED_TACTICAL_RAW="${ROBOTRON_SKIP_UNUSED_TACTICAL_FEATURES:-1}"
SKIP_UNUSED_TACTICAL_NORM="$(printf '%s' "$SKIP_UNUSED_TACTICAL_RAW" | tr '[:upper:]' '[:lower:]')"
VIDEO_ALL_RAW="${ROBOTRON_VIDEO_ALL_CLIENTS:-0}"
VIDEO_ALL_NORM="$(printf '%s' "$VIDEO_ALL_RAW" | tr '[:upper:]' '[:lower:]')"
AUDIO_ALL_RAW="${ROBOTRON_AUDIO_ALL_CLIENTS:-0}"
AUDIO_ALL_NORM="$(printf '%s' "$AUDIO_ALL_RAW" | tr '[:upper:]' '[:lower:]')"
DEFAULT_SOCKET_HOST="ubvmdell"
DEFAULT_SOCKET_PORT="9998"
SOCKET_HOST="$DEFAULT_SOCKET_HOST"
SOCKET_PORT="$DEFAULT_SOCKET_PORT"
SOCKET_ADDRESS=""
PREVIEW_SLOT_SELECTED=0

case "$GAME_AUDIO_ENABLED_NORM" in
    1|true|yes|on)
        GAME_AUDIO_ENABLED=1
        ;;
    *)
        GAME_AUDIO_ENABLED=0
        ;;
esac

case "$SKIP_UNUSED_TACTICAL_NORM" in
    1|true|yes|on)
        SKIP_UNUSED_TACTICAL_FEATURES=1
        ;;
    *)
        SKIP_UNUSED_TACTICAL_FEATURES=0
        ;;
esac

case "$VIDEO_ALL_NORM" in
    1|true|yes|on)
        VIDEO_ALL_CLIENTS=1
        ;;
    *)
        VIDEO_ALL_CLIENTS=0
        ;;
esac

case "$AUDIO_ALL_NORM" in
    1|true|yes|on)
        AUDIO_ALL_CLIENTS=1
        ;;
    *)
        AUDIO_ALL_CLIENTS=0
        ;;
esac

resolve_client_socket() {
    local client_slot="$1"
    local preview_slot="$PREVIEW_SLOT_SELECTED"
    local socket_addr="$SOCKET_ADDRESS"
    local preview_flag="1"

    if [[ "$client_slot" -ne "$preview_slot" ]]; then
        preview_flag="0"
    fi

    printf '%s|%s\n' "$socket_addr" "$preview_flag"
}

ensure_audio_fifo() {
    local fifo_path="$1"
    rm -f "$fifo_path"
    mkfifo "$fifo_path"
}

# Default to project-local ROMs; allow callers to append/override via MAME_ROMPATH.
if [[ -n "${MAME_ROMPATH:-}" ]]; then
    ROMPATH="$ROM_DIR;$MAME_ROMPATH"
else
    ROMPATH="$ROM_DIR"
fi

usage() {
    echo "Usage: $0 [COUNT] [novideo] [nonaudio] [--fg] [--throttle-client0] [--socket-address HOST:PORT] [--socket-host HOST] [--socket-port PORT] [-kill]"
    echo "       $0 kill CLIENT_ID"
    echo "  COUNT              Desired number of MAME instances left running (default: 1, background mode only; 0 kills all)"
    echo "  novideo            Launch MAME headless with -video none and -sound none for faster operation"
    echo "  nonaudio           Launch MAME with -sound none while keeping video behavior unchanged"
    echo "  ROBOTRON_VIDEO_ALL_CLIENTS=1 restores software video for every background client"
    echo "  ROBOTRON_AUDIO_ALL_CLIENTS=1 restores audio capture for every background client unless novideo/nonaudio is set"
    echo "  --socket-address   Set the Python socket target for all clients"
    echo "  --socket-host      Set socket host (default: ubvmdell)"
    echo "  --socket-port      Set socket port (default: 9998)"
    echo "  --fg               Run one MAME instance in foreground"
    echo "  --throttle-client0 Throttle client 0 to real-time speed (default: unthrottled)"
    echo "  --supervise        Stay running after launch and respawn any client slot that dies"
    echo "                     (checks every ${ROBOTRON_SUPERVISE_INTERVAL:-30}s; a slot crashing"
    echo "                     ${ROBOTRON_RESPAWN_GUARD_MAX:-5}x in ${ROBOTRON_RESPAWN_GUARD_WINDOW:-600}s is quarantined; run under tmux/nohup for long sessions;"
    echo "                     with a supervisor active, 'kill CLIENT_ID' becomes force-restart)"
    echo "  -kill              Kill all running Robotron MAME instances"
    echo "  kill CLIENT_ID     Kill one Robotron MAME client by ROBOTRON_CLIENT_SLOT"
    echo "  Tip: use --socket-address ubvmdell:9998 for a remote host"
}

list_robotron_pids() {
    pgrep -f 'mame.*robotron' || true
}

count_running_robotron_instances() {
    local pids
    pids="$(list_robotron_pids)"
    if [[ -z "${pids//[[:space:]]/}" ]]; then
        echo 0
    else
        printf '%s\n' "$pids" | awk 'NF { count++ } END { print count + 0 }'
    fi
}

kill_all_robotron_instances() {
    local message="${1:-Killing all running Robotron MAME instances...}"
    local pids

    echo "$message"
    # Stop any supervisor first, or it would respawn clients as we kill them.
    stop_existing_supervisor
    pids="$(list_robotron_pids)"
    if [[ -n "${pids//[[:space:]]/}" ]]; then
        echo "$pids" | xargs kill -9
        echo "Killed PIDs: $(echo "$pids" | tr '\n' ' ')"
    else
        echo "No Robotron MAME instances found."
    fi

    cleanup_audio_relays
    cleanup_audio_wavs
    cleanup_audio_fifos
    echo "Removed stale audio capture files from /tmp."
}

kill_client_by_id() {
    local client_id="$1"
    if ! [[ "$client_id" =~ ^[0-9]+$ ]]; then
        echo "error: CLIENT_ID must be a non-negative integer" >&2
        return 2
    fi

    local pids=""
    local all_robotron_pids
    all_robotron_pids=$(pgrep -f 'mame.*robotron' || true)

    # Primary path (Linux): match the exported client slot from process env.
    if [[ -d /proc ]]; then
        local pid
        for pid in $all_robotron_pids; do
            if [[ -r "/proc/$pid/environ" ]] && tr '\0' '\n' < "/proc/$pid/environ" | grep -qx "ROBOTRON_CLIENT_SLOT=$client_id"; then
                pids+="$pid "$'\n'
            fi
        done
    fi

    # Fallback: command-line marker (works only if launcher preserved it in argv).
    if [[ -z "${pids//[[:space:]]/}" ]]; then
        pids=$(ps ax -o pid= -o command= | awk -v cid="$client_id" '
            index($0, "mame") && index($0, "robotron") && $0 ~ ("ROBOTRON_CLIENT_SLOT=" cid "([[:space:]]|$)") {
                print $1
            }
        ')
    fi

    if [[ -z "${pids//[[:space:]]/}" ]]; then
        echo "No Robotron MAME process found for client $client_id."
        return 1
    fi

    echo "Killing Robotron MAME client $client_id..."
    echo "$pids" | xargs kill -9
    echo "Killed PIDs: $(echo "$pids" | tr '\n' ' ')"

    if ! pgrep -f 'mame.*robotron' >/dev/null 2>&1; then
        cleanup_audio_relays
        cleanup_audio_wavs
        cleanup_audio_fifos
        echo "No Robotron clients remaining; removed stale audio capture files from /tmp."
    fi
    return 0
}

cleanup_audio_wavs() {
    rm -f $TMP_AUDIO_GLOB 2>/dev/null || true
}

cleanup_audio_fifos() {
    rm -f $TMP_AUDIO_FIFO_GLOB 2>/dev/null || true
}

cleanup_audio_relays() {
    pkill -f "$RELAY_SCRIPT" 2>/dev/null || true
}

# ── supervisor ──────────────────────────────────────────────────────────────
SUPERVISOR_PIDFILE="$LOG_DIR/robotron_supervisor.pid"
SUPERVISE_INTERVAL="${ROBOTRON_SUPERVISE_INTERVAL:-30}"
RESPAWN_GUARD_WINDOW="${ROBOTRON_RESPAWN_GUARD_WINDOW:-600}"
RESPAWN_GUARD_MAX="${ROBOTRON_RESPAWN_GUARD_MAX:-5}"

stop_existing_supervisor() {
    local spid
    if [[ -f "$SUPERVISOR_PIDFILE" ]]; then
        spid="$(cat "$SUPERVISOR_PIDFILE" 2>/dev/null || true)"
        if [[ -n "$spid" && "$spid" != "$$" ]] && kill -0 "$spid" 2>/dev/null; then
            echo "Stopping existing supervisor (PID $spid)..."
            kill "$spid" 2>/dev/null || true
        fi
        rm -f "$SUPERVISOR_PIDFILE"
    fi
}

list_live_slots() {
    # One line per live client slot, discovered from each MAME process's
    # environment (same primary path kill_client_by_id uses).
    local pid slot
    for pid in $(list_robotron_pids); do
        [[ -r "/proc/$pid/environ" ]] || continue
        slot="$(tr '\0' '\n' < "/proc/$pid/environ" 2>/dev/null | sed -n 's/^ROBOTRON_CLIENT_SLOT=//p' | head -1 || true)"
        if [[ -n "$slot" ]]; then
            printf '%s\n' "$slot"
        fi
    done
    # Explicit success: a trailing no-slot match (e.g. a grep/tail whose
    # command line mentions mame+robotron) must not fail the function —
    # under set -e/pipefail that silently killed the supervisor.
    return 0
}

launch_client() {
    # Launch one MAME client for a slot.  ATTACHED=1 keeps stdout on the
    # terminal (initial launch of instance 1 only); respawns always log to
    # the slot's file.  Sets LAST_LAUNCH_PID/_SOCKET/_DESC/_LOG.
    local slot="$1"
    local attached="${2:-0}"
    local socket_info client_socket preview_flag sound_flag video_flag video_desc throttle_flag log_file audio_fifo

    socket_info="$(resolve_client_socket "$slot")"
    client_socket="${socket_info%%|*}"
    preview_flag="${socket_info##*|}"

    sound_flag="$SOUND_DISABLED_FLAG"
    if [[ "$GAME_AUDIO_ENABLED" -eq 1 && ( "$AUDIO_ALL_CLIENTS" -eq 1 || "$slot" -eq "$PREVIEW_SLOT_SELECTED" ) ]]; then
        audio_fifo="/tmp/robotron_audio_client${slot}.fifo"
        # Reuse an existing fifo (the relay may hold it open); only create if
        # missing.  Recreating it here would orphan the relay's read end.
        [[ -p "$audio_fifo" ]] || ensure_audio_fifo "$audio_fifo"
        sound_flag="-wavwrite $audio_fifo -samplerate 48000 -audio_latency 1"
    fi

    video_flag="$VIDEO_FLAG"
    video_desc="$VIDEO_MODE_DESC"
    if [[ "$NO_VIDEO" -eq 0 && "$VIDEO_ALL_CLIENTS" -eq 0 && "$slot" -ne "$PREVIEW_SLOT_SELECTED" ]]; then
        video_flag="-video none"
        video_desc="headless"
    fi

    if [[ "$slot" -eq 0 && "$THROTTLE_CLIENT0" -eq 1 ]]; then
        throttle_flag="-throttle -speed 1.0"
    else
        throttle_flag="-nothrottle"
    fi

    log_file="$LOG_DIR/mame_instance_${slot}.log"
    if [[ "$attached" -eq 1 ]]; then
        ROBOTRON_SOCKET_ADDRESS="$client_socket" ROBOTRON_PREVIEW_CLIENT="$preview_flag" ROBOTRON_CLIENT_SLOT="$slot" ROBOTRON_SKIP_UNUSED_TACTICAL_FEATURES="$SKIP_UNUSED_TACTICAL_FEATURES" "$MAME_BIN" robotron -rompath "$ROMPATH" $throttle_flag $sound_flag $video_flag -skip_gameinfo $WARNING_FLAG -autoboot_script "$LUA_SCRIPT" &
    else
        ROBOTRON_SOCKET_ADDRESS="$client_socket" ROBOTRON_PREVIEW_CLIENT="$preview_flag" ROBOTRON_CLIENT_SLOT="$slot" ROBOTRON_SKIP_UNUSED_TACTICAL_FEATURES="$SKIP_UNUSED_TACTICAL_FEATURES" "$MAME_BIN" robotron -rompath "$ROMPATH" $throttle_flag $sound_flag $video_flag -skip_gameinfo $WARNING_FLAG -autoboot_script "$LUA_SCRIPT" >> "$log_file" 2>&1 &
    fi
    LAST_LAUNCH_PID=$!
    LAST_LAUNCH_SOCKET="$client_socket"
    LAST_LAUNCH_DESC="$video_desc"
    LAST_LAUNCH_LOG="$log_file"
}

supervise_loop() {
    # Respawn dead client slots forever.  Slot identity matters: the server
    # derives its client id from the launch slot, so respawning slot N as
    # slot N automatically restores that cid's role (e.g. eval clients on
    # the stride-10 slots).  Never returns; INT/TERM exits the supervisor
    # while leaving the fleet running.
    declare -A respawn_times=()
    declare -A quarantined=()
    local live now slot times t kept

    # A supervisor must outlive transient hiccups (vanished /proc entries,
    # racing pgrep matches).  The script-wide errexit/pipefail would turn any
    # of those into a silent exit, so run this loop without them.  The loop
    # never returns, so the relaxation cannot leak into other code paths.
    set +e +o pipefail

    stop_existing_supervisor
    echo "$$" > "$SUPERVISOR_PIDFILE"
    trap 'rm -f "$SUPERVISOR_PIDFILE"; echo; echo "[SUPERVISOR] exiting (fleet left running; use '"$0"' -kill to stop it)"; exit 0' INT TERM
    echo "[SUPERVISOR] watching slots 0-$((COUNT - 1)) every ${SUPERVISE_INTERVAL}s" \
         "(quarantine after ${RESPAWN_GUARD_MAX} crashes in ${RESPAWN_GUARD_WINDOW}s; Ctrl-C stops the supervisor only)"
    while :; do
        sleep "$SUPERVISE_INTERVAL" || true
        live=" $(list_live_slots | tr '\n' ' ') "
        now="$(date +%s)"
        for ((slot = 0; slot < COUNT; slot++)); do
            [[ -n "${quarantined[$slot]:-}" ]] && continue
            [[ "$live" == *" $slot "* ]] && continue
            # Prune respawn history to the guard window.
            times=""
            kept=0
            for t in ${respawn_times[$slot]:-}; do
                if (( now - t < RESPAWN_GUARD_WINDOW )); then
                    times+="$t "
                    kept=$((kept + 1))
                fi
            done
            if (( kept >= RESPAWN_GUARD_MAX )); then
                quarantined[$slot]=1
                echo "[SUPERVISOR] $(date '+%H:%M:%S') client $slot crashed ${kept}x in ${RESPAWN_GUARD_WINDOW}s —" \
                     "QUARANTINED (no more respawns; check $LOG_DIR/mame_instance_${slot}.log)"
                continue
            fi
            respawn_times[$slot]="${times}${now}"
            launch_client "$slot" 0
            echo "[SUPERVISOR] $(date '+%H:%M:%S') respawned client $slot" \
                 "(PID $LAST_LAUNCH_PID, crash $((kept + 1))/${RESPAWN_GUARD_MAX} in window)  log: $LAST_LAUNCH_LOG"
        done
    done
}

FOREGROUND=0
COUNT="1"
COUNT_SET=0
NO_VIDEO=0
NO_AUDIO=0
THROTTLE_CLIENT0=0
SUPERVISE=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        kill)
            if [[ $# -lt 2 ]]; then
                echo "error: kill requires CLIENT_ID" >&2
                usage >&2
                exit 2
            fi
            kill_client_by_id "$2"
            exit $?
            ;;
        -kill)
            kill_all_robotron_instances
            exit 0
            ;;
        --fg)
            FOREGROUND=1
            shift
            ;;
        --socket-address)
            if [[ $# -lt 2 ]]; then
                echo "error: --socket-address requires HOST:PORT" >&2
                usage >&2
                exit 2
            fi
            SOCKET_ADDRESS="$2"
            shift 2
            ;;
        --socket-address=*)
            SOCKET_ADDRESS="${1#*=}"
            shift
            ;;
        --socket-host)
            if [[ $# -lt 2 ]]; then
                echo "error: --socket-host requires HOST" >&2
                usage >&2
                exit 2
            fi
            SOCKET_HOST="$2"
            shift 2
            ;;
        --socket-host=*)
            SOCKET_HOST="${1#*=}"
            shift
            ;;
        --socket-port)
            if [[ $# -lt 2 ]]; then
                echo "error: --socket-port requires PORT" >&2
                usage >&2
                exit 2
            fi
            SOCKET_PORT="$2"
            shift 2
            ;;
        --socket-port=*)
            SOCKET_PORT="${1#*=}"
            shift
            ;;
        --throttle-client0)
            THROTTLE_CLIENT0=1
            shift
            ;;
        --supervise)
            SUPERVISE=1
            shift
            ;;
        novideo)
            NO_VIDEO=1
            shift
            ;;
        nonaudio|--nonaudio|noaudio|--noaudio)
            NO_AUDIO=1
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
            if [[ "$1" =~ ^[0-9]+$ ]]; then
                COUNT="$1"
            else
                echo "error: unrecognized argument: $1" >&2
                usage >&2
                exit 1
            fi
            COUNT_SET=1
            shift
            ;;
    esac
done

if [[ -z "$SOCKET_ADDRESS" ]]; then
    SOCKET_ADDRESS="${SOCKET_HOST}:${SOCKET_PORT}"
fi

if ! [[ "$COUNT" =~ ^[0-9]+$ ]]; then
    echo "error: COUNT must be a non-negative integer" >&2
    usage >&2
    exit 1
fi

if [[ "$COUNT" -eq 0 ]]; then
    kill_all_robotron_instances "Target count is 0; stopping all Robotron MAME instances..."
    exit 0
fi

if [[ "$FOREGROUND" -eq 1 && "$COUNT" -ne 1 ]]; then
    echo "error: --fg supports COUNT=1 only" >&2
    exit 1
fi

if [[ "$SUPERVISE" -eq 1 && "$FOREGROUND" -eq 1 ]]; then
    echo "error: --supervise is incompatible with --fg" >&2
    exit 1
fi

mkdir -p "$LOG_DIR"

WARNING_FLAG=""
if "$MAME_BIN" -showusage 2>&1 | grep -q -- "-skip_warnings"; then
    WARNING_FLAG="-skip_warnings"
else
    echo "Note: this MAME build does not support -skip_warnings; continuing without it."
fi

if [[ ! -d "$ROM_DIR" ]]; then
    echo "error: ROM directory not found: $ROM_DIR" >&2
    exit 1
fi

if ! "$MAME_BIN" -rompath "$ROMPATH" -verifyroms robotron >/dev/null 2>&1; then
    echo "error: Robotron ROM verification failed for rompath: $ROMPATH" >&2
    "$MAME_BIN" -rompath "$ROMPATH" -verifyroms robotron || true
    exit 1
fi

RUNNING_COUNT="$(count_running_robotron_instances)"
if [[ "$RUNNING_COUNT" -gt 0 ]]; then
    kill_all_robotron_instances "Reconciling to $COUNT Robotron MAME instance(s) by restarting the current $RUNNING_COUNT instance(s)..."
else
    # A stale supervisor may be sleeping even with the fleet dead; stop it so
    # it cannot fight this launch.
    stop_existing_supervisor
    cleanup_audio_relays
    cleanup_audio_wavs
    cleanup_audio_fifos
fi

if [[ "$NO_VIDEO" -eq 1 || "$NO_AUDIO" -eq 1 ]]; then
    GAME_AUDIO_ENABLED=0
    AUDIO_ALL_CLIENTS=0
fi

if [[ "$NO_VIDEO" -eq 1 ]]; then
    VIDEO_FLAG="-video none"
    VIDEO_MODE_DESC="headless"
else
    VIDEO_FLAG="-video soft"
    if [[ "$GAME_AUDIO_ENABLED" -eq 1 ]]; then
        VIDEO_MODE_DESC="preview audio/video enabled"
    else
        VIDEO_MODE_DESC="preview video enabled"
    fi
fi

SOUND_DISABLED_FLAG="-sound none"

if [[ "$FOREGROUND" -eq 1 ]]; then
    echo "Mode: foreground"
    if [[ "$THROTTLE_CLIENT0" -eq 1 ]]; then
        echo "Launching 1 MAME instance (attached) with $VIDEO_MODE_DESC, throttled to real time..."
    else
        echo "Launching 1 MAME instance (attached) with $VIDEO_MODE_DESC, unthrottled..."
    fi
    SOUND_FLAG="$SOUND_DISABLED_FLAG"
    if [[ "$GAME_AUDIO_ENABLED" -eq 1 ]]; then
        AUDIO_FIFO="/tmp/robotron_audio_client0.fifo"
        ensure_audio_fifo "$AUDIO_FIFO"
        python3 "$RELAY_SCRIPT" --slot-count 1 --audio-dir /tmp --max-bytes "$AUDIO_BUFFER_BYTES" \
            >> "$LOG_DIR/audio_relay.log" 2>&1 &
        SOUND_FLAG="-wavwrite $AUDIO_FIFO -samplerate 48000 -audio_latency 1"
    fi
    if [[ "$THROTTLE_CLIENT0" -eq 1 ]]; then
        THROTTLE_FLAG="-throttle -speed 1.0"
    else
        THROTTLE_FLAG="-nothrottle"
    fi
    socket_info="$(resolve_client_socket 0)"
    CLIENT_SOCKET_ADDRESS="${socket_info%%|*}"
    PREVIEW_CLIENT_FLAG="${socket_info##*|}"
    echo "Socket target: $CLIENT_SOCKET_ADDRESS"
    env ROBOTRON_SOCKET_ADDRESS="$CLIENT_SOCKET_ADDRESS" ROBOTRON_PREVIEW_CLIENT="$PREVIEW_CLIENT_FLAG" ROBOTRON_CLIENT_SLOT=0 ROBOTRON_SKIP_UNUSED_TACTICAL_FEATURES="$SKIP_UNUSED_TACTICAL_FEATURES" "$MAME_BIN" robotron -rompath "$ROMPATH" $THROTTLE_FLAG $SOUND_FLAG $VIDEO_FLAG -window -skip_gameinfo $WARNING_FLAG -autoboot_script "$LUA_SCRIPT"
    status=$?
    cleanup_audio_relays
    cleanup_audio_fifos
    exit "$status"
fi

echo "Mode: background"
if [[ "$COUNT" -eq 1 ]]; then
    if [[ "$THROTTLE_CLIENT0" -eq 1 ]]; then
        echo "Launching 1 MAME instance (client 0) with $VIDEO_MODE_DESC, throttled to real time..."
    else
        echo "Launching 1 MAME instance (client 0) with $VIDEO_MODE_DESC, unthrottled..."
    fi
else
    if [[ "$THROTTLE_CLIENT0" -eq 1 ]]; then
        echo "Launching $COUNT MAME instance(s): client 0 throttled, others unthrottled..."
    else
        echo "Launching $COUNT MAME instance(s): all clients with $VIDEO_MODE_DESC, unthrottled..."
    fi
fi
if [[ "$GAME_AUDIO_ENABLED" -eq 1 ]]; then
    RELAY_SLOT_COUNT="$COUNT"
    if [[ "$AUDIO_ALL_CLIENTS" -eq 0 ]]; then
        RELAY_SLOT_COUNT=$((PREVIEW_SLOT_SELECTED + 1))
    fi
    for i in $(seq 1 "$COUNT"); do
        CLIENT_SLOT=$((i-1))
        if [[ "$AUDIO_ALL_CLIENTS" -eq 1 || "$CLIENT_SLOT" -eq "$PREVIEW_SLOT_SELECTED" ]]; then
            ensure_audio_fifo "/tmp/robotron_audio_client${CLIENT_SLOT}.fifo"
        fi
    done
    python3 "$RELAY_SCRIPT" --slot-count "$RELAY_SLOT_COUNT" --audio-dir /tmp --max-bytes "$AUDIO_BUFFER_BYTES" \
        >> "$LOG_DIR/audio_relay.log" 2>&1 &
fi
declare -a PIDS=()
for i in $(seq 1 "$COUNT"); do
    CLIENT_SLOT=$((i-1))
    if [[ $i -eq 1 ]]; then
        # Keep the first instance attached to the terminal so one clean set of init lines stays visible.
        launch_client "$CLIENT_SLOT" 1
    else
        launch_client "$CLIENT_SLOT" 0
    fi
    PIDS+=("$LAST_LAUNCH_PID")
    if [[ $i -eq 1 && "$THROTTLE_CLIENT0" -eq 1 ]]; then
        echo "  Started instance $i (client $CLIENT_SLOT -> $LAST_LAUNCH_SOCKET - $LAST_LAUNCH_DESC, throttled) PID $LAST_LAUNCH_PID  log: $LAST_LAUNCH_LOG"
    else
        echo "  Started instance $i (client $CLIENT_SLOT -> $LAST_LAUNCH_SOCKET - $LAST_LAUNCH_DESC, unthrottled) PID $LAST_LAUNCH_PID  log: $LAST_LAUNCH_LOG"
    fi
done

echo "All instances launched. Checking process liveness..."
sleep 1
for pid in "${PIDS[@]}"; do
    if kill -0 "$pid" 2>/dev/null; then
        echo "  RUNNING: PID $pid"
    else
        echo "  NOT RUNNING: PID $pid"
    fi
done

if [[ "$SUPERVISE" -eq 1 ]]; then
    supervise_loop   # never returns; Ctrl-C exits the supervisor, fleet keeps running
fi

echo "Script exits now; MAME continues running in background."
