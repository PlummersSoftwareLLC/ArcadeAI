"""Inert CPU engineering experiment. No live journal, learner, GPU or actor edits."""
import argparse
import collections
import copy
import cProfile
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import pstats
import statistics
import sys
import tempfile
import time
import traceback
import unittest
from unittest.mock import patch


def require(value, message):
    if not value:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def load(name, entry):
    path = Path(entry['path'])
    require(hashlib.sha256(path.read_bytes()).hexdigest() == entry['sha256'], 'Source changed: ' + name)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def birth(pid):
    try:
        return int(Path('/proc', str(pid), 'stat').read_text().rsplit(')', 1)[1].split()[19])
    except FileNotFoundError:
        return None


class FixtureView:
    def __init__(self, module, journal_module, fixture, directory):
        self.module = module
        self.fixture = fixture
        self.now = fixture['clock']
        self.journal = journal_module.GameJournal(directory, clock=lambda: self.now,
                                                completion_policy='confirmed_reset_reserves_v1')
        self.restore()
        self.view = module.FixedSlotCohortView(self.journal, policy=fixture['policy'])

    def restore(self):
        self.journal.run_id = self.fixture['run_id']
        self.journal.sequence = self.fixture['sequence']
        self.journal.measurement_games = {r['journal_game_id']: r
            for r in copy.deepcopy(self.fixture['game_table'])}
        self.now = self.fixture['clock']

    def call(self):
        return self.view.cohort_status(*self.fixture['bounds'])


def outcome(function):
    try:
        return dict(value=canonical(function()))
    except Exception as error:
        return dict(exception=type(error).__name__, message=str(error))


def original_guards(modules, journal, measurement, guards):
    reports = []
    for name, module in modules.items():
        stream = io.StringIO()
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(guards.guard_suite(
            dict(journal=journal, measurement=measurement, view=module)))
        record = dict(implementation=name, tests_run=result.testsRun,
                      successful=result.wasSuccessful(), failures=len(result.failures),
                      errors=len(result.errors), output=stream.getvalue())
        reports.append(record)
    return reports


