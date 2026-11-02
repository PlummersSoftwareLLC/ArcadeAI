"""UNEXECUTED source-isolated stdlib metadata/order guards for future root use.

Only this small selector is imported. Saved JSON/source text is read, never any
checkpoint/replay referent. Process, unit, API, source-write, CPU and clock I/O is
strictly substituted; no real activation or numerical validation is performed.
"""
import ast
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import types
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('_healthy_diagnostic_guarded', HERE/'run_healthy_activation.py')
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def saved(path):
    path = Path(path)
    raw = path.read_bytes()
    return json.loads(raw)


def pin(name, digest='a'*64):
    return dict(path='/synthetic-future/'+name,sha256=digest,bytes=1,
        identity=dict(mode='0o444',uid=os.getuid(),nlink=1))


def metadata_pin(path):
    # Only explicitly named closed JSON leaves; never follow a model path.
    path = Path(path); data = path.read_bytes(); s = path.stat()
    return dict(path=str(path),sha256=hashlib.sha256(data).hexdigest(),bytes=len(data),identity=dict(
        device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,ctime_ns=s.st_ctime_ns,
        mode=oct(s.st_mode & 0o777),uid=s.st_uid,nlink=s.st_nlink))


def fixture():
    R = M.RUN
    entry_dir = R/'postaccepted-newgame-live8M-candidate-CPU-original01-root-execution-20261017'
    ep = metadata_pin(entry_dir/'candidate-CPU-report-readonly.json')
    erp = metadata_pin(entry_dir/'root-original-CPU-result-and-owned-release.json')
    entry = saved(ep['path']); rec = saved(R/'accepted-newgame-failed-maintenance-forward-recovery-20261017/result.json')
    # Original transition is only a field-layout seed, not healthy authority.
    seed = saved(R/'accepted-newgame-healthy-CE-maintenance-root-preparation-20261017/root-actual-job.json')['transition']
    cfg = copy.deepcopy(seed)
    cfg.update(before=copy.deepcopy(rec['healthy192']['binding']),running_phase=copy.deepcopy(rec['startup']['phase']),
        phase_id='synthetic_NEW_diagnostic_CE',request_id='synthetic_NEW_diagnostic_start',startup_tag='synthetic_NEW_startup',
        output_directory=str(R/'synthetic-future-output-not-created'))
    cfg['verifier']['context'] = copy.deepcopy(entry['root_job']['source_control_context'])
    cfg['static_pins'] = [p for p in cfg['static_pins'] if p['path'] not in {str(M.GAME/'Scripts/dqn'/x) for x in M.DELTAS}]
    cfg['sources'] = []
    for name,(old,new) in M.DELTAS.items():
        destination = str(M.GAME/'Scripts/dqn'/name)
        cfg['sources'].append(dict(destination=destination,before=None if old is None else dict(pin('old_'+name,old),path=destination),after=pin('after_'+name,new)))
    cfg['actor_masks'] = {str(a['pid']):list(range(72)) for a in cfg['before']['bindings']['actors']}
    cfg['worker_mask'] = list(range(72))
    # Authentic entry package/control .5 context, genuine new owner's phase and
    # synthetic future source staging/intent are intentionally distinct.
    rp = metadata_pin(M.RELEASE); gp = metadata_pin(M.REGRESSION); cp = metadata_pin(M.COMBINED); ip = pin('activation-intent')
    cfg['trial_core'] = ip
    owner = entry['root_job']['phase_snapshot']['owner']
    intent = dict(schema=M.INTENT_SCHEMA,owner=owner,running_phase=cfg['running_phase'],phase_id=cfg['phase_id'],sources=cfg['sources'],
        quality_release=rp,regression_result=gp,combined_manifest=cp,boot_newest_only=True,no_weight_or_optimizer_rollback=True,
        retain_original_fleet=True,target_batch_size=4096,target_lr_scale=.5,telemetry_environment={M.FLAG:'1'},fleet_actions_forbidden=True)
    job = dict(schema=M.SCHEMA,activation_authorized=True,transition=cfg,entry_CPU=ep,entry_CPU_release=erp,
        quality_release=rp,regression_result=gp,combined_manifest=cp,activation_intent=ip)
    values = {ep['path']:entry,erp['path']:saved(erp['path']),rp['path']:saved(rp['path']),gp['path']:saved(gp['path']),
        cp['path']:saved(cp['path']),ip['path']:intent}
    for suite in values[gp['path']]['suites']:values[suite['result']['path']] = saved(suite['result']['path'])
    for key in ('record','boot_verification'):
        p = cfg['running_phase'][key]; values[p['path']] = saved(p['path'])
    base = types.SimpleNamespace(MAX_JSON=4<<20,MAX_SOURCE=4<<20,pin=lambda *a:None,
        read_json=lambda p:copy.deepcopy(values[p['path']]),validate_python_binding=lambda *a,**kw:None)
    # Execute ONLY the exact pure phase-constructor AST during future root test.
    source = Path(cfg['helper_pins']['controller']['path']); tree = ast.parse(source.read_text())
    fn = next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name == 'expected_start')
    clocks = ('training_steps','optimized_samples','learner_frame_count','frame_count')
    ns = {'four':lambda value:{k:value[k] for k in clocks}}
    exec(compile(ast.Module(body=[fn],type_ignores=[]),str(source),'exec'),ns)
    adapter = types.SimpleNamespace(PHASE_SHA=M.HELPER_HASHES['phase_script'],STRICT_SHA=M.HELPER_HASHES['phase_strict'],
        V4=Path(cfg['helper_pins']['v4']['path']),FLAGS=('DQN_RECOMPUTED_CE_CAPTURE_DIR','DQN_EXECUTED_CE_TRACE_DIR'),
        triple=lambda p:{k:p[k] for k in ('path','sha256','bytes')},expected_start=ns['expected_start'],
        CANDIDATE={name:cfg['before']['bindings']['source_hashes'][str(M.GAME/'Scripts/dqn'/name)]
            for name in ('agent.py','training.py','loss_kernel.py','config.py','priority_phase.py')})
    H = types.SimpleNamespace(ADAPTER=source,immutable=lambda base,p:base.read_json(p))
    return job,base,adapter,H,values


