"""Prepare prospective renderer and native-order/receipt contracts, never a study."""
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
R=G/'logs/managed-learning-20261015/run-26'
P=G/'tools/training_connection_lifecycle_proposal_20261023'
B=G/'tools/startup_policy_journal_proposal'
D=R/'initial-readiness-native-family-CPU-original01-preparation-20261023'

TESTS=r'''
        def test_readiness_must_close_before_private_policy_setup_and_has_unchanged_game_helpers(self):
            nodes=ast.parse(rendered['runtime']['source'])
            run=next(n for n in nodes.body if isinstance(n,ast.FunctionDef)and n.name=='run')
            calls=[n for n in ast.walk(run)if isinstance(n,ast.Call)]
            checks=sorted([n for n in calls if isinstance(n.func,ast.Name)and n.func.id=='check_main'],key=lambda n:n.lineno)
            self.assertTrue(any(k.arg=='require_closed'and isinstance(k.value,ast.Constant)and k.value.value is True
                for k in checks[0].keywords))
            sidecar=next(n for n in calls if isinstance(n.func,ast.Name)and n.func.id=='load'
                and n.args and isinstance(n.args[0],ast.Constant)and n.args[0].value=='_compiled32_profile06_sidecar')
            marker=next(n for n in ast.walk(run)if isinstance(n,ast.Assign)
                and any(isinstance(t,ast.Name)and t.id=='main_initial_readiness'for t in n.targets)
                and isinstance(n.value,ast.Call))
            self.assertLess(checks[0].lineno,marker.lineno);self.assertLess(marker.lineno,sidecar.lineno)
            self.assertIn("initial_main_readiness=main_initial_readiness",rendered['runtime']['source'])
            self.assertIn("robotron-native-initial-readiness-main-health-protocol-v4",rendered['leg_preparer']['source'])
            self.assertIn("initial_readiness_protocol=readiness['initial_readiness_protocol']",rendered['leg_preparer']['source'])
            self.assertEqual(runtime.HEALTH_DEPENDENCIES['mixed_transport'],job['proposed_transport']['sha256'])
            self.assertEqual(runtime.HEALTH_DEPENDENCIES['full_health_engine'],job['proposed_engine']['sha256'])
        def test_pure_readiness_receipt_requires_raw_indices_scope_and_before_load_admission(self):
            jp=dict(path='/explicit-synthetic/native-job.json',sha256='1'*64)
            job_value=dict(runtime=dict(path='/explicit-synthetic/native.py',sha256='2'*64),
                main_health_protocol=dict(path='/explicit-synthetic/protocol.json',sha256='3'*64))
            raw=dict(first_observed_unix_s=1000.,transport=dict(initial_readiness=dict(
                first_qualified_baseline_index=1,unaccepted_samples=1,first_qualified_baseline_unix_s=1000.2)))
            receipt=dict(schema='robotron-native-initial-main-readiness-v1',original_job=jp,
                runtime=job_value['runtime'],main_health_protocol=job_value['main_health_protocol'],
                before_sidecar_Torch_policy_or_MAME=True,first_qualified_baseline_index=1,
                unaccepted_initial_samples=1,first_qualified_baseline_unix_s=1000.2,
                observed_unix_s=1000.3,observed_monotonic_s=501.)
            pin=dict(identity=dict(mtime_ns=1000400000000))
            loaded=dict(identity=dict(mtime_ns=1001000000000))
            admission=dict(open_unix_ns=1002000000000)
            def check(value=receipt,r=raw,p=pin,l=loaded,a=admission):
                return reviewer.validate_initial_readiness(value,p,job_value,jp,r,l,a,500.,600.)
            self.assertTrue(check()['before_private_policy_and_game_setup_verified'])
            for name,mutation in [
                ('wrong_job',lambda x:x.update(original_job=dict(path='/other',sha256='0'*64))),
                ('wrong_runtime',lambda x:x.update(runtime={})),
                ('wrong_protocol',lambda x:x.update(main_health_protocol={})),
                ('setup_too_early',lambda x:x.update(before_sidecar_Torch_policy_or_MAME=False)),
                ('different_ready_index',lambda x:x.update(first_qualified_baseline_index=2)),
                ('boolean_ready_index',lambda x:x.update(first_qualified_baseline_index=True)),
                ('boolean_unaccepted_count',lambda x:x.update(unaccepted_initial_samples=True)),
                ('different_ready_time',lambda x:x.update(first_qualified_baseline_unix_s=1000.4)),
                ('receipt_after_loaded_policy',lambda x:x.update(observed_unix_s=1001.5)),
                ('outside_original_scope',lambda x:x.update(observed_monotonic_s=601.)),
                ('nonfinite_receipt',lambda x:x.update(observed_unix_s=float('nan')))]:
                value=copy.deepcopy(receipt);mutation(value)
                with self.assertRaises((ValueError,KeyError,TypeError)):check(value)
                negative.append(name)
            late_raw=copy.deepcopy(raw);late_raw['transport']['initial_readiness']['first_qualified_baseline_unix_s']=1003.
            late_receipt=copy.deepcopy(receipt);late_receipt['first_qualified_baseline_unix_s']=1003.
            with self.assertRaises(ValueError):check(late_receipt,late_raw)
            with self.assertRaises(ValueError):check(p=dict(identity=dict(mtime_ns=1001500000000)))
            with self.assertRaises(ValueError):check(a=dict(open_unix_ns=1000500000000))
            negative.extend(['readiness_over_two_seconds','receipt_file_after_loaded','admission_before_loaded'])
'''

