"""Authored stdlib metadata guards; authors have not imported or executed them."""
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import shlex
import stat
import tempfile
import types
import unittest
from unittest.mock import patch

HERE = Path(__file__).parent


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


M = module(HERE / 'collect_producer.py', '_producer_collector_contract')


def pin(path):
    data = path.read_bytes()
    return dict(path=str(path), sha256=M.sha(data), bytes=len(data), identity=M.identity(path.lstat()))


def write(path, value, mode=0o444):
    data = value if isinstance(value, bytes) else (json.dumps(value, sort_keys=True) + '\n').encode()
    path.write_bytes(data); path.chmod(mode)
    return pin(path)


class FakeHost:
    def __init__(self, fixture):
        self.fixture = fixture; self.clocks = 0; self.observations = 0

    def clock(self):
        value = self.fixture.times[self.clocks]; self.clocks += 1
        return copy.deepcopy(value)

    def observe(self, owner):
        value = self.fixture.observations[self.observations]; self.observations += 1
        return copy.deepcopy(value)

    def csv(self, path):
        return M.csv_capture(path)


class ProducerCollectorGuards(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.game = self.root / 'game'; self.run = self.root / 'run'
        (self.game / 'Scripts/dqn').mkdir(parents=True); self.run.mkdir()
        self.owner = dict(pid=12345, starttime_ticks=67890,
            unit='robotron-managed-fixture-trainer.service', invocation_id='a' * 32,
            cgroup='/user.slice/user-1001.slice/robotron-managed-fixture-trainer.service')
        self.floor = dict(training_steps=10, optimized_samples=20, learner_frame_count=30, frame_count=40)
        self.boot = dict(path=str(self.root / 'historical-boot.pt'), sha256='b' * 64, bytes=300 << 20)
        self.record = write(self.root / 'phase.json', dict(metric='ce', action='start', previous_metric='ce',
            phase_id='ce2048-fixture', root_precommit_sha256='c' * 64, checkpoint=self.boot))
        self.boot_proof = write(self.root / 'boot-proof.json', dict(status='PASS', sha256=self.boot['sha256'],
            bytes=self.boot['bytes'], clocks=self.floor, phase_metadata_verified=True,
            saved_priority_metric_phase=dict(metric='ce', valid=True)))
        self.env = dict(DQN_BATCH_SIZE='2048', DQN_PER_PRIORITY_METRIC='ce',
            DQN_PRIORITY_PHASE_RECORD=self.record['path'], DQN_PRIORITY_PHASE_RECORD_SHA256=self.record['sha256'],
            ROBOTRON_RUN_DIR=str(self.run), CUDA_VISIBLE_DEVICES='1')
        self.argv = ['/fixture/python', '/fixture/trainer.py']
        self.process = dict(pid=self.owner['pid'], starttime_ticks=self.owner['starttime_ticks'], argv=self.argv,
            uid=[os.getuid()] * 4, cgroup='0::' + self.owner['cgroup'], cwd=str(self.game), exe='/fixture/python')
        self.unit_fields = dict(MainPID=str(self.owner['pid']), ExecMainPID=str(self.owner['pid']),
            InvocationID=self.owner['invocation_id'], ControlGroup=self.owner['cgroup'], NRestarts='0', Restart='no',
            ExecMainStartTimestamp='Thu 1970-01-01 00:03:20.000001 UTC', ExecMainStartTimestampMonotonic='200000001',
            Environment=' '.join(shlex.quote(k+'='+v) for k,v in self.env.items()))
        self.unit = dict(argv=['systemctl','--user','--timestamp=us+utc','show',self.owner['unit'],'--all'],
            environment_overrides={'TZ':'UTC'}, returncode=0,
            stdout='\n'.join(k+'='+v for k,v in self.unit_fields.items())+'\n', stderr='')
        self.spec = dict(schema='robotron-batch2048-producer-live-capture-spec-v1', profile=pin(M.PROFILE),
            owner=self.owner, owner_pin=write(self.root / 'owner.json', self.owner), phase_record=self.record,
            boot_verification=self.boot_proof, source_pins={name:write(self.game/'Scripts/dqn'/name,
                ('# fixture source '+name+'\n').encode(),0o644) for name in M.SOURCES}, game_root=str(self.game),
            environment=self.env, argv=self.argv, cwd=str(self.game), exe='/fixture/python',
            experiment='fixture_ce2048', boot_id='11111111-2222-3333-4444-555555555555')
        self.times = [dict(boot_id=self.spec['boot_id'],monotonic_s=10.0,unix_s=300.0),
                      dict(boot_id=self.spec['boot_id'],monotonic_s=11.0,unix_s=301.0)]
        value = dict(owner=self.owner,process=self.process,environment=self.env,unit=self.unit)
        self.observations = [copy.deepcopy(value),copy.deepcopy(value)]
        self.header = b'utc,experiment,measurement_active,batch_size,steps,optimized_samples,learner_frames,frames\n'
        self.row = b'1970-01-01T00:04:10.000000+00:00,fixture_ce2048,False,2048,11,2068,31,41\n'
        self.csv = self.run/'training.csv'; write(self.csv,self.header+self.row,0o664)

    def capture(self, name='capture'):
        return M.capture_live(copy.deepcopy(self.spec),self.root/name,FakeHost(self))

    def source(self):
        size = 300 << 20
        return dict(path=str(self.root/'never-opened-newest.pt'),sha256='d'*64,bytes=size,
            identity=dict(device=1,inode=2,bytes=size,mtime_ns=3,ctime_ns=4,mode='0o444',uid=os.getuid(),nlink=1))

    def acquisition(self, source):
        return write(self.root/'acquisition.json',dict(schema='robotron-owned-phase-snapshot-acquisition-v1',
            purpose='candidate',owner_before=self.owner,owner_after=self.owner,source_checkpoint=M.triple(source),
            experiment=self.spec['experiment'],phase_record_sha256=self.record['sha256'],boot_checkpoint=self.boot,
            client_count=192,tag='fixture-early-insurance',stopped_absence=None,
            captured_floor=self.floor,completed_slot_transition={'fixture':'actual-owned-publication'}))

    def test_default_plan_performs_no_reads_or_runtime_queries(self):
        with patch.object(M,'bounded_read',side_effect=AssertionError('read')), \
             patch.object(M.subprocess,'run',side_effect=AssertionError('runtime')), \
             patch('sys.stdout',new_callable=io.StringIO) as output:
            self.assertEqual(M.main([]),0)
        self.assertIn('PLAN_ONLY',output.getvalue())

    def test_real_files_capture_independent_readonly_archives_and_fd_origin(self):
        captured=M.read_json(self.capture()); origin=M.read_json(captured['csv_origin'])
        self.assertEqual(origin['row_start_offset'],len(self.header))
        self.assertEqual(origin['row_end_offset'],len(self.header+self.row))
        self.assertEqual(origin['source_csv']['fd_before'],pin(self.csv)['identity'])
        self.assertEqual(M.read_pin(captured['csv']),self.header+self.row)
        self.assertEqual(captured['process_before'],captured['process_after'])
        self.assertFalse(captured['phase_CPU_verified']); self.assertFalse(captured['qualification_pass'])
        for artifact in captured['artifacts']:
            self.assertEqual(artifact['identity']['mode'],'0o444'); self.assertEqual(artifact['identity']['nlink'],1)
        for name, archive in captured['source_archives'].items():
            self.assertNotEqual(archive['identity']['inode'],self.spec['source_pins'][name]['identity']['inode'])

    def test_bind_after_retirement_never_reopens_live_csv_sources_or_checkpoint(self):
        capture=self.capture(); source=self.source(); acquisition=self.acquisition(source)
        self.csv.unlink()
        for source_pin in self.spec['source_pins'].values():Path(source_pin['path']).unlink()
        real=M.bounded_read
        def bounded(path,*args,**kwargs):
            self.assertFalse(str(path).startswith('/proc/')); self.assertFalse(str(path).endswith('.pt'))
            return real(path,*args,**kwargs)
        with patch.object(M,'bounded_read',side_effect=bounded), patch.object(M.ReadOnlyHost,'observe',side_effect=AssertionError('retired owner')):
            result=M.read_json(M.bind_capture(capture,source,acquisition,self.root/'bound'))
        self.assertEqual(result['producer_started_unix_s'],200.000001)
        self.assertEqual(result['observed_unix_s'],301.0)
        self.assertEqual(result['source_checkpoint'],M.triple(source))
        self.assertEqual(result['owner'],self.owner)

    def test_real_reviewed2_consumer_accepts_capture_bind_metadata(self):
        capture=self.capture(); source=self.source(); acquisition=self.acquisition(source)
        observation=M.bind_capture(capture,source,acquisition,self.root/'bound')
        wrapper=module(HERE.parent/'batch2048_phase_cpu_verifier_reviewed2_proposal/verify_phase_snapshot_2048.py','_producer_consumer_contract')
        def checked(p,evidence,label,**unused):
            raw=M.read_pin(p); evidence.setdefault('bound_files',{})[label]=p['identity']; return raw
        def decoded(p,evidence,label):return json.loads(checked(p,evidence,label))
        base=types.SimpleNamespace(check_pin=checked,pinned_json=decoded,trainer_identity=lambda value:M.owner(value),
            HELD_RECIPE_CONTEXT=M.read_json(self.spec['profile'])['held_recipe_context'])
        job=dict(experiment=self.spec['experiment'],source=source,batch2048_context=dict(profile=self.spec['profile'],
            role='early_insurance',producer_observation=observation),phase_snapshot=dict(purpose='candidate',
            observed_clients=192,owner=self.owner,acquisition=acquisition,expected_phase=dict(metric='ce')))
        evidence=dict(bound_files={},actual_boot_clocks=self.floor)
        wrapper.check_batch2048_context(job,base,evidence)
        self.assertTrue(evidence['producer_CSV_origin_verified'])
        self.assertEqual(evidence['actual_producer_batch_size'],2048)

    def test_old_same_second_future_naive_and_wrong_mode_csv_refuse(self):
        rows=[self.row.replace(b'00:04:10.000000',b'00:03:20.000000'),
              self.row.replace(b'00:04:10.000000',b'00:05:02.000000'),
              self.row.replace(b'+00:00',b''),self.row.replace(b'fixture_ce2048',b'other'),
              self.row.replace(b',False,',b',True,'),self.row.replace(b',2048,',b',4096,'),
              self.row.replace(b',11,2068,31,41',b',9,2068,31,41')]
        for index,row in enumerate(rows):
            with self.subTest(index=index):
                write(self.csv,self.header+row,0o664)
                with self.assertRaises(ValueError):self.capture('bad'+str(index))
                self.assertFalse((self.root/('bad'+str(index))).exists())

    def test_owner_reuse_environment_flags_uid_and_unit_drift_refuse(self):
        mutations=[lambda v:v['process'].update(starttime_ticks=1),lambda v:v['process'].update(uid=[os.getuid()+1]*4),
            lambda v:v['process'].update(argv=['other']),lambda v:v['environment'].update(DQN_BATCH_SIZE='4096'),
            lambda v:v['environment'].update(DQN_EXECUTED_CE_TRACE_DIR='/fixture/capture'),
            lambda v:v['unit'].update(stdout=v['unit']['stdout'].replace('NRestarts=0','NRestarts=1'))]
        original=copy.deepcopy(self.observations)
        for index,change in enumerate(mutations):
            self.observations=copy.deepcopy(original);change(self.observations[1])
            with self.subTest(index=index),self.assertRaises(ValueError):self.capture('bad'+str(index))

    def test_exact_utc_micro_command_calendar_and_precision_required(self):
        for field,value in [('argv',['systemctl','--user','show',self.owner['unit'],'--all']),
                            ('environment_overrides',{}),('returncode',1),
                            ('stdout',self.unit['stdout'].replace('.000001 UTC',' UTC')),
                            ('stdout',self.unit['stdout'].replace('Thu 1970','Fri 1970'))]:
            command=copy.deepcopy(self.unit);command[field]=value
            with self.subTest(field=field,value=value),self.assertRaises(ValueError):M.unit_start(command,self.owner)

    def test_boot_id_monotonic_interval_and_backward_wall_refuse(self):
        original=copy.deepcopy(self.times)
        for key,value in [('boot_id','aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'),('monotonic_s',21.0),('unix_s',299.0)]:
            self.times=copy.deepcopy(original);self.times[1][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):self.capture('bad'+key)

    def test_partial_final_row_is_not_selected_and_offsets_remain_original(self):
        write(self.csv,self.header+self.row+b'1970-01-01T00:05',0o664)
        result=M.csv_capture(self.csv)
        self.assertEqual(result['raw'],self.header+self.row)
        self.assertEqual(result['row_end_offset'],len(self.header+self.row))

    def test_append_during_read_preserves_original_completed_row_boundary(self):
        real=os.read;changed=False
        def read(fd,amount):
            nonlocal changed
            data=real(fd,amount)
            if not changed:
                changed=True
                with self.csv.open('ab') as stream:stream.write(self.row.replace(b'00:04:10',b'00:04:11'))
            return data
        with patch.object(M.os,'read',side_effect=read):result=M.csv_capture(self.csv)
        self.assertEqual(result['raw'],self.header+self.row)
        self.assertEqual(result['row_end_offset'],result['source_csv']['fd_before']['bytes'])
        self.assertGreater(result['source_csv']['fd_after']['bytes'],result['source_csv']['fd_before']['bytes'])

    def test_source_change_during_live_capture_refuses_closing_bracket(self):
        fixture=self;old=FakeHost.observe
        class ChangedSource(FakeHost):
            def observe(self,owner):
                value=old(self,owner)
                if self.observations==2:
                    path=Path(fixture.spec['source_pins']['agent.py']['path']);path.write_text('# changed\n')
                return value
        with self.assertRaisesRegex(ValueError,'changed'):
            M.capture_live(self.spec,self.root/'changed-source',ChangedSource(self))

    def test_csv_symlink_and_replacement_during_fd_read_refuse(self):
        target=self.run/'other.csv';write(target,self.header+self.row,0o664)
        self.csv.unlink();self.csv.symlink_to(target)
        with self.assertRaises(OSError):M.csv_capture(self.csv)
        self.csv.unlink();write(self.csv,self.header+self.row,0o664)
        real=os.read;changed=False
        def read(fd,amount):
            nonlocal changed
            data=real(fd,amount)
            if not changed:
                changed=True; self.csv.rename(self.run/'old.csv');write(self.csv,self.header+self.row,0o664)
            return data
        with patch.object(M.os,'read',side_effect=read),self.assertRaises(ValueError):M.csv_capture(self.csv)

    def test_proc_virtual_size_zero_is_bounded_without_requiring_disk_size(self):
        fields=dict(st_dev=1,st_ino=2,st_size=0,st_mtime_ns=0,st_ctime_ns=0,st_mode=stat.S_IFREG|0o444,st_uid=os.getuid(),st_nlink=1)
        value=types.SimpleNamespace(**fields)
        with patch.object(M.os,'open',return_value=99),patch.object(M.os,'fstat',return_value=value), \
             patch.object(M.os,'read',side_effect=[b'fixture\n',b'']),patch.object(M.os,'close'), \
             patch.object(Path,'lstat',return_value=value):
            self.assertEqual(M.bounded_read('/proc/12345/stat',128,proc=True)[0],b'fixture\n')
        with self.assertRaises(ValueError):M.bounded_read('/proc/12345/mem',128,proc=True)

    def test_real_host_uses_only_exact_owner_proc_and_precise_readonly_show(self):
        # Real observe() path; all operating-system reads are fixture injected.
        proc_stat=(str(self.owner['pid'])+' (fixture) '+' '.join(['S']+['0']*18+[str(self.owner['starttime_ticks'])]+['0']*4)).encode()
        values=dict(stat=proc_stat,cmdline=b'\0'.join(v.encode() for v in self.argv)+b'\0',
            status=('Uid:\t'+'\t'.join([str(os.getuid())]*4)+'\n').encode(),
            cgroup=('0::'+self.owner['cgroup']+'\n').encode(),
            environ=b'\0'.join((k+'='+v).encode() for k,v in self.env.items())+b'\0')
        def read(path,limit,**kwargs):
            self.assertTrue(kwargs.get('proc'));self.assertEqual(Path(path).parent,Path('/proc')/str(self.owner['pid']))
            return values[Path(path).name],{}
        def link(path):return str(self.game) if Path(path).name=='cwd' else '/fixture/python'
        result=types.SimpleNamespace(returncode=0,stdout=self.unit['stdout'],stderr='')
        with patch.object(M,'bounded_read',side_effect=read),patch.object(M.os,'readlink',side_effect=link), \
             patch.object(M.subprocess,'run',return_value=result) as command:
            observed=M.ReadOnlyHost().observe(self.owner)
        self.assertEqual(observed['process'],self.process)
        self.assertEqual(command.call_args.args[0],self.unit['argv'])
        self.assertEqual(command.call_args.kwargs['env']['TZ'],'UTC')

    def test_bind_rejects_wrong_owner_source_phase_or_mutated_capture_archive(self):
        capture=self.capture();source=self.source();acquisition=self.acquisition(source)
        actual=M.read_json(acquisition)
        for index,key in enumerate(('owner_after','source_checkpoint','phase_record_sha256')):
            bad=copy.deepcopy(actual)
            bad[key]=dict(self.owner,pid=54321) if key=='owner_after' else (dict(self.boot) if key=='source_checkpoint' else 'e'*64)
            badpin=write(self.root/('bad-acq'+str(index)+'.json'),bad)
            with self.subTest(key=key),self.assertRaises(ValueError):M.bind_capture(capture,source,badpin,self.root/('bad-bind'+str(index)))
        archive=Path(M.read_json(capture)['csv']['path']);archive.chmod(0o644);archive.write_bytes(b'changed\n');archive.chmod(0o444)
        with self.assertRaises(ValueError):M.bind_capture(capture,source,acquisition,self.root/'mutated-bind')

    def test_checkpoint_bodies_and_writable_metadata_never_pass_read_pin(self):
        body=write(self.root/'small.pt',b'opaque',0o444)
        with patch.object(M,'bounded_read',side_effect=AssertionError('checkpoint opened')),self.assertRaises(ValueError):M.read_pin(body)
        metadata=write(self.root/'mutable.json',dict(value=1),0o644)
        with self.assertRaises(ValueError):M.read_pin(metadata)

    def test_writer_is_create_only_bounded_and_never_aliases_original(self):
        writer=M.Writer(self.root/'writer');written=writer.put('metadata.json',dict(value=1))
        self.assertEqual(written['identity']['mode'],'0o444')
        with self.assertRaises(ValueError):writer.put('metadata.json',dict(value=2))
        with self.assertRaises(ValueError):writer.put('../escape.json',dict(value=2))
        with patch.object(M,'MAX_FILE',16),self.assertRaises(ValueError):writer.put('too-large.txt',b'x'*17)
        with self.assertRaises(ValueError):M.Writer(self.root/'writer')


if __name__ == '__main__':
    unittest.main()
