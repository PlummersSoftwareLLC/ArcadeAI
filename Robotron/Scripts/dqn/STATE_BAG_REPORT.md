# Robotron DQN State Bag Report

This is the flattened input state used by the DQN model, as produced by
`dqn.config.slice_model_state(wire)`.

Lua sends 2118 big-endian `float32` values per frame. The DQN does not train on
that full payload. It keeps only:

- `wire[0:18]`: 18 scalar core game/player/threat features.
- `wire[18:40]`: 22 raw ELIST/level-state bytes normalized by Lua.
- `wire[1032:1992]`: the 96 stable danger/enemy pool slots, 10 features each.

Final raw DQN single-frame state size:

```text
18 core + 22 ELIST + (96 enemies * 10 features) = 1000 floats
```

With the default 1-frame stack, replay/inference state is also 1000 floats. The
network trunk does not flatten all 1000 floats into the MLP: it concatenates the
40 global/level floats from the current frame and the current-frame enemy
attention embedding. Default first trunk width is:

```text
(40 globals * 1 frame) + 128 enemy-attention embedding = 168 floats
```

If `DQN_FRAME_STACK=2` or `ROBOTRON_DQN_FRAME_STACK=2` is set, replay/inference
state becomes 2000 floats and the first trunk width becomes `80 + 128 = 208`.

## DQN Model Layout

| Model index range | Count | Source | Contents |
|---:|---:|---|---|
| `0..17` | 18 | Lua `wire[0:18]` | Core scalar game/player/threat features. |
| `18..39` | 22 | Lua `wire[18:40]` | Raw ELIST/level-state bytes. |
| `40..999` | 960 | Lua danger pool `wire[1032:1992]` | 96 stable enemy rows * 10 features. |

For enemy row `R` in `0..95`:

```text
model_index = 40 + (R * 10) + row_offset
```

Rows are copied in Lua's stable danger-pool slot order. They are not sorted or
top-K filtered, so row identity can persist across frames when Lua keeps the
same object in the same slot.

## Enemy Row Features

| Row offset | Name | Source / formula | Range / notes |
|---:|---|---|---|
| 0 | `present` | `1.0` for active slot | Empty rows are all zeros. |
| 1 | `dx` | Relative X from player to enemy | Clamped `-1..1`. |
| 2 | `dy` | Relative Y from player to enemy | Clamped `-1..1`. |
| 3 | `dist` | Enemy distance from player | Clamped `0..1`; lower is closer. |
| 4 | `vx` | Enemy velocity X | Clamped `-1..1`. |
| 5 | `vy` | Enemy velocity Y | Clamped `-1..1`. |
| 6 | `threat` | Lua danger/threat score | Clamped `0..1`. |
| 7 | `approach` | Radial approach score | Clamped `-1..1`; positive means approaching. |
| 8 | `ttc` | Time-to-collision estimate | Clamped `0..1`; lower is sooner. |
| 9 | `type_norm` | Lua enemy type id normalized by Lua | Clamped `0..1`. |

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
| `766` | 1 | Projectile pool occupancy | Excluded. |
| `767..1030` | 264 | 24 projectile slots * 11 features | Excluded. |
| `1031` | 1 | Danger pool occupancy | Excluded. |
| `1032..1991` | 960 | 96 danger/enemy slots * 10 features | Kept as model rows `40..999`. |
| `1992` | 1 | Human pool occupancy | Excluded. |
| `1993..2076` | 84 | 12 human slots * 7 features | Excluded. |
| `2077` | 1 | Electrode pool occupancy | Excluded. |
| `2078..2117` | 40 | 8 electrode slots * 5 features | Excluded. |

## Scaling Notes

Robotron object positions are unsigned 8.8 fixed-point values, so one screen
pixel is `256` in the raw coordinate space. Relative X/Y values are normalized
by the playfield width/height and clamped to `-1..1`; distances are normalized
by the playfield diagonal and clamped to `0..1`.

`POS_X_RANGE = (143 - 7) * 256 = 34816`

`POS_Y_RANGE = (234 - 24) * 256 = 53760`

`POS_MAX_DIAG = sqrt(34816^2 + 53760^2) ~= 64022`
