"""Four authored UNEXECUTED stdlib metadata/call-order guards; no numerical claims."""
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
SPEC=importlib.util.spec_from_file_location('_future_postfix_capture_guards',HERE/'capture_candidate.py')
helper=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(helper)
RUN=helper.RUN
RECOVERY=RUN/'accepted-newgame-failed-maintenance-forward-recovery-20261017/result.json'
RELEASE=RUN/'accepted-newgame-forward-recovery-parent-root-execution-20261017/root-original-result-and-owned-release.json'

def fakepin(name):return dict(path='/synthetic/unactivated/'+name,sha256='a'*64,bytes=100,identity={'mode':'0o444'})
def actual(path):return helper.fingerprint(path)[1]
def rawapi():
    # An authentic saved raw API schema, never a live endpoint or model body.
    health=json.loads((RUN/'accepted-newgame-forward-recovery-postrelease-health-root-20261017/root-fresh-postrelease-health.json').read_bytes())
    return json.loads(Path(health['actual_raw_API']['path']).read_bytes())

def fixture():
    assert actual(RECOVERY)['sha256']=='28d6232fb7f1346dd55ac5aa92a8d590ffbbbdc6c0d6d4bfd5618419053e5c88'
    assert actual(RELEASE)['sha256']=='393eb75b2550891de755339fb7533725d83ed8fc61dc69245dbb19d572d0148d'
    rec=helper.pinned(actual(RECOVERY));release=helper.pinned(actual(RELEASE))
    job=helper.pinned(rec['root_job']);failed=helper.pinned(job['failed_job'])
    case=dict(schema=helper.SCHEMA,capture_authorized=True,recovery=dict(result=actual(RECOVERY),release=actual(RELEASE)),
        source_freeze_release=failed['quality_release'],runtime_baseline=fakepin('future-baseline.json'),readiness=fakepin('future-readiness.json'),
        control_before=fakepin('control.json'),completed_slot=fakepin('completed.json'),tag='synthetic_future_first_postfix_8M',
        window=dict(policy=dict(learner_frames=8000000,learner_accepted=8000000,poll_s=1,API_age_s=5,pipeline_age_s=5,
            unobservable_s=30,no_applied_s=60,cutoff_s=3600),preparation_timeout_s=60),
        output_directory=str(RUN/'SYNTHETIC-never-activated-postfix-capture'),cpu_python='/synthetic/root-verified-python')
    binding=rec['healthy192']['binding'];native=binding['bindings'];mask=list(range(72))
    owner=copy.deepcopy(rec['owner'])
    actors=[dict(pid=a['pid'],starttime_ticks=a['starttime_ticks'],slot=a['client_slot'],mask=mask) for a in native['actors']]
    fleet=dict(pid=int(binding['fleet']['MainPID']),starttime_ticks=binding['supervisor_start_ticks'],unit='synthetic-fleet.service',
        invocation_id='b'*32,cgroup=binding['fleet']['ControlGroup'])
    worker=dict(native['worker']['thread'],mask=mask)
    def process(a,cgroup):return dict(pid=a['pid'],starttime_ticks=a['starttime_ticks'],argv=a['cmdline'],
        cwd=a['cwd'],exe=a['exe'],uid=a['uid'],cgroup=cgroup,mask=mask)
    resources=dict(owner=owner,main=process(native['worker']['trainer'],owner['cgroup']),
        fleet=dict(fleet,argv=['synthetic-fleet'],cwd=str(helper.GAME),exe='/synthetic/python',uid=[1001]*4,mask=mask),
        worker=worker,actors=[dict(a) for a in actors])
    baseline=dict(main_owner=owner,fleet_owner=fleet,inference_worker=worker,actors=actors,
        source_hashes=copy.deepcopy(native['source_hashes']),control_hashes=copy.deepcopy(native['control_hashes']),
        unit_files={p:s for values in binding['unit_files'].values() for p,s in values.items()},environment_sha256='c'*64,
        actual_maintenance=case['recovery']['result'],actual_selected_environment=fakepin('selected-env.json'),
        actual_main192_resources=fakepin('resources.json'),actual_API=fakepin('baseline-API.json'))
    historical=helper.pinned(rec['startup']['phase_CPU_readonly_archive']);control=helper.pinned(historical['root_job']['source_control_context']['archived_control'])
    controlpath=str(helper.GAME/'models_dqn/learning_control.json');case['control_before']['path']=controlpath
    case['control_before']['sha256']=baseline['control_hashes'][controlpath]
    ready={k:copy.deepcopy(baseline[k]) for k in ('main_owner','fleet_owner','inference_worker','actors','source_hashes','control_hashes','unit_files','environment_sha256')}
    observed=release['owned_release'][-1]['final']['unix_s']+1
    ready.update(status='PASS',observed_unix_s=observed,resources=dict(GPU0_free_bytes=15<<30,**{k:True for k in
        ('GPU0_no_compute_owner','GPU1_main_only','port9999_clear','lease_free','no_competing_helpers','no_private_cgroup_tmpfs_processes','no_pending_save','owned_units_released')}))
    values={case['recovery']['result']['path']:rec,case['recovery']['release']['path']:release,
        case['runtime_baseline']['path']:baseline,case['readiness']['path']:ready,
        baseline['actual_selected_environment']['path']:binding['environment'],baseline['actual_main192_resources']['path']:resources}
    return case,rec,baseline,ready,resources,control,values


