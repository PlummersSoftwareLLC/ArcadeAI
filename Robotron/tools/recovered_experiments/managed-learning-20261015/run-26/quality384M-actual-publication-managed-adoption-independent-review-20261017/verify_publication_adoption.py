"""One-shot read-only stdlib/proc/API readiness observation, not a benchmark."""
import datetime as dt
import errno
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import subprocess
import time
import urllib.request

OUT=Path(__file__).parent
GAME=Path('/home/dave/source/repos/ArcadeAI/Robotron')
RUN=GAME/'logs/managed-learning-20261015/run-26'
PRE=RUN/'inference-affinity-v2-live-20261017T0012Z/precommit.json'
OLD=RUN/'live-health-and-384M-readiness-independent-review-20261017/health-and-readiness-receipt.json'
REARM=RUN/'fresh3-384M-gate-rearmed-post-warmup-aa-reviewed1-20261017.json'
MASK=list(range(72))
CHECKS={}
ARTIFACTS={}

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def write(name,value):
    data=(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n').encode() if not isinstance(value,bytes) else value
    path=OUT/name
    with path.open('xb') as stream:
        stream.write(data);stream.flush();os.fsync(stream.fileno())
    path.chmod(0o444)
    ARTIFACTS[name]=dict(sha256=hashlib.sha256(data).hexdigest(),bytes=len(data))

def check(name,value):
    CHECKS[name]=bool(value)

def command(argv):
    result=subprocess.run(argv,text=True,capture_output=True,timeout=10,check=False)
    return dict(argv=argv,returncode=result.returncode,stdout=result.stdout,stderr=result.stderr)

def state(pid):
    fields=(Path('/proc')/str(pid)/'stat').read_text().rsplit(')',1)[1].split()
    return fields[0],int(fields[19])

def identify(pid,actor=False):
    path=Path('/proc')/str(pid)
    before_state,before=state(pid)
    words=[word.decode(errors='surrogateescape') for word in (path/'cmdline').read_bytes().split(b'\0') if word]
    uid=[int(word) for line in (path/'status').read_text().splitlines() if line.startswith('Uid:') for word in line.split()[1:]]
    slot=None
    if actor:
        values=[word.split(b'=',1)[1] for word in (path/'environ').read_bytes().split(b'\0')
                if word.startswith(b'ROBOTRON_CLIENT_SLOT=')]
        if len(values)!=1:raise ValueError('Ambiguous actor slot '+str(pid))
        slot=int(values[0])
    result=dict(pid=pid,starttime_ticks=before,uid=uid,cmdline=words,
        cwd=str((path/'cwd').resolve(strict=True)),exe=str((path/'exe').resolve(strict=True)),client_slot=slot)
    after_state,after=state(pid)
    if after!=before:raise ValueError('Process identity changed '+str(pid))
    return dict(identity=result,state=after_state,affinity=sorted(os.sched_getaffinity(pid)),
                cgroup=(path/'cgroup').read_text().strip())

def api(name):
    started=time.monotonic()
    with urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=4) as response:
        data=response.read(1024**2)
    value=json.loads(data)
    write(name,data)
    return value,dict(monotonic=time.monotonic(),read_duration_s=time.monotonic()-started,
                      unix=time.time(),api_ts=value['ts'])

