"""Independent, exact-owner recovery for a selected Robotron handoff.

Before the original stop commit, restore only this case's control and kernel
holds. After commit, delegate to the separately bound forward-recovery adapter;
never roll back sources/models or retry a replacement merely on timeout.
Default invocation performs no reads or actions.
"""
import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import signal
import time


def require(value, message):
    if not value:
        raise RuntimeError(message)


def load(entry, name):
    path = Path(entry['path'])
    require(path.is_file() and not path.is_symlink()
            and hashlib.sha256(path.read_bytes()).hexdigest() == entry['sha256'], 'Recovery dependency changed')
    spec = importlib.util.spec_from_file_location(name,path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def owned_control_variants(base_bytes, case, *, validated_base_measurement=None):
    require(type(case) is str and case.startswith('scorecarry-') and '/' not in case,
            'Exact case label required')
    base = json.loads(base_bytes)
    require(base.get('measurement') is None or base['measurement'] == validated_base_measurement,
            'A nonempty base control requires its source-bound closed authority')
    result = {base_bytes}
    for purpose in ('drain','final'):
        value = dict(base,measurement=dict(label=case+'-'+purpose,checkpoint=None,cohort_s=3600,timeout_s=7200))
        result.add((json.dumps(value,indent=2)+'\n').encode())
    return result


def validate_state(live_job, state, prepared, base, fleet, supplemental0, listener, dashboard):
    require(state['schema'] == 'robotron-owned-handoff-recovery-state-v1'
            and state['case'] == live_job['case'] and state['original_owner'] == base['owner']
            and state['original_fleet'] == prepared['original_fleet']
            and state['original_supplemental0'] == prepared['original_supplemental0']
            and state['original_listener'] == prepared['original_listener'], 'Foreign recovery state')
    require(state['control_path'] == str(live_job['control_path'])
            and state['control_path'].endswith('/Robotron/models_dqn/learning_control.json'), 'Control scope differs')
    expected_child = '/sys/fs/cgroup'+base['owner']['cgroup']+'/listener-'+live_job['case']
    require(state['listener_child'] == expected_child
            and listener['owner'] == base['owner'] and fleet['unit'].endswith('-fleet.service'),
            'Kernel recovery scope differs')
    require(type(state['original_stop_sent']) is bool and type(state['accept_held']) is bool
            and type(state['fleet_frozen']) is bool, 'Recovery stage flags are invalid')
    require(state['original_dashboard_accept'] == prepared['original_dashboard_accept']
            and dashboard['owner'] == base['owner']
            and (dashboard['tid'], dashboard['starttime_ticks'], dashboard['comm']) ==
                (1062559, 117472924, 'Thread-1 (serve')
            and state['dashboard_child'] == '/sys/fs/cgroup'+base['owner']['cgroup']+'/dashboard-'+live_job['case']
            and type(state['dashboard_accept_held']) is bool, 'Foreign HTTP recovery scope')
    require(base['schema'] == 'robotron-current-fresh192-continuation-registry-v1'
            and (base['owner']['pid'],base['owner']['starttime_ticks']) == (1062324,117468652)
            and set(state['producer_holds']) == set(state['producer_roots']) == {'fleet','supplemental0'}
            and all(type(v) is bool for v in state['producer_holds'].values()),
            'Exact original192 split-owner recovery context required')
    for key, producer in (('fleet',fleet),('supplemental0',supplemental0)):
        require(all(producer[k] == base['actual_owners'][key][k] for k in
                    ('pid','starttime_ticks','unit','invocation_id','cgroup'))
                and state['producer_roots'][key] == '/sys/fs/cgroup'+producer['cgroup']
                and producer['original_actors'] == [a for a in base['actors']
                    if base['actor_ownership'][str(a['slot'])] == key],
                'Foreign original input producer recovery scope')
    return expected_child


def release_original_listener(linux, state, listener):
    child = Path(state['listener_child'])
    if not child.exists():
        return dict(status='already_absent')
    owner = state['original_owner']
    parent = child.parent
    linux.live_owner(owner)
    require(child.resolve(strict=True) == child and child.stat().st_uid == os.getuid(), 'Foreign listener child')
    kind = (child/'cgroup.type').read_text().strip()
    if kind == 'domain':
        require(not (child/'cgroup.threads').read_text().strip()
                and dict(line.split() for line in (child/'cgroup.events').read_text().splitlines())['populated'] == '0'
                and not any(q.is_dir() for q in child.iterdir()), 'Nonempty pre-type listener child')
        child.rmdir()
        return dict(status='exact_empty_listener_child_removed_before_threaded_type')
    require(kind == 'threaded', 'Foreign listener child type')
    task = Path('/proc',str(owner['pid']),'task',str(listener['tid']))
    if task.exists() and (task/'cgroup').read_text().strip() == '0::'+str(child).removeprefix('/sys/fs/cgroup'):
        require(linux.starttime(task/'stat') == listener['starttime_ticks'], 'Original listener TID replaced')
        # Return the listener before unfreezing, so later handlers inherit
        # the original domain rather than this temporary child.
        (parent/'cgroup.threads').write_text(str(listener['tid'])+'\n')
    moved = []
    for tid in map(int,(child/'cgroup.threads').read_text().split()):
        task = Path('/proc',str(owner['pid']),'task',str(tid))
        require(task.exists() and (task/'cgroup').read_text().strip() ==
                '0::'+str(child).removeprefix('/sys/fs/cgroup'), 'Refuse an unowned inherited task')
        (parent/'cgroup.threads').write_text(str(tid)+'\n')
        moved.append(tid)
    (child/'cgroup.freeze').write_text('0\n')
    require(not (child/'cgroup.threads').read_text().strip(), 'Original listener child still populated')
    child.rmdir()
    require((parent/'cgroup.type').read_text().strip() == 'domain', 'Original domain did not restore')
    return dict(status='original_listener_returned_before_thaw',inherited_own_threads_returned=moved)


def release_original_dashboard(linux, state, dashboard):
    """Exact owned HTTP hold only; order BEFORE the game-listener unwind."""
    child = Path(state['dashboard_child'])
    if not child.exists():
        return dict(status='owned_HTTP_child_already_absent')
    linux.live_owner(state['original_owner'])
    owner = state['original_owner']; parent = child.parent
    require(child.resolve(strict=True) == child and child.stat().st_uid == os.getuid(), 'Foreign HTTP child')
    kind = (child/'cgroup.type').read_text().strip()
    if kind == 'domain':
        require(not (child/'cgroup.threads').read_text().strip()
                and dict(line.split() for line in (child/'cgroup.events').read_text().splitlines())['populated'] == '0'
                and not any(q.is_dir() for q in child.iterdir()), 'Nonempty pre-type HTTP child')
        child.rmdir()
        return dict(status='exact_empty_HTTP_child_removed_before_threaded_type')
    require(kind == 'threaded', 'Foreign HTTP child type')
    task = Path('/proc', str(owner['pid']), 'task', str(dashboard['tid']))
    require(task.exists() and linux.starttime(task/'stat') == dashboard['starttime_ticks']
            and (task/'comm').read_text().strip() == dashboard['comm'], 'Original HTTP serve task changed')
    moved = []
    for tid in map(int, (child/'cgroup.threads').read_text().split()):
        member = Path('/proc', str(owner['pid']), 'task', str(tid))
        require(member.exists() and (member/'cgroup').read_text().strip() ==
                '0::'+str(child).removeprefix('/sys/fs/cgroup'), 'HTTP child has an unowned native task')
        (parent/'cgroup.threads').write_text(str(tid)+'\n'); moved.append(tid)
    (child/'cgroup.freeze').write_text('0\n')
    require(not (child/'cgroup.threads').read_text().strip(), 'HTTP hold still populated')
    child.rmdir()
    return dict(status='exact_HTTP_tasks_returned_before_listener_control_fleet_unwind', returned_native_tids=moved)


def release_HTTP_if_save_function_returned(live_job, state, linux):
    """Only a shutdown liveness signal; never verifies replay/model save."""
    prepared = json.loads(linux.checked(live_job['prepared']))
    dashboard = json.loads(linux.checked(prepared['original_dashboard_accept']))
    owner = state['original_owner']; linux.live_owner(owner)
    binding = state.get('original_stop_stdout_binding')
    require(binding is not None and binding['owner'] == owner and state['original_stop_sent'] is True,
            'Committed HTTP release needs exact original console/stop scope')
    path = Path(binding['path']); info = path.lstat()
    require(path.resolve(strict=True) == path and (info.st_dev,info.st_ino) ==
            (binding['device'],binding['inode']) and info.st_uid == binding['uid']
            and info.st_nlink == binding['nlink'] == 1
            and 0 <= info.st_size-binding['offset'] <= 8*1024*1024,
            'Original shutdown console append differs')
    with path.open('rb') as stream:
        stream.seek(binding['offset']); tail = stream.read(8*1024*1024+1)
    if b'Final model & settings saved' not in tail:
        return None
    result = release_original_dashboard(linux, state, dashboard)
    result.update(save_function_returned_signal_only=True, persistence_success_not_inferred=True)
    return result


def restore_original_control(linux, live_job, state, base_bytes, base_binding):
    path = Path(state['control_path'])
    current = linux.full_pin(path)
    raw = path.read_bytes()
    closed = linux.validate_base_control(base_binding,base_bytes,
        closed_base_measurement=live_job['closed_base_measurement'])
    require(raw in owned_control_variants(base_bytes,live_job['case'],validated_base_measurement=closed),
            'A foreign control update must not be overwritten')
    if raw == base_bytes:
        return dict(status='original_control_already_restored',pin=current)
    pin = linux.atomic_owned_replace(path,current,base_bytes,suffix=live_job['case']+'-rescue')
    return dict(status='exact_original_control_restored',pin=pin)


def thaw_original_fleet(linux, fleet, *, hold_owned):
    linux.live_owner(fleet)
    for actor in fleet['original_actors']:
        require(linux.process_start(actor['pid']) == actor['starttime_ticks']
                and sorted(os.sched_getaffinity(actor['pid'])) == actor['mask'],
                'An original emulator identity/affinity changed')
    root = Path('/sys/fs/cgroup'+fleet['cgroup'])
    require(root.resolve(strict=True) == root and root.stat().st_uid == os.getuid(), 'Foreign fleet cgroup')
    if not hold_owned:
        require((root/'cgroup.freeze').read_text().strip() == '0',
                'Do not release a producer hold not recorded by this controller')
        return dict(status='original_input_group_already_unheld_no_write', actors=len(fleet['original_actors']))
    (root/'cgroup.freeze').write_text('0\n')
    return dict(status='original_owned_input_group_thawed_without_process_restart', actors=len(fleet['original_actors']))


def recover(live_job, state_path, *, observation_pending):
    linux = load(live_job['backend_source'],'_recovery_linux_primitives')
    prepared = json.loads(linux.checked(live_job['prepared']))
    base = json.loads(linux.checked(prepared['original_main']))
    fleet = json.loads(linux.checked(prepared['original_fleet']))
    supplemental0 = json.loads(linux.checked(prepared['original_supplemental0']))
    listener = json.loads(linux.checked(prepared['original_listener']))
    dashboard = json.loads(linux.checked(prepared['original_dashboard_accept']))
    base_bytes = linux.checked(live_job['base_control_archive'])
    require(hashlib.sha256(base_bytes).hexdigest() == live_job['base_control_sha256'], 'Original control archive differs')
    state_pin = linux.full_pin(state_path)
    state = json.loads(linux.checked(state_pin))
    validate_state(live_job,state,prepared,base,fleet,supplemental0,listener,dashboard)
    if state['original_stop_sent']:
        adapter = load(live_job['poststop_adapter'],'_owned_poststop_recovery')
        require(callable(getattr(adapter,'recover_committed',None)), 'Complete committed recovery adapter required')
        return adapter.recover_committed(live_job,state,observation_pending=observation_pending)
    linux.live_owner(base['owner'])
    require(linux.full_pin(linux.GAME/'Scripts/dqn/metrics_dashboard.py')['sha256'] == linux.OLD_SOCKET_SHA,
            'Original source changed before stop commit; do not unwind blindly')
    result = dict(status='PRESTOP_ORIGINAL_RESOURCES_RESTORED',original_handle_preserved=True,
                  replacement_started=False,restart_retry=False,source_rollback=False,
                  protected_policy_loaded=False,replay_cleared=False,errors=[])
    for name, function in (
        ('dashboard',lambda: release_original_dashboard(linux,state,dashboard)),
        ('listener',lambda: release_original_listener(linux,state,listener)),
        ('control',lambda: restore_original_control(linux,live_job,state,base_bytes,base)),
        ('fleet',lambda: thaw_original_fleet(linux,fleet,hold_owned=state['producer_holds']['fleet'])),
        ('supplemental0',lambda: thaw_original_fleet(linux,supplemental0,hold_owned=state['producer_holds']['supplemental0']))):
        try:
            result[name] = function()
        except BaseException as error:
            result['errors'].append(dict(component=name,error=repr(error)))
    if result['errors']:
        result['status'] = 'PRESTOP_OWNED_RECOVERY_INCOMPLETE_PRESERVED'
    return result


def controller_identity(linux, rescue_job):
    observed = linux.subprocess.run(['systemctl','--user','show',rescue_job['controller_unit']],
                                    capture_output=True,text=True,timeout=15)
    value = dict(line.split('=',1) for line in observed.stdout.splitlines() if '=' in line)
    if observed.returncode != 0:
        require(value.get('LoadState') == 'not-found' and value.get('MainPID','0') == '0',
                'Controller query failed for a reason other than not-yet-created')
        return None
    pid = int(value.get('MainPID','0'))
    if not pid:
        return None
    command = [x.decode() for x in Path('/proc',str(pid),'cmdline').read_bytes().split(b'\0') if x]
    expected_prefix = ['/usr/bin/python3.12','-I','-B',rescue_job['controller_source']['path'],
                       '--execute','--job',rescue_job['live_job_path'],'--expected-job-sha256']
    require(command[:-1] == expected_prefix and len(command[-1]) == 64,
            'Unexpected controller command; no signal or adoption')
    live_pin = linux.full_pin(rescue_job['live_job_path'])
    require(live_pin['sha256'] == command[-1], 'Actual controller job/source changed')
    live_job = json.loads(linux.checked(live_pin))
    require(live_job['prepared'] == rescue_job['prepared'] and live_job['case'] == rescue_job['case']
            and live_job['backend_source'] == rescue_job['backend_source']
            and live_job['recovery_source'] == rescue_job['recovery_source'], 'Controller job has foreign recovery scope')
    owner = dict(pid=pid,starttime_ticks=linux.process_start(pid),unit=rescue_job['controller_unit'],
                 invocation_id=value['InvocationID'],cgroup=value['ControlGroup'])
    linux.live_owner(owner)
    return owner,live_job


def terminal_recovery_required(value):
    """A result file alone cannot prove that its recovery actually completed."""
    if value.get('status') == 'CURRENT_TRAINER_STOPPED_AND_FULL_STATE_HOT_REPLAY_PRESERVED':
        return False
    if value.get('recovery_error'):
        return True
    recovery = value.get('recovery')
    if not isinstance(recovery,dict) or recovery.get('errors'):
        return True
    return recovery.get('status') not in (
        'PRESTOP_ORIGINAL_RESOURCES_RESTORED',
        'SAME_ORIGINAL_HANDLE_OBSERVATION_PENDING',
        'SAME_REPLACEMENT_HANDLE_OBSERVATION_PENDING',
        'COMMITTED_FORWARD_RECOVERY_VERIFIED')


def watch(job):
    linux = load(job['backend_source'],'_rescue_linux_primitives')
    for entry in (job['prepared'],job['controller_source'],job['recovery_source']):
        linux.checked(entry)
    require(job['schema'] == 'robotron-current-fresh192-preserveRAM-stop-rescue-job-v1'
            and job['case'].startswith('scorecarry-'), 'Explicit independent rescue job required')
    value = linux.show(job['unit'])
    owner = dict(pid=os.getpid(),starttime_ticks=linux.process_start(os.getpid()),unit=job['unit'],
                 invocation_id=value['InvocationID'],cgroup=value['ControlGroup'])
    linux.live_owner(owner)
    output = Path(job['output'])
    output.mkdir(mode=0o700)
    owner_pin = linux.publish(Path(job['owner_path']),owner)
    linux.publish(Path(job['ready_path']),dict(owner=owner,case=job['case'],
        prepared_inputs_sha256=job['prepared']['sha256'],recovery_source_sha256=job['recovery_source']['sha256']))
    created = time.monotonic()
    original = live_job = None
    result = dict(status='WAITING_FOR_ORIGINAL_CONTROLLER',owner=owner_pin,restart_retry=False)
    try:
        while time.monotonic()-created < 2200:
            if original is None:
                found = controller_identity(linux,job)
                if found:
                    original,live_job = found
                    linux.publish(output/'original-controller-birth.json',original)
                elif time.monotonic()-created > 90:
                    result.update(status='NO_CONTROLLER_STARTED_NO_RUNTIME_ACTIONS')
                    break
            else:
                terminal = Path(job['live_output'])/'result.json'
                needs_recovery = False
                if terminal.exists():
                    value = json.loads(terminal.read_bytes())
                    needs_recovery = terminal_recovery_required(value)
                    if not needs_recovery:
                        result.update(status='ORIGINAL_CONTROLLER_RESULT_OBSERVED',controller_result=linux.full_pin(terminal),
                                      original_controller=original)
                        break
                state_path = Path(job['live_output'])/'recovery-state.json'
                alive = linux.process_start(original['pid']) == original['starttime_ticks']
                if alive:
                    linux.live_owner(original)
                state = json.loads(state_path.read_bytes()) if state_path.exists() else None
                expired = False
                if state is not None:
                    require(state['controller_pid'] == original['pid']
                            and state['controller_starttime_ticks'] == original['starttime_ticks'], 'Foreign recovery-state writer')
                    start, deadline = state['stage_started_monotonic_s'],state['stage_deadline_monotonic_s']
                    require(all(type(v) in (int,float) and math.isfinite(v) for v in (start,deadline))
                            and 0 < deadline-start <= 900, 'Controller recovery deadline is invalid')
                    expired = time.monotonic() > deadline
                if not alive or expired:
                    if alive:
                        linux.live_owner(original)
                        os.kill(original['pid'],signal.SIGTERM)  # The controller only, never the trainer.
                        deadline = time.monotonic()+5
                        while time.monotonic()<deadline and linux.process_start(original['pid']) == original['starttime_ticks']:
                            time.sleep(.05)
                        require(linux.process_start(original['pid']) != original['starttime_ticks'],
                                'Original controller did not terminate; no concurrent unwind')
                    require(state is not None, 'No recovery state; no mutation inferred')
                    result.update(status='ORIGINAL_CONTROLLER_LOST_OR_DEADLINE_EXPIRED',
                        original_controller=original,controller_was_live_at_deadline=alive,
                        controller_result_required_recovery=needs_recovery,
                        recovery=recover(live_job,state_path,observation_pending=expired))
                    break
            time.sleep(.2)
        else:
            result.update(status='RESCUE_OBSERVATION_WINDOW_ENDED_NO_RESTART',original_controller=original)
    except BaseException as error:
        result.update(status='OWNED_RESCUE_ERROR_PRESERVED',error=repr(error),original_controller=original)
    result['ended_unix_s'] = time.time()
    linux.publish(output/'result.json',result)
    return 0 if 'ERROR' not in result['status'] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--watch',action='store_true')
    parser.add_argument('--job',type=Path)
    parser.add_argument('--expected-job-sha256')
    args = parser.parse_args()
    if not args.watch:
        print('PLAN_ONLY: no reads, output creation or runtime actions')
        return 0
    require(args.job and hashlib.sha256(args.job.read_bytes()).hexdigest() == args.expected_job_sha256,
            'Exact pinned rescue job required')
    return watch(json.loads(args.job.read_bytes()))


if __name__ == '__main__':
    raise SystemExit(main())
