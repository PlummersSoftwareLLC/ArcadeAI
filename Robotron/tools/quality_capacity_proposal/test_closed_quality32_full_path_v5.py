"""Full reviewer tests: synthetic archives/checkpoints, mocked OS state and clock.

The protected reference is read/copied, never changed. Synthetic candidate bytes
and a synthetic verifier report exercise provenance joins; no model is loaded
or claimed verified. No emulator, GPU, service or production control is changed.
"""
import copy
import hashlib
import io
import json
import math
import os
from pathlib import Path
import shutil
import statistics
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

import review_closed_quality32_v5 as review
import supervised_main_fleet_v1 as supervision
import supervised_main_observations_v1 as observations
import test_supervised_main_fleet_v1 as supervision_fixtures
import test_audit_pilot_evidence as evidence_fixtures
from Robotron.tools import run_quality_campaign as campaign


class FullPathTests(unittest.TestCase):
    def test_new_owner_binding_requires_every_one_of_195_inputs(self):
        path=review.GAME/'logs/managed-learning-20261015/run-26/future-score-carry-live-controller-original04-preparation-20261019/completed-registration/current-main-binding.json'
        main=json.loads(path.read_bytes())
        binding=dict(main_holds={key:copy.deepcopy(main[key]) for key in ('owner','actors','held_hashes','experiment')},
                     expected_window=dict(owner=copy.deepcopy(main['owner'])))
        main['supervision_policy']=dict(path='/synthetic/policy.json')
        binding['main_holds']['supervision_policy']=main['supervision_policy']
        review.validate_main_binding(main,binding)
        for count in (193,194,196):
            changed=copy.deepcopy(main)
            changed['held_hashes']={str(i):'a'*64 for i in range(count)}
            claimed=copy.deepcopy(binding)
            claimed['main_holds']['held_hashes']=copy.deepcopy(changed['held_hashes'])
            with self.subTest(count=count),self.assertRaisesRegex(ValueError,'main192/195'):
                review.validate_main_binding(changed,claimed)

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.reader=review.reader_module()
        self.directory=review.GAME/'logs/managed-learning-20261015'/('synthetic-quality32-full-'+str(time.time_ns()))
        self.addCleanup(lambda: shutil.rmtree(self.directory) if self.directory.exists() else None)
        self.real_unix=int(time.time());self.real_mono=int(time.monotonic())
        self.start_unix=self.real_unix+3600;self.start_mono=self.real_mono+3600
        self.end_unix=self.start_unix+22020;self.end_mono=self.start_mono+22020
        self.owner=dict(unit='robotron-quality32-synthetic.service',timer='robotron-quality32-synthetic.timer',
            pid=9_000_000,starttime_ticks=1,observed_live=True,invocation_id='a'*32,
            timer_invocation_id='b'*32,cgroup='/synthetic-quality32-full')
        self.reference=self.reader.pin(review.GAME/'models_dqn/managed-incumbents/freshCE-LR25-1059M-confirmed-reset-20261018.pt')
        self.candidate=self.put(self.root/'candidate.pt',b'synthetic candidate; no numerical model is loaded')
        self.verification_copy=self.put(self.root/'candidate-copy.pt',Path(self.candidate['path']).read_bytes())
        self.library=self.put(self.root/'socket-wait.so',b'synthetic shim bytes; no library is loaded')
        self.native_command=[str(review.GAME.parent/'.venv-gb300/bin/python'),'-Xgil=0','-B','-u',
            str(review.HERE/'profile03/Robotron/tools/run_quality_campaign.py'),
            '--actors','32','--cohort-s','5400','--timeout-s','7200','--game-boundary-diagnostics','--launch']
        self.native_config=dict(unit=self.owner['unit'],output=str(self.root/'native-execution'),argv=self.native_command)

    def put(self,path,value):
        path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
        raw=value if isinstance(value,bytes) else (json.dumps(value,allow_nan=False)+'\n').encode()
        if path.exists():path.chmod(0o644)
        path.write_bytes(raw);path.chmod(0o444)
        return self.reader.pin(path)

    def flat(self,entry):
        return dict(path=entry['path'],sha256=entry['sha256'],bytes=entry['bytes'],**{
            key:value for key,value in entry['identity'].items() if key!='bytes'})

    def closure(self,owner,config,name,start,end):
        area=self.root/name;area.mkdir();archives=[]
        wrapper=['/usr/bin/env','-u','LD_PRELOAD','-u','PYTHONPATH','CUDA_VISIBLE_DEVICES=',
            'PYTHONDONTWRITEBYTECODE=1','TMPDIR='+str(Path(config['output'])/'tmp')]+config['argv']
        fields=dict(Id=owner['unit'],InvocationID=owner['invocation_id'],MainPID='0',
            ExecMainPID=str(owner['pid']),ExecMainCode='1',ExecMainStatus='0',NRestarts='0',Result='success',
            RuntimeMaxUSec='8h 10min',MemoryMax=str(12<<30),CPUQuotaPerSecUSec='12s',Restart='no',SendSIGKILL='no',
            ExecMainStartTimestampMonotonic=str(start*1_000_000),ExecMainExitTimestampMonotonic=str(end*1_000_000),
            ExecStart='{ path=/usr/bin/env ; argv[]='+' '.join(wrapper)+
                ' ; ignore_errors=no ; pid='+str(owner['pid'])+' ; code=exited ; status=0 }')
        for kind,unit in [('service',owner['unit']),('timer',owner['timer'])]:
            for action in ('show','cat','journal'):
                argv=['journalctl','--user','--unit',unit,'--no-pager'] if action=='journal' else ['systemctl','--user',action,unit]
                content='\n'.join(key+'='+value for key,value in fields.items())+'\n' if kind=='service' and action=='show' else ''
                if kind=='timer' and action=='show':content='Id='+unit+'\nLoadState=not-found\n'
                archives.append(dict(argv=argv,exit=1 if kind=='timer' and action=='cat' else 0,timed_out=False,
                    stdout=self.put(area/(kind+'-'+action+'.out'),content.encode()),
                    stderr=self.put(area/(kind+'-'+action+'.err'),b'')))
        return self.put(area/'closure.json',dict(original=owner,original_exit=0,lifecycle_complete=True,
            unit_released=True,original_archived_before_release=True,payload_retried=False,full_original_archives=archives,
            owned_release=[dict(unit=unit,confirmed_absent=True) for unit in (owner['unit'],owner['timer'])]))

    def acquisition(self,main):
        base=review.GAME/'logs/managed-learning-20261015/run-26/confirmed-scoring-quality-original01-preparation-20261018/audit-bindings/binding-job.json'
        old=json.loads(base.read_bytes());bundle={key:json.loads(Path(old['evidence'][key]['path']).read_bytes())
            for key in ('phase_cpu_job','phase_cpu_report','window_job','window_result','window_latch')}
        phase_job,proof=bundle['phase_cpu_job'],bundle['phase_cpu_report']
        self.clocks=copy.deepcopy(proof['clocks'])
        self.clocks.update(training_steps=5_080_000,total_training_steps=5_080_000,
            optimized_samples=19_240_000_000,total_optimized_samples=19_240_000_000,
            learner_frame_count=1_200_000_000,frame_count=2_372_000_000)
        phase_job.update(source=self.candidate,verification_copy=self.verification_copy,
            clock_floor={key:self.clocks[key] for key in ('training_steps','optimized_samples','learner_frame_count','frame_count')},
            output_directory=str(self.root/'synthetic-CPU-output'))
        job_entry=self.put(self.root/'phase-CPU-job.json',phase_job)
        proof.update(root_job=copy.deepcopy(phase_job),job_file=self.flat(job_entry),
            sha256=self.candidate['sha256'],bytes=self.candidate['bytes'],path=self.verification_copy['path'],
            source_before=self.flat(self.candidate),verification_copy=self.flat(self.verification_copy),clocks=self.clocks)
        proof['bound_files']['source_checkpoint']=self.flat(self.candidate)
        proof['bound_files']['root_readonly_verification_copy']=self.flat(self.verification_copy)
        proof_entry=self.put(self.root/'phase-CPU-report.json',proof)
        cpu_owner=dict(self.owner,unit='robotron-quality32-synthetic-CPU.service',timer='robotron-quality32-synthetic-CPU.timer',
            pid=9_000_001,invocation_id='c'*32,timer_invocation_id='d'*32,cgroup='/synthetic-quality32-CPU')
        verifier=review.GAME/'tools/live_lr_recipe_continuation_proposal/verify_recipe_phase_snapshot.py'
        argv=[str(review.GAME.parent/'.venv-gb300/bin/python'),'-Xgil=0','-I','-B',str(verifier),
            '--execute','--job',job_entry['path'],'--expected-job-sha256',job_entry['sha256'],
            '--expected-verifier-sha256','14942da97b06c3c2870ac5d3109a2a5b76acefc1523e9b23b9e510c0994152b5']
        config=dict(unit=cpu_owner['unit'],output=str(self.root/'synthetic-CPU-execution'),argv=argv)
        cpu_closure=self.closure(cpu_owner,config,'CPU-closure',self.start_mono-9,self.start_mono-8)
        completion=self.put(self.root/'CPU-completion.json',dict(status='PASS',CPU_report=proof_entry,cpu_job=job_entry,
            original_controller_release=cpu_closure,actual_candidate=self.candidate,quality_qualified=False,promotion=False))
        window=bundle['window_job'];window.update(owner=main['owner'],actors=main['actors'],
            experiment=main['experiment'],tag='synthetic-future-capture',baseline_monotonic_s=self.start_mono-20)
        package=self.reader.pin(review.HERE/'profile03/runtime-source-package.json')
        window['quality_precommit'].update(reference=self.reference['path'],reference_sha256=self.reference['sha256'],
            all_slots=review.SLOTS.copy(),source_package=package)
        result=bundle['window_result'];result.update(checkpoint=self.candidate,owner=main['owner'],tag=window['tag'])
        latch=bundle['window_latch'];latch.update(progress=copy.deepcopy(result['progress']),
            job_experiment=main['experiment'],observed_monotonic_s=self.start_mono-10)
        return dict(phase_cpu_job=job_entry,phase_cpu_report=proof_entry,
            window_job=self.put(self.root/'window-job.json',window),window_result=self.put(self.root/'window-result.json',result),
            window_latch=self.put(self.root/'window-latch.json',latch),phase_cpu_closure=cpu_closure,
            phase_cpu_completion=completion,phase_cpu_config=self.put(self.root/'CPU-config.json',config),source_package=package)

    def api(self,unix,index,main,gradient=False):
        counters=dict(attempts_started=1000+index,outcomes_recorded=1000+index,applied=1000+index,amp_skipped=0,unavailable=0)
        exposure=dict(optimizer=dict(schema='robotron-optimizer-exposure-v1',enabled=True,available=True,
            process_id=main['owner']['pid'],instance_monotonic_ns=10,epoch=1,total=dict(counters),
            since_epoch=dict(counters),unclassified_started_total=0),replay=dict(enabled=True,available=True,
            process_id=main['owner']['pid'],instance_monotonic_ns=11,epoch=1,accepted_learner_total=1000+index))
        pipe=dict(schema='robotron-host-pipeline-v1',available=True,generation=0,learning_exposure=exposure)
        pipe.update({name:dict(errors=0) for name in ('inference','actor_refresh','target_refresh','learner_priority')})
        result=dict(ts=unix,client_count=192,training_enabled=True,measurement_active=False,
            managed_experiment=main['experiment'],lr=1.25e-5,pipeline_read_error='',bank_persistence_read_error='',
            pipeline_snapshot_age_s=0,host_pipeline=pipe,bank_persistence=dict(write_failures=0),
            grad_norm=float('inf') if gradient else .25)
        result.update({key:1000+index for key in ('frame_count','learner_frame_count','optimized_samples','training_steps')})
        return result

    def build(self,candidate_gain=True,mutation=None):
        N=review.GAME/'logs/managed-learning-20261015/run-26/confirmed-scoring-quality-original01-preparation-20261018/capacity32-confirmed1059-raw-API-v1-preparation-20261019'
        main=json.loads((review.GAME/'logs/managed-learning-20261015/run-26/future-score-carry-live-controller-original04-preparation-20261019/completed-registration/current-main-binding.json').read_bytes())
        evidence=self.acquisition(main)
        config=campaign.Campaign(Path(self.reference['path']),Path(self.candidate['path']),self.directory,
            reference_label='synthetic-reference',candidate_label='synthetic-candidate',actors=32,
            cohort_s=5400,timeout_s=7200,mame=Path('/usr/games/mame'),rompath=review.GAME/'roms',
            boot_assets=review.GAME/'logs/managed-learning-20261015/sidecar-boot-assets-v1')
        with patch.object(campaign.sys,'executable',str(review.GAME.parent/'.venv-gb300/bin/python')):
            plan=campaign.make_plan(config)
        self.directory.mkdir(mode=0o700)
        campaign.snapshot_checkpoints(plan)
        self.put(self.directory/'plan.json',plan)
        records=[];births={};actor_births={}
        for spec in plan['legs']:
            fixture=evidence_fixtures.EvidenceTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
            legdir=Path(spec['job']['directory']);shutil.copytree(fixture.root,legdir);fixture.root=legdir
            data=fixture.data;index=spec['index'];label=spec['job']['label'];record_start=self.start_unix+(index-1)*5500+1
            is_candidate=spec['role']=='candidate';gain=1000 if is_candidate and (candidate_gain or index==4) else 0
            data.update(job=copy.deepcopy(spec['job']),label=label,source_checkpoint_path=spec['job']['checkpoint'],
                checkpoint_path=str(legdir/'checkpoint.pt'),checkpoint_sha256=plan['checkpoints'][spec['role']]['sha256'],
                start_ts=record_start+10,close_ts=record_start+5410,timeout_snapshot_unix_s=record_start+5470,
                ended_unix_s=record_start+5480,elapsed_s=5479,checkpoint_metadata=copy.deepcopy(self.clocks),
                clocks={key:self.clocks[key] for key in ('training_steps','optimized_samples','learner_frame_count')},
                source_hashes=copy.deepcopy(plan['evaluator_source_hashes']),
                ended_source_hashes=copy.deepcopy(plan['evaluator_source_hashes']),boot_assets=copy.deepcopy(plan['boot_assets']),
                runtime=dict(torch='synthetic',device='cuda',cuda_visible_devices=spec['job']['gpu_uuid'],
                    gpu_name='NVIDIA RTX PRO 2000 Blackwell',compute_capability=[12,0]))
            self.put(legdir/'checkpoint.pt',Path(spec['job']['checkpoint']).read_bytes())
            successors={}
            for number,row in enumerate(data['rows']):
                old=row['journal_game_id'];identifier=f'{index}:{old}';successor=data['terminal_successors'][old]
                row.update(journal_game_id=identifier,experiment=label,score=row['score']+gain,
                    start_unix_s=data['start_ts']+number*50,end_unix_s=data['close_ts']+20+number%5)
                row['duration_s']=row['end_unix_s']-row['start_unix_s']
                for context in ('start_context','end_context'):
                    row[context].update(experiment=label,training_steps=self.clocks['training_steps'],
                        optimized_samples=self.clocks['optimized_samples'],learner_frames=self.clocks['learner_frame_count'])
                confirmation=row['terminal_confirmation'];confirmation.update(previous_score=row['score'],next_journal_game_id=identifier+':next')
                for context in ('previous_accepted_wire','classifier_previous'):
                    confirmation['ingest_boundary_inputs'][context]['raw_score']=row['score']%100_000_000
                successor.update(journal_game_id=identifier+':next',start_unix_s=row['end_unix_s']+.01)
                successors[identifier]=successor
            data['terminal_successors']=successors
            scores=[row['score'] for row in data['rows']]
            stats=dict(count=len(scores),started=len(scores),mean=statistics.mean(scores),median=statistics.median(scores),
                sd=statistics.stdev(scores),se=statistics.stdev(scores)/math.sqrt(len(scores)))
            data.update(stats);data['cohort'].update(stats,started_ids=[row['journal_game_id'] for row in data['rows']],
                experiment=label,start_ts=data['start_ts'],close_ts=data['close_ts'])
            fixture.write_originals()
            data['boot_restores']={str(slot):dict(identity=plan['boot_assets']['identity'],files=plan['boot_assets']['files'],
                manifest_sha256=plan['boot_assets']['manifest_sha256'],restored_paths={name:str(legdir/'actors'/str(slot)/name)
                    for name in plan['boot_assets']['files']}) for slot in review.SLOTS}
            data['socket_wait'].update(library=self.library['path'],sha256=self.library['sha256'])
            evaluator=dict(pid=9_000_100+index,parent_pid=self.owner['pid'],cgroup=self.owner['cgroup'],
                starttime_ticks=100+index,observed_live=True)
            births[str(index)]=evaluator;actor_births[str(index)]={}
            for offset,slot in enumerate(review.SLOTS):
                pid=9_100_000+index*100+offset
                actor_births[str(index)][str(slot)]=dict(pid=pid,parent_pid=evaluator['pid'],cgroup=self.owner['cgroup'],
                    starttime_ticks=1000+index*100+offset,observed_live=True)
                data['socket_wait']['actors'][str(slot)]['pid']=pid
                path=legdir/'actors'/str(slot)/'console.log'
                self.put(path,path.read_bytes().replace(str(80000+slot).encode(),str(pid).encode()))
            self.put(legdir/'plan.json',dict(spec['job'],checkpoint_sha256=data['checkpoint_sha256']))
            self.put(legdir/'receipt.json',data);self.put(legdir/'journal/lives.jsonl',b'')
            self.put(spec['console_log'],b'Startup\n[WARN] Robotron expert unavailable (No module named \'v3\'); expert guidance disabled.\n')
            records.append(dict(index=index,role=spec['role'],state='finished',pid=evaluator['pid'],returncode=0,
                started_unix_s=record_start,ended_unix_s=record_start+5490,receipt_path=spec['receipt_path'],
                console_log=spec['console_log'],evaluator_status_path=spec['evaluator_status_path']))
        summary=campaign.assess_campaign(plan,records)
        self.assertEqual(summary['outcome'],'qualified_improvement' if candidate_gain else 'not_improved',summary)
        summary.update(plan_sha256=review.digest(self.directory/'plan.json'),stop_signal=None)
        status=dict(state='finished',plan_sha256=summary['plan_sha256'],outcome=summary['outcome'],legs=records)
        status_entry=self.put(self.directory/'status.json',status);summary_entry=self.put(self.directory/'summary.json',summary)
        main['baseline_API']=self.put(self.root/'baseline-API.json',self.api(self.start_unix-1,0,main))
        held=hashlib.sha256(json.dumps(main['held_hashes'],sort_keys=True,separators=(',',':')).encode()).hexdigest()
        wire=self.reader.checked_module('_full_test_raw_'+str(time.time_ns()),self.reader.pin(
            review.GAME/'tools/eval_capacity_proposal/raw_api_witness_v1.py'))
        samples=[]
        for index,monotonic in enumerate(range(self.start_mono-1,self.end_mono+21,20)):
            unix=self.start_unix+monotonic-self.start_mono;api=self.api(unix,index,main,gradient=index==1)
            raw=json.dumps(api,allow_nan=True).encode();raw_entry=self.put(self.root/'API-wires'/f'{index:04d}.raw',raw)
            sample=dict(monotonic_s=monotonic,unix_s=unix,main_owner=main['owner'],original192_actors_verified=True,
                held_hashes_sha256=held,autosave=dict(mtime_ns=(unix-5)*10**9,bytes=275000000,age_s=5),
                **wire.witness_fields(api,raw_entry))
            if mutation=='raw_projection' and index==2:
                api['lr']=0.;sample['API_wire']=self.put(self.root/'API-wires'/'changed.raw',json.dumps(api).encode())
            samples.append(self.put(self.root/'main-samples'/f'{index:04d}.json',sample))
        manifest=self.put(self.root/'main-manifest.json',dict(schema='robotron-main192-pilot-observations-v1',
            status='PASS',configuration_changed=False,main_owner=main['owner'],accounting_policy='single_inflight_optimizer_v1',
            rejected_observations=[],samples=samples,API_witness_format=wire.FORMAT))
        owner_entry=self.put(self.root/'native-owner.json',self.owner)
        binding=dict(candidate=self.candidate,reference=self.reference,evidence=evidence,
            expected_window=dict(owner=main['owner'],experiment=main['experiment'],tag='synthetic-future-capture'),
            main_holds={key:copy.deepcopy(main[key]) for key in ('owner','actors','held_hashes','experiment')},
            campaign=dict(output_directory=str(self.directory),plan_sha256=summary['plan_sha256'],
                native_unit=self.owner['unit'],native_owner_path=owner_entry['path'],command=self.native_command,
                controller_output=self.native_config['output'],evaluator_source_hashes=plan['evaluator_source_hashes'],
                execution_source_hashes=plan['execution_source_hashes']))
        binding_entry=self.put(self.root/'binding.json',binding)
        context=dict(schema='robotron-closed-quality32-campaign-context-v1',binding=binding_entry,native_owner=owner_entry,
            native_closure=self.closure(self.owner,self.native_config,'native-closure',self.start_mono,self.end_mono),
            native_controller_config=self.put(self.root/'native-config.json',self.native_config),
            status_final=status_entry,summary_final=summary_entry,main_binding=self.put(self.root/'main-binding.json',main),
            main_observations=manifest,leg_evaluator_births=self.put(self.root/'evaluator-births.json',births),
            leg_actor_identities=self.put(self.root/'actor-births.json',actor_births))
        context_entry=self.put(self.root/'closed-context.json',context)
        lease=Path('/dev/shm/robotron-snapshot-smoke-gpu0.lock');info=lease.lstat()
        job=dict(schema='robotron-closed-quality32-root-review-job-v1',binding=binding_entry,
            closed_context_path=context_entry['path'],output=str(self.root/'review'),
            main_guard_source=self.reader.pin(review.GAME/'logs/managed-learning-20261015/run-26/capacity-original-full-reviewer-CPU-original01-preparation-20261019/immutable-main-hold-guard.py'),
            lease_path=str(lease),lease_identity=dict(device=info.st_dev,inode=info.st_ino))
        # Synthetic census and unit observations are never live-process authority.
        policy=supervision_fixtures.fixture()
        policy['trainer']=copy.deepcopy(main['owner'])
        fleet=policy['fleet']
        for slot,oldactor in {str(row['slot']):row for row in main['actors']}.items():
            actor=policy['baseline_actors'][slot]
            actor.update(pid=oldactor['pid'],starttime_ticks=oldactor['starttime_ticks'],
                affinity=oldactor['mask'],parent_pid=fleet['pid'],cgroup=fleet['cgroup'])
        claim=policy['trainer'];obs=policy['baseline_owners']['trainer']
        obs['process'].update(**supervision.birth(claim),cgroup=claim['cgroup'])
        obs['argv']=['systemctl','--user','show',claim['unit']]
        fields=dict(Id=claim['unit'],MainPID=str(claim['pid']),InvocationID=claim['invocation_id'],
            NRestarts='0',ActiveState='active',SubState='running',ControlGroup=claim['cgroup'])
        obs['stdout']=''.join(key+'='+value+'\n' for key,value in fields.items())
        policy['held_hashes_sha256']=observations.checksum(main['held_hashes'])
        main['supervision_policy']=self.put(self.root/'supervision-policy.json',policy)
        supervision.validate_policy(policy)
        manifest_value=self.reader.read_pin(manifest);new_samples=[];state=None
        for index,pin in enumerate(manifest_value['samples']):
            sample=self.reader.read_pin(pin)
            # Keep the last observation after native exit but before review time.
            last=index==len(manifest_value['samples'])-1
            if last:
                sample.update(monotonic_s=self.end_mono+1,unix_s=self.end_unix+1)
                sample['autosave']=dict(mtime_ns=(sample['unix_s']-5)*10**9,bytes=275000000,age_s=5)
            count=191 if index==1 else 192
            if index==1 or last:
                raw_value=wire.parse_wire(self.reader.read_pin(sample['API_wire'],as_json=False))
                raw_value.update(client_count=count,ts=sample['unix_s'])
                raw_entry=self.put(self.root/'API-wires'/('supervised-'+str(index)+'.raw'),json.dumps(raw_value,allow_nan=True).encode())
                sample.update(wire.witness_fields(raw_value,raw_entry))
            missing=['168'] if index==1 else []
            replacements={'168':supervision_fixtures.replacement(policy,'168',100000)} if index==2 else {}
            snapshot=supervision_fixtures.snapshot(policy,state,sample['monotonic_s'],missing,replacements)
            snapshot.update(unix_s=sample['unix_s'],collection_started_unix_s=sample['unix_s']-.01)
            state=supervision.validate_snapshot(policy,snapshot,sample['API']['client_count'],state)
            sample.pop('original192_actors_verified')
            sample.update(supervised_main_fleet_verified=True,
                main_fleet_snapshot=self.put(self.root/'main-fleet-snapshots'/f'{index:04d}.json',observations.pack(snapshot,supervision)),
                main_fleet_state_sha256=observations.checksum(state))
            new_samples.append(self.put(pin['path'],sample))
        manifest_value.update(schema=observations.SCHEMA,samples=new_samples,
            supervision_policy=main['supervision_policy'],supervision_summary=supervision.validate_closed(state))
        new_manifest=self.put(manifest['path'],manifest_value)
        binding['main_holds']['supervision_policy']=main['supervision_policy']
        new_binding=self.put(job['binding']['path'],binding)
        context=self.reader.read_pin(self.reader.pin(job['closed_context_path']))
        context.update(binding=new_binding,main_binding=self.put(context['main_binding']['path'],main),main_observations=new_manifest)
        self.put(job['closed_context_path'],context)
        job['binding']=new_binding
        self.supervision_policy=policy;self.final_supervision_state=state
        return job,self.put(self.root/'root-job.json',job),main

    def execute(self,candidate_gain=True,mutation=None):
        if mutation=='late_precommit':
            self.start_unix=self.real_unix-22050
            self.end_unix=self.start_unix+22020
        job,job_entry,main=self.build(candidate_gain,mutation)
        actual_checked=self.reader.checked_module;holds=Mock();cleanup=Mock()
        def checked(name,entry):
            module=actual_checked(name,entry)
            if entry==job['main_guard_source']:module.owner_and_files=holds
            if entry['sha256']==review.DEPENDENCIES['runtime'][1]:module.verify_cleanup=cleanup
            if entry['sha256']==review.DEPENDENCIES['supervision'][1]:
                def census(policy,state):
                    value=supervision_fixtures.snapshot(policy,state,self.end_mono+5)
                    value.update(unix_s=self.end_unix+5,collection_started_unix_s=self.end_unix+5-.01)
                    return value
                module.collect=census
            return module
        with patch.object(self.reader,'checked_module',side_effect=checked),\
             patch.object(review,'reader_module',return_value=self.reader),\
             patch.object(review.time,'time',return_value=self.end_unix+5),\
             patch.object(review.time,'monotonic',return_value=(self.start_mono+5 if mutation=='future_exit' else self.end_mono+5)),\
             patch.object(review.urllib.request,'urlopen',side_effect=lambda *args,**kwargs:
                io.BytesIO(json.dumps(self.api(self.end_unix+5,9999,main)).encode())):
            code=review.main(['--execute','--job',job_entry['path'],'--job-sha256',job_entry['sha256'],
                              '--source-sha256',review.digest(review.__file__)])
            result=json.loads((Path(job['output'])/'review.json').read_bytes())
            self.assertEqual(code,0 if result['valid'] else 2)
        self.assertNotIn('torch',sys.modules)
        self.assertFalse(result['promotion']);self.assertFalse(result['learning_speed_gain_verified'])
        return result,holds,cleanup

    def test_successful_whole_review_retains200_ROM_proofs_and_accepts_raw_diagnostic_Inf(self):
        result,holds,cleanup=self.execute()
        self.assertTrue(result['valid'],result.get('error'));self.assertTrue(result['quality_qualified'])
        self.assertEqual(sum(leg['cohort']['original_games']['rom_game_over_evidence']['verified_games'] for leg in result['legs']),200)
        self.assertEqual(result['decision']['pooled_reference']['count'],100)
        self.assertEqual([value['index'] for value in result['decision']['individual_candidate_checks']],[2,4])
        holds.assert_called_once();self.assertEqual(cleanup.call_count,4)

    def test_successful_whole_review_does_not_pool_candidates_to_rescue_failure(self):
        result,holds,cleanup=self.execute(candidate_gain=False)
        self.assertTrue(result['valid'],result.get('error'));self.assertFalse(result['quality_qualified'])
        self.assertEqual(result['decision']['outcome'],'not_improved')
        self.assertFalse(result['decision']['individual_candidate_checks'][0]['mean_pass'])
        holds.assert_called_once();self.assertEqual(cleanup.call_count,4)

    def test_raw_API_projection_tamper_fails_inside_whole_review(self):
        result,holds,cleanup=self.execute(mutation='raw_projection')
        self.assertFalse(result['valid']);self.assertFalse(result['quality_qualified'])
        self.assertIn('projection',result.get('error','').lower())
        holds.assert_not_called();cleanup.assert_not_called()

    def test_late_root_binding_and_plan_fail_inside_whole_review(self):
        result,holds,cleanup=self.execute(mutation='late_precommit')
        self.assertFalse(result['valid']);self.assertFalse(result['quality_qualified'])
        self.assertIn('predate the first measurement',result.get('error',''))
        holds.assert_not_called();cleanup.assert_not_called()

    def test_future_native_exit_fails_inside_whole_review(self):
        result,holds,cleanup=self.execute(mutation='future_exit')
        self.assertFalse(result['valid']);self.assertFalse(result['quality_qualified'])
        self.assertIn('Original campaign runtime',result.get('error',''))
        holds.assert_not_called();cleanup.assert_not_called()
