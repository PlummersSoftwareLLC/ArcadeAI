# Robotron DQN State Bag Report

This is the flattened input state used by the DQN model, as produced by
`dqn.config.slice_model_state(wire)`.

Lua sends 1478 big-endian `float32` values per frame. The DQN does not train on
that full payload. It keeps:

- `wire[0:18]`: 18 scalar core features.
- `wire[40:280]`: 8 directional lane blocks, 30 features each.
- 4 Python-derived salience features appended after the Lua slice.
- 16 compact object tokens, 12 features each, distilled from the Lua tactical
	object pools at `wire[766:1478]`.

Final raw DQN single-frame state size:
`18 + (8 * 30) + 4 + (16 * 12) = 454` floats.

With lane and object branches enabled, the model also reshapes `state[18:258]`
into `(8, 30)` lane tokens and `state[262:454]` into `(16, 12)` object tokens.
Those are encoded into learned embeddings and concatenated with the raw stacked
state before the trunk. With the default 2-frame stack, the first trunk layer
sees `908 + 128 + 128 = 1164` floats. The auxiliary lane/object branches read
the current frame.

## Top-Level Layout

| Model index range | Count | Source | Contents |
|---:|---:|---|---|
| `0..17` | 18 | Lua `wire[0:18]` | Core scalar game/player/threat features. |
| `18..257` | 240 | Lua `wire[40:280]`, reordered by Python | 8 directional lanes * 30 features. Model lane `L` starts at `18 + L * 30`, where `L = 0..7`. |
| `258..261` | 4 | Python derived | Enemy/human proximity and nearest-human global direction. |
| `262..453` | 192 | Python derived from Lua `wire[766:1478]` | 16 compact object tokens * 12 features, sorted by tactical priority. |

## Scaling Audit

The geometric quantities are scaled before they are clamped. Robotron object
positions are unsigned 8.8 fixed-point values, so one screen pixel is `256` in
the raw coordinate space.

| Quantity family | Scaling before clamp | Final clamp |
|---|---|---|
| Absolute player X/Y | `(pos16 - POS_MIN) / POS_RANGE` | `0..1` |
| Relative X/Y | `(entity16 - player16) / POS_X_RANGE` or `/ POS_Y_RANGE` | `-1..1` |
| Euclidean distances | `sqrt(dx16^2 + dy16^2) / POS_MAX_DIAG` | `0..1` |
| Per-frame velocities | `(current16 - previous16) / POS_X_RANGE` or `/ POS_Y_RANGE` | `-1..1` |
| TTC | `predicted_frames / TACTICAL_TTC_MAX_FRAMES` | `0..1` |
| Closest pass | `closest_distance16 / POS_MAX_DIAG` | `0..1` |
| Counts | `count / fixed_capacity` | `0..1` |
| Directional clearance | `forward_or_wall_distance16 / (TACTICAL_GRID_CELL_SIZE * 6)` | `0..1` |
| Cross-lane aim gate | `1.0 - cross_distance16 / (AIM_CROSS_THRESHOLD * 2)` | `0..1` |

For `nearest_human_dist`, the current path is:

```text
human center x16/y16
	-> rel_dx16 = human_x16 - player_center_x16
	-> rel_dy16 = human_y16 - player_center_y16
	-> dist_world = sqrt(rel_dx16^2 + rel_dy16^2)
	-> dist_norm = clamp01(dist_world / POS_MAX_DIAG)
	-> nearest_human_dist = min(dist_norm over human objects)
	-> serialize_frame emits clamp01(nearest_human_dist or 1.0)
	-> DQN state[10]
```

`POS_MAX_DIAG` is the playfield diagonal in 8.8 units:

```text
POS_X_RANGE = (143 - 7) * 256 = 34816
POS_Y_RANGE = (234 - 24) * 256 = 53760
POS_MAX_DIAG = sqrt(34816^2 + 53760^2) ~= 64022
```

So a human 16 pixels away horizontally has `dist_world = 16 * 256 = 4096`, and
`nearest_human_dist ~= 4096 / 64022 = 0.064`. No human present emits `1.0`.

Two caveats from the audit:

- `score_scaled` is scaled as `score / 1_000_000.0` but is not clamped, so scores
	above one million produce values above `1.0`.
- `enemy_threat` depends partly on `approach`, which is already `-1..1`; it is
	now explicitly mapped as `((approach or 0.0) + 1.0) * 0.5` before clamping.

## Core Features

