#!/usr/bin/env python3
"""UNSELECTED closure of one already observed original same-LR25 914M quality parent.

Default PLAN reads nothing. Root may execute once after all four native legs
and original metadata audits finish. No payload, retry, promotion or freeze
release is implemented. Archive failures remain failures and leave units alone.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import time

ROOT = Path('/home/dave/source/repos/ArcadeAI')
GAME = ROOT/'Robotron'
RUN = GAME/'logs/managed-learning-20261015/run-26'
PREP = RUN/'same-LR25-continuation-original01-root-preparation-20261018'
PACK = GAME/'tools/same_lr25_prospective_continuation_proposal'
UNIT = 'robotron-quality-same-LR25-vs-CE845-original01-20261018.service'
TIMER = UNIT.removesuffix('.service')+'.timer'
PID = 67638
START = 43813785
INVOCATION = 'a85440fb223f498d86dace1e32496911'
TIMER_INVOCATION = '599130c809cd4cef97b774041bfabfb3'
CAMPAIGN = GAME/'logs/managed-learning-20261015/quality-CE845M-vs-same-LR25-first8M-trial01-20261018'
PLAN_SHA = 'b61ef2cbdd1779e6491d1a181f60260e8474aa633a1a3da9c9a117c3744c7324'
BINDING_SHA = 'fde2f3b3a23f407f6473bb75594d326229da22cef15290ef2186c74e2680c232'
AUDITOR_SHA = 'cd1299f033dfc7b93addca5192ff3c95ee48639f4f6193ff34f7885c634ded80'
CONFIG_SHAS = ('c4b46380646df1b4cef07c4720d7cd91c52f89002c61fb7288913b34ff9a3a70',
    '2c09db3030dd577cd7f00d835fbf3cb3a7f1543f14f22e4bb115c1604766246f',
    'f853568cc8e32d1d12ad4112670062acdf87d21801dfc6a32fd9ca43e84fcd90',
    '50ba9726d063590ec41d15a9de907702ade9c7e3a7de2fd57c080e4b55366f80')
OUTPUT = RUN/'same-LR25-914M-quality-native-parent-owned-closure-original01-20261018'
SCHEMA = 'robotron-root-same-LR25-914M-original-parent-closure-case-v1'
ROLES = ('reference', 'candidate', 'reference', 'candidate')
KNOWN = {
    'live': (PREP/'root-original914M-quality-timer-launch-identity-and-live-parent.json', 'd74c5500efc2b57eadecac18e4551cc77ab39f405a7b4508d0f8a5413adafcd6'),
    'plan': (PREP/'actual914M-native-plan-readonly-copy.json', PLAN_SHA),
    'binding': (PREP/'actual914M-quality-binding.json', BINDING_SHA),
    'family': (PACK/'preparation-manifest.json', '89832dd70397ecc8812e18754f45448454fc6ff76aa2c4a846a379bb09d01a0d'),
}
_ATTEMPTED = False


def require(condition, message):
    if not condition:
        raise ValueError(message)


def identity(s):
    return dict(device=s.st_dev, inode=s.st_ino, bytes=s.st_size,
        mtime_ns=s.st_mtime_ns, ctime_ns=s.st_ctime_ns,
        mode=oct(stat.S_IMODE(s.st_mode)), uid=s.st_uid, nlink=s.st_nlink)


def bounded_bytes(path):
    path = Path(path)
    require(path.is_absolute() and path.suffix not in ('.pt', '.pth'), 'Metadata/source only')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as f:
        before = os.fstat(f.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_uid == os.getuid()
            and before.st_nlink == 1 and before.st_size <= 4 << 20, 'Bounded owned regular file required')
        data = f.read((4 << 20)+1)
        require(identity(before) == identity(os.fstat(f.fileno())) == identity(path.lstat()),
            'File changed while reading')
    return data, dict(path=str(path), sha256=hashlib.sha256(data).hexdigest(),
        bytes=len(data), identity=identity(before))


def read_pin(value):
    require(type(value) is dict and set(value) == {'path', 'sha256', 'bytes', 'identity'}, 'Exact metadata PIN required')
    raw, actual = bounded_bytes(value['path'])
    declared = value['identity']
    require(type(declared) is dict and set(declared) in (
        {'device', 'inode', 'mode', 'uid', 'nlink'}, set(actual['identity'])), 'Full8 or genuine minimal5 identity required')
    require(all(actual[k] == value[k] for k in ('path', 'sha256', 'bytes'))
        and all(actual['identity'][k] == v for k, v in declared.items())
        and actual['identity']['mode'] == '0o444', 'Sealed metadata PIN differs')
    return json.loads(raw)


def known(name):
    path, expected = KNOWN[name]
    raw, actual = bounded_bytes(path)
    require(actual['sha256'] == expected and actual['identity']['mode'] == '0o444', 'Known sealed evidence changed: '+name)
    return json.loads(raw), actual


def properties(text):
    return dict(line.split('=', 1) for line in text.splitlines() if '=' in line)


def original_terminal(value):
    require(all(value.get(k) == v for k, v in dict(Id=UNIT, LoadState='loaded', MainPID='0',
        ExecMainPID=str(PID), InvocationID=INVOCATION, NRestarts='0', ExecMainCode='1',
        ExecMainStatus='0', Result='success').items())
        and value.get('SubState') in ('exited', 'dead'), 'Exact original native0 terminal required; leave untouched')


def original_timer(value):
    require(all(value.get(k) == v for k, v in dict(Id=TIMER, LoadState='loaded',
        InvocationID=TIMER_INVOCATION, Unit=UNIT).items()), 'Exact loaded original timer required; no absent/foreign-unit adoption')


def validate_case(case, reader=read_pin):
    require(type(case) is dict and set(case) == {'schema', 'closure_authorized', 'native_status',
        'native_summary', 'audit_releases', 'output_directory'} and case['schema'] == SCHEMA
        and case['closure_authorized'] is True and case['output_directory'] == str(OUTPUT),
        'Explicit exact original-parent closure case required')
    live, live_pin = known('live'); plan, plan_pin = known('plan'); binding, binding_pin = known('binding')
    family, family_pin = known('family')
    require(live['status'] == 'PASS_ORIGINAL_NATIVE_PARENT_OBSERVED_LIVE'
        and live['original'] == dict(pid=PID, starttime_ticks=START, invocation_id=INVOCATION,
            unit=UNIT, observed_live=True)
        and live['timer'] == dict(unit=TIMER, invocation_id=TIMER_INVOCATION)
        and live['native_parent_restart_count'] == 0 and live['retry'] is False,
        'Genuine prior observed-live ownership required')
    original_terminal_live = properties(live['service_show']['stdout'])
    require(live['service_show']['returncode'] == live['timer_show']['returncode'] == live['timer_cat']['returncode'] == 0
        and live['service_show']['argv'] == ['systemctl', '--user', 'show', UNIT, '--all']
        and live['timer_show']['argv'] == ['systemctl', '--user', 'show', TIMER, '--all']
        and live['timer_cat']['argv'] == ['systemctl', '--user', 'cat', TIMER]
        and original_terminal_live.get('Id') == UNIT and original_terminal_live.get('SubState') == 'running'
        and original_terminal_live.get('MainPID') == str(PID)
        and original_terminal_live.get('InvocationID') == INVOCATION
        and original_terminal_live.get('NRestarts') == '0', 'Saved live service evidence differs')
    original_timer(properties(live['timer_show']['stdout']))
    require(plan['output_directory'] == str(CAMPAIGN)
        and binding['campaign']['output_directory'] == str(CAMPAIGN)
        and binding['campaign']['unit']+'.service' == UNIT
        and binding['recipe'] == dict(priority_metric='ce', batch_size=4096,
            learning_control_lr_scale=.25, scheduled_lr=1.25e-5, max_samples_per_frame=8),
        'Exact original native plan/binding/held recipe required')
    status, summary = reader(case['native_status']), reader(case['native_summary'])
    require(status['state'] == 'finished' and status['plan_sha256'] == summary['plan_sha256'] == PLAN_SHA
        and status['plan_path'] == summary['plan_path'] == str(CAMPAIGN/'plan.json')
        and status['outcome'] == summary['outcome'] in ('qualified_improvement', 'not_improved')
        and summary['stop_signal'] is None, 'All-four native completion required; no gate result is recomputed here')
    require(len(status['legs']) == len(summary['legs']) == 4, 'Exactly four original native legs required')
    for index, role in enumerate(ROLES, 1):
        row, evidence, spec = status['legs'][index-1], summary['legs'][index-1], plan['legs'][index-1]
        require(row['index'] == evidence['index'] == spec['index'] == index
            and row['role'] == evidence['role'] == spec['role'] == role
            and row['state'] == 'finished' and type(row['returncode']) is int and row['returncode'] == 0
            and type(evidence['returncode']) is int and evidence['returncode'] == 0 and evidence['valid'] is True
            and type(row['pid']) is int and row['pid'] > 0 and row['ended_unix_s'] >= row['started_unix_s']
            and row['receipt_path'] == evidence['receipt_path'] == spec['receipt_path']
            and row['console_log'] == evidence['console_log'] == spec['console_log'],
            'Original native leg incomplete, invalid or mismatched: '+str(index))
    require(type(case['audit_releases']) is list and len(case['audit_releases']) == 4, 'Four original audit closures required')
    for index, release_pin in enumerate(case['audit_releases'], 1):
        released = reader(release_pin)
        expected_unit = 'robotron-same-LR25-914M-quality-leg%02d-audit-original01-20261018.service' % index
        expected_out = RUN/('same-LR25-914M-quality-leg%02d-audit-original01-root-execution-20261018' % index)
        require(release_pin['path'] == str(expected_out/'root-original-result-and-owned-release.json')
            and released['schema'] == 'robotron-root-audit-original-result-and-GC-aware-owned-release-v1'
            and released['original']['unit'] == expected_unit and released['original']['observed_live'] is True
            and released['original_exec_code'] == 1 and released['original_exit'] == 0
            and released['original_result'] == 'success' and released['audit_success'] is True
            and released['lifecycle_complete'] is True and released['unit_released'] is True
            and released['original_archived_before_release'] is True
            and released['all_six_original_archive_commands_succeeded'] is True
            and released['error'] is None and released['payload_retried'] is False
            and released['status'] == 'ORIGINAL_AUDIT_EXIT0_ARCHIVED_AND_RELEASED'
            and [x['unit'] for x in released['owned_release']] == [expected_unit.removesuffix('.service')+'.timer', expected_unit]
            and all(x['confirmed_absent'] is True for x in released['owned_release']),
            'Exact completed original audit0 required: '+str(index))
        archive = reader(released['timer_launch_archive']); intent = reader(archive['launch_intent'])
        config_path = PREP/('same-LR25-914M-quality-leg%02d-audit-original01-config.json' % index)
        _, config_pin = bounded_bytes(config_path); config = reader(config_pin)
        require(config_pin['sha256'] == CONFIG_SHAS[index-1], 'Original sealed audit config changed')
        require(intent['unit'] == config['unit'] == expected_unit and intent['output'] == config['output'] == str(expected_out)
            and intent['argv'] == config['argv'] and intent['pins'] == config['pins']
            and intent['properties'] == config['properties'] and intent['no_retry'] is True
            and intent['original_attempt'] == 1, 'Original audit command/config differs')
        argv = config['argv']
        require(argv[:5] == ['/usr/bin/python3.12', '-I', '-B', str(PACK/'audit_completed_leg.py'), '--execute']
            and argv[argv.index('--leg')+1] == str(index)
            and argv[argv.index('--plan-sha256')+1] == PLAN_SHA
            and argv[argv.index('--binding-job-sha256')+1] == BINDING_SHA
            and argv[argv.index('--source-sha256')+1] == AUDITOR_SHA,
            'Original selected audit family/leg/plan differs')
    return dict(live=live_pin, native_plan=plan_pin, binding=binding_pin, family=family_pin,
        case=case, baseline=reader(binding['runtime_baseline']),
        original_cgroup=original_terminal_live['ControlGroup'])


def held_sources(context):
    baseline = context['baseline']
    require(len(baseline['source_hashes']) == 62 and len(baseline['control_hashes']) == 2
        and len(baseline['unit_files']) == 3, 'Exact frozen62+2+3 held inventory required')
    for path, expected in {**baseline['source_hashes'], **baseline['control_hashes'], **baseline['unit_files']}.items():
        require(bounded_bytes(path)[1]['sha256'] == expected, 'Held producer source/control/unit changed: '+path)
    control = json.loads(bounded_bytes(GAME/'models_dqn/learning_control.json')[0])
    binding = read_pin(context['binding'])
    require(control['lr_scale'] == .25 and control['experiment'] == binding['experiment'], 'Held LR25 control changed')


def empty_original_cgroup(context):
    group = context['original_cgroup']
    require(group == '/user.slice/user-1001.slice/user@1001.service/app.slice/'+UNIT,
        'Only the original observed native parent cgroup may be checked')
    try:
        contents = (Path('/sys/fs/cgroup')/group.lstrip('/')/'cgroup.procs').read_text()
    except FileNotFoundError:
        return 'removed'
    require(not contents.strip(), 'Original quality cgroup still has processes; no stop authorized')
    return 'empty'


def sync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def pin(path):
    p=Path(path); b=p.read_bytes(); s=p.stat()
    return dict(path=str(p),sha256=hashlib.sha256(b).hexdigest(),bytes=len(b),identity=dict(device=s.st_dev,inode=s.st_ino,mode=oct(s.st_mode&0o777),uid=s.st_uid,nlink=s.st_nlink))


def publish(path,value):
    p=Path(path)
    with p.open('x') as f:
        json.dump(value,f,indent=2,allow_nan=False); f.write('\n');f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
    return pin(p)


def command(out,label,argv):
    started=time.time();failure=None
    try:
        r=subprocess.run(argv,capture_output=True,timeout=40)
        stdout,stderr,exit_code=r.stdout,r.stderr,r.returncode
    except subprocess.TimeoutExpired as error:
        stdout,stderr,exit_code=error.stdout or b'',error.stderr or b'',None
        failure='TimeoutExpired: command completion unknown; no success inferred'
    files={}
    for kind,data in [('stdout',stdout),('stderr',stderr)]:
        p=out/(label+'-'+kind+'.txt')
        with p.open('xb') as f:f.write(data);f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
        files[kind]=pin(p)
    receipt=dict(argv=argv,exit=exit_code,unix_s=time.time(),started_unix_s=started,
                 timed_out=failure is not None,error=failure,**files)
    publish(out/(label+'-command.json'),receipt)
    return receipt


def fields(record):
    require(record['exit']==0 and not record['timed_out'],'Show command did not complete successfully')
    return dict(x.split('=',1) for x in Path(record['stdout']['path']).read_text().splitlines() if '=' in x)


def close(context):
    global _ATTEMPTED
    require(not _ATTEMPTED, 'One closure attempt only; no cleanup retry')
    _ATTEMPTED = True
    require(not OUTPUT.exists(), 'Fresh fixed closure output required; no rerun')
    OUTPUT.mkdir(mode=0o700)
    result = dict(schema='robotron-root-same-LR25-914M-original-native-parent-owned-closure-v1',
        status='INCOMPLETE_NO_RELEASE_AUTHORITY', original=dict(unit=UNIT, pid=PID, starttime_ticks=START,
            invocation_id=INVOCATION, timer=TIMER, timer_invocation_id=TIMER_INVOCATION, observed_live=True),
        original_exec_code=None, original_exit=None, original_result=None,
        selected_source=context.get('source_pin'), case_file=context.get('case_pin'),
        input_evidence={k:context[k] for k in ('live', 'native_plan', 'binding', 'family')},
        case=context['case'], full_original_archives=[], owned_release=[],
        all_six_original_archive_commands_succeeded=False, original_archived_before_release=False,
        unit_released=False, lifecycle_complete=False, error=None, closure_attempts=1,
        payload_launched=False, payload_retried=False, quality_promotion=False,
        source_freeze_released=False, root_review_and_disposition_required=True)
    try:
        held_sources(context)
        before = command(OUTPUT, 'before-service-show', ['systemctl', '--user', 'show', UNIT, '--all'])
        original_terminal(fields(before))
        result.update(original_exec_code=1, original_exit=0, original_result='success')
        result['original_cgroup_before_archives'] = empty_original_cgroup(context)
        timer_before = command(OUTPUT, 'before-timer-show', ['systemctl', '--user', 'show', TIMER, '--all'])
        original_timer(fields(timer_before))
        for kind, unit, invocation in [('service', UNIT, INVOCATION), ('timer', TIMER, TIMER_INVOCATION)]:
            for action in ('show', 'cat', 'journal'):
                argv = ['journalctl', '--user', '_SYSTEMD_INVOCATION_ID='+invocation, '--no-pager', '-o', 'short-iso-precise'] if action == 'journal' else ['systemctl', '--user', action, unit] + (['--all'] if action == 'show' else [])
                record = command(OUTPUT, 'original-'+kind+'-'+action, argv)
                result['full_original_archives'].append(dict(kind=kind, action=action, **record))
        archives = result['full_original_archives']
        result['all_six_original_archive_commands_succeeded'] = len(archives) == 6 and all(x['exit'] == 0 and not x['timed_out'] for x in archives)
        result['original_archived_before_release'] = True
        publish(OUTPUT/'root-original-terminal-archive.json', result)
        sync_directory(OUTPUT)
        require(result['all_six_original_archive_commands_succeeded'], 'All six raw archive commands must succeed; no stop authorized')
        original_terminal(fields(archives[0])); original_timer(fields(archives[3]))
        held_sources(context)
        result['original_cgroup_before_release'] = empty_original_cgroup(context)
        for kind, unit in [('timer', TIMER), ('service', UNIT)]:
            item = dict(unit=unit, before=None, stop=None, final=None, confirmed_absent=False)
            result['owned_release'].append(item)
            item['before'] = command(OUTPUT, 'release-'+kind+'-before-show', ['systemctl', '--user', 'show', unit, '--all'])
            value = fields(item['before'])
            original_timer(value) if kind == 'timer' else original_terminal(value)
            empty_original_cgroup(context)
            item['stop'] = command(OUTPUT, 'release-'+kind+'-stop', ['systemctl', '--user', 'stop', unit])
            # Even a nonzero/timeout stop gets a saved exact after-show. Its raw
            # exit is never rewritten, no reset/second stop follows a refusal.
            item['final'] = command(OUTPUT, 'release-'+kind+'-after-show', ['systemctl', '--user', 'show', unit, '--all'])
            value = fields(item['final'])
            require(item['stop']['exit'] == 0 and not item['stop']['timed_out'], 'Owned stop did not complete0; preserve and stop cleanup')
            require(value.get('Id') == unit and value.get('LoadState') == 'not-found', 'Exact owned unit not confirmed absent')
            item['confirmed_absent'] = True
            sync_directory(OUTPUT)
        require(all(x['confirmed_absent'] for x in result['owned_release']), 'Both exact owned units must be absent')
        result.update(status='ORIGINAL_NATIVE0_ARCHIVED_AND_OWNED_RELEASE_COMPLETE', unit_released=True, lifecycle_complete=True)
    except Exception as error:
        result.update(status='ORIGINAL_OUTCOME_PRESERVED_CLOSURE_INCOMPLETE', error=repr(error))
    result['ended_unix_s'] = time.time()
    saved = publish(OUTPUT/'root-original-native-parent-result-and-owned-release.json', result)
    sync_directory(OUTPUT)
    print(json.dumps(dict(status=result['status'], receipt=saved, native_exit=result['original_exit'],
        unit_released=result['unit_released'], source_freeze_released=False, quality_promotion=False)), flush=True)
    return 0 if result['lifecycle_complete'] else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true'); parser.add_argument('--case', type=Path)
    parser.add_argument('--expected-case-sha256'); parser.add_argument('--expected-source-sha256')
    args = parser.parse_args(argv)
    if not args.execute:
        print('PLAN_ONLY: no file reads, imports, runtime queries, archives, unit or payload actions')
        return 0
    require(args.case and args.expected_case_sha256 and args.expected_source_sha256, 'Explicit root case and source digests required')
    _, source_pin = bounded_bytes(Path(__file__).resolve())
    require(source_pin['sha256'] == args.expected_source_sha256 and source_pin['identity']['mode'] == '0o444', 'Selected closure source differs')
    raw, case_pin = bounded_bytes(args.case)
    require(case_pin['sha256'] == args.expected_case_sha256 and case_pin['identity']['mode'] == '0o444', 'Sealed root case differs')
    context = validate_case(json.loads(raw)); context.update(case_pin=case_pin, source_pin=source_pin)
    return close(context)


if __name__ == '__main__':
    raise SystemExit(main())
