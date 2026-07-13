# Robotron DQN State Bag Report

This is the flattened input state used by the DQN model, as produced by
`dqn.config.slice_model_state(wire)`.

Lua sends 1890 big-endian `float32` values per frame. The DQN does not train on
that full payload. It keeps only:

- `wire[0:18]`: 18 scalar core game/player/threat features.
- `wire[18:40]`: 22 raw ELIST/level-state bytes normalized by Lua.
- Four distance-sorted object groups from the Lua state-bag pools:
  64 destructible enemies/projectiles, 16 hulks, 16 obstacles, and 16 humans.

The object geometry is HUD-derived: Lua computes player/object centers from the
same `OBJX`/`OBJY` screen position, parsed sprite non-zero bitmap bounds, and
hitbox anchor offsets used by the local MAME HUD outline renderer. The raw
`OX16`/`OY16` fields are only fallback inputs when a HUD screen coordinate is
unavailable.

## Wire row vs. model token row

The Lua **wire** packs a fixed **10-wide** row per object slot:

```text
[present, dx, dy, dist, vx, vy, threat, approach, ttc, type_norm]
```

The DQN **model token row** is *derived* from that wire row inside
`dqn.config._state_bag_row` and is **18-wide**. The wire format is deliberately
left unchanged so the v3/PPO path and the raw-wire expert are unaffected; all
DQN-side signal-fidelity fixes happen in the Python slice layer:

| Field | Wire (low-resolution) | Model token (high-resolution) |
|---|---|---|
| `dx`,`dy` | `rel/POS_X_RANGE`, `rel/POS_Y_RANGE` (anisotropic) | `rel/POS_MAX_DIAG` — isotropic, so `sqrt(dx^2+dy^2) == dist` |
| `vx`,`vy` | per-frame delta / playfield span (~2-6% of range) | per-frame delta / `VELOCITY_NORM_SCALE` (16 px/frame) |
| `approach` | `2*(v.dir)` with mismatched units | normalized radial closing speed `-(v.unit_dir)` |
| type | ordinal scalar `type_id/8` | categorical **one-hot(9)** |

The ordinal `type_norm` scalar is expanded into a 9-way one-hot; the
trunk/attention `Linear` over the token then learns a proper per-type embedding
instead of being forced onto a false grunt->electrode ordering.

## State size

```text
18 core + 22 ELIST + (112 objects * 18 features) = 2056 floats
```

With the default 1-frame stack, replay/inference state is 2056 floats. The
network trunk does NOT consume all of them directly: distance sorting makes
slot contents churn (an object overtaking another swaps their slots), so only
the slot-stable nearest rows get dedicated first-layer weights. The flat trunk
input is the 40 globals plus the nearest-K rows per group (8 destructible +
4 hulk + 4 obstacle + 4 human = 20 rows × 18 = 360):

```text
flat trunk slice = 40 globals + 360 nearest-K floats = 400 floats
```

The remaining 92 rows reach the trunk only through the permutation-invariant
object-attention digest: per-group masked mean-pools (4 × 128) plus a global
masked max-pool (128), so rare rows (last human, closing projectile) are not
averaged away by 64 destructible slots. Default first trunk width is:

```text
400 flat floats + (4 + 1) * 128 object-attention digest = 1040 floats
```

If `DQN_FRAME_STACK=2` or `ROBOTRON_DQN_FRAME_STACK=2` is set, replay/inference
state becomes 4112 floats, the flat slice becomes 800, and the first trunk
width becomes `800 + 640 = 1440`. The object-attention digest is still computed
from the current frame's object rows.

## DQN Model Layout

| Model index range | Count | Source | Contents |
|---:|---:|---|---|
| `0..17` | 18 | Lua `wire[0:18]` | Core scalar game/player/threat features. |
| `18..39` | 22 | Lua `wire[18:40]` | Raw ELIST/level-state bytes. |
| `40..1191` | 1152 | Lua destructible pool `wire[767:1406]` | 64 nearest destructible enemies/projectiles * 18 features. |
| `1192..1479` | 288 | Lua hulk pool `wire[1408:1567]` | 16 nearest hulks * 18 features. |
| `1480..1767` | 288 | Lua obstacle pool `wire[1569:1728]` | 16 nearest obstacles/electrodes * 18 features. |
| `1768..2055` | 288 | Lua human pool `wire[1730:1889]` | 16 nearest humans * 18 features. |

For object row `R` in `0..111`:

```text
model_index = 40 + (R * 18) + row_offset
```

Rows are distance-sorted within each group. Overflow is ignored: if a wave has
more than 64 destructible objects, only the nearest 64 are represented.

## Row Features (model token, 18-wide)

| Row offset | Name | Source / formula | Range / notes |
|---:|---|---|---|
| 0 | `present` | `1.0` for active slot | Empty rows are all zeros. |
| 1 | `dx` | Relative X (player->object), `rel_dx16 / POS_MAX_DIAG` | Clamped `-1..1`; **isotropic** (same scale as `dy`/`dist`). |
| 2 | `dy` | Relative Y, `rel_dy16 / POS_MAX_DIAG` | Clamped `-1..1`; `sqrt(dx^2+dy^2) == dist`. |
| 3 | `dist` | HUD-box-center distance `dist_world / POS_MAX_DIAG` | Clamped `0..1`; lower is closer. |
| 4 | `vx` | Frame-to-frame delta of relative X, `/ VELOCITY_NORM_SCALE` | Clamped `-1..1`; **closing** (relative) velocity. |
| 5 | `vy` | Frame-to-frame delta of relative Y, `/ VELOCITY_NORM_SCALE` | Clamped `-1..1`; same isotropic scale as `vx`. |
| 6 | `threat` | Lua threat score | Clamped `0..1`. |
| 7 | `approach` | Normalized radial closing speed `-(v . unit_dir_to_player)` | Clamped `-1..1`; positive means approaching. |
| 8 | `ttc` | Time-to-collision estimate | Clamped `0..1`; lower is sooner. |
| 9..17 | `type_onehot` | One-hot of the unified type id (9 classes) | Exactly one `1.0` per active row. |

