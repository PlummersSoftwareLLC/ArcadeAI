"""Read-only main health for declared one-game training rounds.

An ordinary client disappearance is invalid unless its durable score explains
the retirement. Actor replacement within a round is rejected. The only accepted
new fleet is the next complete round after a verified192-score barrier. This
module does not change the unchanged private evaluator or qualify any cohort.
"""
import hashlib
import csv
import importlib.util
import json
import mmap
import stat
import os
from pathlib import Path
import subprocess
import statistics
import time
import urllib.request

ROOT = Path('/home/dave/source/repos/ArcadeAI/Robotron')
LINUX = ROOT / 'tools/quality_capacity_proposal/supervised_main_fleet_v2.py'
LINUX_SHA = '1f41d360fa23632cb26d6dee33d3c822bec7f9cf79fdbb75e47f3418059ca5f0'
STATIC = ('parent_pid', 'cgroup', 'command', 'environment', 'affinity', 'uids', 'executable')


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def linux():
    require(hashlib.sha256(LINUX.read_bytes()).hexdigest() == LINUX_SHA, 'Linux reader changed')
    spec = importlib.util.spec_from_file_location('_round_health_linux', LINUX)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def birth(process):
    return process['pid'], process['starttime_ticks']


def process_record(pid, reader):
    result = reader.process_record(pid)
    # Also bind DQN and CUDA recipe settings; omit unrelated environment data.
    environment = Path('/proc', str(pid), 'environ').read_bytes()
    for item in environment.split(b'\0'):
        if b'=' not in item:
            continue
        key, value = item.split(b'=', 1)
        name = key.decode()
        if name.startswith('DQN_') or name in ('CUDA_VISIBLE_DEVICES', 'CUDA_DEVICE_ORDER'):
            result['environment'][name] = value.decode()
    stat = reader.process_stat(pid)
    require(stat is not None and stat['starttime_ticks'] == result['starttime_ticks'], 'Process raced capture')
    result['state'] = stat['state']
    return result


def unit_record(name, reader):
    raw = subprocess.check_output(['systemctl', '--user', 'show', name], text=True, timeout=5)
    values = dict(line.split('=', 1) for line in raw.splitlines() if '=' in line)
    require(values['ActiveState'] == 'active' and values['SubState'] == 'running'
            and values['NRestarts'] == '0', 'Main unit stopped or restarted')
    process = process_record(int(values['MainPID']), reader)
    require(process['cgroup'] == values['ControlGroup'], 'Main unit cgroup differs')
    return dict(unit=name, invocation=values['InvocationID'], process=process, raw_show=raw)


def read(path):
    return json.loads(path.read_bytes())


def file_identity(path):
    return stat_identity(path.stat())


def stat_identity(info):
    return dict(device=info.st_dev, inode=info.st_ino, bytes=info.st_size,
                mtime_ns=info.st_mtime_ns, ctime_ns=info.st_ctime_ns,
                mode=oct(info.st_mode & 0o777), uid=info.st_uid, nlink=info.st_nlink)


def check_inputs(case, full=False):
    for path, value in case['inputs'].items():
        actual = Path(path)
        require(str(actual.resolve(strict=True)) == path and not actual.is_symlink()
                and file_identity(actual) == value['identity'], 'Held input identity changed: ' + path)
        if full:
            with actual.open('rb') as stream:
                info = os.fstat(stream.fileno())
                require(stat.S_ISREG(info.st_mode) and stat_identity(info) == value['identity'],
                        'Held source must remain the selected regular file: ' + path)
                if info.st_size:
                    with mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as view:
                        digest = hashlib.sha256(view).hexdigest()
                else:
                    digest = hashlib.sha256(b'').hexdigest()
                require(digest == value['sha256'], 'Held input bytes changed: ' + path)
                require(not actual.is_symlink() and file_identity(actual) == value['identity']
                        and stat_identity(os.fstat(stream.fileno())) == value['identity'],
                        'Held input changed during full hash: ' + path)


def completed_round(directory, journal):
    results, identities = {}, {}
    started = read(directory / 'started.json')
    for path in sorted(directory.glob('slot-*-result.json')):
        outer = read(path)
        row = outer['result']
        slot = str(row['client_slot'])
        require(outer['round'] == started['round'] and row['start_unix_s'] >= started['started_unix_s']
                and slot not in results and row['complete'] is True and row['eligible'] is True
                and row['known_start'] is True and row['boundary_reason'] in ('score_reset', 'zero_score_restart')
                and type(row['score']) is int and row['score'] >= 0, 'Invalid/duplicate main completion')
        require(journal.get(row['journal_game_id']) == row, 'Score receipt lacks matching committed journal row')
        results[slot] = outer
        identities[slot] = hashlib.sha256(path.read_bytes()).hexdigest()
    return results, identities


