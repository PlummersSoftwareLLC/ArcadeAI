"""Distinct retained first-LATCH frozen-policy follow-up metadata bindings; no import-time work/actions.

Consumes only the genuine first candidate and newest-state4096 return. No model
body is read by this module, and no playing score or gate is changed here.
"""
import hashlib
import datetime
import importlib.util
import json
import os
from pathlib import Path
import re
import stat

GAME = Path('/home/dave/source/repos/ArcadeAI/Robotron')
SCHEMA = 'robotron-CE2048-trial02-first-LATCH-policy-followup-quality-bindings-v1'
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

FOLLOWUP_ACTUAL = {'trial_result': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/CE2048-trial02-controller-20261017/result.json', 'sha256': 'fbb6b71425bee026aaaa49646fa550fe1b9e8435a7da81c10844eefb9c35b6b0', 'bytes': 21794}, 'failed_return': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/CE2048-trial02-return4096-20261017/result.json', 'sha256': 'ef8e6cf97a85e61dbc837eccb8b9223732be629b5b47a1d2df7fb78384cb7f97', 'bytes': 6643}, 'return_job': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/CE2048-trial02-controller-20261017/return-job.json', 'sha256': '2973f3271098a7e8e5cec8aba1f92ad4c22f19a44e28de8d8a5c986ff7531a58', 'bytes': 377318}, 'phase_cpu_job': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/CE2048-trial02-return4096-20261017/ending-candidate-CPU/cpu-job.json', 'sha256': '4f2ab15421062f3550a2bbfa2af6ff4bba009317eb7ceafdf319049742921316', 'bytes': 26275}, 'phase_cpu_report': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/CE2048-trial02-return4096-20261017/ending-candidate-CPU/cpu-report-readonly.json', 'sha256': 'af1efad2cc0887dffd760c2899d1e762cebb8b5b5ae1e04a95394981ac836e6e', 'bytes': 84785}, 'phase_cpu_completion': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/CE2048-trial02-return4096-20261017/ending-candidate-CPU/cpu-completion.json', 'sha256': 'd6a174d18791cecc96a8c19ddc80b3af5c7ff15e0c2a2422da275039b6c48d18', 'bytes': 723}, 'failed_startup_CPU_report': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/CE2048-trial02-return4096-20261017/startup-phase-CPU/cpu-report-readonly.json', 'sha256': '0d58fc5d8bb3805169ab5f0ccacfc70052d3c3a93350e575c945dcb67141d775', 'bytes': 68505}, 'failed_trial_closure': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/CE2048-trial02-original-failure-archives-and-owned-closure-root-20261017/root-actual-original-failed-trial-owned-cleanup.json', 'sha256': '4c129ecea77e04bb7d834731e304b912292059d0068b7f56f4673f5c3d154ba1', 'bytes': 12666}, 'maintenance_job': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/CE2048-trial02-failed-return-forward4096-recovery-root-preparation-20261017/forward-CE4096-repair-job.json', 'sha256': '7c76945bc2861145cf525bbb5851be556734e7afc48c4a3f4895de78af2c3456', 'bytes': 7289}, 'maintenance_result': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/CE2048-trial02-failed-return-forward-CE4096-repair-20261017/result.json', 'sha256': 'b4019062ff5275e842156a643818a6d8205d702e0fce0c5a51ab18d493f5d3b0', 'bytes': 442760}, 'maintenance_closure': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/CE2048-trial02-failed-return-forward4096-recovery-root-execution-20261017/root-actual-maintenance-READY0-and-owned-cleanup.json', 'sha256': 'b0b27f8fcc214ba67e4287011c94cd6859f4c6a3a26de120ad961d4678c55fc0', 'bytes': 4108}, 'maintenance_release': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/CE2048-trial02-failed-return-forward4096-recovery-root-execution-20261017/root-explicit-maintenance-source-freeze-release.json', 'sha256': '610d949c1f6a7b051f5fc4226960ea0832acfc9c1511fc51c0a8f681d59a8e9a', 'bytes': 1332}, 'followup_precommit': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/CE2048-trial02-retained-first-candidate-frozen-quality-followup-root-precommit-20261017/precommit-FINAL.json', 'sha256': 'e467dedfddb25e7b8d8f04f92b631cee734d3679004b51526cdf1de64db56abe', 'bytes': 9870}}

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
    require(trial['status']=='FAILED' and trial['qualification_pass'] is False and trial['manual_recovery_required'] is True and
        activation['status']=='READY' and activation['mode']=='activate_batch2048' and activation['manual_recovery_required'] is False,
        'Original trial failure remains preserved; only its original first-LATCH policy is selected separately')
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


