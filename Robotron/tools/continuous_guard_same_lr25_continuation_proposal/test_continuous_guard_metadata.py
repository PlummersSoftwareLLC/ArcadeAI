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
CAPTURE_SHA = 'ca6b29903f0330d2c7c989bf2e881b41f1af3fe3bf14ce4b010827b8d57e0eed'
BINDING_SHA = '2934df1534c1ff82fdd30e0dec930146fdeb74c2589547abd76967df3fe40989'
GUARD_SHA = 'f157895d90707fc725bda2381c9422c6e9ac22ab924597551d0d4d1f2d973556'
RECIPE_SHA = '9bc9a24f5f36c5dbe4f6385c1f47a5698bcda0bd6178f7546b263ee136aa1c3a'
OLD_CASE = RUN / 'LR25-continuation-original01-root-preparation-20261018/original01-capture-case.json'
OLD_RESULT = RUN / 'LR25-continuation-capture-trial01-20261018/result.json'
RELEASE = RUN / 'LR25-continuation-original01-root-preparation-20261018/root-confirmed845-protected-canonical-adoption-and-source-freeze-release-20261018.json'
BASELINE = RUN / 'same-LR25-914M-quality-runtime-original01-20261018/runtime-baseline.json'
PRIOR_BINDING = RUN / 'LR25-continuation-original01-root-preparation-20261018/actual-LR25-845M-quality-binding.json'
PRIOR_PLAN = RUN / 'LR25-continuation-original01-root-preparation-20261018/actual-LR25-845M-native-plan-readonly-copy.json'