def api_health(raw,pre):
    hp=raw['host_pipeline'];g=hp['inference_graphs'];n=hp['native_batch_update'];b=raw['bank_persistence']
    e=hp['learning_exposure'];o=e['optimizer'];r=e['replay'];t=o['total']
    pending=t['attempts_started']-t['outcomes_recorded']
    identities=all({key:e[kind][key] for key in ('process_id','instance_monotonic_ns','epoch')}
                   ==pre['exposure_identity'][kind] for kind in ('optimizer','replay'))
    return dict(client_count=raw['client_count'],slots=sorted(row['client_slot'] for row in raw['client_rows']),
        healthy=raw['client_count']==192 and sorted(row['client_slot'] for row in raw['client_rows'])==list(range(192))
            and raw['training_enabled'] and not raw['measurement_active'] and raw['managed_experiment']=='best10M-fresh3-eps10-cap8-nosmooth'
            and raw['epsilon']==.1 and abs(raw['expert_ratio']-.1)<1e-12 and raw['lr']==2.5e-5
            and raw['memory_buffer_size']==6000000 and math.isfinite(raw['loss']) and math.isfinite(raw['grad_norm'])
            and not raw['pipeline_read_error'] and not raw['bank_persistence_read_error'],
        graphs=g['ready'] and g['capture_count']==128 and g['validation_replay_count']==640 and g['postload_validations']==1
            and g['runtime_capture_count']==0 and g['fallback_count']==0 and not g['fatal_error'],
        native=n['enabled'] and n['available'] and n['completed_count']==n['success_count'] and n['fallback_count']==n['error_count']==0,
        persistence=b['output']['backend']=='stream' and b['output']['stream_output_enabled']
            and not b['write_failures'] and not b['last_error'] and not any(v['errors'] for v in b['output']['totals'].values()),
        pipeline_errors={key:hp[key]['errors'] for key in ('inference','actor_refresh','target_refresh','learner_priority')},
        exposure=identities and pending in (0,1) and o['unclassified_started_total']==pending
            and (o['available'] or pending==1) and t['unavailable']==0 and o['prior_epoch_outcomes_total']==0
            and t['outcomes_recorded']==t['applied']+t['amp_skipped']+t['unavailable']
            and r['available'] and r['accepted_by_source_total']['unattributed']==0,
        optimizer_pending=pending,learner_frame_count=raw['learner_frame_count'],frame_count=raw['frame_count'],
        optimized_samples=raw['optimized_samples'],training_steps=raw['training_steps'],loss=raw['loss'],grad_norm=raw['grad_norm'],
        experiment=raw['managed_experiment'],quality_campaign=raw['quality_campaign'])


