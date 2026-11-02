"""Four dormant stdlib metadata/closure-route guards; authors have not executed them.

Only authenticated CLOSED metadata/source files are read by the test bootstrap.
The extracted target functions see strict in-memory readers, paths, commands,
publication and cgroup/source checks. No real process, unit, API or model access.
This does not prove host timing, unit-name atomicity, systemd or file durability.
"""
import ast
import copy
import hashlib
import json
from pathlib import Path
import types
import unittest

HERE = Path(__file__).parent
SOURCE = HERE/'close_original_parent.py'
SOURCE_SHA = '4eabe292436da86d46e0576a68395a2fbb4c3204b88b34aba506314e34cabaaa'
ROOT = Path('/home/dave/source/repos/ArcadeAI')
PREP = ROOT/'Robotron/logs/managed-learning-20261015/run-26/LR25-continuation-original01-root-preparation-20261018'
PACK = ROOT/'Robotron/tools/live_lr_recipe_cpu_metadata_review_binding_proposal'
CLOSED = {
    str(PREP/'root-original-LR25-quality-timer-launch-identity-and-live-parent.json'): '0e5a5da6231bb46bfb4dce06409465bf2b2be4f7ac2e5997226b7d1407ed3b59',
    str(PREP/'actual-LR25-845M-native-plan-readonly-copy.json'): '8ac7c5729ca5d53edcbf02ddd61e9e8377b8b1d7f4d43648c2fda7ab263b0c7d',
    str(PREP/'actual-LR25-845M-quality-binding.json'): 'b98dd3f00ef3961f36a2e9748b55c96751411e3945f740cee2b74d8c2bdd16c3',
    str(PACK/'preparation-manifest.json'): 'd21e5a95c1659a82b0a3fa93c6b4f0e960ad70b81d217959a8a74d6e95b81859',
}
CONFIG_SHAS = ('c1f841c653d6b19883f0a9dc62af476fd8bf11eea847cfcc8e481765feeb8686',
    '383d44f5487a543da8c48da865469f6b0730d8d93283fb7871366392e95bc93a',
    '3de4ee34f5f6d55a096cc3c4cd9d4f40068ea3b020933d1e6494c892c4483d0f',
    '6b7d5b672585698c7bb578484116f2f3ac5dd52fc1a24fe6a0c3b3291a820154')
for _index, _sha in enumerate(CONFIG_SHAS, 1):
    CLOSED[str(PREP/('LR25-845M-quality-leg%02d-audit-original01-config.json' % _index))] = _sha


def encode(value):
    return (json.dumps(value, sort_keys=True, allow_nan=False)+'\n').encode()


def synthetic_pin(path, value):
    return synthetic_bytes_pin(path, encode(value))


def synthetic_bytes_pin(path, raw):
    return dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw),
        identity=dict(device=1, inode=1, bytes=len(raw), mtime_ns=1, ctime_ns=1,
            mode='0o444', uid=1001, nlink=1))


