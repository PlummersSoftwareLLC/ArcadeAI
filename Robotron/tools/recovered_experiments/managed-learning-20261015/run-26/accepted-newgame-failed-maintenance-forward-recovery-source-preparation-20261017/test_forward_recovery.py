"""Authored, UNEXECUTED stock-stdlib file/cursor and mocked-clock guards."""
import ast
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest import mock

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('_forward_recovery_guarded',HERE/'run_forward_recovery.py')
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)


def require(value,message):
    if not value:raise RuntimeError(message)


def real_log_reader():
    source=M.GAME/'tools/inference_worker_affinity.py';tree=ast.parse(source.read_text())
    markers=next(n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='LOG_MARKERS' for t in n.targets))
    methods=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Host')
    body=[n for n in methods.body if isinstance(n,ast.FunctionDef) and n.name in ('configure_logs','log_errors')]
    cls=ast.ClassDef(name='CapturedHost',bases=[],keywords=[],body=body,decorator_list=[])
    module=ast.fix_missing_locations(ast.Module(body=[markers,cls],type_ignores=[]))
    ns=dict(Path=Path,os=os,require=require)
    exec(compile(module,str(source),'exec'),ns)
    obj=ns['CapturedHost']();obj.log_offsets={}
    return obj,ns['LOG_MARKERS']


class Base:
    def fingerprint(self,path,limit=None):
        p=Path(path);b=p.read_bytes();st=p.stat()
        if limit is not None:require(len(b)<=limit,'bound')
        return dict(path=str(p),sha256=hashlib.sha256(b).hexdigest(),bytes=len(b),identity=dict(device=st.st_dev,inode=st.st_ino))
    def fsync_directory(self,path):pass  # No synthetic fixture claims durability.
    def publish(self,path,value):
        with Path(path).open('x') as f:json.dump(value,f,allow_nan=False)
        return self.fingerprint(path)


def setup(directory,initial=b''):
    path=directory/'actor.log';path.write_bytes(initial)
    reader,markers=real_log_reader();transition,_=real_log_reader();st=path.stat()
    bindings={str(path):dict(device=st.st_dev,inode=st.st_ino)}
    reader.configure_logs(bindings);transition.configure_logs(bindings)
    runtime=types.SimpleNamespace(host=types.SimpleNamespace(metric_host=reader,transition_logs=transition),metrics=types.SimpleNamespace(LOG_MARKERS=markers))
    coverage=M.TransitionCoverage(runtime,Base(),directory/'coverage')
    return path,reader,runtime,coverage


def append(path,data):
    with path.open('ab') as f:f.write(data)


