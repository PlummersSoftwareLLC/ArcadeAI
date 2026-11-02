"""Prepare one new cold64 prefix diagnostic; default/import are inert.

No GPU/MAME/units, model load, source rewrite, launch or state mutation. The
actual native job remains unqualified until its separate original CPU review.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import secrets
import stat
import sys
import time

HERE=Path(__file__).resolve().parent
E=HERE.parent
N=E.parent
G=Path('/home/dave/source/repos/ArcadeAI/Robotron')

def load(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s)
    sys.modules[name]=m;s.loader.exec_module(m);return m

def prepare():
    h=load('_cold64_prepare_chain',HERE/'startup_slot64_chain_v1.py')
    def read(pin):
        p=Path(pin['path']);assert h.pin(p)==pin;return json.loads(p.read_bytes())
    def put(path,value):
        with path.open('x') as f:
            json.dump(value,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
        return h.pin(path)
    state=json.loads((G/'logs/managed-learning-20261015/state.json').read_bytes())['optimization_goal']
    assert state['scientific_job_running'] is False and state['performance_job_running'] is False
    scope=h.pin(HERE/'cold-prefix-only-precommit.json')
    assert scope['sha256']=='c1804394a9da37aa0834083c594f8fa31a3e1c6b3126de66b835747ed8312cf3'
    old_record=next(x for x in read(h.pin(E/'qualified-original-ABBA-launch-configs.json'))['cases'] if x['case']=='02-B1-capacity64')
    old_job=read(old_record['native_job']);family=read(old_job['source_family_manifest']);protocol=read(old_job['main_health_protocol'])
    assert old_job['checkpoint']['sha256']=='b23152ece3bb614831a278fe0572c07433f1bee59c5accef5a1ab7d3007af883'
    runtime=h.pin(HERE/'run_cold_slot64_prefix_v1.py')
    assert runtime['sha256']=='9f6820ea3633d8e411f4408846d0aaef7a9b9bde1393b16975293315a32ca25d'
    controller=h.pin(HERE/'control_cold_slot64_prefix_v1.py')
    observer_derivation=h.pin(HERE/'observer-bound420-family-original01/source-derivation.json')
    selected_observer=read(observer_derivation)['selected_sources']
    reviewer=h.pin(HERE/'review_cold_slot64_prefix_v1.py')
    wire_auditor=h.pin(HERE/'audit_cold_slot64_prefix_v1.py')
    assert state['current_main_binding']==old_job['main_binding']
    directory=HERE/'cold-prefix-preparation05-original01';assert not directory.exists();directory.mkdir(mode=0o700)
    job=copy.deepcopy(old_job)
    job.update(schema='robotron-cold-all64-startup-prefix-original-v1',created_unix_s=time.time(),
        output=str(directory/'diagnostic-output-original01'),initializer_fixture_only=False,
        label='cold-all64-startup-prefix-original01-20261026',engineering_case='cold-all64-prefix-only-original01',
        engineering_implementation='COLD64_PREFIX_ONLY',diagnostic_role='cold_all64_startup_prefix_only',
        diagnostic_only=True,diagnostic_precommit=scope,experiment_precommit=scope,wall_limit_s=360,
        prelaunch_family_guard_closeout=str(directory/'source-family-guards-CPU-original01/independent-original-family-guards-and-CPU-closeout.json'),
        native_launch_ready=False,actual64_startup_verified=False,scientific_case=False,quality_qualified=False,
        selected_change='Cold all64 startup-prefix certification of corrected actual nested Lua slot domain; no600/rates/quality')
    prior_ids=set();prior_jobs=[]
    for study in [*N.glob('evaluator-count-active600-counterbalanced-engineering-original*'),*N.glob('selector-active600-counterbalanced-engineering-original*')]:
        if not study.is_dir():continue
        for path in sorted(study.glob('*/job.json')):
            item=json.loads(path.read_bytes())
            for key in ('sessions','connections'):prior_ids.update(item.get(key,{}).values())
            prior_jobs.append(h.pin(path))
    # Earlier preparation never launched; retain its identities as excluded.
    for earlier in [HERE/'cold-prefix-original01/job.json',HERE/'cold-prefix-preparation02-original01/job.json',HERE/'cold-prefix-preparation03-original01/job.json']:
        prior_jobs.append(h.pin(earlier));earlier_job=json.loads(earlier.read_bytes())
        for key in ('sessions','connections'):prior_ids.update(earlier_job[key].values())
    fresh=set()
    for key in ('sessions','connections'):
        job[key]={}
        for slot in job['actor_slots']:
            token=secrets.token_hex(16)
            while token in fresh or token in prior_ids or token=='0'*32:token=secrets.token_hex(16)
            fresh.add(token);job[key][str(slot)]=token
    assert len(fresh)==128 and not(fresh&prior_ids)
    job=h.bind_future_job(job);job['runtime']=runtime
    bounds=dict(native_work_s=360,startup_s=300,cleanup_envelope_s=60,native_unit_runtime_s=420,
        observer_unit_runtime_s=420,controller_observation_s=480,positive_load_s=0)
    family.update(runtime=runtime,main_observer=selected_observer,native_closure=controller,observer_bound420_derivation=observer_derivation,
        diagnostic_precommit=scope,experiment_precommit=scope,reviewer=reviewer,
        engineering_case=job['engineering_case'],source_preparation_only=False,native_launch_selected=False,
        cold_prefix_only=True,prospective_bounds=bounds,actual64_startup_verified=False,
        full_new_reviewer_native_raw_pass=False)
    actual_review=load('_cold64_prepare_actual_review',Path(reviewer['path']))
    immutable=load('_cold64_prepare_immutable_reader',Path(job['main_sources']['reader']['path']))
    context=actual_review.validate_protocol_provenance(family,lambda pin,as_json=True: immutable.read_pin(pin,as_json=as_json))
    context_pin=put(directory/'completed-provenance-context-preflight.json',dict(passed=True,context=context,scope='Actual completed historical+selected420 metadata/source provenance only; no native outcomes, model body, Torch, GPU or MAME.'))
    family_pin=put(directory/'source-family-native-preparation.json',family)
    # Existing physical/epoch/socket/health predicates and original log identities
    # remain. Only the declared driver/time metadata follows this new native.
    protocol['health_job'].update(duration_s=360,driver=runtime)
    protocol_pin=put(directory/'diagnostic-main-health-protocol.json',protocol)
    replaced={old_job['source_family_manifest']['path']:family_pin,old_job['main_health_protocol']['path']:protocol_pin}
    inputs=[replaced.get(pin['path'],pin) for pin in job['inputs']]
    inputs += [scope,runtime,controller,observer_derivation,context_pin,reviewer,wire_auditor,h.pin(__file__),*selected_observer.values(),*prior_jobs]
    job.update(source_family_manifest=family_pin,main_health_protocol=protocol_pin)
    job['inputs']=list({p['path']:p for p in inputs}.values())
    native=load('_cold64_prepare_native',Path(runtime['path']))
    assert native.validate_job(job)==Path(job['output'])
    native.validate_main_health_contract(job,protocol,family)
    job_pin=put(directory/'job.json',job)
    # Reuse old immutable payload attestation plus exact current stat. Avoid an
    # unnecessary protected-model hash sweep during source preparation. Actual
    # launch authenticates every selected input again in the original controller.
    def controller_pin(pin):
        p=Path(pin['path']);s=p.stat();i=pin['identity']
        assert stat.S_ISREG(s.st_mode)
        if p.suffix=='.pt':assert not p.is_symlink()
        values=dict(device=s.st_dev,inode=s.st_ino,mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink)
        assert s.st_size==pin['bytes'] and all(values[k]==i[k] for k in values)
        for key,actual in [('mtime_ns',s.st_mtime_ns),('ctime_ns',s.st_ctime_ns)]:
            if key in i:assert i[key]==actual
        if p.suffix!='.pt':assert hashlib.sha256(p.read_bytes()).hexdigest()==pin['sha256']
        return dict(path=str(p),sha256=pin['sha256'],bytes=pin['bytes'],identity=values)
    config=dict(unit='robotron-compiled-full-tail32-integration-cold-slot64-prefix-original01-20261026.service',
        output=str(directory/'execution-original01'),
        argv=['/home/dave/source/repos/ArcadeAI/.venv-gb300/bin/python','-Xgil=0','-I','-B',runtime['path'],
            '--execute','--job',job_pin['path'],'--job-sha256',job_pin['sha256'],'--source-sha256',runtime['sha256']],
        properties=['CPUQuota=1200%','MemoryMax=24G','MemorySwapMax=0','RuntimeMaxSec=420','TasksMax=512',
            'TimeoutStopSec=30','KillMode=mixed','SendSIGKILL=no'],observation_s=480,
        pins=[controller_pin(pin) for pin in {p['path']:p for p in [job_pin,runtime,*job['inputs']]}.values()])
    config_pin=put(directory/'controller-config-NOT-QUALIFIED.json',config)
    actual_control=load('_cold64_prepare_controller',Path(controller['path']))
    assert actual_control.checked_config(config_pin['path'])==config
    manifest=put(directory/'prepared-cold-prefix-job-NOT-LAUNCH-QUALIFIED.json',dict(
        schema='robotron-cold-all64-prefix-job-preparation-v1',scope=scope,native_job=job_pin,
        native_controller=controller,unqualified_controller_config=config_pin,source_family=family_pin,
        main_health_protocol=protocol_pin,reviewer=reviewer,wire_auditor=wire_auditor,runtime=runtime,
        preparer=h.pin(__file__),observer_derivation=observer_derivation,completed_provenance_context=context_pin,
        actual_native_job_main_health_and_controller_interfaces_checked=True,
        original128_IDs_fresh_and_disjoint_from_prior_native_engineering_jobs=True,prior_jobs=prior_jobs,
        resource_bounds=bounds,original_attempt=1,no_retry=True,all_native_outputs_and_executions_absent=True,
        exact_job_CPU_guards_complete=False,native_launch_ready=False,actual64_startup_verified=False,
        quality_qualified=False,performance_gain_verified=False,protected_model_body_read=False,
        remaining='Separate bounded original exact-job/entry/controller CPU proof and independent source review; ROOT adoption and time-local main/GPU/ports/lease readiness; actual native64 startup + full raw independent review/owned closure.'))
    print(json.dumps(manifest))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepare',action='store_true')
    if p.parse_args().prepare:prepare()
    else:print('PLAN_ONLY_NO_READS_OR_ACTIONS')