def check_maintenance_health(trial, maintenance, candidate_clocks):
    require(maintenance['status']=='READY_CE_FORWARD_REPAIR' and maintenance['original_trial_failed'] is True and
        maintenance['trial_retried'] is False and maintenance['qualification_pass'] is False and
        maintenance['manual_recovery_required'] is False and maintenance['owner']!=trial['retired_owner'] and
        maintenance['recovery_target_batch_size']==maintenance['failed_return_configured_batch_size']==4096,
        'Distinct authentic maintenance CE4096 is required; failed trial cannot be relabelled COMPLETE')
    owner(maintenance['owner']);phase=maintenance['startup']['phase']
    require(phase['expected']['metric']=='ce' and phase['expected']['valid'] is True,
        'Separate maintenance saved CE startup phase proof required')
    require(all(four(maintenance['boot_checkpoint']['clocks'])[k]>=candidate_clocks[k] for k in CLOCKS), 'Maintenance newest boot predates candidate')
    healthy=maintenance['healthy192']
    require(healthy['api']['client_count']==192 and healthy['api']['training_enabled'] is True and
        healthy['api']['exposure']['optimizer']['process_id']==maintenance['owner']['pid'] and
        healthy['binding']['environment']['DQN_BATCH_SIZE']=='4096' and not maintenance['final_resume']['failures'],
        'Actual separately restored4096 healthy192 owner differs')


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