class MetadataFixture:
    def __init__(self):
        self.values = {}; self.pins = {}; self.unexpected = []
        for path, expected in CLOSED.items():
            p = Path(path); raw = p.read_bytes(); info = p.lstat()
            if hashlib.sha256(raw).hexdigest() != expected or info.st_mode & 0o777 != 0o444:
                raise AssertionError('Fixed closed bootstrap input changed: '+path)
            value = json.loads(raw)
            pin = dict(path=path, sha256=expected, bytes=len(raw), identity=dict(
                device=info.st_dev, inode=info.st_ino, bytes=info.st_size,
                mtime_ns=info.st_mtime_ns, ctime_ns=info.st_ctime_ns,
                mode=oct(info.st_mode & 0o777), uid=info.st_uid, nlink=info.st_nlink))
            self.values[path], self.pins[path] = value, pin
        raw = SOURCE.read_bytes()
        if hashlib.sha256(raw).hexdigest() != SOURCE_SHA:
            raise AssertionError('Exact closure source changed')
        tree = ast.parse(raw, filename=str(SOURCE))
        functions = {'require', 'properties', 'original_terminal', 'original_timer', 'validate_case', 'close', 'fields'}
        body = [node for node in tree.body if isinstance(node, ast.Assign)
            or isinstance(node, ast.FunctionDef) and node.name in functions]
        self.g = dict(Path=Path, read_pin=self.read, known=self.known,
            bounded_bytes=self.bounded, json=json, time=types.SimpleNamespace(time=lambda: 1000.0))
        exec(compile(ast.Module(body=body, type_ignores=[]), str(SOURCE), 'exec'), self.g)
        self.make_future()

    def fail(self, message):
        self.unexpected.append(message)
        raise AssertionError(message)

    def put(self, path, value):
        p = synthetic_pin(path, value); self.values[str(path)] = value; self.pins[str(path)] = p
        return copy.deepcopy(p)

    def read(self, pin):
        path = pin.get('path')
        if path not in self.values:
            return self.fail('Unexpected target metadata read: '+str(path))
        if pin != self.pins[path]:
            return self.fail('Unexpected target metadata PIN: '+str(path))
        return copy.deepcopy(self.values[path])

    def bounded(self, path):
        path = str(path)
        if path not in CLOSED:
            return self.fail('Unexpected target bounded source read: '+path)
        return encode(self.values[path]), copy.deepcopy(self.pins[path])

    def known(self, name):
        path, expected = self.g['KNOWN'][name]
        if str(path) not in CLOSED or CLOSED[str(path)] != expected:
            return self.fail('Unexpected target known binding: '+name)
        return copy.deepcopy(self.values[str(path)]), copy.deepcopy(self.pins[str(path)])

    def make_future(self):
        g = self.g; plan = self.values[str(g['KNOWN']['plan'][0])]
        binding = self.values[str(g['KNOWN']['binding'][0])]
        self.values[binding['runtime_baseline']['path']] = dict(status='PASS', **copy.deepcopy(binding['runtime_anchor']))
        self.pins[binding['runtime_baseline']['path']] = binding['runtime_baseline']
        rows = [dict(index=p['index'], role=p['role'], state='finished', returncode=0,
            pid=8100+p['index'], started_unix_s=10, ended_unix_s=20,
            receipt_path=p['receipt_path'], console_log=p['console_log']) for p in plan['legs']]
        status = dict(state='finished', outcome='not_improved', plan_sha256=g['PLAN_SHA'],
            plan_path=str(g['CAMPAIGN']/'plan.json'), legs=rows)
        summary = dict(outcome='not_improved', plan_sha256=g['PLAN_SHA'],
            plan_path=str(g['CAMPAIGN']/'plan.json'), stop_signal=None,
            legs=[dict(index=p['index'], role=p['role'], valid=True, returncode=0,
                receipt_path=p['receipt_path'], console_log=p['console_log']) for p in plan['legs']])
        self.status_pin = self.put('/synthetic/closed-native-status.json', status)
        self.summary_pin = self.put('/synthetic/closed-native-summary.json', summary)
        releases = []
        for index in range(1, 5):
            config_path = str(PREP/('LR25-845M-quality-leg%02d-audit-original01-config.json' % index))
            config = self.values[config_path]
            out = Path(config['output']); unit = config['unit']
            intent = dict(config, no_retry=True, original_attempt=1)
            intent_pin = self.put(str(out/'root-launch-intent.json'), intent)
            archive_pin = self.put(str(out/'root-original-timer-launch-archive.json'), dict(launch_intent=intent_pin))
            release = dict(schema='robotron-root-audit-original-result-and-GC-aware-owned-release-v1',
                status='ORIGINAL_AUDIT_EXIT0_ARCHIVED_AND_RELEASED', original=dict(unit=unit, observed_live=True),
                original_exec_code=1, original_exit=0, original_result='success', audit_success=True,
                lifecycle_complete=True, unit_released=True, original_archived_before_release=True,
                all_six_original_archive_commands_succeeded=True, error=None, payload_retried=False,
                owned_release=[dict(unit=unit.removesuffix('.service')+'.timer', confirmed_absent=True),
                    dict(unit=unit, confirmed_absent=True)], timer_launch_archive=archive_pin)
            releases.append(self.put(str(out/'root-original-result-and-owned-release.json'), release))
        self.case = dict(schema=g['SCHEMA'], closure_authorized=True, native_status=self.status_pin,
            native_summary=self.summary_pin, audit_releases=releases, output_directory=str(g['OUTPUT']))

    def change(self, pin, mutator):
        value = copy.deepcopy(self.values[pin['path']]); mutator(value)
        return self.put(pin['path'], value)

    def clean(self, test):
        test.assertEqual([], self.unexpected, 'Strict target IO failures must survive caught target exceptions')


