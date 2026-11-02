"""Isolated real-MAME boundary validation; never a policy qualification cohort.

Two journals observe the same accepted frames. The proposed confirmed scorer
is the measurement observer; the legacy scorer is a diagnostic control only.
Only this process's private fleet is stopped. Installed source/training stay put.
"""
import argparse
from collections import Counter
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.request

GAME=Path('/home/dave/source/repos/ArcadeAI/Robotron')
MODE='confirmed_reset_reserves_v1'


def require(value,message):
    if not value:raise ValueError(message)


def digest(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module


def write(path,value,replace=False):
    target=path.with_suffix(path.suffix+'.writing') if replace else path
    with target.open('x') as stream:
        json.dump(value,stream,indent=2,allow_nan=False);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    if replace:os.replace(target,path)


def process_start(pid):
    try:return int((Path('/proc')/str(pid)/'stat').read_text().rsplit(')',1)[1].split()[19])
    except (FileNotFoundError,ProcessLookupError):return None


def main_health(job):
    require(process_start(job['main_owner']['pid'])==job['main_owner']['starttime_ticks'], 'Original main owner changed')
    raw=urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=5).read();api=json.loads(raw)
    require(api['client_count']==192 and api['memory_buffer_size']==6000000
            and api['training_enabled'] is True and api['lr']==1.25e-5,'Held main192 recipe changed')
    require(0<=time.time()-api['ts']<=5 and 0<=api['pipeline_snapshot_age_s']<=5,'Stale main health')
    require(api['host_pipeline']['learning_exposure']['optimizer']['process_id']==job['main_owner']['pid'], 'API main owner differs')
    require(all(api['host_pipeline'][k]['errors']==0 for k in ('inference','actor_refresh','target_refresh','learner_priority'))
            and api['bank_persistence']['write_failures']==0,'Main pipeline/bank error')
    return dict(pid=job['main_owner']['pid'],clients=192,frames=api['learner_frame_count'],
                steps=api['training_steps'],errors=0,observed_unix_s=time.time())


