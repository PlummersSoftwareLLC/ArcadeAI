"""Pure/readonly source-adoption definitions. No install, signals or publication.

Hash DAG: implementations -> config -> rendered wrapper -> intent -> policy /
binding -> commit -> external ROOT adoption index. Config names an exclusively
owned late-bound commit location/nonce; it does NOT pin the future commit SHA.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import shlex
import stat

INSTALLED_WRAPPER_PATH = '/home/dave/source/repos/ArcadeAI/Robotron/tools/mame_with_socket_wait.sh'
COMMIT_NAME = 'owned-source-transition-commit.json'
CONFIG_KEYS = {'schema', 'entry_source', 'modules', 'plan', 'prior_binding', 'core_binding',
               'original_wrapper', 'wrapper_mode', 'activation'}


def require(value, message):
    if not value:
        raise ValueError(message)


def checksum(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def validate_config(config):
    require(type(config) is dict and set(config) == CONFIG_KEYS
            and config['schema'] == 'robotron-generic-preview-entry-config-v1', 'Exact entry config required')
    require(all(config[key] is not None for key in CONFIG_KEYS - {'schema'}),
            'Future entry/config/activation facts are unfilled')
    require(type(config['wrapper_mode']) is int and 0 < config['wrapper_mode'] <= 0o777
            and config['wrapper_mode'] & 0o111, 'Explicit executable wrapper mode required')
    activation = config['activation']
    require(type(activation) is dict and set(activation) == {'directory', 'nonce'}
            and type(activation['nonce']) is str and len(activation['nonce']) == 32
            and all(c in '0123456789abcdef' for c in activation['nonce']), 'Exact owned activation contract required')


def render_wrapper(config_pin, config, read):
    validate_config(config)
    original = config['original_wrapper']
    require(original['sha256'] == '26464f5e7bf9137744a9a867c606aebc97c0beffd99331b93777c38fdee1aea8',
            'Exact original wait wrapper required')
    raw = read(original, False)
    marker = b'exec env LD_PRELOAD='
    require(raw.count(marker) == 1, 'Original exec marker differs')
    prefix = raw[:raw.index(marker)]
    args = ['env', '-u', 'LD_PRELOAD', '/usr/bin/python3.12', '-I', '-B', config['entry_source']['path'],
            '--execute', '--config', config_pin['path'], '--config-sha256', config_pin['sha256'],
            '--expected-source-sha256', config['entry_source']['sha256'], '--']
    return prefix + ('exec ' + ' '.join(shlex.quote(arg) for arg in args) + ' "$@"\n').encode()


def implementation_pins(config_pin, config):
    values = [config['entry_source'], config['original_wrapper'], config['plan'], config_pin,
              *config['modules'].values()]
    result = {}
    for pin in values:
        require(pin is not None and not pin['path'].endswith('.pt') and 0 < pin['bytes'] <= 2_000_000,
                'Only actual small source/config pins are held')
        require(pin['path'] not in result or result[pin['path']] == pin, 'Conflicting physical source aliases')
        result[pin['path']] = pin
    return result


def prepare_intent(config_pin, config, prior, old_installed_pin, old_archive_pin,
                   staged_wrapper_pin, intent_path, read):
    """Return data only. Actual installed NEW inode remains absent here."""
    validate_config(config)
    require(old_installed_pin['path'] == INSTALLED_WRAPPER_PATH
            and prior['held_hashes'].get(INSTALLED_WRAPPER_PATH) == old_installed_pin['sha256'],
            'Prior binding must hold the actual old trial/persistent wrapper')
    require(old_archive_pin['sha256'] == old_installed_pin['sha256']
            and read(old_archive_pin, False) == read(old_installed_pin, False), 'Old wrapper archive differs')
    expected = render_wrapper(config_pin, config, read)
    require(read(staged_wrapper_pin, False) == expected, 'Staged wrapper is not deterministic config+entry output')
    require(intent_path not in prior['held_hashes'], 'New exclusive intent path required')
    return dict(schema='robotron-owned-preview-wrapper-source-transition-intent-v1',
        config=config_pin, prior_binding=config['prior_binding'], old_installed_wrapper=old_installed_pin,
        old_wrapper_archive=old_archive_pin, staged_wrapper=staged_wrapper_pin,
        expected_wrapper_sha256=hashlib.sha256(expected).hexdigest(),
        installed_wrapper_path=INSTALLED_WRAPPER_PATH, desired_mode=oct(config['wrapper_mode']),
        intent_path=intent_path, nonce=config['activation']['nonce'],
        actor_or_trainer_change_authorized=False)


def expected_holds(config_pin, config, intent_pin, prior, core, wrapper_sha):
    require(len(core['held_hashes']) == 197
            and all(prior['held_hashes'].get(path) == sha for path, sha in core['held_hashes'].items()),
            'All original197 core holds must survive unchanged')
    held = copy.deepcopy(prior['held_hashes'])
    require(INSTALLED_WRAPPER_PATH in held, 'Physical wrapper transition missing from prior holds')
    held[INSTALLED_WRAPPER_PATH] = wrapper_sha
    pins = implementation_pins(config_pin, config)
    require(intent_pin['path'] not in pins, 'Intent cannot alias its source config')
    pins[intent_pin['path']] = intent_pin
    for path, pin in pins.items():
        require(path != INSTALLED_WRAPPER_PATH, 'New wrapper hash is derived, never embedded in config')
        require(path not in held or held[path] == pin['sha256'], 'Another held path would change')
        held[path] = pin['sha256']
    return held


def prepare_binding_objects(config_pin, config, intent_pin, actual_wrapper_pin, read):
    """After FUTURE install: derive policy/binding; no writes or current adoption."""
    intent = read(intent_pin); prior = read(config['prior_binding']); core = read(config['core_binding'])
    require(intent['config'] == config_pin and intent['prior_binding'] == config['prior_binding']
            and intent['nonce'] == config['activation']['nonce'], 'Selected intent differs')
    expected = render_wrapper(config_pin, config, read)
    require(actual_wrapper_pin['path'] == INSTALLED_WRAPPER_PATH
            and actual_wrapper_pin['sha256'] == intent['expected_wrapper_sha256']
            == hashlib.sha256(expected).hexdigest()
            and actual_wrapper_pin['identity']['mode'] == oct(config['wrapper_mode'])
            and actual_wrapper_pin['identity']['uid'] == os.getuid()
            and actual_wrapper_pin['identity']['nlink'] == 1
            and read(actual_wrapper_pin, False) == expected, 'Actual installed wrapper identity/bytes differ')
    held = expected_holds(config_pin, config, intent_pin, prior, core, actual_wrapper_pin['sha256'])
    for pin in implementation_pins(config_pin, config).values(): read(pin, False)
    policy = read(prior['supervision_policy'])
    next_policy = copy.deepcopy(policy); next_policy['held_hashes_sha256'] = checksum(held)
    binding = copy.deepcopy(prior)
    binding.update(held_hashes=held, supervision_policy=None, prior_binding=config['prior_binding'],
                   preview_wrapper_source_transition_intent=intent_pin,
                   preview_wrapper_source_transition_config=config_pin,
                   preview_wrapper_source_transition_kind='SOURCE_ONLY_ACTOR_REGISTRY_UNCHANGED')
    return dict(policy=next_policy, pending_binding=binding,
                actors_and_actual_OUTPUT_policy_unchanged=True, new_held_count=len(held))


def finalize_binding(prepared, actual_policy_pin, read):
    require(read(actual_policy_pin) == prepared['policy'], 'Actual new source-only policy differs')
    result = copy.deepcopy(prepared['pending_binding']); result['supervision_policy'] = actual_policy_pin
    return result


def validate_commit(commit, config_pin, config, entry_pin, read):
    require(commit['schema'] == 'robotron-owned-preview-wrapper-source-transition-commit-v1'
            and commit['config'] == config_pin and commit['entry'] == entry_pin
            and commit['nonce'] == config['activation']['nonce'], 'Owned source commit differs')
    prepared = prepare_binding_objects(config_pin, config, commit['intent'], commit['installed_wrapper'], read)
    expected = finalize_binding(prepared, commit['policy'], read)
    actual = read(commit['binding'])
    require(actual == expected, 'New physical source binding differs')
    # These are historical source-adoption observations, not a claim that all
    # old actor PIDs remain current after later accepted automatic respawns.
    before, after = read(commit['before_snapshot']), read(commit['after_snapshot'])
    prior = read(config['prior_binding']); policy = read(prior['supervision_policy'])
    require(before['actors'] == after['actors'] == policy['baseline_actors'],
            'Source-only adoption also changed actors')
    require(all(before['owners'][role]['process'] == after['owners'][role]['process']
                == policy['baseline_owners'][role]['process']
                for role in ('trainer', 'fleet')), 'Source-only adoption changed original owners')
    observation = read(commit['post_install_readonly_observation'])
    require(observation['binding'] == commit['binding']
            and observation['summary']['all192_exact_policy_identities'] is True
            and observation['summary']['actual_all192_CID_roles_verified'] is True
            and observation['summary']['replay_optimizer_process_instance_epochs_retained'] is True
            and observation['summary']['held_inputs'] == prepared['new_held_count'],
            'Actual post-install source/registry/exposure observation missing')
    return dict(source_transition_verified=True, new_binding=commit['binding'],
                held_inputs=prepared['new_held_count'], actor_source_transition_was_registry_preserving=True)


def read_owned_commit(config, accepted, base):
    """Owner/nonce-bound late receipt. Config deliberately does NOT pin its SHA."""
    directory = config['activation']['directory']
    accepted.validate_private_claim_directory(directory)
    parent_fd = os.open(directory['path'], os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        s = os.fstat(parent_fd)
        require(s.st_nlink == 2 and dict(device=s.st_dev, inode=s.st_ino, mode=oct(stat.S_IMODE(s.st_mode)), uid=s.st_uid)
                == directory['identity'], 'Activation directory changed before open')
        descriptor = os.open(COMMIT_NAME, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent_fd)
        with os.fdopen(descriptor, 'rb') as stream:
            before = os.fstat(stream.fileno())
            require(stat.S_ISREG(before.st_mode) and stat.S_IMODE(before.st_mode) == 0o444
                    and before.st_uid == os.getuid() and before.st_nlink == 1
                    and 0 < before.st_size <= 2_000_000, 'Exact immutable owned commit file required')
            raw = stream.read(2_000_001)
            require(base.identity(os.fstat(stream.fileno())) == base.identity(before), 'Commit changed during read')
        path = Path(directory['path']) / COMMIT_NAME
        require(base.identity(path.lstat()) == base.identity(before) and len(raw) == before.st_size,
                'Commit path changed during read')
        pin = dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw), identity=base.identity(before))
        return base.strict_json(raw), pin
    finally:
        os.close(parent_fd)


if __name__ == '__main__':
    print('PLAN_ONLY: no install, publication, observation, actor or source transition action')
