"""Independent arithmetic/identity/cutoff audit of the new deadline32 seal.

The caller separately replays all32 raw ROM/START/clock prefixes, the full main
health stream and actual owned process/scope release. Last tail score witnesses
are bounded captured origin state, not a reconstruction of all raw tail frames.
"""
import math
import statistics
import struct

SLOTS=list(range(4096,4128))
SUPPORTED_HORIZONS_NS=(600_000_000_000, 900_000_000_000, 1_800_000_000_000, 3_600_000_000_000)
BOUND=3_500_000_000
MODULUS=100_000_000


def require(ok,message):
    if not ok:raise ValueError(message)


def integer(v,label,minimum=0):
    require(type(v) is int and v>=minimum,'Invalid '+label);return v


def audit_packet(packet,member,*,deadline,score=False):
    stamp=integer(packet['completed_exchange_ns'],'exchange completion')
    require(stamp<=deadline,'Postdeadline score or activity leaked into seal')
    source=packet['source_witness'];origin=source['origin_state'];ledger=source['ledger_snapshot']
    require(source['schema']=='robotron-deadline32-completed-origin-snapshot-v1' and
            source['process_return_monotonic_ns']==stamp<=source['snapshot_begin_monotonic_ns']<=source['snapshot_end_monotonic_ns'],
            'Successful process return/snapshot ordering differs')
    require(origin['client_slot']==member['slot'] and origin['eval_only'] is origin['measurement_active'] is True and
            origin['measurement_generation']==member['measurement_generation'],'Actual origin mode/slot/generation differs')
    require(source['selected_journal_game_id']==member['journal_game_id'] and
            packet['origin_game_uid']==origin['game_uid'] and packet['accepted_ordinal']==origin['frames'] and
            packet['sequence']==ledger['sequence'] and ledger['last_accepted_ordinal']==origin['frames'],
            'Actual origin/ledger/selected game witness differs')
    require(type(source['original_payload_sha256']) is str and len(source['original_payload_sha256'])==64,
            'Original payload commitment missing')
    raw=bytes.fromhex(source['raw_header_hex'])
    require(len(raw)==33 and struct.unpack_from('>H',raw)[0]==1890,'Original raw header geometry differs')
    if score:
        require(integer(packet['before_ordinal'],'before ordinal')+1==packet['accepted_ordinal'],
                'A score witness must be an accepted original frame')
        effective=integer(packet['effective_raw_score'],'effective raw score')
        offset=integer(packet['score_offset'],'full-score carry')
        require(effective<MODULUS and offset%MODULUS==0 and
                packet['full_score']==offset+effective==origin['game_score'] and
                origin['raw_score_prev']==effective and origin['score_offset']==offset,
                'Unwrapped full score does not match effective accepted carry state')
        require(struct.unpack_from('>I',raw,19)[0]==packet['raw_wire_score']<MODULUS and
                packet['coerced_score_dips']==origin['coerced_score_dips'],
                'Original display score/coercion witness differs')
        require(packet['policy_sha256']==member['policy_sha256'] and
                packet['measurement_generation']==member['measurement_generation'],'Score witness frozen policy differs')
    return stamp


