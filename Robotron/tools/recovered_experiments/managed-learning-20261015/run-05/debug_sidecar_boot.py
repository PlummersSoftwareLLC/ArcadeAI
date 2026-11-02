#!/usr/bin/env python3
"""One owned CPU-only diagnostic actor. Never a quality/promotion result."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

ROOT = Path('/home/dave/source/repos/ArcadeAI')
sys.path.insert(0, str(ROOT))
from Robotron.tools import run_frozen_sidecar as sidecar


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--boot-assets', type=Path, required=True)
    parser.add_argument('--checkpoint', type=Path, required=True)
    parser.add_argument('--job-dir', type=Path, required=True)
    parser.add_argument('--seconds', type=float, default=60)
    args = parser.parse_args()
    job = sidecar.Job(args.checkpoint.resolve(), args.job_dir.resolve(), 'boot-diagnostic-only',
                      'cpu', boot_assets=args.boot_assets.resolve())
    job.validate(require_boot_assets=True)
    sidecar.configure_environment(job)
    job.directory.mkdir()
    checkpoint, digest = sidecar.copy_checkpoint(job)
    sys.path.insert(0, str(sidecar.GAME/'Scripts'))
    import torch
    from dqn import config
    from dqn.inference_actor import InferenceActor
    from dqn.socket_server import SocketServer
    from Robotron.tools.build_socket_wait import build
    torch.set_num_threads(2)
    torch.set_num_interop_threads(1)
    actor = InferenceActor(checkpoint, device='cpu')
    metadata = actor.checkpoint_metadata
    for name in ('frame_count','learner_frame_count','measurement_frame_count'):
        setattr(config.metrics, name, metadata[name])
    config.metrics.total_training_steps = actor.training_steps
    config.metrics.total_optimized_samples = actor.optimized_samples
    config.metrics.measurement_active = True
    config.metrics.measurement_generation = 1
    config.metrics.measurement_label = 'boot-diagnostic-only'
    config.metrics.preview_capture_enabled = False
    config.metrics.hud_enabled = False
    config.metrics.training_enabled = False
    for name,value in dict(start_advanced=False,start_level_min=1,epsilon_pct=0,
                           expert_pct=0,auto_curriculum=False,difficulty=5).items():
        setattr(config.game_settings,name,value)
    server = SocketServer('127.0.0.1',9999,actor,replay_enabled=False)
    worker = threading.Thread(target=server.start,daemon=True)
    library = build(job.directory/'socket-wait-build')
    command, environment, private = sidecar.mame_spec(job,4096,library)
    for name in ('cfg','nvram','ini','sta','snap','diff','inp','share','comments'):
        (private/name).mkdir(parents=True)
    boot = sidecar.boot_module().restore_snapshot(job.boot_assets,private)
    lua = job.directory/'diagnostic.lua'
    # Official screen:snapshot API writes only the requested private PNG. It
    # observes frame_done and does not step/reset emulation or inject inputs.
    lua.write_text('dofile('+json.dumps(str(sidecar.GAME/'Scripts/main.lua'))+')\n'+'''
local diagnostic_frame = 0
local diagnostic_screen = manager.machine.screens[":screen"]
diagnostic_snapshot_ref = register_frame_done_callback(function()
    diagnostic_frame = diagnostic_frame + 1
    if diagnostic_frame == 120 or diagnostic_frame == 600 or diagnostic_frame == 1800 then
        local filename = '''+json.dumps(str(job.directory/'screen-'))+''' .. diagnostic_frame .. ".png"
        local ok, result = pcall(function() return diagnostic_screen:snapshot(filename) end)
        print("[BOOT DIAGNOSTIC SNAPSHOT] " .. filename .. " ok=" .. tostring(ok) .. " result=" .. tostring(result))
    end
end)
''')
    command[command.index('-autoboot_script')+1] = str(lua)
    process = None
    observed = []
    result = dict(diagnostic_only=True,quality_result=False,device='cpu',checkpoint_sha256=digest,
                  boot_assets=boot,numeric_policy=actor.numeric_policy,command=command,
                  official_snapshot_api='https://docs.mamedev.org/luascript/ref-devices.html')
    started = time.monotonic()
    with (private/'console.log').open('w') as output:
        try:
            worker.start()
            deadline = time.monotonic()+10
            while not server.running:
                if time.monotonic()>=deadline or not worker.is_alive():
                    raise RuntimeError('diagnostic socket did not bind')
                time.sleep(.02)
            process = subprocess.Popen(command,cwd=private,env=environment,stdin=subprocess.DEVNULL,
                                       stdout=output,stderr=subprocess.STDOUT,close_fds=True,start_new_session=True)
            result['mame_pid'] = process.pid
            result['runner_pid'] = os.getpid()
            print('OWNED_DIAGNOSTIC_PID',process.pid,flush=True)
            healthy_at = None
            while time.monotonic()-started < args.seconds:
                if process.poll() is not None:
                    raise RuntimeError(f'owned MAME exited {process.returncode}')
                if server.inference_only_error or actor.inference_error:
                    raise RuntimeError(server.inference_only_error or actor.inference_error)
                with server.client_lock:
                    states=[{k:cs.get(k)for k in ('client_slot','frames','level_number','game_score','lives','player_alive')}
                            for cs in server.client_states.values()]
                now=time.monotonic()
                observed.append(dict(elapsed_s=now-started,states=states))
                if any(1<=int(cs.get('level_number')or 0)<=40 and int(cs.get('game_score')or 0)>0
                       and 0<=int(cs.get('lives',255))<255 for cs in states):
                    healthy_at=healthy_at or now
                if healthy_at and now-healthy_at>=8:
                    break
                time.sleep(.5)
            result['proper_gameplay_observed']=healthy_at is not None
        except BaseException as error:
            result['error']=f'{type(error).__name__}: {error}'
        finally:
            server.shutdown_event.set()
            if process and process.poll()is None:
                process.terminate()
                try:process.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    process.kill();process.wait(timeout=5)
            server.stop()
            worker.join(timeout=10)
    result.update(observations=observed,elapsed_s=time.monotonic()-started,
                  server_error=server.inference_only_error,inference_error=actor.inference_error,
                  cuda_initialized=torch.cuda.is_initialized(),owned_actor_remaining=bool(process and process.poll()is None),
                  snapshots=[str(p)for p in job.directory.glob('screen-*.png')])
    sidecar.write_json(job.directory/'diagnostic.json',result)
    print(json.dumps({k:result.get(k)for k in ('proper_gameplay_observed','error','elapsed_s','owned_actor_remaining','cuda_initialized')}),flush=True)
    return 0 if result.get('proper_gameplay_observed') and not result.get('error')else 1


if __name__=='__main__':raise SystemExit(main())
