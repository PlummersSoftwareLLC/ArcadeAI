"""Factual trial02/phase-CPU/post-return bindings; stdlib, no import-time work.

This module neither evaluates models nor changes quality admission/scoring.
Only explicit carrier/auditor execution reads its immutable root binding job.
"""
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import stat

GAME = Path('/home/dave/source/repos/ArcadeAI/Robotron')
SCHEMA = "robotron-rawKL-trial02-quality-bindings-v1"
REFERENCE = GAME / "models_dqn/managed-incumbents/fresh3-448M-confirmed.pt"
REFERENCE_SHA = "1e085a128e237c2bb0636b073e5053dd8bf5be932bcbd8249543b3af20e23021"
CANDIDATE = GAME / "models_dqn/managed-checkpoints/rawkl-first-8M-20261017-trial02.pt"
TAG = "rawkl-first-8M-20261017-trial02"
PHASE = GAME / "tools/phase_snapshot_cpu_verifier_proposal/verify_phase_snapshot.py"
PHASE_SHA = "b2e732dc731b2b601f7499d2cafd5841896daf2b0713d496b98cb6b8d7279519"
STRICT_SHA = "9ef38e17e1b9eee3f6c43e40005812f2ebe3cff16d08bf61d3e820c2d41134c8"
BASE_SHA = "7d1103daf2a77be8250884cb75ce04a640000f04b4376e994d493bc6fd0f7ead"
HORIZON = GAME / "tools/kl_priority_mixture_proposal/raw_kl_sequential_trial_proposal/sequential_trial_precommit_proposal/horizon_observer_proposal/horizon_observer.py"
HORIZON_SHA = "25d70b4a3888dcba83ea9020c333cba32cfbd19c93b6e69037d6299b161fd7ec"
PREDECESSOR_PLAN = Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/quality-384M-vs-448M-20261017/plan.json')
PREDECESSOR_PLAN_SHA = '5bb1778efdd6b29c6ac9f5defa0373da1c2c8bc13e6324e0c2c17d4cfc4164b4'
EVALUATOR = {'tools/run_frozen_sidecar.py': 'cd034413c2fd8a56bb9d22f8df86889939edfad041ee4e2e0210a831b5f9fe90', 'tools/sidecar_boot.py': 'f06492e6d96cd472d9f0073b4c643e820bcacb6a96c5f542a59d6b6874e62362', 'Scripts/main.lua': '060f838359d35ef6c87b96dfe02ad34618ef974d5a43fefcb74320ebe9deecaf', 'Scripts/robotron_socket_wait.c': 'fc9ed2719839f72e36346d0886e5b32116a167d49414b506dc8b5f4252464cfc', 'Scripts/dqn/config.py': '19abcbde4d08cf8465b82185ac6dd52eb8965adb8611584e0677c4c7ff21d1fd', 'Scripts/dqn/model.py': 'bcd174f05610c6f773ca8c53f9155206eba4f7b6a11383516ddd71f3b513eeb4', 'Scripts/dqn/actor_tags.py': 'fc5b868a7fb68d4ab7ba65ba872ea0e845759af6143edfe648239d57cb7f1591', 'Scripts/dqn/socket_server.py': 'd99dd2782fc3e8f67670aefb398ed0dfdc1fd859432e24c8bd8dea4da2825214', 'Scripts/dqn/game_journal.py': '10827d786becfd19c386bddfbce85f1ab5ace5349d87717305e4044a2843edb0', 'Scripts/dqn/managed_measurement.py': '9649d0ba199bdc0943202164da7a9058e5d578b9c411ce26a950b2595c7e96e6', 'Scripts/dqn/inference_actor.py': '7cc812adeab8dc7cb989f9024592767928afa786966b85f3488023fb8d6b34ce', 'Scripts/dqn/nstep_buffer.py': 'e46f03e9a626b3a24dea702344b0bbf050f1fdc5af672fc8fc9d18e6afef74c1'}
EXECUTION = {'/home/dave/source/repos/ArcadeAI/Robotron/tools/run_quality_campaign.py': '574e56f28499c751c639ee8a3474eecd5ca8de8c896da3dd44d5e4fc2fe60128', '/home/dave/source/repos/ArcadeAI/Robotron/tools/run_frozen_sidecar.py': 'cd034413c2fd8a56bb9d22f8df86889939edfad041ee4e2e0210a831b5f9fe90', '/home/dave/source/repos/ArcadeAI/Robotron/tools/compare_sidecar_measurements.py': '879590b64e760037a81da2ff574d5994d9259cf1746b8e406177e2220d37c746', '/home/dave/source/repos/ArcadeAI/Robotron/tools/compare_frozen_measurements.py': '53f744737a722fec2760c0001dc5747b19b05e07a1de8699764c781f04da6be0'}
CANDIDATE_SOURCES = {'agent.py': '865a0df717b39951b7f7c516e4a962e3d48cf4d3dc11295ff266e58653e6c74b', 'training.py': '90b847856f810cb4f52513a4bd0625b2d15d4801107bff398060faae25bc4be4', 'loss_kernel.py': '23eb8fc0d8409c9f31ef26ec4596da9c2257e3985abbbfa7d5fbdcb337e21f67', 'config.py': '19abcbde4d08cf8465b82185ac6dd52eb8965adb8611584e0677c4c7ff21d1fd', 'priority_phase.py': 'ee3c0d02bc1eab55e92ffd605c3736fe5a0ef905a8a8ee242c687301ea2b7c5b'}

