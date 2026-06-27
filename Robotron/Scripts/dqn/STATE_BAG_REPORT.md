# Robotron DQN State Bag Report

This is the flattened input state used by the DQN model, as produced by
`dqn.config.slice_model_state(wire)`.

Lua sends 2118 big-endian `float32` values per frame. The DQN does not train on
that full payload. It keeps only:

- `wire[0:18]`: 18 scalar core game/player/threat features.
- `wire[18:40]`: 22 raw ELIST/level-state bytes normalized by Lua.
- `wire[40:280]`: only two values from each tactical lane row: enemy density
  and human density, reordered into controller action order.
- `model[56:59]`: Python-derived nearest destructible target `dx/dy/dist`,
  computed from the packed object list.
- A Python-derived 96-row object list distilled from the projectile, danger,
  human, and electrode tactical pools in `wire[766:2118]`.

`ROBOTRON_SKIP_UNUSED_TACTICAL_FEATURES=1` keeps the wire fast, but it no longer
zeros DQN-critical cues. Lua still computes object `threat`, `approach`, `ttc`,
`closest_pass`, and the lane enemy/human density fields consumed by this slice;
only the heavier unused tactical grid and lane affordance details are skipped.

Final raw DQN single-frame state size:

```text
18 core + 22 ELIST + 16 lane density + 3 nearest-target + (96 objects * 16 features) = 1595 floats
```

With the default 1-frame stack, replay/inference state is also 1595 floats. The
network trunk does not flatten all 1595 floats into the MLP: it concatenates the
59 direct global/lane/target floats from the current frame and the current-frame object
attention embedding. Default first trunk width is:

```text
(59 globals/lane/target * 1 frame) + 128 object-attention embedding = 187 floats
```

If `DQN_FRAME_STACK=2` or `ROBOTRON_DQN_FRAME_STACK=2` is set, replay/inference
state becomes 3190 floats and the first trunk width becomes `118 + 128 = 246`.

## DQN Model Layout

| Model index range | Count | Source | Contents |
|---:|---:|---|---|
| `0..17` | 18 | Lua `wire[0:18]` | Core scalar game/player/threat features. |
| `18..39` | 22 | Lua `wire[18:40]` | Raw ELIST/level-state bytes. |
| `40..55` | 16 | Lua tactical lanes `wire[40:280]` | 8 action-order lanes * enemy density + human density. |
| `56..58` | 3 | Python-derived from object rows | Nearest destructible target `dx/dy/dist`. |
| `59..1594` | 1536 | Lua tactical pools `wire[766:2118]` | 96 priority-sorted role-aware object rows * 16 features. |

For lane row `R` in action order `N, NE, E, SE, S, SW, W, NW`:

```text
model_index = 40 + (R * 2) + lane_offset
```

## Lane Density Features

| Lane offset | Name | Source / formula | Range / notes |
|---:|---|---|---|
| 0 | `enemy_density` | Lua lane feature 7, `enemy_count / 50` | Clamped `0..1`. |
| 1 | `human_density` | Lua lane feature 11, `human_count / 16` | Clamped `0..1`. |

## Nearest Destructible Target Features

These features are computed after the Python role-aware object list is built.
They point to the nearest present row with `destructible=1` and `rescue=0`;
currently that includes normal shootable enemies and shootable projectiles, and
excludes humans, hulks, and electrodes. If no target is present the value is
`[0.0, 0.0, 1.0]`.

| Model index | Name | Source / formula | Range / notes |
|---:|---|---|---|
| 56 | `nearest_target_dx` | Object row `dx` for nearest destructible target | Clamped `-1..1`; `0` if absent. |
| 57 | `nearest_target_dy` | Object row `dy` for nearest destructible target | Clamped `-1..1`; `0` if absent. |
| 58 | `nearest_target_dist` | Object row `dist` for nearest destructible target | Clamped `0..1`; `1` if absent. |

For object row `R` in `0..95`:

```text
model_index = 59 + (R * 16) + row_offset
```

Rows are top-K priority sorted by immediate tactical relevance. Row identity is
not stable across frames; the network should treat this as a set/list, not a
slot-addressed table.

## Object Row Features

| Row offset | Name | Source / formula | Range / notes |
|---:|---|---|---|
| 0 | `present` | `1.0` for active row | Empty rows are all zeros. |
| 1 | `dx` | Relative X from player to object | Clamped `-1..1`. |
| 2 | `dy` | Relative Y from player to object | Clamped `-1..1`. |
| 3 | `dist` | Object distance from player | Clamped `0..1`; lower is closer. |
| 4 | `vx` | Object velocity X | Clamped `-1..1`; zero for static objects. |
| 5 | `vy` | Object velocity Y | Clamped `-1..1`; zero for static objects. |
| 6 | `threat` | Pool-specific danger/threat cue | Clamped `0..1`. |
| 7 | `approach` | Radial approach score | Clamped `-1..1`; positive means approaching. |
| 8 | `ttc` | Time-to-collision estimate | Clamped `0..1`; lower is sooner. |
| 9 | `closest_pass` | Projectile pass-distance or fallback distance | Clamped `0..1`. |
| 10 | `type_norm` | Normalized Lua object/enemy type cue | Clamped `0..1`. |
| 11 | `role_norm` | Object role id | `0.25` projectile, `0.50` danger, `0.75` human, `1.00` electrode. |
| 12 | `destructible` | Target can be killed/shot | `0` or `1`; hulks/humans/electrodes are not marked targetable. |
| 13 | `blocker` | Collision/static blocker cue | `0` or `1`; hulks and electrodes are blockers. |
| 14 | `rescue` | Human/rescue cue | `0` or `1`. |
| 15 | `projectile` | Projectile/missile cue | `0` or `1`. |

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
| `40..279` | 240 | Legacy tactical lanes | Enemy/human density only. |
| `280..765` | 486 | 9x9 tactical grid, 6 channels per cell | Excluded. |
| `766` | 1 | Projectile pool occupancy | Used to build object rows. |
| `767..1030` | 264 | 24 projectile slots * 11 features | Used to build object rows. |
| `1031` | 1 | Danger pool occupancy | Used to build object rows. |
| `1032..1991` | 960 | 96 danger/enemy slots * 10 features | Used to build object rows. |
| `1992` | 1 | Human pool occupancy | Used to build object rows. |
| `1993..2076` | 84 | 12 human slots * 7 features | Used to build object rows. |
| `2077` | 1 | Electrode pool occupancy | Used to build object rows. |
| `2078..2117` | 40 | 8 electrode slots * 5 features | Used to build object rows. |

## Scaling Notes

Robotron object positions are unsigned 8.8 fixed-point values, so one screen
pixel is `256` in the raw coordinate space. Relative X/Y values are normalized
by the playfield width/height and clamped to `-1..1`; distances are normalized
by the playfield diagonal and clamped to `0..1`.

`POS_X_RANGE = (143 - 7) * 256 = 34816`

`POS_Y_RANGE = (234 - 24) * 256 = 53760`

`POS_MAX_DIAG = sqrt(34816^2 + 53760^2) ~= 64022`
