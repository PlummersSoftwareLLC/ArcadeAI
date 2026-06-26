#!/usr/bin/env python3
"""Smoke test for all v3 modules."""

import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

def test_config():
    from v3.config import CONFIG, WIRE_PARAMS_COUNT, AUGMENTED_PARAMS_COUNT
    assert WIRE_PARAMS_COUNT == 2118, f"Expected 2118, got {WIRE_PARAMS_COUNT}"
    assert AUGMENTED_PARAMS_COUNT == WIRE_PARAMS_COUNT + 4
    assert CONFIG.model.max_entities == 140
    assert CONFIG.server.port == 9998
    assert CONFIG.model.num_move_actions == 9
    assert CONFIG.model.num_fire_actions == 9
    print("  config: OK")

def test_state_processor():
    from v3.state_processor import StateProcessor
    from v3.config import CONFIG, WIRE_PARAMS_COUNT

    wire = np.zeros(WIRE_PARAMS_COUNT, dtype=np.float32)
    wire[5] = 0.5
    wire[6] = 0.5
    wire[766] = 1.0
    wire[767] = 1.0
    wire[768] = 0.10
    wire[769] = -0.05
    wire[770] = 0.12

    proc = StateProcessor()
    frame = proc.process_frame(wire)
    assert frame["entity_features"].shape == (CONFIG.model.max_entities, CONFIG.model.entity_feature_dim)
    assert frame["entity_mask"].shape == (CONFIG.model.max_entities,)
    assert frame["global_context"].shape == (CONFIG.model.global_context_dim,)
    assert frame["move_action_features"].shape == (9, CONFIG.model.action_feature_dim)
    assert frame["fire_action_features"].shape == (9, CONFIG.model.action_feature_dim)
    assert frame["num_entities"] > 0

    T = CONFIG.model.frame_stack
    frames = [proc.process_frame(wire.copy()) for _ in range(T)]
    stacked = proc.stack_frames(frames)
    assert stacked["entity_features"].shape == (T, CONFIG.model.max_entities, CONFIG.model.entity_feature_dim)
    assert stacked["global_context"].shape == (T, CONFIG.model.global_context_dim)
    assert stacked["move_action_features"].shape == (T, 9, CONFIG.model.action_feature_dim)
    print("  state_processor: OK")

def test_model():
    import torch
    from v3.model import RobotronPPONet

    net = RobotronPPONet()
    params = sum(p.numel() for p in net.parameters())
    assert params > 0

    from v3.config import CONFIG
    T = CONFIG.model.frame_stack
    B = 4
    N = CONFIG.model.max_entities
    F = CONFIG.model.entity_feature_dim
    G = CONFIG.model.global_context_dim
    AF = CONFIG.model.action_feature_dim
    ent = torch.randn(B, T, N, F)
    mask = torch.ones(B, T, N, dtype=torch.bool)
    mask[:, :, :20] = False
    ctx = torch.randn(B, T, G)
    move_feats = torch.randn(B, T, CONFIG.model.num_move_actions, AF)
    fire_feats = torch.randn(B, T, CONFIG.model.num_fire_actions, AF)

    out = net(ent, mask, ctx, move_feats, fire_feats)
    assert out["move_logits"].shape == (B, 9)
    assert out["fire_logits"].shape == (B, 9)
    assert out["value"].shape == (B,)

    from v3.model import compute_action_features
    move_current, fire_current = compute_action_features(ent[:, -1], mask[:, -1], ctx[:, -1])
    move_bias = net.move_dir_attn._geometry_attention_bias(ent[:, -1], move_current)
    fire_bias = net.fire_dir_attn._geometry_attention_bias(ent[:, -1], fire_current)
    assert move_bias.shape == (B, 9, N)
    assert fire_bias.shape == (B, 9, N)
    assert torch.allclose(move_bias[:, 8], torch.zeros_like(move_bias[:, 8]))
    assert torch.allclose(fire_bias[:, 8], torch.zeros_like(fire_bias[:, 8]))

    move, fire, lp, entropy, val = net.get_action_and_value(ent, mask, ctx, move_feats, fire_feats)
    assert move.shape == (B,)
    assert fire.shape == (B,)
    assert lp.shape == (B,)
    assert val.shape == (B,)
    print(f"  model: OK ({params:,} params)")