class JournalTee:
    def __init__(self,primary,legacy,path):
        self.primary,self.legacy,self.path=primary,legacy,path
        self.guard=threading.Lock();self.previous={};self.confirmations=[];self.errors=[]

    def __getattr__(self,key):return getattr(self.primary,key)

    def observe(self,cid,frame,cs,*,new_game=False,context,boundary_inputs=None):
        with self.guard:
            before=self.primary.active.get(cid)
            self.primary.observe(cid,frame,cs,new_game=new_game,context=context,boundary_inputs=boundary_inputs)
            self.legacy.observe(cid,frame,cs,new_game=new_game,context=context,boundary_inputs=boundary_inputs)
            signature=(int(frame.num_lasers),int(frame.lives),bool(frame.player_alive),
                       bool(frame.done),bool(frame.start_pressed),int(frame.level_number))
            event=dict(unix_s=time.time(),cid=cid,slot=cs['client_slot'],game_uid=cs['game_uid'],
                score=int(frame.game_score),wave=int(frame.level_number),raw_reserves=int(frame.num_lasers),
                estimated_wire_lives=int(frame.lives),alive=bool(frame.player_alive),done=bool(frame.done),
                start_pressed=bool(frame.start_pressed),classifier_new_game=bool(new_game))
            if before is not None and before['result'] is not None and before['result']['complete']:
                row=before['result']
                if row['journal_game_id'] not in {x['journal_game_id'] for x in self.confirmations}:
                    confirmation=row['terminal_confirmation']
                    try:
                        require(confirmation is not None and row['completion_policy']==MODE,'Missing actual completion policy')
                        if confirmation['reason']=='zero_score_restart':
                            require(row['score']==0 and confirmation['previous_raw_reserves']==0
                                    and 0<confirmation['next_raw_reserves']<255
                                    and confirmation['restart_pulse'],'Invalid real zero-reserve restart')
                        else:
                            require(new_game and boundary_inputs is not None,'Nonzero terminal lacks actual classifier reset')
                            require(row['score']%100000000==int(boundary_inputs[2]),'Confirmed terminal differs from last accepted classifier baseline')
                        self.confirmations.append(dict(journal_game_id=row['journal_game_id'],slot=row['client_slot'],
                            game_uid=row['game_uid'],known_start=row['known_start'],eligible=row['eligible'],
                            score=row['score'],confirmation=confirmation))
                        event['confirmed_terminal']=row['journal_game_id']
                    except BaseException as error:
                        self.errors.append(repr(error));raise
            if signature!=self.previous.get(cid) or new_game or 'confirmed_terminal' in event:
                with self.path.open('a') as stream:stream.write(json.dumps(event,separators=(',',':'))+'\n')
            self.previous[cid]=signature

    def disconnect(self,cid,context):
        with self.guard:
            self.primary.disconnect(cid,context);self.legacy.disconnect(cid,context)

    def policy_boundary(self,cid,context):
        with self.guard:
            self.primary.policy_boundary(cid,context);self.legacy.policy_boundary(cid,context)

    def progress(self,kind):
        with self.guard:
            rows=[dict(x) for x in self.primary.completed if x['known_start'] and x['eligible']]
            slots=Counter(row['client_slot'] for row in rows)
            zero=[row for row in rows if row['score']==0]
            retained=[]
            for row in rows:
                old=next((x for x in self.legacy.completed if x['client_slot']==row['client_slot']
                          and x['game_uid']==row['game_uid'] and x['known_start'] and x['eligible']),None)
                if row['score']>0 and old is not None and row['score']>old['score']:
                    retained.append(dict(slot=row['client_slot'],game_uid=row['game_uid'],
                        legacy_prefix_score=old['score'],confirmed_score=row['score']))
            ready=set(slots)==set(range(4096,4112)) and not self.errors
            if kind=='neutral':ready=ready and len(zero)>=2 and len({x['client_slot'] for x in zero})>=2
            else:ready=ready and sum(x['score']>0 for x in rows)>=16 and bool(retained)
            return dict(checks_met=ready,completed=len(rows),completed_slot_counts=dict(slots),
                zero_completed=len(zero),zero_slots=sorted({x['client_slot'] for x in zero}),
                retained_full_scores=retained,confirmed_terminals=len(self.confirmations),errors=list(self.errors))


