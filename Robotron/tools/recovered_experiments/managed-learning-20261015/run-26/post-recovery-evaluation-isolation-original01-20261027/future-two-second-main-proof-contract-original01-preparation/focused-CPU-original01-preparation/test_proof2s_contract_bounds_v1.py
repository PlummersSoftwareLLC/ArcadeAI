"""Focused prospective predicates; Root alone executes this CPU fixture.

Compile exact SHA-bound AST statements/methods, with explicit synthetic
collaborators. Never import an observer main, read an original raw sample,
query a service/process, or qualify a scientific run. Actual complete client
_accept and complete original health.validate are exercised; admission/TCP
collection is outside this narrow fixture and remains separately qualified.
"""
import ast
import copy
import hashlib
import os
from pathlib import Path
import stat
import tempfile
import types
import unittest

Q = Path(__file__).resolve().parent.parent
S = Q/'source-family-original01'
I = Q.parent
R = I/'retired-api-row-projection-original01-preparation/capture-bracket-revision02'
G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
SOURCES = {
    'worker': (S/'round_observer_proof2s_v1.py', 'feaeba112ba001b52a3e2e30d882899c37e20c91dc53da709599a8051d39e8cf'),
    'client': (S/'round_observer_client_proof2s_v1.py', 'b61608ccc77a452c83eda35676b42da588045e08d4b98942a4a50188e987dfb1'),
    'reviewer': (S/'review_round_observer_proof2s_v1.py', 'e304bed18692308f3bf4eacfde3c2c44d4bebc1e4bf4033e836b549c8f95dea8'),
    'old_worker': (R/'round_observer_retired_API_v4.py', '8511b62f6e1dc5484b2a3b0604004875d84417db2e170ed5478efcacc7e0d854'),
    'old_reviewer': (R/'review_round_observer_retired_API_v4.py', '5b85c725bfacfbdb047e1f7791f350122e1097d8d0c988d29ce76cf433aa78cb'),
    'health': (R/'round_main_health_retired_API_v4.py', 'bb578e92a7cb796651673ca7e0bbf43027bc5058ee88ed4ae65a973ce7460c3a'),
    'API': (R/'api_cached_projections_v3.py', 'db5f06e406bf62128ccaa46ce3155c2a90c76c31daad37d8afb2fcbfa8c36f02'),
    'control': (G/'tools/post_recovery_evaluation/volatile_live_control_v1.py', 'a2ce55471f7ff14490553cf05871e79a0ff15c925d01441065821b0f95daade8'),
}


def require(value, message):
    if not value:
        raise ValueError(message)


def tree(role):
    path, digest = SOURCES[role]
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == digest, 'Fixture source changed: '+role)
    return ast.parse(raw, filename=str(path))


def function(role, name, namespace):
    nodes = [n for n in ast.walk(tree(role)) if isinstance(n, ast.FunctionDef) and n.name == name]
    require(len(nodes) == 1, 'Exact actual function required: '+name)
    node = copy.deepcopy(nodes[0])
    code = ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[]))
    exec(compile(code, str(SOURCES[role][0]), 'exec'), namespace)
    return namespace[name]


def predicate(role, name, message, **namespace):
    """Execute one complete actual require statement, without rewriting its AST."""
    nodes = [n for n in ast.walk(tree(role)) if isinstance(n, ast.FunctionDef) and n.name == name]
    require(len(nodes) == 1, 'Exact predicate owner required')
    calls = [n for n in ast.walk(nodes[0]) if isinstance(n, ast.Expr)
             and isinstance(n.value, ast.Call) and isinstance(n.value.func, ast.Name)
             and n.value.func.id == 'require' and len(n.value.args) >= 2
             and isinstance(n.value.args[1], ast.Constant)
             and str(n.value.args[1].value).startswith(message)]
    require(len(calls) == 1, 'Exact actual predicate message required: '+message)
    code = ast.fix_missing_locations(ast.Module(body=[copy.deepcopy(calls[0])], type_ignores=[]))
    exec(compile(code, str(SOURCES[role][0]), 'exec'), dict(namespace, require=require))