def source_module(filename, expected, name):
    p = HERE / filename
    if hashlib.sha256(p.read_bytes()).hexdigest() != expected:
        raise AssertionError('Proposal source changed')
    spec = importlib.util.spec_from_file_location(name, p)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def json_bytes(path, expected):
    if path.suffix != '.json' or not path.is_relative_to(RUN):
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
        cls.G = source_module('effective_provenance.py', GUARD_SHA, '_guard_provenance_metadata')
        cls.R = source_module('recipe.py', RECIPE_SHA, '_recipe_capture_common')
        cls.B = source_module('quality_bindings.py', BINDING_SHA, '_recipe_capture_bindings')
        cls.old_case = json_bytes(OLD_CASE, '1c9849a389294ab1f65989cb3ae56bbf1de3618f15674b0e0abbbba50055676c')
        cls.old_result = json_bytes(OLD_RESULT, 'e21df01b2133f0b4c7cd27c890524e7df0faad17b93c1fb2dd14e29f0aab6aaa')
        cls.closed_baseline = json_bytes(BASELINE, 'b0bef7656ad6215c364fc0caf521612b087ccc359f2a6460bfd4b046c2c893c9')
        cls.immediate_binding=json_bytes(RUN/'same-LR25-continuation-original01-root-preparation-20261018/actual914M-quality-binding.json','fde2f3b3a23f407f6473bb75594d326229da22cef15290ef2186c74e2680c232')
        cls.prior_binding = json_bytes(PRIOR_BINDING, 'b98dd3f00ef3961f36a2e9748b55c96751411e3945f740cee2b74d8c2bdd16c3')
        cls.prior_plan = json_bytes(PRIOR_PLAN, '8ac7c5729ca5d53edcbf02ddd61e9e8377b8b1d7f4d43648c2fda7ab263b0c7d')
        observer_path = Path('/home/dave/source/repos/ArcadeAI/Robotron/tools/live_lr_recipe_continuation_proposal/observer.py')
        observer_raw = observer_path.read_bytes()
        if hashlib.sha256(observer_raw).hexdigest() != '11380275b544eb7196d33d92b1fbe28a1ae057404120419a2cfa447410c7e430':
            raise AssertionError('Unchanged pure observer source differs')
        observer_spec = importlib.util.spec_from_file_location('_same25_pure_observer_guard', observer_path)
        cls.O = importlib.util.module_from_spec(observer_spec); observer_spec.loader.exec_module(cls.O)
        cls.release_pin = cls.C.fingerprint(RELEASE)[1]
        if cls.release_pin['sha256'] != '491de9ac25a8a95ff3330c818cae75250ec6d3df73608229a71be29ac04b535b':
            raise AssertionError('Closed confirmed845 release changed')

    def context(self):
        case = dict(activation=copy.deepcopy(self.old_case['activation']), source_freeze_release=self.G.CLOSED['invalid_release'])
        with patch.object(self.C, 'load', side_effect=lambda name: {'recipe':self.R,'guard':self.G}[name]):
            return self.C.activation_context(case, None)

    def fixture(self, scale=.25):
        C = self.C; context = self.context(); baseline = copy.deepcopy(self.closed_baseline)
        baseline_pin = pin('new-runtime-baseline.json'); ready_pin = pin('new-readiness.json')
        environment = C.pinned(baseline['actual_selected_environment'])
        resources = C.pinned(baseline['actual_main192_resources'])
        old_job = C.pinned(self.immediate_binding['evidence']['phase_cpu_job'])
        archived = old_job['source_control_context']['archived_control']
        control = C.pinned(archived)
        control_raw = C.pinned(archived, raw_only=True)
        self.assertEqual(hashlib.sha256(control_raw).hexdigest(), baseline['control_hashes'][str(C.GAME/'models_dqn/learning_control.json')])
        api_raw = C.pinned(baseline['actual_API'], raw_only=True)
        control_pin = dict(pin('current-control.json', control), path=str(C.GAME/'models_dqn/learning_control.json'))
        control_pin.update(sha256=hashlib.sha256(control_raw).hexdigest(), bytes=len(control_raw))
        control_pin['identity'].update(bytes=len(control_raw), mode='0o664')
        now = max(self.R.release_wall_s(context['quality_release']),self.R.release_wall_s(context['previous_invalid']['release'])) + 1
        ready = dict(baseline, status='PASS', observed_unix_s=now, resources=dict(
            GPU0_free_bytes=15 << 30, GPU0_no_compute_owner=True, GPU1_main_only=True,
            port9999_clear=True, lease_free=True, no_competing_helpers=True,
            no_private_cgroup_tmpfs_processes=True, no_pending_save=True, owned_units_released=True))
        case = dict(schema=C.SCHEMA, capture_authorized=True, activation=copy.deepcopy(self.old_case['activation']),
            source_freeze_release=self.G.CLOSED['invalid_release'], runtime_baseline=baseline_pin, readiness=ready_pin,
            control_before=control_pin, completed_slot=self.old_case['completed_slot'],
            experiment=self.G.EXPERIMENT, recipe=self.R.for_scale(scale), tags=dict(barrier='synthetic-barrier',endpoint='synthetic-endpoint'),
            window=dict(policy=dict(learner_frames=8000000,learner_accepted=8000000,poll_s=1,API_age_s=5,
                pipeline_age_s=5,unobservable_s=30,no_applied_s=60,cutoff_s=3600),preparation_timeout_s=180),
            output_directory=str(RUN/'synthetic-new-unselected-lr-output'),cpu_python='/synthetic/python')
        original = C.pinned
        def reader(p, raw_only=False):
            if p == self.G.CLOSED['invalid_peer']: return original(p)
            if p == baseline_pin: return copy.deepcopy(baseline)
            if p == ready_pin: return copy.deepcopy(ready)
            if p == baseline['actual_selected_environment']: return copy.deepcopy(environment)
            if p == baseline['actual_main192_resources']: return copy.deepcopy(resources)
            if p == baseline['actual_API']: return api_raw if raw_only else json.loads(api_raw)
            raise AssertionError('Unexpected synthetic validation dependency: ' + str(p.get('path')))
        modules = dict(recipe=self.R,guard=self.G,observer=SimpleNamespace(POLICY=copy.deepcopy(self.O.POLICY), normalise=self.O.normalise),
                       entry=SimpleNamespace(slot_guard=lambda c,f: None))
        return case, context, baseline, reader, modules, now, control_raw, control

    def test_real_closed_activation_and_confirmed845_release_remain_distinct(self):
        context = self.context()
        self.assertEqual(context['owner'], self.C.ACTUAL_OWNER)
        self.assertEqual(context['phase']['record']['sha256'], self.C.FOUNDER)
        self.assertIs(context['quality_release']['candidate_qualified'], True)
        self.assertIs(context['quality_release']['both_independent_candidate_gates_pass'], True)
        self.assertEqual(context['historical_report']['root_job']['phase_snapshot']['observed_clients'], 0)
        self.assertEqual(context['historical_report']['held_recipe_context']['optimizer_lr'], 2.5e-5)
        case = dict(activation=self.old_case['activation'], source_freeze_release=self.G.CLOSED['invalid_release'])
        original = self.C.pinned
        bad = copy.deepcopy(context['quality_release']); bad['original192actors_preserved'] = True
        with patch.object(self.C,'load',side_effect=lambda name:{'recipe':self.R,'guard':self.G}[name]), patch.object(self.C,'pinned',side_effect=lambda p:bad if p==self.release_pin else original(p)):
            with self.assertRaises(ValueError): self.C.activation_context(case, None)

    def test_real_validate_accepts_fresh_same25_shapes_and_refuses_replacements(self):
        C=self.C
        for scale in (.25,):
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
        context.update(baseline=baseline,env={},resources={},control=control,recipe=case['recipe'])
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
        self.assertEqual(seen,[(control['experiment'],1.25e-5)])

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
        for scale in (.25,):
            selected=recipes.for_scale(scale);before=dict(experiment='old',lr_scale=.25,epsilon_ramp=dict(start=.1,end=.1))
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
        before=dict(experiment='old',lr_scale=.25,epsilon_ramp=dict(start=.1,end=.1))
        case=dict(experiment='new',recipe=selected,control_before=pin('live-control.json'),completed_slot=pin('old-slot.json'),
            tags=dict(barrier='barrier',endpoint='endpoint'),source_freeze_release=pin('release.json'),
            runtime_baseline=pin('baseline.json'),readiness=pin('ready.json'),activation=dict(result=pin('activation.json'),adoption=pin('adoption.json')),
            window=dict(preparation_timeout_s=180,policy=dict(cutoff_s=3600)),cpu_python='/synthetic/python')
        context=dict(owner=C.ACTUAL_OWNER,phase=dict(record=pin('phase.json')),baseline={},env={},resources={},
            previous_invalid=dict(guard_selection=self.G.SELECTION,release_pin=self.G.CLOSED['invalid_release']),
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


    def test_authentic_release_actor_and_publication_joins_refuse_false_success(self):
        value=self.context()['quality_release'];owner=self.C.ACTUAL_OWNER
        self.assertIs(self.R.check_release(value,owner,self.closed_baseline['actors']),value)
        self.assertTrue(value['original_CPU_wrapper_FAIL_preserved'])
        for change in (lambda v:v.update(source_freeze_released=False),
                       lambda v:v.update(candidate_qualified=False),
                       lambda v:v.update(protected_incumbent_changed=False),
                       lambda v:v.update(actual_native_plan_sha256='0'*64),
                       lambda v:v.update(original192actors_preserved=True),
                       lambda v:v['original192actors_preserved'].pop(),
                       lambda v:v['original192actors_preserved'].__setitem__(1,copy.deepcopy(v['original192actors_preserved'][0])),
                       lambda v:v['original192actors_preserved'][0].update(mask_matches=False),
                       lambda v:v['current_owned_units_absent'][0]['argv'].__setitem__(3,'wrong.timer')):
            bad=copy.deepcopy(value);change(bad)
            with self.assertRaises((ValueError,KeyError,TypeError)):self.R.check_release(bad,owner,self.closed_baseline['actors'])

    def test_label_only_control_preserves_scale_schedule_and_every_other_value(self):
        before=dict(experiment='closed-prior-label',lr_scale=.25,measurement=None,
            epsilon_ramp=dict(start=.1,end=.1,start_frame=123,duration_frames=456),other={'kept':True})
        after=copy.deepcopy(before);after['experiment']='future-label'
        self.assertEqual(self.R.check_control(before,after,'future-label',self.R.for_scale(.25)),after)
        for b,a,r in ((dict(before,lr_scale=.5),after,self.R.for_scale(.25)),
                      (before,dict(after,lr_scale=.5),self.R.for_scale(.25)),
                      (before,dict(after,experiment=before['experiment']),self.R.for_scale(.25)),
                      (before,dict(after,other={'kept':False}),self.R.for_scale(.25)),
                      (before,dict(after,lr_scale=.5),self.R.for_scale(.5))):
            with self.assertRaises(ValueError):self.R.check_control(b,a,a['experiment'],r)
        held=self.R.held_context(self.R.for_scale(.25),self.R.HELD_50)
        self.assertEqual(held['optimizer_lr'],1.25e-5)
        self.assertEqual(self.R.HELD_50['optimizer_lr'],2.5e-5)

    def test_actual_predecessor_and_protected845_metadata_keep_separate_invalid49_history(self):
        B=self.B;e=self.prior_binding['evidence']
        old_release=B.read(e['historical_invalid49_release']);old_plan=B.read(e['historical_invalid49_plan'])
        B.check_historical_sources(self.prior_plan,old_release,old_plan,e['historical_invalid49_plan'])
        reference=copy.deepcopy(self.R.REFERENCE);B.check_reference(reference,B.read)
        for key,wrong in (('evaluator_source_hashes',B.PRE_DIAGNOSTIC_EVALUATOR),
                          ('execution_source_hashes',B.PRE_DIAGNOSTIC_EXECUTION)):
            bad=copy.deepcopy(self.prior_plan);bad[key]=copy.deepcopy(wrong)
            with self.assertRaises(ValueError):B.check_historical_sources(bad,old_release,old_plan,e['historical_invalid49_plan'])
        bad=copy.deepcopy(old_release);bad['quality_acceptance']=True
        with self.assertRaises(ValueError):B.check_historical_sources(self.prior_plan,bad,old_plan,e['historical_invalid49_plan'])
        bad=copy.deepcopy(reference);bad['sha256']='eba19578c91b2380859754b99b9a8510efaed11f3ec2f672e89c5988e50ad74c'
        with self.assertRaises(ValueError):B.check_reference(bad,B.read)

    def test_real25_numeric_metadata_remains_valid_but_old_wrapperFAIL_is_not_new_authority(self):
        B=self.B;e=self.prior_binding['evidence']
        job=B.read(e['phase_cpu_job']);proof=B.read(e['phase_cpu_report']);completion=B.read(e['phase_cpu_completion'])
        B.check_cpu(job,proof,completion,self.prior_binding['candidate'])
        self.assertEqual(proof['adam_group']['lr'],1.25e-5)
        self.assertEqual(proof['recipe_specialization']['effective_source_sha256'],'5612ad9c5730030f818232146fc5073000b89ae8e93577fab8bd18a03d16c8e8')
        execution=B.read(e['CPU_execution']);release=B.read(execution['release_receipt'])
        self.assertEqual(release['status'],'FAIL')
        with self.assertRaises(ValueError):
            B.check_CPU_release(execution,e['phase_cpu_job'],e['phase_cpu_report'],e['phase_cpu_completion'],completion,
                B.read,B.archive_text,lambda p:B.archived_bytes(p,allow_empty=True))

    def test_real_carrier_fixed_profile_keeps_each_candidate_against_all_fresh_R_rows(self):
        C=source_module('root_quality_carrier.py', 'a24aca85015154504452fcde9bd674dba8845e749b876cc14b78b0f3c3b73b6a','_same25_carrier_guard')
        plan=copy.deepcopy(self.prior_plan);out=PurePosixPath('/synthetic/future-quality')
        reference=PurePosixPath(self.R.REFERENCE['path']);candidate=PurePosixPath('/synthetic/future-candidate.pt')
        plan['output_directory']=str(out)
        plan['effective_implementation']=copy.deepcopy(self.G.SELECTION)
        for leg in plan['legs']:
            leg['job'].update(continuous_guard_manifest=self.G.SELECTION['guard_manifest']['path'],continuous_guard_manifest_sha256=self.G.SELECTION['guard_manifest']['sha256'])
        plan['checkpoints']['reference'].update(source=str(reference),sha256=self.R.REFERENCE['sha256'])
        plan['checkpoints']['candidate'].update(source=str(candidate),sha256='a'*64)
        with patch.object(C,'BUNDLE',dict(effective_implementation=self.G.SELECTION)),patch.object(C,'OUT',out),patch.object(C,'REFERENCE',reference),patch.object(C,'REFERENCE_SHA',self.R.REFERENCE['sha256']),patch.object(C,'CANDIDATE',candidate):
            C.validate_plan(plan,'a'*64)
            for mutation in (lambda p:p['precommit'].update(min_full_games_per_leg=49),
                             lambda p:p['precommit'].update(include_full_completion_tail=False),
                             lambda p:p['precommit'].update(admission_extensions=True),
                             lambda p:p['precommit']['candidate_gate'].update(each_candidate_individually=False),
                             lambda p:p['precommit']['candidate_gate'].update(minimum_mean_ratio=1.0),
                             lambda p:p['legs'][0]['job'].update(cohort_s=2401)):
                bad=copy.deepcopy(plan);mutation(bad)
                with self.assertRaises(RuntimeError):C.validate_plan(bad,'a'*64)

    def test_unchanged_observer_numerics_strictCPU_body_assets_and_default_readfree(self):
        gc=Path('/home/dave/source/repos/ArcadeAI/Robotron/tools/live_lr_recipe_gcaware_capture_binding_proposal/quality_bindings.py').read_text()
        new=(HERE/'quality_bindings.py').read_text()
        def body(text,name):
            start=text.index('def '+name+'(');end=text.find('\ndef ',start+1)
            return text[start:] if end<0 else text[start:end]
        for name in ('terminal','check_cpu','check_CPU_command','check_CPU_release','check_window','check_transition'):
            self.assertEqual(body(new,name),body(gc,name),name)
        self.assertEqual(hashlib.sha256((HERE/'template-audit-source.py').read_bytes()).hexdigest(),
            '2576d4449b12d6b4a3b17898ab9938c6ff8c762829f61a29e3d510f73d585c21')
        for filename,expected in (('collect_fresh_capture_case.py','238fc4a3030d3b1707f842d56c5bf3cbe809aa23688922ac456e8299e191e824'),
                                  ('collect_quality_readiness.py','5ed6969160b7e24301e75463421232bdc867126bfb3cdc22c9da1b68a1e8cb7a'),
                                  ('root_quality_carrier.py','a24aca85015154504452fcde9bd674dba8845e749b876cc14b78b0f3c3b73b6a'),
                                  ('audit_completed_leg.py','c7f61c1cb538e70a8beb414e593cd1ae0e292678a5a3621e881fc08d4303a3d8')):
            module=source_module(filename,expected,'_same25_default_'+filename.replace('.','_'))
            with patch('builtins.open',side_effect=AssertionError('Default must be read-free')):
                self.assertEqual(module.main([]),0)


    def test_exact_invalid914_disposition_is_separate_from_confirmed845(self):
        G=self.G;owner=self.C.ACTUAL_OWNER
        invalid=self.C.pinned(G.CLOSED['invalid_release']);peer=self.C.pinned(G.CLOSED['invalid_peer'])
        self.assertIs(G.check_invalid_release(invalid,peer,owner),invalid)
        self.assertFalse(invalid['original_unit_released']);self.assertTrue(invalid['descriptor_retained'])
        self.assertFalse(invalid['scientific_disposition']['candidate_quality_assessed'])
        for mutate in (lambda v:v.update(original_unit_released=True),
                       lambda v:v.update(descriptor_retained=False),
                       lambda v:v['scientific_disposition'].update(outcome='qualified'),
                       lambda v:v['scientific_disposition'].update(candidate_quality_assessed=True),
                       lambda v:v['original'].update(exit=0),
                       lambda v:v['optimizer_replay_identities']['optimizer'].update(epoch=2)):
            bad=copy.deepcopy(invalid);mutate(bad)
            if bad['optimizer_replay_identities']['optimizer']['epoch']==2:
                # Invalid-disposition shape permits a positive epoch; actual fresh
                # baseline must retain the pinned release epoch in C.validate.
                case,context,baseline,reader,modules,now,raw,control=self.fixture()
                context['previous_invalid']['release']=bad
                with patch.object(self.C,'Path',NoIOPath),patch.object(self.C,'activation_context',return_value=context), \
                     patch.object(self.C,'pinned',side_effect=reader),patch.object(self.C,'fingerprint',return_value=(raw,case['control_before'])),patch.object(self.C.time,'time',return_value=now):
                    with self.assertRaises(ValueError):self.C.validate(case,NoIOPath(case['output_directory']),modules,object())
            else:
                with self.assertRaises(ValueError):G.check_invalid_release(bad,peer,owner)
        tombstone=dict(LoadState='loaded',Id=G.NATIVE_UNIT,MainPID='0',ExecMainPID='67638',
            InvocationID='a85440fb223f498d86dace1e32496911',NRestarts='0',ExecMainCode='1',
            ExecMainStatus='1',Result='exit-code',ActiveState='failed',SubState='failed',ControlGroup='',TriggeredBy='')
        self.assertIs(G.check_retained_terminal(tombstone),tombstone)
        self.assertEqual(G.check_retained_terminal(dict(LoadState='not-found')),dict(LoadState='not-found'))
        for key,value in (('InvocationID','foreign'),('MainPID','5'),('ControlGroup','/foreign'),('TriggeredBy','foreign.timer'),('ExecMainStatus','0')):
            with self.assertRaises(ValueError):G.check_retained_terminal(dict(tombstone,**{key:value}))

    def test_actual_guard_prerequisites_and_native_profile_not_stock_recompiled(self):
        G=self.G;seen=[]
        def source_reader(p):seen.append(p);return G.source_pin(p)
        result=G.prerequisites(self.C.pinned,self.C.ACTUAL_OWNER)
        self.assertEqual(result['release_pin'],G.CLOSED['invalid_release'])
        profile=G.check_selection(G.SELECTION,self.C.pinned,source_reader=source_reader)
        self.assertEqual(len(seen),5)
        self.assertEqual(profile['runtime_code_sha256'],'c11562ba189bdadc1ce3f70f0e3ecdaa92d4f2201dbb239e3a129f95564d1ef4')
        self.assertFalse(profile['DQN_Torch_NumPy_imported'])
        for key in ('canonical_base_socket','installer','effective_helper','companion_evaluator'):
            bad=copy.deepcopy(G.SELECTION);bad[key]['sha256']='0'*64
            with self.assertRaises(ValueError):G.check_selection(bad,self.C.pinned)
        for key,field,value in (('companion_four','original_exit',1),('companion_four','lifecycle_complete',False),
                                ('guard_six','executions',2),('native_profile','runtime_code_sha256','0'*64)):
            def reader(p):
                actual=self.C.pinned(p)
                if p==G.CLOSED[key]:actual=copy.deepcopy(actual);actual[field]=value
                return actual
            with self.assertRaises(ValueError):G.prerequisites(reader,self.C.ACTUAL_OWNER)

    def test_effective_runtime_identity_is_local_but_stable_provenance_is_crossleg(self):
        G=self.G;profile=self.C.pinned(G.CLOSED['native_profile'])
        def effective(offset=0):
            ids={k:100+offset+i for i,k in enumerate(sorted(G.LOCAL_KEYS))}
            return dict(selection=copy.deepcopy(G.SELECTION),runtime_code_sha256=profile['runtime_code_sha256'],
                python_version=profile['python_version'],python_cache_tag=profile['python_cache_tag'],
                verified_before_serving=True,verified_after_cleanup=True,verification_count=100,
                verification_error=None,local_identity_before=ids,local_identity_after=copy.deepcopy(ids))
        first=G.check_runtime(effective(),G.SELECTION,self.C.pinned)
        self.assertEqual(first,G.check_runtime(effective(1000),G.SELECTION,self.C.pinned))
        for mutate in (lambda v:v.update(runtime_code_sha256='0'*64),lambda v:v.update(python_cache_tag='cpython-312'),
                       lambda v:v.update(verified_after_cleanup=False),lambda v:v.update(verification_count=True),
                       lambda v:v.update(verification_error='changed'),lambda v:v['local_identity_after'].update(code=999),
                       lambda v:(v['local_identity_before'].update(function=True),v['local_identity_after'].update(function=True)),
                       lambda v:v['selection']['effective_helper'].update(path='/foreign/helper.py')):
            bad=effective();mutate(bad)
            with self.assertRaises(ValueError):G.check_runtime(bad,G.SELECTION,self.C.pinned)


if __name__ == '__main__':
    unittest.main()