def test_action_feature_parity():
    import torch
    from v3.config import CONFIG
    from v3.model import compute_action_features
    from v3.state_processor import (
        build_action_features,
        TYPE_GRUNT,
        TYPE_HULK,
        TYPE_BRAIN,
        TYPE_TANK,
        TYPE_PROJECTILE,
        TYPE_HUMAN,
        TYPE_ELECTRODE,
        TYPE_MISSILE,
        NUM_ENTITY_CLASSES,
    )

    N = CONFIG.model.max_entities
    F = CONFIG.model.entity_feature_dim
    entities = np.zeros((N, F), dtype=np.float32)
    mask = np.ones(N, dtype=bool)
    samples = [
        (TYPE_GRUNT, 0.10, 0.00, 0.20, 0.70),
        (TYPE_HULK, 0.00, 0.10, 0.18, 0.90),
        (TYPE_BRAIN, -0.10, 0.00, 0.25, 0.80),
        (TYPE_TANK, 0.10, 0.10, 0.24, 0.75),
        (TYPE_PROJECTILE, 0.00, -0.08, 0.12, 1.00),
        (TYPE_HUMAN, -0.08, -0.08, 0.18, 0.00),
        (TYPE_ELECTRODE, 0.20, 0.00, 0.30, 0.70),
        (TYPE_MISSILE, -0.12, 0.08, 0.22, 1.00),
    ]
    for i, (tid, dx, dy, dist, threat) in enumerate(samples):
        entities[i, 0] = dx
        entities[i, 1] = dy
        entities[i, 6 + tid] = 1.0
        entities[i, 20] = dist
        entities[i, 24] = 0.35
        entities[i, 26] = threat
        entities[i, 27] = 1.0 if tid != TYPE_HUMAN else 0.0
        entities[i, 28] = 1.0 if tid in {TYPE_PROJECTILE, TYPE_MISSILE} else 0.0
        entities[i, 29] = 1.0 if tid == TYPE_HUMAN else 0.0
        entities[i, 30] = 1.0 if tid in {TYPE_HULK, TYPE_ELECTRODE} else 0.0
        entities[i, 31] = 1.0 if tid != TYPE_HUMAN and tid != TYPE_HULK and tid != TYPE_ELECTRODE else 0.0
        mask[i] = False

    ctx = np.zeros(CONFIG.model.global_context_dim, dtype=np.float32)
    ctx[5] = 0.5
    ctx[6] = 0.5
    cpu_move, cpu_fire = build_action_features(entities, mask, ctx)
    gpu_move, gpu_fire = compute_action_features(
        torch.from_numpy(entities).unsqueeze(0),
        torch.from_numpy(mask).unsqueeze(0),
        torch.from_numpy(ctx).unsqueeze(0),
    )
    np.testing.assert_allclose(gpu_move.squeeze(0).numpy(), cpu_move, rtol=1e-5, atol=1e-5)
    np.testing.assert_allclose(gpu_fire.squeeze(0).numpy(), cpu_fire, rtol=1e-5, atol=1e-5)
    assert cpu_move[:, 12:18].max() > 0.0
    assert cpu_fire[:, 12:18].max() > 0.0
    assert NUM_ENTITY_CLASSES == 12
    print("  action_feature_parity: OK")

def test_expert():
    from v3.expert import get_expert_action
    from v3.config import WIRE_PARAMS_COUNT

    wire = np.random.randn(WIRE_PARAMS_COUNT).astype(np.float32)
    move, fire = get_expert_action(wire)
    assert 0 <= move <= 8
    assert 0 <= fire <= 8
    print("  expert: OK")

