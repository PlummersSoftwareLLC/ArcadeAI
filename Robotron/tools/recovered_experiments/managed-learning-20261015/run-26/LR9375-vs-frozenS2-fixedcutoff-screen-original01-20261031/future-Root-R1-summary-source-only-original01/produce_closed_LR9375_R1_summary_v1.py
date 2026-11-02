"""Root-only R1 reference summary from sealed closed metadata.

Run only after Root separately verifies this case's original R1 native and all32
actors absent and its service/timer resources positively closed. The paired
outer and C1 may remain active. No outer result or C1 runtime path is read.
The unchanged parent arm/reader kernels authenticate bounded R1 JSON/text;
embedded Main summaries in result.json are discarded without following samples.
No model/raw actor/journal/API/proc/CONTROL/PUBLIC access or runtime imports.
"""
import argparse
import collections
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import statistics
import time

CASE = Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/LR9375-vs-frozenS2-fixedcutoff-screen-original01-20261031')
PREPARED_SHA = '3722a9834fb33ad5cbf8ab151a5d8e4d3972bdbb606e0af2b97f96e0d0b59cc3'
NATIVE_SHA = '8c8b95fb12c2d12cc118c708bc2a379459ef3a7128b88b9330e974064e2b5fb3'
LUA_SHA = 'a631f02980b2e7cdddd2fc15066b74ee5d5ebfac3de90a40a5833b0a5d48b66d'
CONTROLLER_SHA = '81d4f779d299ba4160c3ae8d74f8a0582cf90f3fd9638b9528c3164e8b61e094'
OUTER_SHA = 'e0c416b58b3041fa732f8cabc906f877cd921c94d0c9c4947c5c9e9bb9dcb314'
REFERENCE_SHA = '06558cbc185b76b2b44229ddfe469d2a92037e70f89de2481e8fb055f2c736ad'
CANDIDATE_SHA = 'e2fc0343e9c1bc32ec31de1ef02694177e4d4f812794d730f2e2444c8dc43c63'
SLOTS = list(range(4096, 4128))
AGE_NS = 3_500_000_000
HORIZON_NS = 3_600_000_000_000


def require(ok, message):
    if not ok:
        raise ValueError(message)


def integer(value, name, minimum=0):
    require(type(value) is int and value >= minimum, 'Typed integer required: ' + name)
    return value


def identity(s):
    return dict(device=s.st_dev, inode=s.st_ino, bytes=s.st_size,
                mtime_ns=s.st_mtime_ns, ctime_ns=s.st_ctime_ns,
                mode=oct(stat.S_IMODE(s.st_mode)), uid=s.st_uid, nlink=s.st_nlink)


def decode(raw):
    def pairs(items):
        out = {}
        for key, value in items:
            require(key not in out, 'Duplicate JSON key')
            out[key] = value
        return out
    def constant(value):
        raise ValueError('Non-finite JSON constant: ' + value)
    def floating(value):
        number = float(value)
        require(math.isfinite(number), 'Non-finite JSON number')
        return number
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant, parse_float=floating)


class ClosedReader:
    def __init__(self):
        self.seen = {}

    def read(self, path, pin=None, *, text=False, source=False):
        p = Path(path)
        require(p.is_absolute() and p.resolve() == p and not p.is_symlink(), 'Canonical regular path required')
        if source:
            require(pin is not None and p.suffix in ('.py', '.lua'), 'Only explicitly held source text')
        else:
            require(p.is_relative_to(CASE) and p.suffix in ('.json', '.txt'), 'Only case closed metadata/text')
            require(not any(part in ('actors', 'journal', 'main-observations') for part in p.relative_to(CASE).parts), 'Raw evidence and Main observations forbidden')
        fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            before = os.fstat(fd)
            require(stat.S_ISREG(before.st_mode) and before.st_uid == os.getuid()
                    and before.st_nlink == 1 and stat.S_IMODE(before.st_mode) == 0o444
                    and 0 <= before.st_size <= 4 << 20, 'Bounded immutable owned metadata required')
            raw = bytearray()
            while len(raw) <= before.st_size:
                block = os.read(fd, min(65536, before.st_size + 1 - len(raw)))
                if not block:
                    break
                raw.extend(block)
            require(len(raw) == before.st_size and identity(before) == identity(os.fstat(fd))
                    == identity(p.lstat()), 'Metadata changed during authenticated read')
        finally:
            os.close(fd)
        raw = bytes(raw)
        actual = dict(path=str(p), sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw), identity=identity(before))
        if pin is not None:
            require(all(actual[k] == pin[k] for k in ('path', 'sha256', 'bytes'))
                    and all(actual['identity'].get(k) == v for k, v in pin.get('identity', {}).items()), 'Held SHA/bytes/full8 drift: ' + p.name)
        old = self.seen.get(str(p))
        require(old is None or old == actual, 'Metadata changed between reads')
        self.seen[str(p)] = actual
        return raw.decode('utf-8') if text else decode(raw)

    def pin(self, path):
        return self.seen[str(Path(path))]

    def finish(self):
        for p, pin in list(self.seen.items()):
            self.read(p, pin, text=True, source=Path(p).suffix in ('.py', '.lua'))


