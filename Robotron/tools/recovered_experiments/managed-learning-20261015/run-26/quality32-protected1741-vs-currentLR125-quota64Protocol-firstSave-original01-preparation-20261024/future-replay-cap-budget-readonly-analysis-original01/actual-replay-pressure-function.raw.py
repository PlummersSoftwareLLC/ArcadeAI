def replay_pressure_reached(agent) -> bool:
    """Check the sample clock before doing replay or transfer work.

    Shared by the producer, consumer and final training guard. A bounded
    prefetch may finish in-flight work at the boundary, but must not keep
    sampling batches that the learner will throw away.
    """
    with metrics.lock:
        frames = int(metrics.frame_count)
        loaded_frames = int(getattr(metrics, "loaded_frame_count", 0))
        measured_frames = int(getattr(metrics, 'measurement_frame_count', 0))
        loaded_measured_frames = int(getattr(metrics, 'loaded_measurement_frame_count', 0))
        loaded_steps = int(getattr(agent, "loaded_training_steps", 0))
        loaded_samples = int(getattr(metrics, "loaded_optimized_samples",
                                     loaded_steps * RL_CONFIG.baseline_batch_size))
        steps = int(agent.training_steps)
        optimized_samples = int(getattr(agent, "optimized_samples",
                                        steps * RL_CONFIG.baseline_batch_size))
        memory = getattr(agent, 'memory', None)
        minimum = max(int(getattr(RL_CONFIG, 'min_replay_to_train', 0)),
                      int(getattr(RL_CONFIG, 'batch_size', 0)))
        if memory is not None and len(memory) < minimum:
            # Fresh-data warmup earns no future burst of replay updates. This
            # per-run budget anchor changes no persisted model/schedule clock.
            agent._replay_pressure_anchor = (frames, measured_frames, optimized_samples)
            agent._replay_warmup_pending = True
            return True
        if getattr(agent, '_replay_warmup_pending', False):
            # Seal at the first ready observation, even if collection passed
            # the threshold while a manual training pause suppressed polling.
            agent._replay_pressure_anchor = (frames, measured_frames, optimized_samples)
            agent._replay_warmup_pending = False
        anchor = getattr(agent, '_replay_pressure_anchor', None)
        if anchor is not None:
            loaded_frames, loaded_measured_frames, loaded_samples = anchor
    limit = float(getattr(RL_CONFIG, "max_samples_per_frame", 0.0))
    if limit <= 0.0 or frames <= 0:
        return False
    samples = max(0, optimized_samples - loaded_samples)
    learning_frames = frames - loaded_frames - max(0, measured_frames - loaded_measured_frames)
    return samples / max(1, learning_frames) >= limit