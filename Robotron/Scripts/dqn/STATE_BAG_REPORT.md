# Robotron DQN State Bag Report

This is the flattened input state used by the DQN model, as produced by
`dqn.config.slice_model_state(wire)`.

Lua sends 1890 big-endian `float32` values per frame. The DQN does not train on
that full payload. It keeps only:

- `wire[0:18]`: 18 scalar core game/player/threat features.
- `wire[18:40]`: 22 raw ELIST/level-state bytes normalized by Lua.
- Four distance-sorted object groups from the Lua state-bag pools:
  64 destructible enemies/projectiles, 16 hulks, 16 obstacles, and 16 humans.

Final raw DQN single-frame state size:

```text
18 core + 22 ELIST + (112 objects * 10 features) = 1160 floats
```

With the default 1-frame stack, replay/inference state is also 1160 floats. The
network trunk does not flatten all 1160 floats into the MLP: it concatenates the
40 global/level floats from the current frame and the current-frame object
attention embedding. Default first trunk width is:

```text
(40 globals * 1 frame) + 128 object-attention embedding = 168 floats
```

If `DQN_FRAME_STACK=2` or `ROBOTRON_DQN_FRAME_STACK=2` is set, replay/inference
state becomes 2320 floats and the first trunk width becomes `80 + 128 = 208`.

## DQN Model Layout

| Model index range | Count | Source | Contents |
|---:|---:|---|---|
| `0..17` | 18 | Lua `wire[0:18]` | Core scalar game/player/threat features. |
| `18..39` | 22 | Lua `wire[18:40]` | Raw ELIST/level-state bytes. |
| `40..679` | 640 | Lua destructible pool `wire[767:1406]` | 64 nearest destructible enemies/projectiles * 10 features. |
| `680..839` | 160 | Lua hulk pool `wire[1408:1567]` | 16 nearest hulks * 10 features. |
| `840..999` | 160 | Lua obstacle pool `wire[1569:1728]` | 16 nearest obstacles/electrodes * 10 features. |
| `1000..1159` | 160 | Lua human pool `wire[1730:1889]` | 16 nearest humans * 10 features. |

For object row `R` in `0..111`:

```text
model_index = 40 + (R * 10) + row_offset
```

Rows are distance-sorted within each group. Overflow is ignored: if a wave has
more than 64 destructible objects, only the nearest 64 are represented.

## Row Features

| Row offset | Name | Source / formula | Range / notes |
|---:|---|---|---|
| 0 | `present` | `1.0` for active slot | Empty rows are all zeros. |
| 1 | `dx` | Relative X from player to object | Clamped `-1..1`. |
| 2 | `dy` | Relative Y from player to object | Clamped `-1..1`. |
| 3 | `dist` | Object distance from player | Clamped `0..1`; lower is closer. |
| 4 | `vx` | Object velocity X | Clamped `-1..1`. |
| 5 | `vy` | Object velocity Y | Clamped `-1..1`. |
| 6 | `threat` | Lua threat score | Clamped `0..1`. |
| 7 | `approach` | Radial approach score | Clamped `-1..1`; positive means approaching. |
| 8 | `ttc` | Time-to-collision estimate | Clamped `0..1`; lower is sooner. |
| 9 | `type_norm` | Lua type id normalized by `/ 8` | `0=grunt`, `1/8=hulk`, `2/8=brain`, `3/8=tank`, `4/8=spawner`, `5/8=enforcer`, `6/8=projectile`, `7/8=human`, `1=electrode`. |

## Core Features

| Model index | Name | Range / notes |
|---:|---|---|
| 0 | `player_alive` | Binary. |
| 1 | `score_scaled` | `score / 1_000_000.0`; not clamped after normalization. |
| 2 | `replay_norm` | Replay/extra-life BCD field. |
| 3 | `lasers_norm` | Player laser/shot count. |
| 4 | `wave_norm` | `min(1.0, wave_number / 40.0)`. |
| 5 | `player_x_norm` | Clamped `0..1`. |
| 6 | `player_y_norm` | Clamped `0..1`. |
| 7 | `player_vel_x` | Clamped `-1..1`. |
| 8 | `player_vel_y` | Clamped `-1..1`. |
| 9 | `nearest_enemy_dist` | Clamped `0..1`; `1.0` if absent. |
| 10 | `nearest_human_dist` | Clamped `0..1`; `1.0` if absent. |
| 11 | `nearest_enemy_dx` | Clamped `-1..1`; `0` if absent. |
| 12 | `nearest_enemy_dy` | Clamped `-1..1`; `0` if absent. |
| 13 | `human_count_norm` | Clamped `0..1`. |
| 14 | `nearest_spawner_dist` | Clamped `0..1`; `1.0` if absent. |
| 15 | `nearest_spawner_dx` | Clamped `-1..1`; `0` if absent. |
| 16 | `nearest_spawner_dy` | Clamped `-1..1`; `0` if absent. |
| 17 | `spawner_count_norm` | Clamped `0..1`. |

## Full Lua Wire Layout

These values are still sent by Lua for the expert/debug paths, but are excluded
from the DQN model state unless listed above.

| Lua wire range | Count | Contents | DQN use |
|---:|---:|---|---|
| `0..17` | 18 | Core scalar features | Kept. |
| `18..39` | 22 | Raw ELIST/level-state bytes | Kept. |
| `40..279` | 240 | Legacy tactical lanes | Excluded. |
| `280..765` | 486 | 9x9 tactical grid, 6 channels per cell | Excluded. |
| `766` | 1 | Destructible pool occupancy | Excluded. |
| `767..1406` | 640 | 64 destructible rows * 10 features | Kept as model rows `40..679`. |
| `1407` | 1 | Hulk pool occupancy | Excluded. |
| `1408..1567` | 160 | 16 hulk rows * 10 features | Kept as model rows `680..839`. |
| `1568` | 1 | Obstacle pool occupancy | Excluded. |
| `1569..1728` | 160 | 16 obstacle rows * 10 features | Kept as model rows `840..999`. |
| `1729` | 1 | Human pool occupancy | Excluded. |
| `1730..1889` | 160 | 16 human rows * 10 features | Kept as model rows `1000..1159`. |

## Scaling Notes

Robotron object positions are unsigned 8.8 fixed-point values, so one screen
pixel is `256` in the raw coordinate space. Relative X/Y values are normalized
by the playfield width/height and clamped to `-1..1`; distances are normalized
by the playfield diagonal and clamped to `0..1`.

`POS_X_RANGE = (143 - 7) * 256 = 34816`

`POS_Y_RANGE = (234 - 24) * 256 = 53760`

`POS_MAX_DIAG = sqrt(34816^2 + 53760^2) ~= 64022`