def run(job):
    output=Path(job['output']);output.mkdir(mode=0o700)
    lease=os.open('/dev/shm/robotron-snapshot-smoke-gpu0.lock',os.O_RDWR|os.O_CREAT,0o600)
    fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
    stopped=threading.Event();prior={s:signal.signal(s,lambda *_:stopped.set()) for s in (signal.SIGINT,signal.SIGTERM)}
    server=fleet=worker=controller=actor=tee=None;failure=None;cleanup=[];timeouts=None
    started=time.monotonic();progress={};actors={};main_before=None;backend={}
    try:
        for entry in job['pins']:require(digest(entry['path'])==entry['sha256'],'Selected source/evidence changed')
        main_before=main_health(job)
        probe=socket.socket();probe.bind(('127.0.0.1',9999));probe.close()
        gpu=subprocess.check_output(['nvidia-smi','--query-gpu=uuid,memory.free','--format=csv,noheader,nounits'],text=True)
        require(int(next(x for x in gpu.splitlines() if job['gpu_uuid'] in x).split(',')[1])>=14336,'GPU0 free-memory preflight')
        compute=subprocess.check_output(['nvidia-smi','--query-compute-apps=gpu_uuid,pid','--format=csv,noheader'],text=True)
        require(job['gpu_uuid'] not in compute,'Another GPU0 compute owner is present')
        require(digest(job['reference']['path'])==job['reference']['sha256'],'Protected reference changed')
        sys.path.insert(0,str(GAME/'tools'))
        import run_frozen_sidecar as frozen
        selected=frozen.Job(Path(job['reference']['path']),output,'confirmed-boundary-'+job['kind']+'-validation',
            'cuda',job['gpu_uuid'],9999,job['max_wall_s']-30,job['max_wall_s'],1000,
            Path('/usr/games/mame'),GAME/'roms',2,Path(job['boot_assets']),'inductor',game_boundary_diagnostics=True)
        # Directory is owned/new here; Job's output-exists rule belongs to the
        # production cohort launcher, which this validation does not call.
        boot=frozen.boot_module().load_snapshot(selected.boot_assets)
        frozen.configure_environment(selected)
        checkpoint,identity=frozen.copy_checkpoint(selected);signature=frozen.checkpoint_identity(checkpoint)
        import torch
        sys.path.insert(0,str(GAME/'Scripts'))
        from dqn import config
        from dqn.inference_actor import InferenceActor
        from dqn.socket_server import SocketServer
        from dqn.managed_measurement import ManagedMeasurement
        candidate=load('_selected_confirmed_journal_validation',Path(job['candidate']['path']))
        torch.set_num_threads(2);torch.set_num_interop_threads(1)
        config.RL_CONFIG.inference_batch_max_size=16
        actor=frozen.build_inference_actor(InferenceActor,checkpoint,selected)
        neutral_calls=[0]
        if job['kind']=='neutral':
            def neutral_batch(states,epsilons,locked_fires=None):
                require(all(e==0 for e in epsilons),'Neutral validation epsilon changed')
                neutral_calls[0]+=len(states)
                return [(8,8,False) for _ in states]
            actor.act_batch=neutral_batch
        metadata=dict(actor.checkpoint_metadata)
        for name in ('learner_frame_count','frame_count','measurement_frame_count'):
            setattr(config.metrics,name,int(metadata[name]))
        config.metrics.total_training_steps=actor.training_steps
        config.metrics.total_optimized_samples=actor.optimized_samples
        config.metrics.training_enabled=False;config.metrics.preview_capture_enabled=False;config.metrics.hud_enabled=False
        for name,value in dict(start_advanced=False,start_level_min=1,epsilon_pct=0,expert_pct=0,
                               auto_curriculum=False,difficulty=5).items():setattr(config.game_settings,name,value)
        library=__import__('build_socket_wait').build(output/'socket-wait-build')
        server=SocketServer('127.0.0.1',9999,actor,replay_enabled=False)
        require(server.async_buffer is None and server.inference_batcher is not None
                and server.inference_batcher.max_batch_size==16 and server.game_boundary_diagnostics,
                'Actual private inference-only/batched/diagnostic profile differs')
        primary=candidate.GameJournal(output/'confirmed-journal',completion_policy=MODE)
        legacy=candidate.GameJournal(output/'legacy-control-journal',completion_policy='wire_lives_v1')
        tee=JournalTee(primary,legacy,output/'wire-boundary-events.jsonl');server.game_journal=tee
        controller=ManagedMeasurement(actor,config.metrics,tee,
            boundary_status=lambda generation:frozen.fixed_boundary(server,generation))
        fleet=frozen.PrivateFleet(selected,library,expected_boot_identity=boot['identity'])
        worker=threading.Thread(target=server.start,name='confirmed-validation-server',daemon=True)
        write(output/'plan.json',dict(schema='robotron-real-MAME-boundary-validation-plan-v1',
            selected_job=job,private_backend=selected.plan(),checkpoint_sha256=identity,
            effective_completion_policy=MODE,candidate_source_sha256=digest(job['candidate']['path']),
            action_policy='fixed_neutral_after_standard_model_warmup' if job['kind']=='neutral' else 'protected845_greedy',
            validation_only=True,quality_qualification=False,promotion=False))
        controller.enter(selected.label,cohort_s=selected.cohort_s,timeout_s=selected.timeout_s)
        worker.start();deadline=time.monotonic()+15
        while not server.running:
            require(worker.is_alive() and time.monotonic()<deadline,'Private listener did not become live');time.sleep(.02)
        fleet.launch()
        actors={str(slot):dict(pid=p.pid,starttime_ticks=process_start(p.pid)) for slot,p in fleet.processes.items()}
        write(output/'original-actors.json',actors)
        require(len(actors)==16,'Expected private16 actors')
        last_health=0
        while True:
            require(not stopped.is_set(),'Original validation interrupted')
            require(time.monotonic()-started<job['max_wall_s'],'Precommitted validation deadline expired; no retry')
            frozen.check_protocol(config,actor,signature,checkpoint)
            require(not server.inference_only_error and not tee.errors,'Private inference/journal failure')
            require(not fleet.exited(),'An owned MAME exited')
            state=controller.tick()
            require(not state['complete'] or state.get('valid') is True,'Validation controller failed')
            if state['phase']!='warming':require(frozen.fixed_boundary(server,controller.generation)['ready'],'Private16 boundary changed')
            if time.monotonic()-last_health>=5:
                current_main=main_health(job);last_health=time.monotonic()
            progress=tee.progress(job['kind'])
            write(output/'status.json',dict(state='observing_validation',elapsed_s=time.monotonic()-started,
                kind=job['kind'],progress=progress,actor_pids=actors,main=current_main,
                actual_policy=MODE,qualification=False,promotion=False),replace=True)
            if progress['checks_met']:
                backend=fleet.backend_evidence()
                require(len(backend)==16 and all(x['matching_activation'] for x in backend.values()),
                        'Actual owned socket-wait backend not verified for all16')
                break
            time.sleep(.25)
    except BaseException as error:
        failure=repr(error)
    finally:
        if server is not None and fleet is not None and worker is not None and controller is not None:
            timeouts,cleanup=frozen.cleanup_with_timeout_evidence(fleet,server,worker,controller,prior)
        elif server is not None:
            server.shutdown_event.set();server.stop()
        for signum,handler in prior.items():signal.signal(signum,handler)
        fcntl.flock(lease,fcntl.LOCK_UN);os.close(lease)
    source_unchanged=all(digest(entry['path'])==entry['sha256'] for entry in job['pins'])
    try:final_main=main_health(job)
    except BaseException as error:
        final_main=dict(error=repr(error))
        failure=failure or 'Final main health unavailable: '+repr(error)
    require(all(process_start(a['pid'])!=a['starttime_ticks'] for a in actors.values()),'Owned actor still live after cleanup')
    runtime_timeouts=(timeouts or {}).get('actor_timeout_logs',{})
    passed=(failure is None and not cleanup and source_unchanged and len(runtime_timeouts)==16
            and not any(runtime_timeouts.values()) and progress.get('checks_met') is True)
    write(output/'result.json',dict(schema='robotron-real-MAME-boundary-validation-result-v1',
        status='PASS' if passed else 'FAIL_PRESERVED',kind=job['kind'],error=failure,cleanup_errors=cleanup,
        progress=progress,timeout_evidence=timeouts,source_unchanged=source_unchanged,
        socket_wait_backend=backend,
        main_before=main_before,main_after=final_main,actors=actors,owned_actors_absent=True,
        candidate_source=job['candidate'],neutral_action_calls=neutral_calls[0] if actor is not None else 0,
        scope='Observer/terminal semantics on real privateMAME. Early controlled validation cleanup may leave partial diagnostic games; no full-cohort policy comparison or score qualification.',
        installed_source_changed=False,quality_qualification=False,promotion=False))
    print(json.dumps(dict(status='PASS' if passed else 'FAIL_PRESERVED',kind=job['kind'],error=failure,
        progress=progress,cleanup_errors=cleanup,qualification=False,promotion=False),indent=2))
    return 0 if passed else 1


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true');parser.add_argument('--job',type=Path)
    parser.add_argument('--job-sha256');parser.add_argument('--source-sha256');args=parser.parse_args()
    if not args.execute:
        print('PLAN_ONLY: no reads, GPU, emulator, listener or training action');return 0
    require(digest(Path(__file__).resolve())==args.source_sha256 and digest(args.job)==args.job_sha256,
            'Exact root source/job required')
    job=json.loads(args.job.read_text())
    require(job['schema']=='robotron-owned-real-MAME-boundary-validation-v1'
            and job['kind'] in ('neutral','reference') and job['gpu_uuid']=='GPU-b549355c-78bb-53d8-04a6-da34d45e1dd0',
            'Explicit selected validation profile required')
    require(job['max_wall_s']==(300 if job['kind']=='neutral' else 1800),'Fixed mode deadline required')
    return run(job)


if __name__=='__main__':raise SystemExit(main())
