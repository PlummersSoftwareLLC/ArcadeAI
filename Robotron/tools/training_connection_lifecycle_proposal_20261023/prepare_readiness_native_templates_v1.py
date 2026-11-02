"""Prepare unselected native/read-review readiness integration with unchanged game gates."""
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
FAILED_PAIR='399f029598471553677c730b97c2ecc174b6fc1c8e295f72e1b319840926890a'
FAILED_POLICY='ea53b8a0495a9c4788ae2c1e0deb9a379bb1ca962d383110eaed148f8dda013c'

VALIDATOR=r'''
def validate_initial_readiness(receipt,receipt_pin,job,job_pin,raw,loaded_pin,admission,started,ended):
    """Require raw-recomputed readiness closure before private policy/game setup."""
    ready=raw['transport']['initial_readiness']
    require(receipt['schema']=='robotron-native-initial-main-readiness-v1'
        and receipt['original_job']==job_pin and receipt['runtime']==job['runtime']
        and receipt['main_health_protocol']==job['main_health_protocol']
        and receipt['before_sidecar_Torch_policy_or_MAME']is True,
        'Original readiness receipt source/job/protocol/order differs')
    require(type(ready['first_qualified_baseline_index'])is int
        and type(ready['unaccepted_samples'])is int
        and ready['first_qualified_baseline_index']==ready['unaccepted_samples']
        and 0<=ready['unaccepted_samples']<=10
        and receipt['first_qualified_baseline_index']==ready['first_qualified_baseline_index']
        and receipt['first_qualified_baseline_unix_s']==ready['first_qualified_baseline_unix_s']
        and receipt['unaccepted_initial_samples']==ready['unaccepted_samples'],
        'Original readiness receipt differs from complete unfiltered raw replay')
    first=ready['first_qualified_baseline_unix_s'];observed=receipt['observed_unix_s']
    mono=receipt['observed_monotonic_s'];loaded=loaded_pin['identity']['mtime_ns']/1e9
    require(all(type(value)in (int,float)and math.isfinite(value)for value in (first,observed,mono,loaded))
        and 0<=first-raw['first_observed_unix_s']<=2
        and started<=mono<=ended
        and first<=observed<=loaded<=admission['open_unix_ns']/1e9
        and receipt_pin['identity']['mtime_ns']<=loaded_pin['identity']['mtime_ns'],
        'Initial readiness was not closed within its bound before loaded policy/admission')
    return dict(original_receipt=receipt_pin,first_qualified_baseline_index=ready['first_qualified_baseline_index'],
        first_qualified_baseline_unix_s=first,unaccepted_initial_samples=ready['unaccepted_samples'],
        before_private_policy_and_game_setup_verified=True,quality_qualified=False)

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
    h=load(B/'run_full_policy_startup_v3.py','_native_ready_h')
    renderer=load(P/'render_owned_quality_family_v2.py','_native_ready_renderer')
    oldjob=json.loads((R/'dynamic-proc-quality-family-renderer-CPU-original01-preparation-20261023/job.json').read_text())
    originals={key:h.checked(pin).read_text()for key,pin in oldjob['templates'].items()}
    D.mkdir(mode=0o700,exist_ok=True)
    names=dict(runtime='run_compiled_full_tail32_quality_owned_health_template_v4.py',
        native_controller='control_compiled_full_tail32_quality_owned_health_template_v3.py',
        leg_reviewer='read_compiled_quality32_owned_health_template_v4.py',
        leg_preparer='prepare_quality32_owned_health_leg_template_v3.py',
        campaign_assessor='assess_quality32_owned_health_campaign_template_v3.py')
    templates={}
    old_guard="PAIR_SHA not in ('"+renderer.OLD_PAIR+"','"+renderer.FAILED2690_PAIR+"')"
    new_guard="PAIR_SHA not in ('"+renderer.OLD_PAIR+"','"+renderer.FAILED2690_PAIR+"','"+FAILED_PAIR+"')"
    for key in ['runtime','leg_reviewer','leg_preparer','campaign_assessor']:
        value=once(originals[key],old_guard,new_guard)
        if key!='campaign_assessor':value=once(value,">2690731936",">2700401151")
        templates[key]=value
    runtime=templates['runtime']
    dep=ast.literal_eval(next(n.value for n in ast.parse(runtime).body if isinstance(n,ast.Assign)
        and any(isinstance(t,ast.Name)and t.id=='HEALTH_DEPENDENCIES'for t in n.targets)))
    dep.update(mixed_transport=h.pin(P/'owned_transport_stream_v5.py')['sha256'],
        full_health_engine=h.pin(P/'owned_main_health_v4.py')['sha256'])
    runtime=renderer.assignment(runtime,'HEALTH_DEPENDENCIES',dep)
    runtime=once(runtime,"'"+renderer.FAILED2690_POLICY+"')","'"+renderer.FAILED2690_POLICY+"','"+FAILED_POLICY+"')")
    runtime=once(runtime,"protocol['schema']=='robotron-native-mixed-main-health-protocol-v3'",
        "protocol['schema']=='robotron-native-initial-readiness-main-health-protocol-v4'")
    runtime=once(runtime,'main_guard=None;main_guard_report=None;main_guard_failure=None;main_finalizer=None',
        'main_guard=None;main_guard_report=None;main_guard_failure=None;main_finalizer=None;main_initial_readiness=None')
    runtime=once(runtime,'        check_main()\n        def watch_main():',"""        initial_ready=check_main(require_closed=True)
        ready_stream=main_guard.collector.stream
        require(ready_stream.ready_index is not None and not initial_ready['phase']['overlap_pending'],
                'Actual initial main readiness must close before private setup')
        main_initial_readiness=h.put(output/'original-initial-main-readiness.json',dict(
            schema='robotron-native-initial-main-readiness-v1',original_job=jp,runtime=job['runtime'],
            main_health_protocol=job['main_health_protocol'],
            first_qualified_baseline_index=ready_stream.ready_index,
            first_qualified_baseline_unix_s=ready_stream.ready_unix_s,
            unaccepted_initial_samples=ready_stream.initial_unaccepted_samples,
            observed_monotonic_s=time.monotonic(),observed_unix_s=time.time(),
            before_sidecar_Torch_policy_or_MAME=True,quality_qualified=False))
        def watch_main():""")
    runtime=once(runtime,'and main_guard_report is not None)','and main_guard_report is not None and main_initial_readiness is not None)')
    runtime=once(runtime,'        main_health_report=main_guard_report,main_health_failure=main_guard_failure,',
        '        main_health_report=main_guard_report,main_health_failure=main_guard_failure,initial_main_readiness=main_initial_readiness,')
    templates['runtime']=runtime
    old_name='run_compiled_full_tail32_quality_owned_health_template_v3.py'
    templates['native_controller']=once(originals['native_controller'],old_name,names['runtime'])
    reviewer=once(templates['leg_reviewer'],old_name,names['runtime'])
    reviewer=renderer.assignment(reviewer,'RUNTIME_SHA',hashlib.sha256(runtime.encode()).hexdigest())
    reviewer=once(reviewer,"    require(type(result.get('main_health_report'))is dict and result.get('main_health_failure')is None",
        "    require(type(result.get('initial_main_readiness'))is dict and type(result.get('main_health_report'))is dict and result.get('main_health_failure')is None")
    reviewer=once(reviewer,"closed_main['schema']=='robotron-owned-main-full-health-closed-report-v2'",
        "closed_main['schema']=='robotron-owned-main-full-health-closed-report-v3'")
    reviewer=once(reviewer,'def validate_runtime_result(result,job):',VALIDATOR+'\ndef validate_runtime_result(result,job):')
    needle="        report.update(main_health_raw_replay=raw_main,\n"
    addition="""        initial_pin=result['initial_main_readiness']
        require(initial_pin['path']==str(out/'original-initial-main-readiness.json'),
                'Original readiness receipt path escaped')
        initial_checked=validate_initial_readiness(read(initial_pin),initial_pin,job,native_pin,raw_main,
            h.pin(out/'original-loaded-policy.json'),admission,started,ended)
        report['initial_main_readiness_verified']=initial_checked
"""
    assert "native_pin=config['native_job']"in reviewer
    reviewer=once(reviewer,needle,addition+needle)
    templates['leg_reviewer']=reviewer
    preparer=once(templates['leg_preparer'],"schema='robotron-native-mixed-main-health-protocol-v3'",
        "schema='robotron-native-initial-readiness-main-health-protocol-v4'")
    preparer=once(preparer,"health_job=dict(sources=readiness['main_health_sources'],binding=mp,log_origins=log_origins,log_root=str(G/'logs')))",
        "health_job=dict(sources=readiness['main_health_sources'],binding=mp,log_origins=log_origins,log_root=str(G/'logs'),initial_readiness_protocol=readiness['initial_readiness_protocol']))")
    templates['leg_preparer']=preparer
    pins={key:write(B/names[key],value)for key,value in templates.items()}
    for key in ['sequence','display_source']:pins[key]=oldjob['templates'][key]
    provenance=h.put(D/'unselected-native-readiness-template-provenance.json',dict(
        schema='robotron-unselected-native-readiness-template-provenance-v1',
        prior_templates=oldjob['templates'],templates=pins,
        transport=h.pin(P/'owned_transport_stream_v5.py'),engine=h.pin(P/'owned_main_health_v4.py'),
        readiness_protocol=dict(schema='robotron-bounded-initial-owned-readiness-v1',max_wait_s=2.,max_samples=11),
        failed2700_pair=FAILED_PAIR,failed2700_policy=FAILED_POLICY,minimum_future_learner_frames_exclusive=2700401151,
        fixed_game_admission_s=5400,whole_cohort_timeout_s=9000,native_wall_limit_s=9600,unit_runtime_s=9660,
        min_games=50,all32_required=True,all_admitted_full_tails_required=True,
        scientific_guard_selected=False,candidate_selected=False,quality_qualified=False))
    print(json.dumps(provenance))