def semantic_guards(modules, journal, fixtures, directory, records):
    # Original append/completion histories replay on the same cached views.
    for role in ('R1', 'C1'):
        series = [f for f in fixtures if f['role'] == role]
        pair = {name: FixtureView(module, journal, series[0], directory / (role + '-history-' + name))
                for name, module in modules.items()}
        for fixture in series:
            outputs = {}
            for name, instance in pair.items():
                instance.fixture = fixture
                instance.restore()
                outputs[name] = outcome(instance.call)
                require(outputs[name] == dict(value=canonical(fixture['expected_cohort'])),
                        'Original append/completion replay differs: ' + fixture['fixture_id'] + ':' + name)
            require(outputs['baseline'] == outputs['proposal'], 'History outputs differ')
            records.append(dict(fixture=fixture['fixture_id'], check='append_completion_history', passed=True))

    for fixture in fixtures:
        pair = {name: FixtureView(module, journal, fixture,
                                 directory / (fixture['fixture_id'] + '-' + name))
                for name, module in modules.items()}
        expected = dict(value=canonical(fixture['expected_cohort']))
        for instance in pair.values():
            require(outcome(instance.call) == expected, 'Cold recorded cohort differs')
        known = [r['journal_game_id'] for r in fixture['game_table'] if r['known_start']]
        selected = set(fixture['expected_cohort']['started_ids'])
        mutations = ('game_uid', 'journal_id', 'slot', 'generation', 'clock',
                     'nested_certificate', 'start_timestamp', 'known_start', 'order', 'disappearance')
        for key in known:
            for mutation in mutations:
                bad = {}
                for name, instance in pair.items():
                    table = instance.journal.measurement_games
                    row = table[key]
                    if mutation == 'game_uid':
                        row['game_uid'] += 1
                    elif mutation == 'journal_id':
                        row['journal_game_id'] += '0'
                    elif mutation == 'slot':
                        row['client_slot'] = 4096 + ((row['client_slot'] - 4096 + 1) % 32)
                    elif mutation == 'generation':
                        row['measurement_generation'] += 1
                    elif mutation == 'clock':
                        row['start']['training_steps'] += 1
                    elif mutation == 'nested_certificate':
                        value = row['start'].get('startup_certificate')
                        row['start']['startup_certificate'] = dict(value or {}, mutation=True)
                    elif mutation == 'start_timestamp':
                        row['start_unix_s'] += .001
                    elif mutation == 'known_start':
                        row['known_start'] = False
                    elif mutation == 'order':
                        items = list(table.items())
                        index = next(i for i, item in enumerate(items) if item[0] == key)
                        item = items.pop(index)
                        items.insert(len(items) if key == known[0] else 0, item)
                        instance.journal.measurement_games = dict(items)
                    elif mutation == 'disappearance':
                        del table[key]
                    bad[name] = outcome(instance.call)
                    require('exception' in bad[name], 'Changed known start accepted: ' + mutation)
                    instance.restore()
                    require(outcome(instance.call) == expected, 'Restored descriptor does not match')
                require(bad['baseline'] == bad['proposal'], 'Mutation exception differs')
                records.append(dict(fixture=fixture['fixture_id'], check='known_start_' + mutation,
                                    journal_game_id=key, selected=key in selected,
                                    rejection=bad['baseline'], passed=True))

        for row in fixture['expected_cohort']['rows']:
            key = row['journal_game_id']
            for mutation in ('score', 'eligible', 'complete', 'disappearance', 'nested_context'):
                bad = {}
                for name, instance in pair.items():
                    game = instance.journal.measurement_games[key]
                    if mutation == 'score':
                        game['result']['score'] += 1
                    elif mutation == 'eligible':
                        game['result']['eligible'] = False
                    elif mutation == 'complete':
                        game['result']['complete'] = False
                    elif mutation == 'disappearance':
                        game['result'] = None
                    else:
                        game['result']['start_context']['mutation'] = True
                    bad[name] = outcome(instance.call)
                    require('exception' in bad[name], 'Changed completed result accepted')
                    instance.restore()
                    require(outcome(instance.call) == expected, 'Restored result differs')
                require(bad['baseline'] == bad['proposal'], 'Result exception differs')
                records.append(dict(fixture=fixture['fixture_id'], check='completed_' + mutation,
                                    journal_game_id=key, rejection=bad['baseline'], passed=True))

        for instance in pair.values():
            bounds = list(fixture['bounds'])
            bounds[1] += 1
            bounds[2] += 1
            changed = outcome(lambda: instance.view.cohort_status(*bounds))
            require('exception' in changed, 'Changed original bounds accepted')
            changed_policy = instance.view.policy()
            changed_policy['numeric_policy']['compile_options']['mutation'] = True
            require(canonical(instance.view.policy()) == canonical(fixture['policy']),
                    'Policy is not a defensive nested copy')
            returned = instance.call()
            for row in returned['rows']:
                row['score'] += 1
                row['start_context']['mutation'] = True
            require(outcome(instance.call) == expected, 'Returned rows are not defensive copies')
        require(outcome(lambda: pair['baseline'].view.cohort_status(*bounds)) ==
                outcome(lambda: pair['proposal'].view.cohort_status(*bounds)), 'Bounds exception differs')
        records.append(dict(fixture=fixture['fixture_id'], check='bounds_and_nested_defensive_copies', passed=True))

        # Mechanism counts are separate from all uninstrumented timing regions.
        for name, instance in pair.items():
            original = instance.module.canonical
            for iteration in range(3):
                counts = collections.Counter()
                def counted(value):
                    if type(value) is dict and 'journal_game_id' in value and 'start_reason' in value:
                        counts[value['journal_game_id']] += 1
                    return original(value)
                with patch.object(instance.module, 'canonical', counted):
                    require(outcome(instance.call) == expected, 'Counting instrumentation changed output')
                multiplier = 2 if name == 'baseline' else 1
                require(counts == collections.Counter({key: multiplier for key in known}),
                        'Every original known start must be freshly serialized per call')
                records.append(dict(fixture=fixture['fixture_id'], check='descriptor_serialization_counts',
                                    implementation=name, iteration=iteration,
                                    expected_each=multiplier, counts=dict(counts), passed=True))
    return records


def timed_call(instance):
    wall_start = time.perf_counter_ns()
    cpu_start = time.process_time_ns()
    value = instance.call()
    cpu_end = time.process_time_ns()
    wall_end = time.perf_counter_ns()
    return value, cpu_end - cpu_start, wall_end - wall_start


class ProfileLock:
    def __init__(self, original):
        self.original = original
        self.samples = []

    def __enter__(self):
        self.original.acquire()
        self.cpu = time.process_time_ns()
        self.wall = time.perf_counter_ns()
        return self

    def __exit__(self, *args):
        cpu, wall = time.process_time_ns() - self.cpu, time.perf_counter_ns() - self.wall
        self.original.release()
        self.samples.append(dict(cpu_ns=cpu, wall_ns=wall))