class ClosedRouteIO:
    def __init__(self, fixture, mutation=None):
        self.f = fixture; self.g = fixture.g; self.mutation = mutation
        self.events = []; self.unexpected = []; self.records = {}; self.texts = {}; self.saved = {}
        self.created = False
        parent = self
        class ClosedPath:
            def __init__(self, value): self.value = str(value)
            def __str__(self): return self.value
            def __truediv__(self, name): return ClosedPath(self.value+'/'+str(name))
            def exists(self):
                if self.value != str(parent.g['OUTPUT']): return parent.fail('Unexpected exists')
                return parent.created
            def mkdir(self, **kwargs):
                if self.value != str(parent.g['OUTPUT']) or parent.created: return parent.fail('Unexpected mkdir')
                parent.created = True
            def read_text(self):
                if self.value not in parent.texts: return parent.fail('Unexpected raw read: '+self.value)
                return parent.texts[self.value]
        self.Path = ClosedPath
        self.g['OUTPUT'] = ClosedPath(str(self.g['OUTPUT']))
        self.g.update(Path=ClosedPath, command=self.command, publish=self.publish,
            held_sources=self.held, empty_original_cgroup=self.cgroup,
            sync_directory=lambda p:self.events.append(('sync', str(p))), print=lambda *a,**k:None)

    def fail(self, message):
        self.unexpected.append(message); raise AssertionError(message)

    def held(self, context): self.events.append(('held',)); return None
    def cgroup(self, context): self.events.append(('cgroup',)); return 'empty'

    def command(self, out, label, argv):
        g = self.g
        if label in self.records: return self.fail('Repeated command: '+label)
        service = dict(Id=g['UNIT'], LoadState='loaded', MainPID='0', ExecMainPID=str(g['PID']),
            InvocationID=g['INVOCATION'], NRestarts='0', ExecMainCode='1', ExecMainStatus='0',
            Result='success', SubState='exited')
        timer = dict(Id=g['TIMER'], LoadState='loaded', InvocationID=g['TIMER_INVOCATION'], Unit=g['UNIT'])
        expected = {}
        for kind, unit, inv in [('service',g['UNIT'],g['INVOCATION']),('timer',g['TIMER'],g['TIMER_INVOCATION'])]:
            expected['before-'+kind+'-show'] = ['systemctl','--user','show',unit,'--all']
            for action in ('show','cat','journal'):
                expected['original-'+kind+'-'+action] = ['journalctl','--user','_SYSTEMD_INVOCATION_ID='+inv,'--no-pager','-o','short-iso-precise'] if action == 'journal' else ['systemctl','--user',action,unit]+(['--all'] if action == 'show' else [])
            for point in ('before','after'):
                expected['release-'+kind+'-'+point+'-show'] = ['systemctl','--user','show',unit,'--all']
            expected['release-'+kind+'-stop'] = ['systemctl','--user','stop',unit]
        if expected.get(label) != argv: return self.fail('Unexpected command: '+repr((label,argv)))
        fields = service if 'service' in label else timer
        if label.startswith('release-') and '-after-show' in label:
            fields = dict(Id=g['UNIT'] if 'service' in label else g['TIMER'], LoadState='not-found')
        fields = dict(fields); exit_code = 0; timed_out = False
        if self.mutation: fields, exit_code, timed_out = self.mutation(label,fields,exit_code,timed_out)
        raw = ''.join(k+'='+v+'\n' for k,v in fields.items())
        if label.endswith('-cat'): raw = '# Synthetic owned unit contents\n'
        if label.endswith('-journal'): raw = '-- No entries --\n'
        stdout_path = str(out)+'/'+label+'-stdout.txt'; self.texts[stdout_path] = raw
        record = dict(argv=argv, exit=exit_code, timed_out=timed_out,
            error='synthetic timeout' if timed_out else None, started_unix_s=100+len(self.records),
            unix_s=100.5+len(self.records), stdout=synthetic_bytes_pin(stdout_path,raw.encode()),
            stderr=synthetic_bytes_pin(str(out)+'/'+label+'-stderr.txt',b''))
        self.records[label] = record; self.events.append(('command',label))
        return record

    def publish(self, path, value):
        path = str(path)
        if path in self.saved: return self.fail('Repeated publication: '+path)
        self.saved[path] = copy.deepcopy(value); self.events.append(('publish',Path(path).name))
        return synthetic_pin(path,value)

    def result(self): return self.saved[str(self.g['OUTPUT'])+'/root-original-native-parent-result-and-owned-release.json']
    def clean(self, test):
        self.f.clean(test); test.assertEqual([],self.unexpected)