def main():
    start=time.time();checks={};proofs={}
    def ck(name,value):checks[name]=bool(value)
    def pin(path,expected):
        actual=sha(path);ck('proof_sha:'+Path(path).name+':'+Path(path).parent.name,actual==expected)
        proofs[str(path)]={'sha256':actual,'expected':expected};return json.loads(Path(path).read_text())
    promotion_path=RUN/'quality384M-managed-incumbent-adoption-root-20261017/root-promotion-and-goal-continuation-receipt.json'
    promotion=pin(promotion_path,'d859661e3b0c3b5ec82f043d6a88f2f58079ecb1ddab43c8c33cb62b219d565d')
    incumbent=promotion['new_incumbent']
    publication=pin(promotion['publication_review'],promotion['publication_review_sha256'])
    final=pin(incumbent['independent_final_gate_review'],incumbent['independent_final_gate_review_sha256'])
    strict_path=RUN/'quality384M-strict-protection-default-review-20261017/root-review.json'
    strict=pin(strict_path,promotion['strict_default_review_sha256'])
    archive_path=RUN/'quality384M-original-controller-terminal-root-archive-20261017/archive-receipt.json'
    archive=pin(archive_path,promotion['original_terminal_archive_sha256'])
    release_path=RUN/'quality384M-owned-terminal-unit-release-20261017/release-reconciliation-receipt.json'
    release=pin(release_path,promotion['original_successful_unit_release_reconciliation_sha256'])
    cleanup_path=RUN/'quality384M-original-terminal-independent-cleanup-readiness-20261017/cleanup-readiness-receipt.json'
    cleanup=pin(cleanup_path,promotion['fresh_cleanup_sha256'])
    meta_path=GAME/incumbent['metadata_path'];meta=pin(meta_path,incumbent['metadata_sha256'])
    summary_path=GAME/incumbent['campaign_report'];summary=pin(summary_path,incumbent['campaign_sha256'])
    cpu=pin(incumbent['CPU_verification'],incumbent['CPU_verification_sha256'])
    ck('publication_original_exit0_reaped',publication['original_publication_exit']==0 and publication['publication_child_reaped'])
    ck('strict_default_original_exit0_reaped',strict['original_exit']==0 and strict['child_reaped'])
    ck('independent_final_gate_PASS',final['status']=='PASS' and not final['failures'] and all(final['checks'].values()))
    ck('prior_terminal_cleanup_PASS',cleanup['status']=='CLEANUP_READINESS_PASS' and all(cleanup['checks'].values()))
    ck('root_freeze_release_after_adoption_only',promotion['quality_source_freeze_released_after_complete_publication_and_adoption_review'] is True)
    ck('original_retained_exit_archive_matches',archive['original_invocation_id']=='611d7a54ae7e4a649b0e1ed3505a7baa' and archive['original_ExecMainPID']==3723673 and str(archive['original_ExecMainCode'])=='1' and str(archive['original_ExecMainStatus'])=='0' and archive['original_terminal_exit_archived_before_release'] is True)
    evidence={path:{'sha256':sha(path),'expected':expected} for path,expected in meta['evidence_sha256'].items()}
    ck('publication_all7_original_evidence_hashes_held',len(evidence)==7 and all(v['sha256']==v['expected'] for v in evidence.values()))
    audits=[]
    for spec in incumbent['independent_original_row_audits']:
        r=pin(spec['path'],spec['sha256']);audits.append(dict(path=spec['path'],sha256=spec['sha256'],valid=r['valid'],leg=r['leg'],role=r['role']))
    ck('four_independent_original_row_audits_valid',len(audits)==4 and all(v['valid'] is True for v in audits))
    ck('summary_four_finished0_valid_roles',len(summary['legs'])==4 and [v['index'] for v in summary['legs']]==[1,2,3,4] and [v['role'] for v in summary['legs']]==['reference','candidate','reference','candidate'] and all(v['returncode']==0 and v['valid'] is True for v in summary['legs']))
    ck('summary_both_independent_candidate_gates_qualified',summary['outcome']=='qualified_improvement' and summary['qualified_improvement'] is True and [v['index'] for v in summary['candidate_checks']]==[2,4] and all(v['mean_pass'] and v['median_pass'] for v in summary['candidate_checks']))
    ck('candidate_and_metadata_exact_identity',meta['checkpoint_sha256']==incumbent['sha256']=='ac8bc98038a7860f1682e66311fd48657361eaa8ec7aff1f44bd53cf84090963' and meta['protected_checkpoint']==str(GAME/incumbent['checkpoint']) and meta['assessment']['qualified_improvement'] is True and meta['plan_sha256']==summary['plan_sha256']==incumbent['plan_sha256']=='81210cb86ad7cd78b3f9a7f4c764b83aad3364d0d8f0e382e29f340245a54704')
    def stable_file_hash(path):
        p=Path(path);before=p.lstat()
        fields=lambda s:(s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_gid,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
        if not stat.S_ISREG(before.st_mode):raise ValueError('Not regular: '+str(p))
        with os.fdopen(os.open(p,os.O_RDONLY|os.O_NOFOLLOW),'rb') as stream:
            assert fields(os.fstat(stream.fileno()))==fields(before)
            digest=hashlib.file_digest(stream,'sha256').hexdigest()
            assert fields(os.fstat(stream.fileno()))==fields(before)
        assert fields(p.lstat())==fields(before)
        return dict(path=str(p),sha256=digest,device=before.st_dev,inode=before.st_ino,mode=oct(stat.S_IMODE(before.st_mode)),uid=before.st_uid,gid=before.st_gid,nlink=before.st_nlink,bytes=before.st_size,mtime_ns=before.st_mtime_ns,ctime_ns=before.st_ctime_ns)
    protected=stable_file_hash(GAME/incumbent['checkpoint']);oldprotected=stable_file_hash(GAME/promotion['prior_incumbent_preserved']['checkpoint'])
    source=(GAME/incumbent['origin']).stat();snapshot=Path(meta['checkpoints']['candidate']['snapshot']).stat();metastat=meta_path.stat()
    ck('newprotected_sha_bytes_readonly_owned_singlelink',protected['sha256']==incumbent['sha256'] and protected['bytes']==275181008 and protected['mode']=='0o444' and protected['uid']==os.getuid() and protected['nlink']==1)
    ck('newprotected_independent_inode_from_origin_and_snapshot',all((protected['device'],protected['inode'])!=(v.st_dev,v.st_ino) for v in (source,snapshot)))
    ck('published_metadata_readonly_owned_singlelink',stat.S_IMODE(metastat.st_mode)==0o444 and metastat.st_uid==os.getuid() and metastat.st_nlink==1)
    ck('previous256_actual_bytes_unchanged',oldprotected['sha256']=='4f0ef22962aa51bd900be6e89d866b7df828a7eb58fa17dfd574aa32d4267b11' and oldprotected['mode']=='0o444')
    oldmetadata=GAME/promotion['prior_incumbent_preserved']['metadata_path']
    ck('previous256_metadata_unchanged',sha(oldmetadata)=='0be1adcc461da8d63f3523509500709dfb61c95196d38db94e1e707d92ae9598')
    statepath=GAME/'logs/managed-learning-20261015/state.json';state_raw=statepath.read_bytes();current=json.loads(state_raw)
    beforepath=promotion_path.parent/'state-before-adoption.json';before=json.loads(beforepath.read_text())
    extra={'root_promotion_receipt','root_promotion_receipt_sha256'}
    normalized={k:v for k,v in current['incumbent'].items() if k not in extra}
    ck('current384_incumbent_exact_adoption_component',normalized==incumbent)
    ck('current384_root_receipt_links_exact',current['incumbent'].get('root_promotion_receipt')==str(promotion_path) and current['incumbent'].get('root_promotion_receipt_sha256')==proofs[str(promotion_path)]['sha256'])
    ck('previous256_descriptor_exact_preserved',current['previous_incumbent']==before['incumbent']==promotion['prior_incumbent_preserved'])
    ck('all9_old_history_exact_plus_once256',len(before['incumbent_history'])==9 and current['incumbent_history']==before['incumbent_history']+[before['incumbent']] and len(current['incumbent_history'])==10)
    goal=current['optimization_goal'];nextscreen=current['next_screen']
    ck('next_fixed_reference384_all_current_bindings',goal['next_fixed_reference']==goal['protected_incumbent']==nextscreen['reference_checkpoint']==incumbent['checkpoint'])
    ck('goal_saved_active_continuing_after_win',goal['status']=='active' and goal['first_win_completes_goal'] is False and goal['last_confirmed_improvement']['does_not_complete_goal'] is True)
    ck('completed_quality_job_retained_dashboard',current['active_quality_job']['directory']==str(GAME/'logs/managed-learning-20261015/quality-256M-vs-384M-20261017') and nextscreen['current_quality_job']['state']=='finished' and nextscreen['current_quality_job']['outcome']=='qualified_improvement')
    se={p:sha(GAME/p) for p in meta['evaluator_source_hashes']};sx={p:sha(p) for p in meta['execution_source_hashes']}
    ck('quality12_execution4_still_exact_after_release',se==meta['evaluator_source_hashes'] and sx==meta['execution_source_hashes'])
    ck('protection_tool_still_exact',sha(GAME/'tools/protect_quality_winner.py')=='e45965d3057ec8542ab2b05fd2250209e53986a0977fbb1294aa54f64a11f0f0')
    ck('frozen20_terminal_evidence_all_exact',len(cleanup['frozen20_sources'])==20 and all(v['expected']==v['current']==v['archived'] for v in cleanup['frozen20_sources'].values()))
    pre=json.loads(PRE.read_text());main=identify(3032848);thread=Path('/proc/3032848/task/3034065')
    ck('same_main_identity_original_fullmask',main['identity']==pre['bindings']['worker']['trainer'] and main['identity']['starttime_ticks']==28609635 and main['affinity']==MASK)
    ck('same_inference_original_ticks_mask72',int((thread/'stat').read_text().rsplit(')',1)[1].split()[19])==28613780 and sorted(os.sched_getaffinity(3034065))==MASK)
    api1,at1=api('current-api-first.json');health1=api_health(api1,pre)
    time.sleep(1)
    api2,at2=api('current-api-final.json');health2=api_health(api2,pre)
    ck('current_API192_held_recipe_all_health_guards',all(h['healthy'] and all(h[k] for k in ('graphs','native','persistence','exposure')) and not any(h['pipeline_errors'].values()) for h in (health1,health2)))
    ck('current_clocks_after_adoption_advancing_no_rollback',api2['learner_frame_count']>api1['learner_frame_count']>=promotion['main_learner_frames_at_adoption'] and api2['training_steps']>api1['training_steps'] and api2['optimized_samples']>api1['optimized_samples'])
    units={}
    for suffix in ('service','timer'):
        name='robotron-quality-256M-vs-384M-20261017.'+suffix
        r=command(['systemctl','--user','show',name,'--property=LoadState,ActiveState,SubState,MainPID,InvocationID'])
        write('released-quality-'+suffix+'-current-show.json',r)
        p=dict(v.split('=',1) for v in r['stdout'].splitlines() if '=' in v);units[suffix]=p
        ck('quality_'+suffix+'_now_notfound',p.get('LoadState')=='not-found' and p.get('ActiveState')=='inactive')
    end=json.loads(statepath.read_text())
    ck('incumbent_history_reference_component_held_during_review',all(end[k]==current[k] for k in ('incumbent','previous_incumbent','incumbent_history')) and end['optimization_goal']['next_fixed_reference']==incumbent['checkpoint'])
    write('publication-files-stable-identities.json',dict(newprotected=protected,previous256=oldprotected,origin=dict(path=str(GAME/incumbent['origin']),device=source.st_dev,inode=source.st_ino),candidate_snapshot=dict(path=meta['checkpoints']['candidate']['snapshot'],device=snapshot.st_dev,inode=snapshot.st_ino),metadata=dict(path=str(meta_path),mode=oct(stat.S_IMODE(metastat.st_mode)),inode=metastat.st_ino),before_adoption_state_sha256=sha(beforepath)))
    write('observed-adoption-state-components.json',dict(observed_state_sha256=hashlib.sha256(state_raw).hexdigest(),incumbent=current['incumbent'],previous_incumbent=current['previous_incumbent'],incumbent_history=current['incumbent_history'],next_fixed_reference=goal['next_fixed_reference'],next_screen_reference=nextscreen['reference_checkpoint'],saved_goal_status=goal['status']))
    record=dict(schema='robotron384-protected-publication-managed-adoption-independent-v1',status='PASS' if all(checks.values()) else 'AUDIT_NEEDS_REVIEW',observed_start_UTC=dt.datetime.fromtimestamp(start,dt.timezone.utc).isoformat(),observed_end_UTC=dt.datetime.now(dt.timezone.utc).isoformat(),checks=checks,proofs=proofs,protected_file=protected,previous256_file=oldprotected,metadata_sha256=sha(meta_path),summary_sha256=sha(summary_path),four_original_audits=audits,source_hashes=se,execution_hashes=sx,current_main=main,API_first=health1,API_final=health2,current_quality_units=units,collector_sha256=sha(__file__),artifacts=ARTIFACTS,limitations=['Publication/adoption verification only; exact saved scientific audits are hash-bound and their valid/result flags checked, not rerun and no fresh original-row/statistical recomputation','Only raw protected checkpoint bytes hashed with stable FD/path identity; no tensor/deserialization/Torch/NumPy/framework or GPU context','Goal active is saved state/root progress evidence, not an independent get_goal poll','Main/inference identity and masks plus192 API clients checked now; exact192 actor identities were independently verified in prior terminal cleanup6e5, not rescanned here','Historical full state SHA may evolve after ordinary progress/reporting writes; only incumbent/previous/history/reference components required held','Current not-found unit defaults are release evidence only; original exit evidence comes from pinned retained611d archive3f02','No publication, load, restart, signal, unit/source/control/state action or promotion performed by this verifier'])
    write('review-receipt.json',record);fd=os.open(OUT,os.O_DIRECTORY);os.fsync(fd);os.close(fd)
    print(json.dumps(dict(status=record['status'],checks=len(checks),failed=[k for k,v in checks.items() if not v],newprotected_sha256=protected['sha256'],learner_frame_count=api2['learner_frame_count'],receipt=str(OUT/'review-receipt.json'),sha256=sha(OUT/'review-receipt.json')),indent=2))
if __name__=='__main__':main()