ACTUAL_LAUNCH_IDENTITIES = GAME / "logs/managed-learning-20261015/run-26/goal-continuation-KL-trial02-running-root-20261017/actual-live-parent-and-trainer-identities.json"
ACTUAL_LAUNCH_IDENTITIES_SHA = "d11a63597d9be19e210f70ec35f82c85d9e7552e3e1abf6821c7efec13e2680d"
CLOCKS = ('training_steps', 'optimized_samples', 'learner_frame_count', 'frame_count')
OWNER_KEYS = {'pid', 'starttime_ticks', 'unit', 'invocation_id', 'cgroup'}
LIMIT = 4 << 20


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
    require(path.is_absolute() and path == path.resolve(strict=True), 'Canonical metadata path required')
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


def load_horizon():
    require(hashlib.sha256(HORIZON.read_bytes()).hexdigest() == HORIZON_SHA, 'Frozen horizon changed')
    spec = importlib.util.spec_from_file_location('_quality_original_horizon', HORIZON)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def four(value):
    result = {key: value[key] for key in CLOCKS}
    require(all(type(v) is int and v > 0 for v in result.values()), 'Four positive actual clocks required')
    return result


def flat(pin):
    return dict(path=pin['path'], sha256=pin['sha256'], **pin['identity'])


def check_cpu(job, proof, completion, candidate):
    require(job['schema'] == 'robotron-phase-snapshot-checkpoint-CPU-job-v1'
        and job['verifier_sha256'] == PHASE_SHA and job['strict_phase_base_sha256'] == STRICT_SHA
        and job['original_strict_base_sha256'] == BASE_SHA, 'Actual candidate phase CPU job required')
    spec = job['phase_snapshot']
    require(spec['purpose'] == 'candidate' and spec['expected_phase']['metric'] == 'kl'
        and spec['expected_phase']['valid'] is True, 'Only historical KL candidate phase CPU accepted')
    source, copied = job['source'], job['verification_copy']
    require(source['path'] == str(CANDIDATE) and candidate['path'] == str(CANDIDATE)
        and candidate['tag'] == TAG and candidate['sha256'] == source['sha256'] == copied['sha256']
        and candidate['bytes'] == source['bytes'] == copied['bytes']
        and type(candidate['bytes']) is int and 200 << 20 <= candidate['bytes'] <= 400 << 20,
        'First trial02 candidate source/hash/bytes differ')
    require(source['path'] != copied['path']
        and (source['identity']['device'], source['identity']['inode']) !=
            (copied['identity']['device'], copied['identity']['inode'])
        and all(p['identity']['mode'] == '0o444' and p['identity']['nlink'] == 1
            and p['identity']['uid'] == os.getuid() for p in (source, copied)), 'Independent readonly candidate copy required')
    require(proof['schema'] == 'robotron-phase-snapshot-checkpoint-CPU-result-v1'
        and proof['status'] == 'PASS' and proof['phase_metadata_verified'] is True
        and proof['script']['sha256'] == PHASE_SHA and proof['strict_phase_base']['sha256'] == STRICT_SHA
        and proof['original_strict_base']['sha256'] == BASE_SHA and proof['root_job'] == job
        and proof['sha256'] == candidate['sha256'] and proof['bytes'] == candidate['bytes']
        and proof['path'] == copied['path'] and proof['source_before'] == flat(source)
        and proof['verification_copy'] == flat(copied)
        and proof['actual_restore_or_optimizer_step'] is False and proof['actual_quality_qualification'] is False,
        'Matching strict phase CPU result required')
    argv = completion['argv']
    require(completion['exit_code'] == 0 and str(PHASE) in argv
        and PHASE_SHA in argv and '--execute' in argv and '--expected-job-sha256' in argv,
        'First inline candidate phase CPU original exit0/argv required')
    require(argv[argv.index('--job') + 1] == proof['job_file']['path']
        and argv[argv.index('--expected-job-sha256') + 1] == proof['job_file']['sha256']
        and argv[argv.index('--expected-verifier-sha256') + 1] == PHASE_SHA,
        'Inline CPU completion must bind exact job/source digest')
    require(argv == [argv[0],'-Xgil=0','-I','-B',str(PHASE),'--execute','--job',proof['job_file']['path'],
        '--expected-job-sha256',proof['job_file']['sha256'],'--expected-verifier-sha256',PHASE_SHA],
        'Inline phase CPU argv flags/order/duplicates differ')
    require(all(proof['clocks'][key] >= job['clock_floor'][key] for key in CLOCKS), 'Candidate saved clocks below acquisition floor')


