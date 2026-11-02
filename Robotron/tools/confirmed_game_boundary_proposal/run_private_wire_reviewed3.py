"""Private actual binary parser/client-handler validation, never a live listener."""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
GAME=HERE.parents[1]


def require(value,message):
    if not value:raise AssertionError(message)


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def publish(path,value):
    with path.open('x') as f:
        json.dump(value,f,indent=2,allow_nan=False);f.write('\n');f.flush()
        os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())


def prepare(work):
    work.mkdir(mode=0o700)
    package=work/'private/Scripts/dqn';package.mkdir(parents=True)
    files={p.name:p.read_bytes() for p in (GAME/'Scripts/dqn').glob('*.py')
           if not p.name.startswith('test_')}
    require(len(files)<=64 and sum(map(len,files.values()))<4<<20,'Private source-copy budget')
    candidate=HERE/'game_journal_candidate_reviewed3.py'
    require(sha(candidate)=='3b8dc9ecf592cdb868443e9c1b21cde3ef398ac0a79a2d00c1c70a811bdeb90e',
            'Selected private proposal changed')
    files['game_journal.py']=candidate.read_bytes()
    for name,raw in files.items():(package/name).write_bytes(raw)
    helper=GAME/'tools/game_boundary_diagnostics_proposal/wire_integration_validation/test_wire_integration.py'
    (work/'private_wire_helper.py').write_bytes(helper.read_bytes())
    for name in ('models','control','cache','journal'):(work/name).mkdir()
    (work/'models/game_settings.json').write_text('{}\n')
    (work/'control/learning_control.json').write_text('{}\n')
    manifest=dict(schema='robotron-private-confirmed-wire-input-v1',
        package_hashes={name:hashlib.sha256(raw).hexdigest() for name,raw in files.items()},
        source_bytes=sum(map(len,files.values())),helper_sha256=sha(helper),
        installed_sources={str(p):sha(p) for p in (GAME/'Scripts/dqn').glob('*.py')
                           if not p.name.startswith('test_')},
        scope='Exact installed private numerical/parser/handler copy; only GameJournal replaced by selected optional-policy proposal.')
    publish(work/'input.json',manifest)
    return manifest