def dispatcher(values):
    original=helper.pinned
    def get(pin,raw_only=False):
        if pin['path'] in values:
            value=values[pin['path']]
            return json.dumps(value,allow_nan=True).encode() if raw_only else copy.deepcopy(value)
        return original(pin,raw_only=raw_only)
    return get

class CaptureContracts(unittest.TestCase):
    def test_genuine_READY_dynamic_phase_release_and_original_archives(self):
        case,rec,baseline,ready,resources,control,values=fixture()
        context=helper.recovery_context(case,None)
        self.assertEqual(context['owner']['pid'],2257565)
        self.assertEqual(context['phase']['expected']['phase_id'],'ce4096_accepted_newgame_forward_recovery_20261017')
        self.assertEqual(context['phase']['record']['sha256'],'cb904195a747ca5dc549a8db7d03ea11cebe6930d61bedde903cf907eb28dfcc')
        for kind in ('failed-status','phase-id','wrong-original-exit','foreign-legitimate-release','wrong-release-show-unit'):
            c=copy.deepcopy(case);v=copy.deepcopy(values)
            if kind=='failed-status':v[c['recovery']['result']['path']]['status']='FAILED'
            elif kind=='phase-id':v[c['recovery']['result']['path']]['startup']['phase']['expected']['phase_id']='wrong_future_phase'
            elif kind=='wrong-original-exit':v[c['recovery']['release']['path']]['original_exit']=1
            elif kind=='foreign-legitimate-release':c['source_freeze_release']=fakepin('old-legitimate-release.json')
            else:v[c['recovery']['release']['path']]['owned_release'][0]['final']['argv']=['systemctl','--user','show','unrelated.timer']
            with self.subTest(kind=kind),patch.object(helper,'pinned',side_effect=dispatcher(v)):
                with self.assertRaises((RuntimeError,KeyError)):helper.recovery_context(c,None)

    def test_real_validate_current_source_key_owner_and_pre_request_guards(self):
        case,rec,baseline,ready,resources,control,values=fixture();clock=ready['observed_unix_s']
        self.assertIn(str(helper.GAME/'Scripts/dqn/socket_server.py'),baseline['source_hashes'])
        self.assertNotIn(str(helper.GAME/'Scripts/socket_server.py'),baseline['source_hashes'])
        observer=SimpleNamespace(POLICY={k:v for k,v in case['window']['policy'].items() if k!='cutoff_s'})
        guarded=[];entry=SimpleNamespace(slot_guard=lambda c,f:guarded.append(c['completed_slot']))
        original_fp=helper.fingerprint
        def fp(path,*args,**kw):
            if str(path)==case['control_before']['path']:return json.dumps(control).encode(),copy.deepcopy(case['control_before'])
            return original_fp(path,*args,**kw)
        def check(c,v):
            with patch.object(helper,'pinned',side_effect=dispatcher(v)),patch.object(helper,'fingerprint',side_effect=fp),patch.object(helper.time,'time',return_value=clock),patch.object(Path,'exists',return_value=False):
                return helper.validate(c,Path(c['output_directory']),dict(observer=observer,entry=entry),None)
        self.assertEqual(check(case,values)['owner'],rec['owner']);self.assertEqual(len(guarded),1)
        for kind in ('copied-control','old-owner','old-socket','wrong-worker','wrong-fleet-start','wrong-8M-policy','old-baseline-maintenance'):
            c=copy.deepcopy(case);v=copy.deepcopy(values)
            if kind=='copied-control':c['control_before']['path']='/synthetic/copied-control.json'
            elif kind=='old-owner':v[c['runtime_baseline']['path']]['main_owner']['pid']=1626184
            elif kind=='old-socket':v[c['runtime_baseline']['path']]['source_hashes'][str(helper.GAME/'Scripts/dqn/socket_server.py')]='d'*64
            elif kind=='wrong-worker':v[c['runtime_baseline']['path']]['inference_worker']['tid']+=1
            elif kind=='wrong-fleet-start':v[c['runtime_baseline']['path']]['fleet_owner']['starttime_ticks']+=1
            elif kind=='wrong-8M-policy':c['window']['policy']['learner_accepted']=6000000
            else:v[c['runtime_baseline']['path']]['actual_maintenance']=fakepin('old-maintenance.json')
            with self.subTest(kind=kind),self.assertRaises((RuntimeError,KeyError)):check(c,v)
        entry.slot_guard=lambda c,f:(_ for _ in ()).throw(RuntimeError('foreign completion/pending/failed'))
        with self.assertRaises(RuntimeError):check(case,values)

    def test_real_run_one_fresh_snapshot_only_after_original_durable_LATCH(self):
        case,rec,baseline,ready,resources,control,values=fixture();api=rawapi();events=[];saved={};api2=copy.deepcopy(api)
        for k in helper.CLOCKS:api2[k]+=8000000
        class Ops:
            @staticmethod
            def write_bytes(path,raw):
                key=str(path);self.assertNotIn(key,saved);saved[key]=raw
                return dict(path=key,sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw))
            @staticmethod
            def publish(path,value):return Ops.write_bytes(path,(json.dumps(value,allow_nan=False)+'\n').encode())
        class Files:
            def __init__(self,ops):self.raw_api=None;self.api=None
            @staticmethod
            def fsync_directory(path):pass
        class Runtime:
            def __init__(self,*args):self.current_completed=case['completed_slot'];self.publications=[]
            def trainer_id(self):return rec['owner']
            def request_guard(self):events.append('guard')
        class Health:
            def __init__(self,*args):self.hashes={}
            def check_health(self,label,lr):
                value=copy.deepcopy(api2 if 'LATCH' in events else api);return json.dumps(value,allow_nan=True).encode(),value
        class Snapshot:
            def __init__(self,adapter,files,runtime,spec,out):
                self.files,self.runtime=files,runtime;self.state='NEW';self.error=None;self.owner=self.owner_after=rec['owner'];self.transition={};self.raw_pin=fakepin('fresh-trigger.json');self.completed=fakepin('new-matched-completion.json')
            def start(self,raw,floor):
                self_test.assertIn('LATCH',events);self_test.assertIs(raw,self.files.api)
                self_test.assertEqual(self.files.raw_api,json.dumps(raw,allow_nan=True).encode());self_test.assertEqual(floor,{k:raw[k] for k in helper.CLOCKS});events.append('snapshot-start');self.state='PENDING'
            def tick(self):self.state='COMPLETE';self.runtime.current_completed=self.completed
            def freeze(self,**kw):events.append('freeze');return dict(source=fakepin('first-endpoint.pt'),verification_copy=fakepin('copy.pt'),acquisition=fakepin('acquisition.json'))
            def result(self):return {'state':self.state}
        self_test=self
        context=dict(owner=rec['owner'],phase=rec['startup']['phase'],baseline=baseline,env={},resources={},historical_floor={k:api[k]-1 for k in helper.CLOCKS},control=control,startup_tag='actual-recovery-startup',ready_clock={'wall_s':api['ts']-max(10,api['pipeline_snapshot_age_s']+1),'monotonic_s':1,'boot_id':'synthetic'})
        capture=SimpleNamespace(Files=Files,CaptureRuntime=Runtime,four=lambda a:{k:a[k] for k in helper.CLOCKS},triple=lambda a:{k:a[k] for k in ('path','sha256','bytes')},request_identity=lambda x:x,publish_request=lambda *a:None)
        def build(*a):events.append('CPU-job-only');return dict(schema='synthetic-numeric-job',output_directory='unused')
        entry=SimpleNamespace(EntryHealth=Health,slot_guard=lambda *a:None,build_CPU_job=build)
        def poll(*args,**kwargs):events.append('LATCH');return dict(status='LATCH_DURABLE',candidate_requests_allowed=1,observation=dict(first_eligible_observation=api2))
        observer=SimpleNamespace(SCHEMA='synthetic-window',RECIPE={},validate_job=lambda *a:None,
            normalise=lambda a:dict(clocks={k:a[k] for k in helper.CLOCKS},unclassified=0,optimizer={'applied':1},learner_accepted=1,accepted=1),
            ReceiptJournal=lambda **kw:SimpleNamespace(emit=lambda x:None,failure=None),poll=poll,encoded=lambda v:json.dumps(v,allow_nan=True).encode())
        modules=dict(entry=entry,driver=SimpleNamespace(clock=lambda:dict(boot_id='synthetic',wall_s=api['ts'],monotonic_s=2)),ops=Ops,capture=capture,snapshot=SimpleNamespace(Snapshot=Snapshot),observer=observer,phase=None)
        with patch.object(helper,'validate',return_value=context),patch.object(helper,'pinned',side_effect=lambda p,raw_only=False:saved[p['path']]),patch.object(Path,'mkdir'),patch.object(helper.time,'sleep'):
            result=helper.run(case,fakepin('actual-case.json'),Path(case['output_directory']),modules)
        self.assertEqual(result['status'],'CAPTURED_PENDING_ROOT_CPU');self.assertEqual(events.count('snapshot-start'),1)
        self.assertLess(events.index('LATCH'),events.index('snapshot-start'));self.assertLess(events.index('freeze'),events.index('CPU-job-only'))
        self.assertFalse(result['CPU_executed']);self.assertFalse(result['control_changed']);self.assertFalse(result['owner_actions'])
        events.clear();saved.clear();observer.poll=lambda *a,**kw:dict(status='INCOMPLETE',candidate_requests_allowed=0)
        with patch.object(helper,'validate',return_value=context),patch.object(Path,'mkdir'),patch.object(helper.time,'sleep'):
            result=helper.run(case,fakepin('actual-case.json'),Path(case['output_directory']),modules)
        self.assertEqual(result['status'],'FAILED');self.assertNotIn('snapshot-start',events)

    def test_default_read_free_and_existing_snapshot_health_builder_are_direct_reuse(self):
        with patch('builtins.open',side_effect=AssertionError('read')),patch.object(Path,'read_bytes',side_effect=AssertionError('read')),patch.object(helper,'load',side_effect=AssertionError('import')),contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(helper.main([]),0)
        self.assertIn('PLAN_ONLY_UNSELECTED',out.getvalue())
        source=(HERE/'capture_candidate.py').read_text()
        for token in ('entry.EntryHealth(','entry.build_CPU_job(','capture.CaptureRuntime(','snapshot_module.Snapshot(','observer.poll('):self.assertIn(token,source)
        self.assertNotIn('replace_control(',source);self.assertNotIn('stop_owned(',source);self.assertNotIn('subprocess.',source)

if __name__=='__main__':unittest.main()
