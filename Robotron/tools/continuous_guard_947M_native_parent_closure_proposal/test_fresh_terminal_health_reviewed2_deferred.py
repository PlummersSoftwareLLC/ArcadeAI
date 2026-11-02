"""UNEXECUTED metadata fixtures; root alone may select one bounded future run.

Only authenticated copies of the selected source and local fixture JSON are
opened. Actual fresh_terminal_health/full8_metadata_pin run on a synthetic
terminal-health envelope at an archived clock. No closure, commands, current
health, cgroup, process, units, models or producer actions are exercised.
"""
import copy
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import types
import unittest


DIRECTORY = Path('/home/dave/source/repos/ArcadeAI/Robotron/tools/continuous_guard_947M_native_parent_closure_proposal')
SOURCE = DIRECTORY/'close_original_parent_reviewed2.py'
SOURCE_SHA = '4bff3e25ea84435936e8b3656138c27b757739cc8a1fb42f961630d783517576'
DATA = DIRECTORY/'closed-health-fixture-inputs-reviewed2.json'
DATA_SHA = '371ebcf970dd786e8d7665e759969d3f44f7b143cecd508dc463b4d8529e96f0'
READS = {SOURCE: (SOURCE_SHA, 32523), DATA: (DATA_SHA, 433946)}
ANCHOR = ('main_owner','fleet_owner','inference_worker','actors','source_hashes',
          'control_hashes','unit_files','environment_sha256')


def sealed_input(path):
    """The test bootstrap's complete closed-file read allowlist."""
    if path not in READS:
        raise AssertionError('Unplanned bootstrap file: '+str(path))
    expected_sha, expected_bytes = READS[path]
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        before = os.fstat(stream.fileno())
        if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
                or stat.S_IMODE(before.st_mode) != 0o444
                or before.st_uid != 1001 or before.st_size != expected_bytes):
            raise AssertionError('Closed fixture/source identity differs')
        raw = stream.read(expected_bytes+1)
        def stable(value):
            return (value.st_dev,value.st_ino,value.st_size,value.st_mtime_ns,
                    value.st_ctime_ns,value.st_mode,value.st_uid,value.st_nlink)
        if stable(before) != stable(os.fstat(stream.fileno())) or stable(before) != stable(path.lstat()):
            raise AssertionError('Closed fixture/source changed during read')
    if len(raw) != expected_bytes or hashlib.sha256(raw).hexdigest() != expected_sha:
        raise AssertionError('Exact closed fixture/source fingerprint differs')
    return raw


def synthetic_pin(name, serial):
    """Declared fake PIN; never presented as an actual saved file fingerprint."""
    return dict(path='/synthetic-closed-fixture/'+name+'.json', sha256=('a' if serial == 1 else 'b')*64,
        bytes=100+serial, identity=dict(device=2304,inode=90000000+serial,bytes=100+serial,
        mtime_ns=1000000000+serial,ctime_ns=1000000000+serial,mode='0o444',uid=1001,nlink=1))


