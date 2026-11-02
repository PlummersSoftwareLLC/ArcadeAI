"""Source-bound actual start/_accept tests; Root alone may execute the CPU suite.

All clocks, scheduling Popen handles, units, process births and live publications
are explicitly synthetic. Tiny temporary prefix files use actual selected worker
pin/checked/read helpers. Tmpfs selection is mapped to a temporary directory;
there is no proc/API/unit/kernel/GPU/MAME operation or runtime qualification.
The constructor and finish/release paths are outside this focused scope.
"""
import ast
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import tempfile
from types import SimpleNamespace
import unittest

SOURCES = {'client': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/health-consumer-quiescence-readiness120-overlay-original06/continuous_physical192_observer_client_readiness120_v1.py', 'sha256': '82e5e02e49c853355fd0bf1dd4839efdb498a8f798dbf08e3c7a72703778cbec', 'bytes': 17485, 'identity': {'device': 2304, 'inode': 85355713, 'bytes': 17485, 'mtime_ns': 1793310753659202653, 'ctime_ns': 1793310753659202653, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'worker': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/health-consumer-live-pidfd-current-EVAL-quiescence-original05/observe_continuous_physical192_v5.py', 'sha256': '39880853e6e04df59a666be020b6b26f2d7946cfcbe8dfbeb66856e9b240ef10', 'bytes': 16758, 'identity': {'device': 2304, 'inode': 85353803, 'bytes': 16758, 'mtime_ns': 1793309242594203611, 'ctime_ns': 1793309543236849422, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}, 'control': {'bytes': 4486, 'identity': {'bytes': 4486, 'ctime_ns': 1793220289402331907, 'device': 2304, 'inode': 84708489, 'mode': '0o664', 'mtime_ns': 1793220289402331907, 'nlink': 1, 'uid': 1001}, 'path': '/home/dave/source/repos/ArcadeAI/Robotron/tools/post_recovery_evaluation/volatile_live_control_v1.py', 'sha256': 'a2ce55471f7ff14490553cf05871e79a0ff15c925d01441065821b0f95daade8'}, 'parent_client': {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/health-consumer-live-pidfd-current-EVAL-quiescence-original05/continuous_physical192_observer_client_v5.py', 'sha256': '1049fcba433abb9df6490a01fd228001ca9aa15f442e4bfc52041c1d153ea0be'}}


def selected_ast(role):
    p=Path(SOURCES[role]['path']);raw=p.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=SOURCES[role]['sha256']:
        raise ValueError('Exact selected source required: '+role)
    return ast.parse(raw),str(p)


class FakeClock:
    def __init__(self):self.now=0.;self.sleeps=[]
    def monotonic(self):return self.now
    def sleep(self,value):
        if value<0:raise ValueError('Nonnegative synthetic sleep required')
        self.sleeps.append(value);self.now+=value


class Harness:
    """The actual acceptance routine is never replaced by a ready stub."""
    def __init__(self,root,*,parent=False,deadline=500.,ready_count=100,max_count=None,
                 stale=False,future=False,worker_death=None,prefix_fault=None,owner_fault=False):
        self.root=Path(root);self.root.mkdir(parents=True)
        self.clock=FakeClock();self.pace=.365
        self.ready_count=ready_count;self.max_count=max_count;self.stale=stale;self.future=future
        self.worker_death=worker_death;self.prefix_fault=prefix_fault;self.owner_fault=owner_fault
        self.launches=[];self.waits=[];self.live_reads=[];self.prefix_pin=None
        # Actual, SHA-bound immutable metadata helpers, not an unverified stub.
        tree,filename=selected_ast('worker')
        names={'require','identity','pin','checked','read','write'}
        ns=dict(Path=Path,hashlib=hashlib,json=json,os=os,stat=stat)
        nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name in names]
        exec(compile(ast.Module(body=nodes,type_ignores=[]),filename,'exec'),ns)
        self.helpers=SimpleNamespace(**ns)
        # Only selected control.identity is compiled; VolatileLiveControl is not constructed.
        tree,filename=selected_ast('control')
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='identity')
        ns=dict(stat=stat);exec(compile(ast.Module(body=[fn],type_ignores=[]),filename,'exec'),ns)
        self.control_identity=ns['identity']
        tree,filename=selected_ast('parent_client'if parent else'client')
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef)and n.name=='DedicatedMainHealth')
        cls=copy.deepcopy(cls)
        cls.body=[n for n in cls.body if isinstance(n,ast.FunctionDef)and n.name in('start','_accept')]
        cls.bases=[];cls.keywords=[];cls.decorator_list=[]
        def paths(value):
            return self.control if str(value)=='/dev/shm' else Path(value)
        def popen(argv,*,stdout,stderr):
            self.launches.append(list(argv))
            child=SimpleNamespace(pid=9001,returncode=None)
            def wait(timeout):
                self.waits.append((child,timeout));child.returncode=0;return 0
            child.wait=wait;return child
        ns=dict(os=os,Path=paths,time=self.clock,
            subprocess=SimpleNamespace(Popen=popen,STDOUT=-2))
        exec(compile(ast.fix_missing_locations(ast.Module(body=[cls],type_ignores=[])),filename,'exec'),ns)
        client=object.__new__(ns['DedicatedMainHealth']);self.client=client
        client.root=self.root/'scope';client.root.mkdir()
        client.output=self.root/'raw';client.output.mkdir()
        self.control=self.root/'SYNTHETIC-TMPFS';self.control.mkdir(mode=0o700)
        client.control_path=self.control;client.live_path=self.control/'live.json';client.live_path.write_bytes(b'SYNTHETIC LIVE PRODUCER')
        client.sources={key:SOURCES[key]for key in('worker','client')}
        client.sources['interpreter']=dict(path='/SYNTHETIC-NOT-EXECUTED/python')
        client.unit='synthetic-owned-health.service';client.job=dict(nonce='a'*32,maximum_gap_s=2.0)
        client.jobpin=self.helpers.write(client.root/'job.json',dict(SYNTHETIC=True,attempt=1,no_retry=True))
        client.child=None;client.finished=False;client.initial=None;client.last_live=None
        client.worker_owner=None;client.owner_pin=None;client.deadline=deadline
        client.control_module=SimpleNamespace(identity=self.control_identity)
        client.h=SimpleNamespace(put=lambda p,v:self.helpers.write(p,v))
        def birth(pid):
            if pid==9001:return 7001
            if pid==9002:
                return None if self.worker_death is not None and self.clock.now>=self.worker_death else 7002
            raise ValueError('No unselected process identity may be queried')
        def show(unit):
            if unit!=client.unit:raise ValueError('No foreign unit may be queried')
            return dict(ActiveState='active',SubState='running',NRestarts='0',MainPID='9002',
                InvocationID='b'*32,ControlGroup='/SYNTHETIC/owned-health')
        def read(path,limit=8<<20):
            if Path(path)==client.live_path:return self.publication()
            return self.helpers.read(path,limit=limit)
        client.common=SimpleNamespace(require=self.helpers.require,birth=birth,show=show,read=read,checked=self.helpers.checked)

    def publication(self):
        c=self.client;t=self.clock.now;count=max(1,int(math.floor((t+1e-10)/self.pace)))
        if self.max_count is not None:count=min(count,self.max_count)
        owner=copy.deepcopy(c.worker_owner)
        if self.owner_fault:owner['birth']+=1
        initial=None
        if count>=self.ready_count:
            if self.prefix_pin is None:
                binding=dict(job=c.jobpin,nonce=c.job['nonce'],owner=c.worker_owner)
                prefix=dict(schema='robotron-buffered-raw-readiness-v2',binding=binding,
                    sample_count=100,committed_records=100,committed_monotonic_s=t)
                if self.prefix_fault=='count':prefix['sample_count']=99
                elif self.prefix_fault=='commit':prefix['committed_records']=99
                elif self.prefix_fault=='binding':prefix['binding']=dict(binding,nonce='f'*32)
                elif self.prefix_fault=='future_commit':prefix['committed_monotonic_s']=t+1
                self.prefix_pin=self.helpers.write(c.root/'durable-prefix.json',prefix)
                self.initial_ready=t
            initial=dict(durable_prefix=self.prefix_pin,index=98 if self.prefix_fault=='index' else 99,
                durable_ready_monotonic_s=self.initial_ready)
        value=dict(schema='robotron-round-observer-live-v2',job=c.jobpin,nonce=c.job['nonce'],
            owner=owner,state='running',updated_monotonic_s=t-(2.0001 if self.stale else 0),
            observed_samples=count,initial=initial,phase='ready'if initial else'collecting_initial',
            control=dict(schema='robotron-owned-volatile-live-directory-v1',path=str(c.control_path),
                binding=dict(job=c.jobpin,nonce=c.job['nonce'],owner=c.worker_owner),
                volatile_not_scientific_raw_evidence=True,identity=self.control_identity(c.control_path.stat())),
            latest_sample=dict(schema='robotron-queued-raw-record-v2',path=str(c.output/('sample-%06d.json'%(count-1))),
                sha256='c'*64,bytes=100,sequence=count-1,kind='sample',index=count-1))
        if self.future:value['updated_monotonic_s']=t+.001
        self.live_reads.append(copy.deepcopy(value));return value


