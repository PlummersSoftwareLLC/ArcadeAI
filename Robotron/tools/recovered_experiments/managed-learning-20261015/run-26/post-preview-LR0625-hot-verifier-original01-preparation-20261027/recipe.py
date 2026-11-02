"""One explicit prospective CE4096 LR.0625 recipe; definitions only."""
from copy import deepcopy

SCHEMA='robotron-live-ce-one-field-hot-LR0625-recipe-v1'
KEYS={'priority_metric','batch_size','learning_control_lr_scale','scheduled_lr','max_samples_per_frame'}
HELD_50=dict(batch_size=4096,baseline_batch_size=512,epsilon=.1,expert_ratio=.1,
    n_step=3,max_samples_per_frame=8,c51_target_smoothing=0,learning_control_lr_scale=.5,
    lr_gear='climb',lr_anchor_step=0.,optimizer_lr=2.5e-5,optimizer_eps=1.5e-4,
    fused=True,gamma=.995,num_atoms=51,v_min=-10.,v_max=50.)


def require(value,message):
    if not value:raise ValueError(message)


def typed(value):
    if isinstance(value,dict):return(type(value).__name__,tuple((k,typed(v))for k,v in sorted(value.items())))
    if isinstance(value,list):return(type(value).__name__,tuple(typed(v)for v in value))
    return(type(value).__name__,value)


def for_scale(scale):
    require(type(scale)is float and scale==.0625,'This prospective companion accepts only explicit float .0625')
    return dict(priority_metric='ce',batch_size=4096,learning_control_lr_scale=.0625,
                scheduled_lr=3.125e-6,max_samples_per_frame=8)


def check_recipe(value):
    require(type(value)is dict and set(value)==KEYS,'Exact five-field recipe required')
    expected=for_scale(value['learning_control_lr_scale'])
    require(typed(value)==typed(expected),'Only the selected LR.0625 full recipe is permitted')
    return deepcopy(expected)


def held_context(recipe,historical):
    recipe=check_recipe(recipe)
    require(typed(historical)==typed(HELD_50),'Raw historical strict9ef context must remain exact')
    return dict(deepcopy(historical),learning_control_lr_scale=.0625,optimizer_lr=3.125e-6)


def from_held(value):
    require(type(value)is dict and set(value)==set(HELD_50),'Exact full held context required')
    recipe=for_scale(value['learning_control_lr_scale'])
    require(typed(value)==typed(held_context(recipe,HELD_50)),'Full context differs beyond selected LR assertions')
    return recipe


def check_control(before,after,experiment,recipe):
    """Exactly one JSON value changes: lr_scale .125→.0625; label stays put."""
    recipe=check_recipe(recipe)
    require(type(before)is dict and type(after)is dict and set(before)==set(after)
            and type(before.get('lr_scale'))is float and before['lr_scale']==.125,
            'Exact float .125 before-control and equal fields required')
    require(type(experiment)is str and experiment==before['experiment']==after['experiment'],
            'Actual training experiment must remain unchanged')
    require(before['epsilon_ramp']['start']==before['epsilon_ramp']['end']==.1,
            'Preserve held epsilon .1')
    expected=deepcopy(before);expected['lr_scale']=recipe['learning_control_lr_scale']
    require(typed(after)==typed(expected),'Only lr_scale may change, with all other JSON values/types preserved')
    return expected
