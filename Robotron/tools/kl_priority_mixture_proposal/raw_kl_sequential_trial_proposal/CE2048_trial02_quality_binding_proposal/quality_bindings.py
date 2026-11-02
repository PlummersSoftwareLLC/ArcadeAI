"""Typed CE2048 trial02 ending metadata bindings; no import-time work/actions.

Consumes only the genuine first candidate and newest-state4096 return. No model
body is read by this module, and no playing score or gate is changed here.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat

GAME = Path('/home/dave/source/repos/ArcadeAI/Robotron')
SCHEMA = 'robotron-CE2048-trial02-ending-quality-bindings-v1'
REFERENCE = GAME/'models_dqn/managed-incumbents/freshCE-543M-confirmed.pt'
REFERENCE_SHA = '8b86546355ade166937a8287a008c7854276ed773a103eb815287dde00d6fb7e'
REFERENCE_META_SHA = 'b080f538f84e9c76739b9d142a2065a55d1292c3dbdcb01806003a14339956d5'
TAG = 'CE2048-first-8M-20261017-trial02'
CANDIDATE = GAME/'models_dqn/managed-checkpoints'/(TAG+'.pt')
PHASE = GAME/'tools/kl_priority_mixture_proposal/raw_kl_sequential_trial_proposal/batch2048_phase_cpu_verifier_reviewed2_proposal/verify_phase_snapshot_2048.py'
PHASE_SHA = 'a331b550191a48ab219cf92f2e1c42fc394e038c93609ecac4fb9a722b75e5cd'
STRICT_SHA = '47677509f170c4c3b6a1c03918e02ab13996af1ceafffac29b7536c2fad61f80'
BASE_SHA = '7d1103daf2a77be8250884cb75ce04a640000f04b4376e994d493bc6fd0f7ead'
RETURN_PHASE = GAME/'tools/phase_snapshot_cpu_verifier_proposal/verify_phase_snapshot.py'
RETURN_PHASE_SHA = 'b2e732dc731b2b601f7499d2cafd5841896daf2b0713d496b98cb6b8d7279519'
RETURN_STRICT_SHA = '9ef38e17e1b9eee3f6c43e40005812f2ebe3cff16d08bf61d3e820c2d41134c8'
CPU_JOB_SCHEMA = 'robotron-batch2048-phase-snapshot-checkpoint-CPU-job-reviewed2-v1'
CPU_RESULT_SCHEMA = 'robotron-batch2048-phase-snapshot-checkpoint-CPU-result-reviewed2-v1'
EARLY_SCHEMA = 'robotron-batch2048-early-phase-insurance-result-v1'
HORIZON = GAME/'tools/kl_priority_mixture_proposal/raw_kl_sequential_trial_proposal/batch2048_profile_horizon_proposal/horizon_observer2048.py'
HORIZON_SHA = 'e8809615c3a837da3400f56d58ecdbfd59b13b83c574c65643731afe8b13a124'
PREDECESSOR_PLAN = GAME/'logs/managed-learning-20261015/quality-CE543M-vs-postRecoveryCE-candidate02-20261017/plan.json'
PREDECESSOR_PLAN_SHA = 'e7419e89f607a95e091085b1afeda49064af3d6af038fff7a06201c17b9e2121'
CLOCKS = ('training_steps','optimized_samples','learner_frame_count','frame_count')
OWNER_KEYS = {'pid','starttime_ticks','unit','invocation_id','cgroup'}
LIMIT = 4 << 20
EVALUATOR = {'tools/run_frozen_sidecar.py': 'cd034413c2fd8a56bb9d22f8df86889939edfad041ee4e2e0210a831b5f9fe90', 'tools/sidecar_boot.py': 'f06492e6d96cd472d9f0073b4c643e820bcacb6a96c5f542a59d6b6874e62362', 'Scripts/main.lua': '060f838359d35ef6c87b96dfe02ad34618ef974d5a43fefcb74320ebe9deecaf', 'Scripts/robotron_socket_wait.c': 'fc9ed2719839f72e36346d0886e5b32116a167d49414b506dc8b5f4252464cfc', 'Scripts/dqn/config.py': '19abcbde4d08cf8465b82185ac6dd52eb8965adb8611584e0677c4c7ff21d1fd', 'Scripts/dqn/model.py': 'bcd174f05610c6f773ca8c53f9155206eba4f7b6a11383516ddd71f3b513eeb4', 'Scripts/dqn/actor_tags.py': 'fc5b868a7fb68d4ab7ba65ba872ea0e845759af6143edfe648239d57cb7f1591', 'Scripts/dqn/socket_server.py': 'd99dd2782fc3e8f67670aefb398ed0dfdc1fd859432e24c8bd8dea4da2825214', 'Scripts/dqn/game_journal.py': '10827d786becfd19c386bddfbce85f1ab5ace5349d87717305e4044a2843edb0', 'Scripts/dqn/managed_measurement.py': '9649d0ba199bdc0943202164da7a9058e5d578b9c411ce26a950b2595c7e96e6', 'Scripts/dqn/inference_actor.py': '7cc812adeab8dc7cb989f9024592767928afa786966b85f3488023fb8d6b34ce', 'Scripts/dqn/nstep_buffer.py': 'e46f03e9a626b3a24dea702344b0bbf050f1fdc5af672fc8fc9d18e6afef74c1'}
EXECUTION = {'/home/dave/source/repos/ArcadeAI/Robotron/tools/run_quality_campaign.py': '574e56f28499c751c639ee8a3474eecd5ca8de8c896da3dd44d5e4fc2fe60128', '/home/dave/source/repos/ArcadeAI/Robotron/tools/run_frozen_sidecar.py': 'cd034413c2fd8a56bb9d22f8df86889939edfad041ee4e2e0210a831b5f9fe90', '/home/dave/source/repos/ArcadeAI/Robotron/tools/compare_sidecar_measurements.py': '879590b64e760037a81da2ff574d5994d9259cf1746b8e406177e2220d37c746', '/home/dave/source/repos/ArcadeAI/Robotron/tools/compare_frozen_measurements.py': '53f744737a722fec2760c0001dc5747b19b05e07a1de8699764c781f04da6be0'}
CANDIDATE_SOURCES = {'agent.py': '865a0df717b39951b7f7c516e4a962e3d48cf4d3dc11295ff266e58653e6c74b', 'training.py': '90b847856f810cb4f52513a4bd0625b2d15d4801107bff398060faae25bc4be4', 'loss_kernel.py': '23eb8fc0d8409c9f31ef26ec4596da9c2257e3985abbbfa7d5fbdcb337e21f67', 'config.py': '19abcbde4d08cf8465b82185ac6dd52eb8965adb8611584e0677c4c7ff21d1fd', 'priority_phase.py': 'ee3c0d02bc1eab55e92ffd605c3736fe5a0ef905a8a8ee242c687301ea2b7c5b'}

ACTUAL = {'outer_job': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/CE2048-trial02-final-root-preparation-20261017/one-trial-job-FINAL.json', 'sha256': 'ae8379e7e5f95c0ca43338a6b1fd2dc12a84ca4c0645767045ed9389b1226893', 'bytes': 12428}, 'activation_job': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/CE2048-trial02-final-root-preparation-20261017/activation-job-FINAL.json', 'sha256': '79b572fe448a78d654f4b7b1b8d745e407759fae8c2089815564ccbff03854ee', 'bytes': 376510}, 'trial_core': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/CE2048-trial02-final-root-preparation-20261017/trial-core-FINAL.json', 'sha256': '4055452bf522d8d2b66d83825cf9c11738b2b1320150aaf8d5238aeebbde2fd9', 'bytes': 2299}, 'activation': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/CE2048-trial02-activation-20261017/result.json', 'sha256': '7d7ae0a041ebe5438550d456e9d7d6c46a9015fb6eae93f1365794aee0c0feeb', 'bytes': 321894}}
LAUNCH_OBSERVATIONS = {'trial_controller': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/CE2048-trial02-root-execution-20261017/controller/root-observed-identity-361303817863879.json', 'sha256': '8c640c1bdcb3a365f7631d17c20973ad8156ac5ad6195ffef74816457fb916bb', 'bytes': 281}, 'deadline': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/CE2048-trial02-root-execution-20261017/deadline/root-observed-identity-361276534666574.json', 'sha256': '2528b1e830a7568902662a6021cfbb72123a3535ae497a8a1e2958402d892db4', 'bytes': 279}}

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


def read(pin):
    # Preserve unrelated optional NaN in captured raw API witnesses. Every clock,
    # horizon and time used below is checked by the frozen horizon implementation.
    return json.loads(read_bytes(pin))


def four(value):
    result = {key: value[key] for key in CLOCKS}
    require(all(type(v) is int and v > 0 for v in result.values()), 'Four positive actual clocks required')
    return result


def flat(pin):
    return dict(path=pin['path'], sha256=pin['sha256'], **pin['identity'])



def triple(value):
    return {key:value[key] for key in ('path','sha256','bytes')}


def load_horizon():
    require(hashlib.sha256(HORIZON.read_bytes()).hexdigest()==HORIZON_SHA, 'Exact CE2048 horizon source differs')
    spec=importlib.util.spec_from_file_location('_quality_CE2048_horizon',HORIZON)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def owner(value):
    require(set(value)==OWNER_KEYS and type(value['pid']) is int and value['pid']>0 and
        type(value['starttime_ticks']) is int and value['starttime_ticks']>0 and
        re.fullmatch('[0-9a-f]{32}',value['invocation_id'] or '') and
        value['cgroup'].endswith('/'+value['unit']), 'Exact actual five-key owner required')
    return value


def check_cpu(job, proof, completion, candidate):
    require(job['schema']==CPU_JOB_SCHEMA and job['verifier_sha256']==PHASE_SHA and
        job['strict_phase_base_sha256']==STRICT_SHA and job['original_strict_base_sha256']==BASE_SHA,
        'Actual reviewed2 CE2048 candidate CPU job required')
    spec=job['phase_snapshot'];owner(spec['owner'])
    require(spec['purpose']=='candidate' and type(spec['observed_clients']) is int and
        spec['observed_clients'] in (0,192) and spec['expected_phase']['metric']=='ce' and
        spec['expected_phase']['valid'] is True and job['batch2048_context']['role']=='candidate',
        'Actual candidate acquisition client count/CE2048 role required; early/startup is not a candidate')
    source,copied=job['source'],job['verification_copy']
    require(set(candidate)=={'tag','path','sha256','bytes'} and candidate['path']==str(CANDIDATE) and
        source['path']==candidate['path'] and candidate['tag']==TAG and
        candidate['sha256']==source['sha256']==copied['sha256'] and
        re.fullmatch('[0-9a-f]{64}',candidate['sha256'] or '') and
        candidate['bytes']==source['bytes']==copied['bytes'] and
        type(candidate['bytes']) is int and 0<candidate['bytes']<=512<<20,
        'First selected candidate source/hash/dynamic bytes differ')
    require(source['path']!=copied['path'] and
        (source['identity']['device'],source['identity']['inode'])!=(copied['identity']['device'],copied['identity']['inode']) and
        all(p['identity']['mode']=='0o444' and p['identity']['uid']==os.getuid() and
            p['identity']['nlink']==1 and p['identity']['bytes']==candidate['bytes'] for p in (source,copied)),
        'Independent readonly candidate copy required')
    require(proof['schema']==CPU_RESULT_SCHEMA and proof['status']=='PASS' and proof['phase_metadata_verified'] is True and
        proof['script']['sha256']==PHASE_SHA and proof['strict_phase_base']['sha256']==STRICT_SHA and
        proof['original_strict_base']['sha256']==BASE_SHA and proof['root_job']==job and
        proof['sha256']==candidate['sha256'] and proof['bytes']==candidate['bytes'] and proof['path']==copied['path'] and
        proof['source_before']==flat(source) and proof['verification_copy']==flat(copied) and
        proof['actual_restore_or_optimizer_step'] is False and proof['actual_quality_qualification'] is False and
        proof['configured_batch_size']==proof['actual_producer_batch_size']==2048 and proof['producer_CSV_verified'] is True,
        'Strict phase CPU/actual2048 producer proof differs')
    require(isinstance(completion.get('argv'),list) and len(completion['argv'])==12 and
        Path(completion['argv'][0]).is_absolute() and completion==dict(argv=[completion['argv'][0],'-Xgil=0','-I','-B',str(PHASE),'--execute','--job',
        proof['job_file']['path'],'--expected-job-sha256',proof['job_file']['sha256'],
        '--expected-verifier-sha256',PHASE_SHA],exit_code=0), 'Original inline candidate CPU exact argv/exit0 required')
    require(all(four(proof['clocks'])[k]>=four(job['clock_floor'])[k] for k in CLOCKS), 'Candidate below actual floor')
    saved=proof['saved_priority_metric_phase'];expected=spec['expected_phase']
    require(saved['metric']=='ce' and saved['valid'] is True and
        all(saved[k]==expected[k] for k in ('phase_id','root_precommit_sha256','started_from')) and
        saved['phase_record_sha256']==expected['founder_phase_record_sha256'] and
        saved['last_resume_record_sha256']==expected['last_resume_record_sha256'], 'Saved CE founder/resume differs')


def check_early(early, profile, expected_owner, phase_record, reader):
    require(early['schema']==EARLY_SCHEMA and early['status']=='PASS' and early['role']=='early_insurance' and
        early['owner']==expected_owner and early['phase']['record']==phase_record and early['profile']==profile and
        early['legacy_7d_insurance'] is False and early['eligible_quality_candidate'] is False and early['tag']!=TAG,
        'Distinct genuine typed CE2048 owner192 early result required; no legacy7d alias')
    job=reader(early['phase_cpu_job']);proof=reader(early['phase_cpu_report']);provenance=early['cpu_provenance']
    require(early['phase_cpu_report']==provenance['phase_cpu_report'] and proof['root_job']==job and
        job['schema']==CPU_JOB_SCHEMA and job['verifier_sha256']==PHASE_SHA and job['strict_phase_base_sha256']==STRICT_SHA and
        job['batch2048_context']['role']=='early_insurance' and job['phase_snapshot']['purpose']=='candidate' and
        job['phase_snapshot']['observed_clients']==192 and job['phase_snapshot']['owner']==expected_owner and
        job['phase_snapshot']['phase_record']==phase_record and proof['schema']==CPU_RESULT_SCHEMA and
        proof['status']=='PASS' and proof['phase_metadata_verified'] is True and proof['script']['sha256']==PHASE_SHA and
        proof['strict_phase_base']['sha256']==STRICT_SHA and proof['job_file']['sha256']==early['phase_cpu_job']['sha256'] and
        job['original_strict_base_sha256']==proof['original_strict_base']['sha256']==BASE_SHA and
        proof['sha256']==job['source']['sha256']==job['verification_copy']['sha256'] and
        proof['bytes']==job['source']['bytes']==job['verification_copy']['bytes'] and
        proof['configured_batch_size']==proof['actual_producer_batch_size']==2048 and proof['producer_CSV_verified'] is True,
        'Actual early reviewed2 CPU/producer metadata differs')
    saved=reader(early['saved_receipt']);acquired=reader(job['phase_snapshot']['acquisition'])
    require(saved['role']=='early_insurance' and saved['tag']==early['tag'] and saved['trainer']==expected_owner and
        saved['source']==job['source']==early['frozen']['source'] and saved['acquisition']==job['phase_snapshot']['acquisition'] and
        job['verification_copy']==early['frozen']['verification_copy'] and
        acquired['purpose']=='candidate' and acquired['client_count']==192 and acquired['tag']==early['tag'] and
        acquired['owner_before']==acquired['owner_after']==expected_owner,
        'Actual early saved/request acquisition differs')
    execution=reader(provenance['successful_execution']);completion=reader(provenance['successful_completion'])
    result=reader(provenance['successful_result']);cpu_owner=owner(completion['original_owner'])
    require(execution['kind']==result['kind']=='phase_early_insurance2048' and completion['original_nrestarts']==0 and
        completion['original_pid']==result['original_pid']==cpu_owner['pid'] and
        completion['original_invocation']==result['original_invocation']==cpu_owner['invocation_id'] and
        completion['original_exec_code']==result['original_exec_code']==1 and completion['original_exit']==result['original_exit']==0 and
        completion['result']==result['original_result']=='success' and result['status']=='PASS' and
        result['original_owner']==cpu_owner and result['actual_unit']==execution['unit']==cpu_owner['unit'] and
        result['original_archived_before_release'] is True and result['original_completion']==provenance['successful_completion'] and
        result['numeric_report_sha256']==early['phase_cpu_report']['sha256'], 'Original retained typed early CPU exit/archive differs')
    command=[early['python'],'-Xgil=0','-I','-B','-u',str(PHASE),'--execute','--job',early['phase_cpu_job']['path'],
        '--expected-job-sha256',early['phase_cpu_job']['sha256'],'--expected-verifier-sha256',PHASE_SHA]
    require(execution['command']==command and execution['argv'][-len(command):]==command and execution['job']==early['phase_cpu_job'] and
        [x['unit'] for x in result['releases']]==[execution['timer'],cpu_owner['unit']], 'Actual retained early command/release order differs')
    require(proof['saved_priority_metric_phase']['metric']=='ce' and proof['saved_priority_metric_phase']['valid'] is True and
        all(four(proof['clocks'])[k]>=four(job['clock_floor'])[k] for k in CLOCKS), 'Early saved phase/floor differs')
    return proof


def check_selection(trial, activation, observer, decision, durability, acquisition, cpu, early_proof, horizon):
    require(trial['status']=='COMPLETE' and trial['qualification_pass'] is False and trial['manual_recovery_required'] is False and
        activation['status']=='READY' and activation['mode']=='activate_batch2048' and activation['manual_recovery_required'] is False,
        'Only completed first trial and genuine READY CE2048 activation may prepare quality')
    horizon.validate_job(observer)
    require(activation['owner']==observer['owner']==cpu['phase_snapshot']['owner']==trial['retired_owner'] and
        observer['boot_four_clocks']==activation['boot_four_clocks'], 'Actual original treatment owner/boot differs')
    require(decision['schema']=='robotron-ce-batch2048-horizon-observation-v1' and decision['state']=='LATCH' and
        decision['candidate_requests_allowed']==1 and decision['qualification_pass'] is False,
        'First immutable BOTH-horizon LATCH required')
    start=observer['start_request']
    require(decision['boot_id']==durability['boot_id']==start['boot_id'] and
        decision['elapsed_s']==decision['observed_monotonic_s']-start['monotonic_s'] and 0<=decision['elapsed_s']<=3240 and
        durability['completed_monotonic_s']>=decision['observed_monotonic_s'] and
        durability['elapsed_s']==durability['completed_monotonic_s']-start['monotonic_s']<=3240,
        'Original first decision/durable receipt cutoff/origin differs')
    current=horizon.normalise(decision['first_eligible_observation']);baseline=horizon.normalise(observer['before_resume_api'])
    require(current['optimizer_identity']==baseline['optimizer_identity'] and current['replay_identity']==baseline['replay_identity'],
        'Original owner/epoch changed')
    progress=decision['progress']
    require(progress['learner_frames']==current['clocks']['learner_frame_count']-observer['boot_four_clocks']['learner_frame_count']>=8000000 and
        progress['physical_accepted']==current['accepted']-baseline['accepted']>=6000000 and progress['optimizer_total']==current['optimizer'],
        'Both actual learner/all-five physical horizons required')
    floor={k:max(four(early_proof['clocks'])[k],current['clocks'][k]) for k in CLOCKS}
    phase=activation['startup_phase_proof']['phase'];spec=cpu['phase_snapshot']
    require(spec['phase_record']==phase['record'] and spec['boot_checkpoint']==phase['boot_checkpoint'] and spec['expected_phase']==phase['expected'] and
        acquisition['tag']==TAG and acquisition['purpose']=='candidate' and acquisition['owner_before']==acquisition['owner_after']==observer['owner'] and
        acquisition['client_count']==spec['observed_clients'] and acquisition['clock_floor']==cpu['clock_floor']==floor and
        acquisition['source_checkpoint']==triple(cpu['source']), 'Actual candidate acquisition/first-LATCH floor differs')


def check_return(trial, ce, candidate_clocks):
    require(ce['status']=='READY' and ce['mode']=='return_batch4096' and ce['qualification_pass'] is False and
        ce['manual_recovery_required'] is False and ce['owner']!=trial['retired_owner'], 'Authentic new-owner4096 return required')
    owner(ce['owner']);require(ce['startup_phase_proof']['phase']['expected']['metric']=='ce' and
        ce['startup_phase_proof']['phase']['expected']['valid'] is True, 'Saved CE startup phase proof required')
    require(all(four(ce['boot_checkpoint']['clocks'])[k]>=candidate_clocks[k] for k in CLOCKS), 'Newest boot predates candidate')
    require(ce['healthy']['api']['client_count']==192 and ce['healthy']['api']['training_enabled'] is True and
        ce['healthy']['api']['exposure']['optimizer']['process_id']==ce['owner']['pid'] and
        ce['healthy']['binding']['environment']['DQN_BATCH_SIZE']=='4096', 'Actual returned4096 healthy192 owner differs')
    require(not ce['final_resume']['failures'], 'Returned original actor undo incomplete')


def check_activation_origin(activation, observer, start, before_resume):
    require(observer['trial_core_sha256']==activation['trial_core']['sha256'] and
        observer['start_request']=={key:start[key] for key in ('boot_id','monotonic_s','unix_s')} and
        start['trial_core']==activation['trial_core'] and
        start['phase_record']==activation['startup_phase_proof']['phase']['record'],
        'Original start clock/core was changed or reanchored')
    require(json.dumps(observer['before_resume_api'],sort_keys=True,allow_nan=True)==
        json.dumps(before_resume,sort_keys=True,allow_nan=True) and
        observer['healthy192_monotonic_s']==activation['healthy192_monotonic_s'],
        'Actual startup exposure baseline/healthy observation origin differs')


def check_reference(reference,reader):
    require(set(reference)=={'path','sha256','bytes','metadata'} and reference['path']==str(REFERENCE) and
        reference['sha256']==REFERENCE_SHA and reference['bytes']==275192614 and
        reference['metadata']['path']==str(REFERENCE)+'.json' and reference['metadata']['sha256']==REFERENCE_META_SHA,
        'Actual protected543 reference/metadata required')
    meta=reader(reference['metadata'])
    require(meta['schema']=='robotron-protected-quality-winner-v1' and meta['protected_checkpoint']==str(REFERENCE) and
        meta['checkpoint_sha256']==REFERENCE_SHA and meta['assessment']['qualified_improvement'] is True,
        'Protected543 publication metadata differs')


def terminal(execution, read_text, read_journal):
    owner = execution['owner']; require(set(owner) == OWNER_KEYS, 'Exact original controller/deadline identity required')
    fields = dict(line.split('=', 1) for line in read_text(execution['show']).splitlines() if '=' in line)
    require(fields['LoadState'] == 'loaded' and fields['MainPID'] == '0'
        and fields['ExecMainPID'] == str(owner['pid']) and fields['InvocationID'] == owner['invocation_id']
        and fields['NRestarts'] == '0' and fields['ExecMainCode'] == '1'
        and fields['ExecMainStatus'] == '0' and fields['Result'] == 'success',
        'Original retained execution exit0 required; collected defaults not accepted')
    require(read_text(execution['cat']) and execution['archived_before_release'] is True and execution['released'] is True,
        'Original unit/cat/invocation archived before actual release required')
    read_journal(execution['journal'])  # An honestly archived empty invocation journal is valid.


def validate(binding, *, reader=read, text_reader=lambda pin:read_bytes(pin).decode(),
             journal_reader=lambda pin:read_bytes(pin,allow_empty=True), horizon=None):
    require(set(binding)=={'schema','experiment','reference','candidate','evidence','runtime_baseline','runtime_anchor',
        'original_executions','actual_launch_identities','predecessor_quality_plan','campaign'} and
        binding['schema']==SCHEMA and binding['experiment']=='best10M-fresh3-eps10-cap8-nosmooth', 'Explicit typed2048 quality binding required')
    check_reference(binding['reference'],reader)
    evidence=binding['evidence']
    require(set(evidence)=={'phase_cpu_job','phase_cpu_report','phase_cpu_completion','trial_result','activation','observer','decision',
        'durability','ce_return','early_phase_insurance','deadline_result','owned_cleanup','outer_job','activation_job','trial_core','return_job'},
        'Exact actual trial-ending evidence PIN set required')
    values={key:reader(value) for key,value in evidence.items()}
    for key,expected in ACTUAL.items():require(triple(evidence[key])==expected, 'Wrong authentic selected trial02 '+key)
    cpu,proof,completion=(values[k] for k in ('phase_cpu_job','phase_cpu_report','phase_cpu_completion'))
    check_cpu(cpu,proof,completion,binding['candidate']);require(proof['job_file']['sha256']==evidence['phase_cpu_job']['sha256'], 'CPU root job differs')
    trial,activation,observer,decision,durability,ce=(values[k] for k in ('trial_result','activation','observer','decision','durability','ce_return'))
    outer,activation_job,core=(values[k] for k in ('outer_job','activation_job','trial_core'))
    require(trial['root_job']==evidence['outer_job'] and outer['activation_job']==evidence['activation_job'] and
        outer['trial_core']==activation_job['trial_core']==evidence['trial_core'] and core['status']=='FINAL_PRECOMMITTED_ROOT_AUTHORIZED' and
        core['activation_authorized'] is True and core['mode']==activation_job['mode']=='activate_batch2048' and
        core['phase_id']==activation_job['phase_id']==cpu['phase_snapshot']['expected_phase']['phase_id'] and
        cpu['phase_snapshot']['expected_phase']['root_precommit_sha256']==evidence['trial_core']['sha256'], 'Actual original trial02 jobs/core differ')
    profile=outer['profile'];require(profile==core['batch_profile']==activation_job['batch_profile'], 'Original profile differs')
    early=values['early_phase_insurance'];early_proof=check_early(early,profile,activation['owner'],activation['startup_phase_proof']['phase']['record'],reader)
    require(outer['candidate_tag']==TAG and outer['early_insurance']['tag']==early['tag'] and trial['early_phase_insurance']==evidence['early_phase_insurance'],
        'Original selected first candidate/typed early result differs')
    require(completion['argv'][0]==activation_job['verifier']['python'] and trial['activation']==evidence['activation'] and
        trial['observer']==evidence['observer'] and trial['decision']['event']==evidence['decision']==durability['event'] and
        trial['decision']['durability']==evidence['durability'] and trial['CE_return']==evidence['ce_return'], 'Actual selected evidence joins differ')
    start=reader(activation['start_request'])
    require(observer['trial_core_sha256']==evidence['trial_core']['sha256'] and
        observer['activation_receipt_sha256']==evidence['activation']['sha256'], 'Original activation/core SHA differs')
    check_activation_origin(activation,observer,start,reader(activation['before_resume_api_PIN']))
    require(trial['candidate']['source']==cpu['source'] and trial['candidate']['verification_copy']==cpu['verification_copy'], 'Not original first candidate')
    acquisition=reader(trial['candidate']['acquisition']);require(reader(cpu['phase_snapshot']['acquisition'])==acquisition, 'FINAL candidate acquisition differs')
    check_selection(trial,activation,observer,decision,durability,acquisition,cpu,early_proof,horizon or load_horizon())
    require(ce['ending']['candidate_CPU']==evidence['phase_cpu_report'] and ce['ending']['candidate_saved_clocks']==four(proof['clocks']), 'Return did not consume original candidate CPU')
    check_return(trial,ce,four(proof['clocks']))
    return_job=values['return_job'];newest=reader(ce['boot_checkpoint']['verification']);nj=newest['root_job']
    require(return_job['mode']=='return_batch4096' and return_job['running_phase']==activation['startup_phase_proof']['phase'] and
        return_job['ending_proof']['candidate']==trial['candidate'] and return_job['ending_proof']['decision']==evidence['decision'] and
        return_job['phase_early_insurance_result']==evidence['early_phase_insurance'] and return_job['producer_capture']==early['producer_capture'],
        'Original typed return job/ending differs')
    require(newest['status']=='PASS' and newest['schema']==CPU_RESULT_SCHEMA and newest['phase_metadata_verified'] is True and
        nj['schema']==CPU_JOB_SCHEMA and nj['phase_snapshot']['purpose']=='newest_stopped' and nj['phase_snapshot']['owner']==activation['owner'] and
        nj['batch2048_context']['role']=='newest_stopped' and newest['script']['sha256']==PHASE_SHA and newest['strict_phase_base']['sha256']==STRICT_SHA and
        newest['configured_batch_size']==newest['actual_producer_batch_size']==2048 and newest['producer_CSV_verified'] is True and
        triple(nj['source'])==triple(ce['boot_checkpoint']['source']) and four(newest['clocks'])==four(ce['boot_checkpoint']['clocks']) and
        newest['sha256']==nj['source']['sha256']==nj['verification_copy']['sha256'] and
        newest['bytes']==nj['source']['bytes']==nj['verification_copy']['bytes'] and
        newest['source_before']==flat(nj['source']) and newest['verification_copy']==flat(nj['verification_copy']) and
        nj['phase_snapshot']['phase_record']==activation['startup_phase_proof']['phase']['record'] and
        nj['phase_snapshot']['expected_phase']==activation['startup_phase_proof']['phase']['expected'] and
        newest['actual_restore_or_optimizer_step'] is False and newest['actual_quality_qualification'] is False and
        all(four(newest['clocks'])[k]>=ce['ending']['required_newest_stopped_floor'][k]>=four(proof['clocks'])[k] for k in CLOCKS),
        'Actual newest2048 stopped proof/floor required before4096 boot')
    ce_start=reader(ce['start_request']);ce_phase=ce['startup_phase_proof']['phase'];ce_record=reader(ce_phase['record'])
    ce_cpu=reader(ce['startup_phase_proof']['phase_CPU']);return_core=reader(return_job['trial_core'])
    require(return_core['mode']=='return_batch4096' and return_core['trial_core']==evidence['trial_core'] and
        ce_start['trial_core']==return_job['trial_core'] and ce_start['phase_record']==ce_phase['record'] and
        ce_record['metric']==ce_record['previous_metric']=='ce' and ce_record['action']=='start' and
        ce_record['root_precommit_sha256']==return_job['trial_core']['sha256'] and
        ce_record['checkpoint']==ce_phase['boot_checkpoint']==triple(ce['boot_checkpoint']['source']) and
        triple(ce_phase['boot_verification'])['sha256']==ce['boot_checkpoint']['verification']['sha256'] and
        ce_phase['boot_verification']['bytes']==ce['boot_checkpoint']['verification']['bytes'] and
        ce_cpu['status']=='PASS' and ce_cpu['schema']=='robotron-phase-snapshot-checkpoint-CPU-result-v1' and
        ce_cpu['phase_metadata_verified'] is True and ce_cpu['script']['sha256']==RETURN_PHASE_SHA and
        ce_cpu['strict_phase_base']['sha256']==RETURN_STRICT_SHA and ce_cpu['root_job']['phase_snapshot']['purpose']=='startup' and
        ce_cpu['root_job']['phase_snapshot']['owner']==ce['owner'] and ce_cpu['saved_priority_metric_phase']['metric']=='ce' and
        ce_cpu['root_job']['phase_snapshot']['observed_clients']==0 and
        ce_cpu['root_job']['source_control_context']['held_recipe_context']['batch_size']==4096 and
        ce_cpu['root_job']['phase_snapshot']['expected_phase']==ce_phase['expected'] and
        ce_cpu['saved_priority_metric_phase']['phase_record_sha256']==ce_phase['record']['sha256'],
        'Authentic new CE4096 founder/newest boot/startup0 proof required')
    deadline=values['deadline_result'];require(deadline['status']=='RETIRED' and deadline['adopted']['owner']==observer['owner'] and
        deadline['absence']['elapsed_s']<=3600 and deadline['absence']['proof']['state']=='ABSENT', 'Original treatment deadline absence required')
    require(set(binding['actual_launch_identities'])==set(binding['original_executions'])=={'trial_controller','deadline'}, 'Both original controller/deadline required')
    for name,execution in binding['original_executions'].items():
        require(triple(binding['actual_launch_identities'][name])==LAUNCH_OBSERVATIONS[name], 'Wrong original launch observation')
        launched=reader(binding['actual_launch_identities'][name]);expected=owner(execution['owner'])
        require((launched['unit'],launched['original_pid'],launched['starttime_ticks'],launched['invocation'])==
            (expected['unit'],expected['pid'],expected['starttime_ticks'],expected['invocation_id']), 'Original terminal/launch identity differs')
        terminal(execution,text_reader,journal_reader)
        text=text_reader(execution['show'])
        require(evidence['outer_job']['path'] in text and evidence['outer_job']['sha256'] in text and
            outer['sources']['controller' if name=='trial_controller' else 'deadline']['path'] in text and
            outer['sources']['controller' if name=='trial_controller' else 'deadline']['sha256'] in text,
            'Original execution did not consume selected job/source')
    cleanup=values['owned_cleanup'];require(str(cleanup['status']).startswith('PASS') and cleanup['owned_cleanup_complete'] is True,
        'Actual original-trial owned cleanup required')
    require(set(cleanup['original_executions'])==set(binding['original_executions']) and all(
        cleanup['original_executions'][name]['owner']==binding['original_executions'][name]['owner'] and
        all(cleanup['original_executions'][name][key]==binding['original_executions'][name][key]
            for key in ('show','cat','journal','archived_before_release','released'))
        for name in binding['original_executions']), 'Owned cleanup is not these two archived original executions')
    baseline=reader(binding['runtime_baseline']);anchor=binding['runtime_anchor']
    require(baseline['status']=='PASS' and baseline['main_owner']==anchor['main_owner']==ce['owner'] and
        all(baseline[k]==anchor[k] for k in ('fleet_owner','inference_worker','actors','source_hashes','control_hashes','unit_files','environment_sha256')),
        'New post-return owner/baseline closure differs')
    require(len(anchor['actors'])==192 and len(anchor['control_hashes'])==2 and len(anchor['source_hashes'])>=61,
        'Complete post-return192/source/control closure required')
    for name,digest in CANDIDATE_SOURCES.items():require(anchor['source_hashes'][str(GAME/'Scripts/dqn'/name)]==digest, 'Installed candidate5 source differs')
    predecessor=reader(binding['predecessor_quality_plan']);require(triple(binding['predecessor_quality_plan'])==dict(
        path=str(PREDECESSOR_PLAN),sha256=PREDECESSOR_PLAN_SHA,bytes=277475) and predecessor['evaluator_source_hashes']==EVALUATOR and
        predecessor['execution_source_hashes']==EXECUTION, 'Actual current predecessor12+4 source closure differs')
    campaign=binding['campaign']
    for key in ('output_directory','preview_directory','execution_directory'):
        p=Path(campaign[key]);require(p.is_absolute() and p==p.resolve(strict=False) and p.is_relative_to(GAME/'logs/managed-learning-20261015'),
            'Canonical explicit future directory required')
    require(len({campaign[k] for k in ('output_directory','preview_directory','execution_directory')})==3 and
        re.fullmatch('robotron-quality-[A-Za-z0-9_-]+',campaign['unit']) and campaign['reference_label']!=campaign['candidate_label'] and
        campaign['hypothesis'].strip(), 'Fresh unique campaign binding required')
    return dict(cpu_job=cpu,proof=proof,completion=completion,trial=trial,activation=activation,ce_return=ce,baseline=baseline,predecessor=predecessor)
