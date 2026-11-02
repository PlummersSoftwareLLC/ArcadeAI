"""Run candidate then reference; preserve native role catalogue and original closure gates."""
import argparse
import errno
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import threading
import time


def read(path):
    raw = Path(path).read_bytes()
    if len(raw) > 8 << 20:
        raise ValueError('Unexpectedly large screen metadata')
    return json.loads(raw)


def selected(path, sha):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != sha:
        raise ValueError('Selected source or metadata changed')
    return raw


def write(path, value, exclusive=False):
    raw = (json.dumps(value, indent=2, allow_nan=False) + '\n').encode()
    if exclusive:
        with path.open('xb') as stream:
            stream.write(raw)
            stream.flush()
            os.fchmod(stream.fileno(), 0o444)
            os.fsync(stream.fileno())
    else:
        temp = path.with_name('.' + path.name + '.' + str(os.getpid()) + '.tmp')
        with temp.open('wb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)


def live(pid, birth):
    try:
        raw = Path('/proc', str(pid), 'stat').read_text()
        return int(raw.rsplit(')', 1)[1].split()[19]) == birth
    except (OSError, ValueError):
        return False


def validate_leg(result, job):
    if not (type(result['original_exit']) is int and result['original_exit'] == 0
            and all(result[k] is True for k in ('unit_released', 'lifecycle_complete', 'audit_success'))):
        raise ValueError('Original leg or owned resource closure failed')
    native = read(Path(job['output']) / 'result.json')
    if not (all(native[k] is True for k in ('complete', 'all_original_threads_stopped',
            'original_lease_released', 'immutable_inputs_unchanged'))
            and native['original_post_origin_child_reap']['all_original_children_reaped'] is True
            and len(native['original_slots']) == 32):
        raise ValueError('Native scores or original writer closure incomplete')
    seal_pin = native['deadline_score_seal']
    seal = json.loads(selected(seal_pin['path'], seal_pin['sha256']))
    rows = seal['rows']
    scores = [row['score_at_deadline'] for row in rows]
    if not (seal['n_scored'] == len(rows) == 32
            and {row['slot'] for row in rows} == set(range(4096, 4128))
            and seal['policy']['policy_sha256'] == job['checkpoint']['sha256']
            and seal['fixed_denominator_valid'] is True
            and seal['n_completed'] + seal['n_censored'] == 32
            and seal['horizon_ns'] == 3_600_000_000_000
            and all(type(v) is int and v >= 0 for v in scores)
            and seal['score_sum'] == sum(scores)
            and seal['mean_score'] == sum(scores) / 32):
        raise ValueError('Invalid fixed-denominator first-game score seal')
    return seal


def wait_for_job_ports(job, *, notify=None, socket_factory=None, clock=None, sleep=None):
    """Observe all selected bind-only ports free together within one90s bound.

    Probe sockets never listen/connect, and all are closed before returning.
    The subsequent native bind remains authoritative; this is no reservation.
    """
    slots, proxies = job['actor_slots'], job['proxy_ports']
    if not (type(slots) is list and len(slots) == 32 and len(set(slots)) == 32
            and all(type(slot) is int for slot in slots)
            and type(proxies) is dict and set(proxies) == {str(slot) for slot in slots}):
        raise ValueError('Exact selected32-slot proxy port map required')
    ports = [job['origin_port'], *[proxies[str(slot)] for slot in slots]]
    if not (all(type(port) is int and 1 <= port <= 65535 for port in ports)
            and len(set(ports)) == 33):
        raise ValueError('Selected origin and32 distinct TCP proxy ports required')
    factory = socket.socket if socket_factory is None else socket_factory
    now = time.monotonic if clock is None else clock
    pause = time.sleep if sleep is None else sleep
    started = now(); deadline = started + 90; tries = 0
    def observe(status, busy_port=None, detail=None, released=True):
        stamp = now()
        value = dict(status=status, tries=tries, elapsed_s=stamp-started, bound_s=90,
            started_monotonic_s=started, deadline_monotonic_s=deadline,
            observed_monotonic_s=stamp, ports=list(ports), busy_port=busy_port, detail=detail,
            bind_address='127.0.0.1', SO_REUSEADDR=0, probe_sockets_released=released, all_probe_socket_close_calls_attempted=True,
            native_launch_started=False, future_native_bind_still_required=True)
        if notify is not None:notify(value)
        return value
    while True:
        if now() >= deadline:
            observe('PORT_WAIT_TIMEOUT', detail='Selected ports did not become jointly bindable within90s')
            raise TimeoutError('Selected screen ports did not become jointly bindable within90s; no native launch')
        tries += 1; probes = []; failure = None; busy_port = None; close_error = None
        try:
            for port in ports:
                busy_port = port
                probe = factory(socket.AF_INET, socket.SOCK_STREAM); probes.append(probe)
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
                probe.bind(('127.0.0.1', port))
        except Exception as error:
            failure = error
        finally:
            for probe in probes:
                try:probe.close()
                except BaseException as error:
                    if close_error is None:close_error = error
        if close_error is not None:
            observe('PORT_PROBE_CLEANUP_FAILED', detail=repr(close_error), released=False)
            raise close_error
        if failure is None:
            if now() >= deadline:
                observe('PORT_WAIT_TIMEOUT', detail='Whole-set bind or cleanup exceeded90s; no native launch')
                raise TimeoutError('Selected screen port gate exceeded90s; no native launch')
            return observe('PORTS_FREE_BEFORE_LAUNCH')
        if not isinstance(failure, OSError) or failure.errno != errno.EADDRINUSE:
            observe('PORT_PROBE_FAILED', busy_port, repr(failure))
            raise failure
        if now() >= deadline:
            observe('PORT_WAIT_TIMEOUT', busy_port, repr(failure))
            raise TimeoutError('Selected screen ports remain busy at90s; no native launch') from failure
        observe('WAITING_FOR_PORTS', busy_port, 'EADDRINUSE; no listener or TIME_WAIT ownership inferred')
        pause(min(.25, max(0, deadline-now())))


def screen_display(selection):
    """Report labels only; selected native/controller remain authoritative."""
    reference=selection['reference'];candidate=selection['candidate']
    def sha(value):
        checkpoint=value.get('checkpoint',value)
        digest=checkpoint.get('sha256')if type(checkpoint)is dict else None
        if (type(digest)is not str or len(digest)!=64
                or any(c not in '0123456789abcdef'for c in digest)
                or value.get('sha256',digest)!=digest):
            raise ValueError('Exact selected policy SHA needed for report labels')
        return digest
    def label(role,value,digest):
        name=value.get('display_name')
        if name is not None and (type(name)is not str or not name.strip()
                or len(name)>80 or not name.isprintable()):
            raise ValueError('Bounded printable selected policy display_name required')
        fallback='Frozen reference'if role=='Reference'else'Candidate'
        return ((role+' ('+name.strip()+'; '+digest[:12]+')',name.strip())if name is not None
                else(fallback+' ('+digest[:12]+')',digest[:12]))
    reference_sha=sha(reference);candidate_sha=sha(candidate)
    reference_label,reference_name=label('Reference',reference,reference_sha)
    candidate_label,candidate_name=label('Candidate',candidate,candidate_sha)
    return dict(candidate_sha256=candidate_sha,reference_sha256=reference_sha,
        candidate_display_name=candidate_name,reference_display_name=reference_name,
        leg_labels=dict(R1=reference_label,C1=candidate_label),
        rationale='Compare the current frozen candidate with '+reference_label+
            ' using the same one-hour cutoff. Protected incumbent b231 remains unchanged; no automatic promotion.',
        policy_scope='Selected frozen candidate versus selected frozen reference; exploratory one-hour screen only, no automatic promotion')


def screen_progress_counts(status):
    """First-game progress; playing excludes naturally finished STOP-pending games."""
    keys=('n_scored','n_completed','n_unfinished','n_emulators_stopped','n_emulators_active')
    if (any(type(status.get(k))is not int or not 0<=status[k]<=32 for k in keys)
            or status['n_completed']>status['n_scored']
            or status['n_completed']+status['n_unfinished']!=32
            or status['n_emulators_stopped']+status['n_emulators_active']!=32
            or status['n_emulators_stopped']>status['n_completed']):
        raise ValueError('Exact typed32 first-game progress counts required')
    counts={k:status[k]for k in keys}
    counts.update(tracked=status['n_scored'],finished=status['n_completed'],playing=status['n_unfinished'])
    return counts


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--execute', action='store_true')
    p.add_argument('--source-sha256')
    p.add_argument('--prepared', type=Path)
    p.add_argument('--prepared-sha256')
    p.add_argument('--controller', type=Path)
    p.add_argument('--controller-sha256')
    p.add_argument('--configs', type=Path)
    p.add_argument('--configs-sha256')
    p.add_argument('--control', type=Path)
    p.add_argument('--output', type=Path)
    args = p.parse_args()
    if not args.execute:
        print('PLAN_ONLY: no input reads, processes, sockets or outputs')
        return 0
    selected(__file__, args.source_sha256)
    prepared = json.loads(selected(args.prepared, args.prepared_sha256))
    configs = json.loads(selected(args.configs, args.configs_sha256))
    # Authenticate the SAME immutable selection for display, without reading model bytes.
    selection = json.loads(selected(prepared['selection']['path'], prepared['selection']['sha256']))
    display = screen_display(selection)
    code = selected(args.controller, args.controller_sha256)
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader('_selected_screen_controller', loader=None))
    module.__file__ = str(args.controller)
    exec(compile(code, str(args.controller), 'exec'), module.__dict__)
    args.output.mkdir(mode=0o700, exist_ok=False)
    pid = os.getpid()
    birth = int(Path('/proc', str(pid), 'stat').read_text().rsplit(')', 1)[1].split()[19])
    write(args.output / 'owner.json', dict(pid=pid, birth=birth, started_unix_s=time.time(),
        prepared=str(args.prepared), controller_sha256=args.controller_sha256), True)
    phase = dict(leg=None, job=None, execution=None, terminal=False, port_gate=None, detail='Preparing the candidate-first original score-screen arm')
    stop = threading.Event()
    monitor_errors = []

    def report():
        try:
            now = time.time()
            c = read(args.control)
            work = c['next_work']
            leg, job = phase['leg'], phase['job']
            stage = phase['detail']
            role = display['leg_labels'].get(leg, 'Score screen')
            if leg in display['leg_labels'] and not phase['terminal']:
                stage = f'{role}: preparing the original score-screen arm'
            wait = 'The original controller and its verified result'
            eta = 'No confirmed start time yet; each admitted arm runs for one hour.'
            if phase['terminal']:
                wait = 'Review of the original score and resource-closure records'
                eta = 'The next action has no confirmed start time until the original results are reviewed.'
            anchor = None
            counts = None
            port_gate = phase.get('port_gate')
            if port_gate is not None and not phase['terminal']:
                stage = f'{role}: waiting for selected local ports'
                wait = f'All33 ports must be free together; {port_gate["tries"]} checks in {port_gate["elapsed_s"]:.1f}s'
                eta = 'Port availability is checked for at most90 seconds; the arm has not launched.'
            elif job is not None and not phase['terminal']:
                status_path = Path(job['output']) / 'status.json'
                identity_path = Path(phase['execution']) / 'root-original-identity.json'
                identity = read(identity_path) if identity_path.is_file() else None
                owner_live = bool(identity and live(identity['pid'], identity['starttime_ticks']))
                if status_path.is_file():
                    status = read(status_path)
                    age = now - status['observed_unix_s']
                    anchor = status.get('anchor')
                    counts = screen_progress_counts(status)
                    if owner_live and 0 <= age <= 20 and anchor:
                        remaining = max(0, (anchor['deadline_monotonic_ns'] - time.monotonic_ns()) / 1e9)
                        stage = (f'{role}: {counts["tracked"]}/32 first-game scores tracked · '
                                 f'{counts["finished"]} finished · {counts["playing"]} playing')
                        wait = 'Unfinished first games are playing until the fixed one-hour cutoff; completed emulators stop'
                        eta = time.strftime('This arm reaches cutoff at %I:%M:%S %p %Z', time.localtime(now + remaining)).replace(' 0', ' ') + f' ({remaining / 60:.1f} minutes remaining).'
                    elif owner_live and 0 <= age <= 20:
                        stage = f'{role}: connecting and certifying 32 fresh game clients'
                        wait = 'All 32 first games must pass startup checks before the one-hour clock starts'
                    else:
                        stage = f'{role}: checking the original process and result'
                        eta = 'Progress is delayed or the arm is closing; no current ETA is available.'
                elif owner_live:
                    stage = f'{role}: loading and compiling the frozen policy'
                    wait = 'Frozen-policy startup, then all 32 fresh first-game clients'
            work.update(state='score_screen_running' if not phase['terminal'] else 'score_screen_review',
                current_stage=stage, waiting_for=wait, detail=display['rationale'],
                next_stage=(display['leg_labels']['R1']+' after the candidate closes successfully'
                    if leg == 'C1' and not phase['terminal'] else
                    display['leg_labels']['C1']+' first, then '+display['leg_labels']['R1'] if leg is None and not phase['terminal'] else
                    'Review the score comparison and select the next learning change'),
                eta=eta, deadline_unix_s=None, main_training_continues=True,
                updated_unix_s=now, observation_unix_s=now, score_screen=dict(leg=leg, counts=counts, port_gate=port_gate,
                    policy_scope=display['policy_scope'],candidate_sha256=display['candidate_sha256'],
                    reference_sha256=display['reference_sha256'],candidate_display_name=display['candidate_display_name'],
                    reference_display_name=display['reference_display_name'],
                    leg_label=role))
            c.update(mode='manual', observation_unix_s=now, main_training_continues=True)
            write(args.control, c)
            write(args.output / 'heartbeat.json', dict(pid=pid, birth=birth, observed_unix_s=now,
                leg=leg, stage=stage, anchor=anchor, counts=counts))
        except Exception as error:
            monitor_errors.append(dict(unix_s=time.time(), error=repr(error)))
            print(json.dumps(dict(status='screen_report_update_delayed', error=repr(error))), flush=True)

    def watch():
        while not stop.is_set():
            report()
            stop.wait(10)

    worker = threading.Thread(target=watch, name='screen-work-status')
    worker.start()
    seals = {}
    port_gates = {}
    exit_code = 1
    error = None
    try:
        if not (selection['ordered_legs'] == prepared['ordered_legs'] == configs['ordered_legs'] == ['R1', 'C1']
                and selection.get('execution_order') == prepared.get('execution_order') == configs.get('execution_order') == ['C1', 'R1']):
            raise ValueError('Exact native role catalogue and selected candidate-first execution order required')
        for leg in ['C1', 'R1']:
            config_pin = configs['configs'][leg]
            config = json.loads(selected(config_pin['path'], config_pin['sha256']))
            job_pin = prepared['jobs'][leg]['job']
            job = json.loads(selected(job_pin['path'], job_pin['sha256']))
            if config['argv'] != prepared['jobs'][leg]['argv']:
                raise ValueError('Controller argv differs from the selected original job')
            phase.update(leg=leg, job=job, execution=config['output'], detail=f'Starting original {leg} score-screen arm')
            def port_observation(value):
                port_gates[leg] = value
                phase.update(port_gate=value, detail=f'Waiting for original {leg} selected ports')
            try:
                wait_for_job_ports(job, notify=port_observation)
            finally:
                if leg in port_gates:
                    write(args.output / (leg + '-port-gate.json'), port_gates[leg], True)
            phase.update(port_gate=None, detail=f'Starting original {leg} score-screen arm')
            module.launch(config_pin['path'])
            result = module.observe(config_pin['path'])
            seals[leg] = validate_leg(result, job)
            write(args.output / (leg + '-closed-and-scores.json'), dict(original_controller=result, score_seal=seals[leg]), True)
            print('------------------------\nRESULTS\n------------------------', flush=True)
            print(json.dumps(dict(leg=leg, mean=seals[leg]['mean_score'], median=seals[leg]['median_score'],
                completed=seals[leg]['n_completed'], censored=seals[leg]['n_censored'], all32_scores_included=True)), flush=True)
        exit_code = 0
        phase.update(terminal=True, detail='Score screen complete; training continues while the comparison is reviewed')
    except Exception as failure:
        error = repr(failure)
        phase.update(terminal=True, detail='Score screen needs review; preserving the original result and continuing Main training')
    finally:
        stop.set()
        worker.join(timeout=15)
        if worker.is_alive():
            exit_code = 1
            error = 'Report thread has not positively closed; preserve its ownership until the original process finishes'
        else:
            report()
    comparison = None
    if len(seals) == 2:
        reference, candidate = seals['R1']['mean_score'], seals['C1']['mean_score']
        comparison = dict(reference_mean=reference, candidate_mean=candidate,
            candidate_mean_change_fraction=None if reference == 0 else candidate / reference - 1,
            inference_scope='Two serial exploratory arms; no independent confirmation, promotion or causal learning claim')
    write(args.output / 'result.json', dict(actual_exit=exit_code, error=error, legs=list(seals),
        comparison=comparison, port_gates=port_gates, report_update_errors=monitor_errors, reporter_thread_closed=not worker.is_alive(),
        native_or_original_controller_retried=False, screen_only=True, promotion=False, ended_unix_s=time.time()), True)
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
