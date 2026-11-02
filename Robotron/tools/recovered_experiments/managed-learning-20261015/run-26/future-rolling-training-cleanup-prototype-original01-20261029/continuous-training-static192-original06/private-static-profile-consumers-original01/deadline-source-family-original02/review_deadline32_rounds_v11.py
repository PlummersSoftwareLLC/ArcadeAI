"""Independent new deadline32 score, raw prefix, health and ownership review."""
import argparse
import ast
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time


def require(ok,message):
    if not ok:raise ValueError(message)


def load(pin,name):
    path=Path(pin['path']);require(hashlib.sha256(path.read_bytes()).hexdigest()==pin['sha256'],'Review source differs')
    spec=importlib.util.spec_from_file_location(name,path);value=importlib.util.module_from_spec(spec)
    sys.modules[name]=value;spec.loader.exec_module(value);return value


def birth(pid):
    try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except FileNotFoundError:return None







def round_contract():
    path=Path(__file__).with_name('deadline_round_contract_v11.py')
    return load(dict(path=str(path),sha256='fd2da3ae65d414947ec2041ff0f44574a5103d1317d140b246d24ec7ad00844a'),'_deadline_round_review_contract')

def review_health(review,job,jp,result,owner,cfg,started,ended,family,protocol,read,h):
    contract=round_contract()
    contract.validate_static(job,protocol,family,h)
    contract.validate_binding(job,protocol,family,read,h)
    verifier=load(family['round_observer_reviewer'],'_deadline_round_raw_reviewer')
    checked=verifier.verify(result['main_observer_lifecycle'],h)
    life=read(result['main_observer_lifecycle']);worker=read(life['worker_job'])
    require(worker['native_job']==jp and worker['native_runtime']==job['runtime'] and worker['case']==job['main_binding'],
            'Original native/worker source context differs')
    parent=worker['parent']
    require(parent['pid']==owner['pid'] and parent['birth']==owner['starttime_ticks'] and parent['unit']==owner['unit']
            and parent['invocation_id']==owner['invocation_id'] and parent['argv']==cfg['argv'],
            'Original native scope does not join the observer parent')
    closed=read(result['main_health_report'])
    require(closed['outcome']==life['outcome'] and closed['job']==life['worker_job'] and closed['success'] is True,
            'Original closed main report differs')
    readiness=read(result['initial_main_readiness']);cleanup=read(result['intentional_cleanup'])
    require(started<=checked['first_accepted_monotonic_s']<=checked['initial_qualified_monotonic_s']
            <=readiness['observed_monotonic_s']<cleanup['begin_monotonic_ns']/1e9
            <=checked['last_accepted_monotonic_s']<=ended,
            'Original main proof does not cover private payload from readiness through teardown')
    return checked


