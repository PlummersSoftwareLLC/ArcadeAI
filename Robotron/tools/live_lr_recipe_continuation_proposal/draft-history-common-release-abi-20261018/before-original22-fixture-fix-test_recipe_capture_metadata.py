"""Deferred metadata and injected-I/O orchestration guards, not runtime proof.

Future root execution imports only the pinned stdlib proposal modules. The
historical positive fixture reads authenticated CLOSED JSON and archived text,
never checkpoint referents. Runtime paths, health, requests and control writes
are strict substitutes in the route fixtures. No numerical verifier is loaded.
"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
RUN = Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26')
CAPTURE_SHA = '96f7035b30e827c1d16cedb9073a6c89d7ccee6dea1e95b9b1433d34529dfbae'
BINDING_SHA = 'c50dae942b52a68f293c2567f5a8c822de0e7d05018eb251332676681ac48556'
RECIPE_SHA = 'f11e4c8d6725c04c4495b416318713f675ba9305ffe6f7c4009a3bff9b860d0e'
OLD_CASE = RUN / 'postdiagnostic-live8M-fresh-root-case-corrected-archive-bindings-20261018/root-case.json'
OLD_RESULT = RUN / 'postdiagnostic-live8M-candidate-trial01-20261018/result.json'
RELEASE = RUN / 'postdiagnostic-live8M-candidate-root-preparation-20261018/root-final779-not-improved-campaign-disposition-and-source-freeze-release-20261018.json'


def source_module(filename, expected, name):
    p = HERE / filename
    if hashlib.sha256(p.read_bytes()).hexdigest() != expected:
        raise AssertionError('Proposal source changed')
    spec = importlib.util.spec_from_file_location(name, p)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def json_bytes(path, expected):
    if path.suffix != '.json':
        raise AssertionError('Closed JSON only; no model referents')
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise AssertionError('Closed metadata changed')
    return json.loads(raw)


def pin(name, value=None):
    raw = json.dumps(value or {}, sort_keys=True).encode()
    return dict(path='/synthetic/' + name, sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw),
                identity=dict(device=1, inode=10, bytes=len(raw), mtime_ns=1, ctime_ns=1,
                              mode='0o444', uid=1001, nlink=1))


class NoIOPath(type(Path())):
    """Only validate's future output/tag path checks; never opens model paths."""
    def exists(self): return False
    def resolve(self, strict=False):
        if strict: raise AssertionError('No filesystem resolution in synthetic validation')
        return self


class RecipeCaptureContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.C = source_module('capture_candidate.py', CAPTURE_SHA, '_recipe_capture_guard')
        cls.R = source_module('recipe.py', RECIPE_SHA, '_recipe_capture_common')
        cls.B = source_module('quality_bindings.py', BINDING_SHA, '_recipe_capture_bindings')
        cls.old_case = json_bytes(OLD_CASE, '1365b1a20032b4698f8dc3c5da23dc561eb6d9f5e3f7d14abcee3fc319f50129')
        cls.old_result = json_bytes(OLD_RESULT, 'cb321aab0078cd343c1fe72503f7b3f707431ca4f3d7921306dba567c46c34a2')
        cls.release_pin = cls.C.fingerprint(RELEASE)[1]
        if cls.release_pin['sha256'] != '567c32a2d89efca4b0dbd972eea0425880d5005ddd0cdf863952367fc24c0e9a':
            raise AssertionError('Closed not-improved release changed')

    def context(self):
        case = dict(activation=copy.deepcopy(self.old_case['activation']), source_freeze_release=self.release_pin)
        with patch.object(self.C, 'load', side_effect=lambda name: self.R if name == 'recipe' else self.fail(name)):
            return self.C.activation_context(case, None)

    def fixture(self, scale=.25):
        C = self.C; context = self.context(); baseline = C.pinned(self.old_case['runtime_baseline'])
        baseline_pin = pin('new-runtime-baseline.json'); ready_pin = pin('new-readiness.json')
        old_job = C.pinned(self.old_result['cpu_job'])
        archived = old_job['source_control_context']['archived_control']
        control = C.pinned(archived)
        control_raw = C.pinned(archived, raw_only=True)
        self.assertEqual(hashlib.sha256(control_raw).hexdigest(), self.old_case['control_before']['sha256'])
        now = context['quality_release']['main_health']['ts'] + 1
        ready = dict(baseline, status='PASS', observed_unix_s=now, resources=dict(
            GPU0_free_bytes=15 << 30, GPU0_no_compute_owner=True, GPU1_main_only=True,
            port9999_clear=True, lease_free=True, no_competing_helpers=True,
            no_private_cgroup_tmpfs_processes=True, no_pending_save=True, owned_units_released=True))
        case = dict(schema=C.SCHEMA, capture_authorized=True, activation=copy.deepcopy(self.old_case['activation']),
            source_freeze_release=self.release_pin, runtime_baseline=baseline_pin, readiness=ready_pin,
            control_before=copy.deepcopy(self.old_case['control_before']), completed_slot=self.old_case['completed_slot'],
            experiment='synthetic-new-lr-label', recipe=self.R.for_scale(scale), tags=dict(barrier='synthetic-barrier',endpoint='synthetic-endpoint'),
            window=dict(policy=dict(learner_frames=8000000,learner_accepted=8000000,poll_s=1,API_age_s=5,
                pipeline_age_s=5,unobservable_s=30,no_applied_s=60,cutoff_s=3600),preparation_timeout_s=180),
            output_directory=str(RUN/'synthetic-new-unselected-lr-output'),cpu_python='/synthetic/python')
        original = C.pinned
        def reader(p, raw_only=False):
            if p == baseline_pin: return copy.deepcopy(baseline)
            if p == ready_pin: return copy.deepcopy(ready)
            return original(p, raw_only=raw_only)
        modules = dict(recipe=self.R,observer=SimpleNamespace(POLICY={k:v for k,v in case['window']['policy'].items() if k!='cutoff_s'}),
                       entry=SimpleNamespace(slot_guard=lambda c,f: None))
        return case, context, baseline, reader, modules, now, control_raw, control

    def test_real_closed_activation_and_not_improved_release_remain_distinct(self):
        context = self.context()
        self.assertEqual(context['owner'], self.C.ACTUAL_OWNER)
        self.assertEqual(context['phase']['record']['sha256'], self.C.FOUNDER)
        self.assertIs(context['quality_release']['candidate_qualified'], False)
        self.assertIs(context['quality_release']['both_independent_candidate_gates_pass'], False)
        self.assertEqual(context['historical_report']['root_job']['phase_snapshot']['observed_clients'], 0)
        self.assertEqual(context['historical_report']['held_recipe_context']['optimizer_lr'], 2.5e-5)
        case = dict(activation=self.old_case['activation'], source_freeze_release=self.release_pin)
        original = self.C.pinned
        bad = copy.deepcopy(context['quality_release']); bad['original192actors_preserved'] = True
        with patch.object(self.C,'load',return_value=self.R), patch.object(self.C,'pinned',side_effect=lambda p:bad if p==self.release_pin else original(p)):
            with self.assertRaises(ValueError): self.C.activation_context(case, None)

    def test_real_validate_accepts_fresh_shapes_for_both_recipes_and_refuses_replacements(self):
        C=self.C
        for scale in (.25,.5):
            case,context,baseline,reader,modules,now,raw,control=self.fixture(scale)
            def check(value):
                with patch.object(C,'Path',NoIOPath),patch.object(C,'activation_context',return_value=context), \
                     patch.object(C,'pinned',side_effect=reader),patch.object(C,'fingerprint',return_value=(raw,case['control_before'])), \
                     patch.object(C.time,'time',return_value=now):
                    return C.validate(value,NoIOPath(value['output_directory']),modules,object())
            self.assertEqual(check(case)['recipe'],self.R.for_scale(scale))
            for mutate in (lambda c:c['recipe'].update(scheduled_lr=9.),
                           lambda c:c['window']['policy'].update(learner_accepted=6000000),
                           lambda c:c['tags'].update(endpoint=c['tags']['barrier'])):
                bad=copy.deepcopy(case);mutate(bad)
                with self.assertRaises((RuntimeError,ValueError)):check(bad)
            bad=copy.deepcopy(baseline);bad['actors'][0]['starttime_ticks']+=1
            with patch.object(C,'Path',NoIOPath),patch.object(C,'activation_context',return_value=context), \
                 patch.object(C,'pinned',side_effect=lambda p:bad if p==case['runtime_baseline'] else reader(p)), \
                 patch.object(C,'fingerprint',return_value=(raw,case['control_before'])),patch.object(C.time,'time',return_value=now):
                with self.assertRaises(ValueError):C.validate(case,NoIOPath(case['output_directory']),modules,object())

    def test_default_and_preflight_never_call_run_or_write(self):
        C=self.C
        with patch('builtins.open',side_effect=AssertionError('default read')):
            self.assertEqual(C.main([]),0)
        case,context,baseline,reader,modules,now,raw,control=self.fixture()
        context.update(baseline=baseline,env={},resources={},control=control)
        source_pin=pin('source.py');case_pin=pin('case.json');source_pin['identity']['mode']='0o444'
        api={k:100 for k in C.CLOCKS};seen=[]
        health=SimpleNamespace(check_health=lambda label,lr:(seen.append((label,lr)) or (b'raw',api)))
        modules.update(capture=SimpleNamespace(Files=lambda ops:object(),four=lambda value:value),ops=object(),driver=object(),phase=object(),snapshot=object())
        modules['observer'].configure_recipe=lambda recipe:None
        modules['entry'].EntryHealth=lambda *args:health
        with patch.object(C,'fingerprint',side_effect=lambda path:(json.dumps(case).encode(),case_pin) if str(path)=='/synthetic/case.json' else (b'source',source_pin)), \
             patch.object(C,'load',side_effect=lambda name:modules[name]),patch.object(C,'validate',return_value=context), \
             patch.object(C,'run',side_effect=AssertionError('preflight must not run')):
            self.assertEqual(C.main(['--preflight-only','--case','/synthetic/case.json','--output',case['output_directory'],
                '--expected-case-sha256',case_pin['sha256'],'--expected-source-sha256',source_pin['sha256']]),0)
        self.assertEqual(seen,[(control['experiment'],2.5e-5)])

    def test_real_save_once_uses_fresh_api_identity_and_carried_completion(self):
        C=self.C;effects=[];fresh={k:300 for k in C.CLOCKS};fresh['marker']='fresh-object'
        files=SimpleNamespace(raw_api=None,api=None);completed=pin('before.json');after=pin('after.json')
        job=dict(experiment='new-label',tags=dict(barrier='new-barrier',endpoint='new-endpoint'))
        context=dict(recipe=self.R.for_scale(.25),owner=C.ACTUAL_OWNER,phase={'record':pin('phase.json')},startup_tag='old-startup')
        health=SimpleNamespace(hashes={},check_health=lambda label,lr:(effects.append(('health',label,lr)) or (b'fresh',fresh)))
        class Runtime:
            def __init__(self,*args):self.current_completed=completed;self.publications=[]
            def request_guard(self):effects.append('request-guard')
        class Snapshot:
            def __init__(self,adapter,fs,runtime,spec,out):
                self.completed=after;self.state='PENDING';self.error=None;self.runtime=runtime;self.tag=spec['tag']
            def start(self,api,floor):
                if api is not fresh or files.api is not fresh or files.raw_api!=b'fresh':raise AssertionError('Stale trigger')
                effects.append(('start',self.tag,dict(floor)));self.state='COMPLETE';self.runtime.current_completed=after
            def freeze(self,**kwargs):effects.append(('freeze',kwargs));return dict(source=pin('endpoint.pt'))
        def forbidden(*a,**kw):raise AssertionError('Unexpected replay/owner/action callback')
        capture=SimpleNamespace(CaptureRuntime=Runtime,four=lambda api:{k:api[k] for k in C.CLOCKS},
            triple=forbidden,request_identity=forbidden,publish_request=forbidden)
        modules=dict(ops=object(),capture=capture,snapshot=SimpleNamespace(Snapshot=Snapshot),
            driver=SimpleNamespace(Driver=SimpleNamespace(slot_guard=lambda obj:effects.append('slot'))))
        runner=C.Continuation(dict(job,completed_slot=completed,control_before=pin('control.json')),pin('case.json'),PurePosixPath('/synthetic'),modules,files,context,health)
        _,_,_,floor=runner.save_once('endpoint',{k:200 for k in C.CLOCKS})
        self.assertEqual(floor,{k:300 for k in C.CLOCKS});self.assertEqual(runner.expected_completed,after)
        self.assertEqual(sum(isinstance(x,tuple) and x[0]=='start' for x in effects),1)
        self.assertIn(('freeze',dict(purpose='candidate',phase=context['phase'])),effects)

    def test_exact_transition_barrier_and_saved_lr_context_join(self):
        B=self.B;recipes=self.R;owner=self.C.ACTUAL_OWNER
        for scale in (.25,.5):
            selected=recipes.for_scale(scale);before=dict(experiment='old',lr_scale=.5,epsilon_ramp=dict(start=.1,end=.1))
            after=dict(before,experiment='new',lr_scale=scale);before_pin=pin('before.json',before);target=pin('target.json',after)
            live_before=dict(before_pin,path='/synthetic/live-control.json');live_after=dict(target,path=live_before['path'])
            phase=dict(record=pin('phase.json'));slot=pin('old-slot.json');newslot=pin('barrier-slot.json');request=pin('pending.json')
            clock=dict(boot_id='boot',monotonic_s=10,wall_s=100)
            acquisition=dict(tag='barrier',owner_before=owner,owner_after=owner,phase_record_sha256=phase['record']['sha256'],
                completed_slot_transition=dict(before=dict(actual_pin=slot),after=dict(actual_pin=newslot),request=dict(actual_pin=request)))
            acq=pin('barrier-acquisition.json',acquisition)
            change=dict(before=live_before,after=live_after,archive=target,completed_clock=clock)
            barrier=dict(frozen=dict(acquisition=acq),completed_slot=newslot,completed_clock=clock,
                request_publications=[dict(tag='barrier',pin=request)])
            change_pin=pin('transaction.json',change);barrier_pin=pin('barrier.json',barrier)
            case=dict(recipe=selected,control_before=live_before,tags=dict(barrier='barrier'),completed_slot=slot)
            result=dict(current_phase=phase,original_control_archive=before_pin,control_after=target,control_transition=change_pin,barrier=barrier_pin)
            job=dict(experiment='new',phase_snapshot=dict(owner=owner),source_control_context=dict(archived_control=target,held_recipe_context=recipes.held_context(selected,recipes.HELD_50)))
            window=dict(proofs=dict(control_transition=change_pin,barrier=barrier_pin,control=target),post_control_barrier_clock=clock)
            def reader(p):
                for pp,v in ((before_pin,before),(target,after),(acq,acquisition)):
                    if p==pp:return copy.deepcopy(v)
                raise AssertionError('Unexpected metadata dependency')
            with patch.object(B,'load_selector',return_value=SimpleNamespace(load=lambda name:recipes)):
                self.assertEqual(B.check_transition(case,result,job,window,change,barrier,reader),after)
                bad=copy.deepcopy(job);bad['source_control_context']['held_recipe_context']=recipes.held_context(recipes.for_scale(.5 if scale==.25 else .25),recipes.HELD_50)
                with self.assertRaises(ValueError):B.check_transition(case,result,bad,window,change,barrier,reader)
                bad=copy.deepcopy(barrier);bad['request_publications'].append(dict(tag='extra',pin=request))
                with self.assertRaises(ValueError):B.check_transition(case,result,job,window,change,bad,reader)

    def test_real_run_order_and_unknown_transaction_failure_never_retry_or_restore(self):
        C=self.C;events=[];values={};selected=self.R.for_scale(.25)
        # Real selected f9 method requires both arguments; the route fake below
        # keeps that exact signature, and its delegation is exercised directly.
        entry_path=Path('/home/dave/source/repos/ArcadeAI/Robotron/tools/kl_priority_mixture_proposal/raw_kl_sequential_trial_proposal/lr25_prechange_entry_capture_proposal/capture_entry.py')
        entry_raw=entry_path.read_bytes()
        self.assertEqual(hashlib.sha256(entry_raw).hexdigest(),'f9eb356ee7d43d549a0e7ffe504afc20c4a717c39890ac4a79d414b9b8bc8003')
        entry_spec=importlib.util.spec_from_file_location('_actual_f9_health_signature_guard',entry_path)
        entry=importlib.util.module_from_spec(entry_spec);entry_spec.loader.exec_module(entry)
        forwarded=[]
        health_holder=SimpleNamespace(driver=SimpleNamespace(Driver=SimpleNamespace(check_health=lambda self,label,lr:forwarded.append((label,lr)))))
        entry.EntryHealth.check_health(health_holder,None,None)
        self.assertEqual(forwarded,[(None,None)])
        before=dict(experiment='old',lr_scale=.5,epsilon_ramp=dict(start=.1,end=.1))
        case=dict(experiment='new',recipe=selected,control_before=pin('live-control.json'),completed_slot=pin('old-slot.json'),
            tags=dict(barrier='barrier',endpoint='endpoint'),source_freeze_release=pin('release.json'),
            runtime_baseline=pin('baseline.json'),readiness=pin('ready.json'),activation=dict(result=pin('activation.json'),adoption=pin('adoption.json')),
            window=dict(preparation_timeout_s=180,policy=dict(cutoff_s=3600)),cpu_python='/synthetic/python')
        context=dict(owner=C.ACTUAL_OWNER,phase=dict(record=pin('phase.json')),baseline={},env={},resources={},
            historical_floor={k:100 for k in C.CLOCKS},control=before,raw_control=json.dumps(before).encode(),recipe=selected)
        class Output(PurePosixPath):
            def mkdir(self,**kwargs):events.append(('mkdir',str(self)))
        out=Output('/synthetic/new-output')
        class Files:
            def __init__(self,ops):pass
            def fsync_directory(self,path):events.append(('fsync',str(path)))
            def fingerprint(self,path,*args):return pin(Path(path).name)
        def publish(path,value):values[str(path)]=copy.deepcopy(value);events.append(('publish',Path(path).name));return pin(Path(path).name,value)
        def write(path,raw):events.append(('write',Path(path).name));return dict(pin(Path(path).name),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw))
        ops=SimpleNamespace(publish=publish,write_bytes=write)
        def api(n):return dict({k:n for k in C.CLOCKS},managed_experiment='new',lr=1.25e-5,ts=200,pipeline_snapshot_age_s=0)
        health=SimpleNamespace(hashes={},check_health=lambda label,lr:(b'raw',api(700)))
        clock=lambda:dict(boot_id='boot',monotonic_s=100,wall_s=100)
        runtime=SimpleNamespace(publications=[dict(tag='tag')],request_guard=lambda:events.append('request-guard'),trainer_id=lambda:C.ACTUAL_OWNER)
        class Runner:
            fail=False
            def __init__(self,*args):self.pending=None;self.expected_completed=case['completed_slot'];self.control_pin=pin('target.json')
            def slot_guard(self):events.append('slot')
            def replace_control(self,raw,name):
                events.append(('control',json.loads(raw)))
                if self.fail:raise OSError('unknown transaction outcome')
                return pin('target.json')
            def save_once(self,stage,floor):
                events.append(('save',stage,dict(floor)));self.expected_completed=pin(stage+'-slot.json')
                snapshot=SimpleNamespace(raw_pin=pin(stage+'-trigger.json'),owner=C.ACTUAL_OWNER,owner_after=C.ACTUAL_OWNER,transition={})
                frozen=dict(source=pin(stage+'.pt'),verification_copy=pin(stage+'-copy.pt'),acquisition=pin(stage+'-acq.json'))
                return snapshot,runtime,frozen,{k:600 for k in C.CLOCKS}
        normal=dict(unclassified=0,optimizer=dict(applied=10),learner_accepted=100,accepted=100,clocks={k:500 for k in C.CLOCKS})
        def poll(job,**callbacks):
            events.append('poll-first-durable')
            self.assertEqual(callbacks['get_owner'](),C.ACTUAL_OWNER);self.assertTrue(callbacks['get_evidence']()['ok'])
            return dict(status='LATCH_DURABLE',candidate_requests_allowed=1,
                observation=dict(first_eligible_observation={k:550 for k in C.CLOCKS}))
        observer=SimpleNamespace(SCHEMA='synthetic-window',configure_recipe=lambda r:None,normalise=lambda api:copy.deepcopy(normal),
            validate_job=lambda *args:events.append('validate-B'),ReceiptJournal=lambda **kw:SimpleNamespace(emit=lambda e:None,failure=None),
            poll=poll,encoded=lambda value:json.dumps(value).encode())
        modules=dict(entry=SimpleNamespace(EntryHealth=lambda *args:health,slot_guard=lambda *args:events.append('initial-slot')),
            driver=SimpleNamespace(clock=clock),ops=ops,capture=SimpleNamespace(Files=Files,four=lambda api:{k:api[k] for k in C.CLOCKS}),
            observer=observer,phase=object(),recipe=self.R)
        with patch.object(C,'validate',return_value=context),patch.object(C,'Continuation',Runner), \
             patch.object(C,'build_CPU_job',side_effect=lambda *args:(events.append('seal-CPU-job') or {})):
            result=C.run(case,pin('case.json'),out,modules)
        self.assertEqual(result['status'],'CAPTURED_PENDING_ROOT_CPU')
        self.assertEqual([e[1] for e in events if isinstance(e,tuple) and e[0]=='save'],['barrier','endpoint'])
        self.assertLess(events.index('validate-B'),events.index('poll-first-durable'))
        self.assertLess(events.index('poll-first-durable'),events.index('seal-CPU-job'))
        self.assertTrue(result['hold_recipe_through_quality']);self.assertFalse(result['restored_control'])
        events.clear();Runner.fail=True
        with patch.object(C,'validate',return_value=context),patch.object(C,'Continuation',Runner):
            failed=C.run(case,pin('case.json'),out,modules)
        self.assertEqual(failed['status'],'FAILED');self.assertIsNone(failed['control_changed'])
        self.assertTrue(failed['manual_control_review']);self.assertFalse(failed['automatic_restoration'])
        self.assertEqual(sum(isinstance(e,tuple) and e[0]=='control' for e in events),1)
        self.assertFalse(any(isinstance(e,tuple) and e[0]=='save' for e in events))


if __name__ == '__main__':
    unittest.main()
