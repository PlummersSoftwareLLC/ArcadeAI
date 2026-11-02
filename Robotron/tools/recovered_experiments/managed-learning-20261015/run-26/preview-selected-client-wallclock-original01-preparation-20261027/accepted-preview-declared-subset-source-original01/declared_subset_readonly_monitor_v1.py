"""Prospective read-only monitor definitions. CLI/import do not observe or write.

ROOT provides authenticated existing modules and actual newly published binding.
Only observe_once explicitly reads process/source/API metadata; never control.
"""
import time
import urllib.request
from pathlib import Path


def require(value, message):
    if not value:
        raise ValueError(message)


def observe_once(binding, policy, read, linux, window, raw, selected, normalise, reconciliation):
    require(binding['supervision_policy'] is not None
            and binding['preview_subset_transition'] is not None, 'Actual future binding is unfilled')
    require(read(binding['supervision_policy']) == policy, 'New policy pin differs')
    linux.live_owner(binding['owner'])
    window.owner_and_files(binding)  # All original197+ plus installed sources; no model bodies.
    snapshot = selected.collect(policy)
    with urllib.request.urlopen('http://127.0.0.1:8771/api/now', timeout=5) as response:
        wire = response.read(raw.MAX_WIRE_BYTES + 1)
    api = raw.parse_wire(wire)
    selected.validate_snapshot(policy, snapshot, api['client_count'])
    require(reconciliation.roles(api) == binding['preview_actual_roles'],
            'Another CID/role changed; trial is invalid rather than silently adopted')
    window.healthy(api, read(binding['baseline_API']), binding['experiment'], time.time())
    current = normalise(api); baseline = binding['preview_before_exposure']
    window.progress(current, baseline, baseline)
    require(current['optimizer_identity']['process_id'] == current['replay_identity']['process_id']
            == binding['owner']['pid'], 'Trainer/replay/optimizer continuity changed')
    latest = Path('/home/dave/source/repos/ArcadeAI/Robotron/models_dqn/robotron_dqn_latest.pt')
    age = time.time() - latest.stat().st_mtime
    require(0 <= age <= 360 and latest.stat().st_size > 200 << 20, 'Autosave stale/future/empty')
    return dict(schema='robotron-preview-declared-subset-reconciled-main-readonly-observation-v1',
                client_count=api['client_count'], held_inputs=len(binding['held_hashes']),
                original_trainer_and_supervisor_retained=True, all192_exact_policy_identities=True,
                actual_all192_CID_roles_verified=True, declared_override_slots=policy['preview_override_slots'],
                per_slot_source_and_actual_role_map_verified=True,
                replay_optimizer_process_instance_epochs_retained=True,
                learner_frame_count=api['learner_frame_count'], training_steps=api['training_steps'],
                optimized_samples=api['optimized_samples'], autosave_age_s=age,
                no_model_body_read_or_runtime_changes=True, quality_qualification=False)


if __name__ == '__main__':
    print('PLAN_ONLY: no current observation, capture, source write or binding adoption')
