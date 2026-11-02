"""Same-.25 prospective CE4096 continuation. Definitions only; no I/O or controls.

Numerical recipe/context definitions remain the sealed f11e functions; the new
control/release seams admit only a label change at the held .25 recipe.
"""
from copy import deepcopy
from datetime import datetime, timezone
import math

SCHEMA = 'robotron-live-ce-lr-recipe-v1'
KEYS = {'priority_metric', 'batch_size', 'learning_control_lr_scale',
        'scheduled_lr', 'max_samples_per_frame'}
HELD_50 = dict(batch_size=4096, baseline_batch_size=512, epsilon=.1, expert_ratio=.1,
    n_step=3, max_samples_per_frame=8, c51_target_smoothing=0, learning_control_lr_scale=.5,
    lr_gear='climb', lr_anchor_step=0., optimizer_lr=2.5e-5, optimizer_eps=1.5e-4,
    fused=True, gamma=.995, num_atoms=51, v_min=-10., v_max=50.)

RELEASE_PIN = {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/LR25-continuation-original01-root-preparation-20261018/root-confirmed845-protected-canonical-adoption-and-source-freeze-release-20261018.json', 'sha256': '491de9ac25a8a95ff3330c818cae75250ec6d3df73608229a71be29ac04b535b', 'bytes': 60128, 'identity': {'device': 2304, 'inode': 81298133, 'bytes': 60128, 'mtime_ns': 1792342790827309529, 'ctime_ns': 1792342790828309529, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}
PREDECESSOR_PLAN_SHA = '8ac7c5729ca5d53edcbf02ddd61e9e8377b8b1d7f4d43648c2fda7ab263b0c7d'
PREDECESSOR_BINDING_SHA = 'b98dd3f00ef3961f36a2e9748b55c96751411e3945f740cee2b74d8c2bdd16c3'
REFERENCE = {'path': '/home/dave/source/repos/ArcadeAI/Robotron/models_dqn/managed-incumbents/freshCE-LR25-845M-confirmed-20261018.pt', 'sha256': 'fda8dcdf80a794b2715843dc892890296363c7586c60bae435a0925e32997ecd', 'bytes': 275197289, 'metadata': {'bytes': 291445, 'identity': {'bytes': 291445, 'ctime_ns': 1792342289299496938, 'device': 2304, 'inode': 79991793, 'mode': '0o444', 'mtime_ns': 1792342289296737183, 'nlink': 1, 'uid': 1001}, 'path': '/home/dave/source/repos/ArcadeAI/Robotron/models_dqn/managed-incumbents/freshCE-LR25-845M-confirmed-20261018.pt.json', 'sha256': 'cbae40714a55aa3ce902bb9804f5ee5545c8e995eec94210fe518946d699a2cb'}}
NATIVE_UNIT = 'robotron-quality-LR25-845M-vs-CE704-original01-20261018.service'


def require(value, message):
    if not value:
        raise ValueError(message)


def for_scale(scale):
    require(type(scale) is float and scale in (.25, .5), 'Only explicit float .25/.5 scales')
    return dict(priority_metric='ce', batch_size=4096, learning_control_lr_scale=scale,
                scheduled_lr=1.25e-5 if scale == .25 else 2.5e-5,
                max_samples_per_frame=8)


def check_recipe(value):
    require(type(value) is dict and set(value) == KEYS, 'Exact five-field recipe required')
    expected = for_scale(value['learning_control_lr_scale'])
    require(all(type(value[k]) is type(v) and value[k] == v for k, v in expected.items()),
            'Recipe changes beyond selected .25/.5 LR are forbidden')
    return deepcopy(expected)


def held_context(recipe, historical):
    """Historical startup remains .5; derive only the endpoint LR expectations."""
    recipe = check_recipe(recipe)
    require(historical == HELD_50 and all(type(historical[k]) is type(v)
            for k, v in HELD_50.items()), 'Historical strict9ef context must remain exact')
    value = deepcopy(historical)
    value.update(learning_control_lr_scale=recipe['learning_control_lr_scale'],
                 optimizer_lr=recipe['scheduled_lr'])
    return value


def from_held(value):
    require(type(value) is dict and set(value) == set(HELD_50), 'Exact full held context required')
    recipe = for_scale(value['learning_control_lr_scale'])
    expected = held_context(recipe, HELD_50)
    require(value == expected and all(type(value[k]) is type(v)
            for k, v in expected.items()), 'Only the two specified LR assertions may differ')
    return recipe


def check_control(before, after, experiment, recipe):
    recipe = check_recipe(recipe)
    require(recipe == for_scale(.25), 'Only the held same-.25 continuation is selected')
    require(type(before) is dict and type(after) is dict and type(before['lr_scale']) is float
            and before['lr_scale'] == .25 and before.get('measurement') is None,
            'Unmeasured .25 before-control required')
    require(type(experiment) is str and 0 < len(experiment) <= 80 and
            all(c.isascii() and (c.isalnum() or c in '_-') for c in experiment)
            and experiment != before['experiment'], 'New explicit continuation label required')
    require(before['epsilon_ramp']['start'] == before['epsilon_ramp']['end'] == .1,
            'Preserve held epsilon .1')
    expected = deepcopy(before)
    expected.update(experiment=experiment, lr_scale=recipe['learning_control_lr_scale'])
    require(after == expected and all(type(after[k]) is type(v) for k, v in expected.items()),
            'Only experiment label may change; held .25 and all other control values stay exact')
    return deepcopy(expected)


def release_wall_s(value):
    require(type(value['utc']) is str, 'Explicit root release UTC timestamp required')
    stamp = datetime.fromisoformat(value['utc'])
    require(stamp.tzinfo is not None and stamp.utcoffset() == timezone.utc.utcoffset(stamp)
            and math.isfinite(stamp.timestamp()) and stamp.timestamp() > 0,
            'Finite timezone-aware UTC release clock required')
    return stamp.timestamp()


def check_release(value, owner, actors=None):
    """Actual confirmed845 adoption is authority; old failures remain historical."""
    require(value['schema'] == 'robotron-root-LR25-845M-confirmed-protection-adoption-and-source-freeze-release-v1'
            and value['status'] == 'CONFIRMED_WINNER_PROTECTED_CANONICAL_REFERENCE_ADOPTED_SOURCE_FREEZE_RELEASED'
            and all(value[k] is True for k in ('source_freeze_released', 'candidate_qualified',
                'both_independent_candidate_gates_pass', 'promotion', 'protected_incumbent_changed',
                'CE_phase_75ec_unchanged', 'all21_original_LR_family_FULL_PINs_exact_through_adoption',
                'all67_source_control_unit_hashes_exact_through_adoption', 'original_CPU_wrapper_FAIL_preserved'))
            and all(value[k] is False for k in ('source_or_control_changed', 'source_changed',
                'model_structure_changed', 'quality_retry_or_extension', 'learner_rollback', 'live_learner_restored')),
            'Exact truthful confirmed845 adoption and full freeze release required')
    require(value['actual_native_plan_sha256'] == PREDECESSOR_PLAN_SHA
            and value['binding_sha256'] == PREDECESSOR_BINDING_SHA
            and value['main_original'] == {k: owner[k] for k in ('pid', 'starttime_ticks', 'invocation_id')}
            and value['original_main_owner'] == owner
            and value['CE_phase_record_sha256'] == '75ec8703405edfb250100006cab8ff44a364cbc84e33583697a985306fd21f10'
            and value['learning_control_lr_scale'] == .25 and value['effective_lr'] == 1.25e-5
            and value['held_source_counts'] == dict(producer_sources=62, controls=2, unit_files=3, total=67),
            'Current release plan/binding/owner/phase/held .25 closure differs')
    require({k:value['confirmed_checkpoint'][k] for k in ('path', 'sha256', 'bytes')} ==
            {k:REFERENCE[k] for k in ('path', 'sha256', 'bytes')}
            and value['protected_metadata'] == REFERENCE['metadata']
            and value['adopted_incumbent']['sha256'] == REFERENCE['sha256']
            and value['adopted_incumbent']['plan_sha256'] == PREDECESSOR_PLAN_SHA,
            'Actually published and adopted protected845 reference required')
    health = value['main_health']
    require(health['client_count'] == 192 and health['training_enabled'] is True
            and health['lr'] == 1.25e-5 and health['pipeline_read_error'] == ''
            and health['bank_persistence_read_error'] == ''
            and all(type(health[k]) is int and health[k] > 0 for k in
                ('training_steps', 'optimized_samples', 'learner_frame_count')),
            'Saved release facts must retain healthy same-.25 learner192')
    identities = value['main_exposure_identities']
    require(set(identities) == {'optimizer', 'replay'} and all(
            set(row) == {'process_id', 'instance_monotonic_ns', 'epoch'}
            and row['process_id'] == owner['pid'] and all(type(row[k]) is int
                and row[k] > 0 for k in row) for row in identities.values()),
            'Saved release optimizer/replay identities required')
    preserved = value['original192actors_preserved']
    require(type(preserved) is list and len(preserved) == 192 and all(
            type(row) is dict and set(row) == {'slot', 'pid', 'starttime_ticks', 'mask_matches'}
            and type(row['slot']) is int and 0 <= row['slot'] < 192
            and type(row['pid']) is int and row['pid'] > 0
            and type(row['starttime_ticks']) is int and row['starttime_ticks'] > 0
            and row['mask_matches'] is True for row in preserved)
            and {row['slot'] for row in preserved} == set(range(192))
            and len({row['pid'] for row in preserved}) == 192,
            'Authentic 192 original actor slot/PID/start/mask records required')
    if actors is not None:
        require(type(actors) is list and len(actors) == 192 and all(
                type(row) is dict and all(type(row.get(k)) is int for k in ('slot', 'pid', 'starttime_ticks'))
                for row in actors) and
                {(row['slot'], row['pid'], row['starttime_ticks']) for row in actors} ==
                {(row['slot'], row['pid'], row['starttime_ticks']) for row in preserved},
                'Fresh baseline must retain every released original actor identity')
    absent = value['current_owned_units_absent']
    require(type(absent) is list and len(absent) == 2 and all(
            row['argv'] == ['systemctl', '--user', 'show', unit, '--property=LoadState']
            and row['exit'] == 0 and row['stdout'] == 'LoadState=not-found\n'
            for row, unit in zip(absent, (NATIVE_UNIT.removesuffix('.service') + '.timer', NATIVE_UNIT))),
            'Actual named original timer/service closure must be complete')
    release_wall_s(value)
    return value