def collect(case, previous=None):
    observer_previous = previous
    module = launchers()
    evidence = dict(stage='starting', started_monotonic_s=time.monotonic())
    try:
        reader = linux()
        started = time.monotonic()
        root = Path(case['round_root'])
        raw_status = (root/'status.json').read_bytes()
        status = json.loads(raw_status)
        directory = root/('round-%06d'%status['round'])
        number = status['round'] + int((root/('round-%06d'%(status['round']+1))/'started.json').exists())
        owners = {role:unit_record(case['units'][role],reader) for role in ['trainer','fleet']}
        evidence.update(stage='child-capture',raw_status=raw_status.decode(),owners=owners,effective_round=number)
        fleet = owners['fleet']['process']
        children = Path('/proc',str(fleet['pid']),'task',str(fleet['pid']),'children').read_text().split()
        evidence['original_children'] = children
        actors,census = module.capture_children(case,fleet,lambda pid:process_record(pid,reader),children,number)
        evidence.update(stage='round-and-API',launcher_census=census)
        wire = Path(case['completion_journal']).read_bytes()
        journal,journal_lines = {},{}
        for line in wire.split(b'\n')[:-1]:
            if not line:continue
            row=json.loads(line)
            journal[row['journal_game_id']]=row
            journal_lines[row['journal_game_id']]=line.decode('utf-8')+'\n'
        results,receipts = completed_round(directory,journal)
        with urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=5) as response:
            api_wire=response.read(1_048_577)
        require(len(api_wire)<=1_048_576,'Raw API exceeds bound')
        api=json.loads(api_wire)
        evidence['raw_API_wire']=api_wire.decode('utf-8')
        require(stable_round_status(json.loads((root/'status.json').read_bytes()))==stable_round_status(status),
                'Round publication raced capture')
        require(time.monotonic()-started<=5,'Main census exceeded5s')
        sample=dict(schema='robotron-round-main-health-snapshot-v1',unix_s=time.time(),monotonic_s=time.monotonic(),
            owners=owners,actors=actors,status=status,started=read(directory/'started.json'),results=results,
            receipt_hashes=receipts,previous_complete=None,api=api,raw_API_wire=api_wire.decode('utf-8'),
            api_wire_sha256=hashlib.sha256(api_wire).hexdigest(),launcher_census=census)
        sample['observed_counts']=observed_counts(sample)
        sample=admission().collect(case,sample,observer_previous,journal_lines=journal_lines)
        return api_projection().collect_retired(case,sample,observer_previous,journal_lines=journal_lines)
    except (OSError,ValueError,KeyError) as failure:
        evidence.update(failure=repr(failure),ended_monotonic_s=time.monotonic())
        if isinstance(failure,module.CensusFailure):evidence['rejected_child_census']=failure.raw_snapshot
        raise module.CensusFailure(repr(failure),evidence) from failure


