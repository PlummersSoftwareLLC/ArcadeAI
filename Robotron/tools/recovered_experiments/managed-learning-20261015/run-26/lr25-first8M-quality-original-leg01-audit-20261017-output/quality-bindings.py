"""Unselected LR25 first durable endpoint frozen-policy quality metadata; no import-time I/O.

Same owner/CE phase, restored .5 live control, separate genuine .25 saved CPU.
This validates model-policy eligibility, never causal LR/sample/wall-time efficacy.
"""
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import stat
import shlex

GAME = Path('/home/dave/source/repos/ArcadeAI/Robotron')

REFERENCE = GAME/'models_dqn/managed-incumbents/freshCE-543M-confirmed.pt'

REFERENCE_SHA = '8b86546355ade166937a8287a008c7854276ed773a103eb815287dde00d6fb7e'

REFERENCE_META_SHA = 'b080f538f84e9c76739b9d142a2065a55d1292c3dbdcb01806003a14339956d5'

CLOCKS = ('training_steps','optimized_samples','learner_frame_count','frame_count')

OWNER_KEYS = {'pid','starttime_ticks','unit','invocation_id','cgroup'}

LIMIT = 4 << 20

EVALUATOR = {'tools/run_frozen_sidecar.py': 'cd034413c2fd8a56bb9d22f8df86889939edfad041ee4e2e0210a831b5f9fe90', 'tools/sidecar_boot.py': 'f06492e6d96cd472d9f0073b4c643e820bcacb6a96c5f542a59d6b6874e62362', 'Scripts/main.lua': '060f838359d35ef6c87b96dfe02ad34618ef974d5a43fefcb74320ebe9deecaf', 'Scripts/robotron_socket_wait.c': 'fc9ed2719839f72e36346d0886e5b32116a167d49414b506dc8b5f4252464cfc', 'Scripts/dqn/config.py': '19abcbde4d08cf8465b82185ac6dd52eb8965adb8611584e0677c4c7ff21d1fd', 'Scripts/dqn/model.py': 'bcd174f05610c6f773ca8c53f9155206eba4f7b6a11383516ddd71f3b513eeb4', 'Scripts/dqn/actor_tags.py': 'fc5b868a7fb68d4ab7ba65ba872ea0e845759af6143edfe648239d57cb7f1591', 'Scripts/dqn/socket_server.py': 'd99dd2782fc3e8f67670aefb398ed0dfdc1fd859432e24c8bd8dea4da2825214', 'Scripts/dqn/game_journal.py': '10827d786becfd19c386bddfbce85f1ab5ace5349d87717305e4044a2843edb0', 'Scripts/dqn/managed_measurement.py': '9649d0ba199bdc0943202164da7a9058e5d578b9c411ce26a950b2595c7e96e6', 'Scripts/dqn/inference_actor.py': '7cc812adeab8dc7cb989f9024592767928afa786966b85f3488023fb8d6b34ce', 'Scripts/dqn/nstep_buffer.py': 'e46f03e9a626b3a24dea702344b0bbf050f1fdc5af672fc8fc9d18e6afef74c1'}

EXECUTION = {'/home/dave/source/repos/ArcadeAI/Robotron/tools/run_quality_campaign.py': '574e56f28499c751c639ee8a3474eecd5ca8de8c896da3dd44d5e4fc2fe60128', '/home/dave/source/repos/ArcadeAI/Robotron/tools/run_frozen_sidecar.py': 'cd034413c2fd8a56bb9d22f8df86889939edfad041ee4e2e0210a831b5f9fe90', '/home/dave/source/repos/ArcadeAI/Robotron/tools/compare_sidecar_measurements.py': '879590b64e760037a81da2ff574d5994d9259cf1746b8e406177e2220d37c746', '/home/dave/source/repos/ArcadeAI/Robotron/tools/compare_frozen_measurements.py': '53f744737a722fec2760c0001dc5747b19b05e07a1de8699764c781f04da6be0'}

CANDIDATE_SOURCES = {'agent.py': '865a0df717b39951b7f7c516e4a962e3d48cf4d3dc11295ff266e58653e6c74b', 'training.py': '90b847856f810cb4f52513a4bd0625b2d15d4801107bff398060faae25bc4be4', 'loss_kernel.py': '23eb8fc0d8409c9f31ef26ec4596da9c2257e3985abbbfa7d5fbdcb337e21f67', 'config.py': '19abcbde4d08cf8465b82185ac6dd52eb8965adb8611584e0677c4c7ff21d1fd', 'priority_phase.py': 'ee3c0d02bc1eab55e92ffd605c3736fe5a0ef905a8a8ee242c687301ea2b7c5b'}


