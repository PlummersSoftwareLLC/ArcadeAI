"""Independently close one exact four-job round-aware CPU qualification.

Read actual owned descriptors and absence first. Engineering fixtures never
publish launch guards; production can publish four exact-job receipts. No unit/process controls, native launch or state update.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys


def require(ok,message):
    if not ok:raise ValueError(message)


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec)
    sys.modules[name]=m;spec.loader.exec_module(m);return m


def close(prepared_path,prepared_sha256,source_sha256):
    require(hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==source_sha256,'Actual closeout source differs')
    raw=Path(prepared_path).read_bytes()
    require(hashlib.sha256(raw).hexdigest()==prepared_sha256,'Actual prepared CPU packet differs')
    packet=json.loads(raw)
    h=load('_deadline_CPU_close_helpers',Path(packet['helpers']['path']))
    for entry in (packet['helpers'],packet['controller'],packet['CPU_job'],packet['config'],packet['source_preparer'],packet['archive'],packet['reader'],packet['driver']):h.checked(entry)
    immutable=load('_deadline_CPU_close_immutable_reader',h.checked(packet['reader']))
    def read(entry,as_json=True):return immutable.read_pin(entry,as_json=as_json)
    job=read(packet['CPU_job']);cfg=read(packet['config']);study=read(job['prepared_manifest'])
    require(job['schema']=='robotron-deadline32-four-actual-jobs-CPU-guard-v2'
        and job['engineering_only'] is packet['engineering_only'] is study['engineering_only'], 'Selected exact CPU study domain differs')
    root=Path(cfg['output']);closurepin=h.pin(root/'root-original-result-and-owned-release.json')
    closure=read(closurepin);ownerpin=h.pin(root/'root-original-identity.json');owner=read(ownerpin)
    archive=load('_deadline_CPU_close_archive',h.checked(packet['archive']))
    fields=archive.archived_closure(closure,owner,read,exit_zero=True)
    require(owner['unit']==job['unit']==cfg['unit']and closure['original_exit']==0,'Actual original CPU owner/exit differs')
    control=load('_deadline_CPU_close_controller',h.checked(packet['controller']))
    require(control.checked_config(packet['config']['path'])==cfg,'Actual CPU configuration differs')
    require(cfg['properties']==['CPUQuota=200%','MemoryMax=4G','MemorySwapMax=0','RuntimeMaxSec=180','TasksMax=128','TimeoutStopSec=5','SendSIGKILL=no']
        and cfg['observation_s']==240,'Actual declared CPU resources differ')
    livepin=h.pin(root/'original-first-observed-show-command.json');live=read(livepin)
    livefields=dict(line.split('=',1)for line in read(live['stdout'],False).decode().splitlines()if'='in line)
    expected=dict(Id=owner['unit'],MainPID=str(owner['pid']),InvocationID=owner['invocation_id'],CPUQuotaPerSecUSec='2s',MemoryMax=str(4<<30),
        MemorySwapMax='0',RuntimeMaxUSec='3min',TasksMax='128',TimeoutStopUSec='5s',SendSIGKILL='no',Restart='no')
    require(all(livefields.get(k)==v for k,v in expected.items()),'Actual archived live2CPU/4GiB/180s scope differs')
    witness=read(job['interpreter_symlink_binding'])
    require(cfg['argv']==[witness['source_pin']['path'],'-Xgil=0','-I','-B',
        packet['driver']['path'],'--execute','--job',packet['CPU_job']['path'],'--job-sha256',packet['CPU_job']['sha256'],
        '--source-sha256',packet['driver']['sha256']], 'Exact actual CPU argv differs')
    require(all(token in fields['ExecStart']for token in cfg['argv']), 'Archived original CPU runtime argv differs')
    for pin in job['inputs']:h.checked(pin)
    proc=Path('/proc',str(owner['pid']),'stat')
    require(not proc.exists()or int(proc.read_text().rsplit(')',1)[1].split()[19])!=owner['starttime_ticks'],'Original CPU process remains')
    for unit in (owner['unit'],owner['timer']):require(control.show(unit)['LoadState']=='not-found','Original CPU unit remains')
    cgroup=livefields['ControlGroup']
    require(cgroup.endswith('/'+owner['unit'])and not Path('/sys/fs/cgroup'+cgroup).exists(),'Original CPU cgroup remains')
    reportpin=h.pin(Path(job['output'])/'report.json');report=read(reportpin)
    require(report['passed']is True and report['tests_run']==job['expected_actual_serialized_job_tests']+report['new_native_chain_tests']
        and job['expected_actual_serialized_job_tests']==6 and report['new_native_chain_tests']==4
        and report['new_native_chain_tests']==job['expected_new_native_chain_tests'] and report['old_clock_controller19_rerun']is False
        and report['errors']==report['failures']==[]and report['actual_PID']==owner['pid']
        and report['actual_ControlGroup']==cgroup and report['original_CPU_job']==packet['CPU_job']
        and report['all_native_outputs_absent']is True and report['Torch_imported']is report['checkpoint_body_opened']is False,
        'Actual new CPU guard result differs')
    cases=study['cases'];contexts=report['actual_prebody_contexts']
    require([c['leg']for c in cases]==[c['leg']for c in contexts]==['R1','C1','R2','C2']
        and report['native_jobs']==[c['native_job']for c in cases],'CPU result does not bind allfour actual jobs')
    guard_paths=[]
    for case,ctx in zip(cases,contexts):
        native=read(case['native_job']);target=Path(native['prelaunch_family_guard_closeout'])
        require(target==Path(native['output']).parent/'source-family-guards-CPU-original01/independent-deadline32-family-guards-and-CPU-closeout.json'
            and not target.parent.exists()and not Path(native['output']).exists(),'Exact future guard/native paths must remain unused')
        require(ctx['native_job']==case['native_job']and ctx['runtime']==case['runtime']
            and ctx['component_count']==12 and ctx['package_source_count']==123
            and ctx['actual_full_health_contract_checked']is True,'Actual full native completedcontext proof differs')
        family=read(native['source_family_manifest'])
        require(family['engineering_only'] is study['engineering_only']
            and family['native_launch_qualified'] is (not study['engineering_only']), 'Actual family domain differs')
        require(ctx['main_binding']==native['main_binding'] and ctx['Torch_and_checkpoint_body_opened'] is False, 'Actual context domain differs')
        require(ctx['protocol_provenance']['background_health_contract_only'] is True
            and ctx['protocol_provenance']['extra_preownership_launch_gate'] is True, 'Actual private derivation differs')
        guard_paths.append((case,target,ctx))
    require(len(report['actual_contract_negative_cases'])==4*job['expected_negative_cases_per_leg']
        and job['expected_negative_cases_per_leg']==8
        and all(row['rejected'] is True for row in report['actual_contract_negative_cases'])
        and report['all_future_guard_receipts_absent'] is True, 'Exact negative cases or unopened guard paths differ')
    closeout_pin=h.pin(Path(__file__).resolve())
    index=dict(schema='robotron-round-aware-one-original-all4-CPU-independent-closeout-v1',status='PASS',
        actual_CPU_job=packet['CPU_job'],actual_CPU_report=reportpin,actual_CPU_owner=ownerpin,actual_CPU_closure=closurepin,
        all_six_descriptors_resources_argv_birth_units_cgroup_and_release_verified=True,
        actual_exit=0,actual_CPU_cores=2,actual_memory_bytes=4<<30,actual_runtime_limit_s=180,
        tests_run=report['tests_run'],new_native_chain_tests=job['expected_new_native_chain_tests'],old19_rerun=False,
        exact_all4_prebody_contexts=contexts,all_native_outputs_absent=True,no_scientific_launch=True,
        engineering_only=study['engineering_only'], native_launch_qualified=False,
        native_guard_receipts_published=not study['engineering_only'], source=closeout_pin)
    indexpin=h.put(Path(job['output']).parent/'independent-original-all4-CPU-closeout.json',index)
    if study['engineering_only']:
        print(json.dumps(dict(independent_closeout=indexpin,engineering_only=True,native_guard_receipts_published=False)),flush=True)
        return
    guards=[]
    for case,target,ctx in guard_paths:
        target.parent.mkdir(mode=0o700)
        guards.append(h.put(target,dict(schema='robotron-deadline32-original-prelaunch-family-guard-v1',status='PASS',
            native_job=case['native_job'],runtime=case['runtime'],actual_exit=0,actual_CPU_cores=2,
            actual_memory_bytes=4<<30,actual_runtime_limit_s=180,original_all4_CPU_closeout=indexpin,
            actual_full_prebody_context=ctx,actual_CPU_report=reportpin,actual_CPU_closure=closurepin,
            actual_CPU_owner=ownerpin,original_attempt=1,no_retry=True,model_body_or_Torch_opened=False,
            deadline_metric_qualified=False,improvement_qualified=False)))
    result=h.put(Path(job['output']).parent/'all-four-exact-native-guard-receipts.json',dict(status='PASS',
        original_all4_CPU_closeout=indexpin,guards=guards,ROOT_native_readiness_and_adoption_still_required=True))
    print(json.dumps(result),flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true');p.add_argument('--prepared');p.add_argument('--prepared-sha256');p.add_argument('--source-sha256')
    a=p.parse_args()
    if not a.execute:print('PLAN_ONLY_NO_READS_OR_ACTIONS');return
    close(a.prepared,a.prepared_sha256,a.source_sha256)

if __name__=='__main__':main()
