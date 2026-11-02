"""Close the original invalid study from original receipts; never launch/retry."""
import hashlib
import importlib.util
import json
import sys
import time
from pathlib import Path

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
N = Path(__file__).resolve().parent


def load(name, path, digest):
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def birth(pid):
    try:
        return int(Path('/proc', str(pid), 'stat').read_text().rsplit(')', 1)[1].split()[19])
    except (FileNotFoundError, ProcessLookupError):
        return None


def main():
    h = load('_invalid_close_h', G / 'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py',
             '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1')
    reader = load('_invalid_close_reader', G / 'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py',
                  'c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071')
    read = lambda p, as_json=True: reader.read_pin(p, as_json=as_json)
    ready_pin = h.pin(N / 'new-original-quality-launch-readiness.json')
    assert ready_pin['sha256'] == '8a2ed32fa379317bf4557c3c900c2006715df8738412e59c2608d9ad7f3025cf'
    ready = read(ready_pin)
    arc = load('_invalid_close_arc', h.checked(ready['native_closure']), ready['native_closure']['sha256'])
    ctl = load('_invalid_close_ctl', h.checked(ready['CPU_controller']), ready['CPU_controller']['sha256'])
    outcome_pin = h.pin(N / 'original-fresh-sequence-observer-original01-outcome.json')
    outcome = read(outcome_pin)
    assert outcome['status'] == 'ORIGINAL_SEQUENCE_FAILURE_PRESERVED_NO_RETRY'
    assert outcome['quality_qualified'] is False and outcome['promotion'] is False
    assert len(outcome['original_records']) == 1 and outcome['original_records'][0]['role'] == 'R1'
    closed = []

    def scope(config_pin, owner_pin, closure_pin, expected_exit, cpu, memory, runtime, tasks, stop):
        config, owner, closure = map(read, (config_pin, owner_pin, closure_pin))
        fields = arc.archived_closure(closure, owner, read, exit_zero=expected_exit == 0)
        assert closure['original_exit'] == expected_exit
        assert ' '.join(config['argv']) + ' ; ignore_errors=no ;' in fields['ExecStart']
        assert arc.duration_seconds(fields['CPUQuotaPerSecUSec']) == cpu
        assert fields['MemoryMax'] == str(memory) and fields['MemorySwapMax'] == '0'
        assert arc.duration_seconds(fields['RuntimeMaxUSec']) == runtime
        assert fields['TasksMax'] == str(tasks) and fields['SendSIGKILL'] == 'no'
        assert arc.duration_seconds(fields['TimeoutStopUSec']) == stop and fields['Restart'] == 'no'
        assert birth(owner['pid']) != owner['starttime_ticks']
        for unit in (owner['unit'], owner['timer']):
            assert ctl.show(unit)['LoadState'] == 'not-found'
            assert not Path('/sys/fs/cgroup/user.slice/user-1001.slice/user@1001.service/app.slice', unit).exists()
        for pin in config['pins']:
            assert ctl.pin(pin['path']) == pin
        row = dict(config=config_pin, owner=owner_pin, closure=closure_pin, actual_exit=expected_exit,
                   all6_archived_descriptors_identity_argv_resources_pins_and_release_verified=True,
                   actual_pid_birth_and_both_units_and_cgroups_absent=True)
        closed.append(row)
        return row

    c = N / '02-candidate'
    controller_pin = h.pin(c / 'controller-original-result.json')
    controller = read(controller_pin)
    assert controller['actual_exit'] == 1 and controller['original_attempt'] == 1 and controller['no_retry'] is True
    scope(h.pin(c / 'controller-config.json'), h.pin(c / 'execution-original01/root-original-identity.json'),
          controller['closure'], 1, 12, 16 << 30, 22260, 512, 30)
    native_pin = h.pin(c / 'diagnostic-output-original01/result.json')
    native = read(native_pin)
    life = read(native['main_observer_lifecycle'])
    scope(life['worker_config'], life['worker_owner'], life['worker_closure'], 1, 2, 4 << 30, 22260, 128, 5)
    assert life['actual_controller_exit'] == 1 and life['original_scope_released'] is True
    assert life['all_owned_worker_and_controller_processes_reaped'] is True
    assert native['status'] == 'ORIGINAL_COMPILED_QUALITY32_INVALID_NO_RETRY'
    assert native['quality_qualified'] is False and native['complete'] is False
    cohort = native['after_intentional_stop']
    assert cohort['failure_reason'] == 'slot_quota_unfilled_at_start_horizon'
    assert cohort['count'] == 18 and cohort['started'] == 45 and cohort['abandoned'] == 27 and cohort['pending'] == 0
    assert len(cohort['rows']) == 18 and sum(cohort['slot_admitted_counts'].values()) == 45
    assert sum(v == 1 for v in cohort['slot_admitted_counts'].values()) == 19
    assert cohort['expected_games'] == 64 and cohort['games_per_slot'] == 2
    assert native['immutable_inputs_unchanged'] is True and native['all_original_threads_stopped'] is True
    assert native['original_lease_released'] is True and native['original_unsealed_journal_paths'] == []
    assert native['original_post_origin_child_reap']['all_original_children_reaped'] is True
    assert len(native['original_slots']) == 32
    for slot, actor in native['original_slots'].items():
        assert actor['actual_exit'] == 0 and birth(actor['pid']) != actor['birth']
        for pin in actor['files'].values():
            h.checked(pin)
    for pin in native['journal'].values():
        h.checked(pin)
    lease = native['lease']['coordinator']
    assert h.pin(lease['path']) == lease
    assert (lease['identity']['device'], lease['identity']['inode']) == (32, 757)
    for role, folder in [('R2', '03-reference'), ('C2', '04-candidate')]:
        assert not (N / folder).exists(), (role, 'must never have launched')
    for pid, original_birth in [(436041, 105465786), (436863, 105466229), (1817911, 108513519), (1261387, 107296702)]:
        assert birth(pid) != original_birth
    # This remains a failed original, regardless of its partial subset statistics.
    destination = N / 'original-campaign-invalid-C1-horizon-independent-closeout-original01'
    destination.mkdir(mode=0o700)
    report = dict(schema='robotron-original-invalid-campaign-independent-disposition-v1', created_unix_s=time.time(),
                  source=h.pin(__file__), readiness=ready_pin, sequence_outcome=outcome_pin,
                  actual_sequence_tool_exit=1, actual_display_tool_exit=0, actual_passive_watch03_tool_exit=0,
                  controller=controller_pin, native=native_pin, closed_scopes=closed,
                  original32_MAME_closed0_and_births_absent=True,
                  immutable_actor_and_game_life_start_journal_pins_verified=True,
                  original_persistent_GPU_coordinator_preserved_and_native_release_verified=True,
                  R2_C2_never_prepared_or_launched=True,
                  disposition='INVALID_ORIGINAL_C1_ADMISSION_HORIZON_NO_RETRY_NO_PROMOTION',
                  reason='19 slots had not started their required second game at the fixed 21540s admission horizon',
                  final_selected=dict(count=18, started=45, abandoned=27, pending=0, missing_selected_starts=19,
                                      mean=cohort['mean'], median=cohort['median']),
                  candidate_quality_unknown=True, partial_subset_used_for_quality=False,
                  quality_qualified=False, full_game_score_verified=False, promotion=False,
                  original_scientific_case_closed=True, current_isolated_family_freeze_releasable=True,
                  main_runtime_or_recipe_changed=False,
                  limits=['This is a failure/cleanup audit, not a scientific pass or a replay of unfinished full games.',
                          'Source-family release does not authorize changing the live main trainer or reusing this failed candidate confirmation.'])
    target = destination / 'independent-invalid-original-campaign-disposition.json'
    h.put(target, report)
    print(json.dumps(dict(report=h.pin(target), status=report['disposition'])))


if __name__ == '__main__':
    main()