def validate(case, sample, previous=None):
    expected_slots = set(map(str, range(192)))
    status, actors, results = sample['status'], sample['actors'], sample['results']
    counts = observed_counts(sample)
    require(status['total'] == 192 and all(type(status.get(key)) is int for key in ('completed', 'retired', 'active'))
            and 0 <= status['retired'] <= status['completed'] <= counts['completed']
            and status['active'] + status['retired'] == 192
            and 0 <= sample['unix_s'] - status['updated_unix_s'] <= 5,
            'Published round counts are ahead, invalid or stale')
    require(sample.get('observed_counts', counts) == counts, 'Observed count derivation differs')
    admitted=admission().verify(case,sample,previous)
    launching=launchers().verify_sample(case,sample,admitted,previous)
    effective_round=admitted['round']
    results=admitted['results']
    pending=admitted['pending']
    require(set(actors) | set(results) | pending == expected_slots, 'Actor vanished without a committed score or proved sequential spawn')
    require(set(actors) <= expected_slots and set(results) <= expected_slots, 'Unknown actor slot')
    active = set(actors) - set(results)
    frozen = set(actors) & set(results)
    require(len(active) + len(results) + len(pending) == 192, 'Actual active and committed slot partition differs')
    for role in ['trainer', 'fleet']:
        actual, baseline = sample['owners'][role], case['owners'][role]
        require(actual['unit'] == baseline['unit'] and actual['invocation'] == baseline['invocation']
                and birth(actual['process']) == birth(baseline['process'])
                and all(actual['process'][key] == baseline['process'][key] for key in STATIC),
                'Original main owner, recipe, cgroup or executable changed')
    fleet = sample['owners']['fleet']['process']
    for slot, actor in actors.items():
        if slot in launching:
            continue  # Exact raw launcher ownership/input/stage/age was checked above.
        env = actor['environment']
        expected_env = dict(case['actor_environment'], ROBOTRON_CLIENT_SLOT=slot,
            ROBOTRON_ACTOR_ROUND=str(effective_round),
            ROBOTRON_EVAL_MODE='1' if case['slot_eval'][slot] else '2',
            ROBOTRON_PREVIEW_CLIENT='1' if slot == '0' else '0')
        require(actor['parent_pid'] == fleet['pid'] and actor['cgroup'] == fleet['cgroup']
                and actor['uids'] == [os.getuid()] * 4 and actor['affinity']
                and env == expected_env and actor['command'] == case['actor_command']
                and actor['affinity'] == case['actor_affinity']
                and actor['executable'] == case['actor_executable']
                and env['ROBOTRON_CLIENT_SLOT'] == slot
                and env['ROBOTRON_ACTOR_ROUND'] == str(effective_round)
                and env['ROBOTRON_SOCKET_ADDRESS'] == 'dell:9998'
                and env['ROBOTRON_RETIRE_AFTER_GAME'] == '1'
                and env['ROBOTRON_EVAL_MODE'] == ('1' if case['slot_eval'][slot] else '2'),
                'Actor ownership, role, round or socket changed')
        require((slot in frozen and actor['state'] in ('T', 't')
                 and results[slot]['pid'] == actor['pid'])
                or (slot in active and actor['state'] not in ('T', 't', 'Z', 'X', 'x')),
                'Completed actor still executing, or active actor stopped')
    api = sample['api']
    partition_sample=api_projection().project_retired(case,sample,previous)
    partition_api=partition_sample['api']
    rows = partition_api['client_rows']
    slots = [str(row['client_slot']) for row in rows]
    if admitted['bootstrap']:
        require(len(slots)==len(set(slots))==partition_api['client_count']
                and set(slots)-frozen==active-admitted['registering']
                and set(slots)<=set(actors), 'Proved bootstrap API partition differs')
    elif not (len(slots) == len(set(slots)) == partition_api['client_count'] and set(slots) - frozen == active
            and set(slots) <= set(actors)):
        certify_API_reconnect(case,partition_sample,previous)
    require(api['training_enabled'] is True and api['measurement_active'] is False
            and api['lr'] == 3.125e-6 and 0 <= sample['unix_s'] - api['ts'] <= 5
            and 0 <= api['pipeline_snapshot_age_s'] <= 5, 'Main training state stale or changed')
    for key in ['optimizer', 'replay']:
        actual = api['host_pipeline']['learning_exposure'][key]
        require(all(actual[field] == case['exposure'][key][field] for field in
                    ['process_id', 'instance_monotonic_ns', 'epoch', 'epoch_reason']),
                'Main optimizer/replay lineage changed')
        if key == 'optimizer':
            validate_optimizer_accounting(actual)
        else:
            require(actual['available'] is True, 'Replay exposure unavailable')
    if previous is None:
        require(effective_round==case['initial_round'] or (sample.get('round_admission')is not None
                and sample['round_admission']['chain_start']==case['initial_round']
                and bool(sample['round_admission']['closed_chain'])),
                'Initial round lacks the complete verified predecessor chain')
        return
    require(0 <= sample['monotonic_s'] - previous['monotonic_s'] <= 30, 'Observation gap exceeds30s')
    prior=admission().view(previous)
    old_round = prior['round']
    if effective_round == old_round:
        require(set(prior['results']) <= set(results), 'Completed slot lost or restarted')
        require(all(prior['receipt_hashes'][slot] == admitted['receipt_hashes'][slot]
                    for slot in prior['results']), 'Committed score receipt changed')
        for slot in set(previous['actors']) & set(actors):
            original, current = previous['actors'][slot], actors[slot]
            require(birth(original) == birth(current)
                    and (all(original[key] == current[key] for key in STATIC)
                         or forward_declared_exec(case,original,current)),
                    'Unplanned actor replacement within a round')
        for slot in set(previous['actors']) - set(actors):
            require(results[slot]['pid'] == previous['actors'][slot]['pid'], 'Retirement PID differs')
    else:
        require(effective_round == old_round + 1, 'Unobserved skipped training rounds')
        closed = admitted.get('previous_complete',sample['previous_complete'])
        require(closed is not None and set(closed['results']) == expected_slots
                and closed['summary']['complete'] is True and closed['summary']['completed'] == 192
                and closed['summary']['retired'] == 192
                and admitted['started']['started_unix_s'] >= closed['summary']['updated_unix_s'],
                'Next fleet started without the complete durable192-score barrier')
        require(all(closed['receipts'][slot] == digest for slot, digest in
                    prior['receipt_hashes'].items()), 'Closed prior score receipt changed')
        old_births = {birth(actor) for actor in previous['actors'].values()}
        require(not old_births & {birth(actor) for actor in actors.values()}, 'Old actor survived round turnover')
    for key in ['training_steps', 'learner_frame_count', 'optimized_samples', 'frame_count']:
        require(api[key] >= previous['api'][key], 'Main clock rolled back')


