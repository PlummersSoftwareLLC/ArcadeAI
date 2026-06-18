#!/usr/bin/env python3
"""Smoke test for all v3 modules."""

import numpy as np
import sys

def test_config():
    from v3.config import CONFIG, WIRE_PARAMS_COUNT, AUGMENTED_PARAMS_COUNT
    assert WIRE_PARAMS_COUNT == 1454, f"Expected 1454, got {WIRE_PARAMS_COUNT}"
    assert AUGMENTED_PARAMS_COUNT == 1458
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
    assert frame["global_context"].shape == (40,)
    assert frame["move_action_features"].shape == (9, CONFIG.model.action_feature_dim)
    assert frame["fire_action_features"].shape == (9, CONFIG.model.action_feature_dim)
    assert frame["num_entities"] > 0

    T = CONFIG.model.frame_stack
    frames = [proc.process_frame(wire.copy()) for _ in range(T)]
    stacked = proc.stack_frames(frames)
    assert stacked["entity_features"].shape == (T, CONFIG.model.max_entities, CONFIG.model.entity_feature_dim)
    assert stacked["global_context"].shape == (T, 40)
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

    move, fire, lp, entropy, val = net.get_action_and_value(ent, mask, ctx, move_feats, fire_feats)
    assert move.shape == (B,)
    assert fire.shape == (B,)
    assert lp.shape == (B,)
    assert val.shape == (B,)
    print(f"  model: OK ({params:,} params)")

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
    print("  reward: OK")

def test_agent():
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
    print("  agent: OK")

def test_rollout_buffer():
    import torch
    from v3.rollout_buffer import RolloutBuffer

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
    print(f"  rollout_buffer: OK ({len(batches)} batches)")

def test_socket_protocol():
    import struct
    from v3.socket_server import parse_frame_data, encode_action_to_game
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
    test_expert()
    test_reward()
    test_agent()
    test_rollout_buffer()
    test_socket_protocol()
    print("=" * 40)
    print("ALL TESTS PASSED")