def command_ok(command):
    require(type(command) is dict and type(command['exit']) is int and command['exit'] == 0
            and command['timed_out'] is False and command['error'] is None, 'Original archive/release command failed')


def controller_closed(reader, leg, controller, result, config):
    unit = 'robotron-LR9375-S2-fixedcutoff-score-' + leg.lower() + '-original01-20261031.service'
    require(config['unit'] == unit and controller['original']['unit'] == unit
            and controller['original']['timer'] == unit[:-8] + '.timer', 'Exact fresh original unit/timer')
    require(controller['original_exit'] == 0 and type(controller['original_exit']) is int
            and controller['original_exec_code'] == 1 and controller['original_result'] == 'success'
            and controller['unit_released'] is controller['lifecycle_complete'] is controller['audit_success'] is True
            and controller['payload_retried'] is False and controller['error'] is None
            and controller['all_six_original_archive_commands_succeeded'] is True
            and controller['original_archived_before_release'] is True, 'Original C218 positive normal0 closure required')
    original = controller['original']
    require(original['observed_live'] is True and original['pid'] == result['lease']['owner_pid']
            and original['starttime_ticks'] == result['lease']['owner_birth'], 'Original controller/native PID birth join')
    archives = controller['full_original_archives']
    require(len(archives) == 6, 'Exactly six original terminal archives')
    execution = CASE / leg / 'controller-execution-original01'
    def archived(command, allowed=(0,)):
        require(type(command['exit']) is int and command['exit'] in allowed
                and command['error'] is None and command['timed_out'] is False, 'Retained owned command failed')
        texts = {}
        for stream in ('stdout', 'stderr'):
            pin = command[stream]
            require(Path(pin['path']).parent == execution and Path(pin['path']).suffix == '.txt', 'Exact execution archive directory')
            texts[stream] = reader.read(pin['path'], pin, text=True)
        return texts, dict(line.split('=', 1) for line in texts['stdout'].splitlines() if '=' in line)
    launch_pin = controller['timer_launch_archive']
    require(Path(launch_pin['path']) == execution/'root-original-timer-launch-archive.json', 'Original timer launch archive path')
    launch = reader.read(launch_pin['path'], launch_pin)
    require(launch['schema'] == 'robotron-root-exact-audit-timer-launch-archive-v1'
            and launch['unit'] == unit and launch['timer'] == original['timer']
            and launch['timer_invocation_id'] == original['timer_invocation_id']
            and launch['original_attempt'] == 1 and launch['no_retry'] is True, 'Positive original timer provenance required even after GC')
    archived(launch['scheduling_carrier'])
    _, timer_show = archived(launch['timer_show'])
    require(timer_show['Id'] == original['timer'] and timer_show['InvocationID'] == original['timer_invocation_id']
            and timer_show['Unit'] == unit and timer_show['LoadState'] == 'loaded', 'Original launch-time timer identity')
    for index, archive in enumerate(archives):
        command_ok(archive)
        name = ('service' if index < 3 else 'timer') + '-' + ('show', 'cat', 'journal')[index % 3]
        for stream in ('stdout', 'stderr'):
            pin = archive[stream]
            require(Path(pin['path']) == execution / ('original-' + name + '-' + stream + '.txt'), 'Exact terminal archive path')
            text = reader.read(pin['path'], pin, text=True)
            if index == 0 and stream == 'stdout':
                fields = dict(line.split('=', 1) for line in text.splitlines() if '=' in line)
                require(fields['ExecMainStatus'] == '0' and fields['ExecMainCode'] == '1'
                        and fields['Result'] == 'success' and fields['InvocationID'] == original['invocation_id']
                        and fields['NRestarts'] == '0' and fields['ExecMainPID'] == str(original['pid'])
                        and fields['MainPID'] == '0', 'Same invocation terminal normal0')
    releases = controller['owned_release']
    require(len(releases) == 2 and {r['unit'] for r in releases} == {unit, original['timer']}, 'Both original owned units released')
    for release in releases:
        require(release['confirmed_absent'] is True, 'Owned release absence missing')
        _, before = archived(release['before'])
        _, final = archived(release['final'])
        require(before['Id'] == final['Id'] == release['unit'] and final['LoadState'] == 'not-found'
                and final['ActiveState'] == 'inactive' and final['SubState'] == 'dead', 'Positive released unit archive required')
        kind = release['classification']
        if kind == 'already_absent_with_original_launch_and_terminal_evidence':
            require(release['stop'] is release['reset_failed'] is None and release['final'] == release['before']
                    and before['LoadState'] == 'not-found', 'Exact already-GC positive evidence branch')
        else:
            require(before['LoadState'] == 'loaded', 'Owned release must begin with exact loaded original')
            require(before['InvocationID'] == original['invocation_id' if release['unit'] == unit else 'timer_invocation_id'], 'Release cannot target replacement invocation')
            texts, _ = archived(release['stop'], (0, 5) if kind == 'timer_autoGC_race_stop5_preserved' else (0,))
            _, after = archived(release['after_stop'])
            if kind == 'timer_autoGC_race_stop5_preserved':
                require(release['unit'] == original['timer'] and release['stop']['exit'] == 5
                        and texts['stderr'].strip() in {'Unit '+release['unit']+' not loaded.', 'Failed to stop '+release['unit']+': Unit '+release['unit']+' not loaded.'}
                        and after['LoadState'] == 'not-found' and release['final'] == release['after_stop']
                        and release['reset_failed'] is None, 'Only exact original timer auto-GC stop5 is allowed')
            elif kind == 'owned_stop_completed':
                require(after['LoadState'] == 'not-found' and release['final'] == release['after_stop']
                        and release['reset_failed'] is None, 'Exact original stop0/absence')
            else:
                require(kind == 'owned_stop_and_original_failed_state_reset' and after['ActiveState'] == 'failed'
                        and after['InvocationID'] == before['InvocationID'], 'Only exact original failed-state reset branch')
                archived(release['reset_failed'])