def test_reward():
    from v3.reward import RewardShaper

    shaper = RewardShaper()
    r = shaper.shape_simple(100.0, 5.0, False)
    assert r > 0  # positive reward for scoring
    r_death = shaper.shape_simple(0.0, 0.0, True)
    assert r_death < 0  # negative for death
    r_wave2 = shaper.shape(0.0, 0.0, False, True, wave_completed=True, wave_number=2)
    r_wave5 = shaper.shape(0.0, 0.0, False, True, wave_completed=True, wave_number=5)
    assert r_wave5 > r_wave2  # deeper wave clears should be more valuable
    r_kill, c_kill = shaper.shape_with_components(100.0, 0.0, False, True, score_delta=100.0)
    r_rescue, c_rescue = shaper.shape_with_components(1000.0, 0.0, False, True, score_delta=1000.0)
    assert c_kill["human"] == 0.0
    assert c_rescue["human"] > 0.0
    assert r_rescue > r_kill
    # The score component is exempt from the tight ±reward_clip: a big human
    # rescue (and the escalating rescue chain) must rank-order all the way to the
    # 5,000-pt maximum instead of saturating the clip at 2,500. Assert reward is
    # STRICTLY increasing across the rescue tiers so the move head sees the full
    # gradient.
    tiers = [1000.0, 2000.0, 2500.0, 3000.0, 4000.0, 5000.0]
    rewards = [
        shaper.shape_with_components(v, 0.0, False, True, score_delta=v)[0]
        for v in tiers
    ]
    for lo, hi in zip(rewards, rewards[1:]):
        assert hi > lo, f"rescue reward not strictly increasing: {rewards}"
    # Movement potential Φ(s): closing on a human raises Φ (approach reward),
    # with a convex ramp so the FINAL approach is steepest; a close enemy lowers
    # Φ (so moving away = flee reward); dead => 0.
    phi_far = shaper.move_potential(0.9, 1.0, True)
    phi_near = shaper.move_potential(0.1, 1.0, True)
    assert phi_near > phi_far
    # Anchored Φ <= 0 with Φ == 0 at the ideal state (on the human, no enemy
    # near): prevents the (γ-1)·Φ PBRS leak from becoming a constant negative
    # RMove drag.
    assert shaper.move_potential(0.0, 1.0, True, nearest_enemy_dist=1.0) == 0.0
    assert phi_far <= 0.0 and phi_near <= 0.0
    final_approach = shaper.move_potential(0.0, 1.0, True) - shaper.move_potential(0.2, 1.0, True)
    early_approach = shaper.move_potential(0.7, 1.0, True) - shaper.move_potential(0.9, 1.0, True)
    assert final_approach > early_approach  # convex (sharp final approach)
    phi_safe = shaper.move_potential(1.0, 0.0, True, nearest_enemy_dist=1.0)
    phi_danger = shaper.move_potential(1.0, 0.0, True, nearest_enemy_dist=0.02)
    assert phi_danger < phi_safe  # in danger -> negative potential -> fleeing pays
    assert shaper.move_potential(0.1, 1.0, False, 0.02) == 0.0  # dead -> 0
    print("  reward: OK")