| Model index | Name | Source / formula | Range / notes |
|---:|---|---|---|
| 0 | `player_alive` | `1.0` if alive, else `0.0` | Binary. |
| 1 | `score_scaled` | `score / 1_000_000.0` | Not clamped to 1.0 after score normalization. |
| 2 | `replay_norm` | `min(1.0, replay_level / 99_999_999.0)` | Replay/extra-life BCD field. |
| 3 | `lasers_norm` | `min(1.0, num_lasers / 9.0)` | Player laser/shot count. |
| 4 | `wave_norm` | `min(1.0, wave_number / 40.0)` | Current wave. |
| 5 | `player_x_norm` | Normalized player X position | Clamped `0..1`. |
| 6 | `player_y_norm` | Normalized player Y position | Clamped `0..1`. |
| 7 | `player_vel_x` | Frame-to-frame player X delta / playfield X range | Clamped `-1..1`; `0` when no previous live sample. |
| 8 | `player_vel_y` | Frame-to-frame player Y delta / playfield Y range | Clamped `-1..1`; `0` when no previous live sample. |
| 9 | `nearest_enemy_dist` | Distance to nearest dangerous enemy or spawner | Clamped `0..1`; `1.0` if absent. |
| 10 | `nearest_human_dist` | Distance to nearest human | Clamped `0..1`; `1.0` if absent. |
| 11 | `nearest_enemy_dx` | Relative X to nearest enemy | Clamped `-1..1`; `0` if absent. |
| 12 | `nearest_enemy_dy` | Relative Y to nearest enemy | Clamped `-1..1`; `0` if absent. |
| 13 | `human_count_norm` | `num_humans / 255.0` | Clamped `0..1`. |
| 14 | `nearest_spawner_dist` | Distance to nearest spawner | Clamped `0..1`; `1.0` if absent. |
| 15 | `nearest_spawner_dx` | Relative X to nearest spawner | Clamped `-1..1`; `0` if absent. |
| 16 | `nearest_spawner_dy` | Relative Y to nearest spawner | Clamped `-1..1`; `0` if absent. |
| 17 | `spawner_count_norm` | `num_spawners / 16.0` | Clamped `0..1`. |

## Repeated Lane Block

For lane `L` in `0..7`, the model index for a lane-local offset is:

```text
model_index = 18 + (L * 30) + lane_offset
```

Model lane rows are in controller action order:

```text
0=N, 1=NE, 2=E, 3=SE, 4=S, 5=SW, 6=W, 7=NW
```

Lua emits lane rows in geometric order:

```text
0=E, 1=NE, 2=N, 3=NW, 4=W, 5=SW, 6=S, 7=SE
```

`slice_model_state` reorders Lua lane rows with:

```text
ACTION_LANE_WIRE_INDICES = [2, 1, 0, 7, 6, 5, 4, 3]
```

so each model lane row lines up with the same move/fire action index. Lane
identity is also embedded directly as `lane_sin` and `lane_cos`, based on 8
evenly spaced directions around the player.

