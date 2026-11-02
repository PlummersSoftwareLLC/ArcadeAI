"""NEW entry/adoption CPU fixtures only. Never exec real MAME or touch live state.

Old fixture definitions provide synthetic accepted/mixed192 records; no old
test methods run. Process admission is explicitly injected, never live /proc.
"""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import types
import unittest

HERE = Path(__file__).resolve().parent
P = HERE.parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


class CapturedExec(Exception):
    pass


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.entry = load('_new_generic_entry', HERE / 'exec_declared_preview_entry_v1.py')
        cls.transition = load('_new_source_transition', HERE / 'owned_preview_source_transition_v1.py')
        old = P / 'accepted-preview-declared-subset-source-original01'
        cls.fixture_defs = load('_prior_fixture_definitions_NO_PRIOR_TESTS', old / 'test_declared_preview_subset_v1.py')
        cls.fixture_defs.Tests.setUpClass()
        cls.previous = cls.fixture_defs.Tests()
        cls.base = cls.previous.fixtures.Tests.execbase
        paths = dict(
            base=P / 'role-bound-wrapper-trial-original01/exec_role_bound_mame_v1.py',
            fuse=P / 'role-bound-wrapper-trial-original02-single-use/exec_role_bound_mame_once_v2.py',
            collector=Path('/home/dave/source/repos/ArcadeAI/Robotron/tools/quality_capacity_proposal/supervised_main_fleet_v2.py'),
            core=old / 'declared_preview_subset_v1.py',
            accepted=P / 'posttrial-slot163-authorities-and-readonly-reconciliation-original02-guard-corrections/posttrial_slot163_output_authority_v2.py',
            roles=P / 'posttrial-slot163-authorities-and-readonly-reconciliation-original02-guard-corrections/prepare_slot163_readonly_reconciliation_v2.py',
            transition=HERE / 'owned_preview_source_transition_v1.py')
        cls.module_pins = {role: cls.pin(path) for role, path in paths.items()}
        cls.modules = {role: load('_entry_test_' + role, path) for role, path in paths.items()}

    @classmethod
    def pin(cls, path):
        path = Path(path); raw = path.read_bytes()
        return dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw),
                    identity=cls.base.identity(path.lstat()))

    def write(self, path, value, mode=0o444):
        path = Path(path)
        path.write_bytes(value if isinstance(value, bytes) else json.dumps(value, sort_keys=True).encode())
        path.chmod(mode)
        return self.pin(path)

    def fixture(self, directory):
        fixture, plan, old_read, table, pins = self.previous.complete_plan()
        table = copy.deepcopy(table)
        # Historical fixture-only plan/current output remains synthetic. Source
        # files and the activation receipt themselves use actual temp full pins.
        prior = copy.deepcopy(table[pins['binding']['path']])
        core_pin = dict(path='/CPUfixture/core197')
        prior_pin = dict(path='/CPUfixture/source-adoption-prior')
        table[core_pin['path']] = fixture.old
        table[prior_pin['path']] = prior
        plan_pin = self.write(directory / 'selected plan.json', plan)
        activation = directory / 'activation'; activation.mkdir(mode=0o700)
        ds = activation.lstat()
        original = fixture.manifest['original_wrapper']
        config = dict(schema='robotron-generic-preview-entry-config-v1', entry_source=self.pin(HERE / 'exec_declared_preview_entry_v1.py'),
            modules=self.module_pins, plan=plan_pin, prior_binding=prior_pin, core_binding=core_pin,
            original_wrapper=original, wrapper_mode=0o555,
            activation=dict(directory=dict(path=str(activation), identity=dict(device=ds.st_dev,
                inode=ds.st_ino, mode='0o700', uid=os.getuid())), nonce='a' * 32))
        config_pin = self.write(directory / 'entry config.json', config)
        def read(pin, as_json=True):
            if pin['path'] in table:
                result = copy.deepcopy(table[pin['path']])
                if not as_json and isinstance(result, bytes): return result
                return result
            if pin['path'].startswith('/CPUfixture/'):
                return old_read(pin, as_json)
            raw = self.base.read_bytes_pin(pin)
            return self.base.strict_json(raw) if as_json else raw
        old_installed = dict(path=self.transition.INSTALLED_WRAPPER_PATH, sha256='a' * 64,
                             bytes=10, identity={})
        old_archive = dict(path='/CPUfixture/old-installed-wrapper-archive', sha256='a' * 64,
                           bytes=10, identity={})
        table[old_installed['path']] = b'old trial CPUfixture'
        table[old_archive['path']] = b'old trial CPUfixture'
        rendered = self.transition.render_wrapper(config_pin, config, read)
        stage = self.write(directory / 'rendered wrapper.sh', rendered, 0o555)
        intent_path = directory / 'immutable source intent.json'
        intent = self.transition.prepare_intent(config_pin, config, prior, old_installed, old_archive,
                                                stage, str(intent_path), read)
        intent_pin = self.write(intent_path, intent)
        installed = copy.deepcopy(stage); installed['path'] = self.transition.INSTALLED_WRAPPER_PATH
        # Only read callback substitutes the canonical path: no real installed
        # wrapper/source/current binding is written by this test.
        def installed_read(pin, as_json=True):
            if pin == installed: return rendered
            return read(pin, as_json)
        prepared = self.transition.prepare_binding_objects(config_pin, config, intent_pin, installed, installed_read)
        policy_pin = self.write(directory / 'new actual policy.json', prepared['policy'])
        binding = self.transition.finalize_binding(prepared, policy_pin, installed_read)
        binding_pin = self.write(directory / 'new actual binding.json', binding)
        snapshot = copy.deepcopy(table[pins['snapshot']['path']])
        before = self.write(directory / 'before source snapshot.json', snapshot)
        after = self.write(directory / 'after source snapshot.json', snapshot)
        observation = self.write(directory / 'actual source observation.json', dict(binding=binding_pin, summary=dict(
            all192_exact_policy_identities=True, actual_all192_CID_roles_verified=True,
            replay_optimizer_process_instance_epochs_retained=True, held_inputs=prepared['new_held_count'])))
        commit = dict(schema='robotron-owned-preview-wrapper-source-transition-commit-v1', config=config_pin,
            entry=config['entry_source'], nonce=config['activation']['nonce'], intent=intent_pin,
            installed_wrapper=installed, policy=policy_pin, binding=binding_pin,
            before_snapshot=before, after_snapshot=after, post_install_readonly_observation=observation)
        return locals()

    def test_default_is_inert_and_templates_fail_closed(self):
        process = subprocess.run(['/usr/bin/python3.12', '-I', '-B', str(HERE / 'exec_declared_preview_entry_v1.py')],
                                 capture_output=True, text=True, timeout=5)
        self.assertEqual(process.returncode, 0); self.assertIn('PLAN_ONLY', process.stdout)
        with self.assertRaises(ValueError): self.transition.validate_config(dict.fromkeys(self.transition.CONFIG_KEYS))

    def test_actual_fixed_source_loader_and_wrong_role_pin(self):
        with tempfile.TemporaryDirectory(prefix='entry loader ') as d:
            f = self.fixture(Path(d))
            modules, read = self.entry.load_runtime(f['config_pin'], f['config'], f['config']['entry_source'])
            self.assertEqual(set(modules), set(self.entry.EXPECTED_MODULES))
            wrong = copy.deepcopy(f['config']); wrong['modules']['core']['sha256'] = '0' * 64
            with self.assertRaises(ValueError): self.entry.load_runtime(f['config_pin'], wrong, wrong['entry_source'])

    def test_rendered_shell_preserves_literal_arguments_and_wait_prefix(self):
        with tempfile.TemporaryDirectory(prefix='entry quote $ ; ') as d:
            f = self.fixture(Path(d)); config = copy.deepcopy(f['config'])
            fake = Path(d) / "fake entry $ ; ' only.py"
            self.write(fake, b'import json,sys,os\nprint(json.dumps(dict(args=sys.argv[1:],preload=os.environ.get("LD_PRELOAD"))))\n')
            config['entry_source'] = self.pin(fake)
            rendered = self.transition.render_wrapper(f['config_pin'], config, f['read'])
            wrapper = Path(d) / 'wrapper shell.sh'; wrapper.write_bytes(rendered)
            source = f['read'](config['original_wrapper'], False)
            self.assertEqual(rendered.split(b'exec env -u LD_PRELOAD')[0], source.split(b'exec env LD_PRELOAD=')[0])
            env = dict(os.environ); env.update(f['fixture'].manifest['slots']['0']['expected_environment'])
            env.pop('LD_PRELOAD', None)
            literal = ["spaces ; $(not-a-command) `literal` ' \"", '-autoboot_script', '/literal old.lua']
            process = subprocess.run(['/bin/bash', str(wrapper), *literal], env=env,
                                     capture_output=True, text=True, timeout=5)
            self.assertEqual(process.returncode, 0, process.stderr)
            output = json.loads(process.stdout)
            self.assertEqual(output['args'][-len(literal):], literal); self.assertIsNone(output['preload'])

    def test_owned_source_commit_is_exact_and_registry_preserving(self):
        with tempfile.TemporaryDirectory(prefix='entry adoption ') as d:
            f = self.fixture(Path(d))
            result = self.transition.validate_commit(f['commit'], f['config_pin'], f['config'],
                                                     f['config']['entry_source'], f['installed_read'])
            self.assertTrue(result['source_transition_verified'])
            old = f['prior']['held_hashes']; new = f['binding']['held_hashes']
            self.assertEqual({path for path in old if new[path] != old[path]}, {self.transition.INSTALLED_WRAPPER_PATH})
            self.assertEqual(f['prepared']['policy']['baseline_actors'], f['prior']['actors'] and
                             f['table'][f['prior']['supervision_policy']['path']]['baseline_actors'])
            self.assertEqual(f['prepared']['new_held_count'], len(new))

    def test_wrong_installed_source_or_changed_actor_or_core_hold_refuses(self):
        for kind in ('installedSHA', 'nonce', 'actor', 'core', 'observer'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory(prefix='entry reject ') as d:
                f = self.fixture(Path(d)); commit = copy.deepcopy(f['commit'])
                if kind == 'installedSHA': commit['installed_wrapper']['sha256'] = '0' * 64
                if kind == 'nonce': commit['nonce'] = 'b' * 32
                if kind == 'actor':
                    snap = copy.deepcopy(f['snapshot']); snap['actors']['0']['pid'] += 1
                    commit['after_snapshot'] = self.write(Path(d) / 'wrong actor.json', snap)
                if kind == 'core':
                    core = f['table'][f['core_pin']['path']]
                    core['held_hashes'][next(iter(core['held_hashes']))] = '0' * 64
                if kind == 'observer':
                    value = dict(binding=f['binding_pin'], summary=dict(all192_exact_policy_identities=False))
                    commit['post_install_readonly_observation'] = self.write(Path(d) / 'bad observation.json', value)
                with self.assertRaises(ValueError):
                    self.transition.validate_commit(commit, f['config_pin'], f['config'],
                                                     f['config']['entry_source'], f['installed_read'])

    def test_owned_receipt_requires_private_directory_and_regular_frozen_file(self):
        with tempfile.TemporaryDirectory(prefix='entry commit ') as d:
            f = self.fixture(Path(d)); path = Path(f['activation']) / self.transition.COMMIT_NAME
            with self.assertRaises(FileNotFoundError):
                self.transition.read_owned_commit(f['config'], self.modules['accepted'], self.base)
            self.write(path, f['commit'])
            commit, pin = self.transition.read_owned_commit(f['config'], self.modules['accepted'], self.base)
            self.assertEqual(commit, f['commit']); self.assertEqual(pin, self.pin(path))
            f['activation'].chmod(0o777)
            with self.assertRaises(ValueError):
                self.transition.read_owned_commit(f['config'], self.modules['accepted'], self.base)

    def test_real_plan_and_commit_join_and_benchmark_gate(self):
        with tempfile.TemporaryDirectory(prefix='entry actual context ') as d:
            f = self.fixture(Path(d)); self.write(f['activation'] / self.transition.COMMIT_NAME, f['commit'])
            prepared = self.entry.prepare_context(f['config_pin'], f['config'], f['config']['entry_source'],
                                                 self.modules, f['installed_read'])
            self.assertEqual(prepared['context']['newly_declared_slots'], [0, 1])
            f['table'][f['pins']['selection']['path']]['operational_benchmark_accepted'] = False
            with self.assertRaises(ValueError):
                self.entry.prepare_context(f['config_pin'], f['config'], f['config']['entry_source'],
                                           self.modules, f['installed_read'])

    def test_actual_dispatch_literal_train2_eval1_undeclared0_no_real_MAME(self):
        with tempfile.TemporaryDirectory(prefix='entry capture exec ') as d:
            f = self.fixture(Path(d)); self.write(f['activation'] / self.transition.COMMIT_NAME, f['commit'])
            modules = dict(self.modules); observed = []
            modules['fuse'] = types.SimpleNamespace(verify_parent=lambda authority, collector:
                observed.append(copy.deepcopy(authority)))
            prepared = self.entry.prepare_context(f['config_pin'], f['config'], f['config']['entry_source'],
                                                 modules, f['installed_read'])
            captured = []
            def fake_exec(path, command, environment):
                captured.append((path, command, environment)); raise CapturedExec()
            for slot, mode in ((0, '2'), (1, '1'), (2, '0')):
                row = f['fixture'].manifest['slots'][str(slot)]
                env = dict(row['expected_environment'], EXTRA_LITERAL="spaces $ ; ' ` untouched")
                with self.assertRaises(CapturedExec):
                    self.entry.admit(prepared, row['expected_args'], env, modules, f['installed_read'], fake_exec)
                path, command, output = captured[-1]
                self.assertEqual(path, '/usr/games/mame')  # captured only, NEVER executed
                self.assertEqual(output['ROBOTRON_EVAL_MODE'], mode)
                self.assertEqual(output['EXTRA_LITERAL'], env['EXTRA_LITERAL'])
                self.assertEqual(observed[-1]['prior_actor'], f['plan'] and
                    prepared['context']['current_registry']['actors'][str(slot)])
                expected = 'original_lua' if slot == 2 else 'target_lua'
                self.assertEqual(command[command.index('-autoboot_script') + 1], f['fixture'].manifest[expected]['path'])
            self.assertEqual(len(captured), 3)


if __name__ == '__main__':
    unittest.main()
