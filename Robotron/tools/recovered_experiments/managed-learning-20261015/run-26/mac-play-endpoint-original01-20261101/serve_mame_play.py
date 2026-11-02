"""Serve a frozen policy to remote MAME without trainer or replay access."""
import argparse,hashlib,importlib.util,json,os
from pathlib import Path
import signal,sys,threading,time
from types import SimpleNamespace

G=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--game-root',type=Path,default=G)
    p.add_argument('--checkpoint',type=Path,required=True)
    p.add_argument('--checkpoint-sha256',required=True)
    p.add_argument('--directory',type=Path,required=True)
    p.add_argument('--port',type=int,default=9999)
    a=p.parse_args();game=a.game_root.resolve()
    assert a.port!=9998 and 1024<=a.port<=65535
    assert os.environ.get('CUDA_VISIBLE_DEVICES')=='' and not os.environ.get('LD_PRELOAD')
    assert a.directory.is_absolute()and not a.directory.exists()
    a.directory.mkdir(mode=0o700)
    def load(name,path):
        s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
    helper=load('_macPlayHelper',game/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    package=helper.pin(game/'tools/quality_capacity_proposal/profile06/runtime-source-package.json')
    assert package['sha256']=='9c9d513328fb8f82427217b2bb2844d73226b3814de34905e28808a93496532e'
    frozen,pins=helper.package_inputs(package)
    policy=helper.pin(a.checkpoint);assert policy['sha256']==a.checkpoint_sha256 and policy['identity']['mode']=='0o444'
    sidecar=load('_macPlayEnvironment',frozen/'tools/run_frozen_sidecar.py')
    sidecar.configure_environment(SimpleNamespace(directory=a.directory,device='cpu',gpu_uuid=None,cpu_threads=2,game_boundary_diagnostics=False,completion_policy='confirmed_reset_reserves_v1'))
    os.environ.update(ROBOTRON_CONTINUOUS_TRAINING_MODE='0',ROBOTRON_ROLLING_TRAINING_CLEANUP='0',ROBOTRON_CONTINUOUS_STARTUP_HOLD='0',ROBOTRON_RETIRE_AFTER_GAME='0')
    sys.path.insert(0,str(frozen/'Scripts'))
    import torch
    torch.set_num_threads(2);torch.set_num_interop_threads(1)
    from dqn import config
    from dqn.inference_actor import InferenceActor
    from dqn.socket_server import SocketServer
    config.RL_CONFIG.inference_batch_max_size=4
    config.RL_CONFIG.eval_epsilon=0.0
    config.metrics.training_enabled=False
    config.metrics.preview_capture_enabled=False
    config.metrics.hud_enabled=False
    for name,value in dict(start_advanced=False,start_level_min=1,epsilon_pct=0,expert_pct=0,auto_curriculum=False,difficulty=5).items():setattr(config.game_settings,name,value)
    actor=InferenceActor(a.checkpoint,device='cpu',inference_backend='eager')
    assert actor.memory is actor.optimizer is None and actor.checkpoint_sha256==a.checkpoint_sha256
    class PlayServer(SocketServer):
        @staticmethod
        def _parse_client_handshake(value):
            preview,slot,role=SocketServer._parse_client_handshake(value)
            if role==2:raise ConnectionError('This play endpoint serves greedy EVAL clients; omit --noeval')
            return preview,slot,1
    server=PlayServer('0.0.0.0',a.port,actor,replay_enabled=False)
    assert server.async_buffer is None and not torch.cuda.is_initialized()
    # Human play remains outside every scientific cohort and promotion path.
    stopped=threading.Event()
    for sig in [signal.SIGINT,signal.SIGTERM]:signal.signal(sig,lambda *_:stopped.set())
    worker=threading.Thread(target=server.start,name='mac-play-listener',daemon=True);worker.start()
    until=time.monotonic()+15
    while not server.running:
        assert worker.is_alive()and time.monotonic()<until,'Play listener did not start'
        time.sleep(.05)
    ready=dict(status='READY_REMOTE_MAME_PLAY',host='0.0.0.0',port=a.port,checkpoint=policy,
        source_package=package,device='cpu',replay_enabled=False,optimizer_created=False,
        CUDA_initialized=False,auto_role_maps_to_eval=True,quality_qualified=False,promotion=False,
        pid=os.getpid(),birth=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]))
    helper.put(a.directory/'ready.json',ready);print(json.dumps(dict(status=ready['status'],port=a.port,checkpoint_sha256=a.checkpoint_sha256)),flush=True)
    try:
        while not stopped.wait(1):
            if not worker.is_alive():raise RuntimeError('Play listener ended')
            if actor.inference_error:raise RuntimeError(actor.inference_error)
    finally:
        server.stop();worker.join(10);actor.close()
    for pin in pins:helper.checked(pin)
    helper.checked(policy)

if __name__=='__main__':main()
