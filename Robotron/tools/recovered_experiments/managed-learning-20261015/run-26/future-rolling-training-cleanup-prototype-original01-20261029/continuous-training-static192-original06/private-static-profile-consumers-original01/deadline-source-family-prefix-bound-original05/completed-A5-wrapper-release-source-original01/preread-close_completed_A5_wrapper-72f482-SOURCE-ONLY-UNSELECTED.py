"""One current7067 completed A5 wrapper release, explicit Root mode only.

This source never launches/adopts a Popen, retries a scientific payload, or
controls PUB, Main, fleet, a timer, or any service except CURRENT_A5_UNIT.
Future terminal evidence is required at operation time; no completion is inferred
from a terminal-file name, process absence alone, or stale status.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import time

HERE = Path(__file__).resolve().parent
FIXED = {'selection': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/deadline-source-family-prefix-bound-original05/durable-R1-launch-source-original01/actual-original03-R1-launch-selection-original01.json', 'sha256': '7067e638c7b47e5b34b14c2076af0717d142c23bcbaade4484298c570abe7e5b', 'bytes': 12973, 'identity': {'device': 2304, 'inode': 85340191, 'bytes': 12973, 'mtime_ns': 1793303533826166807, 'ctime_ns': 1793303533826166807, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'intent': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/deadline-source-family-prefix-bound-original05/durable-R1-launch-source-original01/original-R1-wrapper-intent.json', 'sha256': '4ef52d87cac99518474256ed6b443b33dde8a64be07c2500217bf477e0aa7aae', 'bytes': 17343, 'identity': {'device': 2304, 'inode': 85340197, 'bytes': 17343, 'mtime_ns': 1793303533918831293, 'ctime_ns': 1793303533918831293, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'live': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/deadline-source-family-prefix-bound-original05/durable-R1-launch-source-original01/actual-original-R1-live-owner.json', 'sha256': '245df07bccd1157c28ea6d26e05e7c93eee4e7644618d4b92c17d5fea895557b', 'bytes': 2593, 'identity': {'device': 2304, 'inode': 85340192, 'bytes': 2593, 'mtime_ns': 1793303537925020882, 'ctime_ns': 1793303537925020882, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'wrapper': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/deadline-source-family-prefix-bound-original05/durable-R1-launch-source-original01/run_owned_physical_R1_v1.py', 'sha256': '4ad6672a24d8df7d321d2ce9e6fb597b0b970f6af4b2e041e0a73dcf5a705640', 'bytes': 9475, 'identity': {'device': 2304, 'inode': 85334090, 'bytes': 9475, 'mtime_ns': 1793297542214666488, 'ctime_ns': 1793297542214666488, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'review_preparer': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/deadline-source-family-prefix-bound-original05/prepare_deadline_independent_review_v4.py', 'sha256': 'd0955c345dd46d08d261cf6c20c8dff87e1335c4977d55d75a8ed895fac99be0', 'bytes': 17179, 'identity': {'device': 2304, 'inode': 85333911, 'bytes': 17179, 'mtime_ns': 1793297226271097135, 'ctime_ns': 1793297226271097135, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'review_precommit': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/fresh-prefix16c-b231-deadline32-RCRC-original03-20261029/review-precommit-original01/precommitted-four-reviews.json', 'sha256': 'b8d9b78e7e51f81ca59c63efefd79fffae7e657629cdcc3a38aaebcde476f79a', 'bytes': 22046, 'identity': {'device': 2304, 'inode': 85339976, 'bytes': 22046, 'mtime_ns': 1793303296310263712, 'ctime_ns': 1793303296310263712, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'helpers': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py', 'sha256': '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1', 'bytes': 19907, 'identity': {'device': 2304, 'inode': 82204560, 'bytes': 19907, 'mtime_ns': 1792667384836340773, 'ctime_ns': 1792667384836340773, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'lifecycle': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/tools/quality_capacity_proposal/control_quality32_review_v1.py', 'sha256': '218e7f861deb82c340527d218ed9f92ef5c5836c8cb9d32452c0598e61ff9a14', 'bytes': 17290, 'identity': {'device': 2304, 'inode': 81930188, 'bytes': 17290, 'mtime_ns': 1792424008109022468, 'ctime_ns': 1792424257834393599, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'sequence': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/tools/startup_policy_journal_proposal/sequence_quality32_2259_prospective197_v1.py', 'sha256': 'b462dbb6562e08ef6efca66bc10f6b0c94273daceb12ac9f86f4a68eb972d6e4', 'bytes': 20193, 'identity': {'device': 2304, 'inode': 82217207, 'bytes': 20193, 'mtime_ns': 1792698816935644930, 'ctime_ns': 1792698816935644930, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}}
CURRENT_A5_UNIT = 'robotron-physical-cohort-proof2s-1087277eafb3f40e-r1-wrapper-original01-20261029.service'
SCHEMA = 'robotron-current7067-A5-wrapper-only-owned-release-v1'
SUCCESS = 'PASS_ORIGINAL_A5_WRAPPER_EXIT0_ARCHIVED_AND_RELEASED'
RESOURCE_FIELDS = dict(Type='exec', Restart='no', NRestarts='0', RemainAfterExit='yes',
    CPUQuotaPerSecUSec='2s', MemoryMax='536870912', MemorySwapMax='0', TasksMax='128',
    RuntimeMaxUSec='1h 20min', TimeoutStopUSec='10s', SendSIGKILL='no')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def identity_of(s):
    return dict(device=s.st_dev, inode=s.st_ino, bytes=s.st_size,
        mtime_ns=s.st_mtime_ns, ctime_ns=s.st_ctime_ns,
        mode=oct(stat.S_IMODE(s.st_mode)), uid=s.st_uid, nlink=s.st_nlink)


def raw_pin(path):
    p = Path(path)
    require(p.is_absolute() and str(p) == str(p.resolve()) and not p.is_symlink(),
            'Canonical non-symlink file required')
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_uid == 1001 and before.st_nlink == 1
                and stat.S_IMODE(before.st_mode) == 0o444 and 0 <= before.st_size <= 2 << 20,
                'Bounded immutable owned source/metadata required')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            body = stream.read((2 << 20) + 1)
        after = os.fstat(fd)
        require(identity_of(before) == identity_of(after) == identity_of(p.stat())
                and len(body) == before.st_size, 'Immutable read bracket changed')
        return dict(path=str(p), sha256=hashlib.sha256(body).hexdigest(), bytes=len(body),
                    identity=identity_of(after)), body
    finally:
        os.close(fd)


def checked(value, as_json=True):
    actual, body = raw_pin(value['path'])
    require(actual == value, 'Exact held full8 pin changed: ' + value['path'])
    return json.loads(body) if as_json else body


def put(path, value):
    path = Path(path)
    body = (json.dumps(value, indent=2, allow_nan=False) + '\n').encode()
    with path.open('xb') as stream:
        stream.write(body)
        stream.flush()
        os.fchmod(stream.fileno(), 0o444)
        os.fsync(stream.fileno())
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    return raw_pin(path)[0]


def load(name, value):
    checked(value, as_json=False)
    spec = importlib.util.spec_from_file_location(name, value['path'])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def validate_scope(s, identity, terminal=False):
    require(identity['unit'] == CURRENT_A5_UNIT and s.get('Id') == CURRENT_A5_UNIT
            and s.get('InvocationID') == identity['invocation_id']
            and s.get('ExecMainPID') == str(identity['pid']), 'Exact original A5 owner required')
    require(all(s.get(k) == v for k, v in RESOURCE_FIELDS.items()),
            'Original A5 resources/restart policy changed')
    command = s.get('ExecStart', '')
    require(all(x in command for x in (FIXED['wrapper']['path'], FIXED['wrapper']['sha256'],
            FIXED['selection']['path'], FIXED['selection']['sha256'],
            '--run', '--launch-selection', '--launch-selection-sha256', '--expected-source-sha256')),
            'Original A5 source/selection command changed')
    if terminal:
        require(s.get('MainPID') == '0' and s.get('ExecMainCode') == '1'
                and s.get('ExecMainStatus') == '0' and s.get('Result') == 'success'
                and s.get('SubState') in ('exited', 'dead'), 'Original A5 normal0 terminal required')
    else:
        require(s.get('MainPID') == str(identity['pid']) and s.get('ActiveState') == 'active'
                and s.get('SubState') == 'running', 'Captured original live A5 scope required')
        expected = '/user.slice/user-1001.slice/user@1001.service/app.slice/' + CURRENT_A5_UNIT
        require(s.get('ControlGroup') == expected, 'Exact captured running A5 cgroup required')


def validate_recorded(selection, intent, live, terminal, intent_pin):
    require(selection['schema'] == 'robotron-generic-physical-original-R1-launch-selection-v1'
            and selection['wrapper_unit'] == CURRENT_A5_UNIT
            and selection['sources']['wrapper'] == FIXED['wrapper']
            and selection['sources']['review_preparer'] == FIXED['review_preparer']
            and selection['original_attempt'] == 1 and selection['no_retry'] is True,
            'Only current7067 original A5 selection is authorized')
    require(intent['launch_selection'] == FIXED['selection'] and intent['source'] == FIXED['wrapper']
            and intent['readiness'] == selection['readiness']
            and intent['exact_original_job'] == selection['R1']['native_job']
            and intent['exact_original_config'] == selection['R1']['config']
            and intent['original_attempt'] == 1 and intent['no_retry'] is True
            and intent['unit'] == CURRENT_A5_UNIT and intent['canonical_state_written'] is False,
            'Exact original A5 intent/source/job/config required')
    identity = dict(unit=intent['unit'], invocation_id=intent['invocation_id'],
        pid=intent['actual_wrapper_pid'], starttime_ticks=intent['actual_wrapper_birth'],
        properties=intent['actual_wrapper_scope'])
    require(type(identity['pid']) is type(identity['starttime_ticks']) is int
            and identity['pid'] > 0 and identity['starttime_ticks'] > 0
            and len(identity['invocation_id']) == 32, 'Recorded original wrapper identity required')
    validate_scope(identity['properties'], identity)
    require(live['wrapper_pid'] == identity['pid'] and live['wrapper_birth'] == identity['starttime_ticks']
            and live['wrapper_unit'] == identity['unit']
            and live['wrapper_invocation_id'] == identity['invocation_id']
            and live['readiness'] == selection['readiness']
            and live['original_job'] == selection['R1']['native_job']
            and live['config'] == selection['R1']['config'], 'Original A5 live registration differs')
    for original in (live['controller'], live['owner']):
        require(type(original['pid']) is type(original['starttime_ticks']) is int
                and original['pid'] > 0 and original['starttime_ticks'] > 0
                and original['observed_live'] is True, 'Actual original child owner required')
    require(live['owner']['unit'] == selection['R1']['native_unit'], 'Original native unit differs')
    require(terminal['schema'] == 'robotron-owned-durable-R1-wrapper-terminal-v1'
            and terminal['intent'] == intent_pin
            and terminal['wrapper_pid'] == identity['pid']
            and terminal['wrapper_birth'] == identity['starttime_ticks']
            and terminal['original_attempt'] == 1 and terminal['no_retry'] is True
            and terminal['scientific_payload_retried'] is False
            and terminal['quality_qualified'] is False and terminal['promotion'] is False
            and terminal['status'] == 'NATIVE_CLOSED_REVIEW_PENDING'
            and type(terminal['actual_controller_exit']) is int and terminal['actual_controller_exit'] == 0
            and terminal['live_registration_errors'] == [], 'Original successful A5 terminal required')
    return identity


def require_original_births_absent(identity, live, birth):
    originals = [dict(pid=identity['pid'], starttime_ticks=identity['starttime_ticks']),
                 live['controller'], live['owner']]
    require(all(birth(row['pid']) != row['starttime_ticks'] for row in originals),
            'An original wrapper/controller/native birth is still live')


def archive_release_completed_A5(out, identity, live, control, birth, cgroup_exists, record):
    # This kernel is deliberately A5-only, even for callers sharing the C218 ABI.
    require(identity['unit'] == CURRENT_A5_UNIT, 'No other service is authorized')
    require_original_births_absent(identity, live, birth)
    archives = record['archives']
    shown = control.command(out, 'original-A5-service-show',
                            ['systemctl', '--user', 'show', CURRENT_A5_UNIT])
    archives.append(shown)
    props = control.fields(shown)
    control.original_terminal(props, identity)
    validate_scope(props, identity, terminal=True)
    for label, argv in [
        ('cat', ['systemctl', '--user', 'cat', CURRENT_A5_UNIT]),
        ('journal', ['journalctl', '--user', '--no-pager', '-o', 'short-iso',
                     '_SYSTEMD_INVOCATION_ID=' + identity['invocation_id']])]:
        archived = control.command(out, 'original-A5-service-' + label, argv)
        archives.append(archived)
        require(archived['exit'] == 0 and archived['timed_out'] is False,
                'All three original A5 archives must succeed before release')
    record['all_three_archives_succeeded'] = True
    record['original_wrapper_exit'] = 0
    require_original_births_absent(identity, live, birth)
    release = record['owned_release']
    control.release_original(out, 'service', identity, {}, release)
    final = control.fields(release['final'])
    require(release['confirmed_absent'] is True and final.get('Id') == CURRENT_A5_UNIT
            and final.get('LoadState') == 'not-found', 'Positive original A5 unit absence required')
    require_original_births_absent(identity, live, birth)
    captured_cgroup = identity['properties']['ControlGroup']
    require(not cgroup_exists(captured_cgroup), 'Captured running A5 cgroup remains')
    record['original_wrapper_birth_unit_and_captured_cgroup_absent'] = True
    record['lifecycle_complete'] = True
    record['status'] = SUCCESS


def release_completed(selection, selection_sha, output, source_sha):
    own, unused = raw_pin(Path(__file__).resolve())
    require(own['sha256'] == source_sha, 'Exact selected frozen adapter SHA required')
    require(Path(selection) == Path(FIXED['selection']['path'])
            and selection_sha == FIXED['selection']['sha256'], 'Only selected current7067 launch allowed')
    selected = checked(FIXED['selection'])
    intent = checked(FIXED['intent']); live = checked(FIXED['live'])
    checked(FIXED['wrapper'], as_json=False)
    terminal_pin, unused = raw_pin(Path(FIXED['intent']['path']).with_name('original-R1-wrapper-terminal.json'))
    terminal = checked(terminal_pin)
    identity = validate_recorded(selected, intent, live, terminal, FIXED['intent'])
    sequence = load('_current7067_A5_release_sequence', FIXED['sequence'])
    require_original_births_absent(identity, live, sequence.birth)
    preparer = load('_current7067_A5_release_review_preparer', FIXED['review_preparer'])
    h, read, pp, packet, case = preparer.selected(Path(FIXED['review_precommit']['path']), 'R1')
    require(pp == FIXED['review_precommit']
            and case['native_job'] == selected['R1']['native_job']
            and case['native_config'] == selected['R1']['config']
            and case['native_controller'] == selected['sources']['controller'],
            'Exact selected original R1 precommit required')
    root = Path(case['native_job']['path']).parent
    closed = preparer.closed_controller(root, '', case['native_config'],
                case['native_controller'], packet['sources'], h, read)
    require(closed['result'] == terminal['controller_result'], 'A5 terminal original controller result differs')
    child = read(h.pin(root/'controller-original-child.json'))
    require(child['pid'] == live['controller']['pid']
            and child['starttime_ticks'] == live['controller']['starttime_ticks']
            and closed['identity'] == live['owner'], 'Original live child/native owner differs')
    job = read(case['native_job'])
    # Use the unchanged independent reader for the potentially large native result.
    native_result_pin = h.pin(Path(job['output'])/'result.json')
    result = read(native_result_pin)
    require(result['original_job'] == case['native_job'] and result['complete'] is True
            and result['errors'] == [] and result['status'] == 'ORIGINAL_DEADLINE32_SEALED_AND_CLOSED'
            and result['attempt'] == 1 and result['no_retry'] is True,
            'Original sealed complete native result required')
    del result
    output = Path(output)
    require(output.is_absolute() and str(output) == str(output.resolve())
            and output.parent == HERE and not output.exists(), 'Exclusive direct-child release output required')
    # This fixed O_EXCL sentinel prevents another output name from becoming a retry.
    attempt = put(HERE/'one-shot-release-attempt.json', dict(source=own, launch_selection=FIXED['selection'],
        output=str(output), original_attempt=1, no_retry=True, created_unix_s=time.time()))
    output.mkdir(mode=0o700)
    record = dict(schema=SCHEMA, status='OWNED_A5_RELEASE_INCOMPLETE_NO_RETRY', source=own,
        launch_selection=FIXED['selection'], release_attempt=attempt, identity=identity,
        original_wrapper_intent=FIXED['intent'], original_wrapper_live=FIXED['live'],
        original_wrapper_terminal=terminal_pin, original_controller_closed=closed,
        original_controller_result=closed['result'], native_result=native_result_pin,
        archives=[], owned_release={}, all_three_archives_succeeded=False, original_wrapper_exit=None,
        original_wrapper_birth_unit_and_captured_cgroup_absent=False, lifecycle_complete=False,
        original_attempt=1, no_retry=True, scientific_payload_retried=False,
        original_Popen_adopted=False, native_relaunched=False, PUB_Main_fleet_touched=False,
        quality_qualified=False, promotion=False, error=None)
    try:
        control = load('_current7067_A5_release_C218', FIXED['lifecycle'])
        archive_release_completed_A5(output, identity, live, control, sequence.birth,
            lambda value: (Path('/sys/fs/cgroup')/value.lstrip('/')).exists(), record)
    except BaseException as error:
        record['error'] = repr(error)
        record['ended_unix_s'] = time.time()
        failure = put(output/'owned-A5-wrapper-release.json', record)
        raise RuntimeError('Original A5 release incomplete; no retry. Receipt: ' + failure['path']) from error
    record['ended_unix_s'] = time.time()
    return put(output/'owned-A5-wrapper-release.json', record)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release', action='store_true')
    parser.add_argument('--launch-selection', type=Path)
    parser.add_argument('--launch-selection-sha256')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--expected-source-sha256')
    args = parser.parse_args()
    if not args.release:
        print('SOURCE ONLY: explicit Root --release required; no observation or action performed.')
        return
    require(all((args.launch_selection, args.launch_selection_sha256, args.output,
                 args.expected_source_sha256)), 'Explicit selected Root release arguments required')
    print(json.dumps(release_completed(args.launch_selection, args.launch_selection_sha256,
        args.output, args.expected_source_sha256), allow_nan=False))


if __name__ == '__main__':
    main()