def review_closed(review,read,h):
    jp=review['native_job'];job=read(jp);result=read(review['native_result']);out=Path(job['output'])
    assert job['schema']=='robotron-deadline32-one-original-leg-v1' and result['schema']=='robotron-deadline32-original-leg-result-v1'
    assert result['original_job']==jp and result['complete'] is True and result['errors']==[]
    assert result['status']=='ORIGINAL_DEADLINE32_SEALED_AND_CLOSED' and result['attempt']==1 and result['no_retry'] is True
    assert result['original_lease_released'] is result['all_original_threads_stopped'] is result['immutable_inputs_unchanged'] is True
    assert result['main_health_failure'] is None and result['policy_before']==result['policy_after']
    assert result['full_game_quality_qualified'] is result['deadline_metric_independently_qualified'] is result['improvement_qualified'] is False
    owner=read(review['native_owner']);cfg=read(review['native_config'])
    archive=load(review['archive'],'_deadline_native_scope_archive')
    fields=archive.archived_closure(read(review['native_closure']),owner,read,exit_zero=True)
    expected=dict(Id=owner['unit'],InvocationID=owner['invocation_id'],ExecMainPID=str(owner['pid']),ExecMainCode='1',ExecMainStatus='0',
        CPUQuotaPerSecUSec='12s',MemoryMax=str(24<<30),MemorySwapMax='0',RuntimeMaxUSec='1h 11min',TasksMax='512',
        TimeoutStopUSec='30s',KillMode='mixed',SendSIGKILL='no',Restart='no',NRestarts='0')
    for k,v in expected.items():assert fields[k]==v,(k,fields[k],v)
    command='/usr/bin/env -u LD_PRELOAD -u PYTHONPATH CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1 TMPDIR='+str(Path(cfg['output'])/'tmp')+' '+' '.join(cfg['argv'])
    assert command+' ; ignore_errors=no ;'in fields['ExecStart']
    control=load(review['native_controller'],'_deadline_actual_native_controller')
    validate_controller_pins(cfg,control)
    control.checked_config(review['native_config']['path'])
    for unit in (owner['unit'],owner['timer']):assert control.show(unit)['LoadState']=='not-found'
    assert birth(owner['pid'])!=owner['starttime_ticks']
    assert not Path('/sys/fs/cgroup/user.slice/user-1001.slice/user@1001.service/app.slice',owner['unit']).exists()
    started=int(fields['ExecMainStartTimestampMonotonic'])/1e6;ended=int(fields['ExecMainExitTimestampMonotonic'])/1e6
    assert 0<started<ended<=time.monotonic() and ended-started<=4320
    family=read(job['source_family_manifest']);protocol=read(job['main_health_protocol'])
    assert family['runtime']==job['runtime'] and family['deadline_components']==job['components']
    health=review_health(review,job,jp,result,owner,cfg,started,ended,family,protocol,read,h)
    guard=read(review['source_family_guard_closeout'])
    assert guard['schema']=='robotron-deadline32-original-prelaunch-family-guard-v1' and guard['native_job']==jp and guard['runtime']==job['runtime']
    assert guard['status']=='PASS' and guard['actual_exit']==0 and guard['actual_CPU_cores']==2 and guard['actual_memory_bytes']==4<<30 and guard['actual_runtime_limit_s']==180
    loaded=read(h.pin(out/'original-loaded-policy.json'));policy=result['policy_before']
    assert loaded['policy']==policy and policy['checkpoint_sha256']==job['checkpoint']['sha256']
    assert policy['training_enabled'] is policy['replay_enabled'] is False and policy['epsilon']==policy['expert_ratio']==0
    assert loaded['gpu_uuid']==job['gpu_uuid'] and loaded['memory_is_none'] is loaded['optimizer_is_none'] is True
    assert loaded['compile_report']==result['compile_report'] and result['compile_report']['all_shapes_verified']==list(range(1,17))
    anchor=read(result['deadline_anchor']);seal=read(result['deadline_score_seal']);cleanup=read(result['intentional_cleanup'])
    assert seal['recorder_implementation_revision']==3
    assert cleanup['original_score_seal']==result['deadline_score_seal'] and cleanup['original_barrier']==result['original_barrier']
    assert started<=result['native_started_monotonic_s']<anchor['anchor']['anchor_monotonic_ns']/1e9<=result['native_started_monotonic_s']+300
    assert result['native_deadline_monotonic_s']==result['native_started_monotonic_s']+4200
    failures=result['private_failure_events'];assert len(failures)==32 and {r['slot']for r in failures}==set(range(4096,4128))
    for event in failures:
        assert event['expected_deadline_retirement'] is event['intentional_cleanup_flag'] is True
        assert event['error'].startswith('DeadlineRetired(') and event['observed_monotonic_ns']>=cleanup['begin_monotonic_ns']
    reaped=result['original_post_origin_child_reap']
    writers=result['original_writer_capture']
    assert writers['all32_client_thread_objects_retained_before_shutdown'] is writers['retained_inference_thread'] is writers['all_retained_writers_stopped'] is True
    assert writers['retained_client_threads']==32 and type(writers['original_cleanup_timers_joined']) is int
    assert reaped['all_original_children_reaped'] is True and reaped['unknown_slots']==[]
    assert reaped['signals_sent'] is reaped['exit_statuses_normalized'] is False
    def index(pin):
        rows=[json.loads(line)for line in read(pin,False).splitlines()]
        values={r['journal_game_id']:r for r in rows};assert len(values)==len(rows);return values
    starts=index(result['journal']['measurement_starts.jsonl']);games=index(result['journal']['games.jsonl'])
    auditor=load(job['components']['prefix_auditor'],'_deadline_independent_actual_first_START');auditor.dependencies()
    prefix_result=dict(result,_admission=anchor['fixed_admission']);prefixes=[]
    assert anchor['fixed_admission']['close_unix_ns']-anchor['fixed_admission']['open_unix_ns']==300_000_000_000
    for slot in range(4096,4128):
        row=result['original_slots'][str(slot)];child=reaped['original_children'][str(slot)]
        assert child['pid']==row['pid'] and child['birth']==row['birth'] and child['actual_exit']==row['actual_exit']
        assert type(row['actual_exit']) is int and row['outputs_sealed_after_original_writer_closure'] is True and row['original_unsealed_output_paths']==[]
        assert row['expected_deadline_retirement'] is True and row['actual_proxy_error'].startswith('DeadlineRetired(')
        assert row['intentional_cleanup']=={k:cleanup[k]for k in ('begin_monotonic_ns','declared_monotonic_ns','after_flags_monotonic_ns','score_sealed_monotonic_ns')}
        prefixes.append(auditor.audit_first_start_prefix(slot,row,job,prefix_result,starts,games,read,h.pin,expected_job_sha256=jp['sha256']))
    score_auditor=load(job['components']['score_auditor'],'_deadline_actual_score_cutoff_audit')
    score=score_auditor.audit(job,result,seal,anchor,cleanup,prefixes,starts,games)
    restored=result['measurement_restoration']
    assert restored['metric_sealed'] is restored['all_original_threads_stopped'] is restored['complete_game_judgment_not_requested'] is True
    assert restored['original_cutoff_seal']==result['deadline_score_seal'] and restored['measurement_active_after'] is restored['owns_mode_after'] is False
    for pin in job['inputs']:h.checked(pin)
    assert h.pin(result['acquired_checkpoint']['path'])==result['acquired_checkpoint']
    fd=os.open(job['lease']['path'],os.O_RDWR|os.O_NOFOLLOW)
    try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(fd,fcntl.LOCK_UN)
    finally:os.close(fd)
    return dict(schema='robotron-deadline32-original-leg-independent-review-v1',status='PASS',original_job=jp,
        native_result=review['native_result'],leg=job['leg'],source_family=job['source_family_manifest'],
        actual_native_exit=0,all32_original_prefixes=prefixes,score_cutoff=score,main_health=health,
        actual_actor_exit_statuses_retained=True,positive_owned_native_observer_children_threads_and_lease_closure=True,
        deadline_metric_independently_qualified=True,complete_game_quality_qualified=False,improvement_qualified=False)


def validate_controller_pins(cfg,control):
    # Controller envelopes deliberately retain their own reduced identity shape.
    # Full immutable job inputs remain checked by the independent full helper.
    for pin in cfg['pins']:assert control.pin(pin['path'])==pin
    return True


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true')
    parser.add_argument('--job');parser.add_argument('--job-sha256');parser.add_argument('--source-sha256');args=parser.parse_args()
    if not args.execute:print('PLAN_ONLY');return 0
    assert os.environ.get('CUDA_VISIBLE_DEVICES')=='' and hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==args.source_sha256
    raw=Path(args.job).read_bytes();assert hashlib.sha256(raw).hexdigest()==args.job_sha256;review=json.loads(raw)
    assert review['schema']=='robotron-deadline32-original-leg-independent-review-job-v1'
    h=load(review['helpers'],'_deadline_review_helpers');reader=load(review['reader'],'_deadline_review_reader')
    for pin in review['inputs']:h.checked(pin)
    def read(pin,as_json=True):return reader.read_pin(pin,as_json=as_json)
    value=review_closed(review,read,h)
    entry=h.put(Path(review['output']),value);print(json.dumps(dict(review=entry,status='PASS')),flush=True);return 0


if __name__=='__main__':raise SystemExit(main())