def check_maintenance_chain(binding, values, reader):
    e=binding['evidence'];job=values['maintenance_job'];m=values['maintenance_result'];failed=values['failed_return']
    require(m['root_job']==e['maintenance_job'] and job['schema']=='robotron-CE2048-trial02-failed-return-forward-CE4096-repair-job-v1' and
        all(job[k]==e[k] for k in ('activation_job','trial_result','return_job','return_result','failed_startup_CPU_report') if k!='return_result') and
        job['return_result']==e['failed_return'], 'Separate actual maintenance job/predecessor differs')
    newest=reader(job['newest_CPU_report']);cpu=reader(job['newest_CPU_job']);spec=cpu['phase_snapshot']
    fs=values['failed_startup_CPU_report']['root_job']['phase_snapshot']
    require(newest['status']=='PASS' and newest['phase_metadata_verified'] is True and newest['root_job']==cpu and
        newest['script']['sha256']==RETURN_PHASE_SHA and newest['strict_phase_base']['sha256']==RETURN_STRICT_SHA and
        spec['purpose']=='newest_stopped' and spec['observed_clients']==0 and spec['owner']==failed['failed_requested_CE_retired'] and
        all(spec[k]==fs[k] for k in ('phase_record','boot_checkpoint','expected_phase')) and
        cpu['source_control_context']['held_recipe_context']['batch_size']==4096 and
        m['boot_checkpoint']['source']==cpu['source'] and m['boot_checkpoint']['verification']==job['newest_CPU_report'] and
        four(m['boot_checkpoint']['clocks'])==four(newest['clocks']) and
        newest['sha256']==cpu['source']['sha256']==cpu['verification_copy']['sha256'] and
        newest['bytes']==cpu['source']['bytes']==cpu['verification_copy']['bytes'] and
        all(four(newest['clocks'])[k]>=four(cpu['clock_floor'])[k]>=four(values['failed_startup_CPU_report']['clocks'])[k] for k in CLOCKS),
        'Separate maintenance must boot actual newest after failed4096 owner, preserving that CE founder/floor')
    release=reader(job['newest_CPU_release']);require(release['status']=='PASS' and release['original_exit']==0 and
        release['original_archived_before_release'] is True and release['unit_released'] is True and release['sha256']==newest['sha256'],
        'Actual maintenance newest CPU original0/archive/release differs')
    intent=reader(job['repair_intent']);phase=m['startup']['phase'];record=reader(phase['record']);start=reader(m['start_request'])
    require(intent['original_failed_trial']==e['trial_result'] and intent['original_failed_return']==e['failed_return'] and
        intent['target_batch_size']==4096 and intent['no_trial_retry'] is True and intent['newest_checkpoint']==triple(cpu['source']) and
        record['action']=='start' and record['metric']==record['previous_metric']=='ce' and
        record['root_precommit_sha256']==job['repair_intent']['sha256'] and
        record['checkpoint']==phase['boot_checkpoint']==triple(cpu['source']) and m['phase_record']==phase['record'] and
        start['trial_core']==job['repair_intent'] and start['phase_record']==phase['record'] and
        phase['boot_verification']==job['newest_CPU_report'] and phase['expected']['root_precommit_sha256']==job['repair_intent']['sha256'],
        'Actual NEW maintenance CE4096 founder/intent/start/newest tuple differs')
    startup=reader(m['startup']['phase_CPU_readonly_archive']);sj=startup['root_job'];ss=sj['phase_snapshot']
    require(startup['status']=='PASS' and startup['phase_metadata_verified'] is True and
        startup['script']['sha256']==RETURN_PHASE_SHA and startup['strict_phase_base']['sha256']==RETURN_STRICT_SHA and
        ss['purpose']=='startup' and ss['observed_clients']==0 and ss['owner']==m['owner'] and
        ss['phase_record']==phase['record'] and ss['expected_phase']==phase['expected'] and
        sj['source_control_context']['held_recipe_context']['batch_size']==4096 and
        startup['saved_priority_metric_phase']['metric']=='ce' and startup['saved_priority_metric_phase']['valid'] is True and
        startup['saved_priority_metric_phase']['phase_record_sha256']==phase['record']['sha256'] and
        all(four(startup['clocks'])[k]>=four(newest['clocks'])[k] for k in CLOCKS),
        'Separate maintenance startup0 phase CPU proof differs')
    published=m['CSV_publication'];stamp=datetime.datetime.fromisoformat(published['CSV']['utc'].replace('Z','+00:00'))
    require(published['status']=='PASS_CURRENT_OWNER_CE4096_CSV_PUBLICATION' and published['owner']==m['owner'] and
        published['start_request']==m['start_request'] and published['CSV']['batch_size']==4096 and published['CSV']['replay_sample_cap']==8 and
        stamp.tzinfo is not None and stamp.timestamp()>=start['unix_s'], 'Actual new maintenance4096 producer CSV publication required')
    closure=values['maintenance_closure'];archive=reader(closure['original_terminal_archive'])
    require(str(closure['status']).startswith('PASS') and closure['owned_cleanup_complete'] is True and closure['unit_released'] is True and
        closure['original_exec_code']==archive['original_exec_code']==1 and closure['original_exit']==archive['original_exit']==0 and
        closure['original_result']==archive['original_result']=='success' and closure['original_archived_before_release'] is True and
        archive['archived_before_release'] is True and closure['actual_result']==archive['result']==e['maintenance_result'] and
        closure['actual_current_owner']==m['owner'] and closure['original_trial_status']=='FAILED_preserved' and
        closure['original_trial_retried'] is False and closure['quality_qualified'] is False and
        (closure['original_pid'],closure['original_starttime_ticks'],closure['original_invocation'])==
            (archive['original']['pid'],archive['original']['starttime_ticks'],archive['original']['invocation_id']) and
        [x['unit'] for x in closure['owned_release']]==[archive['original']['timer'],archive['original']['unit']] and
        all(x['stop_returncode']==0 and x['final_load_state']=='not-found' for x in closure['owned_release']),
        'Separate original0 maintenance/archive/owned timer-first closure differs')
    released=values['maintenance_release'];require(released['source_freeze_released'] is True and
        released['actual_maintenance_closure']==e['maintenance_closure'] and released['actual_current_owner']==m['owner'] and
        released['original_trial_status']=='FAILED_preserved' and released['playing_quality_qualified'] is False and
        released['protected_reference_changed'] is False, 'Actual separate maintenance source release differs')