def validate_score_row(row, slot, job, result, anchor, policy, clocks, A, D):
    member = row['member']; orig = result['original_slots'][str(slot)]
    prefix = anchor['prefixes'][str(slot)]; witness = row['score_witness']
    at_anchor = row['score_witness_at_anchor']; activity = row['last_activity']; aa = row['activity_at_anchor']
    require(row['slot'] == member['slot'] == slot and member['session'] == job['sessions'][str(slot)]
            and member['connection'] == job['connections'][str(slot)], 'Fixed original member transport join')
    require(member['policy_sha256'] == policy['checkpoint_sha256'] and member['policy_clocks'] == clocks
            and member['measurement_generation'] == policy['measurement_generation']
            and member['experiment'] == job['label'], 'Frozen first-game policy/clock join')
    require(member['start_certificate_id'] == orig['handoff']['certificate_identifier'] == prefix['handoff']['certificate_identifier']
            and member['journal_game_id'] == orig['handoff']['journal_game_id'] == prefix['handoff']['journal_game_id']
            and orig['handoff']['new_known_start'] is orig['handoff']['game_uid_unchanged'] is True
            and orig['handoff']['previous_complete'] is orig['handoff']['previous_eligible'] is False, 'Certified original first-game prefix')
    footer = prefix['summary']['footer']
    require(footer['slot'] == slot and footer['session'] == member['session'] and footer['connection'] == member['connection']
            and prefix['summary']['continues_after_prefix'] is True, 'Prefix footer membership')
    score = integer(row['score_at_deadline'], 'full deadline score')
    require(score == row['score'] == witness['full_score'] == witness['effective_raw_score'] + witness['score_offset'], 'Full integer unwrapped score')
    for w, bound in ((witness, D), (at_anchor, A)):
        require(w['full_score'] == integer(w['effective_raw_score'], 'effective raw') + integer(w['score_offset'], 'carry')
                and w['score_offset'] % 100_000_000 == 0 and w['effective_raw_score'] >= integer(w['raw_wire_score'], 'wire raw')
                and w['origin_game_uid'] == member['game_uid'] and w['policy_sha256'] == member['policy_sha256']
                and w['measurement_generation'] == member['measurement_generation']
                and w['before_ordinal'] + 1 == w['accepted_ordinal']
                and 0 <= integer(w['completed_exchange_ns'], 'exchange clock') <= bound, 'Accepted OLDUID score provenance')
        source = w['source_witness']; state = source['origin_state']
        require(source['process_return_monotonic_ns'] == w['completed_exchange_ns']
                and source['selected_journal_game_id'] == member['journal_game_id']
                and state['game_uid'] == member['game_uid'] and state['client_slot'] == slot
                and state['eval_only'] is True and state['game_score'] == w['full_score']
                and state['measurement_generation'] == member['measurement_generation'], 'Original source score witness')
    require(row['score_at_anchor'] == at_anchor['full_score'] and row['score_observed_ns'] == witness['completed_exchange_ns']
            and row['score_observed_ns_at_anchor'] == at_anchor['completed_exchange_ns']
            and 0 <= A - at_anchor['completed_exchange_ns'] <= AGE_NS
            and 0 <= A - aa['completed_exchange_ns'] <= AGE_NS
            and aa['origin_game_uid'] == member['game_uid'], 'Fresh coherent anchor score/activity')
    require(row['score_snapshot_age_ns'] == D - row['score_observed_ns'] >= 0
            and row['activity_age_ns'] == D - activity['completed_exchange_ns'] >= 0
            and row['accepted_frame_exposure'] == integer(activity['accepted_ordinal'] - aa['accepted_ordinal'], 'accepted exposure')
            and row['selected_first_game_accepted_frame_exposure'] == max(0, witness['accepted_ordinal'] - aa['accepted_ordinal'])
            and row['first_play_level'] == 1 and row['playable_frames'] >= row['playable_frames_at_anchor'] > 0
            and row['whole_game_complete_at_anchor'] is False, 'First-game exposure/age arithmetic')
    require(orig['outputs_sealed_after_original_writer_closure'] is True and orig['original_unsealed_output_paths'] == [], 'Actor finalizer metadata sealed after writer closure')
    completed = row['whole_game_complete']
    require(type(completed) is bool and row['right_censored'] is (not completed), 'Typed completed/censored partition')
    if not completed:
        require(row['status'] == 'censored' and row['completion_observed_ns'] is row['completed_row'] is None
                and row['score_snapshot_age_ns'] <= AGE_NS and row['activity_age_ns'] <= AGE_NS
                and activity['origin_game_uid'] == member['game_uid'] and orig['expected_deadline_retirement'] is True, 'Unfinished score/activity freshness cannot be waived')
    else:
        receipt = result['completed_first_game_STOP_authorities'][str(slot)]
        terminal_row = row['completed_row']; terminal = terminal_row['terminal_confirmation']
        require(row['status'] == 'completed' and A < integer(row['completion_observed_ns'], 'completion clock') <= D
                and receipt['member'] == member and receipt['slot'] == slot
                and receipt['session'] == member['session'] and receipt['connection'] == member['connection']
                and receipt['nonce'] == member['startup_nonce'] and receipt['sequence'] > 1200
                and receipt['consumed_before_send'] is receipt['screen_first_game_complete'] is True
                and row['completion_observed_ns'] <= receipt['consumed_monotonic_ns']
                and all(row[k] == v for k, v in receipt['completion'].items()), 'Authentic completed first-game STOP metadata')
        require(terminal_row['complete'] is terminal_row['eligible'] is terminal_row['known_start'] is terminal_row['measurement_active'] is True
                and terminal_row['score'] == score and terminal_row['journal_game_id'] == member['journal_game_id']
                and terminal_row['game_uid'] == member['game_uid'] and terminal_row['client_slot'] == slot
                and terminal_row['measurement_generation'] == member['measurement_generation']
                and terminal_row['experiment'] == member['experiment'] and terminal_row['first_play_level'] == 1
                and terminal['schema'] == 'robotron-confirmed-game-reset-v1'
                and terminal['previous_game_uid'] == member['game_uid'] and terminal['previous_score'] == score
                and terminal['next_journal_game_id'] != member['journal_game_id'], 'Completed OLDUID natural-terminal join')
        require(type(row['completion_sequence']) is int and row['completion_sequence'] > witness['sequence']
                and row['completion_accepted_ordinal'] == witness['accepted_ordinal'] + 1,
                'Completion requires the next accepted closing exchange')
        if terminal['reason'] == 'zero_score_restart':
            require(score == terminal['next_score'] == 0 and terminal['previous_raw_reserves'] == 0
                    and type(terminal['next_raw_reserves']) is int and 0 < terminal['next_raw_reserves'] < 255
                    and terminal['restart_pulse'] is True and terminal['next_wave'] in (0, 1), 'Confirmed zero-score restart required')
        else:
            require(terminal['reason'] == 'score_reset' and terminal['classifier_new_game'] is True
                    and terminal['next_game_uid'] != member['game_uid'], 'Confirmed natural score reset required')
        require(orig['actual_exit'] == 0 and type(orig['actual_exit']) is int, 'Completed STOP child must be actual normal0')
    return completed


