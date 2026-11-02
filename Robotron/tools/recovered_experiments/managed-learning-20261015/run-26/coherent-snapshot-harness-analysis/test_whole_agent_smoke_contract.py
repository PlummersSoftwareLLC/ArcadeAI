"""CPU-only import/production-API contracts; never imports Torch or the trainer."""
import ast
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from unittest.mock import Mock

from . import whole_agent_smoke as parent
from . import whole_agent_smoke_worker as worker


def parse(name):
    path=parent.GAME/'Scripts/dqn'/name
    return ast.parse(path.read_text())


class WholeAgentContracts(unittest.TestCase):
    def test_worker_configuration_names_match_actual_dataclass_and_module(self):
        config=parse('config.py')
        definition=next(node for node in config.body if isinstance(node,ast.ClassDef) and node.name=='RLConfigData')
        fields={node.target.id for node in definition.body if isinstance(node,ast.AnnAssign) and isinstance(node.target,ast.Name)}
        source=ast.parse(Path(worker.__file__).read_text())
        used={node.attr for node in ast.walk(source) if isinstance(node,ast.Attribute) and
              (isinstance(node.value,ast.Name) and node.value.id=='cfg' or
               isinstance(node.value,ast.Attribute) and isinstance(node.value.value,ast.Name) and
               node.value.value.id=='ctx' and node.value.attr=='cfg')}
        self.assertEqual(used-fields,set(), 'Worker references a nonexistent production config field')
        setup=next(node for node in source.body if isinstance(node,ast.FunctionDef) and node.name=='setup')
        values=next(node.value for node in ast.walk(setup) if isinstance(node,ast.Assign) and
                    any(isinstance(target,ast.Name) and target.id=='values' for target in node.targets))
        overrides={keyword.arg for keyword in values.keywords}
        self.assertEqual(overrides-fields,set(), 'Bounded override field was renamed in production')
        self.assertIn('replay_tmpfs_dir',overrides)
        constants=set()
        for node in config.body:
            if isinstance(node,ast.Assign):
                constants.update(target.id for target in node.targets if isinstance(target,ast.Name))
        uses={node.attr for node in ast.walk(source) if isinstance(node,ast.Attribute) and
              isinstance(node.value,ast.Attribute) and isinstance(node.value.value,ast.Name) and
              node.value.value.id=='ctx' and node.value.attr=='config' and node.attr.isupper()}
        self.assertEqual(uses-constants,set())

    def test_actual_api_keywords_exist_without_importing_production(self):
        def method(filename,classname,name):
            module=parse(filename)
            cls=next(node for node in module.body if isinstance(node,ast.ClassDef) and node.name==classname)
            return next(node for node in cls.body if isinstance(node,ast.FunctionDef) and node.name==name)
        cases=[('agent.py','RainbowAgent','__init__',{'state_size'}),
               ('agent.py','RainbowAgent','load',{'filepath','show_status'}),
               ('replay_buffer.py','PrioritizedReplayBuffer','hof_admit',{'indices','game_score','game_uid','level'}),
               ('replay_buffer.py','PrioritizedReplayBuffer','ephof_admit',{'indices','episode_score','game_uid','level'}),
               ('replay_buffer.py','PrioritizedReplayBuffer','_wait_bank_writer',{'timeout'}),
               ('prefetch.py','ReplayPrefetcher','get',{'timeout'}),
               ('socket_server.py','SocketServer','__init__',{'host','port','agent'})]
        for filename,classname,name,expected in cases:
            function=method(filename,classname,name)
            names={item.arg for item in function.args.args+function.args.kwonlyargs}
            self.assertTrue(expected<=names,(filename,name,expected-names))
        staged=ast.parse((parent.HERE/'staged/Robotron/Scripts/dqn/socket_server.py').read_text())
        cls=next(node for node in staged.body if isinstance(node,ast.ClassDef) and node.name=='AsyncReplayBuffer')
        barrier=next(node for node in cls.body if isinstance(node,ast.FunctionDef) and node.name=='barrier_async')
        self.assertIn('timeout',{item.arg for item in barrier.args.args})

    def test_environment_uses_the_production_exposure_enable_key(self):
        source=parse('learning_exposure.py')
        enable=next(node for node in source.body if isinstance(node,ast.FunctionDef) and node.name=='exposure_enabled')
        keys={node.value for node in ast.walk(enable) if isinstance(node,ast.Constant) and
              isinstance(node.value,str) and node.value.startswith('DQN_')}
        environment=parent.configure_environment(parent.Layout(Path('/private/output'),'a'*32),'capture')
        self.assertTrue(keys)
        self.assertTrue(all(environment.get(name)=='1' for name in keys))

    def test_top_level_parent_and_worker_have_no_numerical_imports(self):
        for module in (parent,worker):
            tree=ast.parse(Path(module.__file__).read_text())
            imports=[]
            for node in tree.body:
                if isinstance(node,ast.Import):imports.extend(alias.name for alias in node.names)
                if isinstance(node,ast.ImportFrom):imports.append(node.module)
            self.assertFalse(any(name.split('.')[0] in ('numpy','torch','dqn') for name in imports))

    def test_failed_worker_bootstrap_cannot_reach_numerical_setup(self):
        with patch.object(worker,'bootstrap',side_effect=RuntimeError('guard failed')) as guard, \
             patch.object(worker,'setup') as setup:
            with self.assertRaisesRegex(RuntimeError,'guard failed'):
                worker.main(['--manifest','/unowned/manifest.json','--phase','capture'])
            setup.assert_not_called()

    def test_worker_waits_for_parent_token_before_cgroup_membership_read(self):
        with tempfile.TemporaryDirectory() as temporary:
            output=Path(temporary)
            layout=parent.Layout(output,'a'*32,output/'shm')
            manifest=dict(explicit_launch=True,schema='robotron-private-whole-agent-smoke-v1',
                gpu_uuid=parent.GPU0_UUID,forbidden_gpu_uuid=parent.MAIN_GPU_UUID,bounds=parent.BOUNDS,
                parent={'pid':12345},output=str(output),nonce='a'*32,tmpfs=str(layout.tmpfs),
                output_identity={},tmpfs_identity={},launcher_sha256='hash',worker_sha256='hash',
                launch_token='secret')
            file=output/'launch-manifest.json'
            file.write_text(json.dumps(manifest))
            fake=SimpleNamespace(GPU0_UUID=parent.GPU0_UUID,MAIN_GPU_UUID=parent.MAIN_GPU_UUID,
                BOUNDS=parent.BOUNDS,Layout=parent.Layout,regular=parent.regular,
                identity=Mock(return_value={'pid':12345}),check_directory=Mock(),digest=Mock(return_value='hash'))
            with patch.object(worker,'launcher_module',return_value=fake), \
                 patch.object(worker,'arm_parent_death_signal') as death, \
                 patch.object(worker,'reset_inherited_signal_mask') as reset, \
                 patch.object(worker.os,'getppid',return_value=12345):
                with self.assertRaisesRegex(RuntimeError,'Missing parent launch token'):
                    worker.bootstrap(file,'capture',token_reader=lambda:b'wrong\n')
                death.assert_called_once_with(12345)
                reset.assert_called_once_with()
                # There is no cgroup key: inspecting it before the token would
                # raise KeyError instead of the required token rejection.
                self.assertEqual(fake.check_directory.call_count,2)

    def test_parent_death_protection_checks_syscall_and_parent_race(self):
        libc=SimpleNamespace(prctl=Mock(return_value=0))
        with patch.object(worker.os,'getppid',return_value=12):
            worker.arm_parent_death_signal(12,libc=libc)
            self.assertEqual(libc.prctl.call_args.args[0],1)
            with self.assertRaisesRegex(RuntimeError,'Parent exited'):
                worker.arm_parent_death_signal(99,libc=libc)
        libc.prctl.return_value=-1
        with self.assertRaisesRegex(RuntimeError,'Unable to arm'):
            worker.arm_parent_death_signal(12,libc=libc)
        with patch.object(worker.signal,'pthread_sigmask') as mask:
            worker.reset_inherited_signal_mask()
            mask.assert_called_once_with(worker.signal.SIG_UNBLOCK,
                (worker.signal.SIGINT,worker.signal.SIGTERM,worker.signal.SIGHUP))

    def test_delegated_cgroup_requires_empty_owned_service_supervisor_topology(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            mount=root/'cgroup'
            service=mount/'user.slice/robotron-snapshot-smoke-test.service'
            supervisor=service/'snapshot-supervisor'
            supervisor.mkdir(parents=True)
            (service/'cgroup.procs').write_text('')
            (service/'cgroup.controllers').write_text('cpu memory pids')
            (service/'cgroup.subtree_control').write_text('')
            proc=root/'self-cgroup'
            proc.write_text('0::/user.slice/robotron-snapshot-smoke-test.service/snapshot-supervisor\n')
            self.assertEqual(parent.cgroup_parent(proc_file=proc,mount=mount),service)
            self.assertEqual((service/'cgroup.subtree_control').read_text(),'') # validation is read-only
            (service/'cgroup.procs').write_text('123\n')
            with self.assertRaisesRegex(RuntimeError,'empty of processes'):
                parent.cgroup_parent(proc_file=proc,mount=mount)
            session=mount/'user.slice/session-841.scope'
            session.mkdir()
            proc.write_text('0::/user.slice/session-841.scope\n')
            with self.assertRaisesRegex(RuntimeError,'session cgroups are forbidden'):
                parent.cgroup_parent(proc_file=proc,mount=mount)

    def test_candidate_module_cannot_resolve_to_production_tree(self):
        layout=parent.Layout(Path('/private/output'),'a'*32)
        with patch.dict(sys.modules,{'dqn.private_escape_probe':SimpleNamespace(__file__='/production/dqn/agent.py')}):
            with self.assertRaisesRegex(RuntimeError,'escaped private package'):
                worker.assert_private_modules(layout)

    def test_private_archive_verification_rejects_drift_and_path_escape(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive=Path(temporary)/'archive'
            archive.mkdir()
            payload=archive/'model.pt'
            payload.write_bytes(b'private synthetic model')
            manifest=dict(before={'clock':1},after={'clock':1},files={
                'model.pt':dict(bytes=payload.stat().st_size,sha256=parent.digest(payload))})
            (archive/'COMPLETE.json').write_text(json.dumps(manifest))
            self.assertEqual(worker.verify_archive(parent,archive),manifest)
            payload.write_bytes(b'changed')
            with self.assertRaisesRegex(RuntimeError,'hash differs'):
                worker.verify_archive(parent,archive)
            manifest['files']={'../outside':dict(bytes=0,sha256='0'*64)}
            (archive/'COMPLETE.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(RuntimeError,'escaped'):
                worker.verify_archive(parent,archive)


if __name__=='__main__':
    unittest.main()
