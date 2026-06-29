# Robotron AI Baseline

This `Robotron/Scripts` project is now a stripped baseline for Robotron-specific bring-up.

## Current Scope

- Lua sends a **1890-value wire packet** each frame:
  - 18 core player/game values
  - 22 `ZP1ENM` / ELIST bytes
  - legacy lane/grid sections kept on the wire for server stability
  - distance-sorted state-bag pools for 64 destructibles/projectiles, 16 hulks, 16 obstacles, and 16 humans
- Python v3 now converts those state-bag pools into an **object-ray representation**:
  - HUD-consistent collision-center object positions from `OPTR`, `HPTR`, `RPTR`, and `PPTR`
  - 32-feature entity tokens with relative/absolute position, velocity, timing, threat, type, and role flags
  - per-action move/fire ray features so each joystick direction is scored against the current geometry
- Python returns **dual 8-way joystick actions**:
  - movement direction index `0..7`
  - firing direction index `0..7`
- Replay/training pipeline remains active with this expanded state vector.

## Protocol (Lua -> Python)

- Header format: `>HddBIBBIBB`
  - `H`: number of float state values (currently `1890`)
  - `d`: subjective reward
  - `d`: objective reward
  - `B`: done flag
  - `I`: score (decoded from `ZP1SCR`)
  - `B`: player alive flag
  - `B`: save signal
  - `I`: next replay level (decoded from `ZP1RP`)
  - `B`: number of lasers (`ZP1LAS`)
  - `B`: wave number (`ZP1WAV`)
- Followed by `N` big-endian float32 state values.

## Protocol (Python -> Lua)

- Action format: `bbBBB`
  - movement direction index `0..7`
  - firing direction index `0..7`
  - source byte / preview flags
  - advanced-start flag
  - start-level minimum

When advanced start is off, Python now sends level `1` so Robotron starts on the
default wave.

## Startup Diagnostics

- Run the Python v3 server from `Robotron/Scripts`:
  - `python3 run_v3.py`
- Run foreground diagnostics:
  - `cd Robotron`
  - `./startmame.sh --fg`
- Point MAME at a remote Python host:
  - `ROBOTRON_SOCKET_ADDRESS=ubvmdell:9998 ./startmame.sh --fg`
  - or `./startmame.sh --fg --socket-address ubvmdell:9998`
- Background mode now reports explicit process liveness:
  - `./startmame.sh`
- Startup trace output is written to:
  - terminal
  - `Robotron/logs/startup_trace.log`

Lua debug controls in `Robotron/Scripts/main.lua`:

- Press `H` in a MAME window to toggle the local hitbox HUD. Set `ROBOTRON_LOCAL_HUD=1` to start it enabled.
- `DEBUG_STARTUP_TRACE` (default `false`)
- `DEBUG_TRACE_FRAMES` (default `10`)
- `DEBUG_BYPASS_SOCKET_FOR_FRAMES` (default `0`)
  - Set to `10` to skip socket send/recv for first 10 frames (neutral action), for A/B isolation.

Interpretation guide:

- Failure before `socket_write_ok`:
  - memory extraction / frame serialization path issue.
- Failure after `socket_write_begin` but before `socket_read_ok`:
  - socket exchange/timeout path issue.
- Failure after `apply_action`:
  - likely game runtime/ROM/input interaction issue.

## Remote Preview (WebRTC TURN/STUN)

The dashboard preview card can use WebRTC video streaming when `aiortc`, `av`, and `numpy` are installed.
For reliable mobile/remote viewing (5G, cross-country/international), configure TURN/STUN via:

- `ROBOTRON_WEBRTC_ICE_SERVERS` (JSON array of ICE server objects)

Example:

```bash
export ROBOTRON_WEBRTC_ICE_SERVERS='[
  {"urls":["stun:stun.l.google.com:19302"]},
  {"urls":["turn:turn.example.com:3478?transport=udp","turn:turn.example.com:3478?transport=tcp"],"username":"robotron","credential":"YOUR_SECRET"}
]'
```

If unset or invalid, dashboard uses built-in ICE defaults from
`Robotron/Scripts/v3/metrics_dashboard.py`.

## TODO (Known Missing Robotron Wiring)

- Exact MAME input field names for:
  - Start button
  - Coin insert
- Deeper Robotron feature extraction beyond PLDATA/ELIST mirror bytes.

The script now uses real RAM extraction for `PlayerAlive`, PLDATA fields, and enemy-state bag bytes.