def load(path,name):
    s=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def once(source,old,new):
    assert source.count(old)==1,(old,source.count(old))
    return source.replace(old,new)

def write(path,source):
    ast.parse(source)
    with path.open('xb')as f:
        f.write(source.encode());f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
    return h.pin(path)

if __name__=='__main__':
    h=load(B/'run_full_policy_startup_v3.py','_readyrender_h')
    meta=json.loads((D/'unselected-native-readiness-template-provenance.json').read_text())
    templates=meta['templates']
    q=h.checked(templates['leg_reviewer']).read_text()
    needle="    require(type(ready['first_qualified_baseline_index'])is int\n"
    q=once(q,needle,needle+"        and type(receipt['first_qualified_baseline_index'])is int\n        and type(receipt['unaccepted_initial_samples'])is int\n")
    templates['leg_reviewer']=write(B/'read_compiled_quality32_owned_health_template_v5.py',q)
    render=(P/'render_owned_quality_family_v2.py').read_text()
    render=once(render,"KINDS=('runtime'",
        "FAILED2700_PAIR='"+meta['failed2700_pair']+"'\nFAILED2700_POLICY='"+meta['failed2700_policy']+"'\n"
        "FAILED2700_CLOCKS=dict(learner_frame_count=2700401151,training_steps=10721482,"
        "optimized_samples=42339395584,frame_count=5274310141)\nKINDS=('runtime'")
    render=once(render,'pair_sha not in (OLD_PAIR,FAILED2690_PAIR)','pair_sha not in (OLD_PAIR,FAILED2690_PAIR,FAILED2700_PAIR)')
    render=once(render,'all(clocks[key]>value for key,value in FAILED2690_CLOCKS.items())',
        'all(clocks[key]>value for key,value in FAILED2700_CLOCKS.items())')
    render=once(render,'sha not in (REFERENCE,OLD_POLICY,FAILED2690_POLICY)',
        'sha not in (REFERENCE,OLD_POLICY,FAILED2690_POLICY,FAILED2700_POLICY)')
    render=once(render,'run_compiled_full_tail32_quality_owned_health_template_v3.py',
        'run_compiled_full_tail32_quality_owned_health_template_v4.py')
    renderer=write(P/'render_owned_quality_family_v3.py',render)
    test=(P/'validate_owned_quality_family_v2.py').read_text()
    test=once(test,'for key,value in subject.FAILED2690_CLOCKS.items()}))',
        'for key,value in subject.FAILED2700_CLOCKS.items()}))')
    test=once(test,'+subject.FAILED2690_PAIR+"\')",rendered',
        '+subject.FAILED2690_PAIR+"\',\'"+subject.FAILED2700_PAIR+"\')",rendered')
    needle="                negative.append('closed2690_nonlater_'+key)"
    addition=needle+"""
            with self.assertRaises(ValueError):subject.render(templates,pair,subject.FAILED2700_PAIR,'synthetic')
            negative.append('closed2700_pair_forbidden')
            data=copy.deepcopy(pair);data['candidate']['policy']['sha256']=subject.FAILED2700_POLICY
            with self.assertRaises(ValueError):subject.render(templates,data,'f'*64,'synthetic')
            negative.append('closed2700_policy_forbidden')
            for key,floor in subject.FAILED2700_CLOCKS.items():
                data=copy.deepcopy(pair);data['candidate']['saved_clocks'][key]=floor
                with self.assertRaises(ValueError):subject.render(templates,data,'f'*64,'synthetic')
                negative.append('closed2700_nonlater_'+key)"""
    test=once(test,needle,addition)
    test=once(test,'    result=unittest.TextTestRunner(verbosity=2).run(',TESTS+'\n    result=unittest.TextTestRunner(verbosity=2).run(')
    driver=write(P/'validate_readiness_quality_family_v3.py',test)
    old=json.loads((R/'dynamic-proc-quality-family-renderer-CPU-original01-preparation-20261023/job.json').read_text())
    job=old.copy();job.update(templates=templates,subject=renderer,
        proposed_transport=h.pin(P/'owned_transport_stream_v5.py'),
        proposed_engine=h.pin(P/'owned_main_health_v4.py'),output=str(D/'output-original01'))
    jp=h.put(D/'job.json',job)
    cpu=load(G/'tools/quality_capacity_proposal/control_quality32_review_v1.py','_readyrender_cpu')
    entries=[*templates.values(),jp,driver,*[v for v in job.values()if isinstance(v,dict)and 'path'in v]]
    cfg=dict(unit='robotron-initial-readiness-native-family-CPU-original01-20261023.service',
        output=str(D/'execution-original01'),
        argv=['/usr/bin/python3.12','-I','-B',driver['path'],'--execute','--job',jp['path'],
            '--job-sha256',jp['sha256'],'--source-sha256',driver['sha256']],
        properties=['CPUQuota=200%','MemoryMax=4G','MemorySwapMax=0','RuntimeMaxSec=180',
            'TasksMax=128','TimeoutStopSec=5','SendSIGKILL=no'],
        pins=[cpu.pin(v['path'])for v in entries],observation_s=240)
    h.put(D/'controller-config.json',cfg)
    print(str(D/'controller-config.json'))
