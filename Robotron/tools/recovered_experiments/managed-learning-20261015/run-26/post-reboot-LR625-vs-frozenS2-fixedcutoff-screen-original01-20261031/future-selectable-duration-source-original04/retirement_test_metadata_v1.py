"""Synthetic native metadata for CPU fixtures, never physical closure evidence."""
from copy import deepcopy


def attach(result,seal):
    result.update(complete=True,errors=[],all_original_threads_stopped=True,original_lease_released=True,
        completed_original_normal0_slots=[],completed_first_game_STOP_authorities={},original_slots={})
    keys=('status','score','score_observed_ns','score_witness','first_play_level','playable_frames',
        'completion_observed_ns','completion_sequence','completion_accepted_ordinal','completed_row','completion_source_witness')
    for row in seal['rows']:
        slot=row['slot'];result['original_slots'][str(slot)]=dict(actual_exit=0,
            outputs_sealed_after_original_writer_closure=True,original_unsealed_output_paths=[])
        if not row['whole_game_complete']:continue
        member=row['member'];result['completed_original_normal0_slots'].append(slot)
        result['completed_first_game_STOP_authorities'][str(slot)]=dict(
            slot=slot,member=deepcopy(member),session=member['session'],connection=member['connection'],
            nonce=member['startup_nonce'],sequence=row['completion_sequence'],
            consumed_before_send=True,screen_first_game_complete=True,
            consumed_monotonic_ns=row['completion_observed_ns']+1,
            completion={key:deepcopy(row[key])for key in keys})
    return result
