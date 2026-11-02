"""Preserve a new policy only after the original certified four-leg assessment.

Default invocation is inert. --execute verifies closed original receipts;
--publish additionally copies the qualified candidate to a fresh protected
label. No scientific reader is rerun and no live process or pointer is changed.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import sys
import tempfile
import time

GAME = Path('/home/dave/source/repos/ArcadeAI/Robotron')
B = GAME/'tools/startup_policy_journal_proposal'
READER = GAME/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py'
READER_SHA = 'c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071'
ASSESSOR_SHA = '7feb9aa46fff44e11e8d9e669250f71bed4813e3ee66e7ab9398931532fc2039'
ASSESSOR_PATH = Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/quality32-protected3045-vs-later3262-selectorReuse-original01-preparation-20261025/isolated-source-family-original01/assess_quality32_quota64_selected_original01_v2.py')
CANDIDATE_SHA = 'df4314b05aceddeec263e598690fe803e32985497a0e26b38f36162452291bb4'
CANDIDATE_CLOCKS = {'training_steps': 12796292, 'optimized_samples': 50837817344, 'learner_frame_count': 3262935672, 'frame_count': 6336612924}
PAIR_SHA = '95092f4aaaf7384a6bebfeb72a5b8743bb01159dd9fbe5a374f49b0716493f25'
READINESS_SHA = '8a2ed32fa379317bf4557c3c900c2006715df8738412e59c2608d9ad7f3025cf'
ARCHIVES = GAME/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py'
ARCHIVES_SHA = '2ed5fde26fe50a23bc9572965e483ae6634b31ffbe5d4147c9f5bc338396d445'
CONTROLLER = GAME/'tools/training_connection_lifecycle_proposal_20261023/control_owned_health_CPU660_v2.py'
CONTROLLER_SHA = 'a524ebb3be864bb03f13fff0af471782b2c6497c321da38ff83b679934cd03d1'
ORDER = ('R1', 'C1', 'R2', 'C2')
FOLDERS = ('01-reference', '02-candidate', '03-reference', '04-candidate')


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def reader_module():
    require(digest(READER) == READER_SHA, 'Exact immutable reader differs')
    spec = importlib.util.spec_from_file_location('_certified_protection_reader_'+str(time.time_ns()), READER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def birth(pid):
    try:
        return int(Path('/proc', str(pid), 'stat').read_text().rsplit(')', 1)[1].split()[19])
    except (FileNotFoundError, ProcessLookupError):
        return None


def validate_assessment_command(fields, owner, config, job):
    root_job = job['assessment_job']
    expected = ['/usr/bin/python3.12', '-I', '-B', job['assessor_source']['path'],
        '--execute', '--job', root_job['path'], '--job-sha256', root_job['sha256'],
        '--source-sha256', ASSESSOR_SHA]
    require(config['unit'] == owner['unit'] and config['argv'] == expected,
        'Original campaign assessor config differs')
    wrapper = ['/usr/bin/env', '-u', 'LD_PRELOAD', '-u', 'PYTHONPATH', 'CUDA_VISIBLE_DEVICES=',
        'PYTHONDONTWRITEBYTECODE=1', 'TMPDIR='+str(Path(config['output'])/'tmp')]+expected
    match = re.fullmatch(r'\{ path=/usr/bin/env ; argv\[\]=(.*?) ; ignore_errors=no ; .* \}', fields['ExecStart'])
    require(match is not None and shlex.split(match[1]) == wrapper,
        'Actual original service did not execute the selected campaign assessor')


def verify_held_launch_pin(entry, readiness, controller, reader):
    """Require exact controller ABI plus the original full readiness identity."""
    path = Path(entry['path'])
    require(path.is_absolute() and str(path) == entry['path'] and '..' not in path.parts,
        'Exact absolute original held launch input path required')
    require(set(entry) == {'path', 'sha256', 'bytes', 'identity'}
        and set(entry['identity']) == {'device', 'inode', 'mode', 'uid', 'nlink'},
        'Exact original launch-pin ABI required')
    matches = [pin for pin in readiness['inputs'] if pin['path'] == entry['path']]
    require(len(matches) == 1, 'Non-immutable launch input must have one full original readiness hold')
    require(set(matches[0]['identity']) == {'device', 'inode', 'bytes', 'mtime_ns', 'ctime_ns', 'mode', 'uid', 'nlink'}
        and reader.pin(path) == matches[0] and controller.pin(path) == entry,
        'Original held launch input bytes or complete identity changed')


def verify(job, job_pin, reader):
    """Read original receipts and recompute gates; never call any scientific main."""
    require(job['schema'] == 'robotron-certified-quota64-winner-protection-job-v1',
        'Exact certified-start protection job required')
    evidence = {job_pin['path']: job_pin['sha256']}
    def read(entry, as_json=True):
        value = reader.read_pin(entry, as_json=as_json)
        evidence[entry['path']] = entry['sha256']
        return value
    def module(path, expected, name):
        entry = reader.pin(path)
        require(entry['sha256'] == expected, 'Original protection dependency changed: '+name)
        read(entry, False)
        return reader.checked_module('_certified_protection_'+name+'_'+str(time.time_ns()), entry)

    require(job['assessor_source']['path'] == str(ASSESSOR_PATH)
        and job['assessor_source']['sha256'] == ASSESSOR_SHA, 'Exact original campaign assessor required')
    read(job['assessor_source'], False)
    assessor = module(job['assessor_source']['path'], ASSESSOR_SHA, 'assessor')
    runtime = module(ARCHIVES, ARCHIVES_SHA, 'archives')
    controller = module(CONTROLLER, CONTROLLER_SHA, 'controller')
    report = read(job['assessment_report'])
    root_job = read(job['assessment_job'])
    config = read(job['assessment_controller_config'])
    result = read(job['assessment_controller_result'])
    owner = read(job['assessment_owner'])
    closure = read(result['closure'])
    directory = Path(root_job['campaign_directory'])
    require(directory.is_absolute() and directory.resolve(strict=True) == directory
        and directory.is_relative_to(GAME/'logs/managed-learning-20261015/run-26')
        and root_job['schema'] == 'robotron-original-certified-quality32-campaign-assessment-job-v1'
        and root_job['output'] == str(directory/'independent-campaign-assessment-original01')
        and job['assessment_report']['path'] == str(Path(root_job['output'])/'assessment.json')
        and job['assessment_job']['path'] == str(directory/'campaign-assessment-job-original01.json')
        and job['assessment_controller_config']['path'] == str(directory/'campaign-assessment-controller-config-original01.json')
        and job['assessment_controller_result']['path'] == str(directory/'campaign-assessment-controller-original-result.json')
        and job['assessment_owner']['path'] == str(directory/'campaign-assessment-execution-original01/root-original-identity.json')
        and config['output'] == str(directory/'campaign-assessment-execution-original01'),
        'Original campaign assessment paths/schema differ')
    require(report['schema'] == 'robotron-original-certified-quality32-campaign-assessment-v1'
        and report['valid'] is report['quality_qualified'] is True
        and report['status'] == 'ORIGINAL_FOUR_LEG_QUALITY_ASSESSMENT_COMPLETE'
        and report['promotion'] is report['main_runtime_changed'] is report['learning_speed_gain_verified'] is False
        and report['job'] == job['assessment_job']
        and report['all_original_runtime_and_review_scopes_verified'] is True,
        'Successful original qualified campaign assessment required')
    require(result['actual_exit'] == 0 and result['original_attempt'] == 1 and result['no_retry'] is True
        and result['live_registration_errors'] == [], 'Original assessment controller failed or retried')
    controller.checked_config(job['assessment_controller_config']['path'])
    fields = runtime.archived_closure(closure, owner, read, exit_zero=True)
    validate_assessment_command(fields, owner, config, job)
    require(runtime.duration_seconds(fields['CPUQuotaPerSecUSec']) == 2
        and fields['MemoryMax'] == str(4 << 30) and fields['MemorySwapMax'] == '0'
        and runtime.duration_seconds(fields['RuntimeMaxUSec']) == 660 and fields['TasksMax'] == '128'
        and runtime.duration_seconds(fields['TimeoutStopUSec']) == 5
        and fields['SendSIGKILL'] == fields['Restart'] == 'no', 'Original assessor CPU scope differs')
    require(birth(owner['pid']) != owner['starttime_ticks'], 'Original assessor process remains')
    for unit in (owner['unit'], owner['timer']):
        require(controller.show(unit)['LoadState'] == 'not-found', 'Original assessor unit remains')
        require(not Path('/sys/fs/cgroup/user.slice/user-1001.slice/user@1001.service/app.slice', unit).exists(),
            'Original assessor cgroup remains')
    held_readiness = read(root_job['launch_readiness_precommit'])
    require(root_job['launch_readiness_precommit']['sha256'] == READINESS_SHA,
        'Exact selected launch readiness required before verifying launch pins')
    for entry in config['pins']:
        if entry['identity']['mode'] == '0o444':
            read(entry, False)
        else:
            # Executable and source input modes are preserved by the selected
            # controller. Require their full original readiness identity too.
            verify_held_launch_pin(entry, held_readiness, controller, reader)
            evidence[entry['path']] = entry['sha256']
    require(root_job['pair']['sha256'] == PAIR_SHA
        and root_job['launch_readiness_precommit']['sha256'] == READINESS_SHA
        and report['fixed_input_pair'] == root_job['pair'], 'Original fixed pair/readiness differs')
    pair = read(root_job['pair'])
    readiness = read(root_job['launch_readiness_precommit'])
    require(readiness['campaign_assessor'] == job['assessor_source']
        and readiness['quality_pair'] == root_job['pair'], 'Original readiness assessor/pair differs')
    for entry in report['artifacts']:
        read(entry, False)
    reviews = [reader.pin(directory/folder/'independent-quality-leg-review-original01/review.json')
        for folder in FOLDERS]
    require(report['original_leg_reviews'] == reviews, 'Original four independent review identities differ')
    legs = []
    for index, (role, folder, review_pin) in enumerate(zip(ORDER, FOLDERS, reviews)):
        root = directory/folder
        reviewed = read(review_pin)
        native_job_pin = reader.pin(root/'job.json')
        native_job = read(native_job_pin)
        native_result_pin = reader.pin(root/'diagnostic-output-original01/result.json')
        native = read(native_result_pin)
        native_owner_pin = reader.pin(root/'execution-original01/root-original-identity.json')
        native_owner = read(native_owner_pin)
        review_owner = read(reader.pin(root/'independent-review-execution-original01/root-original-identity.json'))
        require(reviewed['schema'] == 'robotron-original-quota64-independent-cohort-review-v1'
            and reviewed['expected_selected_games'] == 64
            and reviewed['minimum_quality_complete_games'] == 50
            and reviewed['outer_start_horizon_s'] == 21540
            and reviewed['cohort_selection'] == assessor.COHORT_SELECTION
            and reviewed['valid'] is reviewed['full_game_score_verified'] is True
            and reviewed['quality_qualified'] is reviewed['promotion'] is False
            and reviewed['quality_leg'] == native_job['quality_leg'] == role
            and reviewed['quality_pair_precommit'] == native_job['quality_pair_precommit'] == root_job['pair']
            and reviewed['original_native_job'] == native_job_pin
            and reviewed['original_result'] == native_result_pin and reviewed['original_owner'] == native_owner_pin,
            'Original independent leg joins differ')
        # The original assessor already proved runtime/wire/ROM/life/closure and
        # bound every immutable artifact. Recompute only its exact score decision.
        cohort = native['before_intentional_stop']
        legs.append(dict(role=role, policy_sha256=native['policy_before']['checkpoint_sha256'],
            cohort=cohort, cohort_selection=reviewed['cohort_selection'], evidence_verified=True, original_attempt=1, no_retry=True,
            native_identity=[native_owner['pid'], native_owner['starttime_ticks'], native_owner['invocation_id']],
            review_identity=[review_owner['pid'], review_owner['starttime_ticks'], review_owner['invocation_id']]))
    decision = assessor.assess_validated_cohorts(legs, pair['reference']['policy']['sha256'], pair['candidate']['policy']['sha256'])
    require(decision == report['decision'] and decision['all_candidate_gates_passed'] is True
        and decision['candidate_pool_used'] is False, 'Both original candidate mean/median gates must pass')
    source = pair['candidate']['policy']
    require(source['sha256'] == CANDIDATE_SHA and pair['candidate']['saved_clocks'] == CANDIDATE_CLOCKS,
        'Exact independently CPU-verified current candidate and all four saved clocks required')
    read(source, False)
    read(pair['reference']['policy'], False)
    require(all(digest(path) == expected for path, expected in evidence.items()),
        'Original protection evidence changed during verification')
    require('torch' not in sys.modules, 'Protection unexpectedly imported numerical runtime')
    return dict(schema='robotron-certified-quota64-protected-winner-v1',
        reviewed_utc=datetime.now(timezone.utc).isoformat(), root_protection_job=job_pin,
        campaign_directory=str(directory), original_assessment_report=job['assessment_report'],
        original_assessment_controller_result=job['assessment_controller_result'],
        original_assessment_owner=job['assessment_owner'], original_assessment_closure=result['closure'],
        original_assessment_job=job['assessment_job'], fixed_input_pair=root_job['pair'],
        launch_readiness=root_job['launch_readiness_precommit'], original_leg_reviews=reviews,
        assessment=decision, candidate_source=source, reference=pair['reference'],
        candidate_saved_clocks=pair['candidate']['saved_clocks'], evidence_sha256=evidence,
        original_scientific_audit_rerun=False, managed_incumbent_updated=False, live_learner_restored=False,
        learning_speed_gain_verified=False,
        scope='Frozen-policy quality only; both independent candidates and every original admitted game retained.')


def fsync_directory(path):
    fd=os.open(path,os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)


def publish(job,job_pin,reader):
    label=job['label'];destination=Path(job['destination'])
    require(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,95}',label) is not None,'Simple new label required')
    require(destination.is_absolute() and destination.resolve(strict=True) == destination
            and destination.is_dir() and destination.stat().st_uid == os.getuid(),
            'Exact owned destination directory required')
    final=destination/(label+'.pt');metadata=destination/(label+'.pt.json')
    require(not final.exists() and not metadata.exists(),'Never overwrite or retry an existing protected label')
    checked=verify(job,job_pin,reader);source=checked['candidate_source'];partials=[]
    try:
        fd,name=tempfile.mkstemp(prefix='.'+label+'.',suffix='.partial',dir=destination);partials.append(Path(name))
        with os.fdopen(fd,'wb') as output,Path(source['path']).open('rb') as stream:
            shutil.copyfileobj(stream,output);output.flush();os.fchmod(output.fileno(),0o444);os.fsync(output.fileno())
        require(digest(name) == source['sha256'],'Protected copy differs from original candidate')
        after=verify(job,job_pin,reader)
        require(after['evidence_sha256'] == checked['evidence_sha256']
                and after['candidate_source'] == source,'Original evidence changed while copying; no publication')
        checked.update(published_utc=datetime.now(timezone.utc).isoformat(),protected_checkpoint=str(final),
            checkpoint_sha256=source['sha256'],checkpoint_bytes=source['bytes'])
        fd,meta_name=tempfile.mkstemp(prefix='.'+label+'.',suffix='.partial',dir=destination);partials.append(Path(meta_name))
        with os.fdopen(fd,'w') as stream:
            json.dump(checked,stream,indent=2,allow_nan=False);stream.write('\n')
            stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
        os.link(name,final);fsync_directory(destination)
        # A failure here deliberately retains the unpromoted model orphan.
        os.link(meta_name,metadata);fsync_directory(destination)
    finally:
        for path in partials:path.unlink(missing_ok=True)
        fsync_directory(destination)
    return checked


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if '--execute' not in argv:
        print('PLAN_ONLY: no reads, writes, launches, services or policy publication')
        return 0
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--publish', action='store_true')
    parser.add_argument('--job', type=Path, required=True)
    parser.add_argument('--job-sha256', required=True)
    parser.add_argument('--source-sha256', required=True)
    args = parser.parse_args(argv)
    require(digest(__file__) == args.source_sha256, 'Exact selected protection source required')
    reader = reader_module()
    entry = reader.pin(args.job)
    require(entry['sha256'] == args.job_sha256, 'Protection job SHA differs')
    job = reader.read_pin(entry)
    result = publish(job, entry, reader) if args.publish else verify(job, entry, reader)
    print(json.dumps(dict(quality_qualified=result['assessment']['all_candidate_gates_passed'],
        protected_checkpoint=result.get('protected_checkpoint'), managed_incumbent_updated=False,
        live_learner_restored=False)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