Type one-hot index (offset within cols `9..17`): `0=grunt`, `1=hulk`, `2=brain`,
`3=tank`, `4=spawner`, `5=enforcer`, `6=projectile`, `7=human`, `8=electrode`.
Decode with `dqn.config.decode_token_types(rows)` (argmax over the one-hot block).

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
| 7 | `player_vel_x` | Delta player X `/ VELOCITY_NORM_SCALE`; clamped `-1..1`; subtractable from object `vx`. |
| 8 | `player_vel_y` | Delta player Y `/ VELOCITY_NORM_SCALE`; clamped `-1..1`. |
| 9 | `nearest_enemy_dist` | Clamped `0..1`; `1.0` if absent. |
| 10 | `nearest_human_dist` | Clamped `0..1`; `1.0` if absent. |
| 11 | `nearest_enemy_dx` | Isotropic (`* POS_X_RANGE/POS_MAX_DIAG`); clamped `-1..1`; `0` if absent. |
| 12 | `nearest_enemy_dy` | Isotropic (`* POS_Y_RANGE/POS_MAX_DIAG`); clamped `-1..1`; `0` if absent. |
| 13 | `human_count_norm` | Clamped `0..1`. |
| 14 | `nearest_spawner_dist` | Clamped `0..1`; `1.0` if absent. |
| 15 | `nearest_spawner_dx` | Isotropic; clamped `-1..1`; `0` if absent. |
| 16 | `nearest_spawner_dy` | Isotropic; clamped `-1..1`; `0` if absent. |
| 17 | `spawner_count_norm` | Clamped `0..1`. |

Core cols `7,8,11,12,15,16` are rescaled DQN-side in `slice_model_state`
(velocity -> per-frame scale, nearest dx/dy -> isotropic) so they match the
object rows. The wire itself is never mutated (a copy is taken).

## Full Lua Wire Layout

These values are still sent by Lua for the expert/debug paths, but are excluded
from the DQN model state unless listed above. Pool rows are **10-wide on the
wire** and expanded to 18-wide model rows by the DQN slice.

| Lua wire range | Count | Contents | DQN use |
|---:|---:|---|---|
| `0..17` | 18 | Core scalar features | Kept (cols 7,8,11,12,15,16 rescaled). |
| `18..39` | 22 | Raw ELIST/level-state bytes | Kept. |
| `40..279` | 240 | Legacy tactical lanes | Excluded. |
| `280..765` | 486 | 9x9 tactical grid, 6 channels per cell | Excluded. |
| `766` | 1 | Destructible pool occupancy | Excluded. |
| `767..1406` | 640 | 64 destructible rows * 10 features | Expanded to model rows `40..1191`. |
| `1407` | 1 | Hulk pool occupancy | Excluded. |
| `1408..1567` | 160 | 16 hulk rows * 10 features | Expanded to model rows `1192..1479`. |
| `1568` | 1 | Obstacle pool occupancy | Excluded. |
| `1569..1728` | 160 | 16 obstacle rows * 10 features | Expanded to model rows `1480..1767`. |
| `1729` | 1 | Human pool occupancy | Excluded. |
| `1730..1889` | 160 | 16 human rows * 10 features | Expanded to model rows `1768..2055`. |

## Scaling Notes

Robotron object positions are unsigned 8.8 fixed-point values, so one screen
pixel is `256` in the raw coordinate space.

`POS_X_RANGE = (143 - 7) * 256 = 34816`

`POS_Y_RANGE = (234 - 24) * 256 = 53760`

`POS_MAX_DIAG = sqrt(34816^2 + 53760^2) ~= 64049`

`VELOCITY_NORM_SCALE = 16 * 256 = 4096` (raw units/frame mapped to `1.0`)

**Position** (`dx`, `dy`) and **distance** share the isotropic diagonal
`POS_MAX_DIAG`, so a diagonal offset is not distorted and `sqrt(dx^2 + dy^2)`
equals `dist`. **Velocity** (`vx`, `vy`, and the core player velocity) is a
*per-frame* delta; the wire divides it by the whole playfield span (crushing real
motion of 1-8 px/frame into ~2-6% of the range), so the DQN recovers the raw
delta and re-normalizes by `VELOCITY_NORM_SCALE`. 16 px/frame maps to `1.0` and
covers all real enemy/projectile motion (Lua treats >32 px/frame as slot reuse
and zeroes it). Because object velocity is *relative* (object minus player) and
the player velocity now uses the same scale, the model can recover absolute
object motion by subtraction.

All of the above transforms are applied in `dqn.config.slice_model_state` /
`_state_bag_row` (DQN-only). The Lua wire and the v3/PPO + expert paths are
unchanged.
