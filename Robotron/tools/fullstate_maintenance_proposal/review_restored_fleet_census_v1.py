"""Read-only independent physical census of the newly restored original fleet."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import time
import urllib.request


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--execute', action='store_true')
    p.add_argument('--header', type=Path)
    p.add_argument('--header-sha256')
    p.add_argument('--output', type=Path)
    a = p.parse_args()
    if not a.execute:
        print('PLAN_ONLY_NO_READS_OR_ACTIONS')
        return
    assert hashlib.sha256(a.header.read_bytes()).hexdigest() == a.header_sha256
    h = load('_restored_census_header', a.header)
    root = a.header.parent.parent
    pin = lambda path: h.metadata(path)[0]
    job_pin = pin(root / 'actual-restored-Main-fleet-preparation-original01/fresh-continuous-supervisor-v6-job.json')
    job = h.read(job_pin)
    helper = job['physical_helper']
    assert pin(helper['path']) == helper
    physical = load('_restored_census_physical', helper['path'])
    health_path = root.parent / ('quality32-protectedb231-vs-postreboot1c-fullgame-original01-20261101/'
        'future-owned-overlap-observer-reviewer-original02/current_v6_owned_overlap_health_v5.py')
    health = load('_restored_census_health', health_path)
    source = next(v for v in job['inputs'] if v['sha256'] == '986777d1be4a474bab21f968a1a30bbf79b58623682bad75c23417d140e85a6a')
    assert pin(source['path']) == source
    supervisor = load('_restored_census_supervisor', source['path'])
    assert callable(supervisor.closed_connection)
    assert a.output.is_absolute() and not a.output.exists()
    a.output.mkdir(mode=0o700)
    started = time.monotonic()

    def api(route):
        with urllib.request.urlopen('http://127.0.0.1:8771' + route, timeout=10) as response:
            return json.load(response)

    def fleet():
        return json.loads((root / 'post-backup-fleet-v6-original01/status.json').read_bytes())

    connections = api('/api/continuous_training_connections')
    before = fleet()
    stamp = time.time()
    assert before['trainer'] == job['trainer'] and before['source_authority'] == job['source_authority']
    assert before['rolemap'] == job['rolemap']
    assert before['supervisor']['pid'] == 1360667 and before['supervisor']['birth'] == 4655175
    assert before['supervisor']['invocation_id'] == 'b0c61bc709164f05981edca85aa05924'
    sup = physical.actor(before['supervisor']['pid'])
    assert sup['birth'] == before['supervisor']['birth'] and sup['cgroup'] == before['supervisor']['cgroup']
    assert sup['environment']['INVOCATION_ID'] == before['supervisor']['invocation_id'] and sup['uid'] == os.getuid()
    assert sup['command'][3:] == [source['path'], '--execute', '--config', job_pin['path'],
        '--config-sha256', job_pin['sha256'], '--source-sha256', source['sha256']]
    members = h.read(before['original_membership'])
    roles = h.read(before['rolemap'])['slot_eval']
    expected = {k: before[k] for k in ('epoch', 'supervisor', 'trainer', 'source_authority', 'original_membership', 'rolemap')}
    h.put(a.output / 'connections-before.json', connections)
    h.put(a.output / 'fleet-before.json', before)
    assert health.validate_metadata(before, connections, expected, members, roles, now=stamp) == []
    bindings, proofs, closures = {}, {}, {}
    for key, row in before['slots'].items():
        slot = int(key)
        binding = h.read(row['current_physical_binding'])
        bindings[slot] = binding
        if row['state'] == 'closed_eval':
            proc = Path('/proc', str(row['original_pid']), 'stat')
            absent = not proc.exists() or int(proc.read_text().rsplit(')', 1)[1].split()[19]) != row['original_birth']
            closures[slot] = dict(closure=h.read(row['closure']), natural=h.read(row['natural_result']), original_birth_absent=absent)
            continue
        actor = physical.actor(row['original_pid'])
        tcp = physical.tcp_binding(row['original_pid'], binding['data']['connection']['socket_endpoints'])
        assert physical.actor(row['original_pid']) == actor
        keys = binding['data']['actor']['environment']
        actor['environment'] = {k: actor['environment'].get(k) for k in keys}
        proofs[slot] = dict(actor=actor, TCP=tcp, before_after_actor_equal=True)
    for name, value in [('physical-proofs', proofs), ('bindings', bindings), ('closures', closures)]:
        h.put(a.output / (name + '.json'), value)
    result = health.validate_join(before, connections, expected, members, roles, proofs, bindings, closures,
        now=stamp, closed_connection_predicate=supervisor.closed_connection)
    after_connections = api('/api/continuous_training_connections')
    after = fleet()
    assert health.validate_metadata(after, after_connections, expected, members, roles, now=time.time()) == []
    assert health.stable_projection(before, connections) == health.stable_projection(after, after_connections)
    assert time.monotonic() - started <= 10
    h.put(a.output / 'connections-after.json', after_connections)
    h.put(a.output / 'fleet-after.json', after)
    now = api('/api/now')
    now_pin = h.put(a.output / 'Main-now.json', now)
    assert now['learner_frame_count'] > 5160938463
    assert now['pipeline_read_error'] == now['bank_persistence_read_error'] == ''
    report = h.put(a.output / 'report.json', dict(
        status='PASS_INDEPENDENT_RESTORED_ORIGINAL192_PHYSICAL_TCP_CENSUS', observed_unix_s=time.time(),
        actual_main=job['trainer'], actual_supervisor=before['supervisor'], current_fleet_job=job_pin,
        physical_helper=helper, health_validator=pin(health_path), source_supervisor=source,
        join_result=result, collection_elapsed_s=time.monotonic() - started, live_actors=len(proofs),
        closed_original_eval=len(closures), API=now_pin,
        all_live_original_pid_birth_parent_command_controlled_env_and_process_owned_TCP_verified=True,
        main_learning_frames_advanced=True, Main_recipe_changed=False, quality_qualified=False, promotion=False,
        test_source=pin(Path(__file__).resolve())))
    print(json.dumps(dict(report={k: report[k] for k in ('path', 'sha256', 'bytes')},
        join_result=result, live_actors=len(proofs), closed_eval=len(closures), fps=now['fps'])))


if __name__ == '__main__':
    main()
