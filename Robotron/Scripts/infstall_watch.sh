#!/bin/bash
# Watch for the recurring inference-stall episodes (AvgInf ~120ms, FPS /10)
# and capture forensics from the LIVE trainer the moment one starts.
# Usage: nohup ./Scripts/infstall_watch.sh >/dev/null 2>&1 &
# Log:   logs/infstall_watch.log
set -u
LOG="$(dirname "$0")/../logs/infstall_watch.log"
API="http://localhost:8771/api/now"
THRESH=40          # ms — normal is 7-14, stall is ~120
POLL=5             # s between polls
CAPTURE_SECS=60    # forensic window per episode

log() { echo "$(date '+%F %T') $*" >> "$LOG"; }

thread_sched() {  # $1=pid: per-thread name, exec_ms, voluntary switches
  local pid=$1 t
  for t in /proc/$pid/task/*; do
    local comm exec vol
    comm=$(cat "$t/comm" 2>/dev/null) || continue
    exec=$(awk '/se.sum_exec_runtime/{print $3}' "$t/sched" 2>/dev/null)
    vol=$(awk '/nr_voluntary_switches/{print $3}' "$t/sched" 2>/dev/null)
    echo "  $(basename "$t") $comm exec=${exec}ms vol=${vol}"
  done
}

log "watcher started (threshold ${THRESH}ms)"
in_episode=0
while :; do
  inf=$(curl -s -m 3 "$API" | python3 -c "import json,sys;d=json.load(sys.stdin);print(f\"{d.get('avg_inf_ms',0):.1f} {d.get('fps',0):.0f} {d.get('frame_count',d.get('frames',0))}\")" 2>/dev/null) || { sleep $POLL; continue; }
  ms=${inf%% *}
  if (( $(echo "$ms > $THRESH" | bc -l) )); then
    if [[ $in_episode -eq 0 ]]; then
      in_episode=1
      pid=$(pgrep -f 'run_dqn[.]py' | head -1)
      log "=== EPISODE START: avg_inf/fps/frame = $inf (pid $pid) ==="
      end=$(( $(date +%s) + CAPTURE_SECS ))
      while (( $(date +%s) < end )); do
        log "--- sample: $(curl -s -m 3 "$API" | python3 -c "import json,sys;d=json.load(sys.stdin);print(f\"inf={d.get('avg_inf_ms',0):.1f}ms fps={d.get('fps',0):.0f}\")" 2>/dev/null) ---"
        log "GPU: $(nvidia-smi --query-gpu=index,utilization.gpu,clocks.sm,power.draw,temperature.gpu --format=csv,noheader | tr '\n' '|')"
        log "PSI: $(head -1 /proc/pressure/memory) / io: $(head -1 /proc/pressure/io)"
        thread_sched "$pid" | grep -E "InferBatch|TrainWorker|MainThread|Consume|python" >> "$LOG" 2>/dev/null
        thread_sched "$pid" | sort -t= -k2 -rn | head -8 >> "$LOG" 2>/dev/null
        sleep 10
      done
      log "=== capture window done ==="
    fi
  else
    [[ $in_episode -eq 1 ]] && log "=== EPISODE END: back to ${ms}ms ==="
    in_episode=0
  fi
  sleep $POLL
done