class OriginalParentClosureMetadata(unittest.TestCase):
    def test_real_closed_owner_plan_and_configs_with_future_complete_rows(self):
        f = MetadataFixture(); result = f.g['validate_case'](f.case)
        self.assertEqual(result['native_plan']['sha256'],f.g['PLAN_SHA'])
        self.assertEqual(result['case']['audit_releases'],f.case['audit_releases']); f.clean(self)
        mutations = [
            ('status',lambda x:x.update(state='running')),
            ('status',lambda x:x['legs'][3].update(state='running')),
            ('status',lambda x:x['legs'][1].update(returncode=1)),
            ('summary',lambda x:x['legs'][2].update(valid=False)),
            ('audit',lambda x:x.update(original_exit=2,audit_success=False)),
            ('audit',lambda x:x['original'].update(unit='foreign.service')),
        ]
        for name, mutation in mutations:
            with self.subTest(name=name,mutation=mutation):
                f = MetadataFixture(); key = 'native_status' if name=='status' else 'native_summary'
                if name=='audit': f.case['audit_releases'][0] = f.change(f.case['audit_releases'][0],mutation)
                else: f.case[key] = f.change(f.case[key],mutation)
                with self.assertRaises(ValueError): f.g['validate_case'](f.case)
                f.clean(self)

    def test_exact_terminal_and_timer_owners_reject_foreign_or_nonzero(self):
        f=MetadataFixture(); g=f.g
        terminal=dict(Id=g['UNIT'],LoadState='loaded',MainPID='0',ExecMainPID=str(g['PID']),
            InvocationID=g['INVOCATION'],NRestarts='0',ExecMainCode='1',ExecMainStatus='0',Result='success',SubState='exited')
        timer=dict(Id=g['TIMER'],LoadState='loaded',InvocationID=g['TIMER_INVOCATION'],Unit=g['UNIT'])
        g['original_terminal'](terminal);g['original_timer'](timer)
        for key,value in [('Id','foreign.service'),('MainPID','1'),('InvocationID','0'*32),('NRestarts','1'),('ExecMainStatus','1'),('Result','exit-code')]:
            with self.subTest(key=key):
                with self.assertRaises(ValueError):g['original_terminal'](dict(terminal,**{key:value}))
        for key,value in [('Id','foreign.timer'),('LoadState','not-found'),('InvocationID','0'*32),('Unit','foreign.service')]:
            with self.subTest(key=key):
                with self.assertRaises(ValueError):g['original_timer'](dict(timer,**{key:value}))
        f.clean(self)

    def test_actual_close_route_six_archives_before_exact_timer_first_stops_once(self):
        f=MetadataFixture();context=f.g['validate_case'](f.case);io=ClosedRouteIO(f)
        self.assertEqual(f.g['close'](context),0);r=io.result()
        self.assertEqual(len(r['full_original_archives']),6)
        self.assertTrue(r['all_six_original_archive_commands_succeeded']);self.assertTrue(r['lifecycle_complete']);self.assertTrue(r['unit_released'])
        self.assertFalse(r['quality_promotion']);self.assertFalse(r['source_freeze_released'])
        labels=[event[1] for event in io.events if event[0]=='command']
        archives=[labels.index('original-'+k+'-'+a) for k in ('service','timer') for a in ('show','cat','journal')]
        self.assertLess(max(archives),labels.index('release-timer-stop'))
        self.assertLess(labels.index('release-timer-after-show'),labels.index('release-service-stop'))
        n=len(io.records)
        with self.assertRaises(ValueError):f.g['close'](context)
        self.assertEqual(len(io.records),n);io.clean(self)

    def test_actual_route_preserves_archive_stop_failures_without_other_unit_actions(self):
        cases=[('before-service-show','foreign',0),('before-timer-show','foreign',0),
            ('original-timer-cat','exit1',0),('original-service-journal','timeout',0),
            ('release-timer-stop','exit5',1),('release-service-before-show','foreign',1)]
        for label,kind,stops in cases:
            with self.subTest(label=label,kind=kind):
                f=MetadataFixture();context=f.g['validate_case'](f.case)
                def mutate(name,values,exit_code,timed_out):
                    if name==label:
                        if kind=='foreign':values['InvocationID']='0'*32
                        elif kind=='timeout':exit_code=None;timed_out=True
                        else:exit_code=1 if kind=='exit1' else 5
                    return values,exit_code,timed_out
                io=ClosedRouteIO(f,mutate);self.assertEqual(f.g['close'](context),1);r=io.result()
                self.assertFalse(r['unit_released']);self.assertFalse(r['lifecycle_complete'])
                self.assertFalse(r['quality_promotion']);self.assertFalse(r['source_freeze_released'])
                self.assertEqual(len([x for x in io.records if x.endswith('-stop')]),stops)
                if kind=='exit5':self.assertEqual(r['owned_release'][0]['stop']['exit'],5)
                if kind=='timeout':self.assertIsNone(io.records[label]['exit']);self.assertTrue(io.records[label]['timed_out'])
                io.clean(self)


if __name__ == '__main__':
    unittest.main()
