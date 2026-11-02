"""Two explicit CE4096 recipes. Definitions only; no I/O or mutable controls."""
from copy import deepcopy

SCHEMA = 'robotron-live-ce-lr-recipe-v1'
KEYS = {'priority_metric', 'batch_size', 'learning_control_lr_scale',
        'scheduled_lr', 'max_samples_per_frame'}
HELD_50 = dict(batch_size=4096, baseline_batch_size=512, epsilon=.1, expert_ratio=.1,
    n_step=3, max_samples_per_frame=8, c51_target_smoothing=0, learning_control_lr_scale=.5,
    lr_gear='climb', lr_anchor_step=0., optimizer_lr=2.5e-5, optimizer_eps=1.5e-4,
    fused=True, gamma=.995, num_atoms=51, v_min=-10., v_max=50.)


def require(value, message):
    if not value:
        raise ValueError(message)


def for_scale(scale):
    require(type(scale) is float and scale in (.125, .5), 'Only explicit float .125/.5 scales')
    return dict(priority_metric='ce', batch_size=4096, learning_control_lr_scale=scale,
                scheduled_lr=6.25e-6 if scale == .125 else 2.5e-5,
                max_samples_per_frame=8)


def check_recipe(value):
    require(type(value) is dict and set(value) == KEYS, 'Exact five-field recipe required')
    expected = for_scale(value['learning_control_lr_scale'])
    require(all(type(value[k]) is type(v) and value[k] == v for k, v in expected.items()),
            'Recipe changes beyond selected .125/.5 LR are forbidden')
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
    require(type(before) is dict and type(after) is dict and before['lr_scale'] == .5
            and before.get('measurement') is None, 'Unmeasured .5 before-control required')
    require(type(experiment) is str and 0 < len(experiment) <= 80 and
            all(c.isascii() and (c.isalnum() or c in '_-') for c in experiment)
            and experiment != before['experiment'], 'New explicit continuation label required')
    require(before['epsilon_ramp']['start'] == before['epsilon_ramp']['end'] == .1,
            'Preserve held epsilon .1')
    expected = deepcopy(before)
    expected.update(experiment=experiment, lr_scale=recipe['learning_control_lr_scale'])
    require(after == expected and all(type(after[k]) is type(v) for k, v in expected.items()),
            'Only experiment label and LR scale may change')
    return deepcopy(expected)


def check_release(value, owner, actors=None):
    """Current failed quality is preserved; startup46f is separate history."""
    require(value['schema'] == 'robotron-root-complete-not-improved-campaign-ownedclosure-and-source-freeze-release-v1'
            and value['source_freeze_released'] is True and value['outcome'] == 'not_improved'
            and value['both_independent_candidate_gates_pass'] is False
            and value['candidate_qualified'] is False and value['promotion'] is False
            and value['protected_incumbent_changed'] is False
            and value['CE_phase_75ec_unchanged'] is True
            and value['source_or_control_changed'] is False
            and value['model_structure_changed'] is False,
            'Honest complete not-improved release required')
    require(value['actual_native_plan_sha256'] == '30afaefd29132f2f75d115a07c35278a490b5948ddfb8a3717f759dc1ab70bce'
            and value['binding_sha256'] == 'a16c29c4c169de3ceda8a3d02bcbfed179f8f32c0de6adaead572bf1c59ddd47'
            and value['main_original'] == {k: owner[k] for k in ('pid', 'starttime_ticks', 'invocation_id')},
            'Current release plan/binding/main differs')
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
    unit = 'robotron-' + value['campaign'].rsplit('/', 1)[-1]
    absent = value['current_owned_units_absent']
    require(type(absent) is list and len(absent) == 2 and all(
            row['argv'] == ['systemctl', '--user', 'show', unit + suffix, '--property=LoadState']
            and row['exit'] == 0 and row['stdout'] == 'LoadState=not-found\n'
            for row, suffix in zip(absent, ('.timer', '.service'))),
            'Root original timer/service closure must be complete')
    return value