class HealthyActivationContracts(unittest.TestCase):
    def test_real_closed_candidate192_phase_release_and43_positive(self):
        job,base,A,H,values = fixture()
        cfg,entry = M.validate(job,base,A,H)
        self.assertEqual(entry['root_job']['phase_snapshot']['observed_clients'],192)
        self.assertEqual(entry['root_job']['phase_snapshot']['owner']['pid'],2257565)
        self.assertEqual(len(M.check_sources(cfg,base)),62)
        self.assertNotEqual(cfg['insurance_verification'],job['entry_CPU'])
        self.assertNotEqual(cfg['running_phase']['record']['sha256'],cfg['running_phase']['expected']['phase_id'])
        self.assertEqual(values[job['quality_release']['path']]['C1_original_failed_audit_preserved'],True)

    def test_scope_current_owner_phase_recipe_release_and_original_fail_closed(self):
        for kind in ('unauthorized','old_release','foreign_owner','startup0','phase_as_hash','recipe2048','lr25','missing_original_guard','skip','wrong_entry_release','source_base_descriptor'):
            job,base,A,H,values = fixture();cfg=job['transition']
            if kind=='unauthorized':job['activation_authorized']=False
            if kind=='old_release':job['quality_release']['sha256']='f'*64
            if kind=='foreign_owner':cfg['before']['bindings']['worker']['trainer']['pid']+=1
            if kind=='startup0':values[job['entry_CPU']['path']]['root_job']['phase_snapshot']['observed_clients']=0
            if kind=='phase_as_hash':values[job['entry_CPU']['path']]['saved_priority_metric_phase']['phase_id']=cfg['running_phase']['record']['sha256']
            if kind=='recipe2048':cfg['before']['environment']['DQN_BATCH_SIZE']='2048'
            if kind=='lr25':values[job['entry_CPU']['path']]['held_recipe_context']['learning_control_lr_scale']=.25
            aggregate=values[job['regression_result']['path']]
            if kind=='missing_original_guard':aggregate['suites'].pop()
            if kind=='skip':values[aggregate['suites'][1]['result']['path']]['tests_skipped']=1
            if kind=='source_base_descriptor':aggregate['source_bases_still_unchanged'][0]['sha256']='0'*64
            if kind=='wrong_entry_release':values[job['entry_CPU_release']['path']]['CPU_report']=pin('unrelated-zero-report')
            with self.subTest(kind=kind),self.assertRaises((RuntimeError,KeyError)):M.validate(job,base,A,H)

    def test_exact_four_sources_new_helper_and_mutable_exclusions(self):
        for kind in ('old_reader','original_helper','extra','duplicate','helper_before','static_mutable','old61_wrong'):
            job,base,A,H,_=fixture();cfg=job['transition']
            if kind=='old_reader':cfg['sources'][2]['after']['sha256']='b8ca'+'0'*60
            if kind=='original_helper':cfg['sources'][3]['after']['sha256']='56cd'+'0'*60
            if kind=='extra':cfg['sources'].append(copy.deepcopy(cfg['sources'][0]))
            if kind=='duplicate':cfg['sources'][1]=copy.deepcopy(cfg['sources'][0])
            if kind=='helper_before':cfg['sources'][3]['before']=pin('existing_helper')
            if kind=='static_mutable':cfg['static_pins'].append(copy.deepcopy(cfg['sources'][0]['before']))
            if kind=='old61_wrong':cfg['before']['bindings']['source_hashes'][cfg['sources'][0]['destination']]='0'*64
            with self.subTest(kind=kind),self.assertRaises(RuntimeError):M.check_sources(cfg,base)

    def test_environment_shim_both_start_and_inspect_and_command_allowlist(self):
        seen=[]
        def selected(before,metric,record):
            seen.append(copy.deepcopy(before));return dict(before,DQN_PER_PRIORITY_METRIC=metric,DQN_PRIORITY_PHASE_RECORD=record['path'])
        A=types.SimpleNamespace(selected_environment=selected)
        with self.assertRaisesRegex(ValueError,'first-error'):
            with M.diagnostic_environment(A):
                self.assertEqual(A.selected_environment({},'ce',{'path':'phase'})[M.FLAG],'1')
                self.assertEqual(A.selected_environment({'HELD':'yes'},'ce',{'path':'phase'})['HELD'],'yes')
                raise ValueError('first-error')
        self.assertIs(A.selected_environment,selected);self.assertEqual(seen,[{}, {'HELD':'yes'}])
        trainer='robotron-managed-synthetic-trainer.service'
        for args in (('daemon-reload',),('start','--no-block',trainer),('stop','--no-block',trainer)):
            self.assertTrue(M.trainer_command_allowed(args,trainer))
        for args in (('start',trainer),('restart','--no-block',trainer),('start','--no-block',trainer.replace('trainer','fleet')),('startmame.sh',)):
            self.assertFalse(M.trainer_command_allowed(args,trainer))

    def test_actor_guard_real_function_detects_replacement_extra_masks_and_unpaused(self):
        actors=[dict(pid=1000+i,client_slot=i,starttime_ticks=100+i) for i in range(192)]
        state=types.SimpleNamespace(actors=copy.deepcopy(actors),global_pids={a['pid'] for a in actors},mask=list(range(72)),stopped=True,supervisor=99)
        class P:
            def __init__(self,value):self.value=str(value);self.name=self.value.rstrip('/').split('/')[-1]
            def __truediv__(self,value):return P(self.value+'/'+str(value))
            def read_text(self):
                if self.value=='/proc/500/stat':return 'supervisor-stat'
                raise AssertionError('unexpected read '+self.value)
            def read_bytes(self):
                if self.value.endswith('/cmdline'):return b'/synthetic/mame\0robotron\0'
                raise AssertionError('unexpected bytes '+self.value)
            def iterdir(self):
                if self.value!='/proc':raise AssertionError(self.value)
                return [P('/proc/'+str(x)) for x in sorted(state.global_pids)]
        host=types.SimpleNamespace(unit=lambda name:dict(MainPID='500',ActiveState='active',ControlGroup='/fleet'),actor_stopped=lambda a:state.stopped)
        metrics=types.SimpleNamespace(identity=types.SimpleNamespace(stat_fields=lambda text:dict(starttime_ticks=state.supervisor)),
            discover_fleet_actors=lambda group:(state.actors,set()))
        runtime=types.SimpleNamespace(host=host,metrics=metrics,job=dict(fleet_unit='fleet',before=dict(fleet=dict(MainPID='500',ControlGroup='/fleet'),
            supervisor_start_ticks=99,bindings=dict(actors=actors,fleet_cgroup='/fleet')),actor_masks={str(a['pid']):list(range(72))for a in actors}))
        with mock.patch.object(M,'Path',P),mock.patch.object(M.os,'sched_getaffinity',side_effect=lambda pid:state.mask):
            self.assertEqual(M.actor_guard(runtime,paused=True)['actor_count'],192)
            for kind in ('replacement','extra','mask','supervisor','unpaused'):
                original=copy.deepcopy(state.__dict__)
                if kind=='replacement':state.actors[0]['starttime_ticks']+=1
                if kind=='extra':state.global_pids.add(9999)
                if kind=='mask':state.mask=[0]
                if kind=='supervisor':state.supervisor+=1
                if kind=='unpaused':state.stopped=False
                with self.subTest(kind=kind),self.assertRaises(RuntimeError):M.actor_guard(runtime,paused=True)
                state.__dict__.update(original)

    def route(self, failure=None):
        events=[]; clocks={k:100 for k in ('training_steps','optimized_samples','learner_frame_count','frame_count')}
        owner=dict(pid=100,starttime_ticks=1,unit='trainer',invocation_id='a'*32,cgroup='/trainer')
        new=dict(owner,pid=200,starttime_ticks=2,invocation_id='b'*32)
        raw=dict(clocks,client_count=192,training_enabled=True,measurement_active=False,managed_experiment='held',lr=2.5e-5,ts=10,
            host_pipeline=dict(learning_exposure=dict(optimizer=dict(process_id=100,epoch='old'),replay=dict(process_id=100,epoch='old'))))
        initial=dict(clocks,ts=9,exposure=copy.deepcopy(raw['host_pipeline']['learning_exposure']))
        cfg=dict(experiment='held',running_phase=dict(record={'path':'phase'}),before=dict(bindings=dict(actors=[{'pid':1}],logs={'log':{}})),trainer_unit='trainer',bank_spec={})
        host=types.SimpleNamespace(paused=[],known_trainer=None,metric_host=types.SimpleNamespace(configure_logs=lambda logs:events.append('arm_runtime')))
        host.begin_transition_logs=lambda *a:events.append('arm_transition')
        def pause(plan):events.append('pause_original');host.paused=[{'pid':1}]
        host.pause=pause;host.wait_paused=lambda:events.append('wait_pause');host.unit=lambda unit:dict(MainPID='200')
        host.signal_actor=lambda actor,sig:events.append(('signal',actor['pid'],sig))
        metrics=types.SimpleNamespace(exposure_key=lambda v:v,block_restore_signals=contextlib.nullcontext)
        runtime=types.SimpleNamespace(job=cfg,host=host,metrics=metrics,output=Path('/synthetic-no-IO'),insured=owner,floor=dict(clocks),initial_api=initial,
            start_request=None,cpu_attempts={},pending=None,initial=lambda:events.append('initial') or dict(bindings=dict(logs={'log':{}}),trainer_stdout={}),
            raw_api=lambda:copy.deepcopy(raw),inspect=lambda phase:events.append('inspect_'+phase))
        def stop(expected=None):events.append('stop_old' if runtime.start_request is None else 'stop_new');return owner if runtime.start_request is None else new
        runtime.stop_owned=stop
        proof=dict(status='PASS',phase_metadata_verified=True,held_recipe_context=dict(batch_size=4096,learning_control_lr_scale=.5),
            root_job=dict(phase_snapshot=dict(purpose='newest_stopped',observed_clients=192)),saved_priority_metric_phase=dict(phase_id='old',metric='ce',valid=True),clocks=clocks)
        def newest(*a):
            events.append('newest_CPU')
            if failure=='newest':raise RuntimeError('first-newest-failure')
            return dict(source={'path':'NEW-latest'},verification={'path':'proof'})
        runtime.stopped_checkpoint=newest
        runtime.startup_snapshot=lambda raw:events.append('startup_CPU0') or dict(phase_CPU={'path':'startup-report'})
        runtime.absence=lambda:events.append('absence')
        runtime.banks=types.SimpleNamespace(stopped_state=lambda spec:events.append('banks_stopped') or {},assert_unchanged=lambda *a:events.append('banks_unchanged'))
        def reconcile(*a):runtime.absence();events.append('WRITE_four')
        sources=types.SimpleNamespace(stage=lambda:events.append('stage'),reconcile=reconcile)
        def resume(host):events.append('CONT_original');host.paused=[];return dict(failures=[],all_matching_actors_resumed=True)
        def read(pin):
            if pin['path']=='proof':return proof
            if pin['path']=='phase':return dict(phase_id='old')
            if pin['path']=='start':return dict(monotonic_s=0)
            raise AssertionError('unexpected metadata '+str(pin))
        base=types.SimpleNamespace(read_json=read,resume_all=resume,publish=lambda path,value:dict(path=str(path)))
        A=types.SimpleNamespace(CLOCKS=tuple(clocks),clock_max=lambda a,b:{k:max(a[k],b[k])for k in clocks},
            source_state=lambda sources:{'all_after':True},zero_replay=lambda raw,pid:events.append('zero_replay'))
        def start(rt,adapter):
            events.append('ONE_start');rt.start_request={'path':'start'};rt.host.known_trainer={'pid':200};rt.record_pin={'path':'new-phase'}
            raw['client_count']=0;return new
        def ready(*a,**kw):events.append('ready0');return {}
        H=types.SimpleNamespace(start_repair_CE4096=start,ready_with_budget=ready,archive_report=lambda *a:dict(path='readonly-startup'))
        def coverage(*a):events.append('coverage_at_original_offset');return object()
        def reconnect(*a):
            events.append('handover_strict60')
            if failure=='strict':raise RuntimeError('first-strict-failure')
            return dict(healthy192={})
        C=types.SimpleNamespace(TransitionCoverage=coverage,reconnect_and_strict=reconnect)
        with mock.patch.object(M,'actor_guard',side_effect=lambda *a,**kw:events.append('actors_paused' if kw.get('paused') else 'actors_exact') or {}):
            outcome=M.activate(runtime,sources,base,A,H,C)
        return events,outcome

    def test_real_activation_order_newest_before_write_and_no_automatic_retry(self):
        events,result=self.route()
        self.assertEqual(result['status'],'READY_HEALTHY_DIAGNOSTIC_ACTIVATION')
        order=('initial','stage','arm_transition','pause_original','stop_old','newest_CPU','banks_stopped','WRITE_four','ONE_start','ready0','startup_CPU0','coverage_at_original_offset','CONT_original','handover_strict60')
        self.assertEqual([events.index(x) for x in order],sorted(events.index(x)for x in order))
        self.assertEqual(events.count('ONE_start'),1);self.assertEqual(events.count('WRITE_four'),1)
        self.assertEqual(events[-1],'CONT_original')
        events,result=self.route('newest')
        self.assertEqual(result['status'],'FAILED');self.assertNotIn('WRITE_four',events);self.assertNotIn('ONE_start',events)
        self.assertEqual(events[-1],'CONT_original');self.assertIn('first-newest-failure',result['error'])
        events,result=self.route('strict')
        self.assertEqual(result['status'],'FAILED');self.assertEqual(events.count('ONE_start'),1)
        self.assertIn('stop_new',events);self.assertEqual(events[-1],'CONT_original');self.assertIn('first-strict-failure',result['error'])

    def test_default_PLAN_has_no_source_reads_or_loads(self):
        with mock.patch.object(M,'load',side_effect=AssertionError('load')),mock.patch.object(Path,'read_bytes',side_effect=AssertionError('read')):
            with contextlib.redirect_stdout(io.StringIO()) as out:self.assertEqual(M.main([]),0)
        self.assertIn('PLAN_ONLY',out.getvalue())


if __name__=='__main__':
    unittest.main()
