#!/usr/bin/env python3
"""UNSELECTED closure of the already root-observed original continuous-guard947M parent.

Default PLAN reads nothing. Root may execute once after all four native legs
and original metadata audits finish. No payload, retry, promotion or freeze
release is implemented. Archive failures remain failures and leave units alone.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import subprocess
import sys
import time

ROOT = Path('/home/dave/source/repos/ArcadeAI')
GAME = ROOT/'Robotron'
RUN = GAME/'logs/managed-learning-20261015/run-26'
PREP = RUN/'continuous-guard-same-LR25-continuation-original01-root-preparation-20261018'
PACK = GAME/'tools/continuous_guard_same_lr25_continuation_proposal'
UNIT = 'robotron-quality-continuous-guard-same-LR25-vs-CE845-original01-20261018.service'
TIMER = UNIT.removesuffix('.service')+'.timer'
PID = 359834
START = 44664226
INVOCATION = 'c646fc24d96143979e96b2c40a656ec7'
TIMER_INVOCATION = 'f912ce046cf74b35b1be87f20635fbd7'
CAMPAIGN = GAME/'logs/managed-learning-20261015/quality-CE845M-vs-continuous-guard-same-LR25-first8M-trial01-20261018'
PLAN_SHA = '6517ec4eff1d31afd86aa5721c433b35d4c34f1244653e03919ab271aa697f88'
BINDING_SHA = 'f9cb5bd19ffca1caa3c80216cecb4e5eb8370d4e55fc31cf8327cffc0d28dd06'
AUDITOR_SHA = '61b299b327fe6156571646aa809e38563f7bf71de980a48b36272c9f555551d2'
CONTROL = GAME/'tools/quality_audit_control_gc_repair_proposal/control_audit_reviewed3.py'
CONTROL_SHA = 'b5a50047e1a2981a41732c756bf908c6b9b935c58d1d0503c0df494e6f863aee'
CONFIG_SHAS = ('cc6c181b38eaae94755584bdb4a2fff725184069ab8a5f649c3005ada3060dbc',
    'a4e03121b1e71706d3dd89663a00703312dfa242c88b7310b83d9d87d50509ba',
    '2c99d6b28c1a3fb87a184f307db9fb7d159f9901de3977ecc1f011814beacf6c',
    '98cc3a154215eb42526201ea26a9cc5801d985feb84eff1675a98873723b4192')
OUTPUT = RUN/'continuous-guard-same-LR25-947M-quality-native-parent-owned-closure-original01-20261018'
SCHEMA = 'robotron-root-continuous-guard-947M-original-parent-closure-case-v1'
HEALTH_SCHEMA = 'robotron-root-continuous-guard-947M-fresh-terminal-health-v1'
ANCHOR = ('main_owner','fleet_owner','inference_worker','actors','source_hashes','control_hashes','unit_files','environment_sha256')
ROLES = ('reference', 'candidate', 'reference', 'candidate')
KNOWN = {
    'live': (PREP/'root-original947M-native-quality-launch-and-main-health-PASS.json', '700ff17618eb740d8af7c8b6c90b8210d1958753494cf9e7a2c1a0ad863a0eef'),
    'plan': (PREP/'actual947M-native-plan-readonly-copy.json', PLAN_SHA),
    'binding': (PREP/'actual947M-quality-binding.json', BINDING_SHA),
    'family': (PACK/'preparation-reviewed3-manifest.json', '55933898484a2593f34adaa6943086d7f49667ebe9b782f99125d2963c7ecacf'),
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
        'native_summary', 'audit_releases', 'fresh_terminal_health', 'output_directory'} and case['schema'] == SCHEMA
        and case['closure_authorized'] is True and case['output_directory'] == str(OUTPUT),
        'Explicit exact original-parent closure case required')
    live, live_pin = known('live'); plan, plan_pin = known('plan'); binding, binding_pin = known('binding')
    family, family_pin = known('family')
    require(live['schema'] == 'robotron-root-original947M-native-quality-launch-and-health-v1'
        and live['status'] == 'PASS_ORIGINAL_QUALITY_PARENT_RUNNING_MAIN192_UNCHANGED'
        and live['original'] == dict(pid=PID, starttime_ticks=START, invocation_id=INVOCATION,
            unit=UNIT, observed_live=True)
        and live['timer_invocation_id'] == TIMER_INVOCATION and live['native_plan'] == plan_pin
        and live['retry'] is False and live['qualification'] is False and live['promotion'] is False
        and live['learning_changes'] is False and live['exact_original192_verified'] is True
        and live['held62_source_and_two_controls_verified'] is True,
        'Genuine prior observed-live947M ownership and unchanged main192 required')
    original_terminal_live = properties(live['service_show']['stdout'])
    require(live['service_show']['returncode'] == live['timer_show']['returncode'] == 0
        and live['service_show']['argv'] == ['systemctl', '--user', 'show', UNIT, '--all']
        and live['timer_show']['argv'] == ['systemctl', '--user', 'show', TIMER, '--all']
        and original_terminal_live.get('Id') == UNIT and original_terminal_live.get('SubState') == 'running'
        and original_terminal_live.get('MainPID') == str(PID)
        and original_terminal_live.get('InvocationID') == INVOCATION
        and original_terminal_live.get('NRestarts') == '0', 'Saved live service evidence differs')
    original_timer(properties(live['timer_show']['stdout']))
    _, audit_control = bounded_bytes(CONTROL)
    require(audit_control['sha256'] == CONTROL_SHA and audit_control['identity']['mode'] == '0o444',
        'Selected existing B5 audit controller differs')
    require(binding['candidate']['sha256'] == '402827c43c2ed5a81bffbaa4bdc017c087004fbd94350e1fcc2b048f65b3e839'
        and binding['reference']['sha256'] == 'fda8dcdf80a794b2715843dc892890296363c7586c60bae435a0925e32997ecd'
        and plan['checkpoints']['candidate']['sha256'] == binding['candidate']['sha256']
        and plan['checkpoints']['reference']['sha256'] == binding['reference']['sha256'],
        'Only actual947M402827 versus protected845fda8 metadata is eligible')
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
        expected_unit = 'robotron-continuous-guard-same-LR25-947M-leg%02d-audit-original01-20261018.service' % index
        expected_out = RUN/('continuous-guard-same-LR25-947M-leg%02d-audit-original01-root-execution-20261018' % index)
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
        config_path = PREP/('actual947M-original-leg%02d-audit-control-config.json' % index)
        _, config_pin = bounded_bytes(config_path); config = reader(config_pin)
        require(config_pin['sha256'] == CONFIG_SHAS[index-1], 'Original sealed audit config changed')
        require(intent['unit'] == config['unit'] == expected_unit and intent['output'] == config['output'] == str(expected_out)
            and intent['argv'] == config['argv'] and intent['pins'] == config['pins']
            and intent['properties'] == config['properties'] and intent['no_retry'] is True
            and intent['original_attempt'] == 1, 'Original audit command/config differs')
        argv = config['argv']
        require(argv[:5] == ['/usr/bin/python3.12', '-I', '-B', str(PACK/'audit_completed_leg_reviewed2.py'), '--execute']
            and argv[argv.index('--leg')+1] == str(index)
            and argv[argv.index('--plan-sha256')+1] == PLAN_SHA
            and argv[argv.index('--binding-job-sha256')+1] == BINDING_SHA
            and argv[argv.index('--source-sha256')+1] == AUDITOR_SHA,
            'Original selected audit family/leg/plan differs')
    baseline = reader(binding['runtime_baseline'])
    require(baseline['main_owner'] == live['main_owner'] and baseline['fleet_owner'] == live['fleet_owner']
        and len(baseline['actors']) == 192, 'Actual binding baseline/main192 lineage differs')
    context = dict(live=live_pin, native_plan=plan_pin, binding=binding_pin, family=family_pin,
        case=case, baseline=baseline, experiment=binding['experiment'],
        original_cgroup=original_terminal_live['ControlGroup'])
    fresh_terminal_health(context, reader=reader)
    return context


def full8_metadata_pin(value):
    require(type(value) is dict and set(value) == {'path','sha256','bytes','identity'}
        and type(value['path']) is str and Path(value['path']).is_absolute()
        and '..' not in Path(value['path']).parts and Path(value['path']).suffix == '.json'
        and type(value['sha256']) is str and len(value['sha256']) == 64
        and all(c in '0123456789abcdef' for c in value['sha256'])
        and type(value['bytes']) is int and value['bytes'] > 0, 'Typed FULL8 closed JSON PIN required')
    fields = {'device','inode','bytes','mtime_ns','ctime_ns','mode','uid','nlink'}
    require(type(value['identity']) is dict and set(value['identity']) == fields,
        'Fresh health must retain all eight real identity fields')
    row = value['identity']
    require(all(type(row[k]) is int for k in fields-{'mode'})
        and row['device'] >= 0 and row['inode'] > 0 and row['bytes'] == value['bytes']
        and row['mtime_ns'] > 0 and row['ctime_ns'] > 0 and row['uid'] == os.getuid()
        and row['nlink'] == 1 and type(row['mode']) is str and row['mode'] == '0o444',
        'Readonly owned FULL8 identity types/values differ')
    return value


def fresh_terminal_health(context, *, reader=read_pin, now=None):
    # This authenticates a ROOT-observed, sealed record. No API/GPU/proc query,
    # producer action or claim of independent current liveness occurs here.
    pin_value = full8_metadata_pin(context['case']['fresh_terminal_health'])
    value = reader(pin_value)
    require(type(value) is dict and set(value) == {'schema','status','observed_unix_s',*ANCHOR,
        'main_api','quality_terminal','resources'} and value['schema'] == HEALTH_SCHEMA
        and value['status'] == 'PASS', 'Exact fresh-terminal-health schema/status required')
    observed = value['observed_unix_s']; checked = time.time() if now is None else now
    require(type(observed) in (int,float) and type(checked) in (int,float)
        and math.isfinite(observed) and math.isfinite(checked) and observed > 0 and checked > 0
        and 0 <= checked-observed < 180,
        'Root terminal health must be younger than180s and cannot be future-dated')
    baseline = context['baseline']
    require(all(value[k] == baseline[k] for k in ANCHOR if k != 'actors'),
        'Original main/fleet/inference/environment/frozen source-control-unit identities changed')
    worker = value['inference_worker']
    require(type(worker) is dict and set(worker) == {'tid','starttime_ticks','mask'}
        and type(worker['tid']) is int and worker['tid'] > 0
        and type(worker['starttime_ticks']) is int and worker['starttime_ticks'] > 0
        and type(worker['mask']) is list and bool(worker['mask'])
        and all(type(cpu) is int and cpu >= 0 for cpu in worker['mask'])
        and len(set(worker['mask'])) == len(worker['mask']), 'Typed original inference worker required')
    require(len(value['source_hashes']) == 62 and len(value['control_hashes']) == 2
        and len(value['unit_files']) == 3, 'Exact held62+2+3 inventory required')
    censuses = []
    for actors in (value['actors'], baseline['actors']):
        require(type(actors) is list and len(actors) == 192, 'Every original actor required')
        census = set()
        for row in actors:
            require(type(row) is dict and set(row) == {'slot','pid','starttime_ticks','mask'}
                and all(type(row[k]) is int for k in ('slot','pid','starttime_ticks'))
                and 0 <= row['slot'] < 192 and row['pid'] > 0 and row['starttime_ticks'] > 0
                and type(row['mask']) is list and bool(row['mask'])
                and all(type(cpu) is int and cpu >= 0 for cpu in row['mask'])
                and len(set(row['mask'])) == len(row['mask']), 'Complete typed actor slot/PID/start/mask required')
            census.add((row['slot'],row['pid'],row['starttime_ticks'],tuple(sorted(row['mask']))))
        require(len(census) == 192 and {r[0] for r in census} == set(range(192))
            and len({r[1] for r in census}) == 192, 'Unique192 original actor identities required')
        censuses.append(census)
    require(censuses[0] == censuses[1], 'Original192 actor identity/mask set changed')
    expected_terminal = dict(unit=UNIT,pid=PID,starttime_ticks=START,invocation_id=INVOCATION,
        timer=TIMER,timer_invocation_id=TIMER_INVOCATION,exec_main_code=1,exit_status=0,
        result='success',n_restarts=0,main_pid=0,cgroup=context['original_cgroup'])
    terminal = value['quality_terminal']
    require(type(terminal) is dict and set(terminal) == set(expected_terminal)|{'cgroup_state'}
        and all(type(terminal[k]) is type(v) and terminal[k] == v for k,v in expected_terminal.items())
        and terminal['cgroup_state'] in ('empty','removed'), 'Fresh root record must identify this terminal native0 only')
    resource_keys = {'GPU0_empty','GPU1_main_only','port9999_clear','no_pending_save','lease_free'}
    require(type(value['resources']) is dict and set(value['resources']) == resource_keys
        and all(value['resources'][k] is True for k in resource_keys), 'Root private-resource release/idle proof incomplete')
    api = reader(full8_metadata_pin(value['main_api']))
    require(type(api['client_count']) is int and api['client_count'] == 192
        and api['training_enabled'] is True and api['measurement_active'] is False
        and api['managed_experiment'] == context['experiment'] and api['lr'] == 1.25e-5
        and api['pipeline_read_error'] == api['bank_persistence_read_error'] == '',
        'Fresh root API must retain active same-.25 main192 without pipeline/bank errors')
    require(type(api['ts']) in (int,float) and math.isfinite(api['ts']) and 0 <= observed-api['ts'] <= 5
        and type(api['pipeline_snapshot_age_s']) in (int,float) and math.isfinite(api['pipeline_snapshot_age_s'])
        and 0 <= api['pipeline_snapshot_age_s'] <= 5, 'Fresh root API/pipeline sample stale or future-dated')
    old_api = reader(baseline['actual_API']); pipe = api['host_pipeline']; old_pipe = old_api['host_pipeline']
    require(pipe['schema'] == 'robotron-host-pipeline-v1' and pipe['available'] is True
        and type(pipe['generation']) is int and pipe['generation'] >= 0
        and pipe['generation'] == old_pipe['generation']
        and all(type(pipe[k]['errors']) is int and pipe[k]['errors'] == 0
            for k in ('inference','actor_refresh','target_refresh')),
        'Host pipeline partial, reset or reports errors')
    require(all(type(api[k]) is int and api[k] >= old_api[k] for k in
        ('training_steps','optimized_samples','learner_frame_count','frame_count')),
        'Original main learning clocks regressed')
    identities = ('process_id','instance_monotonic_ns','epoch','epoch_reason')
    for name in ('optimizer','replay'):
        row = pipe['learning_exposure'][name]; old = old_pipe['learning_exposure'][name]
        require(row['enabled'] is True and all(row[k] == old[k] for k in identities)
            and type(row['process_id']) is int and row['process_id'] == baseline['main_owner']['pid']
            and type(row['instance_monotonic_ns']) is int and row['instance_monotonic_ns'] > 0
            and type(row['epoch']) is int and row['epoch'] == 1,
            'Original replay/optimizer identity or epoch changed')
        if name == 'optimizer':
            require(row['schema'] == 'robotron-optimizer-exposure-v1', 'Optimizer schema differs')
            keys = ('attempts_started','outcomes_recorded','applied','amp_skipped','unavailable')
            for group in ('total','since_epoch'):
                c = row[group]
                require(all(type(c[k]) is int and c[k] >= old[group][k] for k in keys)
                    and c['outcomes_recorded'] == c['applied']+c['amp_skipped']+c['unavailable']
                    and c['unavailable'] == 0, 'Optimizer outcome counters/partition unavailable or regressed')
            require(all(row['since_epoch'][k] <= row['total'][k] for k in keys),
                'Optimizer epoch counters exceed process totals')
            pending = row['unclassified_started_total']
            require(type(pending) is int and pending in (0,1)
                and row['total']['attempts_started']-row['total']['outcomes_recorded'] == pending
                and type(row['available']) is bool and row['available'] is
                (row['since_epoch']['outcomes_recorded'] > 0 and row['since_epoch']['unavailable'] == 0 and pending == 0),
                'Optimizer available flag must preserve the normal one-attempt-in-flight case')
        else:
            keys = ('dqn','epsilon','expert','eval','unattributed')
            c = row['accepted_by_source_total']
            require(row['schema'] == 'robotron-replay-insert-exposure-v1' and row['available'] is True
                and set(c) == set(keys) and all(type(c[k]) is int and c[k] >= old['accepted_by_source_total'][k] for k in keys)
                and type(row['accepted_total']) is int and row['accepted_total'] == sum(c.values())
                and type(row['accepted_learner_total']) is int and row['accepted_learner_total'] == c['dqn']+c['epsilon'],
                'Replay counter/source partition unavailable or regressed')
    return dict(pin=pin_value,observed_unix_s=observed,checked_unix_s=checked,age_s=checked-observed,
        scope='Authenticated historical root health; no new API/GPU/proc query by this controller')


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
    result = dict(schema='robotron-root-continuous-guard-947M-original-native-parent-owned-closure-v1',
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
        result['fresh_terminal_health_at_start'] = fresh_terminal_health(context)
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
        result['fresh_terminal_health_before_release'] = fresh_terminal_health(context)
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