SCHEMA='robotron-lr25-first-durable-endpoint-quality-bindings-v1'
Q=GAME/'tools/kl_priority_mixture_proposal/raw_kl_sequential_trial_proposal'
PHASE=Q/'lr25_phase_cpu_verifier_proposal/verify_phase_snapshot_lr25.py'
PHASE_SHA='d73b7381adc6405af41cdfcaa910ec1f444bc66935616f6f94e6e804faad0b5f'
STRICT_SHA='0854f1437510a4264bc922d241e76350ee3209963bd4f28ce9b8a826e6cb159b'
BASE_SHA='7d1103daf2a77be8250884cb75ce04a640000f04b4376e994d493bc6fd0f7ead'
ENTRY_PHASE_SHA='b2e732dc731b2b601f7499d2cafd5841896daf2b0713d496b98cb6b8d7279519'
ENTRY_STRICT_SHA='9ef38e17e1b9eee3f6c43e40005812f2ebe3cff16d08bf61d3e820c2d41134c8'
CPU_JOB_SCHEMA='robotron-lr25-phase-snapshot-checkpoint-CPU-job-v1'
CPU_RESULT_SCHEMA='robotron-lr25-phase-snapshot-checkpoint-CPU-result-v1'
DRIVER=Q/'lr25_hot_window_driver_reviewed2_proposal/run_hot_window.py'
DRIVER_SHA='35c774c87827252ec623211110f887e98da6da728cb67b2cfa039f894f5a33b5'
OBSERVER=Q/'lr25_hot_window_observer_proposal/hot_window_observer.py'
OBSERVER_SHA='f1faaa37da0fc91f943b00fccc96f1e1ff31fbfa741f00bcf30183a5e10f51ab'
FOUNDER='9b3b839fe39044538412f0f78a8c28feae60170ea2d1c363d21efeead17d84d1'
KNOWN_ACTUAL={'driver_job': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/lr25-hot-window-root-preparation-20261017/root-hot-LR025-driver-job.json', 'sha256': '3724ff12bd4af4298e80ad975fb4d35c0fd470be3172fac5dadeef10a7d1bda9', 'bytes': 3252}, 'precommit': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/lr25-hot-window-root-preparation-20261017/root-hot-LR025-precommit.json', 'sha256': 'b4981e7bd35db28d9c5edab848ef084210062306b4c906a72f410d112ad2ed54', 'bytes': 4331}, 'driver_identity': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/lr25-hot-window-root-preparation-20261017/actual-hot-driver-execution/root-observed-original-driver-identity.json', 'sha256': '862b792abd5610ce4dd09ab4320a12395798a2b2cfc46b7045e1acdbe47e9254', 'bytes': 886}, 'entry_CPU': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/lr25-prechange-entry-numeric-CPU-root-execution-20261017/entry-CPU-report-readonly.json', 'sha256': '2affe1109838a0419f49dcc0763254c3030ee007f22a1d274627fab2d76aa108', 'bytes': 63585}, 'prior_release': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/CE2048-trial02-first-LATCH-followup-all4-final-closure-root-20261017/root-explicit-current-quality-source-freeze-release.json', 'sha256': 'f43a0356805d21d3ee29c47d637692676a603abe44e4be38cc6409ee33b83821', 'bytes': 3365}}
CANDIDATE=None  # Set only after the explicit authenticated binding validates.
EVIDENCE_KEYS={'driver_job','precommit','driver_result','driver_identity','driver_completion',
    'entry_CPU','entry_CPU_release','window_job','window_result','decision','durability','barrier',
    'endpoint_trigger','phase_cpu_job','phase_cpu_report','phase_cpu_completion','CPU_execution',
    'restored_control','prior_release'}


def require(value, message):
    if not value:
        raise ValueError(message)


def identity(info):
    return dict(device=info.st_dev, inode=info.st_ino, bytes=info.st_size,
        mtime_ns=info.st_mtime_ns, ctime_ns=info.st_ctime_ns,
        mode=oct(stat.S_IMODE(info.st_mode)), uid=info.st_uid, nlink=info.st_nlink)


def read_bytes(pin, *, allow_empty=False):
    require(set(pin) == {'path', 'sha256', 'bytes', 'identity'}, 'Full metadata PIN required')
    path = Path(pin['path'])
    require(path.is_absolute() and path == path.resolve(strict=True) and
        path.suffix not in ('.pt','.pth','.npy','.npz'), 'Canonical metadata path required; no tensor bodies')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and (0 if allow_empty else 1) <= before.st_size <= LIMIT
            and before.st_uid == os.getuid() and before.st_nlink == 1
            and stat.S_IMODE(before.st_mode) == 0o444, 'Owned readonly bounded metadata required')
        data = stream.read(LIMIT + 1)
        require(identity(os.fstat(stream.fileno())) == identity(before) == identity(path.lstat())
            == pin['identity'], 'Metadata changed during read')
    require(len(data) == pin['bytes'] and hashlib.sha256(data).hexdigest() == pin['sha256'], 'Metadata PIN differs')
    return data


def four(value):
    result = {key: value[key] for key in CLOCKS}
    require(all(type(v) is int and v > 0 for v in result.values()), 'Four positive actual clocks required')
    return result


def flat(pin):
    return dict(path=pin['path'], sha256=pin['sha256'], **pin['identity'])


