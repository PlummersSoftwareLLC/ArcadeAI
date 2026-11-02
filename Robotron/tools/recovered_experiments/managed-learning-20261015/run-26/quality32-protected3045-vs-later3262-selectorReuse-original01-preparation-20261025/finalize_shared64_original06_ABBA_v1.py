"""Prepare/review the complete original06 ABBA; refuse missing original cases.

One independent bounded CPU review. This never launches native evaluators,
changes production, scores partial games, pools B cases, or promotes a policy.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time

N=Path(__file__).resolve().parent
G=N.parents[3]
E=N/'evaluator-count-active600-counterbalanced-engineering-original06'
ORDER=('01-A1-control','02-B1-capacity64','03-B2-capacity64','04-A2-control')

def load(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s)
    sys.modules[name]=m;s.loader.exec_module(m);return m

def context():
    c=load('_final_capacity_close',N/'close_shared64_original06_case_v1.py').CloseOriginal(ORDER[0])
    assert c.qualified_pin['sha256']=='332a83d90457fb325cd862a4d255d2767f91653c5d624445f6f11fd73056280b'
    return c

def prepare():
    c=context();h=c.h;cases=[];pins=[]
    # All required originals must already have independently valid closeouts.
    # No output directory or CPU scheduling is permitted before these checks.
    for name in ORDER:
        p=h.pin(E/name/'independent-original-capacity64-case-closeout.json');proof=c.read(p)
        assert proof['case']==name and proof['status']=='VALID_ORIGINAL_CAPACITY64_ENGINEERING_CASE_NO_QUALITY'
        assert proof['all_native_observer_reviewer_archives_resources_pins_and_release_verified']is True
        assert proof['actual_native_exit']==1 and proof['actual_observer_exit']==proof['actual_reviewer_exit']==0
        assert proof['quality_qualified']is False
        cases.append(dict(case=name,closeout=p));pins.extend((p,proof['independent_report'],proof['native_job'],proof['native_result']))
    directory=E/'independent-original-final-ABBA-CPU-original01';assert not directory.exists()
    cpu=load('_final_capacity_cpu',G/'tools/training_connection_lifecycle_proposal_20261023/control_owned_health_CPU660_v2.py')
    assert h.pin(cpu.__file__)['sha256']=='a524ebb3be864bb03f13fff0af471782b2c6497c321da38ff83b679934cd03d1'
    design=c.read(c.qualified['design'])
    job=dict(schema='robotron-shared64-original06-independent-final-ABBA-job-v1',output=str(directory/'output-original01'),
        qualified_launches=c.qualified_pin,design=c.qualified['design'],cases=cases,
        measurement_reader=design['measurement_reader'],main_rate_reader=design['main_rate_reader'],
        comparator=design['comparator'],comparison_spec=design['fixed_comparison_spec'],
        original_attempt=1,no_retry=True,no_B_pooling=True,quality_qualified=False)
    pins.extend([c.qualified_pin,c.qualified['design'],h.pin(__file__),h.pin(N/'close_shared64_original06_case_v1.py')])
    pins.extend(p for p in job.values()if isinstance(p,dict)and 'path'in p)
    for record in c.qualified['cases']:
        native=c.read(record['native_job']);pins.extend(native['inputs']);pins.extend([record['native_job'],record['launch_config'],record['native_controller']])
    job['inputs']=list({p['path']:p for p in pins}.values())
    directory.mkdir(mode=0o700);jp=h.put(directory/'job.json',job);source=h.pin(__file__)
    cfg=dict(unit='robotron-shared64-original06-independent-final-ABBA-CPU-original01-20261026.service',
        output=str(directory/'execution-original01'),
        argv=['/usr/bin/python3.12','-I','-B',source['path'],'--execute','--job',jp['path'],
            '--job-sha256',jp['sha256'],'--source-sha256',source['sha256']],
        properties=['CPUQuota=200%','MemoryMax=4G','MemorySwapMax=0','RuntimeMaxSec=660','TasksMax=128','TimeoutStopSec=5','SendSIGKILL=no'],
        observation_s=720,pins=[cpu.pin(p['path'])for p in [jp,*job['inputs']]])
    cp=h.put(directory/'controller-config.json',cfg);assert cpu.checked_config(cp['path'])==cfg
    print(json.dumps(dict(job=jp,config=cp,source=source,original_attempt=1)))

def review(args):
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==args.source_sha256
    c=context();h=c.h;jp=h.pin(Path(args.job).resolve());assert jp['sha256']==args.job_sha256
    job=c.read(jp);assert job['schema']=='robotron-shared64-original06-independent-final-ABBA-job-v1'
    assert job['qualified_launches']==c.qualified_pin and job['design']==c.qualified['design']
    assert job['original_attempt']==1 and job['no_retry']is job['no_B_pooling']is True and job['quality_qualified']is False
    assert [v['case']for v in job['cases']]==list(ORDER)
    for pin in job['inputs']:h.checked(pin)
    design=c.read(job['design']);assert design['measurement_reader']==job['measurement_reader']
    assert design['main_rate_reader']==job['main_rate_reader']and design['comparator']==job['comparator']
    assert design['fixed_comparison_spec']==job['comparison_spec']
    measurements=load('_final_capacity_measurements',h.checked(job['measurement_reader']))
    math=load('_final_capacity_math',h.checked(job['comparator']))
    records={r['case']:r for r in c.qualified['cases']};measured={};evidence=[];identities=set()
    for index,case in enumerate(job['cases']):
        name=case['case'];current=load('_final_close_'+str(index),N/'close_shared64_original06_case_v1.py').CloseOriginal(name)
        p=current.read(case['closeout']);record=records[name]
        assert p['schema']=='robotron-capacity64-original-case-independent-closeout-v1'
        assert p['case']==name and p['status']=='VALID_ORIGINAL_CAPACITY64_ENGINEERING_CASE_NO_QUALITY'
        assert p['native_job']==record['native_job']and p['completed_valid_originals']==index+1
        assert p['prior_original_valid_closeouts']==[v['closeout']for v in job['cases'][:index]]
        assert p['all_native_observer_reviewer_archives_resources_pins_and_release_verified']is True
        assert p['all_declared_original_MAME_exit0_and_ROM1200_prefixes_verified']is True
        assert p['private_resources_free']is True and p['quality_qualified']is False
        native=current.read(p['native_job']);result=current.read(p['native_result']);report=current.read(p['independent_report'])
        lifecycle=current.read(result['main_observer_lifecycle']);outcome=current.read(lifecycle['worker_outcome'])
        publication_stats=outcome['running_projection_publication_stats']
        assert publication_stats==p['running_projection_publication_stats']
        assert publication_stats['attempts']==publication_stats['published']+publication_stats['coalesced_busy_reader']==outcome['observed_samples']
        assert publication_stats['errors']==0 and publication_stats['published']>0
        assert native['checkpoint']==design['reference_policy']and native['experiment_precommit']==job['design']
        assert native['main_binding']==design['main_binding']and native['main_rate_reader']==job['main_rate_reader']
        assert native['initializer_fixture_only']is native['scientific_case']is False
        assert report['native_job']==p['native_job']and report['native_result']==p['native_result']
        assert report['historical_transient_and_selected_coalescing_provenance_verified'] is True
        provenance=report['protocol_provenance']
        assert provenance['coalescing_protocol_CPU']==c.qualified['observer_protocol_CPU']
        assert provenance['current_context_observer_CPU']==c.qualified['current_main_context_CPU']
        assert provenance['selected_protocol']==current.read(native['source_family_manifest'])['main_observer']['protocol']
        assert report['declared_actor_count']==p['declared_actor_count']==record['actor_count']
        prefixes=report['all_declared_original_startup_prefixes']
        assert [v['slot']for v in prefixes]==native['actor_slots']
        assert all(v['all1200_original_pairs_and_loaded_ROM_verified']is True for v in prefixes)
        assert report['raw_replay']['samples']==p['raw_samples']and report['raw_replay']['deep_samples']==p['deep_samples']>=100
        assert report['raw_replay']['maximum_observation_gap_s']==p['maximum_observation_gap_s']<=.5
        for value in [*native['sessions'].values(),*native['connections'].values()]:
            assert value not in identities;identities.add(value)
        terminal=current.read(p['native_and_observer_terminal_closeout']);scopes=[]
        for key,code,cpu,memory,runtime,tasks,stop,native_scope in [
            ('native_scope',1,12,24<<30,22260,512,30,True),('observer_scope',0,2,4<<30,22260,128,5,False)]:
            original=terminal[key]
            scopes.append(current.scope(original['owner'],original['closure'],original['config'],code,cpu,memory,runtime,tasks,stop,native_scope))
        original=p['independent_reviewer_scope']
        scopes.append(current.scope(original['owner'],original['closure'],original['config'],0,2,4<<30,660,128,5))
        actual=measurements.analyse(native,p['native_job'],result,current.read,h)
        assert actual==report['timing_analysis']
        assert actual['accepted_frames']==p['active_accepted_frames']and actual['active_duration_ns']==p['active_duration_ns']
        assert actual['aggregate_accepted_frame_FPS']==p['accepted_frame_FPS']and actual['main_rates']==p['main_rates']
        measured[name]=actual
        evidence.append(dict(case=name,original_closeout=case['closeout'],original_raw_report=p['independent_report'],
            rechecked_native_observer_reviewer_scopes=scopes,running_projection_publication_stats=publication_stats,original_measurements_recomputed=True))
    assert len(identities)==384
    decision=math.compare(measured,c.read(job['comparison_spec']))
    assert decision['candidate_B_pool_used']is decision['quality_qualified']is False
    resources=load('_final_close_B64',N/'close_shared64_original06_case_v1.py').CloseOriginal(ORDER[1]).free_resources()
    out=Path(job['output']);assert not out.exists();out.mkdir(mode=0o700)
    pin=h.put(out/'report.json',dict(schema='robotron-shared64-original06-independent-final-ABBA-review-v1',
        job=jp,qualified_launches=c.qualified_pin,design=job['design'],case_evidence=evidence,measurements=measured,
        decision=decision,status='VALID_ENGINEERING_GATES_PASS'if decision['both_independent_B_gates_passed']else'VALID_ENGINEERING_GATES_REJECTED',
        all4_original_cases_valid_and12_scopes_independently_rechecked=True,all384_IDs_unique=True,
        actual64_startup_prefixes_independently_reviewed_twice=True,original_measurement_and_main_own_clock_rates_recomputed=True,
        resources=resources,quality_qualified=False,full_game_wall_time_gain_verified=False,
        useful_training_throughput_gain_verified=False,learning_speed_gain_verified=False,production_adoption=False,
        limits=['Engineering FPS gates only; complete-game wall-time and policy-quality work remain separate.',
            'Optimizer admission rows do not prove every parameter and Adam state advanced.'],created_unix_s=time.time()))
    print(json.dumps(dict(report=pin,both_independent_B_gates_passed=decision['both_independent_B_gates_passed'])),flush=True)
    time.sleep(8)

if __name__=='__main__':
    p=argparse.ArgumentParser();m=p.add_mutually_exclusive_group();m.add_argument('--prepare',action='store_true');m.add_argument('--execute',action='store_true')
    p.add_argument('--job');p.add_argument('--job-sha256');p.add_argument('--source-sha256');a=p.parse_args()
    if a.prepare:prepare()
    elif a.execute:review(a)
    else:print('PLAN_ONLY')