def specs(case):
    def f(score=0,wave=1,alive=True,done=False,lives=3,reserves=2,start=False):
        return dict(score=score,wave=wave,alive=alive,done=done,lives=lives,reserves=reserves,start=start)
    begin=[f(20000,2),f(0,1,False,reserves=3,start=True),f()]
    if case=='truncated_nonzero':
        rows=list(begin)
        def grow(start,end):
            for score in range(start+5000,end,5000):rows.append(f(score,max(1,score//25000+1)))
            rows.append(f(end,max(1,end//25000+1)))
        grow(0,459825);rows.append(f(459825,19,False,True,0,1))
        grow(459825,739300)
        rows.extend([f(739300,30,False,lives=0,reserves=0),
                     f(0,0,False,reserves=3,start=True),f()])
        return rows
    rows=list(begin)
    for reserve in (1,0,0):
        rows.extend([f(alive=False,done=True,lives=0,reserves=reserve),
                     f(lives=0,reserves=reserve)])
    rows.append(f(alive=False,lives=0,reserves=0,start=True))
    if case=='zero_real_restart':rows.extend([f(alive=False,reserves=3),f(reserves=2)])
    elif case!='zero_no_restart':raise ValueError(case)
    return rows


def child(work):
    import numpy as np
    sys.path.insert(0,str(HERE))
    from confirmed_terminal_evidence import collect_successors
    sys.path.insert(0,str(work/'private/Scripts'))
    from dqn import socket_server as module, config
    config.RL_CONFIG.inference_batch_max_size = 16
    manifest=json.loads((work/'input.json').read_text())
    require(all(sha(work/'private/Scripts/dqn'/name)==digest for name,digest in manifest['package_hashes'].items()),
            'Private package changed')
    spec=importlib.util.spec_from_file_location('_confirmed_wire_memory_carrier',work/'private_wire_helper.py')
    helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    reports=[]
    for case in ('truncated_nonzero','zero_real_restart','zero_no_restart'):
        prior=None
        for mode in ('wire_lives_v1','confirmed_reset_reserves_v1'):
            directory=work/'journal'/(case+'-'+mode)
            os.environ['ROBOTRON_RUN_DIR']=str(directory)
            os.environ['ROBOTRON_GAME_COMPLETION_POLICY']=mode
            os.environ['ROBOTRON_GAME_BOUNDARY_DIAGNOSTICS']='1'
            metrics=config.MetricsData();config.metrics=module.metrics=metrics
            for key,value in dict(measurement_active=True,measurement_generation=1,
                measurement_label='confirmed-wire-fixture',frame_count=2000,learner_frame_count=1000,
                measurement_frame_count=1000,total_training_steps=7,total_optimized_samples=3584,
                training_enabled=False,ratchet_frozen=False,preview_capture_enabled=False,hud_enabled=False).items():
                setattr(metrics,key,value)
            class Actor:
                optimized_samples,training_steps=3584,7
                def __init__(self):self.calls=[]
                @property
                def memory(self):raise AssertionError('Inference-only handler touched replay')
                def act(self,state,epsilon,locked_fire=None):
                    require(state.shape==(config.RL_CONFIG.state_size,) and np.isfinite(state).all(),'Actual decoded state invalid')
                    require(epsilon==0.,'Frozen epsilon changed')
                    self.calls.append(hashlib.sha256(state.tobytes()).hexdigest());return 8,8,False
                def act_batch(self,states,epsilons,locked_fires=None):
                    locked_fires=locked_fires or [None]*len(states)
                    return [self.act(state,epsilon,locked_fire=locked)
                            for state,epsilon,locked in zip(states,epsilons,locked_fires)]
                def step(self,*a,**k):raise AssertionError('No replay/training action permitted')
            actor=Actor();server=module.SocketServer('private-confirmed-wire',0,actor,replay_enabled=False)
            require(server.server_socket is server.async_buffer is None and server.inference_batcher is not None
                    and server.inference_batcher.max_batch_size==16,'Private no-listener/batched profile differs')
            require(server.game_journal.completion_policy==mode,'Explicit completion mode not bound')
            server.running=True;server._init_client(7)
            rows=specs(case);state=np.zeros(module.WIRE_PARAMS_COUNT,dtype='>f4').tobytes()
            wire=bytearray(struct.pack('>H',(1<<14)|(4097<<1)))
            for row in rows:
                payload=struct.pack(module._HDR_FMT_V2,module.WIRE_PARAMS_COUNT,0.,0.,
                    int(row['done']),row['score'],int(row['alive']),0,int(row['start']),
                    20000,row['reserves'],row['wave'],row['lives'])+state
                wire.extend(struct.pack('>I',len(payload))+payload)
            connection=helper.MemoryWire(server,bytes(wire))
            timer=type('NoTimer',(),{'start':lambda self:None})()
            try:
                with patch.object(module.select,'select',side_effect=connection.ready), \
                     patch.object(module.threading,'Timer',return_value=timer), \
                     patch.object(module.socket,'socket',side_effect=AssertionError('No real listener allowed')):
                    server.handle_client(connection,7)
            finally:
                server.inference_batcher.stop()
            require(not server.inference_batcher._thread.is_alive(),'Owned actual batcher did not stop')
            require(server.inference_only_error is None,'Whole actual handler failed: '+str(server.inference_only_error))
            require(connection.offset==len(wire) and connection.closed and connection.shutdown_called,'Whole handler/EOF cleanup failed')
            require(len(connection.actions)==len(rows),'Action/accepted frame count differs')
            require(metrics.learner_frame_count==1000 and metrics.total_training_steps==7
                    and metrics.total_optimized_samples==3584,'Frozen learner clocks advanced')
            games=[json.loads(x) for x in (directory/'games.jsonl').read_text().splitlines()]
            completed=[x for x in games if x['known_start'] and x['eligible']]
            expected=(459825 if mode=='wire_lives_v1' else 739300) if case=='truncated_nonzero' else 0
            expected_count=0 if case=='zero_no_restart' and mode=='confirmed_reset_reserves_v1' else 1
            require(len(completed)==expected_count,'Unexpected complete-game count')
            if completed:require(completed[0]['score']==expected,'Terminal score differs')
            if mode=='confirmed_reset_reserves_v1':
                require(all(x['completion_policy']==mode and x['terminal_confirmation'] is not None for x in completed),
                        'Completion lacks actual selected-policy confirmation')
                starts=[json.loads(x) for x in (directory/'measurement_starts.jsonl').read_text().splitlines()]
                successors=collect_successors(completed,games,starts)
                require(len(successors)==len(completed),'Original successor evidence incomplete')
                if case=='zero_real_restart':
                    proof=completed[0]['terminal_confirmation']
                    require(proof['previous_raw_reserves']==0 and proof['next_raw_reserves']==3,
                            'Actual binary num_lasers reserve field was not preserved')
            actual=dict(actions=[x.hex() for x in connection.actions],state_hashes=actor.calls,
                frames=metrics.frame_count,measurement_frames=metrics.measurement_frame_count)
            if prior is not None:require(actual==prior,'Journal policy changed actor inputs/actions/frame accounting')
            prior=actual
            reports.append(dict(case=case,mode=mode,frames=len(rows),actor_calls=len(actor.calls),
                completed=len(completed),scores=[x['score'] for x in completed],
                journal=str(directory),actual_parser_handler=True,actual_async_batcher=True,real_socket=False,replay_access=False))
    publish(work/'child-result.json',dict(status='PASS',cases=reports,
        scope='Actual binary parser, full inference-only handler, actual async batcher16, state stack and journals; synthetic descriptor-free carrier. No MAME/model/GPU/training.',
        installed_sources_changed=False,quality_qualification=False,promotion=False))
    return 0


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true');parser.add_argument('--child',action='store_true')
    parser.add_argument('--work',type=Path,required=True)
    args=parser.parse_args()
    if args.child:return child(args.work)
    if not args.execute:
        print('PLAN_ONLY: no reads, outputs, imports or actions');return 0
    manifest=prepare(args.work)
    env={k:v for k,v in os.environ.items() if not k.startswith(('DQN_','ROBOTRON_')) and k not in ('LD_PRELOAD','PYTHONPATH')}
    env.update(CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1',ROBOTRON_DQN_MODEL_DIR=str(args.work/'models'),
        ROBOTRON_DQN_CONTROL_PATH=str(args.work/'control/learning_control.json'),ROBOTRON_RUN_DIR=str(args.work/'journal'),
        DQN_FRAME_STACK='4',DQN_LEARNING_EXPOSURE_COUNTERS='0',DQN_NATIVE_BATCH_UPDATE='0',
        OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',NUMEXPR_NUM_THREADS='2',
        XDG_CACHE_HOME=str(args.work/'cache'),TORCH_HOME=str(args.work/'cache/torch'),
        TORCHINDUCTOR_CACHE_DIR=str(args.work/'cache/inductor'),TRITON_CACHE_DIR=str(args.work/'cache/triton'),
        TORCH_EXTENSIONS_DIR=str(args.work/'cache/extensions'),CUDA_CACHE_PATH=str(args.work/'cache/cuda'))
    argv=[str(GAME.parent/'.venv-gb300/bin/python'),'-Xgil=0','-I','-B',str(Path(__file__).resolve()),'--child','--work',str(args.work)]
    with (args.work/'child.stdout.txt').open('x') as stdout,(args.work/'child.stderr.txt').open('x') as stderr:
        result=subprocess.run(argv,env=env,stdout=stdout,stderr=stderr,timeout=130)
    for name in ('child.stdout.txt','child.stderr.txt'):(args.work/name).chmod(0o444)
    require(all(sha(path)==digest for path,digest in manifest['installed_sources'].items()),'Installed source changed')
    require(result.returncode==0,'Original numerical wire child failed; preserve without retry')
    report=json.loads((args.work/'child-result.json').read_text());require(report['status']=='PASS','Wire child did not pass')
    publish(args.work/'result.json',dict(status='PASS',child_exit=result.returncode,
        manifest=manifest,cases=report['cases'],actual_MAME=False,actual_model=False,actual_GPU=False,
        scope=report['scope'],installed_source_changed=False,qualification=False,promotion=False))
    print(json.dumps(dict(status='PASS',child_exit=result.returncode,cases=report['cases']),indent=2));return 0


if __name__=='__main__':raise SystemExit(main())