def arm(reader, leg, prepared, selected, configs):
    folder = CASE / leg; runtime = folder / 'runtime-original01'
    job_pin = prepared['jobs'][leg]['job']; job = reader.read(folder / 'job.json', job_pin)
    result = reader.read(runtime / 'result.json'); result.pop('main_samples', None)
    closed = reader.read(CASE / 'Root-controller-runtime-original01' / (leg + '-closed-and-scores.json'))
    ctl = reader.read(folder / 'controller-execution-original01/root-original-result-and-owned-release.json')
    config = reader.read(folder / 'Root-original-C218-config.json', configs['configs'][leg])
    require(closed['original_controller'] == ctl and result['original_job'] == job_pin
            and result['leg'] == job['leg'] == leg and job['output'] == str(runtime)
            and result['schema'] == 'robotron-deadline32-original-leg-result-v1'
            and result['status'] == 'ORIGINAL_DEADLINE32_SEALED_AND_CLOSED'
            and result['complete'] is True and result['errors'] == [] and result['main_health_failure'] is None
            and result['attempt'] == 1 and result['no_retry'] is True, 'Original complete error-free fresh native job required')
    require(job['screen_selection'] == prepared['selection'] and job['current_main'] == result['current_main'] == selected['current_main'], 'Selected case and Main identity epochs')
    require(config['argv'] == prepared['jobs'][leg]['argv'] and config['argv'][7] == job_pin['path']
            and config['argv'][9] == job_pin['sha256'] and config['argv'][11] == NATIVE_SHA, 'Original config argv/job/source join')
    require(job['runtime'] == prepared['selected_sources']['native'] and job['lua'] == prepared['selected_sources']['lua']
            and job['screen_support']['sha256'] == '2ccd2fbcdec7f1ca31000c5d696bf3b30ecf48c21a96b25ba01db7a6fc90787f', 'Exact native/Lua/completed-STOP support sources')
    reader.read(job['screen_support']['path'], job['screen_support'], text=True, source=True)
    reader.read(job['components']['recorder']['path'], job['components']['recorder'], text=True, source=True)
    for key in ('immutable_inputs_unchanged', 'all_original_threads_stopped', 'original_lease_released', 'screen_only'):
        require(result[key] is True, 'Native positive closure flag: ' + key)
    for key in ('main_runtime_changed', 'promotion_gates_changed', 'full_game_quality_qualified', 'improvement_qualified', 'deadline_metric_independently_qualified', 'promotion', 'score_progress_required_for_liveness'):
        require(result[key] is False, 'Unexpected claim/runtime mutation: ' + key)
    require(type(result['declared_score_stall_timeout_s']) is int and result['declared_score_stall_timeout_s'] == job['private_score_stall_timeout_s'] == 0
            and type(result['declared_lua_score_stall_timeout_s']) is int and result['declared_lua_score_stall_timeout_s'] == job['private_lua_score_stall_timeout_s'] == 4260
            and result['private_score_stall_override_applied'] is True, 'Matched typed private watchdog0/Lua4260')
    role = selected['reference' if leg == 'R1' else 'candidate']; policy = result['policy_before']
    require(policy == result['policy_after'] and result['expected_policy_clocks'] == job['expected_policy_clocks'] == role['expected_policy_clocks']
            and result['acquired_checkpoint']['sha256'] == job['checkpoint']['sha256'] == role['checkpoint']['sha256']
            and job['policy_authority'] == role['authority'], 'Selected frozen policy and four-clock authority')
    clocks = {k: role['expected_policy_clocks'][k] for k in ('learner_frame_count', 'training_steps', 'optimized_samples')}
    require(policy['checkpoint_sha256'] == role['checkpoint']['sha256'] and all(policy[k] == v for k, v in clocks.items())
            and policy['training_enabled'] is policy['replay_enabled'] is False and policy['measurement_active'] is True
            and policy['epsilon'] == policy['expert_ratio'] == 0, 'Frozen private nonlearning policy')
    require(Path(result['deadline_score_seal']['path']) == runtime / 'original-deadline-score-seal.json'
            and Path(result['deadline_anchor']['path']) == runtime / 'original-deadline-anchor.json'
            and Path(result['intentional_cleanup']['path']) == runtime / 'original-intentional-deadline-cleanup.json', 'Exact same-leg seal/anchor/cleanup paths')
    seal = reader.read(result['deadline_score_seal']['path'], result['deadline_score_seal'])
    anchor = reader.read(result['deadline_anchor']['path'], result['deadline_anchor'])
    intent = reader.read(result['intentional_cleanup']['path'], result['intentional_cleanup'])
    require(closed['score_seal'] == seal and seal['schema'] == 'robotron-first-game-deadline-score32-v2'
            and seal['fixed_denominator_valid'] is True and seal['full_game_quality_qualified'] is seal['improvement_qualified'] is False, 'Closed score seal schema/denominator')
    require(seal['policy'] == anchor['policy'] == dict(policy_sha256=policy['checkpoint_sha256'], measurement_generation=policy['measurement_generation'], experiment=job['label'], policy_clocks=clocks)
            and anchor['original_job'] == job_pin and anchor['anchor']['members'] == 32, 'Anchor policy and original-job join')
    A = integer(seal['anchor_monotonic_ns'], 'anchor', 1); D = integer(seal['deadline_monotonic_ns'], 'deadline', 1)
    T = integer(seal['seal_observed_monotonic_ns'], 'seal', 1)
    require(D - A == seal['horizon_ns'] == HORIZON_NS and T >= D and T - D == seal['cutoff_lateness_ns']
            and all(anchor['anchor'][k] == seal[k] for k in ('anchor_monotonic_ns', 'deadline_monotonic_ns', 'horizon_ns')), 'Exact3600s cutoff clocks')
    barrier = result['original_barrier']
    require(barrier == seal['barrier'] == intent['original_barrier'] and barrier['deadline_monotonic_ns'] == D
            and barrier['no_new_origin_entries'] is True and barrier['inflight'] == 0
            and D <= barrier['closed_monotonic_ns'] <= T and barrier['closed_monotonic_ns'] - D <= AGE_NS
            and barrier['entered'] == barrier['finished'], 'Original barrier must drain with no postD entry')
    ready = seal['readiness']; bd = ready['boundary']
    require(ready['all_first_play_certified'] is True and ready['policy_sha256'] == policy['checkpoint_sha256']
            and ready['measurement_generation'] == policy['measurement_generation']
            and bd['ready'] is bd['active'] is True and bd['generation'] == bd['requested_generation'] == policy['measurement_generation']
            and bd['clients'] == bd['expected'] == bd['acknowledged'] == 32 and bd['actor_slots'] == SLOTS
            and bd['pending_client_ids'] == bd['replay_pending_client_ids'] == [], 'All32 original common admission')
    rows = seal['rows']
    require(len(rows) == 32 and [r['slot'] for r in rows] == SLOTS and set(result['original_slots']) == {str(s) for s in SLOTS}, 'All32 original score rows and child slots')
    for field in ('game_uid', 'session', 'connection', 'journal_game_id', 'start_certificate_id', 'startup_nonce'):
        require(len({r['member'][field] for r in rows}) == 32, 'Distinct first-game identities: ' + field)
    completed = {r['slot'] for r in rows if validate_score_row(r, r['slot'], job, result, anchor, policy, clocks, A, D)}
    require(set(result['completed_original_normal0_slots']) == completed
            and set(result['completed_first_game_STOP_authorities']) == {str(s) for s in completed}
            and set(intent['completed_normal0_slots']).issubset(completed), 'Completed STOP/final normal0 partition; atD positive-close subset')
    require(intent['errors_before'] == [] and intent['inference_error_before'] is None
            and intent['all_unfinished_original_children_live_before_cutoff'] is True
            and intent['all32_original_origin_handlers_retained_until_common_shutdown'] is True
            and intent['score_sealed_monotonic_ns'] == T and intent['original_score_seal'] == result['deadline_score_seal']
            and T < intent['begin_monotonic_ns'] <= intent['declared_monotonic_ns'] <= intent['after_flags_monotonic_ns'], 'Seal precedes explicit intentional cleanup')
    failures = result['private_failure_events']; pending = set(SLOTS) - completed
    require({e['slot'] for e in failures} == pending and len(failures) == len(pending)
            and all(e['intentional_cleanup_flag'] is e['expected_deadline_retirement'] is True
                    and e['observed_monotonic_ns'] >= intent['after_flags_monotonic_ns']
                    and e['error'].startswith('DeadlineRetired(') for e in failures), 'Only expected postseal unfinished retirement events')
    reap = result['original_post_origin_child_reap']
    require(reap['all_original_children_reaped'] is True and reap['unknown_slots'] == [] and reap['exit_statuses_normalized'] is False
            and set(reap['original_children']) == {str(s) for s in SLOTS}
            and len({(r['pid'], r['birth']) for r in reap['original_children'].values()}) == 32, 'All32 original PID births reaped unnormalized')
    for slot, child in reap['original_children'].items():
        require(all(child[k] == result['original_slots'][slot][k] for k in ('pid', 'birth', 'actual_exit'))
                and type(child['actual_exit']) is int and child['actual_exit'] in ((0,) if int(slot) in completed else (0, -15)), 'Completed0 versus pending0/or-15 actual child exits')
    writer = result['original_writer_capture']
    require(writer['all32_client_thread_objects_retained_before_shutdown'] is writer['retained_inference_thread'] is writer['all_retained_writers_stopped'] is True
            and writer['retained_client_threads'] == writer['original_cleanup_timers_joined'] == 32
            and result['main_observer_lifecycle'] == dict(original_observer_thread_closed=True, no_child_scope_created=True)
            and result['lease']['coordinator'] == job['lease'] and result['lease']['persistent_file_preserved'] is True, 'Retained writer/observer closure and original lease release')
    restoration = result['measurement_restoration']
    require(restoration['metric_sealed'] is restoration['all_original_threads_stopped'] is True
            and restoration['measurement_active_after'] is False, 'Measurement restoration after closed writers')
    controller_closed(reader, leg, ctl, result, config)
    scores = [r['score_at_deadline'] for r in rows]; gain = sum(r['score_at_deadline'] - r['score_at_anchor'] for r in rows)
    frames = sum(r['selected_first_game_accepted_frame_exposure'] for r in rows)
    require(sum(scores) == seal['score_sum'] and statistics.mean(scores) == seal['mean_score']
            and statistics.median(scores) == seal['median_score'] and sum(sorted(scores)[15:17]) == seal['median_twice']
            and seal['n_scored'] == 32 and seal['n_completed'] == len(completed) and seal['n_censored'] == 32 - len(completed)
            and gain == seal['score_gain_since_anchor'] and frames == seal['selected_first_game_accepted_frame_exposure']
            and sum(r['accepted_frame_exposure'] for r in rows) == seal['accepted_frame_exposure'] and frames > 0, 'Independent all32 score/count/gain/frame arithmetic')
    summary = dict(policy_sha256=policy['checkpoint_sha256'], score_sum=sum(scores), mean=statistics.mean(scores), median=statistics.median(scores),
                   bottom8_mean=statistics.mean(sorted(scores)[:8]), minimum=min(scores), maximum=max(scores), n_scored=32,
                   n_completed=len(completed), n_censored=32-len(completed), score_gain_since_anchor=gain,
                   first_game_frame_exposure=frames, gain_per_first_game_frame=gain/frames,
                   first_game_frames_per_actor_second=frames/(32*3600), score_age_min_ns=min(r['score_snapshot_age_ns'] for r in rows),
                   score_age_max_ns=max(r['score_snapshot_age_ns'] for r in rows), unfinished_score_age_max_ns=max((r['score_snapshot_age_ns'] for r in rows if r['slot'] not in completed), default=None),
                   activity_age_max_ns=max(r['activity_age_ns'] for r in rows), anchor_monotonic_ns=A, deadline_monotonic_ns=D,
                   seal_lateness_ns=T-D, original_child_actual_exit_counts=dict(sorted(collections.Counter(str(r['actual_exit']) for r in reap['original_children'].values()).items())),
                   completed_STOP_normal0_slots=sorted(completed), original_controller_ended_unix_s=ctl['ended_unix_s'])
    subject = dict(native_result=reader.pin(runtime/'result.json'), score_seal=result['deadline_score_seal'], original_C218=reader.pin(folder/'controller-execution-original01/root-original-result-and-owned-release.json'))
    tokens = {r['member'][key] for r in rows for key in ('session', 'connection')}
    return summary, subject, tokens