class FreshTerminalHealthMetadata(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Authenticate before importing the inert stdlib-only selected module.
        source_raw = sealed_input(SOURCE)
        cls.fixture = json.loads(sealed_input(DATA))
        if cls.fixture['status'] != 'SOURCE_ONLY_FIXTURE_DATA_NOT_CURRENT_HEALTH':
            raise AssertionError('Synthetic fixture scope changed')
        cls.target = types.ModuleType('_947_closure_health_deferred')
        cls.target.__file__ = str(SOURCE)
        # Future root execution compiles these exact authenticated bytes only;
        # no bytecode-cache/import-loader fallback can supply another body.
        exec(compile(source_raw,str(SOURCE),'exec'),cls.target.__dict__)

    def setUp(self):
        self.unexpected = []
        target = self.target
        def forbidden(*args, **kwargs):
            self.unexpected.append((args,kwargs))
            raise AssertionError('Unplanned target I/O/action; no host fallback')
        # Only the two real pure metadata functions and require remain callable.
        # Default-bound read_pin is never used: every call passes strict_reader.
        for name in ('bounded_bytes','read_pin','known','properties','validate_case',
                     'original_terminal','original_timer','held_sources','empty_original_cgroup',
                     'sync_directory','pin','publish','command','fields','close','main'):
            setattr(target,name,forbidden)
        target.os = types.SimpleNamespace(getuid=lambda: 1001)
        target.time = types.SimpleNamespace(time=forbidden)
        target.Path = PurePosixPath
        target.subprocess = types.SimpleNamespace(run=forbidden)

        self.baseline = copy.deepcopy(self.fixture['baseline_projection'])
        self.old_api = copy.deepcopy(self.fixture['baseline_API'])
        self.api = copy.deepcopy(self.fixture['startup_API'])
        self.observed = self.api['ts']+.25
        self.now = self.observed+1
        self.health_pin = synthetic_pin('terminal-health',1)
        self.api_pin = synthetic_pin('root-main-api',2)
        self.health = {key: copy.deepcopy(self.baseline[key]) for key in ANCHOR}
        self.health.update(schema=target.HEALTH_SCHEMA,status='PASS',observed_unix_s=self.observed,
            main_api=copy.deepcopy(self.api_pin),quality_terminal=dict(unit=target.UNIT,pid=target.PID,
            starttime_ticks=target.START,invocation_id=target.INVOCATION,timer=target.TIMER,
            timer_invocation_id=target.TIMER_INVOCATION,exec_main_code=1,exit_status=0,
            result='success',n_restarts=0,main_pid=0,
            cgroup='/user.slice/user-1001.slice/user@1001.service/app.slice/'+target.UNIT,
            cgroup_state='empty'),resources=dict(GPU0_empty=True,GPU1_main_only=True,
            port9999_clear=True,no_pending_save=True,lease_free=True))
        self.context = dict(case={'fresh_terminal_health':self.health_pin},baseline=self.baseline,
            experiment=self.fixture['experiment'],original_cgroup=self.health['quality_terminal']['cgroup'])
        self.reads = []

    def tearDown(self):
        # This check is outside the expected ValueError branches. A mistaken
        # negative cannot swallow a failed mock expectation or forbidden action.
        self.assertEqual(self.unexpected, [], 'Unexpected access was attempted')

    def strict_reader(self, pin):
        choices = ((self.health_pin,self.health), (self.api_pin,self.api),
                   (self.baseline['actual_API'],self.old_api))
        for expected, value in choices:
            if pin == expected:
                self.reads.append(expected['path'])
                return copy.deepcopy(value)
        self.unexpected.append(('reader',pin))
        raise AssertionError('Unplanned metadata PIN; no file/current-health fallback')

    def check(self):
        return self.target.fresh_terminal_health(self.context, reader=self.strict_reader, now=self.now)

    def assert_refused(self, mutator):
        state = copy.deepcopy((self.context,self.health,self.api,self.old_api,self.now))
        try:
            mutator()
            with self.assertRaises(ValueError):
                self.check()
        finally:
            self.context,self.health,self.api,self.old_api,self.now = state
            self.baseline = self.context['baseline']
            self.health_pin = self.context['case']['fresh_terminal_health']
            self.api_pin = self.health['main_api']
        self.assertEqual(self.unexpected, [])

    def test_actual_closed_projection_accepts_archived_clock_and_exact_census(self):
        value = self.check()
        self.assertEqual(value['pin'],self.health_pin)
        self.assertEqual(value['age_s'],1)
        self.assertEqual(self.reads,[self.health_pin['path'],self.api_pin['path'],self.baseline['actual_API']['path']])
        self.assertEqual(len(self.health['actors']),192)
        self.assertEqual(len(self.health['source_hashes']),62)
        self.health['actors'].reverse()
        for row in self.health['actors']:
            row['mask'].reverse()
        self.health['quality_terminal']['cgroup_state'] = 'removed'
        self.assertEqual(self.check()['observed_unix_s'],self.observed)

    def test_optimizer_pending_zero_or_one_and_available_partition(self):
        optimizer = self.api['host_pipeline']['learning_exposure']['optimizer']
        self.assertEqual(optimizer['unclassified_started_total'],0)
        self.assertIs(optimizer['available'],True)
        self.check()
        for group in ('total','since_epoch'):
            optimizer[group]['attempts_started'] += 1
        optimizer['unclassified_started_total'] = 1
        optimizer['available'] = False
        self.check()
        self.assert_refused(lambda: self.api['host_pipeline']['learning_exposure']['optimizer'].__setitem__('available',True))
        self.assert_refused(lambda: self.api['host_pipeline']['learning_exposure']['optimizer'].__setitem__('unclassified_started_total',2))
        self.assert_refused(lambda: self.api['host_pipeline']['learning_exposure']['optimizer'].__setitem__('unclassified_started_total',True))
        def inconsistent_partition():
            row = self.api['host_pipeline']['learning_exposure']['optimizer']['total']
            row['outcomes_recorded'] += 1
            row['attempts_started'] += 1
        self.assert_refused(inconsistent_partition)

    def test_each_of_four_pipeline_error_stages_is_fatal(self):
        stages = ('inference','actor_refresh','target_refresh','learner_priority')
        self.assertTrue(all(type(self.api['host_pipeline'][k]['errors']) is int
                            and self.api['host_pipeline'][k]['errors'] == 0 for k in stages))
        for stage in stages:
            with self.subTest(stage=stage):
                self.assert_refused(lambda stage=stage: self.api['host_pipeline'][stage].__setitem__('errors',1))
                self.assert_refused(lambda stage=stage: self.api['host_pipeline'][stage].__setitem__('errors',False))
        self.assert_refused(lambda: self.api['host_pipeline'].__setitem__('available',False))
        self.assert_refused(lambda: self.api.__setitem__('pipeline_read_error','partial'))
        self.assert_refused(lambda: self.api.__setitem__('bank_persistence_read_error','unavailable'))

    def test_health_pin_and_observation_are_typed_fresh_closed_metadata(self):
        self.assert_refused(lambda: self.health.__setitem__('observed_unix_s',self.now-180))
        self.assert_refused(lambda: self.health.__setitem__('observed_unix_s',self.now+.01))
        self.assert_refused(lambda: self.health.__setitem__('observed_unix_s',True))
        self.assert_refused(lambda: self.health.__setitem__('status','UNKNOWN'))
        self.assert_refused(lambda: self.health.__setitem__('schema','old-health-schema'))
        self.assert_refused(lambda: self.api.__setitem__('ts',self.observed-5.01))
        self.assert_refused(lambda: self.api.__setitem__('ts',self.observed+.01))
        self.assert_refused(lambda: self.api.__setitem__('pipeline_snapshot_age_s',5.01))
        self.assert_refused(lambda: self.api.__setitem__('pipeline_snapshot_age_s',float('nan')))
        self.assert_refused(lambda: self.health_pin['identity'].pop('mtime_ns'))
        self.assert_refused(lambda: self.health_pin['identity'].__setitem__('inode',True))
        self.assert_refused(lambda: self.health_pin.__setitem__('bytes',True))

    def test_main_fleet_worker_actor_and_frozen_inventory_must_match(self):
        self.assert_refused(lambda: self.health['main_owner'].__setitem__('pid',999))
        self.assert_refused(lambda: self.health['fleet_owner'].__setitem__('starttime_ticks',1))
        self.assert_refused(lambda: self.health['inference_worker'].__setitem__('tid',1))
        self.assert_refused(lambda: self.health.__setitem__('environment_sha256','f'*64))
        self.assert_refused(lambda: self.health['actors'][0].__setitem__('pid',1))
        self.assert_refused(lambda: self.health['actors'][0].__setitem__('starttime_ticks',1))
        self.assert_refused(lambda: self.health['actors'][0].__setitem__('slot',True))
        self.assert_refused(lambda: self.health['actors'][0].__setitem__('mask',[999]))
        self.assert_refused(lambda: self.health['actors'].__setitem__(1,copy.deepcopy(self.health['actors'][0])))
        self.assert_refused(lambda: self.health['actors'].pop())
        for key in ('source_hashes','control_hashes','unit_files'):
            with self.subTest(inventory=key):
                self.assert_refused(lambda key=key: self.health[key].__setitem__(next(iter(self.health[key])),'f'*64))

    def test_resource_and_exact_owned_terminal_identity_are_mandatory(self):
        for key in tuple(self.health['resources']):
            with self.subTest(resource=key):
                self.assert_refused(lambda key=key: self.health['resources'].__setitem__(key,False))
        for key, value in (('unit','foreign.service'),('pid',1),('starttime_ticks',1),
                ('invocation_id','f'*32),('timer','foreign.timer'),('timer_invocation_id','f'*32),
                ('exit_status',1),('exec_main_code',0),('n_restarts',1),('main_pid',1),
                ('cgroup','/foreign'),('cgroup_state','populated')):
            with self.subTest(terminal=key):
                self.assert_refused(lambda key=key,value=value: self.health['quality_terminal'].__setitem__(key,value))

    def test_exposure_reset_unavailable_regression_and_source_partitions_refuse(self):
        for name in ('optimizer','replay'):
            for key, value in (('epoch',2),('epoch',True),('instance_monotonic_ns',1),
                               ('process_id',1),('epoch_reason','reset'),('enabled',False)):
                with self.subTest(exposure=name,field=key):
                    self.assert_refused(lambda name=name,key=key,value=value:
                        self.api['host_pipeline']['learning_exposure'][name].__setitem__(key,value))
        self.assert_refused(lambda: self.api['host_pipeline'].__setitem__('generation',self.api['host_pipeline']['generation']+1))
        def unavailable_with_consistent_partition():
            optimizer = self.api['host_pipeline']['learning_exposure']['optimizer']
            for group in ('total','since_epoch'):
                optimizer[group]['attempts_started'] += 1
                optimizer[group]['outcomes_recorded'] += 1
                optimizer[group]['unavailable'] += 1
        self.assert_refused(unavailable_with_consistent_partition)
        self.assert_refused(lambda: self.api['host_pipeline']['learning_exposure']['optimizer']['since_epoch'].__setitem__('applied',0))
        self.assert_refused(lambda: self.api['host_pipeline']['learning_exposure']['replay'].__setitem__('available',False))
        self.assert_refused(lambda: self.api['host_pipeline']['learning_exposure']['replay'].__setitem__('accepted_total',0))
        self.assert_refused(lambda: self.api['host_pipeline']['learning_exposure']['replay'].__setitem__('accepted_learner_total',0))
        self.assert_refused(lambda: self.api['host_pipeline']['learning_exposure']['replay']['accepted_by_source_total'].__setitem__('dqn',0))
        self.assert_refused(lambda: self.api.__setitem__('learner_frame_count',0))
        self.assert_refused(lambda: self.api.__setitem__('managed_experiment','foreign'))
        self.assert_refused(lambda: self.api.__setitem__('lr',2.5e-5))


if __name__ == '__main__':
    unittest.main()