def health_fixture():
    """All192 actors are explicit synthetic process records, with no live probe."""
    now = 1000.0
    roles = {str(i): i < 37 for i in range(192)}
    static = ('parent_pid','cgroup','command','environment','affinity','uids','executable')
    def process(pid):
        return dict(pid=pid,starttime_ticks=pid+1,parent_pid=2,cgroup='/fixture',
                    command=['fixture'],environment={},affinity=[1],uids=[os.getuid()]*4,
                    executable=dict(path='/fixture/executable',sha256='1'*64))
    owners = {k:dict(unit='fixture-'+k,invocation=k,process=process(10+i))
              for i,k in enumerate(('trainer','fleet'))}
    env = dict(ROBOTRON_SOCKET_ADDRESS='dell:9998',ROBOTRON_RETIRE_AFTER_GAME='1')
    case = dict(owners=copy.deepcopy(owners),slot_eval=roles,actor_environment=env,
                actor_command=['fixture-mame'],actor_affinity=[1],
                actor_executable=dict(path='/fixture/mame',sha256='2'*64),initial_round=1)
    actors = {}
    for slot in roles:
        p = process(10000+int(slot))
        p.update(parent_pid=owners['fleet']['process']['pid'],state='S',
                 environment=dict(env,ROBOTRON_CLIENT_SLOT=slot,ROBOTRON_ACTOR_ROUND='1',
                     ROBOTRON_EVAL_MODE='1' if roles[slot] else '2',
                     ROBOTRON_PREVIEW_CLIENT='1' if slot == '0' else '0'),
                 command=case['actor_command'],executable=case['actor_executable'])
        actors[slot] = p
    exposure = {k:dict(process_id=10,instance_monotonic_ns=123,epoch=1,epoch_reason='fixture')
                for k in ('optimizer','replay')}
    case['exposure'] = copy.deepcopy(exposure)
    counts = dict(attempts_started=10,outcomes_recorded=10,applied=10,amp_skipped=0,unavailable=0)
    exposure['optimizer'].update(schema='robotron-optimizer-exposure-v1',enabled=True,
        total=copy.deepcopy(counts),since_epoch=copy.deepcopy(counts),
        unclassified_started_total=0,available=True)
    exposure['replay']['available'] = True
    api = dict(client_count=192,client_rows=[dict(client_id=i,client_slot=i,eval=roles[str(i)])
        for i in range(192)],training_enabled=True,measurement_active=False,lr=3.125e-6,
        ts=now,pipeline_snapshot_age_s=0.0,host_pipeline=dict(learning_exposure=exposure),
        training_steps=20,learner_frame_count=20,optimized_samples=20,frame_count=20)
    sample = dict(status=dict(total=192,completed=0,retired=0,active=192,round=1,updated_unix_s=now),
        actors=actors,results={},receipt_hashes={},owners=owners,api=api,
        monotonic_s=100.0,unix_s=now,previous_complete=None)
    admitted = lambda case,sample,previous=None:dict(round=1,results=sample['results'],
        receipt_hashes=sample['receipt_hashes'],pending=set(),registering=set(),bootstrap=False)
    view = lambda sample:dict(round=1,results=sample['results'],receipt_hashes=sample['receipt_hashes'])
    ns = dict(require=require,os=os,STATIC=static,
        admission=lambda:types.SimpleNamespace(verify=admitted,view=view),
        launchers=lambda:types.SimpleNamespace(verify_sample=lambda *a:set()),
        api_projection=lambda:types.SimpleNamespace(project_retired=lambda c,s,p:s),
        forward_declared_exec=lambda *a:False)
    for name in ('birth','observed_counts','validate_optimizer_accounting'):
        function('health',name,ns)
    validate = function('health','validate',ns)
    return case,sample,validate