def test_agent():
    import torch
    from v3.agent import PPOAgent

    agent = PPOAgent(device="cpu")
    from v3.config import WIRE_PARAMS_COUNT
    wire = np.random.randn(WIRE_PARAMS_COUNT).astype(np.float32)

    move, fire, is_eps = agent.act(wire, epsilon=0.0, client_id=0)
    assert 0 <= move <= 8
    assert 0 <= fire <= 8

    move, fire, lp, val, is_eps, tensors = agent.act_with_value(wire, client_id=1)
    assert 0 <= move <= 8
    assert isinstance(val, float)

    move_target = torch.tensor([0])
    exact_logits = torch.full((1, 9), -4.0)
    adjacent_logits = torch.full((1, 9), -4.0)
    opposite_logits = torch.full((1, 9), -4.0)
    exact_logits[0, 0] = 4.0
    adjacent_logits[0, 1] = 4.0
    opposite_logits[0, 4] = 4.0
    exact_loss = agent._move_bc_loss(exact_logits, move_target)
    adjacent_loss = agent._move_bc_loss(adjacent_logits, move_target)
    opposite_loss = agent._move_bc_loss(opposite_logits, move_target)
    assert exact_loss < adjacent_loss < opposite_loss

    from v3.config import CONFIG
    agent.total_frames = 87_000_000
    # Make the controller deterministic for the hysteresis assertions: no EMA
    # smoothing, immediate flips. Save and restore the globals afterward.
    _saved_alpha = CONFIG.train.guidance_rescue_bc_ema_alpha
    _saved_debounce = CONFIG.train.guidance_rescue_debounce_evals
    try:
        CONFIG.train.guidance_rescue_bc_ema_alpha = 1.0
        CONFIG.train.guidance_rescue_debounce_evals = 1
        agent._guidance_rescue_active = False
        agent._guidance_rescue_bc_fire_ema = None
        agent._guidance_rescue_bc_move_ema = None
        agent._guidance_rescue_pending_count = 0
        # Bad competence -> rescue ON, expert floor raised.
        assert agent.update_guidance_rescue(
            avg_reward=2.0,
            avg_score=12_000,
            avg_ep_len=220,
            bc_fire_loss=2.1972,
            bc_move_loss=1.9,
        )
        assert agent.get_expert_ratio() >= 0.40
        # Partial recovery: score/ep_len recovered but FIRE BC still bad -> stays
        # ON (fire BC is a required recovery signal).
        assert agent.update_guidance_rescue(
            avg_reward=5.0,
            avg_score=50_000,
            avg_ep_len=420,
            bc_fire_loss=1.7,
            bc_move_loss=1.4,
        )
        # Full recovery: score/ep_len/fire recovered. MOVE BC is intentionally
        # NOT a recovery requirement (it is a noisy one-way ratchet), so a still-
        # high BCMv must NOT keep the clamp on -> OFF.
        assert not agent.update_guidance_rescue(
            avg_reward=5.0,
            avg_score=50_000,
            avg_ep_len=420,
            bc_fire_loss=1.1,
            bc_move_loss=1.9,
        )

        # De-bounce: with 3 required evals, a single bad eval must NOT flip the
        # committed state; it only flips after 3 consecutive agreeing evals.
        CONFIG.train.guidance_rescue_bc_ema_alpha = 1.0
        CONFIG.train.guidance_rescue_debounce_evals = 3
        agent._guidance_rescue_active = False
        agent._guidance_rescue_bc_fire_ema = None
        agent._guidance_rescue_bc_move_ema = None
        agent._guidance_rescue_pending_count = 0
        bad = dict(avg_reward=2.0, avg_score=12_000, avg_ep_len=220,
                   bc_fire_loss=2.2, bc_move_loss=1.9)
        assert not agent.update_guidance_rescue(**bad)   # eval 1: still OFF
        assert not agent.update_guidance_rescue(**bad)   # eval 2: still OFF
        assert agent.update_guidance_rescue(**bad)       # eval 3: flips ON
    finally:
        CONFIG.train.guidance_rescue_bc_ema_alpha = _saved_alpha
        CONFIG.train.guidance_rescue_debounce_evals = _saved_debounce
    print("  agent: OK")

def test_rollout_buffer():
    import torch
    from v3.rollout_buffer import RolloutBuffer
    from v3.socket_server import SocketServer

    from v3.config import CONFIG
    T = CONFIG.model.frame_stack
    buf = RolloutBuffer(rollout_length=8, num_actors=2, device=torch.device("cpu"))
    for step in range(8):
        for actor in range(2):
            buf.add(
                actor_id=actor,
                entity_features=torch.randn(T, CONFIG.model.max_entities, CONFIG.model.entity_feature_dim),
                entity_mask=torch.ones(T, CONFIG.model.max_entities, dtype=torch.bool),
                global_context=torch.randn(T, CONFIG.model.global_context_dim),
                move_action_features=torch.randn(T, CONFIG.model.num_move_actions, CONFIG.model.action_feature_dim),
                fire_action_features=torch.randn(T, CONFIG.model.num_fire_actions, CONFIG.model.action_feature_dim),
                move_action=np.random.randint(0, 9),
                fire_action=np.random.randint(0, 9),
                log_prob=-0.5,
                value=1.0,
                has_value=True,
                reward=0.1,
                done=False,
            )
        buf.advance()

    assert buf.ready
    last_values = torch.ones(2)
    buf.compute_gae(last_values)

    batches = list(buf.iterate_minibatches(mini_batch_size=4, num_epochs=2))
    assert len(batches) > 0
    assert "entity_features" in batches[0]
    assert "advantages" in batches[0]

    grouped = RolloutBuffer(rollout_length=4, num_actors=1, device=torch.device("cpu"))
    grouped.values[:, 0] = torch.tensor([1.0, 10.0, 2.0, 20.0])
    grouped.rewards[:, 0] = torch.tensor([1.0, 10.0, 1.0, 10.0])
    grouped.has_value[:, 0] = True
    grouped.dones[:, 0] = torch.tensor([False, False, True, True])
    SocketServer._compute_grouped_advantages(
        grouped,
        client_ids=[0, 1, 0, 1],
        next_values=[2.0, 20.0, 0.0, 0.0],
    )
    assert grouped.advantages[0, 0] > grouped.advantages[2, 0]
    assert grouped.advantages[1, 0] > grouped.advantages[3, 0]

    out_of_order = RolloutBuffer(rollout_length=2, num_actors=1, device=torch.device("cpu"))
    out_of_order.values[:, 0] = torch.tensor([0.0, 0.0])
    out_of_order.rewards[:, 0] = torch.tensor([1.0, 1.0])
    out_of_order.has_value[:, 0] = True
    out_of_order.dones[:, 0] = torch.tensor([True, False])
    SocketServer._compute_grouped_advantages(
        out_of_order,
        client_ids=[0, 0],
        next_values=[0.0, 0.0],
        frame_seqs=[2, 1],
    )
    assert out_of_order.advantages[1, 0] > out_of_order.advantages[0, 0]
    print(f"  rollout_buffer: OK ({len(batches)} batches)")