class ForwardRecoveryContracts(unittest.TestCase):
    def test_covered_restart_once_handover_never_skips_postread_append(self):
        with tempfile.TemporaryDirectory() as d:
            p,reader,runtime,coverage=setup(Path(d))
            payload=b'[SOCKET ACTION TIMEOUT] elapsed=83.0s\n'
            append(p,payload);coverage.scan()
            append(p,b'Traceback (most recent call last):\n')  # After covered read, before handover.
            proof=coverage.handover(reader)
            self.assertEqual(proof[str(p)]['offset'],len(payload))
            self.assertTrue(any(e['marker']=='Traceback' for e in reader.log_errors()))
            raw=list((Path(d)/'coverage').glob('*.bin'))
            self.assertEqual(len(raw),1);self.assertEqual(raw[0].read_bytes(),payload)

    def test_same_timeout_after_handover_is_strict_and_partial_cannot_handover(self):
        with tempfile.TemporaryDirectory() as d:
            p,reader,runtime,coverage=setup(Path(d))
            append(p,b'[SOCKET ACTION TIMEOUT] old\n');coverage.scan();coverage.handover(reader)
            self.assertEqual(reader.log_errors(),[])
            append(p,b'[SOCKET ACTION TIMEOUT] NEW\n')
            self.assertEqual([e['marker'] for e in reader.log_errors()],['[SOCKET ACTION TIMEOUT]'])
        with tempfile.TemporaryDirectory() as d:
            p,reader,runtime,coverage=setup(Path(d))
            append(p,b'[SOCKET ACTION TIME');coverage.scan()
            with self.assertRaises(RuntimeError):coverage.handover(reader)
            coverage.scan()  # Empty subsequent read must not republish same path.
            append(p,b'OUT] complete\n');coverage.scan();coverage.handover(reader)
            self.assertEqual(reader.log_errors(),[])

    def test_unknown_marker_exception_rotation_truncation_and_bound_fail_closed(self):
        for payload in (b'Training error: BAD\n',b'Traceback (most recent call last):\nValueError: BAD\n'):
            with self.subTest(payload=payload),tempfile.TemporaryDirectory() as d:
                p,reader,runtime,coverage=setup(Path(d));append(p,payload)
                with self.assertRaises(RuntimeError):coverage.scan()
                self.assertEqual(next((Path(d)/'coverage').glob('*.bin')).read_bytes(),payload)
        for kind in ('rotate','truncate','bound'):
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as d:
                p,reader,runtime,coverage=setup(Path(d),b'baseline\n')
                if kind=='rotate':p.rename(p.with_suffix('.old'));p.write_bytes(b'new\n')
                if kind=='truncate':p.write_bytes(b'')
                if kind=='bound':append(p,b'x'*(M.MAX_INCREMENT+1))
                with self.assertRaises(RuntimeError):coverage.scan()

    def test_reconnect_real_reader_then_full60_and_no_deadline_extension(self):
        with tempfile.TemporaryDirectory() as d:
            directory=Path(d);p,reader,runtime,coverage=setup(directory)
            runtime.output=directory;runtime.job=dict(baseline_csv=dict(batch_size=4096,replay_sample_cap=8,replay_dropped=0),before=dict(bindings=dict(logs={str(p):dict(device=p.stat().st_dev,inode=p.stat().st_ino)})))
            runtime.start_request={'path':'start'};runtime.inspect=lambda phase:None;runtime.trainer_id=lambda:dict(pid=999)
            clock=types.SimpleNamespace(t=0.0)
            def row():
                return dict(client_count=192,csv=dict(utc='1970-01-01T00:01:41+00:00',batch_size=4096,replay_sample_cap=8,replay_dropped=0),
                    observed_unix_s=101+clock.t,exposure=dict(optimizer=dict(process_id=999),replay=dict(process_id=999)),log_errors=reader.log_errors())
            runtime.host.capture=row
            runtime.metrics.exposure_key=lambda v:v
            runtime.metrics.api_issues=lambda row,plan,previous=None:['new_runtime_log_error'] if row['log_errors'] else []
            base=Base();base.read_json=lambda pin:dict(unix_s=100)
            H=types.SimpleNamespace(ready_with_budget=lambda *args,**kwargs:dict(healthy=True))
            append(p,b'[SOCKET ACTION TIMEOUT] reconnect\n')
            with mock.patch.object(M.time,'monotonic',side_effect=lambda:clock.t),mock.patch.object(M.time,'sleep',side_effect=lambda s:setattr(clock,'t',clock.t+s)):
                result=M.reconnect_and_strict(runtime,base,H,{},600,coverage)
            self.assertGreaterEqual(clock.t,60)
            report=json.loads(Path(result['strict_runtime']['path']).read_text())
            self.assertGreaterEqual(report['end_monotonic_s']-report['start_monotonic_s'],60)
            self.assertEqual(report['original_deadline_monotonic_s'],600)
            self.assertTrue(all(not x['issues'] for x in report['observations']))
            self.assertIs(reader.log_errors.__func__,type(reader).log_errors)
            clock.t=0
            with mock.patch.object(M.time,'monotonic',side_effect=lambda:clock.t),self.assertRaises(RuntimeError):
                M.reconnect_and_strict(runtime,base,H,{},59,coverage)
            self.assertEqual(clock.t,0)  # No extension to obtain the required60s.

    def test_actual_saved_selector_keeps_failed_phase_and_zero_scope(self):
        root=M.R
        json_pin=lambda p:dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=len(p.read_bytes()),identity=dict(mode='0o444',uid=os.getuid(),nlink=1))
        failed_job=json_pin(root/'accepted-newgame-healthy-CE-maintenance-root-preparation-20261017/root-actual-job.json')
        original=json.loads(Path(failed_job['path']).read_text());failed_output=Path(original['transition']['output_directory'])
        job=dict(schema=M.SCHEMA,activation_authorized=True,failure_evidence=json_pin(M.FAILURE),
            failed_job=failed_job,failed_result=json_pin(failed_output/'result.json'),
            failed_startup_CPU=json_pin(failed_output/'startup-phase-CPU/cpu-report-readonly.json'),
            newest_CPU_job=json_pin(root/'accepted-newgame-failed-maintenance-newest-stopped-CPU-root-preparation-20261017/actual-newest-stopped-CPU-job.json'),
            newest_CPU_report=json_pin(root/'accepted-newgame-failed-maintenance-newest-stopped-CPU-root-execution-20261017/newest-stopped-CPU-report-readonly.json'),
            newest_CPU_release=json_pin(root/'accepted-newgame-failed-maintenance-newest-stopped-CPU-root-execution-20261017/root-original-newest-stopped-CPU-result-and-owned-release.json'),
            recovery_intent=dict(path='/synthetic_future/intent.json'),phase_id='synthetic_separate_recovery_CE',request_id='synthetic_recovery_start',
            startup_tag='synthetic_recovery_startup',output_directory='/synthetic_future/output',current_completed_request=dict(path=str(M.GAME/'models_dqn/managed_save.request.json.completed')),
            settings_lifecycle=dict(initial=dict(path=str(M.GAME/'models_dqn/game_settings.json'))),
            current_dropin=copy.deepcopy(original['transition']['original_dropin']))
        cache={}
        def read_pin(pin):
            return copy.deepcopy(cache[pin['path']]) if pin['path'] in cache else json.loads(Path(pin['path']).read_text())
        failed=read_pin(job['failed_result']);cpu=read_pin(job['newest_CPU_job']);owner=failed['failed_new_CE_retired']
        intent=dict(schema='robotron-accepted-newgame-failed-maintenance-forward-recovery-intent-v1',failed_job=job['failed_job'],
            failed_result=job['failed_result'],failure_evidence=job['failure_evidence'],owner=owner,
            newest_checkpoint={k:cpu['source'][k] for k in ('path','sha256','bytes')},phase_id=job['phase_id'],
            no_maintenance_retry=True,no_rollback=True,target_batch_size=4096,target_lr_scale=.5,strict_runtime_s=60,ready_s=600)
        cache[job['recovery_intent']['path']]=intent
        base=types.SimpleNamespace(MAX_SOURCE=2<<20,pin=lambda *a:None,read_json=read_pin,fingerprint=lambda *a:dict(sha256='4a1f6a3cc7c82d8c85e1af93ceac0ca7457663d5f5ba7c7d893e3c2b3003e26c'))
        adapter_path=M.GAME/'tools/kl_priority_mixture_proposal/raw_kl_sequential_trial_proposal/live_one_trial_installed_ce_revision2_proposal/run_raw_kl_transition.py'
        tree=ast.parse(adapter_path.read_text());node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='expected_start')
        clocks=('training_steps','optimized_samples','learner_frame_count','frame_count')
        ns=dict(four=lambda v:{k:v[k] for k in clocks});exec(compile(ast.Module(body=[node],type_ignores=[]),str(adapter_path),'exec'),ns)
        adapter=types.SimpleNamespace(PHASE_SHA='b2e732dc731b2b601f7499d2cafd5841896daf2b0713d496b98cb6b8d7279519',
            STRICT_SHA='9ef38e17e1b9eee3f6c43e40005812f2ebe3cff16d08bf61d3e820c2d41134c8',CLOCKS=clocks,
            triple=lambda p:{k:p[k] for k in ('path','sha256','bytes')},expected_start=ns['expected_start'])
        H=types.SimpleNamespace(immutable=lambda base,p:read_pin(p),SOCKET=M.GAME/'Scripts/dqn/socket_server.py',
            AFTER_SHA='4a1f6a3cc7c82d8c85e1af93ceac0ca7457663d5f5ba7c7d893e3c2b3003e26c')
        cfg,*_=M.validate(job,base,adapter,H)
        self.assertEqual(cfg['sources'],[])
        self.assertEqual(cfg['running_phase']['expected']['phase_id'],'ce4096_accepted_newgame_replay_boundary_fix_20261017')
        self.assertEqual(cpu['phase_snapshot']['observed_clients'],0)
        changed=copy.deepcopy(cpu);changed['phase_snapshot']['observed_clients']=192
        proof=read_pin(job['newest_CPU_report']);proof['root_job']=copy.deepcopy(changed)
        cache[job['newest_CPU_job']['path']]=changed;cache[job['newest_CPU_report']['path']]=proof
        with self.assertRaises(RuntimeError):M.validate(job,base,adapter,H)

    def test_default_is_read_free_and_current_scope_is_zero_client(self):
        with mock.patch.object(M,'load_helper',side_effect=AssertionError('load')),mock.patch.object(Path,'read_bytes',side_effect=AssertionError('read')):
            with contextlib.redirect_stdout(io.StringIO()) as output:self.assertEqual(M.main([]),0)
        self.assertIn('PLAN_ONLY',output.getvalue())
        text=(HERE/'run_forward_recovery.py').read_text()
        self.assertIn("fresh['observed_clients']==0",text)
        self.assertNotIn('runtime.stopped_checkpoint(',text)
        self.assertNotIn('sources.reconcile(',text)
        self.assertIn("intent['strict_runtime_s']==60",text)


if __name__=='__main__':unittest.main()