class Tests(unittest.TestCase):
    def test_worker_and_reviewer_accept_prospective_bounds_old_half_second_rejects(self):
        for gap in (.75,1.25,2.0):
            for role,fn,msg in [('worker','run','Accepted main proof gap'),
                                ('reviewer','verify','Accepted main evidence gap')]:
                with self.subTest(gap=gap,role=role):
                    values=dict(job=dict(maximum_gap_s=2.0),sample=dict(monotonic_s=100+gap),
                                previous=dict(monotonic_s=100))
                    predicate(role,fn,msg,**values)
                    with self.assertRaises(ValueError):
                        predicate('old_'+role,fn,msg,**dict(values,job=dict(maximum_gap_s=.5)))
        for role,fn,msg in [('worker','run','Accepted main proof gap'),
                            ('reviewer','verify','Accepted main evidence gap')]:
            with self.assertRaises(ValueError):
                predicate(role,fn,msg,job=dict(maximum_gap_s=2.0),
                          sample=dict(monotonic_s=102.0001),previous=dict(monotonic_s=100))

    def test_worker_retry_and_publication_edges_use_exact_selected_two_seconds(self):
        for gap in (.75,2.0):
            predicate('worker','run','Main projection source',job=dict(maximum_gap_s=2.0),
                      published=100+gap,sample=dict(monotonic_s=100))
            predicate('worker','run','Main projection gap',job=dict(maximum_gap_s=2.0),
                      published=100+gap,publications=[dict(updated_monotonic_s=100)])
        for msg,values in [('Main projection source',dict(published=102.0001,sample=dict(monotonic_s=100))),
                           ('Main projection gap',dict(published=102.0001,publications=[dict(updated_monotonic_s=100)]))]:
            with self.assertRaises(ValueError):
                predicate('worker','run',msg,job=dict(maximum_gap_s=2.0),**values)
        predicate('worker','run','No accepted original main proof',job=dict(maximum_gap_s=2.0),
                  time=types.SimpleNamespace(monotonic=lambda:101.9999),baseline=100)
        with self.assertRaises(ValueError):
            predicate('worker','run','No accepted original main proof',job=dict(maximum_gap_s=2.0),
                      time=types.SimpleNamespace(monotonic=lambda:102.0),baseline=100)

    def test_reviewer_publication_edges_preserve_nonnegative_age(self):
        for gap in (.75,2.0):
            values=dict(job=dict(maximum_gap_s=2.0),index=0,
                publication=dict(index=0,updated_monotonic_s=100+gap),
                records=[dict(monotonic_s=100)],preceding=100)
            predicate('reviewer','verify','Running projection source age',**values)
            predicate('reviewer','verify','Running projection gap',**values)
        for gap in (-.001,2.0001):
            with self.assertRaises(ValueError):
                predicate('reviewer','verify','Running projection source age',job=dict(maximum_gap_s=2.0),
                    index=0,publication=dict(index=0,updated_monotonic_s=100+gap),records=[dict(monotonic_s=100)])

    def test_whole_actual_client_accept_age_identity_and_hundred_sample_guards(self):
        identity = function('control','identity',dict(stat=stat))
        for age in (.75,2.0,2.0001):
            with tempfile.TemporaryDirectory(prefix='robotron-proof2s-fixture-',dir='/dev/shm') as temporary:
                control=Path(temporary);output=control/'synthetic-observations'
                owner=dict(pid=700000001,birth=11);jp=dict(path='/fixture/job',sha256='a'*64)
                binding=dict(job=jp,nonce='b'*32,owner=owner)
                prefix=dict(schema='robotron-buffered-raw-readiness-v2',binding=binding,
                            sample_count=100,committed_records=100,committed_monotonic_s=90)
                common=types.SimpleNamespace(require=require,birth=lambda pid:11,
                    checked=lambda p:p,read=lambda p:copy.deepcopy(prefix))
                obj=types.SimpleNamespace(common=common,jobpin=jp,
                    job=dict(nonce='b'*32,maximum_gap_s=2.0),worker_owner=owner,
                    last_live=None,initial=None,control_path=control,output=output,
                    control_module=types.SimpleNamespace(identity=identity))
                accept=function('client','_accept',dict(time=types.SimpleNamespace(monotonic=lambda:100),Path=Path,os=os))
                value=dict(schema='robotron-round-observer-live-v2',job=jp,nonce='b'*32,owner=owner,
                    state='running',updated_monotonic_s=100-age,observed_samples=100,phase='ready',
                    control=dict(schema='robotron-owned-volatile-live-directory-v1',path=str(control),
                        binding=binding,volatile_not_scientific_raw_evidence=True,identity=identity(control.stat())),
                    latest_sample=dict(schema='robotron-queued-raw-record-v2',path=str(output/'sample-000099.json'),
                        sha256='c'*64,bytes=100,sequence=99,kind='sample',index=99),
                    initial=dict(durable_prefix=dict(path='/fixture/prefix'),index=99,durable_ready_monotonic_s=90))
                if age>2:
                    with self.assertRaisesRegex(ValueError,'publication expired'):accept(obj,value)
                    continue
                self.assertEqual(accept(obj,value)['observed_samples'],100)
                for field in ('job','owner','nonce'):
                    bad=copy.deepcopy(value);bad[field]={} if field!='nonce' else 'wrong'
                    with self.subTest(field=field),self.assertRaises(ValueError):accept(obj,bad)
                prefix['sample_count']=99
                with self.assertRaisesRegex(ValueError,'Initial100'):accept(obj,value)

    def test_complete_original_health_function_keeps_owner_source_role_epoch_strict(self):
        case,sample,validate=health_fixture();previous=copy.deepcopy(sample)
        sample['monotonic_s']+=1.5
        validate(case,sample,previous=previous)
        for damage in ('owner','source','role','optimizer_epoch','replay_epoch'):
            bad=copy.deepcopy(sample)
            if damage=='owner':bad['owners']['trainer']['invocation']='foreign'
            elif damage=='source':bad['actors']['40']['executable']=dict(path='/foreign')
            elif damage=='role':bad['actors']['40']['environment']['ROBOTRON_EVAL_MODE']='1'
            else:bad['api']['host_pipeline']['learning_exposure'][damage.removesuffix('_epoch')]['epoch']+=1
            with self.subTest(damage=damage),self.assertRaises(ValueError):validate(case,bad,previous=previous)

    def test_actual_retained_API_projection_half_second_TTLs_do_not_expand(self):
        for age in (.5,.5001):
            contexts=[('verify','Reconnect projection exceeds',dict(sample=dict(monotonic_s=100+age),previous=dict(monotonic_s=100))),
                ('verify','Reconnect API snapshot is stale',dict(api_age=age)),
                ('verify','New reconnect registration is stale',dict(new_age=age)),
                ('project_retired','Retired API projection exceeds',dict(sample=dict(monotonic_s=100+age),previous=dict(monotonic_s=100))),
                ('project_retired','Retired API cache is stale',dict(sample=dict(unix_s=100+age,api=dict(ts=100)))),
                ('project_retired','Retired API receipt-end expiry',dict(sample=dict(unix_s=100+age),end=100))]
            for fn,msg,context in contexts:
                with self.subTest(age=age,predicate=msg):
                    if age>.5:
                        with self.assertRaises(ValueError):predicate('API',fn,msg,RETIREMENT_MAX_S=.5,number=lambda x:x,**context)
                    else:predicate('API',fn,msg,RETIREMENT_MAX_S=.5,number=lambda x:x,**context)

    def test_actual_worker_bounds_reject_old_contract_and_changed_cadence(self):
        job=dict(interval_s=.2,initial_samples=100,maximum_gap_s=2.0,work_s=4200,runtime_s=4260)
        predicate('worker','run','Exact deadline observer bounds',job=job)
        for key,value in [('interval_s',1),('initial_samples',99),('maximum_gap_s',.5),('maximum_gap_s',2.1)]:
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):
                predicate('worker','run','Exact deadline observer bounds',job=dict(job,**{key:value}))


if __name__=='__main__':
    unittest.main()