def check_selection(trial, activation, observer, decision, durability, acquisition, cpu, early, horizon):
    require(trial['status'] == 'COMPLETE' and trial['qualification_pass'] is False
        and trial['manual_recovery_required'] is False and activation['status'] == 'READY'
        and activation['manual_recovery_required'] is False, 'Completed first trial and READY activation required')
    horizon.validate_job(observer)
    require(activation['owner'] == observer['owner'] == cpu['phase_snapshot']['owner']
        and observer['boot_four_clocks'] == activation['boot_four_clocks'], 'Candidate original KL owner/boot differs')
    require(decision['schema'] == 'robotron-raw-kl-horizon-observation-v1' and decision['state'] == 'LATCH'
        and decision['candidate_requests_allowed'] == 1 and decision['qualification_pass'] is False,
        'First immutable BOTH-horizon LATCH required; a generic snapshot is insufficient')
    start = observer['start_request']
    require(decision['boot_id'] == durability['boot_id'] == start['boot_id']
        and decision['elapsed_s'] == decision['observed_monotonic_s'] - start['monotonic_s']
        and 0 <= decision['elapsed_s'] <= 3240
        and durability['completed_monotonic_s'] >= decision['observed_monotonic_s']
        and durability['elapsed_s'] == durability['completed_monotonic_s'] - start['monotonic_s'] <= 3240,
        'Actual first decision/durable receipt missed fixed cutoff or reanchored')
    current = horizon.normalise(decision['first_eligible_observation'])
    baseline = horizon.normalise(observer['before_resume_api'])
    require(current['optimizer_identity'] == baseline['optimizer_identity']
        and current['replay_identity'] == baseline['replay_identity'], 'First candidate owner/epoch changed')
    progress = decision['progress']
    require(progress['learner_frames'] == current['clocks']['learner_frame_count'] - observer['boot_four_clocks']['learner_frame_count'] >= 8000000
        and progress['physical_accepted'] == current['accepted'] - baseline['accepted'] >= 6000000
        and progress['optimizer_total'] == current['optimizer'], 'Both actual learner/all-five physical horizons required')
    require(early['schema'] == 'robotron-live8-maintenance-checkpoint-CPU-result-v1'
        and early['status'] == 'PASS' and early['mode'] == 'insurance'
        and early['script']['sha256'] == BASE_SHA and early['root_job']['mode'] == 'insurance'
        and early['root_job']['verifier_sha256'] == BASE_SHA
        and early['root_job']['insurance']['trainer'] == observer['owner']
        and early['insurance_trigger']['client_count'] == 192
        and early['root_job']['insurance']['tag'] != TAG, 'Distinct actual7d early KL-owner192 insurance required')
    floor = {k: max(four(early['clocks'])[k], current['clocks'][k]) for k in CLOCKS}
    phase = activation['startup_phase_proof']['phase']
    spec = cpu['phase_snapshot']
    require(spec['phase_record'] == phase['record'] and spec['boot_checkpoint'] == phase['boot_checkpoint']
        and spec['expected_phase'] == phase['expected'] and acquisition['tag'] == TAG
        and acquisition['purpose'] == 'candidate' and acquisition['owner_before'] == acquisition['owner_after'] == observer['owner']
        and acquisition['clock_floor'] == cpu['clock_floor'] == floor
        and acquisition['source_checkpoint'] == {k:cpu['source'][k] for k in ('path', 'sha256', 'bytes')},
        'Candidate acquisition/founder/actual first-LATCH floor differs')