def benchmark(modules, journal, fixtures, manifest, directory, output, h, job):
    all_results = []
    for fixture, declared in zip(fixtures, manifest['fixtures']):
        pair = {name: FixtureView(module, journal, fixture,
                                 directory / ('timed-' + fixture['fixture_id'] + '-' + name))
                for name, module in modules.items()}
        cold = {}
        for name, instance in pair.items():
            value, cpu, wall = timed_call(instance)
            require(canonical(value) == canonical(fixture['expected_cohort']), 'Cold benchmark output differs')
            cold[name] = dict(cpu_ns=cpu, wall_ns=wall)
            del value
            for _ in range(job['warmup_calls']):
                require(instance.call() == fixture['expected_cohort'], 'Warmup output differs')
        rounds = []
        for index in range(job['rounds']):
            order = ('baseline', 'proposal') if index % 2 == 0 else ('proposal', 'baseline')
            values = {}
            for name in order:
                cpu_samples, wall_samples = [], []
                for _ in range(job['calls_per_round']):
                    value, cpu, wall = timed_call(pair[name])
                    require(value == fixture['expected_cohort'], 'Timed output differs')
                    cpu_samples.append(cpu)
                    wall_samples.append(wall)
                    del value
                values[name] = dict(cpu_ns=cpu_samples, wall_ns=wall_samples)
            rounds.append(h.put(output / (fixture['fixture_id'] + '-round-' + str(index).zfill(2) + '.json'),
                                dict(fixture=fixture['fixture_id'], round=index, order=order,
                                     calls_per_implementation=job['calls_per_round'], values=values)))
        data = [json.loads(h.checked(pin).read_bytes()) for pin in rounds]
        summary = {}
        for clock in ('cpu_ns', 'wall_ns'):
            a = [v for r in data for v in r['values']['baseline'][clock]]
            b = [v for r in data for v in r['values']['proposal'][clock]]
            differences = [1 - statistics.mean(r['values']['proposal'][clock]) /
                              statistics.mean(r['values']['baseline'][clock]) for r in data]
            centre = statistics.mean(differences)
            radius = job['t_critical_df9_975'] * statistics.stdev(differences) / math.sqrt(len(differences))
            summary[clock] = dict(baseline_median=statistics.median(a), proposal_median=statistics.median(b),
                                 median_fraction_reduction=1 - statistics.median(b) / statistics.median(a),
                                 paired_round_mean_fraction_reductions=differences,
                                 paired_mean_fraction_reduction=centre,
                                 paired95_t_interval=[centre - radius, centre + radius])

        profiles = {}
        for name, module in modules.items():
            instance = FixtureView(module, journal, fixture,
                                   directory / ('profile-' + fixture['fixture_id'] + '-' + name))
            require(instance.call() == fixture['expected_cohort'], 'Profile warmup differs')
            control_cpu, control_wall = time.process_time_ns(), time.perf_counter_ns()
            for _ in range(job['profile_calls']):
                value = instance.call()
            control_cpu = time.process_time_ns() - control_cpu
            control_wall = time.perf_counter_ns() - control_wall
            require(value == fixture['expected_cohort'], 'Unprofiled matched control differs')
            lock = ProfileLock(instance.journal.lock)
            instance.journal.lock = lock
            profile = cProfile.Profile()
            cpu_start, wall_start = time.process_time_ns(), time.perf_counter_ns()
            profile.enable()
            for _ in range(job['profile_calls']):
                value = instance.call()
            profile.disable()
            cpu_elapsed, wall_elapsed = time.process_time_ns() - cpu_start, time.perf_counter_ns() - wall_start
            require(value == fixture['expected_cohort'], 'Profile output differs')
            path = output / (fixture['fixture_id'] + '-' + name + '.pstats')
            profile.dump_stats(path)
            with path.open('rb') as stream:
                os.fchmod(stream.fileno(), 0o444)
                os.fsync(stream.fileno())
            stats = pstats.Stats(profile)
            selected = []
            for (filename, line, function), (primitive, total, exclusive, cumulative, _) in stats.stats.items():
                if function in ('cohort_status', '_descriptor', 'canonical', 'dumps', 'deepcopy',
                                'mean', 'median', 'stdev', '__enter__', '__exit__'):
                    selected.append(dict(filename=filename, line=line, function=function,
                                         primitive_calls=primitive, total_calls=total,
                                         exclusive_s=exclusive, cumulative_s=cumulative))
            profiles[name] = dict(raw_profile=h.pin(path), calls=job['profile_calls'],
                                  cpu_ns=cpu_elapsed, wall_ns=wall_elapsed,
                                  selected_function_stats=selected, lock_hold_samples=lock.samples,
                                  instrumented_CPU_per_call=cpu_elapsed / job['profile_calls'],
                                  matched_unprofiled_control_CPU_ns=control_cpu,
                                  matched_unprofiled_control_wall_ns=control_wall,
                                  uninstrumented_CPU_median=summary['cpu_ns'][name + '_median'],
                                  profiler_and_lock_instrumentation_overhead_ratio=
                                      cpu_elapsed / control_cpu)
        cpu = summary['cpu_ns']
        result = dict(fixture=fixture['fixture_id'], fixture_pin=declared['fixture'],
                      primary_active_tail=declared['primary_active_tail'], cold_calls=cold,
                      timing_rounds=rounds, summary=summary, profiles=profiles,
                      no_median_CPU_regression_over_5_percent=cpu['median_fraction_reduction'] >= -.05,
                      active_tail_CPU_gate=(cpu['median_fraction_reduction'] >= .10 and
                                            cpu['paired95_t_interval'][0] > 0))
        all_results.append(h.put(output / (fixture['fixture_id'] + '-result.json'), result))
        print(json.dumps(dict(event='fixture_measured', fixture=fixture['fixture_id'],
                              median_CPU_reduction=cpu['median_fraction_reduction'],
                              paired95=cpu['paired95_t_interval'])), flush=True)
    return all_results