def triple(value):
    return {key:value[key] for key in ('path','sha256','bytes')}


def owner(value):
    require(set(value)==OWNER_KEYS and type(value['pid']) is int and value['pid']>0 and
        type(value['starttime_ticks']) is int and value['starttime_ticks']>0 and
        re.fullmatch('[0-9a-f]{32}',value['invocation_id'] or '') and
        value['cgroup'].endswith('/'+value['unit']), 'Exact actual five-key owner required')
    return value


def check_reference(reference,reader):
    require(set(reference)=={'path','sha256','bytes','metadata'} and reference['path']==str(REFERENCE) and
        reference['sha256']==REFERENCE_SHA and reference['bytes']==275192614 and
        reference['metadata']['path']==str(REFERENCE)+'.json' and reference['metadata']['sha256']==REFERENCE_META_SHA,
        'Actual protected543 reference/metadata required')
    meta=reader(reference['metadata'])
    require(meta['schema']=='robotron-protected-quality-winner-v1' and meta['protected_checkpoint']==str(REFERENCE) and
        meta['checkpoint_sha256']==REFERENCE_SHA and meta['assessment']['qualified_improvement'] is True,
        'Protected543 publication metadata differs')


def terminal(execution, read_text, read_journal, *, exit_status=0, result="success"):
    owner = execution['owner']; require(set(owner) == OWNER_KEYS, 'Exact original controller/deadline identity required')
    fields = dict(line.split('=', 1) for line in read_text(execution['show']).splitlines() if '=' in line)
    require(fields['LoadState'] == 'loaded' and fields['MainPID'] == '0'
        and fields['ExecMainPID'] == str(owner['pid']) and fields['InvocationID'] == owner['invocation_id']
        and fields['NRestarts'] == '0' and fields['ExecMainCode'] == '1'
        and fields['ExecMainStatus'] == str(exit_status) and fields['Result'] == result,
        'Exact original retained execution exit/result required; failures cannot be relabelled')
    require(read_text(execution['cat']) and execution['archived_before_release'] is True and execution['released'] is True,
        'Original unit/cat/invocation archived before actual release required')
    read_journal(execution['journal'])  # An honestly archived empty invocation journal is valid.



def read(pin):
    return json.loads(read_bytes(pin),parse_constant=lambda value:(_ for _ in ()).throw(ValueError(value)))


def read_raw(pin):
    # Only explicitly named raw API/event/outcome witnesses use this reader.
    return json.loads(read_bytes(pin))


def same_raw(left,right):
    return json.dumps(left,sort_keys=True,allow_nan=True)==json.dumps(right,sort_keys=True,allow_nan=True)


def finite(value):
    require(type(value) in (int,float) and math.isfinite(value),'Finite numeric evidence required')
    return value


