#!/usr/bin/env python3
"""Separate CPU-only practice listener; cannot write training replay or weights."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import sys
import threading
import time


def serve(checkpoint, directory):
    root = Path(__file__).resolve().parents[1]
    assert checkpoint.is_file() and checkpoint.stat().st_mode & 0o222 == 0
    directory.mkdir(parents=True, exist_ok=True)
    os.environ.update(CUDA_VISIBLE_DEVICES='', ROBOTRON_DQN_MODEL_DIR=str(directory/'isolated-models'),
        ROBOTRON_DQN_CONTROL_PATH=str(directory/'isolated-control.json'),
        ROBOTRON_RUN_DIR=str(directory/'journal'), ROBOTRON_RETIRE_AFTER_GAME='0',
        OMP_NUM_THREADS='2', MKL_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2')
    os.environ.pop('LD_PRELOAD', None)
    sys.path.insert(0,str(root/'Scripts'))
    import torch
    from dqn.config import metrics, game_settings
    from dqn.inference_actor import InferenceActor
    from dqn.managed_measurement import ManagedMeasurement
    from dqn.socket_server import SocketServer
    torch.set_num_threads(2)
    torch.set_num_interop_threads(1)
    actor = InferenceActor(checkpoint, device='cpu')
    metrics.training_enabled = False
    metrics.preview_capture_enabled = False
    metrics.hud_enabled = False
    for key,value in dict(start_advanced=False,start_level_min=1,auto_curriculum=False,
                          epsilon_pct=0,expert_pct=0,difficulty=5).items():
        setattr(game_settings,key,value)

    class PracticeServer(SocketServer):
        @staticmethod
        def _parse_client_handshake(value):
            preview,slot,mode=SocketServer._parse_client_handshake(value)
            if mode not in (0,1,2):
                raise ValueError('Unknown practice client mode')
            # Practice is always greedy and read-only, including clients that
            # would normally request training on the production listener.
            return preview,slot,1

        def _is_eval_client(self,cid):
            return True

        @staticmethod
        def _actor_controls(cs):
            return 0.0,0.0,'measurement'

    server = PracticeServer('0.0.0.0',9997,actor,replay_enabled=False)
    assert server.async_buffer is None and actor.memory is actor.optimizer is None
    assert not server.game_journal.retire_after_game
    # Use the existing policy-lock lifecycle required by inference-only
    # serving. Practice never opens or qualifies a scored evaluation cohort.
    controller=ManagedMeasurement(actor,metrics,server.game_journal,
        boundary_status=lambda generation: server.measurement_boundary_status(generation))
    controller.enter('practice-only-not-a-quality-cohort',cohort_s=86400,timeout_s=86460)
    initial_clocks=(metrics.total_training_steps,metrics.total_optimized_samples,metrics.learner_frame_count)
    stopped=threading.Event()
    for sig in [signal.SIGTERM,signal.SIGINT]:
        signal.signal(sig,lambda *_:stopped.set())
    thread=threading.Thread(target=server.start,name='practice-listener',daemon=True)
    thread.start()
    try:
        while not stopped.wait(1):
            assert thread.is_alive() and server.inference_only_error is None
            assert actor.memory is actor.optimizer is None and not actor.training_enabled
            assert not torch.cuda.is_initialized()
            assert (metrics.total_training_steps,metrics.total_optimized_samples,metrics.learner_frame_count)==initial_clocks
            status=dict(state='ready',port=9997,device='cpu',client_rows=server.get_client_rows(),
                snapshot_sha256=actor.checkpoint_sha256,checkpoint_metadata=actor.checkpoint_metadata,
                training_enabled=False,replay_enabled=False,optimizer_created=False,frozen_policy_mode=True,
                preview_capture_enabled=False,quality_qualified=False,updated_unix_s=time.time())
            temporary=directory/'status.json.tmp'
            with temporary.open('w')as stream:
                json.dump(status,stream,indent=2);stream.flush();os.fsync(stream.fileno())
            os.replace(temporary,directory/'status.json')
    finally:
        server.stop()
        thread.join(timeout=10)
        controller.exit()
        actor.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint',type=Path,required=True)
    parser.add_argument('--run-dir',type=Path,required=True)
    parser.add_argument('--serve',action='store_true')
    args=parser.parse_args()
    if args.serve:
        serve(args.checkpoint.resolve(strict=True),args.run_dir.resolve())
    else:
        print('PLAN_ONLY: no model, listener or files created')