| Lane-local offset | Name | Source / formula | Range / notes |
|---:|---|---|---|
| 0 | `enemy_dist` | Nearest dangerous enemy distance in this lane | Clamped `0..1`; Python changes to `1.0` when `enemy_count == 0`. |
| 1 | `enemy_dx` | Nearest enemy relative X | Clamped `-1..1`; `0` if absent. |
| 2 | `enemy_dy` | Nearest enemy relative Y | Clamped `-1..1`; `0` if absent. |
| 3 | `enemy_vx` | Nearest enemy velocity X | Clamped `-1..1`; `0` if absent. |
| 4 | `enemy_vy` | Nearest enemy velocity Y | Clamped `-1..1`; `0` if absent. |
| 5 | `enemy_threat` | Nearest enemy threat score | Clamped `0..1`; `0` if absent. |
| 6 | `enemy_approach` | Nearest enemy radial approach score | Clamped `-1..1`; `0` if absent. |
| 7 | `enemy_count_norm` | `enemy_count_in_lane / 50.0` | Clamped `0..1`. |
| 8 | `human_dist` | Nearest human distance in this lane | Clamped `0..1`; Python changes to `1.0` when `human_count == 0`. |
| 9 | `human_dx` | Nearest human relative X | Clamped `-1..1`; `0` if absent. |
| 10 | `human_dy` | Nearest human relative Y | Clamped `-1..1`; `0` if absent. |
| 11 | `human_count_norm` | `human_count_in_lane / 16.0` | Clamped `0..1`. |
| 12 | `electrode_dist` | Nearest electrode distance in this lane | Clamped `0..1`; Python maps non-positive values to `1.0`. |
| 13 | `projectile_dist` | Nearest projectile distance in this lane | Clamped `0..1`; Python changes to `1.0` when `projectile_count == 0`. |
| 14 | `projectile_ttc` | Projectile time-to-collision estimate | Clamped `0..1`; Python changes to `1.0` when `projectile_count == 0`. |
| 15 | `projectile_closest_pass` | Predicted closest-pass distance | Clamped `0..1`; Python changes to `1.0` when `projectile_count == 0`. |
| 16 | `projectile_count_norm` | `projectile_count_in_lane / 24.0` | Clamped `0..1`. |
| 17 | `enemy_ttc` | Enemy time-to-collision estimate | Clamped `0..1`; Python changes to `1.0` when `enemy_count == 0`. |
| 18 | `lane_sin` | `sin(2*pi*L/8)` | Direction identity, `-1..1`. |
| 19 | `lane_cos` | `cos(2*pi*L/8)` | Direction identity, `-1..1`. |
| 20 | `move_clearance` | Directional movement affordance | Clamped `0..1`. |
| 21 | `move_danger_pressure` | Enemy pressure if moving this way | Clamped `0..1`. |
| 22 | `move_projectile_pressure` | Projectile pressure if moving this way | Clamped `0..1`. |
| 23 | `move_blocker_pressure` | Electrode/blocker pressure if moving this way | Clamped `0..1`. |
| 24 | `move_human_pull` | Human-rescue pull in this direction | Clamped `0..1`. |
| 25 | `move_escape_score` | Directional escape desirability | Clamped `0..1`. |
| 26 | `fire_best_target` | Best fire target score in this direction | Clamped `0..1`. |
| 27 | `fire_projectile_intercept` | Projectile-intercept fire score | Clamped `0..1`. |
| 28 | `fire_priority_target` | Priority target fire score | Clamped `0..1`. |
| 29 | `fire_target_density` | Target density for firing this way | Clamped `0..1`. |

## Derived Tail Features

| Model index | Name | Formula | Range / notes |
|---:|---|---|---|
| 258 | `enemy_proximity` | `1.0 - state[9]` | Near enemies become high-salience. |
| 259 | `human_proximity` | `1.0 - state[10]` | Near humans become high-salience. |
| 260 | `nearest_human_dx` | `human_dx` from the lane with the smallest present `human_dist` | `0` if no human is present. |
| 261 | `nearest_human_dy` | `human_dy` from the lane with the smallest present `human_dist` | `0` if no human is present. |

## Repeated Object Token Block

For object token `T` in `0..15`, the model index for a token-local offset is:

```text
model_index = 262 + (T * 12) + object_offset
```

Tokens are distilled from the Lua tactical pools in this order: projectiles,
dangerous enemies/spawners, humans, electrodes. The highest-priority 16 active
objects are kept; the rest are dropped. Empty token rows are all zeros and are
masked by object attention.

| Token-local offset | Name | Source / formula | Range / notes |
|---:|---|---|---|
| 0 | `present` | `1.0` for an active selected object | Empty rows are `0.0`. |
| 1 | `dx` | Relative X from player to object | Clamped `-1..1`. |
| 2 | `dy` | Relative Y from player to object | Clamped `-1..1`. |
| 3 | `dist` | Object distance from player | Clamped `0..1`; lower is closer. |
| 4 | `vx` | Object velocity X | Clamped `-1..1`; `0` when absent/unavailable. |
| 5 | `vy` | Object velocity Y | Clamped `-1..1`; `0` when absent/unavailable. |
| 6 | `threat` | Pool-specific threat/pressure score | Clamped `0..1`. |
| 7 | `ttc` | Time-to-collision or far default | Clamped `0..1`; lower is sooner. |
| 8 | `closest_pass` | Predicted closest pass distance | Clamped `0..1`; defaults to `dist`. |
| 9 | `approach` | Radial approach score | Clamped `-1..1`; positive means approaching. |
| 10 | `type_norm` | Compact object subtype code | Normalized `0..1`. |
| 11 | `role_norm` | Pool role code | Projectile `0.25`, danger `0.50`, human `0.75`, electrode `1.00`. |

## Lua Payload Values Not In The DQN State Bag

These values are still sent by Lua for other consumers/debugging, but are not in
the DQN replay state or the raw 454-float single-frame model input as full raw
payloads:

| Lua wire range | Count | Contents |
|---:|---:|---|
| `18..39` | 22 | Raw `ZP1ENM`/ELIST bytes normalized by `/255.0`. |
| `280..765` | 486 | 9x9 tactical grid, 6 channels per cell. |
| `766..1477` | 712 | Tactical object pools; DQN keeps only the compact top-16 object-token projection. |