def collect_reference():
    reader = ClosedReader()
    prepared_path = CASE / 'prepared-matched-fixed-cutoff-two-arm-DATA-NOT-LAUNCHED-v1.json'
    prepared = reader.read(prepared_path)
    require(reader.pin(prepared_path)['sha256'] == PREPARED_SHA, 'Exact frozen current-case DATA')
    selected = reader.read(prepared['selection']['path'], prepared['selection'])
    require(Path(prepared['selection']['path']) == CASE / 'Root-prospective-matched-fixed-cutoff-selection.json'
            and Path(prepared['controller_configs']['path']) == CASE / 'Root-original-controller-configs.json', 'Exact selected DATA metadata paths')
    configs = reader.read(prepared['controller_configs']['path'], prepared['controller_configs'])
    source = configs['source']; full_source = prepared['selected_sources']['controller']
    require(all(source[k] == full_source[k] for k in ('path', 'sha256', 'bytes'))
            and all(full_source['identity'][k] == v for k, v in source['identity'].items())
            and configs['ordered_legs'] == ['R1', 'C1'], 'Exact selected original controller catalogue, reduced5/full8 join')
    require(selected['ordered_legs'] == ['R1', 'C1'] and selected['screen_only'] is True and selected['promotion'] is False
            and selected['reference']['checkpoint']['sha256'] == REFERENCE_SHA
            and selected['candidate']['checkpoint']['sha256'] == CANDIDATE_SHA, 'Exact fresh reference/candidate policy selection')
    for key, sha in (('native', NATIVE_SHA), ('lua', LUA_SHA), ('controller', CONTROLLER_SHA), ('outer', OUTER_SHA)):
        pin = prepared['selected_sources'][key]
        require(pin['sha256'] == sha, 'Exact selected source role: ' + key)
        reader.read(pin['path'], pin, text=True, source=True)
    reference, subject, tokens = arm(reader, 'R1', prepared, selected, configs)
    require(len(tokens) == 64, 'All64 original R1 session/connection tokens required')
    reader.finish()
    summary = dict(reference)
    summary['mean_score'] = summary.pop('mean')
    summary['median_score'] = summary.pop('median')
    summary.update(schema='robotron-offline-closed-LR9375-S2-reference-summary-v1',
        status='PASS_SEALED_R1_ALL32_SCORE_ARITHMETIC_AND_OWNED_CLOSURE',
        observed_unix_s=time.time(), case=str(CASE), leg='R1', original_outer_tool_session=2024,
        native_result={k:subject['native_result'][k] for k in ('path', 'sha256', 'bytes')},
        score_seal=subject['score_seal'], original_C218=subject['original_C218'],
        prepared_DATA=reader.pin(prepared_path), source_and_named_metadata_inventory=list(reader.seen.values()),
        Root_R1_native32actors_and_service_timer_closed_owners_absent_attested=True,
        scope=dict(Root_owner_absence_is_explicit_prerequisite_not_live_checked_by_producer=True,
            all32_fixed_cutoff_scores_included=True, source_immutable_flags_and_owned_closure_metadata_joined=True,
            completed_before_cutoff_requires_authentic_STOP_metadata_and_child0=True,
            pending_postcutoff_child0_or_minus15_codes_preserved=True,
            original_outer_may_remain_active=True, outer_result_read=False, C1_runtime_read=False,
            pair_comparison_or_candidate_verdict=False, full_game_quality_or_IID_confidence_or_promotion_claim=False,
            raw_metric_independent_qualification=False, model_raw_evidence_CONTROL_PUBLIC_or_live_runtime_access=False,
            individual_Main_or_API_sample_paths_followed=False, embedded_Main_summary_rows_discarded=True))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--Root-confirmed-R1-native32actors-and-service-timer-closed-and-owners-absent', action='store_true')
    parser.add_argument('--source-sha256', required=True)
    args = parser.parse_args()
    require(args.Root_confirmed_R1_native32actors_and_service_timer_closed_and_owners_absent,
            'Root must first verify original R1 native/32actors absent and service/timer closed')
    require(hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == args.source_sha256, 'Exact R1 producer source SHA required')
    output = CASE / 'Root-complete-S2-reference-summary-original01.json'
    require(output.parent.resolve() == CASE and not output.exists(), 'Fresh exact reference-summary output required')
    report = collect_reference()  # No output on absent/live/failed/inconsistent R1 metadata.
    raw = (json.dumps(report, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode()
    require(len(raw) <= 128 << 10, 'Bounded R1 reference-summary report')
    fd = os.open(output, os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno()); os.fchmod(stream.fileno(), 0o444)
    directory_fd = os.open(CASE, os.O_RDONLY|os.O_DIRECTORY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
    print(json.dumps(dict(status=report['status'], summary=str(output), sha256=hashlib.sha256(raw).hexdigest(),
        bytes=len(raw), score_sum=report['score_sum'], mean_score=report['mean_score'], median_score=report['median_score']), sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