def check_return(trial, ce, candidate_clocks):
    require(ce['status'] == 'READY' and ce['mode'] == 'return_ce' and ce['qualification_pass'] is False
        and ce['manual_recovery_required'] is False and ce['owner'] != trial['retired_owner'],
        'Explicit new-owner READY CE return required before quality')
    require(ce['startup_phase_proof']['phase']['expected']['metric'] == 'ce'
        and ce['startup_phase_proof']['phase']['expected']['valid'] is True,
        'Saved CE startup phase proof required')
    require(all(ce['boot_checkpoint']['clocks'][k] >= candidate_clocks[k] for k in CLOCKS), 'CE boot latest predates frozen candidate')
    require(ce['healthy']['api']['client_count'] == 192 and ce['healthy']['api']['training_enabled'] is True
        and ce['healthy']['api']['exposure']['optimizer']['process_id'] == ce['owner']['pid'], 'Returned CE healthy192 owner differs')
    require(not ce['final_resume']['failures'], 'Returned CE actor undo incomplete')


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


def validate(binding, *, reader=read, text_reader=lambda pin: read_bytes(pin).decode(),
             journal_reader=lambda pin: read_bytes(pin, allow_empty=True), horizon=None):
    require(binding['schema'] == SCHEMA and binding['experiment'] == 'best10M-fresh3-eps10-cap8-nosmooth', 'Wrong concrete trial02 binding schema')
    require(set(binding) == {'schema','experiment','candidate','evidence','runtime_baseline','runtime_anchor',
        'original_executions','actual_launch_identities','predecessor_quality_plan','campaign'}, 'Explicit binding fields differ')
    evidence = binding['evidence']
    require(set(evidence) == {'phase_cpu_job','phase_cpu_report','phase_cpu_completion','trial_result','activation',
        'observer','decision','durability','ce_return','early_insurance','deadline_result','owned_cleanup',
        'outer_job','activation_job','trial_core'}, 'Exact actual evidence PIN set required')
    values = {key:reader(value) for key,value in evidence.items()}
    cpu, proof, completion = (values[k] for k in ('phase_cpu_job', 'phase_cpu_report', 'phase_cpu_completion'))
    check_cpu(cpu, proof, completion, binding['candidate'])
    require(proof['job_file']['sha256'] == evidence['phase_cpu_job']['sha256'], 'CPU report/root-job SHA differs')
    trial, activation, observer, decision, durability, ce = (values[k] for k in ('trial_result','activation','observer','decision','durability','ce_return'))
    outer, activation_job, core = (values[k] for k in ('outer_job','activation_job','trial_core'))
    require(trial['root_job'] == evidence['outer_job'] and outer['activation_job'] == evidence['activation_job']
        and outer['trial_core'] == activation_job['trial_core'] == evidence['trial_core']
        and core['status'] == 'FINAL_PRECOMMITTED_ROOT_AUTHORIZED' and core['activation_authorized'] is True
        and core['mode'] == activation_job['mode'] == 'activate_kl'
        and core['phase_id'] == activation_job['phase_id'] == cpu['phase_snapshot']['expected_phase']['phase_id']
        and cpu['phase_snapshot']['expected_phase']['root_precommit_sha256'] == evidence['trial_core']['sha256'],
        'Actual selected trial02 outer job/activation/core differs')
    require(outer['candidate_tag'] == TAG and outer['early_insurance']['tag'] == values['early_insurance']['root_job']['insurance']['tag'],
        'Candidate or early insurance not selected by the original outer job')
    require(completion['argv'] == [activation_job['verifier']['python'],'-Xgil=0','-I','-B',str(PHASE),
        '--execute','--job',evidence['phase_cpu_job']['path'],'--expected-job-sha256',evidence['phase_cpu_job']['sha256'],
        '--expected-verifier-sha256',PHASE_SHA], 'Original inline candidate CPU full argv differs')
    require(trial['activation'] == evidence['activation'] and trial['observer'] == evidence['observer']
        and trial['decision']['event'] == evidence['decision'] == durability['event']
        and trial['decision']['durability'] == evidence['durability'] and trial['CE_return'] == evidence['ce_return'],
        'Actual first-trial selected evidence PINs differ')
    start = reader(activation['start_request'])
    require(observer['trial_core_sha256'] == activation['trial_core']['sha256'] == evidence['trial_core']['sha256']
        and observer['activation_receipt_sha256'] == evidence['activation']['sha256']
        and observer['start_request'] == {key:start[key] for key in ('boot_id','monotonic_s','unix_s')}
        and start['trial_core'] == activation['trial_core']
        and start['phase_record'] == activation['startup_phase_proof']['phase']['record'],
        'Original activation receipt/core/start clock was changed or reanchored')
    require(trial['candidate']['source'] == cpu['source'] and trial['candidate']['verification_copy'] == cpu['verification_copy'], 'CPU candidate is not the FIRST selected trial02 candidate')
    acquisition = reader(trial['candidate']['acquisition'])
    require(reader(cpu['phase_snapshot']['acquisition']) == acquisition, 'Phase CPU acquired another snapshot')
    historical_early = trial['early_insurance']
    require(all(evidence['early_insurance'][key] == historical_early[key] for key in ('sha256','bytes')),
        'Readonly early insurance archive does not match original historical proof')
    if historical_early['identity']['mode'] != '0o444':
        require(evidence['early_insurance']['path'] != historical_early['path']
            and (evidence['early_insurance']['identity']['device'],evidence['early_insurance']['identity']['inode']) !=
                (historical_early['identity']['device'],historical_early['identity']['inode']),
            'Writable original early report needs an independent readonly archive')
    check_selection(trial,activation,observer,decision,durability,acquisition,cpu,values['early_insurance'],horizon or load_horizon())
    require(ce['ending']['candidate_CPU'] == evidence['phase_cpu_report'], 'CE return did not consume selected candidate CPU proof')
    check_return(trial,ce,four(proof['clocks']))
    ce_start = reader(ce['start_request']); ce_phase = ce['startup_phase_proof']['phase']
    ce_record = reader(ce_phase['record']); ce_cpu = reader(ce['startup_phase_proof']['phase_CPU'])
    require(ce_start['phase_record'] == ce_phase['record'] and ce_record['metric'] == 'ce'
        and ce_record['action'] == 'start' and ce_record['previous_metric'] == 'kl'
        and ce_record['root_precommit_sha256'] == ce_start['trial_core']['sha256']
        and ce_phase['boot_checkpoint'] == {key:ce['boot_checkpoint']['source'][key] for key in ('path','sha256','bytes')}
        and ce_cpu['status'] == 'PASS' and ce_cpu['phase_metadata_verified'] is True
        and ce_cpu['script']['sha256'] == PHASE_SHA
        and ce_cpu['root_job']['phase_snapshot']['purpose'] == 'startup'
        and ce_cpu['root_job']['phase_snapshot']['owner'] == ce['owner']
        and ce_cpu['saved_priority_metric_phase']['metric'] == 'ce'
        and ce_cpu['saved_priority_metric_phase']['phase_record_sha256'] == ce_phase['record']['sha256'],
        'Authentic new CE record/boot/client0 phase CPU lineage required')
    deadline = values['deadline_result']
    require(deadline['status'] == 'RETIRED' and deadline['adopted']['owner'] == observer['owner']
        and deadline['absence']['elapsed_s'] <= 3600 and deadline['absence']['proof']['state'] == 'ABSENT', 'Original KL deadline retirement proof absent')
    launched = reader(binding['actual_launch_identities'])
    require(binding['actual_launch_identities']['path'] == str(ACTUAL_LAUNCH_IDENTITIES)
        and binding['actual_launch_identities']['sha256'] == ACTUAL_LAUNCH_IDENTITIES_SHA,
        'Exact original trial02 launch identities required')
    require(activation['owner'] == observer['owner'] == dict(launched['trainer']['expected'],
        cgroup=launched['trainer']['fields']['ControlGroup']), 'Not the actual selected trial02 KL owner')
    command = launched['controller']['fields']['ExecStart']
    require(evidence['outer_job']['path'] in command and evidence['outer_job']['sha256'] in command
        and outer['sources']['controller']['path'] in command and outer['sources']['controller']['sha256'] in command,
        'Original actual controller did not execute the selected outer job/source')
    for name,execution in binding['original_executions'].items():
        key = 'controller' if name == 'trial_controller' else name
        require(execution['owner'] == dict(launched[key]['expected'],cgroup=launched[key]['fields']['ControlGroup']),
            'Terminal is not the actual selected trial02 controller/deadline')
        terminal(execution,text_reader,journal_reader)
    require(set(binding['original_executions']) == {'trial_controller','deadline'}, 'Both original retained invocations required')
    cleanup = values['owned_cleanup']
    require(str(cleanup['status']).startswith('PASS') and cleanup['owned_cleanup_complete'] is True, 'Root actual owned cleanup proof required')
    baseline = reader(binding['runtime_baseline']); anchor = binding['runtime_anchor']
    require(baseline['status'] == 'PASS' and baseline['main_owner'] == anchor['main_owner'] == ce['owner']
        and all(baseline[key] == anchor[key] for key in ('fleet_owner','inference_worker','actors','source_hashes','control_hashes','unit_files','environment_sha256')),
        'Concrete post-return CE baseline differs from returned owner/held closure')
    require(len(anchor['actors']) == 192 and len(anchor['control_hashes']) == 2
        and len(anchor['source_hashes']) >= 61, 'Complete actual192/source/control closure required')
    for name,digest in CANDIDATE_SOURCES.items():
        require(anchor['source_hashes'][str(GAME/'Scripts/dqn'/name)] == digest, 'Installed candidate5 source differs')
    predecessor = reader(binding['predecessor_quality_plan'])
    require(binding['predecessor_quality_plan']['path'] == str(PREDECESSOR_PLAN)
        and binding['predecessor_quality_plan']['sha256'] == PREDECESSOR_PLAN_SHA, 'Exact predecessor-quality plan required')
    expected_old = dict(EVALUATOR); expected_old['Scripts/dqn/config.py'] = 'f2794754a14e9f13c82b613aa131698246a08dc9021c18f1b78fda7c4b484498'
    require(predecessor['evaluator_source_hashes'] == expected_old and predecessor['execution_source_hashes'] == EXECUTION,
        'Only reviewed installed config source delta is allowed from predecessor')
    campaign = binding['campaign']
    for key in ('output_directory','preview_directory','execution_directory'):
        p = Path(campaign[key]); require(p.is_absolute() and p == p.resolve(strict=False)
            and p.is_relative_to(GAME/'logs/managed-learning-20261015'), 'Explicit canonical owned future directory required')
    require(len({campaign[k] for k in ('output_directory','preview_directory','execution_directory')}) == 3
        and re.fullmatch(r'robotron-quality-[A-Za-z0-9_-]+',campaign['unit'])
        and campaign['reference_label'] != campaign['candidate_label'] and campaign['hypothesis'].strip(), 'Unique fresh quality names/hypothesis required')
    return dict(cpu_job=cpu,proof=proof,completion=completion,trial=trial,activation=activation,ce_return=ce,baseline=baseline,predecessor=predecessor)
