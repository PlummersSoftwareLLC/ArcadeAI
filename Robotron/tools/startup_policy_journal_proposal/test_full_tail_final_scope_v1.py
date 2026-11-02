"""New controller-v2, job-bound wire and final-review predicate contract.

Only consumed fixture definitions are used, with synthetic receipts/actor PIDs.
No old test methods, real emulator/model/GPU, main changes or scientific reader
main runs. A predicate PASS is not a completed original or quality gate.
"""
import ast
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module


wire=load('_new_final_scope_wire_v2',HERE/'audit_full_tail_wire_v2.py');wire.dependencies()
runtime=load('_new_final_scope_runtime_v2',HERE/'run_compiled_full_tail32_v2.py')
control=load('_new_final_scope_controller_v2',HERE/'control_compiled_full_tail32_v2.py')
review=load('_new_final_scope_independent_reader',HERE/'read_compiled_full_tail32_original_v1.py')
defs=load('_consumed_independent_wire_fixture_definitions_only',HERE/'test_audit_full_tail_wire_v1.py')
h=load('_final_scope_pin_helpers',HERE/'run_full_policy_startup_v3.py')
rt=load('_final_scope_resource_helpers',runtime.G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py')


class FinalFullTailScope(unittest.TestCase):
    def directory(self):
        temp=tempfile.TemporaryDirectory(prefix='robotron-new-final-full-tail-scope-');self.addCleanup(temp.cleanup)
        return Path(temp.name)

    def documents(self):
        directory=self.directory()
        prior=runtime.G/'logs/managed-learning-20261015/run-26/compiled32-policy-full-tail-real-original01-preparation-20261022/job.json'
        job=json.loads(prior.read_bytes())
        job['historical_startup_acceptance_scope']=job.pop('acceptance_scope')
        job.update(schema='robotron-compiled-full-tail32-original-v2',runtime=h.pin(HERE/'run_compiled_full_tail32_v2.py'),
            output=str(directory/'uncreated-output'))
        jp=dict(path=str(runtime.G/'logs/managed-learning-20261015/run-26/final-full-tail-scope-fixture/job.json'),sha256='a'*64)
        cfg=dict(unit='robotron-compiled-full-tail32-integration-final-scope-fixture.service',output=str(directory/'no-execution'),
            argv=['/home/dave/source/repos/ArcadeAI/.venv-gb300/bin/python','-Xgil=0','-I','-B',job['runtime']['path'],
                '--execute','--job',jp['path'],'--job-sha256',jp['sha256'],'--source-sha256',job['runtime']['sha256']],
            properties=review.PROPERTIES,pins=[dict(path=jp['path'],sha256=jp['sha256']),
                dict(path=job['runtime']['path'],sha256=job['runtime']['sha256'])],observation_s=9720)
        scope=dict(schema='robotron-original-all32-compiled-full-tail-engineering-acceptance-v2',job=jp,
            original_attempt=1,no_retry=True,fixed_admission_s=90,whole_cohort_timeout_s=9000,wall_limit_s=9600,
            startup_trace_frames=1200,minimum_engineering_completed_games=32,quality_minimum_games_remains=50,
            quality_qualified=False,promotion=False)
        return directory,job,jp,cfg,scope

    def result(self):
        policy=dict(checkpoint_sha256=review.CHECKPOINT,measurement_active=True,training_enabled=False,
            replay_enabled=False,epsilon=0.,expert_ratio=0.,learner_frame_count=1741229950,training_steps=7128160,
            optimized_samples=27621148672,numeric_policy=dict(compiled=True,backend='inductor',device='cuda:0',
                weights='float32',inputs='float32',support='float32',autocast=False,warm_shapes=list(range(1,17)),
                max_batch_size=16,serving_thread_checked=True,graph_breaks=0))
        slots={str(s):dict(pid=900000+s,birth=s,actual_exit=0,outputs_sealed_after_original_writer_closure=True,
            original_unsealed_output_paths=[],peer_EOF=True)for s in runtime.SLOTS}
        cohort=dict(closed=True,complete=True,valid=True,pending=0,abandoned=0,count=32,started=32,
            started_ids=['synthetic:'+str(s)for s in runtime.SLOTS],pending_ids=[],abandoned_ids=[],
            rows=[dict(journal_game_id='synthetic:'+str(s))for s in runtime.SLOTS],started_actor_slots=list(runtime.SLOTS))
        return dict(schema='robotron-compiled-full-tail32-original-result-v2',
            status='PASS_ALL32_COMMON_COMPILED_CERTIFIED_FULL_TAIL_AND_HOST_DRAIN',complete=True,errors=[],
            original_attempt=1,no_retry=True,original_lease_released=True,immutable_inputs_unchanged=True,
            all_original_threads_stopped=True,main_observation_failures=[],original_unsealed_journal_paths=[],
            quality_qualified=False,full_game_score_verified=False,policy_before=policy,policy_after=copy.deepcopy(policy),
            before_intentional_stop=cohort,after_intentional_stop=copy.deepcopy(cohort),
            controller_exit=dict(active=False,phase='finished',complete=True,valid=True,reason=None,cohort=copy.deepcopy(cohort)),
            original_slots=slots,original_post_origin_child_reap=dict(all_original_children_reaped=True,
                unknown_slots=[],signals_sent=False,exit_statuses_normalized=False,
                original_children={s:{k:v[k]for k in ('pid','birth','actual_exit')}for s,v in slots.items()}))

    def test_explicit_new_job_SHA_binds_original_actor_and_does_not_reuse_failed_job_constant(self):
        f=defs.Fixture();self.addCleanup(f.close)
        proof=wire.audit_slot_prefix(4096,f.entry,f.job,f.result,f.starts,f.games,f.read,h.pin,
                                    expected_job_sha256=defs.audit.JOB_SHA)
        self.assertEqual(proof['session'],f.subject['session'])
        with self.assertRaises(ValueError):wire.audit_slot_prefix(4096,f.entry,f.job,f.result,f.starts,f.games,
            f.read,h.pin,expected_job_sha256='b'*64)
        alternate=self.directory();actor_dir=alternate/'actors/4096';actor_dir.mkdir(parents=True)
        actor=f.read(f.actor);actor['original_job']['sha256']='b'*64
        h.put(actor_dir/'original-actor.json',actor)
        other_job=dict(f.job,output=str(alternate))
        second=wire.audit_slot_prefix(4096,f.entry,other_job,f.result,f.starts,f.games,f.read,h.pin,
                                     expected_job_sha256='b'*64)
        self.assertEqual(second['certificate_identifier'],proof['certificate_identifier'])
        self.assertFalse(hasattr(wire,'JOB_SHA'));self.assertNotIn('torch',sys.modules)

    def test_original_precreated_lifecycle_inode_owner_and_final_seal_are_required(self):
        path=self.directory()/'lifecycle.jsonl';path.touch(mode=0o600);stat=path.stat()
        identity=dict(device=stat.st_dev,inode=stat.st_ino,mode='0o600',uid=stat.st_uid,nlink=1)
        path.write_bytes(b'synthetic final lifecycle\n');path.chmod(0o444);final=h.pin(path)
        self.assertTrue(wire.validate_original_file_identity(identity,final)['final_owned_seal_verified'])
        for name,value in [('inode',identity['inode']+1),('uid',identity['uid']+1),('mode','0o444'),('nlink',2)]:
            with self.subTest(name=name),self.assertRaises(ValueError):
                wire.validate_original_file_identity(dict(identity,**{name:value}),final)
        damaged=copy.deepcopy(final);damaged['identity']['mode']='0o600'
        with self.assertRaises(ValueError):wire.validate_original_file_identity(identity,damaged)

    def test_v2_scope_acceptance_naming_resources_and_unchanged_controller_ownership(self):
        directory,job,jp,cfg,scope=self.documents()
        self.assertEqual(runtime.validate_job(job),directory/'uncreated-output')
        review.validate_scope(job,jp,scope,cfg)
        path=directory/'controller-fixture.json';path.write_text(json.dumps(cfg));self.assertEqual(control.checked_config(path),cfg)
        for damage in ('alias','minimum','resource','schema','GPU','timeout'):
            j,s,c=copy.deepcopy(job),copy.deepcopy(scope),copy.deepcopy(cfg)
            if damage=='alias':j['acceptance_scope']=j['historical_startup_acceptance_scope']
            elif damage=='minimum':s['quality_minimum_games_remains']=32
            elif damage=='resource':c['properties'][3]='RuntimeMaxSec=900'
            elif damage=='schema':j['schema']='robotron-compiled-full-tail32-original-v1'
            elif damage=='GPU':j['gpu_uuid']='GPU-c0c5d295-6f07-aab5-bbde-b592ea426ec1'
            else:j['whole_cohort_timeout_s']=180
            with self.subTest(damage=damage),self.assertRaises(ValueError):review.validate_scope(j,jp,s,c)
        old=ast.parse((HERE/'control_compiled_full_tail32_v1.py').read_text());new=ast.parse((HERE/'control_compiled_full_tail32_v2.py').read_text())
        def functions(tree):return [ast.dump(n,include_attributes=False)for n in tree.body
            if isinstance(n,(ast.FunctionDef,ast.ClassDef))and n.name!='checked_config']
        self.assertEqual(functions(old),functions(new))

    def test_runtime_result_rejects_unknown_exits_mutating_policy_unsealed_writers_and_missing_tails(self):
        _,job,_,_,_=self.documents();original=self.result()
        policy,cohort=review.validate_runtime_result(original,job)
        self.assertEqual(cohort['count'],32);self.assertEqual(policy['checkpoint_sha256'],review.CHECKPOINT)
        self.assertFalse(original['quality_qualified'])
        for damage in ('unknown','nonzero','unsealed','policy','failure','cohort','lease','thread'):
            result=copy.deepcopy(original)
            if damage=='unknown':result['original_slots']['4096']['actual_exit']=None
            elif damage=='nonzero':result['original_slots']['4096']['actual_exit']=-15
            elif damage=='unsealed':result['original_slots']['4096']['outputs_sealed_after_original_writer_closure']=False
            elif damage=='policy':result['policy_after']['training_steps']+=1
            elif damage=='failure':result['main_observation_failures']=[dict(actual_error='synthetic')]
            elif damage=='cohort':result['before_intentional_stop']['rows'].pop()
            elif damage=='lease':result['original_lease_released']=False
            else:result['all_original_threads_stopped']=False
            with self.subTest(damage=damage),self.assertRaises(ValueError):review.validate_runtime_result(result,job)

    def test_actual_native_descriptor_command_identity_exit_and_resources_are_required(self):
        _,_,_,cfg,_=self.documents();owner=dict(unit=cfg['unit'],invocation_id='c'*32,pid=999999999)
        now=time.monotonic();fields=dict(Id=owner['unit'],InvocationID=owner['invocation_id'],ExecMainPID=str(owner['pid']),
            ExecMainCode='1',ExecMainStatus='0',NRestarts='0',CPUQuotaPerSecUSec='12s',MemoryMax=str(16<<30),
            MemorySwapMax='0',RuntimeMaxUSec='9660s',TasksMax='512',TimeoutStopUSec='30s',KillMode='mixed',
            SendSIGKILL='no',Restart='no',ExecStart='argv[]='+' '.join(cfg['argv'])+' ; ignore_errors=no ;',
            ExecMainStartTimestampMonotonic=str(int((now-2)*1e6)),ExecMainExitTimestampMonotonic=str(int((now-1)*1e6)))
        start,end=review.validate_native_fields(fields,cfg,owner,rt.duration_seconds);self.assertLess(start,end)
        for key,value in [('ExecMainStatus','1'),('InvocationID','d'*32),('MemoryMax',str(4<<30)),
            ('RuntimeMaxUSec','900s'),('ExecStart','wrong'),('ExecMainExitTimestampMonotonic',str(int((now+100)*1e6)))]:
            with self.subTest(key=key),self.assertRaises(ValueError):
                review.validate_native_fields(dict(fields,**{key:value}),cfg,owner,rt.duration_seconds)

    def test_narrow_log_classifications_do_not_hide_actor_timeout_fallback_or_unknown_errors(self):
        pid=999999999;port=20000
        stdout='\n'.join(['MAME interface initialized.','[PATCH] RRCHRIS runtime ROM patch disabled.',
            'Socket connection opened to socket.127.0.0.1:20000','[DIFFICULTY] GA1 poked to 5'])
        stderr=review.ALSA+'\n'+f'[robotron-socket-wait] pid={pid} fd=9 port={port} interval_us=1000\n'
        self.assertEqual(review.audit_actor_logs(stdout,stderr,4096,pid,port)['action_timeouts'],0)
        policy=dict(epsilon=0.,expert_ratio=0.,training_enabled=False)
        clean=review.EXPERT+'\nClient 0 disconnected: EOF\n'
        self.assertEqual(review.audit_evaluator_logs(clean,'',policy,True)['unknown_errors'],0)
        for bad in ['[SOCKET ACTION TIMEOUT]','RuntimeError: failed','[WARN] unknown unavailable']:
            with self.subTest(bad=bad),self.assertRaises(ValueError):review.audit_actor_logs(stdout+'\n'+bad,stderr,4096,pid,port)
            with self.assertRaises(ValueError):review.audit_evaluator_logs(clean+'\n'+bad,'',policy,True)
        with self.assertRaises(ValueError):review.audit_evaluator_logs(clean,'',policy,False)
        with self.assertRaises(ValueError):review.audit_evaluator_logs(clean,'',dict(policy,epsilon=.1),True)


if __name__=='__main__':unittest.main(verbosity=2)