def load_observer():
    require(hashlib.sha256(OBSERVER.read_bytes()).hexdigest()==OBSERVER_SHA,'Selected pure observer source differs')
    spec=importlib.util.spec_from_file_location('_quality_lr25_pure_observer',OBSERVER)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def check_cpu(job,proof,completion,candidate):
    require(job['schema']==CPU_JOB_SCHEMA and job['verifier_sha256']==PHASE_SHA and
        job['strict_phase_base_sha256']==STRICT_SHA and job['original_strict_base_sha256']==BASE_SHA,
        'Genuine d73/0854 LR25 candidate CPU required; old2048/b2e reports are incompatible')
    spec=job['phase_snapshot'];owner(spec['owner'])
    require(spec['purpose']=='candidate' and type(spec['observed_clients']) is int and spec['observed_clients']==192 and
        spec['expected_phase']['metric']=='ce' and spec['expected_phase']['valid'] is True and
        spec['expected_phase']['founder_phase_record_sha256']==FOUNDER and
        job['lr25_context']['schema']=='robotron-live-CE-lr25-hot-control-context-v1',
        'Actual live192 unchanged-CE LR25 endpoint role required')
    source,copied=job['source'],job['verification_copy']
    require(set(candidate)=={'tag','path','sha256','bytes'} and
        re.fullmatch('[A-Za-z0-9_-]{1,80}',candidate['tag'] or '') and
        candidate['path']==str(GAME/'models_dqn/managed-checkpoints'/(candidate['tag']+'.pt')) and
        source['path']==candidate['path'] and candidate['sha256']==source['sha256']==copied['sha256'] and
        re.fullmatch('[0-9a-f]{64}',candidate['sha256'] or '') and
        type(candidate['bytes']) is int and 0<candidate['bytes']<=512<<20 and
        candidate['bytes']==source['bytes']==copied['bytes'],'Dynamic first endpoint source/copy descriptor differs')
    require(source['path']!=copied['path'] and
        (source['identity']['device'],source['identity']['inode'])!=(copied['identity']['device'],copied['identity']['inode']) and
        all(p['identity']['mode']=='0o444' and p['identity']['uid']==os.getuid() and p['identity']['nlink']==1 and
            p['identity']['bytes']==candidate['bytes'] for p in (source,copied)),'Independent readonly endpoint copy required')
    require(proof['schema']==CPU_RESULT_SCHEMA and proof['status']=='PASS' and proof['phase_metadata_verified'] is True and
        proof['lr25_hot_context_verified'] is True and proof['script']['sha256']==PHASE_SHA and
        proof['strict_phase_base']['sha256']==STRICT_SHA and proof['original_strict_base']['sha256']==BASE_SHA and
        proof['root_job']==job and proof['sha256']==candidate['sha256'] and proof['bytes']==candidate['bytes'] and
        proof['path']==copied['path'] and proof['source_before']==flat(source) and proof['verification_copy']==flat(copied) and
        proof['actual_restore_or_optimizer_step'] is False and proof['actual_quality_qualification'] is False,
        'Original strict LR25 phase/numeric PASS evidence differs')
    require(proof['cuda_initialized'] is False and proof['visible_cuda_devices']==0 and
        proof['finite']['tensors']==443 and proof['adam_state_count']==81 and proof['adam_group_count']==1 and
        len(proof['adam_uninitialized_parameter_names'])==18 and len(proof['adam_steps'])==81 and
        finite(proof['adam_step_min'])==finite(proof['adam_step_max'])>0 and
        proof['adam_group']['lr']==1.25e-5 and proof['grad_scaler']['scale']>0 and
        set(proof['models'])=={'online_state_dict','target_state_dict'} and
        all(x['strict_cpu_load'] is True for x in proof['models'].values()),'Original finite/model81Adam/scaler evidence incomplete')
    require(set(completion)=={'argv','exit_code'} and completion['exit_code']==0 and
        completion['argv']==[completion['argv'][0],'-Xgil=0','-I','-B',str(PHASE),'--execute','--job',
            proof['job_file']['path'],'--expected-job-sha256',proof['job_file']['sha256'],
            '--expected-verifier-sha256',PHASE_SHA] and Path(completion['argv'][0]).is_absolute(),
        'Genuine exact numerical command/exit0 required; retained outer owner is separate')
    require(all(four(proof['clocks'])[k]>=four(job['clock_floor'])[k] for k in CLOCKS),'Numeric endpoint predates bound floor')
    saved=proof['saved_priority_metric_phase'];expected=spec['expected_phase']
    require(saved['metric']=='ce' and saved['valid'] is True and
        all(saved[k]==expected[k] for k in ('phase_id','root_precommit_sha256','started_from')) and
        saved['phase_record_sha256']==expected['founder_phase_record_sha256'] and
        saved['last_resume_record_sha256']==expected['last_resume_record_sha256'],'Saved unchanged CE founder/resume differs')



