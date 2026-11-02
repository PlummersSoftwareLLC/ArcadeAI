"""CPU contracts for packaging only; never run the copied game or an emulator."""
import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
path=HERE/'prepare_diagnostic_package_v1.py'
spec=importlib.util.spec_from_file_location('_startup_diagnostic_packager_CPU',path)
package=importlib.util.module_from_spec(spec);spec.loader.exec_module(package)
fixture_path=HERE/'test_startup_lua_v1.py'
if hashlib.sha256(fixture_path.read_bytes()).hexdigest()!='e07e3688afcbbd1c7e7c9ba0435341519066f7d6b8dd851f0742cc40f64557f2':
    raise ValueError('Exact CPU Lua fixture required')
spec=importlib.util.spec_from_file_location('_package_CPU_Lua_fixture',fixture_path)
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary=tempfile.TemporaryDirectory(prefix='startup-package-CPU-')
        cls.parent=Path(cls.temporary.name).resolve()
        cls.output=cls.parent/'isolated-package'
        cls.result=package.prepare(cls.output)
        cls.manifest=package.decode(package.read(Path(cls.result['path']))[0])
        cls.root=Path(cls.manifest['root'])
        cls.base=package.decode(package.read(package.BASE_MANIFEST)[0])

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_actual125_file_inventory_and_all_source_pins_match(self):
        manifest=self.manifest
        self.assertEqual(manifest['source_count'],125)
        self.assertEqual(len(manifest['files']),125)
        package.inventory(self.root,manifest['files'])
        for name,entry in manifest['file_pins'].items():
            raw,observed=package.read(self.root/package.relative(name))
            self.assertEqual(observed,entry)
            self.assertEqual(hashlib.sha256(raw).hexdigest(),manifest['files'][name])
        self.assertEqual(sum(x['bytes'] for x in manifest['file_pins'].values()),manifest['byte_count'])

    def test_exactly121_parent_sources_unchanged_and_two_helpers_added(self):
        changed={name for name,sha in self.base['files'].items() if self.manifest['files'][name]!=sha}
        self.assertEqual(changed,package.CHANGED)
        self.assertEqual(set(self.manifest['files'])-set(self.base['files']),package.ADDED)
        self.assertEqual(len(self.base['files'])-len(changed),121)
        for name in ('Scripts/dqn/game_journal.py','Scripts/dqn/managed_measurement.py',
                     'Scripts/dqn/model.py','Scripts/dqn/agent.py','Scripts/dqn/inference_actor.py',
                     'tools/run_frozen_sidecar.py'):
            self.assertEqual(self.manifest['files'][name],self.base['files'][name])

    def test_relocated_Lua_and_socket_copy_preserve_original_operations(self):
        lua=package.checked_builder('_package_CPU_lua_builder',HERE/'prepare_startup_lua_v1.py',
                                   self.manifest['builder_inputs']['prepare_startup_lua_v1.py'])
        server=package.checked_builder('_package_CPU_server_builder',HERE/'prepare_startup_server_v1.py',
                                      self.manifest['builder_inputs']['prepare_startup_server_v1.py'])
        original_lua=(package.BASE_ROOT/'Scripts/main.lua').read_text()
        proposed_lua=(self.root/'Scripts/main.lua').read_text()
        self.assertEqual(lua.stripped(proposed_lua),original_lua)
        self.assertIn(json.dumps(str(self.root/'Scripts/startup_prefix_v1.lua')),proposed_lua)
        runtime=fixture.Lua();runtime.run(proposed_lua,compile_only=True)
        before=(package.BASE_ROOT/'Scripts/dqn/socket_server.py').read_text()
        after=(self.root/'Scripts/dqn/socket_server.py').read_text()
        self.assertEqual(server.stripped_tree(after),ast.dump(ast.parse(before),include_attributes=False))
        compile(after,'<packaged-server-copy>','exec')

    def test_packaged_python_recorder_imports_without_game_modules_or_capture(self):
        path=self.root/'Scripts/startup_server_prefix_v1.py'
        spec=importlib.util.spec_from_file_location('_isolated_packaged_startup_helper',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        self.assertEqual(module.SCHEMA,'robotron-server-startup-prefix-v1')
        self.assertIsNone(module._active)
        self.assertNotIn('torch',sys.modules)
        self.assertFalse(any(name.startswith('dqn.') for name in sys.modules))

    def test_existing_package_refused_without_changing_immutable_sources(self):
        before={name:package.read(self.root/package.relative(name))[1] for name in self.manifest['files']}
        with self.assertRaises(ValueError):package.prepare(self.output)
        after={name:package.read(self.root/package.relative(name))[1] for name in self.manifest['files']}
        self.assertEqual(before,after)

    def test_bad_parent_manifest_hash_fails_before_output_creation(self):
        output=self.parent/'wrong-parent'
        with patch.object(package,'BASE_SHA','0'*64):
            with self.assertRaises(ValueError):package.prepare(output)
        self.assertFalse(output.exists())

    def test_bad_helper_hash_fails_before_output_creation(self):
        output=self.parent/'wrong-helper';inputs=dict(package.INPUTS)
        inputs['startup_prefix_v1.lua']='0'*64
        with patch.object(package,'INPUTS',inputs):
            with self.assertRaises(ValueError):package.prepare(output)
        self.assertFalse(output.exists())

    def test_relative_traversal_alias_and_non_source_names_fail(self):
        for name in ('../escape.py','/absolute.py','Scripts/../alias.py','Scripts//alias.py',
                     'Scripts/./alias.py','Scripts\\alias.py','Script\x00.py','Scripts/model.pt',''):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):package.relative(name)
        self.assertEqual(package.relative('Scripts/dqn/model.py'),Path('Scripts/dqn/model.py'))

    def test_declared_scope_rejects_bad_counts_hashes_and_helper_collision(self):
        for change in ('count','boolean','hash','traversal','collision'):
            value=copy.deepcopy(self.base)
            if change=='count':value['source_count']=124
            elif change=='boolean':value['source_count']=True
            elif change=='hash':value['files']['Scripts/main.lua']='x'*64
            elif change=='traversal':value['files']['../main.lua']=value['files'].pop('Scripts/main.lua')
            else:value['files']['Scripts/startup_prefix_v1.lua']=value['files'].pop('Scripts/display.lua')
            with self.subTest(change=change):
                with self.assertRaises(ValueError):package.declared_files(value)

    def test_destination_rejects_protected_and_noncanonical_paths(self):
        for output in (Path('relative'),package.GAME,package.GAME/'Scripts/new-probe-source',
                       package.GAME/'models_dqn/new-probe-source',package.BASE_ROOT/'new-probe-source',
                       self.parent/'missing-parent'/'nested',self.parent/'unsupported-\u00e9'):
            with self.subTest(output=str(output)):
                with self.assertRaises(ValueError):package.destination(output)
        link=self.parent/'linked-parent';target=self.parent/'owned-parent';target.mkdir()
        link.symlink_to(target,target_is_directory=True)
        with self.assertRaises(ValueError):package.destination(link/'new-package')

    def test_mutable_hardlinked_symlink_and_oversized_inputs_are_refused(self):
        root=self.parent/'input-fixtures';root.mkdir()
        path=root/'owned.py';path.write_bytes(b'pass\n')
        with self.assertRaises(ValueError):package.read(path)
        path.chmod(0o444)
        with self.assertRaises(ValueError):package.read(path,maximum_bytes=1)
        link=root/'linked.py';link.symlink_to(path)
        with self.assertRaises(ValueError):package.read(link)
        hard=root/'hard.py';os.link(path,hard)
        with self.assertRaises(ValueError):package.read(hard)

    def test_inventory_rejects_unlisted_files_and_directory_symlinks(self):
        root=self.parent/'inventory-fixtures';root.mkdir();(root/'extra.py').write_bytes(b'pass\n')
        with self.assertRaises(ValueError):package.inventory(root,{})
        (root/'extra.py').unlink();(root/'linked').symlink_to(self.root,target_is_directory=True)
        with self.assertRaises(ValueError):package.inventory(root,{})

    def test_late_source_mismatch_leaves_no_usable_manifest(self):
        output=self.parent/'late-mismatch';read=package.read;seen={}
        target=package.BASE_ROOT/'Scripts/main.lua'
        def checked(path,**kwargs):
            path=Path(path);seen[path]=seen.get(path,0)+1
            if path==target and seen[path]>1:raise ValueError('Injected late source PIN mismatch')
            return read(path,**kwargs)
        with patch.object(package,'read',side_effect=checked):
            with self.assertRaises(ValueError):package.prepare(output)
        self.assertTrue((output/'Robotron').is_dir())
        self.assertFalse((output/'runtime-source-package.json').exists())

    def test_default_CLI_is_plan_only_even_with_missing_output(self):
        output=self.parent/'must-not-be-created'
        result=subprocess.run([sys.executable,'-I','-B',str(HERE/'prepare_diagnostic_package_v1.py'),
                               '--output',str(output)],capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0);self.assertIn('PLAN_ONLY',result.stdout)
        self.assertFalse(output.exists())

    def test_manifest_decode_rejects_duplicates_nonfinite_and_nonobjects(self):
        for raw in (b'{"files":{},"files":{}}',b'{"n":NaN}',b'[]'):
            with self.assertRaises(ValueError):package.decode(raw)


if __name__=='__main__':
    time.sleep(2)  # Keep the original bounded CPU service birth bracketable.
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    assert 'torch' not in sys.modules and not any(name.startswith('dqn.') for name in sys.modules)
    print(json.dumps(dict(schema='robotron-startup-isolated-package-CPU-contracts-v1',tests=result.testsRun,
        failures=len(result.failures),errors=len(result.errors),successful=result.wasSuccessful(),
        scope='Actual125-file copied package in CPU temporary directories; immutable-input/path/inventory/failure contracts, Lua5.4 syntax and operational AST checks. No game-module execution, model, bank, socket or emulator.',
        production_changed=False,launch_selected=False,protocol_selected=False,real_ROM_start_proven=False)))
    sys.exit(0 if result.wasSuccessful() else 1)
