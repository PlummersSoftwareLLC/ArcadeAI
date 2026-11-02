"""Close an original winner publication and adopt its fresh-reference policy.

Default inert. No learner restore, model overwrite, game launch, scientific
retry or reuse of candidate games as the next reference's score pool.
"""
import argparse
import copy
import importlib.util
import json
import os
from pathlib import Path
import time

HERE=Path(__file__).resolve().parent


def protection():
    spec=importlib.util.spec_from_file_location('_fullgame_epoch_protection',HERE/'protect_fullgame_winner_v4.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def validate_report(job,jp,report,p,h):
    p.require(job['schema']=='robotron-recovered-fullgame-winner-protection-job-v1'and job['engineering_only']is False
        and job['source']==h.pin(HERE/'protect_fullgame_winner_v4.py')and job['original_attempt']==1 and job['no_retry']is True,
        'Engineering or foreign protection jobs cannot establish a reference')
    p.require(report['schema']=='robotron-recovered-fullgame-protection-original-CPU-result-v1'and report['status']=='PASS'
        and report['original_job']==jp and report['original_assessment_report']==job['assessment_report']
        and report['original_assessment_closeout']==job['assessment_closeout']
        and report['Torch_imported']is report['GPU_or_MAME_launched']is report['quality_qualified']is report['promotion']
        is report['next_reference_epoch_adopted']is False,'Actual original publication CPU report required')


def prepare_publication_scope(job_path):
    w=protection();p=w.pipeline();h=p.helpers();jp=h.pin(job_path.resolve());job=p.read(jp)
    p.require(job['schema']=='robotron-recovered-fullgame-winner-protection-job-v1'and job['engineering_only']is False,
        'Production winner protection job required before scope preparation')
    w.verify(job,jp)
    directory=Path(jp['path']).parent;config_path=directory/'controller-config.json'
    p.require(not config_path.exists()and not Path(job['output']).exists()and not(directory/'execution-original01').exists(),
        'Original protection configuration/output namespace already consumed')
    ctl=p.load('_epoch_publication_scope_controller',p.ROOT/'tools/quality_capacity_proposal/control_quality32_review_v1.py')
    inputs=[jp,*job['inputs'],h.pin(Path(__file__).resolve())]
    config=dict(unit=job['unit'],output=str(directory/'execution-original01'),argv=['/usr/bin/python3','-I','-B',job['source']['path'],
        '--execute','--job',jp['path'],'--job-sha256',jp['sha256'],'--publish','--source-sha256',job['source']['sha256']],
        properties=['CPUQuota=200%','MemoryMax=4G','MemorySwapMax=0','RuntimeMaxSec=180','TasksMax=128','TimeoutStopSec=5','SendSIGKILL=no'],
        pins=[ctl.pin(pin['path'])for pin in inputs],observation_s=240)
    cp=h.put(config_path,config);p.require(ctl.checked_config(cp['path'])==config,'Actual publication CPU controller interface differs')
    return h.put(directory/'prepared-publication-scope-NOT-LAUNCHED.json',dict(schema='robotron-recovered-fullgame-publication-CPU-preparation-v1',
        protection_job=jp,config=cp,controller=h.pin(Path(ctl.__file__)),source=h.pin(Path(__file__).resolve()),publication_launched=False,
        next_reference_epoch_adopted=False))


def verify_publication(directory):
    """Read-only replay of the actual original short CPU scope and protected copy."""
    w=protection();p=w.pipeline();h=p.helpers();directory=directory.resolve()
    p.require(directory.is_relative_to(p.BASE),'Canonical run-26 protection directory required')
    jp=h.pin(directory/'job.json');job=p.read(jp);report_pin=h.pin(Path(job['output'])/'report.json');report=p.read(report_pin)
    validate_report(job,jp,report,p,h)
    cfg_pin=h.pin(directory/'controller-config.json');cfg=p.read(cfg_pin)
    p.require(cfg['argv']==['/usr/bin/python3','-I','-B',job['source']['path'],'--execute','--job',jp['path'],
        '--job-sha256',jp['sha256'],'--publish','--source-sha256',job['source']['sha256']]
        and cfg['unit']==job['unit']and cfg['properties']==['CPUQuota=200%','MemoryMax=4G','MemorySwapMax=0','RuntimeMaxSec=180',
        'TasksMax=128','TimeoutStopSec=5','SendSIGKILL=no']and cfg['observation_s']==240,
        'Actual original publication source/job/argv/resource declaration differs')
    ctl=p.load('_epoch_short_CPU_controller',p.ROOT/'tools/quality_capacity_proposal/control_quality32_review_v1.py');ctl.checked_config(cfg_pin['path'])
    for pin in cfg['pins']:p.require(ctl.pin(pin['path'])==pin,'Original publication launch input changed')
    root=Path(cfg['output']);owner_pin=h.pin(root/'root-original-identity.json');closure_pin=h.pin(root/'root-original-result-and-owned-release.json')
    owner=p.read(owner_pin);closure=p.read(closure_pin)
    archive=p.load('_epoch_original_archive',p.ROOT/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py')
    fields=archive.archived_closure(closure,owner,p.read,exit_zero=True)
    p.require(owner['unit']==cfg['unit']and owner['pid']==report['actual_PID']and closure['original']==owner
        and all(token in fields['ExecStart']for token in cfg['argv'])and'CUDA_VISIBLE_DEVICES='in fields['ExecStart'],
        'Actual original publication scope/CPU argv differs')
    expected=dict(CPUQuotaPerSecUSec='2s',MemoryMax=str(4<<30),MemorySwapMax='0',RuntimeMaxUSec='3min',TasksMax='128',
        TimeoutStopUSec='5s',SendSIGKILL='no',Restart='no',NRestarts='0',ExecMainCode='1',ExecMainStatus='0')
    p.require(all(fields.get(key)==value for key,value in expected.items()),'Actual original publication CPU resources/exit differ')
    proc=Path('/proc',str(owner['pid']),'stat')
    p.require(not proc.exists()or int(proc.read_text().rsplit(')',1)[1].split()[19])!=owner['starttime_ticks'],'Original publication birth remains')
    p.require(all(ctl.show(unit)['LoadState']=='not-found'for unit in (owner['unit'],owner['timer'])),'Original publication unit/timer remains')
    command=p.read(h.pin(root/'original-first-observed-show-command.json'))
    live=dict(line.split('=',1)for line in p.read(command['stdout'],False).decode().splitlines()if'='in line)
    p.require(live['MainPID']==str(owner['pid'])and live['InvocationID']==owner['invocation_id']
        and live['ControlGroup'].startswith('/user.slice/')and not Path('/sys/fs/cgroup'+live['ControlGroup']).exists(),
        'Original live owner/cgroup join differs or remains')
    checked=w.verify(job,jp)
    publisher=p.ROOT/'tools/startup_policy_journal_proposal/protect_certified_quality32_current_lr125_winner_v1.py'
    p.require(report['publisher_source']==h.pin(publisher)and report['publisher_source']['sha256']==w.PUBLISHER_SHA,
        'Actual validated immutable publication routine differs')
    model=report['protected_checkpoint'];metadata_pin=report['protected_metadata'];metadata=p.read(metadata_pin)
    destination=p.ROOT/'models_dqn/managed-incumbents'
    p.require(model['path']==str(destination/(job['label']+'.pt'))and metadata_pin['path']==model['path']+'.json'
        and model['sha256']==checked['candidate_source']['sha256']and model['bytes']==checked['candidate_source']['bytes']
        and model['identity']['mode']==metadata_pin['identity']['mode']=='0o444'
        and model['identity']['nlink']==metadata_pin['identity']['nlink']==1,
        'Exact independently copied read-only protected policy/metadata required')
    h.checked(model)
    p.require(metadata['schema']=='robotron-recovered-fullgame-protected-winner-v1'and metadata['root_protection_job']==jp
        and metadata['protected_checkpoint']==model['path']and metadata['checkpoint_sha256']==model['sha256']
        and metadata['evidence_sha256']==checked['evidence_sha256']and metadata['assessment']==checked['assessment']
        and metadata['candidate_saved_clocks']==checked['candidate_saved_clocks'],
        'Protected metadata does not bind the actual confirmed candidate/evidence')
    return dict(job=job,job_pin=jp,report=report,report_pin=report_pin,config=cfg_pin,owner=owner_pin,closure=closure_pin,
        protected_checkpoint=model,protected_metadata=metadata_pin,verified=checked)


def close_publication(directory):
    w=protection();p=w.pipeline();h=p.helpers();checked=verify_publication(directory)
    closer=p.load('_epoch_independent_publication_CPU_close',HERE/'close_engineering_cpu_scope_v2.py')
    scope=closer.close(directory)
    again=verify_publication(directory)
    p.require(again['verified']['evidence_sha256']==checked['verified']['evidence_sha256']
        and again['protected_checkpoint']==checked['protected_checkpoint'],'Publication evidence changed during independent closure')
    return h.put(directory.resolve()/'independent-winner-publication-closeout.json',dict(
        schema='robotron-recovered-fullgame-winner-publication-closeout-v1',status='PASS_PROTECTED_COPY_AND_ORIGINAL_CPU_SCOPE',
        protection_job=checked['job_pin'],actual_report=checked['report_pin'],actual_CPU_closeout=scope,
        original_config=checked['config'],original_owner=checked['owner'],original_closure=checked['closure'],
        protected_checkpoint=checked['protected_checkpoint'],protected_metadata=checked['protected_metadata'],
        previous_reference_epoch=checked['job']['previous_reference_epoch'],saved_clocks=checked['verified']['candidate_saved_clocks'],
        source=h.pin(Path(__file__).resolve()),real_policy_protected=True,next_reference_epoch_adopted=False))


def epoch_value(closeout_pin,closeout,verified):
    return dict(schema='robotron-next-fixed-reference-policy-epoch-v1',created_unix_s=time.time(),engineering_only=False,
        reference_policy=closeout['protected_checkpoint'],protected_metadata=closeout['protected_metadata'],protection_closeout=closeout_pin,
        previous_reference_epoch=closeout['previous_reference_epoch'],previous_reference_policy=verified['reference']['policy'],
        prior_policy_integrity=verified['prior_protected_files'],saved_clocks=closeout['saved_clocks'],
        status='PROTECTED_POLICY_ADOPTED_FRESH_NEXT_STUDY_REFERENCE_SCORES_NOT_YET_COLLECTED',next_reference_score_pool=None,
        prior_candidate_games_reused_as_next_reference=False,requires_new_R1_plus_R2_in_next_controlled_campaign=True,
        candidate_gates_each=dict(mean_ratio_at_least=1.05,median_preserved=True,minimum_complete_games=64,all32_slots=True,
            all_selected_full_games=True,all_runtime_audits=True,no_pooling=True,no_scientific_retry=True),
        quality_confirmation_only=verified['assessment'],causal_learning_speed_gain_established=False,
        useful_throughput_gain_established=False,live_learner_restored=False)


def updated_state(state,epoch_pin,epoch,root):
    result=copy.deepcopy(state);goal=result['optimization_goal'];previous=epoch['previous_reference_epoch']
    if epoch['schema']!='robotron-next-fixed-reference-policy-epoch-v1'or epoch['engineering_only']is not False:
        raise ValueError('Actual production reference epoch required')
    if goal['next_fixed_reference_epoch']!=previous or goal['current_fixed_reference_policy']!=epoch['previous_reference_policy']:
        raise ValueError('Current fixed-reference epoch/policy changed')
    if goal.get('scientific_job_running')or goal.get('performance_job_running'):
        raise ValueError('A scientific/performance workload is still active')
    if epoch['next_reference_score_pool']is not None or epoch['prior_candidate_games_reused_as_next_reference']is not False \
        or epoch['requires_new_R1_plus_R2_in_next_controlled_campaign']is not True:
        raise ValueError('Next reference must use fresh R1+R2; candidate-score reuse is forbidden')
    if epoch['candidate_gates_each']!=dict(mean_ratio_at_least=1.05,median_preserved=True,minimum_complete_games=64,
        all32_slots=True,all_selected_full_games=True,all_runtime_audits=True,no_pooling=True,no_scientific_retry=True):
        raise ValueError('Complete-game confirmation rules changed')
    # An active registration may be removed only by the caller after it proves
    # that registration is this exact fully closed winning sequence.
    if result.get('active_quality_job'):raise ValueError('Active quality registration must be independently closed first')
    reference=epoch['reference_policy'];relative=Path(reference['path']).relative_to(root).as_posix()
    goal.update(previous_fixed_reference_epoch=previous,next_fixed_reference_epoch=epoch_pin,current_fixed_reference_policy=reference,
        protected_incumbent=relative,next_fixed_reference=relative,current_fixed_reference_pool=None,next_fixed_reference_score_pool=None,
        current_complete_game_winner_closeout=epoch['protection_closeout'],
        last_progress='Confirmed complete-game winner protected; next fixed policy adopted with fresh R1+R2 scores still required.')
    result['updated_unix_s']=time.time();return result


def adopt(closeout_path,epoch_path):
    w=protection();p=w.pipeline();h=p.helpers();cp=h.pin(closeout_path.resolve());closed=p.read(cp)
    p.require(closed['schema']=='robotron-recovered-fullgame-winner-publication-closeout-v1'
        and closed['status']=='PASS_PROTECTED_COPY_AND_ORIGINAL_CPU_SCOPE'and closed['real_policy_protected']is True
        and closed['next_reference_epoch_adopted']is False and closed['source']==h.pin(Path(__file__).resolve()),
        'Actual independently closed winner publication required')
    directory=Path(closed['protection_job']['path']).parent;checked=verify_publication(directory)
    p.require(closed['protection_job']==checked['job_pin']and closed['actual_report']==checked['report_pin']
        and closed['original_config']==checked['config']and closed['original_owner']==checked['owner']
        and closed['original_closure']==checked['closure']and closed['protected_checkpoint']==checked['protected_checkpoint']
        and closed['protected_metadata']==checked['protected_metadata'],'Winner closeout belongs to other original evidence')
    cpu=p.read(closed['actual_CPU_closeout'])
    p.require(cpu['actual_exit']==0 and cpu['original_job']==checked['job_pin']and cpu['actual_report']==checked['report_pin']
        and cpu['actual_CPU_cores']==2 and cpu['actual_memory_bytes']==4<<30 and cpu['actual_runtime_limit_s']==180
        and cpu['all_six_original_descriptors_and_resources_argv_birth_unit_timer_cgroup_and_owned_release_verified']is True,
        'Independent original protection CPU closeout differs')
    epoch_path=epoch_path.resolve();p.require(epoch_path.parent==directory and not epoch_path.exists(),'Unused epoch path inside original protection directory required')
    state_path=p.ROOT/'logs/managed-learning-20261015/state.json';before=state_path.read_bytes();state=json.loads(before)
    active=state.get('active_quality_job')
    if active:
        p.require(active['state']=='finished'and not active.get('pending_owned_scope_audit'),'Active quality sequence is not fully closed')
        sequence=p.read(active['sequence_precommit']);final_close=p.read(checked['job']['assessment_closeout'])
        p.require(sequence['assessment_preparation']==final_close['assessment_preparation']
            and sequence['output']==active['directory'],'Active quality registration belongs to another sequence')
        state['active_quality_job']=None
    epoch=epoch_value(cp,closed,checked['verified']);ep=h.put(epoch_path,epoch)
    result=updated_state(state,ep,epoch,p.ROOT);encoded=(json.dumps(result,separators=(',',':'),allow_nan=False)+'\n').encode()
    p.require(len(encoded)<1<<20,'Canonical reference update exceeds reader size bound')
    backup=directory/'state-before-reference-adoption.exact.json'
    with backup.open('xb')as stream:stream.write(before);stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
    p.require(state_path.read_bytes()==before,'Concurrent canonical update; no reference overwrite')
    tmp=state_path.with_name('state.fullgame-reference-adoption.tmp')
    with tmp.open('xb')as stream:stream.write(encoded);stream.flush();os.fchmod(stream.fileno(),0o664);os.fsync(stream.fileno())
    p.require(state_path.read_bytes()==before,'Concurrent canonical update; no reference overwrite');os.replace(tmp,state_path)
    fd=os.open(state_path.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)
    p.require(json.loads(state_path.read_bytes())==result,'Canonical adopted reference readback differs')
    return h.put(directory/'independent-reference-adoption-readback.json',dict(schema='robotron-recovered-fullgame-reference-adoption-v1',
        status='PROTECTED_POLICY_ADOPTED_FRESH_REFERENCE_SCORES_REQUIRED',epoch=ep,publication_closeout=cp,
        canonical_preimage=h.pin(backup),all_prior_protected_files_preserved=True,next_reference_score_pool=None,
        prior_candidate_games_reused_as_reference=False,source=h.pin(Path(__file__).resolve()),live_learner_restored=False))


if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--prepare-scope',action='store_true');a.add_argument('--job',type=Path)
    a.add_argument('--close-publication',action='store_true');a.add_argument('--adopt',action='store_true')
    a.add_argument('--directory',type=Path);a.add_argument('--closeout',type=Path);a.add_argument('--epoch-output',type=Path);args=a.parse_args()
    if args.prepare_scope:print(json.dumps(prepare_publication_scope(args.job)),flush=True)
    elif args.close_publication:print(json.dumps(close_publication(args.directory)),flush=True)
    elif args.adopt:print(json.dumps(adopt(args.closeout,args.epoch_output)),flush=True)
    else:print('PLAN_ONLY_NO_READS_OR_ACTIONS')
