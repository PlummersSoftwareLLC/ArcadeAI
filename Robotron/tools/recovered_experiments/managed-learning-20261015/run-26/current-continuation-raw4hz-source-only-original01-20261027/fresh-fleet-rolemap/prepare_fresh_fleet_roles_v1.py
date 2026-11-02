"""Pure fresh-manifest/wrapper preparation; no install, unit or process action."""


def prepare_manifest(sources, helper, read_json=None, read_source=None):
    read_json=helper.read if read_json is None else read_json
    read_source=helper.read_bytes if read_source is None else read_source
    roles={'helper','collector','rolemap','launcher','canonical_lua','wait_library','original_wrapper'}
    helper.require(type(sources)is dict and set(sources)==roles and all(sources.values()),
        'All actual installed/source pins required; no futureinode fiction')
    rolemap=read_json(sources['rolemap'])
    parent,actor=helper.input_environments(rolemap,read_json)
    result=dict(schema='robotron-fresh192-owned-role-exec-manifest-v1',**sources,
        parent_unit=helper.UNIT,parent_argv=helper.parent_argv(),parent_environment=parent,
        actor_environment=actor,actor_args=helper.actor_argv(),fleet_tag=helper.FLEET_TAG,
        wrapper_path=helper.GAME_ROOT+'/tools/mame_with_socket_wait.sh')
    helper.validate_manifest(result,read_json,read_source)
    return result


def prepare_wrapper(actual_manifest_pin,manifest,helper,read_json=None,read_source=None):
    read_json=helper.read if read_json is None else read_json
    read_source=helper.read_bytes if read_source is None else read_source
    helper.require(read_json(actual_manifest_pin)==manifest,'Publish immutable actual manifest before wrapper')
    helper.validate_manifest(manifest,read_json,read_source)
    return helper.render_wrapper(actual_manifest_pin,manifest,read_source)


if __name__=='__main__':
    print('PLAN_ONLY: no prepare/install/launch; actual canonical RAW/source/unit facts remain unfilled')