def validate_optimizer_accounting(value):
    """One admitted update may be in flight; unknown outcomes never qualify."""
    require(value['schema'] == 'robotron-optimizer-exposure-v1' and value['enabled'] is True,
            'Optimizer accounting disabled or foreign')
    names = ('attempts_started', 'outcomes_recorded', 'applied', 'amp_skipped', 'unavailable')
    total, epoch = value['total'], value['since_epoch']
    for counters in (total, epoch):
        require(all(type(counters.get(name)) is int and counters[name] >= 0 for name in names)
                and counters['unavailable'] == 0
                and counters['outcomes_recorded'] == counters['applied'] + counters['amp_skipped'],
                'Unknown or inconsistent optimizer outcomes')
    pending = total['attempts_started'] - total['outcomes_recorded']
    require(pending in (0, 1)
            and epoch['attempts_started'] - epoch['outcomes_recorded'] == pending
            and all(epoch[name] <= total[name] for name in names)
            and epoch['outcomes_recorded'] > 0
            and type(value['unclassified_started_total']) is int
            and value['unclassified_started_total'] == pending
            and type(value['available']) is bool and value['available'] is (pending == 0),
            'Optimizer in-flight accounting differs')
    return pending


def stable_round_status(value):
    # The publication heartbeat alone does not alter the round, roster, or scores.
    return {key: item for key, item in value.items() if key != 'updated_unix_s'}


def observed_counts(sample):
    """Receipt/kernel partition; the separately retained status is a projection."""
    actors, results = set(sample['actors']), set(sample['results'])
    return dict(total=192, completed=len(results), retired=len(results),
                active=len(actors-results), frozen=len(actors & results))


def api_projection():
    path=Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-recovery-evaluation-isolation-original01-20261027/retired-api-row-projection-original01-preparation/capture-bracket-revision02/api_cached_projections_v3.py')
    require(hashlib.sha256(path.read_bytes()).hexdigest()=='db5f06e406bf62128ccaa46ce3155c2a90c76c31daad37d8afb2fcbfa8c36f02','Exact combined cached-API projection verifier required')
    import sys
    name='_round_combined_cached_API_projection_v3'
    if name not in sys.modules:
        spec=importlib.util.spec_from_file_location(name,path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        sys.modules[name]=module
    return sys.modules[name]


def certify_API_reconnect(case,sample,previous):
    return api_projection().verify(case,sample,previous)


def admission():
    path=ROOT/'tools/post_recovery_evaluation/round_admission_proof_v2.py'
    require(hashlib.sha256(path.read_bytes()).hexdigest()=='9a5506a5b2163506f0cd40f71ca9c0a78945653a6ae9ae5552fb5a2bf70a4087',
            'Exact prospective natural-round admission verifier required')
    import sys
    name='_source_bound_natural_round_admission_v2'
    if name not in sys.modules:
        spec=importlib.util.spec_from_file_location(name,path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        sys.modules[name]=module
    return sys.modules[name]


def forward_declared_exec(case,original,current):
    module=launchers()
    return (birth(original)==birth(current)
        and all(original[key]==current[key] for key in ('parent_pid','cgroup','affinity','uids'))
        and module.ORDER[module.phase(case,original)]<module.ORDER[module.phase(case,current)])


def launchers():
    path=Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-recovery-evaluation-isolation-original01-20261027/declared-launcher-census-original34-preparation/launcher_census_v1.py')
    require(hashlib.sha256(path.read_bytes()).hexdigest()=='9da0759190ee2dc60393e293b707285168f35fe5a99c8707c10a8c0f834be26f','Exact prospective launcher census source required')
    import sys
    name='_declared_launcher_census_original34_v1'
    if name not in sys.modules:
        spec=importlib.util.spec_from_file_location(name,path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        sys.modules[name]=module
    return sys.modules[name]
