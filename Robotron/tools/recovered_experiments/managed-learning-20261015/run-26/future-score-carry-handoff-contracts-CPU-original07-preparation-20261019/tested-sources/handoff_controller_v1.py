"""One bounded score-carry handoff, driven by an authenticated backend.

Default invocation performs no reads or actions. A backend owns real process,
control, cgroup, source, CPU-verifier and recovery operations. This module owns
their required order and the no-retry lifecycle. ObservationPending never
authorizes restarting or terminating a live replacement.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path


class HandoffError(RuntimeError):
    pass


class ObservationPending(HandoffError):
    """The same original handle remains live; later work must observe it."""


def require(value, message):
    if not value:
        raise HandoffError(message)


class Handoff:
    def __init__(self, backend):
        self.backend = backend
        if callable(getattr(backend, 'bind_observation_pending', None)):
            backend.bind_observation_pending(ObservationPending)
        self.stage = 'unstarted'
        self.stop_attempts = self.start_attempts = 0
        self.original_stop_requested = False
        self.replacement = None
        self.completed = False
        self.has_run = False

    def call(self, stage, function, *args):
        self.stage = stage
        self.backend.before_stage(stage)
        value = function(*args)
        self.backend.after_stage(stage, value)
        return value

    def run(self):
        require(not self.has_run, 'Do not retry the same handoff controller instance')
        self.has_run = True
        b = self.backend
        outcome = dict(status='UNSTARTED', restart_retry=False, rollback=False,
                       protected_policy_loaded=False, replay_cleared=False)
        try:
            context = self.call('preflight', b.preflight)
            probe = self.call('probe_registered_without_frames', b.open_probe, context)
            pause1 = self.call('first_supported_pause', b.pause, 'drain', probe)
            self.call('all192_acknowledged_and_advanced8_measured_frames', b.measured_progress, pause1)
            listener = self.call('exact_accept_thread_held', b.hold_listener, context)
            fleet = self.call('original_emulator_fleet_frozen', b.freeze_fleet, context)
            seal = self.call('input_ownership_and_receive_queues_sealed', b.seal_inputs,
                             context, probe, listener, fleet, pause1)
            self.call('first_FIFO_marker_acknowledged', b.marker, probe, pause1, seal)
            # Keep only the owned EVAL probe alive. Let old handlers reach
            # their original idle timeout while emulators remain frozen. This
            # settles all final counters before the actual model/phase save.
            self.call('original192_handlers_finished', b.finish_original_handlers,
                      context, probe, pause1, seal)
            self.call('first_pause_restored_with_no_input', b.cancel_pause, pause1)
            budget = self.call('actual_original_budget_exhausted', b.drain_budget, context, seal)
            pause2 = self.call('final_supported_pause_prefetch_quiesced', b.pause, 'final', probe)
            self.call('final_FIFO_marker_acknowledged', b.marker, probe, pause2, seal)
            self.call('owned_probe_closed_and_handler_finished', b.close_probe, probe)
            no_producers = self.call('no_remaining_input_producers', b.no_producers, context, seal)
            banks = self.call('real_bank_shutdown_intent_sealed', b.seal_banks,
                              context, pause2, seal, budget, no_producers)
            require(banks.get('input_sources_sealed') is True
                    and banks.get('all_handlers_finished') is True
                    and banks.get('prefetch_paused') is True
                    and banks.get('budget_exhausted') is True
                    and banks.get('bank_shutdown_intent_verified') is True,
                    'Final source/budget/bank gate is incomplete')
            self.original_stop_requested = True
            self.stop_attempts += 1
            require(self.stop_attempts == 1, 'One original stop attempt only')
            retired = self.call('original_main_graceful_stop', b.stop_original, context, banks)
            require(type(retired.get('actual_exit')) is int and retired['actual_exit'] == 0
                    and retired.get('original_absent') is True,
                    'Original main did not close cleanly')
            saved = self.call('newest_stopped_checkpoint_CPU_verified', b.verify_stopped,
                              context, retired, banks)
            require(type(saved.get('actual_original_CPU_exit')) is int and saved['actual_original_CPU_exit'] == 0
                    and saved.get('strict_phase_verified') is True
                    and saved.get('newest_stopped_source') is True
                    and saved.get('replay_bank_consistency_verified') is True,
                    'Actual newest stopped checkpoint/replay verification is incomplete')
            installed = self.call('exact_parser_and_resume_record_installed', b.install,
                                  context, retired, saved)
            require(installed.get('exact_selected_parser') is True
                    and installed.get('only_selected_source_changed') is True
                    and installed.get('newest_checkpoint_unchanged') is True,
                    'Source installation escaped its verified transaction')
            self.start_attempts += 1
            require(self.start_attempts == 1, 'One replacement start attempt only')
            self.replacement = self.call('one_replacement_started', b.start_once,
                                         context, saved, installed)
            startup = self.call('same_replacement_startup_verified', b.verify_startup,
                                self.replacement, saved, installed)
            require(startup.get('same_original_replacement') is True
                    and startup.get('newest_state_preserved') is True
                    and startup.get('startup_update_count') in (0, 1)
                    and type(startup.get('startup_update_count')) is int
                    and all(type(startup.get(k)) is int for k in
                            ('logical_sample_delta','learner_frame_delta','raw_frame_delta'))
                    and startup.get('logical_sample_delta') == startup['startup_update_count']*4096
                    and startup.get('learner_frame_delta') == 0
                    and startup.get('raw_frame_delta') == 0
                    and startup.get('replay_storage_and_bank_identity_verified') is True,
                    'Verified startup did not preserve the newest state')
            self.call('original_fleet_thawed', b.thaw_fleet, context, startup)
            live = self.call('original192_reconnected_and_learning', b.verify_progress,
                             context, self.replacement, startup)
            require(live.get('original192_identities_preserved') is True
                    and live.get('training_progress_verified') is True
                    and type(live.get('pipeline_errors')) is int and live['pipeline_errors'] == 0,
                    'Original actors or healthy learning were not restored')
            self.completed = True
            outcome.update(status='SCORE_CARRY_HANDOFF_VERIFIED_ORIGINAL192_LEARNING',
                           production_changed=True, live=live,
                           startup_update_count=startup['startup_update_count'])
        except ObservationPending as error:
            outcome.update(status='SAME_ORIGINAL_HANDLE_OBSERVATION_PENDING',
                           error=str(error), pending_stage=self.stage)
            # The backend may release only the exact resources it owns. It
            # must preserve the live replacement and any actual startup work.
            try:
                outcome['recovery'] = b.recover(self, observation_pending=True)
            except BaseException as recovery_error:
                outcome['recovery_error'] = repr(recovery_error)
        except BaseException as error:
            outcome.update(status='ORIGINAL_HANDOFF_FAILURE_PRESERVED',
                           error=repr(error), failed_stage=self.stage)
            try:
                outcome['recovery'] = b.recover(self, observation_pending=False)
            except BaseException as recovery_error:
                outcome['recovery_error'] = repr(recovery_error)
        finally:
            outcome.update(stage=self.stage, original_stop_attempts=self.stop_attempts,
                           replacement_start_attempts=self.start_attempts,
                           objective_complete=False, quality_qualified=False,
                           learning_speed_gain_verified=False)
            b.finish(outcome)
        return outcome


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--job', type=Path)
    parser.add_argument('--expected-job-sha256')
    args = parser.parse_args()
    if not args.execute:
        print('PLAN_ONLY: no reads, output creation, signals or runtime changes')
        return 0
    require(args.job is not None and args.expected_job_sha256
            and hashlib.sha256(args.job.read_bytes()).hexdigest() == args.expected_job_sha256,
            'Exact selected immutable handoff job required')
    job = json.loads(args.job.read_bytes())
    require(job.get('authorized') is True and job.get('schema') == 'robotron-score-carry-live-handoff-job-v1',
            'Explicit selected live handoff scope required')
    entry = job['backend_source']
    path = Path(entry['path'])
    require(hashlib.sha256(path.read_bytes()).hexdigest() == entry['sha256'], 'Backend source changed')
    spec = importlib.util.spec_from_file_location('_selected_handoff_backend', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    backend = module.prepare(job)
    result = Handoff(backend).run()
    return 0 if result['status'] == 'SCORE_CARRY_HANDOFF_VERIFIED_ORIGINAL192_LEARNING' else 1


if __name__ == '__main__':
    raise SystemExit(main())
