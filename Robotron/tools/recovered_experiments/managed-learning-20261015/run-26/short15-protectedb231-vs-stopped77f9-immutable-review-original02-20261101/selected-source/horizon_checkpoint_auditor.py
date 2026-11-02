"""Pure independent audit of one predeclared intermediate score checkpoint.

The caller must first qualify the final cutoff, raw startup prefixes, current
Main evidence and original owned closure. Captured origin witnesses do not
reconstruct every tail frame. This module makes no statistical decision.
"""
import statistics

SLOTS=list(range(4096,4128))
BOUND=3_500_000_000


def require(value,message):
    if not value:raise ValueError(message)


def integer(value,label,minimum=0):
    require(type(value)is int and value>=minimum,'Invalid '+label)
    return value


def audit_checkpoint(job,checkpoint,final,final_audit,prefixes,native,games,packet_auditor):
    require(checkpoint['schema']=='robotron-planned-first-game-score-checkpoint-v1'
        and final['schema']=='robotron-first-game-deadline-score32-v2','Exact checkpoint/final schemas required')
    require(final_audit['schema']=='robotron-deadline32-independent-score-cutoff-audit-v1'
        and final_audit['n_scored']==32 and final_audit['all32_first_start_identities_joined'] is True
        and final_audit['no_postdeadline_score_credit'] is True
        and all(final_audit[key]==final[key]for key in ('score_sum','mean_score','median_score','n_completed')),
        'Matching prior independent final-cutoff/identity audit required')
    require(native['complete'] is True and native['errors']==[]
        and native['all_original_threads_stopped'] is native['original_lease_released'] is True,
        'Original final writer/lease closure required')
    anchor=integer(checkpoint['anchor_monotonic_ns'],'checkpoint anchor')
    offset=integer(checkpoint['horizon_offset_ns'],'checkpoint offset',1)
    target=integer(checkpoint['horizon_monotonic_ns'],'checkpoint target')
    observed=integer(checkpoint['observed_monotonic_ns'],'checkpoint observation')
    require(type(job['checkpoint_offsets_ns'])is list and all(type(v)is int for v in job['checkpoint_offsets_ns'])
        and offset in job['checkpoint_offsets_ns'] and checkpoint['final_horizon_ns']==job['horizon_ns']==final['horizon_ns']
        and anchor==final['anchor_monotonic_ns'] and target==anchor+offset
        and 0<offset<job['horizon_ns'] and target<=observed<=final['seal_observed_monotonic_ns'],
        'Declared intermediate horizon/clock join differs')
    require(checkpoint['policy']==final['policy']
        and final['policy']['policy_sha256']==job['checkpoint']['sha256']
        and final['policy']['experiment']==job['measurement_label'],'Frozen selected policy differs')
    require(checkpoint['all32_original_members_retained'] is checkpoint['repeated_looks_are_not_independent_games'] is True
        and checkpoint['confidence_interval_computed'] is checkpoint['automatic_decision'] is False
        and checkpoint['full_game_quality_qualified'] is checkpoint['promotion'] is False,
        'Observation-only scope and repeated-game identity must remain explicit')
    rows=checkpoint['rows'];require(checkpoint['n_scored']==len(rows)==len(final['rows'])==32
        and [r['slot']for r in rows]==[r['slot']for r in final['rows']]==SLOTS
        and len(prefixes)==32 and {p['slot']for p in prefixes}==set(SLOTS),
        'All32 selected original members required; none may be dropped or duplicated')
    prefix_by_slot={p['slot']:p for p in prefixes};scores=[];completed=0
    for row,last in zip(rows,final['rows']):
        member=row['member'];slot=row['slot'];proof=prefix_by_slot[slot]
        require(member==last['member'] and member['slot']==slot
            and member['session']==job['sessions'][str(slot)]==proof['session']
            and member['connection']==job['connections'][str(slot)]==proof['connection']
            and member['journal_game_id']==proof['journal_game_id']
            and member['game_uid']==proof['game_uid']
            and member['start_certificate_id']==proof['certificate_identifier']
            and member['startup_nonce']==proof['nonce'],'Original prefix/member transport join differs')
        score=integer(row['score_at_horizon'],'checkpoint full score')
        require(row['score_at_anchor']==last['score_at_anchor']<=score<=last['score_at_deadline'],
            'First-game score/anchor/final ordering differs')
        witness=row['score_witness'];stamp=packet_auditor.audit_packet(witness,member,deadline=target,score=True)
        activity=row['activity'];activity_stamp=packet_auditor.audit_packet(activity,member,deadline=target)
        require(witness['origin_game_uid']==member['game_uid'] and witness['full_score']==score
            and witness['sequence']<=activity['sequence']<=last['last_activity']['sequence']
            and witness['accepted_ordinal']<=activity['accepted_ordinal']<=last['last_activity']['accepted_ordinal'],
            'Original score/activity/accepted-frame order differs')
        baseline=last['activity_at_anchor']['accepted_ordinal']
        require(row['accepted_frame_exposure']==integer(activity['accepted_ordinal']-baseline,'checkpoint exposure')
            and row['selected_first_game_accepted_frame_exposure']==max(0,witness['accepted_ordinal']-baseline),
            'Original since-anchor exposure differs')
        done=row['whole_game_complete'];retired=row['positively_retired_without_future_traffic']
        require(type(done)is bool and type(retired)is bool
            and row['status']==('completed'if done else'censored'),'Typed completion partition differs')
        if done:
            jid=member['journal_game_id'];receipt=native['completed_first_game_STOP_authorities'][str(slot)]
            require(last['whole_game_complete'] is True and row['completed_row']==last['completed_row']==games[jid]
                and row['completion_observed_ns']==last['completion_observed_ns']<=target
                and score==last['score_at_deadline']
                and native['original_slots'][str(slot)]['actual_exit']==0
                and type(native['original_slots'][str(slot)]['actual_exit'])is int,
                'Natural completed game/recorded actual child0 differs')
            require(receipt['member']==member and receipt['slot']==slot
                and receipt['session']==member['session'] and receipt['connection']==member['connection']
                and receipt['nonce']==member['startup_nonce'] and receipt['consumed_before_send'] is True
                and receipt['screen_first_game_complete'] is True
                and receipt['completion']['completed_row']==row['completed_row']
                and receipt['completion']['completion_observed_ns']==row['completion_observed_ns']
                and row['completion_observed_ns']<=receipt['consumed_monotonic_ns']<=observed,
                'Completed first-game original STOP authority differs')
            completed+=1
        else:
            require(row['completed_row'] is row['completion_observed_ns'] is None and retired is False
                and target-stamp<=BOUND and target-activity_stamp<=BOUND
                and activity['origin_game_uid']==member['game_uid']
                and (last['completion_observed_ns'] is None or last['completion_observed_ns']>target),
                'Unfinished checkpoint must retain fresh original score/activity')
        crossing=row['first_post_horizon_activity']
        if retired:
            require(done and crossing is None,'Only positively retired complete games may omit future traffic')
        else:
            require(type(crossing)is dict,'Original next exchange across the horizon required')
            crossing_stamp=packet_auditor.audit_packet(crossing,member,deadline=observed)
            require(activity_stamp<=target<crossing_stamp<=final['deadline_monotonic_ns']
                and crossing['sequence']==activity['sequence']+1
                and crossing['accepted_ordinal']-activity['accepted_ordinal']in(0,1),
                'Last-before/first-after horizon adjacency differs')
            require(done or crossing['origin_game_uid']==member['game_uid']
                or (last['whole_game_complete'] is True
                    and crossing_stamp==last['completion_observed_ns']
                    and crossing['sequence']==last['completion_sequence']),
                'A different origin game needs its actual terminal closing exchange')
        scores.append(score)
    require(checkpoint['n_completed']==completed and checkpoint['score_sum']==sum(scores)
        and checkpoint['mean_score']==statistics.mean(scores)
        and checkpoint['median_score']==statistics.median(scores),'All32 checkpoint arithmetic differs')
    return dict(schema='robotron-independent-horizon-checkpoint-audit-v1',status='PASS',
        horizon_offset_ns=offset,final_horizon_ns=job['horizon_ns'],n_scored=32,n_completed=completed,
        mean_score=statistics.mean(scores),median_score=statistics.median(scores),
        all32_original_first_game_identities_joined=True,original_crossing_or_retirement_required=True,
        no_post_horizon_score_credit=True,statistical_decision_qualified=False,
        repeated_checkpoints_are_not_independent_games=True,all_raw_tail_frames_reconstructed=False,
        full_game_quality_qualified=False,promotion=False)