def test_bc_label_pipeline():
    import torch
    from v3.config import CONFIG
    from v3.rollout_buffer import RolloutBuffer
    from v3.socket_server import _stored_action_label

    assert _stored_action_label({"last_expert_move": 0}, "last_expert_move") == 0
    assert _stored_action_label({"last_expert_fire": 0}, "last_expert_fire") == 0
    assert _stored_action_label({}, "last_expert_move") == 8

    T = CONFIG.model.frame_stack
    buf = RolloutBuffer(rollout_length=1, num_actors=1, device=torch.device("cpu"))
    buf.add(
        actor_id=0,
        entity_features=torch.zeros(T, CONFIG.model.max_entities, CONFIG.model.entity_feature_dim),
        entity_mask=torch.ones(T, CONFIG.model.max_entities, dtype=torch.bool),
        global_context=torch.zeros(T, CONFIG.model.global_context_dim),
        move_action=0,
        fire_action=0,
        log_prob=0.0,
        value=0.0,
        has_value=True,
        reward=0.0,
        done=False,
        expert_move=0,
        expert_fire=0,
        is_expert=True,
        fire_locked=False,
    )
    flat = buf._flatten()
    assert int(flat["expert_move"][0].item()) == 0
    assert int(flat["expert_fire"][0].item()) == 0
    assert bool(flat["is_expert"][0].item())
    print("  bc_label_pipeline: OK")

def test_socket_protocol():
    import struct
    from v3.socket_server import FrameData, _frame_confirms_gameplay, parse_frame_data, encode_action_to_game
    from v3.config import WIRE_PARAMS_COUNT

    # Build a fake binary frame
    n = WIRE_PARAMS_COUNT
    state_data = np.random.randn(n).astype(np.float32)
    header = struct.pack(">HddBIBBBIBB",
        n,        # n_params
        1.5,      # subj_reward
        100.0,    # obj_reward
        0,        # done
        12500,    # score
        1,        # player_alive
        0,        # save
        0,        # start_pressed
        0,        # replay_level
        3,        # num_lasers
        5,        # wave_number
    )
    payload = header + state_data.astype(">f4").tobytes()

    frame = parse_frame_data(payload)
    assert frame is not None
    assert frame.state.shape == (n,)
    assert abs(frame.subjreward - 1.5) < 0.01
    assert abs(frame.objreward - 100.0) < 0.01
    assert frame.player_alive == True
    assert frame.level_number == 5
    assert frame.game_score == 12500

    cs = {"start_pulse_window": 0, "alive_streak": 30, "plausible_start_streak": 0}
    progressed_frame = FrameData(
        state=np.zeros(n, dtype=np.float32),
        subjreward=0.0,
        objreward=0.0,
        done=False,
        player_alive=True,
        save_signal=False,
        start_pressed=False,
        level_number=5,
        game_score=12500,
        next_replay_level=0,
        num_lasers=3,
    )
    assert _frame_confirms_gameplay(cs, progressed_frame)

    # Test action encoding
    m, f = encode_action_to_game(2, 5)
    assert m == 2
    assert f == 5
    m, f = encode_action_to_game(8, 8)  # idle
    assert m == -1
    assert f == -1
    print("  socket_protocol: OK")


if __name__ == "__main__":
    print("Robotron AI v3 — Smoke Tests")
    print("=" * 40)
    test_config()
    test_state_processor()
    test_model()
    test_action_feature_parity()
    test_expert()
    test_reward()
    test_agent()
    test_rollout_buffer()
    test_bc_label_pipeline()
    test_socket_protocol()
    print("=" * 40)
    print("ALL TESTS PASSED")