def check_followup_precommit(binding, values):
    p=values['followup_precommit'];e=binding['evidence']
    require(p['schema']=='robotron-retained-first-LATCH-frozen-policy-followup-precommit-v1' and
        p['status']=='ROOT_SELECTED_NEW_FIRST_FROZEN_POLICY_COMPARISON_BEFORE_ANY_FRESH_QUALITY_SCORES' and
        p['original_trial_status']==p['original_return_status']=='FAILED' and p['original_failure_records_immutable'] is True and
        p['retroactive_original_trial_success'] is False and p['original_trial_retried'] is False and
        p['candidate']==binding['candidate'] and p['reference']==binding['reference'] and
        p['candidate_saved_four_clocks']==four(values['phase_cpu_report']['clocks']) and
        p['candidate_new_quality_attempts_started']==0 and p['fresh_reference_results'] is None and p['fresh_candidate_results'] is None and
        p['actual_current_maintenance_owner']==values['maintenance_result']['owner'],
        'Distinct prescore first frozen-policy follow-up precommit required; no retroactive trial qualification')
    mapping={'original_trial':'trial_result','original_failed_return':'failed_return','original_first_LATCH':'decision',
        'original_first_durability':'durability','original_candidate_CPU':'phase_cpu_report','separate_maintenance_READY':'maintenance_result',
        'separate_maintenance_owned_closure':'maintenance_closure','separate_maintenance_source_freeze_release':'maintenance_release'}
    require(all(p['evidence'][left]==e[right] for left,right in mapping.items()), 'Actual follow-up precommit evidence differs')
    expected=dict(order=['reference1','candidate1','reference2','candidate2'],admission_seconds_per_leg=1200,game_timeout_seconds=2400,
        slots=list(range(4096,4112)),minimum_complete_games_each_leg=50,all_slots_required=True,all_admitted_games_full_tails_required=True,
        abandoned_or_pending_games_allowed=0,runtime_errors_allowed=0,compiled_FP32=True,epsilon=0,expert_ratio=0,replay_enabled=False,
        diagnostics_enabled=True,attempts_per_leg=1,admission_extensions_allowed=False,
        reference_pool='Both FRESH reference legs pooled once; same fixed pool for both candidate gates',
        each_candidate_required_mean_multiplier=1.05,each_candidate_required_median_multiplier=1.0,
        pooled_candidate_rescue_allowed=False,automatic_promotion=False)
    require(p['confirmation']==expected, 'Fresh R/C/R/C gates or one-attempt protocol changed')


