"""Future live-CE capture metadata bindings; no import-time reads or actions.

No KL trial, LATCH, ending, replay or learning-speed claim is inferred here.
The root alone supplies actual post-closure evidence and selects a reference.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import stat

GAME = Path('/home/dave/source/repos/ArcadeAI/Robotron')
SCHEMA = 'robotron-live-CE-candidate-quality-bindings-v1'
PHASE = GAME / 'tools/phase_snapshot_cpu_verifier_proposal/verify_phase_snapshot.py'
PHASE_SHA = 'b2e732dc731b2b601f7499d2cafd5841896daf2b0713d496b98cb6b8d7279519'
STRICT_SHA = '9ef38e17e1b9eee3f6c43e40005812f2ebe3cff16d08bf61d3e820c2d41134c8'
BASE_SHA = '7d1103daf2a77be8250884cb75ce04a640000f04b4376e994d493bc6fd0f7ead'
PREDECESSOR_PLAN = GAME / 'logs/managed-learning-20261015/quality-448M-vs-rawKL-trial02-first8M-20261017/plan.json'
PREDECESSOR_PLAN_SHA = 'b502625ed8e39f01fa57af1c9f9cc8283794aa14e351e2b9bc9ec1268b267ecf'
FREEZE_RELEASE = GAME / 'logs/managed-learning-20261015/run-26/rawKL-trial02-quality-root-freeze-release-20261017/root-explicit-source-freeze-release.json'
FREEZE_RELEASE_SHA = '6d509af8bab78803f2f57088f5ef62efa1b07be4f107da45cde906ce6aade34f'
REFERENCES = {
    str(GAME/'models_dqn/managed-incumbents/fresh3-448M-confirmed.pt'):
        '1e085a128e237c2bb0636b073e5053dd8bf5be932bcbd8249543b3af20e23021',
    str(GAME/'models_dqn/managed-incumbents/rawkl-trial02-512M-confirmed.pt'):
        '1b2fb26bb01842ac43e71681d92ce3f7cdad38bfcdd2279e2c9058b2e760f7d8',
}
CLOCKS = ('training_steps', 'optimized_samples', 'learner_frame_count', 'frame_count')
OWNER_KEYS = {'pid', 'starttime_ticks', 'unit', 'invocation_id', 'cgroup'}
EVALUATOR = {'tools/run_frozen_sidecar.py': 'cd034413c2fd8a56bb9d22f8df86889939edfad041ee4e2e0210a831b5f9fe90', 'tools/sidecar_boot.py': 'f06492e6d96cd472d9f0073b4c643e820bcacb6a96c5f542a59d6b6874e62362', 'Scripts/main.lua': '060f838359d35ef6c87b96dfe02ad34618ef974d5a43fefcb74320ebe9deecaf', 'Scripts/robotron_socket_wait.c': 'fc9ed2719839f72e36346d0886e5b32116a167d49414b506dc8b5f4252464cfc', 'Scripts/dqn/config.py': '19abcbde4d08cf8465b82185ac6dd52eb8965adb8611584e0677c4c7ff21d1fd', 'Scripts/dqn/model.py': 'bcd174f05610c6f773ca8c53f9155206eba4f7b6a11383516ddd71f3b513eeb4', 'Scripts/dqn/actor_tags.py': 'fc5b868a7fb68d4ab7ba65ba872ea0e845759af6143edfe648239d57cb7f1591', 'Scripts/dqn/socket_server.py': 'd99dd2782fc3e8f67670aefb398ed0dfdc1fd859432e24c8bd8dea4da2825214', 'Scripts/dqn/game_journal.py': '10827d786becfd19c386bddfbce85f1ab5ace5349d87717305e4044a2843edb0', 'Scripts/dqn/managed_measurement.py': '9649d0ba199bdc0943202164da7a9058e5d578b9c411ce26a950b2595c7e96e6', 'Scripts/dqn/inference_actor.py': '7cc812adeab8dc7cb989f9024592767928afa786966b85f3488023fb8d6b34ce', 'Scripts/dqn/nstep_buffer.py': 'e46f03e9a626b3a24dea702344b0bbf050f1fdc5af672fc8fc9d18e6afef74c1'}
EXECUTION = {'/home/dave/source/repos/ArcadeAI/Robotron/tools/run_quality_campaign.py': '574e56f28499c751c639ee8a3474eecd5ca8de8c896da3dd44d5e4fc2fe60128', '/home/dave/source/repos/ArcadeAI/Robotron/tools/run_frozen_sidecar.py': 'cd034413c2fd8a56bb9d22f8df86889939edfad041ee4e2e0210a831b5f9fe90', '/home/dave/source/repos/ArcadeAI/Robotron/tools/compare_sidecar_measurements.py': '879590b64e760037a81da2ff574d5994d9259cf1746b8e406177e2220d37c746', '/home/dave/source/repos/ArcadeAI/Robotron/tools/compare_frozen_measurements.py': '53f744737a722fec2760c0001dc5747b19b05e07a1de8699764c781f04da6be0'}
CANDIDATE_SOURCES = {'agent.py': '865a0df717b39951b7f7c516e4a962e3d48cf4d3dc11295ff266e58653e6c74b', 'training.py': '90b847856f810cb4f52513a4bd0625b2d15d4801107bff398060faae25bc4be4', 'loss_kernel.py': '23eb8fc0d8409c9f31ef26ec4596da9c2257e3985abbbfa7d5fbdcb337e21f67', 'config.py': '19abcbde4d08cf8465b82185ac6dd52eb8965adb8611584e0677c4c7ff21d1fd', 'priority_phase.py': 'ee3c0d02bc1eab55e92ffd605c3736fe5a0ef905a8a8ee242c687301ea2b7c5b'}
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
    return json.loads(read_bytes(pin),parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def read_api(pin):
    # Only the explicitly named raw trigger API may retain optional NaN fields.
    return json.loads(read_bytes(pin))


def four(value):
    result = {key: value[key] for key in CLOCKS}
    require(all(type(v) is int and v > 0 for v in result.values()), 'Four positive actual clocks required')
    return result


def flat(pin):
    return dict(path=pin['path'], sha256=pin['sha256'], **pin['identity'])


def owner(value):
    require(set(value) == OWNER_KEYS and type(value['pid']) is int and value['pid'] > 0
        and type(value['starttime_ticks']) is int and value['starttime_ticks'] > 0
        and re.fullmatch('[0-9a-f]{32}', value['invocation_id'])
        and value['unit'].endswith('.service') and value['cgroup'].startswith('/'), 'Actual five-key owner required')
    return value


def candidate_descriptor(value):
    require(set(value) == {'tag','path','sha256','bytes'}
        and re.fullmatch('[A-Za-z0-9_-]{1,100}', value['tag'] or '')
        and value['path'] == str(GAME/'models_dqn/managed-checkpoints'/(value['tag']+'.pt'))
        and re.fullmatch('[0-9a-f]{64}', value['sha256'] or '')
        and type(value['bytes']) is int and 0 < value['bytes'] <= 512 << 20,
        'Actual unique live-CE candidate tag/hash/dynamic bytes required')


def check_cpu(job, proof, completion, candidate):
    candidate_descriptor(candidate)
    require(job['schema'] == 'robotron-phase-snapshot-checkpoint-CPU-job-v1'
        and job['verifier_sha256'] == PHASE_SHA and job['strict_phase_base_sha256'] == STRICT_SHA
        and job['original_strict_base_sha256'] == BASE_SHA, 'Actual candidate phase CPU job required')
    spec = job['phase_snapshot']
    require(spec['purpose'] == 'candidate' and spec['observed_clients'] == 192
        and spec['expected_phase']['metric'] == 'ce' and spec['expected_phase']['valid'] is True,
        'Only genuine live192 CE candidate phase CPU accepted')
    owner(spec['owner'])
    source, copied = job['source'], job['verification_copy']
    require(source['path'] == candidate['path']
        and candidate['sha256'] == source['sha256'] == copied['sha256']
        and candidate['bytes'] == source['bytes'] == copied['bytes'], 'Candidate source/hash/bytes differ')
    require(source['path'] != copied['path']
        and (source['identity']['device'], source['identity']['inode']) !=
            (copied['identity']['device'], copied['identity']['inode'])
        and all(p['identity']['bytes'] == candidate['bytes'] and p['identity']['mode'] == '0o444'
            and p['identity']['nlink'] == 1 and p['identity']['uid'] == os.getuid() for p in (source, copied)),
        'Independent readonly candidate copy required')
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
    require(set(completion) == {'argv','exit_code'} and completion['exit_code'] == 0
        and isinstance(argv,list) and len(argv) == 12 and Path(argv[0]).is_absolute(),
        'Genuine numerical command and original exit0 required; no fabricated CPU owner')
    require(argv == [argv[0],'-Xgil=0','-I','-B',str(PHASE),'--execute','--job',proof['job_file']['path'],
        '--expected-job-sha256',proof['job_file']['sha256'],'--expected-verifier-sha256',PHASE_SHA],
        'Phase CPU argv flags/order/job/source differ')
    require(all(four(proof['clocks'])[k] >= four(job['clock_floor'])[k] for k in CLOCKS), 'Candidate predates capture floor')
    saved = proof['saved_priority_metric_phase']; expected = spec['expected_phase']
    require(saved['metric'] == 'ce' and saved['valid'] is True
        and all(saved[k] == expected[k] for k in ('phase_id','root_precommit_sha256','started_from'))
        and saved['phase_record_sha256'] == expected['founder_phase_record_sha256']
        and saved['last_resume_record_sha256'] == expected['last_resume_record_sha256'], 'Saved CE founder/resume differs')


def check_reference(reference, metadata, closure):
    require(set(reference) == {'path','sha256','bytes','metadata'}
        and reference['path'] in REFERENCES and reference['sha256'] == REFERENCES[reference['path']]
        and type(reference['bytes']) is int and 0 < reference['bytes'] <= 512 << 20,
        'Root must explicitly select protected448 or actually protected512')
    require(reference['metadata']['path'] == reference['path']+'.json'
        and metadata['schema'] == 'robotron-protected-quality-winner-v1'
        and metadata['protected_checkpoint'] == reference['path']
        and metadata['checkpoint_sha256'] == reference['sha256']
        and metadata['assessment']['qualified_improvement'] is True,
        'Actual create-only qualified protected metadata required')
    outcome = closure['accepted_quality_outcome']
    require(outcome in ('qualified_improvement','not_improved'), 'Previous outcome is not a completed valid campaign')
    is512 = reference['path'].endswith('/rawkl-trial02-512M-confirmed.pt')
    require(is512 == (outcome == 'qualified_improvement'), 'Reference must follow actual previous outcome; no synthetic promotion')
    if is512:
        require(metadata['plan_sha256'] == PREDECESSOR_PLAN_SHA, 'Protected512 must come from actual preceding campaign')


def validate(binding, *, reader=read, api_reader=None):
    api_reader = (read_api if reader is read else reader) if api_reader is None else api_reader
    require(set(binding) == {'schema','experiment','candidate','reference','evidence','current_ce_phase',
        'runtime_baseline','runtime_anchor','previous_campaign','predecessor_quality_plan','campaign'}
        and binding['schema'] == SCHEMA and binding['experiment'] == 'best10M-fresh3-eps10-cap8-nosmooth', 'Explicit live-CE binding schema required')
    evidence = binding['evidence']
    require(set(evidence) == {'capture_result','phase_cpu_job','phase_cpu_report','phase_cpu_completion'}, 'Exact actual capture/CPU evidence required')
    capture,cpu,proof,completion = [reader(evidence[k]) for k in ('capture_result','phase_cpu_job','phase_cpu_report','phase_cpu_completion')]
    check_cpu(cpu,proof,completion,binding['candidate'])
    require(proof['job_file']['path'] == evidence['phase_cpu_job']['path']
        and proof['job_file']['sha256'] == evidence['phase_cpu_job']['sha256'], 'Report does not identify this actual CPU job')
    phase = binding['current_ce_phase']; spec = cpu['phase_snapshot']
    require(set(phase) == {'record','boot_checkpoint','boot_verification','expected'}
        and (phase['record'],phase['boot_checkpoint'],phase['boot_verification'],phase['expected']) ==
        (spec['phase_record'],spec['boot_checkpoint'],spec['boot_verification'],spec['expected_phase']),
        'Live CE record/actual boot/founder must match phase CPU')
    record = reader(phase['record']); boot = reader(phase['boot_verification'])
    require(record['metric'] == 'ce' and record['checkpoint'] == phase['boot_checkpoint']
        and boot['status'] == 'PASS' and (boot['sha256'],boot['bytes']) ==
        (phase['boot_checkpoint']['sha256'],phase['boot_checkpoint']['bytes']), 'Actual CE boot proof differs; a startup snapshot is not its boot')
    acquisition = reader(spec['acquisition'])
    require(acquisition['schema'] == 'robotron-owned-phase-snapshot-acquisition-v1'
        and acquisition['purpose'] == 'candidate' and acquisition['client_count'] == 192
        and acquisition['owner_before'] == acquisition['owner_after'] == spec['owner']
        and acquisition['tag'] == binding['candidate']['tag'] and acquisition['stopped_absence'] is None
        and acquisition['source_checkpoint'] == {k:binding['candidate'][k] for k in ('path','sha256','bytes')}
        and acquisition['clock_floor'] == cpu['clock_floor']
        and acquisition['phase_record_sha256'] == phase['record']['sha256']
        and acquisition['boot_checkpoint'] == phase['boot_checkpoint']
        and acquisition['completed_slot_transition'] is not None, 'Authentic live192 CE managed acquisition required')
    require(capture['status'] == 'CAPTURED_PENDING_CPU' and capture['source'] == cpu['source']
        and capture['verification_copy'] == cpu['verification_copy'] and capture['acquisition'] == spec['acquisition']
        and capture['cpu_job'] == evidence['phase_cpu_job'] and capture['current_phase'] == phase
        and capture['owner'] == spec['owner'], 'Actual capture result/source/copy/acquisition/owner differs')
    finished_capture = reader(capture['capture_completion'])
    require(finished_capture['status'] == 'COMPLETE' and finished_capture['tag'] == binding['candidate']['tag']
        and finished_capture['owner_before'] == finished_capture['owner_after'] == spec['owner']
        and finished_capture['transition'] == acquisition['completed_slot_transition'],
        'Original capture completion must bind this actual owner/tag/request transition')
    trigger = api_reader(capture['trigger_API'])
    require(trigger['client_count'] == 192 and trigger['training_enabled'] is True and trigger['measurement_active'] is False
        and trigger['managed_experiment'] == binding['experiment']
        and trigger['host_pipeline']['learning_exposure']['optimizer']['process_id'] == spec['owner']['pid']
        and four(trigger) == four(cpu['clock_floor']),
        'Trigger must be actual unpaused192 training on the captured CE owner')
    previous = binding['previous_campaign']
    require(set(previous) == {'closure','source_freeze_release'} and isinstance(previous['source_freeze_release'],dict)
        and previous['source_freeze_release']['path'] == str(FREEZE_RELEASE)
        and previous['source_freeze_release']['sha256'] == FREEZE_RELEASE_SHA,
        'Actual root explicit source-freeze release required before preparing new quality')
    release = reader(previous['source_freeze_release'])
    closure = reader(previous['closure'])
    require(closure['status'] == 'PASS_ORIGINAL_QUALITY_ARCHIVED_OWNED_CLEANUP_COMPLETE'
        and closure['owned_cleanup_complete'] is True and closure['main192_and_resources_healthy'] is True
        and closure['original_execution']['exec_code'] == 1 and closure['original_execution']['exit_status'] == 0
        and closure['original_execution']['result'] == 'success'
        and closure['original_execution']['archived_before_release'] is True,
        'Actual prior campaign original terminal/owned cleanup required')
    closure_job = reader(closure['root_job'])
    require(closure_job['schema'] == 'robotron-trial02-quality-owned-closure-job-v1'
        and closure_job['binding_job']['sha256'] == '3b16c36da91c63fd4fb218f1fed3c1c5a5fe8caff73534d880aeaeccfe4c81fe'
        and closure_job['terminal_summary']['path'] == str(PREDECESSOR_PLAN.parent/'summary.json'),
        'Closure is not the preceding actual b502 campaign')
    require(release['schema'] == 'robotron-quality-campaign-root-source-freeze-release-v1'
        and release['source_freeze_released'] is True and release['actual_plan_sha256'] == PREDECESSOR_PLAN_SHA
        and release['campaign_outcome'] == closure['accepted_quality_outcome']
        and release['actual_quality_cleanup'] == {k:previous['closure'][k] for k in ('path','sha256','bytes')}
        and release['protected_incumbent'] == {k:binding['reference'][k] for k in ('path','sha256','bytes')},
        'Actual freeze release/cleanup/protected reference differs')
    check_reference(binding['reference'],reader(binding['reference']['metadata']),closure)
    baseline = reader(binding['runtime_baseline']); anchor = binding['runtime_anchor']
    require(baseline['status'] == 'PASS' and baseline['main_owner'] == anchor['main_owner'] == spec['owner']
        and all(baseline[k] == anchor[k] for k in ('fleet_owner','inference_worker','actors','source_hashes','control_hashes','unit_files','environment_sha256')),
        'Fresh actual same-CE-owner baseline differs')
    require(len(anchor['actors']) == 192 and len({a['pid'] for a in anchor['actors']}) == 192
        and len(anchor['control_hashes']) == 2 and len(anchor['source_hashes']) >= 61, 'Complete192/source/control closure required')
    for name,digest in CANDIDATE_SOURCES.items():
        require(anchor['source_hashes'][str(GAME/'Scripts/dqn'/name)] == digest, 'Installed candidate5 source differs')
    predecessor = reader(binding['predecessor_quality_plan'])
    require(binding['predecessor_quality_plan']['path'] == str(PREDECESSOR_PLAN)
        and binding['predecessor_quality_plan']['sha256'] == PREDECESSOR_PLAN_SHA
        and predecessor['evaluator_source_hashes'] == EVALUATOR and predecessor['execution_source_hashes'] == EXECUTION,
        'Same approved current12+4 evaluator/compiled backend required')
    campaign = binding['campaign']
    for key in ('output_directory','preview_directory','execution_directory'):
        p = Path(campaign[key]); require(p.is_absolute() and p == p.resolve(strict=False)
            and p.is_relative_to(GAME/'logs/managed-learning-20261015'), 'Canonical future quality directory required')
    require(len({campaign[k] for k in ('output_directory','preview_directory','execution_directory')}) == 3
        and re.fullmatch(r'robotron-quality-[A-Za-z0-9_-]+',campaign['unit'])
        and campaign['reference_label'] != campaign['candidate_label'] and campaign['hypothesis'].strip(), 'Unique future campaign names required')
    return dict(cpu_job=cpu,proof=proof,completion=completion,capture=capture,current_ce_phase=phase,baseline=baseline,predecessor=predecessor)