def check_CPU_command(execution,completion,text_reader):
    cat=text_reader(execution['cat']);show=text_reader(execution['show'])
    commands=[shlex.split(line.split('=',1)[1]) for line in cat.splitlines()
        if line.startswith('ExecStart=') and line.split('=',1)[1].strip()]
    require(len(commands)==1,'One actual archived ExecStart required')
    argv=commands[0];command=completion['argv']
    require(argv[-len(command):]==command and argv[:5]==['/usr/bin/env','-u','LD_PRELOAD','-u','PYTHONPATH'],
        'Archived retained CPU ExecStart is not the original exact numerical command')
    assignments=argv[5:-len(command)]
    require(all('=' in x for x in assignments),'Exact explicit numerical environment assignments required')
    environment=dict(x.split('=',1) for x in assignments)
    require(len(environment)==len(assignments) and set(environment)=={'CUDA_VISIBLE_DEVICES','PYTHONDONTWRITEBYTECODE',
        'OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','TMPDIR'} and
        environment['CUDA_VISIBLE_DEVICES']=='' and environment['PYTHONDONTWRITEBYTECODE']=='1' and
        all(environment[k]=='2' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')) and
        Path(environment['TMPDIR']).is_absolute(),'Actual CPU CUDAhidden/unset preload+pythonpath/thread context differs')
    field=next((line.split('=',1)[1] for line in show.splitlines() if line.startswith('ExecStart=')),None)
    match=re.search(r'argv\[\]=(.*?) ; ignore_errors=',field or '')
    require(match is not None and shlex.split(match.group(1))==argv,
        'Original full show and unit cat ExecStart differ')


def check_window(driver,pre,result,window,outcome,B,event,receipt,barrier,observer):
    require(result['status']=='CAPTURED_PENDING_ROOT_CPU' and result['CPU_executed'] is False and
        result['qualification_pass'] is False and result['original_control_bytes_restored'] is True and
        result['no_owner_stop_or_model_restore'] is True and result['CPU_must_run_separately'] is True and
        result['window_status']=='LATCH_DURABLE','Successful original endpoint/restoration required; no failed-window escape')
    observer.validate_job(window,B)
    require(driver['schema']=='robotron-root-lr25-hot-window-driver-job-v1' and driver['activation_authorized'] is True and
        window['owner']==pre['owner']==result['owner'] and window['current_phase']==pre['current_phase'] and
        window['experiment']==pre['experiment'] and window['policy']==driver['window']['policy'],
        'Actual root driver/window owner/phase/recipe/policy differs')
    require(window['barrier_completed_clock']==barrier['completed_clock'] and
        window['proofs']['entry_CPU']==pre['entry_CPU'] and window['proofs']['root_precommit']==result['root_job'],
        'Actual barrier/B/driver origin differs')
    require(outcome['status']=='LATCH_DURABLE' and outcome['candidate_requests_allowed']==1 and
        outcome['qualification_pass'] is False and same_raw(outcome['observation'],event) and
        event['schema']==observer.OBSERVATION_SCHEMA and event['state']=='LATCH' and
        event['candidate_requests_allowed']==0 and event['qualification_pass'] is False,
        'Original LATCH grants zero until its original paired durability grants one')
    pair=outcome['durability']
    require(pair['completion']==receipt and same_raw(observer.durable_result(event,pair,window),outcome),
        'Original durable result/receipt differs or completed after fixed cutoff')
    start=window['baseline']['observed_clock'];elapsed=finite(event['observed_monotonic_s'])-start['monotonic_s']
    require(event['boot_id']==start['boot_id'] and event['elapsed_s']==elapsed and 0<=elapsed<=window['policy']['cutoff_s'],
        'Original LATCH origin/cutoff differs')
    base=observer.normalise(B);current=observer.normalise(event['first_eligible_observation'])
    # Age at actual poll is retained in the original event; do not invent/replay intermediate polls.
    require(current['optimizer_identity']==base['optimizer_identity'] and current['replay_identity']==base['replay_identity'] and
        all(current[group][k]>=base[group][k] for group in ('clocks','optimizer','optimizer_since_epoch','categories') for k in base[group]) and
        current['optimizer']['unavailable']==base['optimizer']['unavailable']==0,'Same-B identities/partition/counters regressed')
    require(event['first_eligible_observation']['client_count']==192 and
        event['first_eligible_observation']['managed_experiment']==pre['experiment'] and
        event['first_eligible_observation']['training_enabled'] is True and
        event['first_eligible_observation']['measurement_active'] is False and
        finite(event['first_eligible_observation']['lr'])==1.25e-5,'Original LATCH API recipe scope differs')
    delta={k:current['optimizer'][k]-base['optimizer'][k] for k in observer.COUNTERS};p=event['progress']
    expected=dict(learner_frames=current['clocks']['learner_frame_count']-base['clocks']['learner_frame_count'],
        fleet_frames=current['clocks']['frame_count']-base['clocks']['frame_count'],physical_accepted=current['accepted']-base['accepted'],
        learner_accepted=current['learner_accepted']-base['learner_accepted'],
        physical_by_source={k:current['categories'][k]-base['categories'][k] for k in observer.CATEGORIES},
        logical_steps=current['clocks']['training_steps']-base['clocks']['training_steps'],
        logical_samples=current['clocks']['optimized_samples']-base['clocks']['optimized_samples'],
        optimizer_total=current['optimizer'],optimizer_delta_from_B=delta,optimizer_pending=current['unclassified'],
        AMP_classified_denominator=delta['applied']+delta['amp_skipped'],admitted_samples_from_B=delta['applied']*4096,
        admitted_samples_process_total=current['optimizer']['applied']*4096)
    require(all(p[k]==v for k,v in expected.items()) and p['learner_frames']>=8000000 and p['learner_accepted']>=6000000,
        'Both original learner8M AND DQN+epsilon accepted6M horizons required; no all5 substitute')
    den=expected['AMP_classified_denominator'];require(p['AMP_skip_fraction']==(None if den==0 else delta['amp_skipped']/den),
        'Same-B actual AMP denominator differs')
    return base,current


def check_endpoint(driver,result,job,acquisition,candidate,trigger,entry_clocks,B,current,entry_checkpoint):
    frozen=result['endpoint'];spec=job['phase_snapshot'];tag=driver['tags']['endpoint']
    require(set(frozen)=={'source','verification_copy','acquisition'} and candidate['tag']==tag and
        tag!=driver['tags']['barrier'] and tag!=Path(driver['startup_tag']).stem and
        tag!=Path(entry_checkpoint['path']).stem and
        frozen['source']==job['source'] and frozen['verification_copy']==job['verification_copy'] and
        frozen['acquisition']==spec['acquisition'],'Only predeclared original endpoint is eligible; entry/barrier cannot substitute')
    floor={k:max(entry_clocks[k],B['clocks'][k],current['clocks'][k]) for k in CLOCKS}
    require(job['clock_floor']==floor and acquisition['clock_floor']==floor and
        acquisition['purpose']=='candidate' and acquisition['client_count']==192 and acquisition['tag']==tag and
        acquisition['owner_before']==acquisition['owner_after']==spec['owner'] and
        acquisition['source_checkpoint']==triple(job['source']) and
        all(four(trigger)[k]>=floor[k] for k in CLOCKS),'Endpoint exact max(entry,B,LATCH) floor/fresh trigger differs')
    require(trigger['client_count']==192 and trigger['training_enabled'] is True and trigger['measurement_active'] is False and
        trigger['managed_experiment']==job['experiment'] and finite(trigger['lr'])==1.25e-5,'Endpoint trigger recipe scope differs')
    transition=acquisition['completed_slot_transition']
    require(transition['request_unix_s']<=transition['after_unix_s'] and
        transition['request']['actual_pin']['identity']['inode']==transition['after']['actual_pin']['identity']['inode'] and
        transition['request']['actual_pin']['sha256']==transition['after']['actual_pin']['sha256'] and
        transition['request']['archive']['sha256']==transition['after']['archive']['sha256'],
        'Actual same-inode matched endpoint completion transition required')


def check_restoration(driver,result,restore,original,restored,control25):
    require(result['original_control_archive']['sha256']==driver['control_before']['sha256']==restore['after']['sha256']==
        restore['archive']['sha256'] and result['original_control_archive']['bytes']==driver['control_before']['bytes']==
        restore['after']['bytes']==restore['archive']['bytes'] and restore['after']['path']==driver['control_before']['path'] and
        restore['after']['identity']['mode']==driver['control_before']['identity']['mode'],
        'Same original .5 control bytes/path/mode must be restored; inode may legitimately change')
    require(original==restored and original['lr_scale']==.5 and original.get('measurement') is None and
        control25==dict(original,experiment=result['_candidate_experiment'],lr_scale=.25) and
        restore['before']['sha256']==result['_control25_sha256'],'Only label/.25 changed before exact .5 byte restoration')
    require(result['original_control_archive']['path']!=restore['archive']['path'] and
        (result['original_control_archive']['identity']['device'],result['original_control_archive']['identity']['inode'])!=
        (restore['archive']['identity']['device'],restore['archive']['identity']['inode']),
        'Independent immutable original/restored control archives required')


def check_current(binding,baseline,api,pre,proof,restored,observer):
    anchor=binding['runtime_anchor']
    require(baseline['status']=='PASS' and baseline['main_owner']==anchor['main_owner']==pre['owner'] and
        all(baseline[k]==anchor[k] for k in ('fleet_owner','inference_worker','actors','source_hashes','control_hashes','unit_files','environment_sha256')) and
        len(anchor['actors'])==192 and len(anchor['source_hashes'])>=61 and len(anchor['control_hashes'])==2 and len(anchor['unit_files'])==3,
        'Same-owner fresh restored192/full source-control-unit baseline differs')
    for name,digest in CANDIDATE_SOURCES.items():require(anchor['source_hashes'][str(GAME/'Scripts/dqn'/name)]==digest,'Candidate5 science source changed')
    require(anchor['control_hashes'][str(GAME/'models_dqn/learning_control.json')]==restored['archive']['sha256'],
        'Fresh runtime control must be restored .5 bytes, not endpoint .25 archive')
    require(api['client_count']==192 and api['training_enabled'] is True and api['measurement_active'] is False and
        api['managed_experiment']==binding['experiment'] and finite(api['lr'])==2.5e-5 and
        all(four(api)[k]>=four(proof['clocks'])[k] for k in CLOCKS),'Fresh same-owner API must be restored .5 and at least endpoint clocks')
    current=observer.normalise(api)
    require(current['optimizer_identity']['process_id']==current['replay_identity']['process_id']==pre['owner']['pid'],
        'Fresh API exposure belongs to another owner')


def validate(binding,*,reader=read,raw_reader=read_raw,text_reader=lambda p:read_bytes(p).decode(),
             journal_reader=lambda p:read_bytes(p,allow_empty=True),observer=None):
    global CANDIDATE
    require(set(binding)=={'schema','activation_authorized','experiment','candidate_experiment','reference','candidate',
        'evidence','runtime_baseline','runtime_anchor','predecessor_quality_plan','campaign'} and
        binding['schema']==SCHEMA and binding['activation_authorized'] is True,'Explicit future root quality binding required; template stays disabled')
    check_reference(binding['reference'],reader);e=binding['evidence']
    require(set(e)==EVIDENCE_KEYS,'Exact honest LR25 driver/endpoint/numeric/restoration evidence required')
    raw_keys={'window_result','decision','endpoint_trigger'}
    require(all(triple(e[k])==p for k,p in KNOWN_ACTUAL.items()),'Wrong selected actual LR25 window/entry/precommit')
    v={k:(raw_reader(pin) if k in raw_keys else reader(pin)) for k,pin in e.items()}
    driver,pre,result=v['driver_job'],v['precommit'],v['driver_result'];job,proof,completion=v['phase_cpu_job'],v['phase_cpu_report'],v['phase_cpu_completion']
    require(driver['precommit']==e['precommit'] and result['root_job']==e['driver_job'] and
        result['window_job']==e['window_job'] and result['window_result']==e['window_result'] and result['endpoint_CPU_job']==e['phase_cpu_job'] and
        driver['precommit']==job['lr25_context']['precommit'] and job['lr25_context']['entry_CPU']==pre['entry_CPU']==e['entry_CPU'] and
        binding['candidate_experiment']==job['experiment']==pre['experiment'],'Exact original driver/precommit/endpoint CPU tuple differs')
    require(pre['schema']=='robotron-live-CE-lr25-hot-change-precommit-v1' and
        pre['status']=='ROOT_PRECOMMITTED_AFTER_QUALITY_CLOSURE_AND_FREEZE_RELEASE' and pre['quality_closed'] is True and
        pre['no_weight_or_optimizer_reset'] is True and pre['no_replay_clear'] is True and
        (pre['lr_scale_before'],pre['lr_scale_after'],pre['optimizer_lr_before'],pre['optimizer_lr_after'])==(.5,.25,2.5e-5,1.25e-5) and
        pre['source_freeze_release']==e['prior_release'],'Actual precommitted one-knob hot control context differs')
    released=v['prior_release'];require(released['source_freeze_released'] is True and released['owned_cleanup_complete'] is True and
        released['outcome']=='not_improved' and released['candidate_promoted'] is False,'Actual preceding quality closure/release required')
    entry=v['entry_CPU'];ej=entry['root_job'];es=ej['phase_snapshot'];phase=pre['current_phase']
    require(entry['status']=='PASS' and entry['schema']=='robotron-phase-snapshot-checkpoint-CPU-result-v1' and
        entry['phase_metadata_verified'] is True and entry['script']['sha256']==ENTRY_PHASE_SHA and entry['strict_phase_base']['sha256']==ENTRY_STRICT_SHA and
        es['purpose']=='candidate' and es['observed_clients']==192 and es['owner']==pre['owner']==job['phase_snapshot']['owner'] and
        pre['entry_checkpoint']==triple(ej['source']) and entry['sha256']==ej['source']['sha256']==ej['verification_copy']['sha256'] and
        phase=={k:job['phase_snapshot'][s] for k,s in (('record','phase_record'),('boot_checkpoint','boot_checkpoint'),
            ('boot_verification','boot_verification'),('expected','expected_phase'))},'Genuine .5 live192 entry/unchanged phase/owner required')
    er=v['entry_CPU_release'];require(er['status']=='PASS' and er['original_exit']==0 and er['original_archived_before_release'] is True and
        er['unit_released'] is True and er['CPU_report']==e['entry_CPU'],'Original .5 entry CPU success/archive/release required')
    check_cpu(job,proof,completion,binding['candidate'])
    require(triple(e['phase_cpu_job'])==triple(proof['job_file']) and proof['lr25_precommit']==e['precommit'] and
        proof['lr25_entry_checkpoint']==pre['entry_checkpoint'] and proof['lr25_entry_clocks']==four(entry['clocks']),
        'Actual numeric job/precommit/entry report differs')
    window,outcome,event,receipt=v['window_job'],v['window_result'],v['decision'],v['durability'];obs=observer or load_observer()
    require(window['baseline']['api']['path']==str(Path(driver['output_directory'])/'raw-B-API.json') and
        window['proofs']['barrier']==e['barrier'] and window['proofs']['root_precommit']==e['driver_job'] and
        outcome['durability']['event']==e['decision'] and outcome['durability']['durability']==e['durability'],
        'Exact original post-barrier B/decision/durability PINs required')
    B=raw_reader(window['baseline']['api']);base,current=check_window(driver,pre,result,window,outcome,B,event,receipt,v['barrier'],obs)
    root=Path(driver['output_directory']);seq=event['sequence']
    require(type(seq) is int and seq>=0 and e['decision']['path']==str(root/'observations'/('observation-%04d.json'%seq)) and
        e['durability']['path']==str(root/'observations'/('durability-%04d.json'%seq)) and
        e['endpoint_trigger']['path']==str(root/'endpoint/trigger-API.json') and
        e['restored_control']['path']==str(root/'control50-restored-receipt.json') and
        e['endpoint_trigger'] in job['source_control_context']['provenance'],'Original source-generated endpoint/event paths differ')
    acquisition=reader(job['phase_snapshot']['acquisition'])
    check_endpoint(driver,result,job,acquisition,binding['candidate'],v['endpoint_trigger'],four(entry['clocks']),base,current,pre['entry_checkpoint'])
    restore=v['restored_control'];original=reader(result['original_control_archive']);restored=reader(restore['archive'])
    control25=reader(job['source_control_context']['archived_control']);change=reader(dict(window['proofs']['control_after']))
    require(window['proofs']['control_after']['path']==str(root/'control25-readonly.json') and change==control25 and
        job['source_control_context']['archived_control']['sha256']==window['proofs']['control_after']['sha256'] and
        restore['before']['sha256']==window['proofs']['control_after']['sha256'],'Original .25 control archive differs from endpoint/restore receipt')
    marked=dict(result,_candidate_experiment=pre['experiment'],_control25_sha256=window['proofs']['control_after']['sha256'])
    check_restoration(driver,marked,restore,original,restored,control25)
    require(binding['experiment']==original['experiment'] and binding['experiment']!=binding['candidate_experiment'],
        'Candidate .25 label is distinct from restored live .5 label')
    identity=v['driver_identity'];done=v['driver_completion'];original_return=reader(done['original_return'])
    require(done['schema']=='robotron-root-original-direct-driver-completion-v1' and done['original_identity']==e['driver_identity'] and
        done['returncode']==original_return['returncode']==0 and done['result']==e['driver_result'] and done['one_attempt'] is True and
        done['original_return']['path']==str(Path(e['driver_identity']['path']).with_name('root-original-driver-return.json')) and
        original_return['pid']==identity['pid'] and original_return['starttime_ticks']==identity['starttime_ticks'] and
        original_return['argv']==identity['argv'] and original_return['original_process_untouched'] is True and
        original_return['observation_timeout'] is False and
        identity['argv']==done['argv']==[identity['exe'],'-I','-B',str(DRIVER),'--execute','--job',e['driver_job']['path'],
            '--expected-job-sha256',e['driver_job']['sha256'],'--expected-source-sha256',DRIVER_SHA] and
        type(identity['pid']) is int and identity['pid']>0 and type(identity['starttime_ticks']) is int and identity['starttime_ticks']>0 and
        identity['uid']==os.getuid(),'Actual original direct driver return0/identity required; no invented systemd execution')
    execution=v['CPU_execution'];terminal(execution,text_reader,journal_reader)
    check_CPU_command(execution,completion,text_reader)
    release=reader(execution['release_receipt']);archive=reader(release['original_terminal_archive']);cpu_owner=execution['owner']
    require(release['status']=='PASS' and release['original_exec_code']==1 and release['original_exit']==0 and
        release['original_result']=='success' and release['original_archived_before_release'] is True and
        release['unit_released'] is True and release['CPU_report']==e['phase_cpu_report'] and release['cpu_job']==e['phase_cpu_job'] and
        (release['original_pid'],release['original_starttime_ticks'],release['original_invocation'])==
        (cpu_owner['pid'],cpu_owner['starttime_ticks'],cpu_owner['invocation_id']) and
        archive['full_original_archives']['service_show']['stdout']==execution['show'] and
        archive['full_original_archives']['service_cat']['stdout']==execution['cat'] and
        archive['full_original_archives']['service_journal']['stdout']==execution['journal'] and
        [x['unit'] for x in release['owned_release']]==[execution['timer'],cpu_owner['unit']] and
        all(x['stop_returncode']==0 and x['final_load_state']=='not-found' for x in release['owned_release']),
        'Actual original retained numerical CPU full archives and exact timer-first release required')
    require(execution['job']==e['phase_cpu_job'] and execution['report']==e['phase_cpu_report'] and
        execution['completion']==e['phase_cpu_completion'] and execution['command']==completion['argv'],
        'Retained original CPU owner/archive must join this exact numerical command/job/report')
    baseline=reader(binding['runtime_baseline']);api=raw_reader(baseline['actual_API'])
    check_current(binding,baseline,api,pre,proof,restore,obs)
    fresh=obs.normalise(api)
    require(fresh['optimizer_identity']==base['optimizer_identity'] and fresh['replay_identity']==base['replay_identity'],
        'Same-owner restoration must preserve the original exposure epochs')
    require(baseline['actual_API']['identity']['mtime_ns']>=restore['archive']['identity']['mtime_ns'] and
        baseline['actual_API']['identity']['mtime_ns']>=e['phase_cpu_report']['identity']['mtime_ns'],
        'Root baseline API must be collected after restoration and endpoint CPU')
    predecessor=reader(binding['predecessor_quality_plan'])
    require(binding['predecessor_quality_plan']==released['plan'] and predecessor['evaluator_source_hashes']==EVALUATOR and
        predecessor['execution_source_hashes']==EXECUTION,'Actual immediately preceding evaluator12+execution4 closure differs')
    campaign=binding['campaign']
    for key in ('output_directory','preview_directory','execution_directory'):
        p=Path(campaign[key]);require(p.is_absolute() and p==p.resolve(strict=False) and p.is_relative_to(GAME/'logs/managed-learning-20261015'),'Canonical fresh campaign directory required')
    require(len({campaign[k] for k in ('output_directory','preview_directory','execution_directory')})==3 and
        re.fullmatch('robotron-quality-[A-Za-z0-9_-]+',campaign['unit']) and campaign['reference_label']!=campaign['candidate_label'] and
        campaign['hypothesis'].strip(),'Fresh unique campaign binding required')
    CANDIDATE=Path(binding['candidate']['path'])
    return dict(cpu_job=job,proof=proof,completion=completion,driver=result,window=window,current_phase=phase,
        baseline=baseline,predecessor=predecessor)