def validate(binding, *, reader=read, text_reader=lambda pin:read_bytes(pin).decode(),
             journal_reader=lambda pin:read_bytes(pin,allow_empty=True), horizon=None):
    require(set(binding)=={'schema','experiment','reference','candidate','evidence','runtime_baseline','runtime_anchor',
        'original_executions','actual_launch_identities','predecessor_quality_plan','campaign'} and
        binding['schema']==SCHEMA and binding['experiment']=='best10M-fresh3-eps10-cap8-nosmooth', 'Explicit distinct first-LATCH policy follow-up binding required')
    check_reference(binding['reference'],reader);evidence=binding['evidence']
    require(set(evidence)=={'phase_cpu_job','phase_cpu_report','phase_cpu_completion','trial_result','activation','observer','decision',
        'durability','failed_return','early_phase_insurance','deadline_result','failed_trial_closure','outer_job','activation_job','trial_core','return_job',
        'failed_startup_CPU_report','maintenance_job','maintenance_result','maintenance_closure','maintenance_release','followup_precommit'},
        'Exact original failed-trial plus separate maintenance and new precommit evidence PIN set required')
    values={key:reader(value) for key,value in evidence.items()}
    for key,expected in ACTUAL.items():require(triple(evidence[key])==expected, 'Wrong authentic selected trial02 '+key)
    for key,expected in FOLLOWUP_ACTUAL.items():require(triple(evidence[key])==expected, 'Wrong actual follow-up lineage '+key)
    cpu,proof,completion=(values[k] for k in ('phase_cpu_job','phase_cpu_report','phase_cpu_completion'))
    check_cpu(cpu,proof,completion,binding['candidate']);require(proof['job_file']['sha256']==evidence['phase_cpu_job']['sha256'], 'CPU root job differs')
    trial,activation,observer,decision,durability,failed=(values[k] for k in ('trial_result','activation','observer','decision','durability','failed_return'))
    outer,activation_job,core=(values[k] for k in ('outer_job','activation_job','trial_core'))
    require(trial['root_job']==evidence['outer_job'] and outer['activation_job']==evidence['activation_job'] and
        outer['trial_core']==activation_job['trial_core']==evidence['trial_core'] and core['status']=='FINAL_PRECOMMITTED_ROOT_AUTHORIZED' and
        core['activation_authorized'] is True and core['mode']==activation_job['mode']=='activate_batch2048' and
        core['phase_id']==activation_job['phase_id']==cpu['phase_snapshot']['expected_phase']['phase_id'] and
        cpu['phase_snapshot']['expected_phase']['root_precommit_sha256']==evidence['trial_core']['sha256'], 'Actual original trial02 jobs/core differ')
    profile=outer['profile'];require(profile==core['batch_profile']==activation_job['batch_profile'], 'Original profile differs')
    early=values['early_phase_insurance'];early_proof=check_early(early,profile,activation['owner'],activation['startup_phase_proof']['phase']['record'],reader)
    require(outer['candidate_tag']==TAG and outer['early_insurance']['tag']==early['tag'] and
        trial['early_insurance_at_terminal']['result_pin']==evidence['early_phase_insurance'], 'Original first candidate/typed early result differs')
    require(completion['argv'][0]==activation_job['verifier']['python'] and trial['activation']==evidence['activation'] and
        trial['observer']==evidence['observer'] and trial['decision']['event']==evidence['decision']==durability['event'] and
        trial['decision']['durability']==evidence['durability'] and trial['CE_return']==evidence['failed_return'], 'Actual failed-trial evidence joins differ')
    start=reader(activation['start_request'])
    require(observer['trial_core_sha256']==evidence['trial_core']['sha256'] and observer['activation_receipt_sha256']==evidence['activation']['sha256'],
        'Original activation/core SHA differs')
    check_activation_origin(activation,observer,start,reader(activation['before_resume_api_PIN']))
    return_job=values['return_job'];candidate=return_job['ending_proof']['candidate']
    require(candidate['source']==cpu['source'] and candidate['verification_copy']==cpu['verification_copy'], 'Not original first frozen candidate')
    acquisition=reader(candidate['acquisition']);require(reader(cpu['phase_snapshot']['acquisition'])==acquisition, 'FINAL original candidate acquisition differs')
    check_selection(trial,activation,observer,decision,durability,acquisition,cpu,early_proof,horizon or load_horizon())
    require(failed['status']=='FAILED' and failed['mode']=='return_batch4096' and failed['manual_recovery_required'] is True and
        failed['qualification_pass'] is False and failed['error']=="RuntimeError(\"Postload guards: ['CSV_recipe']\")" and
        not failed['final_resume']['failures'] and
        failed['ending']['candidate_CPU']==evidence['phase_cpu_report'] and failed['ending']['candidate_saved_clocks']==four(proof['clocks']),
        'Actual post-LATCH failed CE4096 return remains a failure; candidate CPU tuple differs')
    require(return_job['mode']=='return_batch4096' and return_job['running_phase']==activation['startup_phase_proof']['phase'] and
        return_job['ending_proof']['observer_job']==evidence['observer'] and return_job['ending_proof']['activation_receipt']==evidence['activation'] and
        return_job['ending_proof']['decision']==evidence['decision'] and return_job['phase_early_insurance_result']==evidence['early_phase_insurance'] and
        return_job['producer_capture']==early['producer_capture'], 'Original typed return job/first-LATCH ending differs')
    failed_startup=values['failed_startup_CPU_report'];fjob=failed_startup['root_job'];fspec=fjob['phase_snapshot']
    require(failed_startup['status']=='PASS' and failed_startup['phase_metadata_verified'] is True and
        failed_startup['script']['sha256']==RETURN_PHASE_SHA and failed_startup['strict_phase_base']['sha256']==RETURN_STRICT_SHA and
        fspec['purpose']=='startup' and fspec['observed_clients']==0 and fspec['owner']==failed['failed_requested_CE_retired'] and
        fjob['source_control_context']['held_recipe_context']['batch_size']==4096 and
        failed_startup['saved_priority_metric_phase']['metric']=='ce' and failed_startup['saved_priority_metric_phase']['valid'] is True,
        'Authentic failed-return startup0 CE4096 proof required')
    newest2048=reader(fspec['boot_verification']);nj=newest2048['root_job'];require(
        newest2048['status']=='PASS' and newest2048['schema']==CPU_RESULT_SCHEMA and newest2048['phase_metadata_verified'] is True and
        nj['schema']==CPU_JOB_SCHEMA and nj['phase_snapshot']['purpose']=='newest_stopped' and nj['phase_snapshot']['owner']==activation['owner'] and
        nj['batch2048_context']['role']=='newest_stopped' and newest2048['script']['sha256']==PHASE_SHA and newest2048['strict_phase_base']['sha256']==STRICT_SHA and
        newest2048['configured_batch_size']==newest2048['actual_producer_batch_size']==2048 and newest2048['producer_CSV_verified'] is True and
        triple(nj['source'])==fspec['boot_checkpoint'] and newest2048['sha256']==nj['source']['sha256']==nj['verification_copy']['sha256'] and
        newest2048['bytes']==nj['source']['bytes']==nj['verification_copy']['bytes'] and
        nj['phase_snapshot']['phase_record']==activation['startup_phase_proof']['phase']['record'] and
        nj['phase_snapshot']['expected_phase']==activation['startup_phase_proof']['phase']['expected'] and
        all(four(newest2048['clocks'])[k]>=failed['ending']['required_newest_stopped_floor'][k]>=four(proof['clocks'])[k] for k in CLOCKS),
        'Original genuine newest2048 stopped proof/floor before failed4096 startup differs')
    deadline=values['deadline_result'];require(deadline['status']=='RETIRED' and deadline['adopted']['owner']==observer['owner'] and
        deadline['absence']['elapsed_s']<=3600 and deadline['absence']['proof']['state']=='ABSENT', 'Original treatment deadline absence required')
    require(set(binding['actual_launch_identities'])==set(binding['original_executions'])=={'trial_controller','deadline'}, 'Both original failed controller/deadline required')
    for name,execution in binding['original_executions'].items():
        require(triple(binding['actual_launch_identities'][name])==LAUNCH_OBSERVATIONS[name], 'Wrong original launch observation')
        launched=reader(binding['actual_launch_identities'][name]);expected=owner(execution['owner'])
        require((launched['unit'],launched['original_pid'],launched['starttime_ticks'],launched['invocation'])==
            (expected['unit'],expected['pid'],expected['starttime_ticks'],expected['invocation_id']), 'Original terminal/launch identity differs')
        terminal(execution,text_reader,journal_reader,exit_status=1 if name=='trial_controller' else 0,result='exit-code' if name=='trial_controller' else 'success')
        text=text_reader(execution['show'])
        require(evidence['outer_job']['path'] in text and evidence['outer_job']['sha256'] in text and
            outer['sources']['controller' if name=='trial_controller' else 'deadline']['path'] in text and
            outer['sources']['controller' if name=='trial_controller' else 'deadline']['sha256'] in text, 'Original selected job/source changed')
    cleanup=values['failed_trial_closure'];require(str(cleanup['status']).startswith('PASS') and cleanup['owned_cleanup_complete'] is True and
        cleanup['original_trial_status']=='FAILED' and cleanup['original_controller_exit']==1 and cleanup['original_deadline_exit']==0 and
        cleanup['actual_trial_retried'] is False and cleanup['model_quality_qualification'] is False,
        'Original failed-trial cleanup must preserve original exits and failure')
    require(set(cleanup['original_executions'])==set(binding['original_executions']) and all(
        all(cleanup['original_executions'][name][key]==binding['original_executions'][name][key] for key in
            ('owner','show','cat','journal','archived_before_release','released')) for name in binding['original_executions']),
        'Cleanup is not the archived original failed jobs')
    maintenance=values['maintenance_result'];check_maintenance_health(trial,maintenance,four(proof['clocks']))
    check_maintenance_chain(binding,values,reader)
    check_followup_precommit(binding,values)
    baseline=reader(binding['runtime_baseline']);anchor=binding['runtime_anchor']
    require(baseline['status']=='PASS' and baseline['main_owner']==anchor['main_owner']==maintenance['owner'] and
        all(baseline[k]==anchor[k] for k in ('fleet_owner','inference_worker','actors','source_hashes','control_hashes','unit_files','environment_sha256')),
        'Actual separate maintenance owner/fresh baseline closure differs')
    require(len(anchor['actors'])==192 and len(anchor['control_hashes'])==2 and len(anchor['source_hashes'])>=61, 'Complete fresh192/source/control closure required')
    for name,digest in CANDIDATE_SOURCES.items():require(anchor['source_hashes'][str(GAME/'Scripts/dqn'/name)]==digest, 'Installed candidate5 source differs')
    predecessor=reader(binding['predecessor_quality_plan']);require(triple(binding['predecessor_quality_plan'])==dict(
        path=str(PREDECESSOR_PLAN),sha256=PREDECESSOR_PLAN_SHA,bytes=277475) and predecessor['evaluator_source_hashes']==EVALUATOR and
        predecessor['execution_source_hashes']==EXECUTION, 'Actual predecessor12+4 source closure differs')
    campaign=binding['campaign']
    for key in ('output_directory','preview_directory','execution_directory'):
        p=Path(campaign[key]);require(p.is_absolute() and p==p.resolve(strict=False) and p.is_relative_to(GAME/'logs/managed-learning-20261015'), 'Canonical fresh directory required')
    require(len({campaign[k] for k in ('output_directory','preview_directory','execution_directory')})==3 and
        re.fullmatch('robotron-quality-[A-Za-z0-9_-]+',campaign['unit']) and campaign['reference_label']!=campaign['candidate_label'] and
        campaign['hypothesis'].strip(), 'Fresh unique campaign binding required')
    return dict(cpu_job=cpu,proof=proof,completion=completion,trial=trial,activation=activation,failed_return=failed,
        maintenance=maintenance,baseline=baseline,predecessor=predecessor)