class Tests(unittest.TestCase):
    def test_measured_sample_pace_old30_fails_new120_reaches_durable100_once(self):
        with tempfile.TemporaryDirectory()as directory:
            old=Harness(Path(directory)/'old30',parent=True)
            with self.assertRaisesRegex(ValueError,'100-sample readiness proof'):old.client.start()
            self.assertGreaterEqual(old.clock.now,30.)
            self.assertLess(old.live_reads[-1]['observed_samples'],100)
            self.assertEqual(len(old.launches),1);self.assertEqual(len(old.waits),1)
            original=old.client.child
            with self.assertRaisesRegex(ValueError,'single-use'):old.client.start()
            self.assertIs(old.client.child,original);self.assertEqual(len(old.launches),1)
            new=Harness(Path(directory)/'new120')
            result=new.client.start()
            self.assertEqual(result['initial']['index'],99)
            prefix=new.helpers.read(new.helpers.checked(result['initial']['durable_prefix']))
            self.assertEqual(prefix['sample_count'],100);self.assertGreaterEqual(prefix['committed_records'],100)
            self.assertGreater(new.clock.now,30.);self.assertLess(new.clock.now,40.)
            self.assertEqual(len(new.launches),1);self.assertEqual(len(new.waits),1)
            self.assertIs(new.waits[0][0],new.client.child)
            with self.assertRaisesRegex(ValueError,'single-use'):new.client.start()
            self.assertEqual(len(new.launches),1)

    def test_readiness_deadline_owner_freshness_and_prefix_gates_remain_strict(self):
        with tempfile.TemporaryDirectory()as directory:
            settings=[dict(max_count=99),dict(deadline=20.),dict(worker_death=.5),dict(stale=True),
                dict(future=True),dict(owner_fault=True)]
            settings += [dict(prefix_fault=kind)for kind in('count','commit','binding','future_commit','index')]
            for i,options in enumerate(settings):
                with self.subTest(options=options):
                    h=Harness(Path(directory)/('negative-%02d'%i),**options)
                    with self.assertRaises(ValueError):h.client.start()
                    self.assertEqual(len(h.launches),1);self.assertEqual(len(h.waits),1)
                    child=h.client.child
                    with self.assertRaises(ValueError):h.client.start()
                    self.assertIs(h.client.child,child);self.assertEqual(len(h.launches),1)
                    if options.get('max_count')==99:self.assertGreaterEqual(h.clock.now,120.)
                    if options.get('deadline')==20.:self.assertLess(h.clock.now,20.2)
            # _accept itself retains the original source owner/publication/100 proof.
            h=Harness(Path(directory)/'accept');h.client.start();value=h.publication()
            for field,replacement in [('nonce','d'*32),('job',dict(foreign=True)),('state','stopped')]:
                bad=copy.deepcopy(value);bad[field]=replacement
                with self.subTest(identity=field),self.assertRaises(ValueError):h.client._accept(bad)
            bad=copy.deepcopy(value);bad['observed_samples']-=1
            bad['latest_sample']['index']-=1;bad['latest_sample']['sequence']-=1
            bad['latest_sample']['path']=str(h.client.output/('sample-%06d.json'%bad['latest_sample']['index']))
            with self.assertRaises(ValueError):h.client._accept(bad)
            self.assertEqual(len(h.launches),1)


if __name__=='__main__':unittest.main()