def execute(args):
    source = Path(__file__)
    require(hashlib.sha256(source.read_bytes()).hexdigest() == args.source_sha256, 'Runner source changed')
    raw = Path(args.job).read_bytes()
    require(hashlib.sha256(raw).hexdigest() == args.job_sha256, 'Job changed')
    job = json.loads(raw)
    h = load('_selector_profile_h', job['sources']['helpers'])
    for pin in job['inputs']:
        h.checked(pin)
    output = Path(job['output'])
    output.mkdir(mode=0o700)
    intent = h.put(output / 'intent.json', dict(pid=os.getpid(), birth=birth(os.getpid()),
        source=h.pin(source), job=h.pin(args.job), scientific_case=False, created_unix_s=time.time()))
    semantic_records = []
    try:
        require(job['rounds'] == 10 and job['calls_per_round'] == 100 and job['profile_calls'] == 100,
                'Precommitted workload differs')
        require(job['warmup_calls'] == 20 and job['t_critical_df9_975'] == 2.2621571628540993,
                'Precommitted estimator differs')
        reader = load('_selector_profile_reader', job['sources']['immutable_reader'])
        read = lambda entry, as_json=True: reader.read_pin(entry, as_json=as_json)
        rt = load('_selector_profile_archives', job['sources']['native_closure'])
        ctl = load('_selector_profile_ctl', job['sources']['CPU_controller'])
        closed = read(job['scientific_closeout'])
        require(closed['all_original_scientific_scopes_closed_zero_and_released'], 'Original scopes incomplete')
        scopes = closed['original_native_and_review_scopes'] + closed['original_worker_scopes'] + [
            closed['original_final_assessor_scope']]
        require(len(scopes) == 13, 'All thirteen original scientific scopes required')
        for scope in scopes:
            owner = read(scope['owner'])
            fields = rt.archived_closure(read(scope['closure']), owner, read, exit_zero=True)
            require(fields == scope['fields'], 'Original closure readback changed')
            require(birth(owner['pid']) != owner['starttime_ticks'], 'Original scientific birth remains')
            for unit in (owner['unit'], owner['timer']):
                require(ctl.show(unit)['LoadState'] == 'not-found', 'Original unit remains')
                require(not Path('/sys/fs/cgroup/user.slice/user-1001.slice/user@1001.service/app.slice',
                                 unit).exists(), 'Original cgroup remains')
        require(birth(job['original_sequence']['pid']) != job['original_sequence']['birth'], 'Sequence remains')
        winner = read(job['protected_winner_closeout'])
        require(winner['actual_terminal_exit'] == 0 and winner['quality_qualified'] and
                winner['protected_copy_published'], 'Winner disposition not verified')
        h.checked(winner['protected_checkpoint'])
        modules = {name: load('_selector_profile_' + name, job['sources'][name])
                   for name in ('baseline', 'proposal')}
        journal = load('_selector_profile_journal', job['sources']['journal'])
        measurement = load('_selector_profile_measurement', job['sources']['measurement'])
        guards = load('_selector_profile_original_guards', job['sources']['original_guards'])
        manifest = read(job['fixture_manifest'])
        fixtures = [read(item['fixture']) for item in manifest['fixtures']]
        require(len(fixtures) == 12 and {f['role'] for f in fixtures} == {'R1', 'C1'}, 'Both original roles required')
        for fixture in fixtures:
            require(hashlib.sha256(canonical(fixture['game_table']).encode()).hexdigest() ==
                    fixture['table_canonical_SHA256'], 'Fixture table changed')
            require(hashlib.sha256(canonical(fixture['expected_cohort']).encode()).hexdigest() ==
                    fixture['expected_cohort_canonical_SHA256'], 'Expected snapshot changed')
        original = original_guards(modules, journal, measurement, guards)
        h.put(output / 'original-guard-results.json', original)
        require(all(r['tests_run'] == len(job['original_guard_methods']) for r in original),
                'Every original guard method must run for both implementations')
        require(all(r['successful'] for r in original), 'Original unmodified engineering guards failed')
        print(json.dumps(dict(event='original_guards_passed', results=[
            dict(implementation=r['implementation'], tests_run=r['tests_run']) for r in original])), flush=True)
        with tempfile.TemporaryDirectory(prefix='selector-profile-fixtures-') as temporary:
            directory = Path(temporary)
            semantics = semantic_guards(modules, journal, fixtures, directory, semantic_records)
            sempin = h.put(output / 'semantic-and-mutation-results.json', dict(
                checks=semantics, check_count=len(semantics), all_passed=True,
                includes_all_known_selected_and_outside_starts=True))
            print(json.dumps(dict(event='semantic_guards_passed', checks=len(semantics))), flush=True)
            require(len(list(Path('/proc/self/task').iterdir())) == 1, 'Single-threaded CPU timing required')
            results = benchmark(modules, journal, fixtures, manifest, directory, output, h, job)
        reviewed = [read(pin) for pin in results]
        no_regression = all(r['no_median_CPU_regression_over_5_percent'] for r in reviewed)
        active = [r for r in reviewed if r['primary_active_tail']]
        require(len(active) == 4, 'Four predeclared active-tail fixtures required')
        selected = no_regression and all(r['active_tail_CPU_gate'] for r in active)
        require('torch' not in sys.modules, 'Numerical runtime imported unexpectedly')
        report = dict(schema='robotron-original-selector-CPU-equivalence-profile-result-v1',
            status='COMPLETE', intent=intent, job=h.pin(args.job), source=h.pin(source),
            all_original_guards_passed=True, original_guard_result=h.pin(output / 'original-guard-results.json'),
            all_semantic_guards_passed=True, semantic_guard_result=sempin, fixtures=results,
            no_fixture_median_CPU_regression_over_5_percent=no_regression,
            all4_active_tail_CPU_gates_passed=all(r['active_tail_CPU_gate'] for r in active),
            proposal_passes_precommitted_CPU_experiment=selected,
            next_action='Fresh source-family/initializer guards and controlled runtime validation required'
                if selected else 'Retain baseline;do not relax criteria;profile next measured cost',
            production_runtime_selected=False, production_sources_changed=False,
            quality_qualified=False, learning_speed_gain_verified=False,
            useful_training_throughput_gain_verified=False, created_unix_s=time.time(),
            limitations=job['limitations'])
        rp = h.put(output / 'result.json', report)
        print(json.dumps(dict(result=rp, CPU_experiment_passed=selected,
                              runtime_selected=False, quality_qualified=False)), flush=True)
        return 0
    except Exception as error:
        failure = h.put(output / 'failure.json', dict(status='FAILED_ORIGINAL_ENGINEERING_EXPERIMENT',
            error=repr(error), traceback=traceback.format_exc(), intent=intent,
            completed_semantic_checks=semantic_records,
            quality_qualified=False, production_sources_changed=False, created_unix_s=time.time()))
        print(json.dumps(dict(failure=failure, error=repr(error))), flush=True)
        return 1


def main():
    if '--execute' not in sys.argv:
        print('PLAN_ONLY: no fixtures, source loading, guards, profiling or runtime changes')
        return 0
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--job', required=True)
    parser.add_argument('--job-sha256', required=True)
    parser.add_argument('--source-sha256', required=True)
    return execute(parser.parse_args())


if __name__ == '__main__':
    raise SystemExit(main())