def audit(job,result,seal,anchor,cleanup,prefixes,starts,games):
    horizon=integer(job['horizon_ns'],'selected horizon')
    require(horizon in SUPPORTED_HORIZONS_NS,'Unsupported selected horizon')
    require(seal['schema']=='robotron-first-game-deadline-score32-v2' and seal['horizon_ns']==horizon,
            'Selected supported32/horizon schema required')
    a=integer(seal['anchor_monotonic_ns'],'anchor');d=integer(seal['deadline_monotonic_ns'],'deadline')
    require(d-a==horizon and anchor['anchor']==dict(anchor_monotonic_ns=a,deadline_monotonic_ns=d,horizon_ns=horizon,members=32),
            'Common monotonic anchor/horizon differs')
    require(job['actor_slots']==SLOTS and [r['slot']for r in seal['rows']]==SLOTS and
            len(prefixes)==seal['n_scored']==32,'Exactly32 original first-game members required')
    barrier=seal['barrier']
    require(barrier==result['original_barrier'] and barrier['deadline_monotonic_ns']==d and
            barrier['no_new_origin_entries'] is True and barrier['inflight']==0 and
            barrier['entered']==barrier['finished'] and barrier['fixed_drain_bound_ns']==BOUND and
            d<=barrier['closed_monotonic_ns']<=seal['seal_observed_monotonic_ns']<=d+BOUND,
            'Fixed cutoff barrier/registered exchange closure differs')
    require(seal['cutoff_lateness_ns']==seal['seal_observed_monotonic_ns']-d and
            cleanup['score_sealed_monotonic_ns']==seal['seal_observed_monotonic_ns']<=cleanup['begin_monotonic_ns']<=
            cleanup['declared_monotonic_ns']<=cleanup['after_flags_monotonic_ns'] and cleanup['errors_before']==[] and
            cleanup['inference_error_before'] is None and cleanup['server_shutdown_set_before_owned_signals'] is True,
            'Metric must be sealed before source-ordered intentional teardown')
    policy=seal['policy'];generation=policy['measurement_generation'];ready=seal['readiness'];boundary=ready['boundary']
    require(policy['policy_sha256']==job['checkpoint']['sha256'] and policy['experiment']==job['measurement_label'] and
            policy['policy_clocks']=={k:job['expected_policy_clocks'][k]for k in ('learner_frame_count','training_steps','optimized_samples')},
            'New metric policy/clock identity differs')
    require(ready['all_first_play_certified'] is True and ready['policy_sha256']==policy['policy_sha256'] and
            ready['measurement_generation']==generation and boundary['ready'] is boundary['active'] is True and
            boundary['clients']==boundary['expected']==boundary['acknowledged']==32 and boundary['actor_slots']==SLOTS and
            boundary['generation']==boundary['requested_generation']==generation and
            boundary['pending_client_ids']==boundary['replay_pending_client_ids']==[], 'Actual32 armed generation differs')
    completed=0;scores=[];sessions=set();connections=set();game_ids=set();nonces=set()
    for row,proof in zip(seal['rows'],prefixes):
        slot=row['slot'];member=row['member'];jid=member['journal_game_id']
        require(proof['slot']==member['slot']==slot and member['session']==job['sessions'][str(slot)]==proof['session'] and
                member['connection']==job['connections'][str(slot)]==proof['connection'] and
                member['game_uid']==proof['game_uid'] and jid==proof['journal_game_id'] and
                member['start_certificate_id']==proof['certificate_identifier'] and member['startup_nonce']==proof['nonce'],
                'Scored first game differs from independently replayed original startup')
        for key,seen in (('session',sessions),('connection',connections),('journal_game_id',game_ids),('startup_nonce',nonces)):
            require(member[key]not in seen,'Original member identity repeated');seen.add(member[key])
        require({k:member[k]for k in policy}==policy,'Member frozen policy differs')
        start=starts[jid]
        require(start['client_slot']==slot and start['game_uid']==member['game_uid'] and
                start['known_start'] is start['measurement_active'] is True and start['measurement_generation']==generation and
                start['experiment']==job['measurement_label'],'Original known first-game journal start differs')
        score=integer(row['score_at_deadline'],'full score');require(score==row['score'],'Published score differs')
        witness=row['score_witness'];stamp=audit_packet(witness,member,deadline=d,score=True)
        require(witness['origin_game_uid']==member['game_uid'] and witness['full_score']==score and
                row['score_observed_ns']==stamp and row['score_snapshot_age_ns']==d-stamp,
                'Selected OLDUID score/age differs')
        anchor_score=row['score_witness_at_anchor'];anchor_stamp=audit_packet(anchor_score,member,deadline=a,score=True)
        require(anchor_score['origin_game_uid']==member['game_uid'] and anchor_score['full_score']==row['score_at_anchor'] and
                row['score_observed_ns_at_anchor']==anchor_stamp,'First-game anchor witness differs')
        activity=row['last_activity'];activity_stamp=audit_packet(activity,member,deadline=d)
        baseline=row['activity_at_anchor'];audit_packet(baseline,member,deadline=a)
        require(row['activity_age_ns']==d-activity_stamp<=BOUND and
                row['accepted_frame_exposure']==activity['accepted_ordinal']-baseline['accepted_ordinal']>=0 and
                row['selected_first_game_accepted_frame_exposure']==max(0,witness['accepted_ordinal']-baseline['accepted_ordinal']) and
                row['selected_first_game_accepted_frame_exposure']<=row['accepted_frame_exposure'],
                'Since-anchor accepted frame exposure/activity differs')
        require(row['first_play_level']==1 and row['playable_frames']>0 and
                row['playable_frames_at_anchor']>0 and type(row['whole_game_complete_at_anchor']) is bool,
                'Certified first-play exposure required')
        done=row['status']=='completed'
        require(row['status'] in ('completed','censored') and row['whole_game_complete'] is done and
                row['right_censored'] is (not done),'Completed/censored labels differ')
        if done:
            terminal=row['completed_row'];confirmation=terminal['terminal_confirmation']
            require(terminal==games[jid] and terminal['complete'] is terminal['eligible'] is True and
                    terminal['known_start'] is terminal['measurement_active'] is True and
                    terminal['score']==score==confirmation['previous_score'] and
                    terminal['game_uid']==confirmation['previous_game_uid']==member['game_uid'] and
                    terminal['journal_game_id']==jid and terminal['client_slot']==slot and
                    terminal['measurement_generation']==generation and terminal['experiment']==policy['experiment'] and
                    terminal['first_play_level']==1,'Natural completed first-game terminal differs')
            require(confirmation['schema']=='robotron-confirmed-game-reset-v1' and
                    confirmation['next_journal_game_id']!=jid and confirmation['reason'] in ('score_reset','zero_score_restart'),
                    'Disconnect/unknown termination cannot become a completed member')
            closing=row['completion_source_witness']
            closing_packet=dict(sequence=row['completion_sequence'],accepted_ordinal=row['completion_accepted_ordinal'],
                origin_game_uid=confirmation['next_game_uid'],completed_exchange_ns=row['completion_observed_ns'],source_witness=closing)
            audit_packet(closing_packet,member,deadline=d)
            require(row['completion_accepted_ordinal']==witness['accepted_ordinal']+1 and
                    row['completion_sequence']>witness['sequence'],'Terminal closing accepted exchange differs')
            if confirmation['reason']=='zero_score_restart':
                require(score==confirmation['next_score']==0 and confirmation['previous_raw_reserves']==0 and
                        0<confirmation['next_raw_reserves']<255 and confirmation['restart_pulse'] is True and
                        confirmation['next_wave'] in (0,1),'Unconfirmed zero-score restart')
            else:require(confirmation['classifier_new_game'] is True and confirmation['next_game_uid']!=member['game_uid'],'Unconfirmed reset')
            completed+=1
        else:
            require(row['completed_row'] is None and row['completion_observed_ns'] is None and d-stamp<=BOUND,
                    'Censored member must retain a fresh accepted score without fabricated completion')
        scores.append(score)
    ordered=sorted(scores);sd=statistics.stdev(scores)
    require(seal['n_completed']==completed and seal['n_censored']==32-completed and
            seal['score_sum']==sum(scores) and seal['mean_score']==statistics.mean(scores) and
            seal['median_score']==statistics.median(scores) and seal['median_twice']==ordered[15]+ordered[16] and
            seal['sd_score']==sd and seal['se_score']==sd/math.sqrt(32),'Original32 arithmetic/denominator differs')
    require(seal['score_gain_since_anchor']==sum(r['score_at_deadline']-r['score_at_anchor']for r in seal['rows']) and
            seal['accepted_frame_exposure']==sum(r['accepted_frame_exposure']for r in seal['rows']) and
            seal['selected_first_game_accepted_frame_exposure']==sum(r['selected_first_game_accepted_frame_exposure']for r in seal['rows']),
            'Original exposure totals differ')
    require(seal['fixed_denominator_valid'] is seal['source_or_runtime_faults_may_not_be_censored'] is True and
            seal['full_game_quality_qualified'] is seal['improvement_qualified'] is False,'Explicit new metric scope differs')
    return dict(schema='robotron-deadline32-independent-score-cutoff-audit-v1',n_scored=32,n_completed=completed,
        n_censored=32-completed,score_sum=sum(scores),mean_score=seal['mean_score'],median_score=seal['median_score'],
        all32_first_start_identities_joined=True,no_postdeadline_score_credit=True,full_integer_score_carry_joined=True,
        common_anchor_exposure_retained=True,pending_games_not_discarded=True,
        complete_game_quality_qualified=False,all_raw_tail_frames_reconstructed=False,
        actual_runtime_origin_snapshot_witnesses_source_bound_by_outer_review=True)
