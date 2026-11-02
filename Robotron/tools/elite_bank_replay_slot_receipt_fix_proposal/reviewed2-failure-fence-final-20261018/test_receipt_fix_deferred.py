"""Unexecuted isolated tests for an UNAPPLIED three-source receipt patch.

Only future root execution after full quality closure/release and original six
characterization tests. No project modules/torch/models/sockets/real worker or
filesystem mmap operations. NumPy math uses64-slot CPU arrays. Candidate source
is reconstructed and selected exact AST bodies run only during future tests.
"""
import ast,contextlib,hashlib,io,json,os,queue,re,stat,threading,time,unittest
from collections import deque
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np

HERE=Path(__file__).resolve().parent


def read(pin):
    p=Path(pin['path'])
    if p.suffix in ('.pt','.pth','.npy','.npz'):raise AssertionError('No model/replay referents')
    a=p.lstat();raw=p.read_bytes();b=p.lstat()
    identity=lambda x:(x.st_dev,x.st_ino,x.st_size,x.st_mtime_ns,x.st_ctime_ns,stat.S_IMODE(x.st_mode),x.st_uid,x.st_nlink)
    if not(stat.S_ISREG(a.st_mode) and identity(a)==identity(b) and len(raw)==pin['bytes'] and hashlib.sha256(raw).hexdigest()==pin['sha256']):raise AssertionError('Pinned source changed')
    return raw.decode()


def apply(raw,section,reverse=False):
    old=raw.splitlines(True);out=[];cursor=0;lines=section.splitlines(True);i=2
    while i<len(lines):
        m=re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@',lines[i])
        if not m:raise AssertionError('Invalid hunk')
        i+=1;begin=int(m.group(3 if reverse else 1))-1
        if begin<cursor:raise AssertionError('Overlapping hunk')
        out.extend(old[cursor:begin]);cursor=begin
        while i<len(lines) and not lines[i].startswith('@@ '):
            kind=lines[i][0];value=lines[i][1:];i+=1
            if kind==' ' or kind==('+' if reverse else '-'):
                if old[cursor]!=value:raise AssertionError('Hunk preimage differs')
                if kind==' ':out.append(value)
                cursor+=1
            elif kind==('-' if reverse else '+'):out.append(value)
            else:raise AssertionError('Hunk marker')
    out.extend(old[cursor:]);return ''.join(out)


def extract(raw,classname,names,ns):
    tree=ast.parse(raw)
    if classname=='module':container=tree
    else:
        found=[n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==classname]
        if len(found)!=1:raise AssertionError('Source class missing')
        container=found[0]
    if names=='WHOLE_SMALL_CLASS':body=[container]
    else:
        chosen=[n for n in container.body if isinstance(n,ast.FunctionDef) and n.name in names]
        if {n.name for n in chosen}!=set(names):raise AssertionError('Exact selected methods missing')
        body=chosen if classname=='module' else [ast.ClassDef(name=classname,bases=[],keywords=[],body=chosen,decorator_list=[])]
    # Actual ensure_live_mmap contains one stdlib shutil import in an untouched
    # branch; every other import is forbidden. Virtual tests keep that branch off.
    for node in ast.walk(ast.Module(body=body,type_ignores=[])):
        if isinstance(node,ast.ImportFrom):raise AssertionError('Project import forbidden')
        if isinstance(node,ast.Import) and [a.name for a in node.names]!=['shutil']:raise AssertionError('Unexpected import')
    program=ast.fix_missing_locations(ast.Module(body=body,type_ignores=[]))
    exec(compile(program,'<isolated unapplied receipt methods>','exec'),ns)


class ReceiptPatchContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec=json.loads((HERE/'test-source-contract.json').read_bytes());meta=json.loads(read(spec['preservation']))
        patch_text=read(spec['patch']);sections=re.split(r'(?=^--- a/)',patch_text,flags=re.M)[1:]
        if len(sections)!=3:raise AssertionError('Exactly three source deltas')
        cls.original={n:read(p) for n,p in meta['base_sources'].items()};cls.raw={}
        for name,section in zip(cls.original,sections):
            value=apply(cls.original[name],section)
            if apply(value,section,True)!=cls.original[name] or hashlib.sha256(value.encode()).hexdigest()!=meta['candidates'][name]['sha256']:raise AssertionError('Exact forward/reverse source failure')
            cls.raw[name]=value
        cls.raw.update({n:read(p) for n,p in spec['extra_sources'].items()});cls.spec=spec

    def setUp(self):
        self.unexpected=[]
        def forbidden(*a,**kw):self.unexpected.append((a,kw));raise AssertionError('Forbidden host/startup operation')
        self.forbidden=forbidden
        class Telemetry:
            def __init__(_,enabled):
                if enabled is not False:forbidden(enabled)
        self.cfg=SimpleNamespace(hof_enabled=True,ephof_enabled=True,hof_max_episodes=2,ephof_max_episodes=2,
            hof_episode_stride=64,ephof_episode_stride=64,interesting_replay_bank_size=64,
            hof_min_game_score=50000,ephof_min_episode_score=25000,interesting_replay_min_score=.5,
            max_interesting_replay_fraction=.3,pre_death_base_penalty=0.,pre_death_danger_penalty=0.,
            pre_death_priority_boost=2.,pre_death_lookback=150)
        ns=dict(np=np,deque=deque,queue=queue,time=time,RL_CONFIG=self.cfg,ACTOR_DQN=0,ACTOR_EPSILON=1,ACTOR_EXPERT=2,ACTOR_KIND_COUNT=3,
            NUM_MOVE=9,NUM_FIRE=9,NUM_JOINT=81,_native_propagate=None,_native_batch_update=None,
            exposure_enabled=lambda:False,ReplayInsertExposure=forbidden,stream_output_enabled=lambda:False,BankOutputTelemetry=Telemetry,
            threading=SimpleNamespace(Lock=threading.Lock,RLock=threading.RLock,Thread=forbidden,Event=threading.Event),open=forbidden)
        for filename in ('model.py','replay_buffer.py','agent.py','socket_server.py'):
            for name,methods in self.spec['selected_nodes'][filename].items():extract(self.raw[filename],name,methods,ns)
        self.ns=ns;self.Memory=ns['PrioritizedReplayBuffer'];self.Async=ns['AsyncReplayBuffer'];self.Agent=ns['RainbowAgent']

    def memory(self,width=4):return self.Memory(64,width)

    def agent(self,m):
        a=self.Agent.__new__(self.Agent);a.memory=m;return a

    def consumer(self,m):
        a=self.agent(m);c=self.Async.__new__(self.Async);c.agent=a;c._step_with_receipt=a.step_with_receipt;c.running=True
        c._stop_lock=threading.Lock();c.batch_size=1;c._lookback=150;c._client_indices={};c._episode_indices={}
        c._recent_ep_scores=deque(maxlen=20);c._recent_ep_levels=deque(maxlen=20);c.thresholds=[]
        def thresholds(*args):c.thresholds.append(args);return float('inf'),float('inf')
        c._elite_thresholds=thresholds;return c

    def item(self,cid,marker,ordinal,done=False):
        s=np.array([marker,ordinal,0.,0.],dtype=np.float32)
        return ('step',cid,(s,(0,0),float(marker),s+np.array([0.,0.,1.,0.]),done),dict(actor='dqn',horizon=1,priority_reward=float(marker)))

    def finite_queue(self,c,items,normal=True):
        owner=self
        class Q:
            def get(_,timeout):
                if timeout!=.01:owner.forbidden('queue timeout')
                if items:return items.pop(0)
                c.running=False;raise queue.Empty
            def get_nowait(_):
                if normal:owner.forbidden('unexpected bulk-read')
                if items:return items.pop(0)
                raise queue.Empty
        return Q()

    def drive(self,c,items):
        c.queue=self.finite_queue(c,items);output=io.StringIO()
        with contextlib.redirect_stdout(output):c._consume()
        self.assertEqual(output.getvalue(),'');self.assertFalse(items);self.assertEqual(self.unexpected,[])

    def scenario(self,foreign,elite=True):
        m=self.memory();c=self.consumer(m);items=[self.item('A',1,i) for i in range(32)]
        items += [self.item('B',2,i) for i in range(foreign)]
        if elite:items += [self.item('A',1,32,True),('elite','A',(100000,1,32.,33,60000,7001),None)]
        self.drive(c,items);return m,c

    def test_legacy_defaults_and_receipted_adds_share_every_successful_write(self):
        m=self.memory();a=self.agent(m);s=np.zeros(4,dtype=np.float32)
        self.assertIsNone(m.add(s,0,0.,s,False));self.assertEqual(m._ring_receipt_serial,1)
        self.assertEqual(a.step(s,(0,0),0.,s,False),1);self.assertEqual(m._ring_receipt_serial,2)
        receipt=a.step_with_receipt(s,(0,0),0.,s,False)
        self.assertEqual((receipt[0],receipt[2]),(2,3));self.assertIs(receipt[1],m._ring_receipt_epoch)
        with m.lock:np.testing.assert_array_equal(m._indices_from_receipts_locked([3],(receipt[1],True)),[2])
        self.assertEqual(m._adds_total,3)
        with self.assertRaises(TypeError):self.Async(SimpleNamespace(step=lambda:None))
        self.assertEqual(self.unexpected,[],'Missing receipt capability must fail BEFORE thread startup')

    def test_actual_consumer_no_overwrite_both_banks_and_fifo_reset_ack(self):
        m,c=self.scenario(0)
        for bank in ('hof','ephof'):
            self.assertEqual(getattr(m,bank+'_ep_count'),1);self.assertEqual(getattr(m,bank+'_ep_len')[0],33)
            np.testing.assert_array_equal(getattr(m,bank+'_states')[:33,0],np.ones(33))
            self.assertEqual(getattr(m,bank+'_ep_game')[0],7001)
        self.assertEqual(list(c._episode_indices['A']),[]);self.assertTrue(c._episode_indices['A'].complete);self.assertIsNone(c._episode_indices['A'].epoch)
        c.running=True;reset=threading.Event();barrier=threading.Event()
        self.drive(c,[('reset_client','A',None,{'event':reset}),self.item('A',1,99),('barrier',None,None,{'event':barrier})])
        self.assertTrue(reset.is_set());self.assertTrue(barrier.is_set());self.assertEqual(len(c._episode_indices['A']),1)

    def test_actual_crossactor_wrap_rejects_whole_banks_but_keeps_offers_stats_and_clear(self):
        m,c=self.scenario(64)
        self.assertEqual((m.hof_ep_count,m.ephof_ep_count),(0,0))
        self.assertEqual(list(m._hof_recent_offers),[100000]);self.assertEqual(list(m._ephof_recent_offers),[60000])
        self.assertEqual(list(c._recent_ep_scores),[100000]);self.assertEqual(list(c._recent_ep_levels),[1])
        self.assertEqual(list(c._episode_indices['A']),[]);self.assertTrue(c._episode_indices['A'].complete)
        self.assertEqual(m._adds_total,97)

    def test_deque_overflow_and_epoch_change_never_become_complete_bank_episode(self):
        m=self.memory();c=self.consumer(m);c._record_step('A',self.item('A',1,0)[2],self.item('A',1,0)[3])
        small=self.ns['_ReplayReceiptHistory'](m._ring_receipt_epoch,2);small.extend(c._episode_indices['A']);c._episode_indices['A']=small
        for i in (1,2):c._record_step('A',self.item('A',1,i)[2],self.item('A',1,i)[3])
        self.assertFalse(c._episode_indices['A'].complete)
        c._do_elite_episode_boost('A',100000,1,0.,3,60000,7001)
        self.assertEqual((m.hof_ep_count,m.ephof_ep_count),(0,0));self.assertEqual(len(m._hof_recent_offers),1)
        c._record_step('A',self.item('A',1,3)[2],self.item('A',1,3)[3]);m.clear()
        c._record_step('A',self.item('A',1,4)[2],self.item('A',1,4)[3]);self.assertFalse(c._episode_indices['A'].complete)
        c._do_elite_episode_boost('A',100001,1,0.,2,60001,7002)
        self.assertEqual((m.hof_ep_count,m.ephof_ep_count),(0,0));self.assertTrue(c._episode_indices['A'].complete)

    def test_stale_selected_writes_refuse_under_same_plain_lock_without_foreign_changes(self):
        m,c=self.scenario(64,False);h=c._client_indices['A'];context=(h.epoch,True)
        before={k:getattr(m,k).copy() for k in ('rewards','interesting')};tree=m.tree.tree.copy()
        self.cfg.pre_death_reward_lookback=90;self.cfg.pre_death_base_penalty=.1;self.cfg.pre_death_max_penalty=.35
        held=[]
        class Lock:
            def __enter__(_):
                if held:raise AssertionError('Nested plain-lock acquisition')
                held.append(True)
            def __exit__(_,typ,val,tb):held.pop()
        m.lock=Lock();actual=m._indices_from_receipts_locked;checks=[]
        def resolver(*args):
            self.assertTrue(held);checks.append(True);return actual(*args)
        m._indices_from_receipts_locked=resolver
        m.boost_priorities(list(h),2.,receipt_context=context)
        self.assertEqual(m.apply_pre_death_penalty(list(h),receipt_context=context),0)
        m.mark_interesting(list(h),1.,receipt_context=context)
        c._do_boost('A')
        self.assertGreaterEqual(len(checks),5)
        np.testing.assert_array_equal(m.tree.tree,tree)
        for k,v in before.items():np.testing.assert_array_equal(getattr(m,k),v)
        self.assertFalse(c._client_indices['A'])

    def test_partial_add_failures_publish_no_receipt_and_reanchor_before_unlock(self):
        m=self.memory();s=np.zeros(4);old=m.add_with_receipt(s,0,0.,s,False)
        class Bad:
            def __int__(_):raise ValueError('before-tree')
        with self.assertRaisesRegex(ValueError,'before-tree'):m.add_with_receipt(s,0,0.,s,False,actor_kind=Bad())
        self.assertIsNot(m._ring_receipt_epoch,old[1]);self.assertEqual(m._ring_receipt_serial,0)
        epoch=m._ring_receipt_epoch;pointer=m.tree.data_ptr
        class FailArray:
            def __setitem__(_,key,value):raise ValueError('after-tree')
        m.rewards=FailArray()
        with self.assertRaisesRegex(ValueError,'after-tree'):m.add_with_receipt(s,0,0.,s,False)
        self.assertIsNot(m._ring_receipt_epoch,epoch);self.assertEqual(m._ring_receipt_serial,0)
        self.assertEqual(m.tree.data_ptr,(pointer+1)%64);self.assertEqual(m._ring_receipt_origin,m.tree.data_ptr)
        with m.lock:self.assertIsNone(m._indices_from_receipts_locked([old[2]],(old[1],True)))

        # The actual async recording transaction must poison a missing prefix,
        # including failures before add and after a successful ring insertion.
        History=self.ns['_ReplayReceiptHistory']
        for mode in ('first-add','mid-before-add','malformed','episode-append','history-create'):
            with self.subTest(recording_failure=mode):
                m=self.memory();c=self.consumer(m);args=self.item('A',1,0)[2];kw=self.item('A',1,0)[3]
                if mode=='mid-before-add':
                    for i in range(4):c._record_step('A',self.item('A',1,i)[2],kw)
                before=m._adds_total;actual=c._step_with_receipt;epoch=m._ring_receipt_epoch
                cleanup=lambda:None
                if mode=='first-add':
                    class BadKind:
                        def __int__(_):raise ValueError('first-add')
                    original_kind=m.actor_kind_from_name
                    m.actor_kind_from_name=lambda *a:BadKind()
                    cleanup=lambda:setattr(m,'actor_kind_from_name',original_kind)
                elif mode=='mid-before-add':
                    def fail_before_add(*a,**k):raise ValueError('mid-before-add')
                    c._step_with_receipt=fail_before_add
                elif mode=='malformed':c._step_with_receipt=lambda *a,**k:(0,epoch)
                elif mode=='episode-append':
                    class FailAppend(History):
                        def append(h,value):
                            if not getattr(h,'failed_once',False):
                                h.failed_once=True;raise ValueError('episode-append')
                            return super().append(value)
                    c._episode_indices['A']=FailAppend(epoch,65_536)
                else:
                    class FailCreate(History):
                        attempts=0
                        def __init__(h,*a):
                            type(h).attempts+=1
                            if type(h).attempts==1:raise ValueError('history-create')
                            super().__init__(*a)
                    self.ns['_ReplayReceiptHistory']=FailCreate
                    cleanup=lambda:self.ns.__setitem__('_ReplayReceiptHistory',History)
                try:
                    with self.assertRaises((ValueError,RuntimeError)):c._record_step('A',args,kw)
                finally:cleanup();c._step_with_receipt=actual
                self.assertEqual(m._adds_total-before,1 if mode in ('first-add','episode-append','history-create') else 0,'No retry or second insertion')
                self.assertFalse(c._episode_indices['A'].complete)
                if mode=='mid-before-add':
                    self.assertIs(m._ring_receipt_epoch,epoch);self.assertEqual(len(c._episode_indices['A']),4)
                # More than either bank's minimum, all currently resident, but
                # the missing prefix still makes the WHOLE episode ineligible.
                items=[self.item('A',1,10+i,i==32) for i in range(33)]
                items += [('elite','A',(100000,1,32.,33,60000,7001),None)]
                self.drive(c,items)
                self.assertEqual((m.hof_ep_count,m.ephof_ep_count),(0,0))
                self.assertEqual(list(m._hof_recent_offers),[100000]);self.assertEqual(list(c._recent_ep_scores),[100000])
                self.assertTrue(c._episode_indices['A'].complete);self.assertFalse(c._episode_indices['A'])
                # Genuine FIFO reset/elite boundary clears the failure marker;
                # the next complete 33-row episode is eligible for both banks.
                c.running=True;ack=threading.Event()
                items=[('reset_client','A',None,{'event':ack})]+[self.item('A',1,50+i,i==32) for i in range(33)]
                items += [('elite','A',(100001,1,32.,33,60001,7002),None)]
                self.drive(c,items);self.assertTrue(ack.is_set())
                self.assertEqual((m.hof_ep_count,m.ephof_ep_count),(1,1))

        # Empty failure history must end at the same genuine elite boundary:
        # there may be no subsequent successful row before this life finishes.
        m=self.memory();c=self.consumer(m);actual=c._step_with_receipt
        def fail_empty(*a,**k):raise ValueError('empty-first-step')
        c._step_with_receipt=fail_empty
        with self.assertRaisesRegex(ValueError,'empty-first-step'):
            c._record_step('A',self.item('A',1,0)[2],self.item('A',1,0)[3])
        self.assertFalse(c._episode_indices['A']);self.assertFalse(c._episode_indices['A'].complete)
        c._do_elite_episode_boost('A',100000,1,0.,0,60000,7001)
        self.assertTrue(c._episode_indices['A'].complete);self.assertIsNone(c._episode_indices['A'].epoch)
        self.assertEqual(list(c._recent_ep_scores),[100000]);self.assertFalse(m._hof_recent_offers)
        c._step_with_receipt=actual
        self.drive(c,[self.item('A',1,i,i==32) for i in range(33)]+[('elite','A',(100001,1,32.,33,60001,7002),None)])
        self.assertEqual((m.hof_ep_count,m.ephof_ep_count),(1,1));self.assertEqual(m._adds_total,33)

    def test_clear_flush_and_nonzero_array_restore_invalidate_old_tokens_preserving_bank_formats(self):
        m,c=self.scenario(0);s=np.zeros(4);token=m.add_with_receipt(s,0,0.,s,False);before=m.hof_states.copy();adds=m._adds_total
        m.clear();self.assertIsNot(m._ring_receipt_epoch,token[1]);self.assertEqual(m._adds_total,adds)
        np.testing.assert_array_equal(m.hof_states,before);self.assertEqual(m.hof_ep_count,1)
        token=m.add_with_receipt(s,0,0.,s,False);out=io.StringIO()
        with contextlib.redirect_stdout(out):m.flush()
        self.assertEqual(out.getvalue().strip(),'Replay buffer flushed.');self.assertIsNot(m._ring_receipt_epoch,token[1])
        arrays={name:np.zeros_like(getattr(m,name)) for name in ('states','next_states','actions','rewards','dones','horizons','is_expert','actor_kind','interesting')}
        arrays['horizons'].fill(1);arrays['priorities']=np.ones(64)
        epoch=m._ring_receipt_epoch
        self.assertTrue(m._restore_from_arrays(arrays,17,1.,time.time(),'/unopened-metadata',False,saved_n=64))
        self.assertIsNot(m._ring_receipt_epoch,epoch);self.assertEqual(m._ring_receipt_origin,17)
        token=m.add_with_receipt(s,0,0.,s,False);self.assertEqual((token[0],token[2]),(17,1))
        with m.lock:np.testing.assert_array_equal(m._indices_from_receipts_locked([1],(token[1],True)),[17])

    @contextlib.contextmanager
    def virtual_files(self,m,fail_open=None,load=True):
        calls=[];owner=self;spec=m._storage_specs();arrays={name:np.zeros(shape,dtype=dtype) for name,(_,dtype,shape) in spec.items()}
        arrays['horizons'].fill(1);arrays['priorities']=np.ones(64,dtype=np.float64)
        allowed={('/virtual-ring/'+name+'.npy'):value for name,value in arrays.items()}
        def isfile(path):
            path=str(path)
            if path in allowed:return True
            if path=='/virtual-ring/_meta.npy':return False
            owner.forbidden('isfile',path)
        def read_array(path,mmap_mode=None):
            path=str(path);calls.append(('load',path))
            if path not in allowed:owner.forbidden('np.load',path)
            return allowed[path]
        def open_array(path,mode,dtype,shape):
            path=str(path);calls.append(('open',path))
            if fail_open and len([x for x in calls if x[0]=='open'])==fail_open:raise OSError('injected-map-failure')
            if path not in allowed or mode!='w+' or tuple(shape)!=allowed[path].shape or np.dtype(dtype)!=allowed[path].dtype:owner.forbidden('open_memmap',path)
            return np.zeros(shape,dtype=dtype)
        def save_array(path,value):
            calls.append(('save',str(path)))
            if str(path)!='/virtual-ring/_meta.npy.tmp.npy':owner.forbidden('np.save',path)
        def replace(a,b):
            calls.append(('replace',str(a),str(b)))
            if (str(a),str(b))!=('/virtual-ring/_meta.npy.tmp.npy','/virtual-ring/_meta.npy'):owner.forbidden('replace',a,b)
        class NP:
            load=staticmethod(read_array);save=staticmethod(save_array)
            lib=SimpleNamespace(format=SimpleNamespace(open_memmap=open_array))
            def __getattr__(_,name):
                if name in ('savez','loadtxt','savetxt','fromfile','memmap'):return owner.forbidden
                return getattr(np,name)
        def mkdir(path,exist_ok):
            calls.append(('mkdir',str(path)))
            if str(path)!='/virtual-ring' or exist_ok is not True:owner.forbidden('mkdir',path)
        fakeos=SimpleNamespace(path=SimpleNamespace(abspath=lambda p:'/virtual-ring' if p=='/virtual-ring' else owner.forbidden('abspath',p),
            join=os.path.join,isfile=isfile,isdir=lambda p:False if p=='/virtual-ring.tmp' else owner.forbidden('isdir',p)),
            makedirs=mkdir,replace=replace,remove=owner.forbidden,posix_fallocate=owner.forbidden)
        oldnp=self.ns['np'];oldos=self.ns.get('os');self.ns.update(np=NP(),os=fakeos)
        try:yield calls
        finally:
            self.ns['np']=oldnp
            if oldos is None:self.ns.pop('os',None)
            else:self.ns['os']=oldos
            self.assertEqual(self.unexpected,[])

    def test_mmap_ensure_promote_and_adopt_use_virtual_arrays_and_reanchor_including_failure(self):
        m=self.memory();epoch=m._ring_receipt_epoch
        with self.virtual_files(m) as calls:self.assertTrue(m.ensure_live_mmap('/virtual-ring',False))
        self.assertIsNot(m._ring_receipt_epoch,epoch);self.assertEqual(m._ring_receipt_origin,m.tree.data_ptr)
        m=self.memory();s=np.zeros(4);old=m.add_with_receipt(s,0,0.,s,False);out=io.StringIO()
        with self.virtual_files(m,fail_open=2),contextlib.redirect_stdout(out):self.assertFalse(m._promote_to_live_mmap('/virtual-ring',False))
        self.assertIn('injected-map-failure',out.getvalue());self.assertIsNot(m._ring_receipt_epoch,old[1]);self.assertEqual(m._ring_receipt_origin,m.tree.data_ptr)
        m=self.memory();old=m._ring_receipt_epoch
        with self.virtual_files(m):self.assertTrue(m._try_adopt_mmap_directory('/virtual-ring',23,64,1.,time.time(),False))
        self.assertIsNot(m._ring_receipt_epoch,old);self.assertEqual(m._ring_receipt_origin,23)
        token=m.add_with_receipt(s,0,0.,s,False);self.assertEqual((token[0],token[2]),(23,1))

    def test_receipt_boundary_crossbuffer_unknown_pointer_and_no_current_index_minting(self):
        m=self.memory();s=np.zeros(4);first=m.add_with_receipt(s,0,0.,s,False)
        for _ in range(63):m.add(s,0,0.,s,False)
        with m.lock:np.testing.assert_array_equal(m._indices_from_receipts_locked([1],(first[1],True)),[0])
        m.add(s,0,0.,s,False)
        with m.lock:
            self.assertIsNone(m._indices_from_receipts_locked([1],(first[1],True)))
            self.assertIsNone(m._indices_from_receipts_locked([True],(first[1],True)))
            self.assertIsNone(m._indices_from_receipts_locked([65],(self.memory()._ring_receipt_epoch,True)))
            self.assertIsNone(m._indices_from_receipts_locked([65],(first[1],False)))
            m.size=63;self.assertIsNone(m._indices_from_receipts_locked([65],(first[1],True)));m.size=64
            m.tree.data_ptr=7;self.assertIsNone(m._indices_from_receipts_locked([65],(first[1],True)))

    def test_stop_finishes_prefetched_work_then_drains_with_reset_barrier_and_serializes_callers(self):
        m=self.memory();c=self.consumer(m);events=[];reset=threading.Event();barrier=threading.Event()
        queued=[('reset_client','A',None,{'event':reset}),self.item('A',1,1),('barrier',None,None,{'event':barrier})]
        c.queue=self.finite_queue(c,queued,normal=False)
        class Worker:
            def join(_,timeout):
                events.append('join');self.assertEqual(timeout,5.)
                if len(events)==1:c._record_step('A',self.item('A',1,0)[2],self.item('A',1,0)[3]);events.append('prefetched-finished')
            def is_alive(_):return False
        c._thread=Worker();c.stop();self.assertEqual(events[:2],['join','prefetched-finished'])
        self.assertTrue(reset.is_set());self.assertTrue(barrier.is_set());self.assertEqual(m._adds_total,2)
        self.assertEqual(len(c._episode_indices['A']),1);self.assertFalse(queued)
        c.stop();self.assertEqual(m._adds_total,2)
        class Locked:
            def __enter__(_):raise AssertionError('Concurrent stop caller is serialized before state/queue access')
            def __exit__(_,*args):pass
        c._stop_lock=Locked();before=m._adds_total
        with self.assertRaisesRegex(AssertionError,'Concurrent stop'):c.stop()
        self.assertEqual(m._adds_total,before)

    def test_stop_join_timeout_refuses_second_consumer_and_keeps_pending_commands(self):
        m=self.memory();c=self.consumer(m);pending=[self.item('A',1,0)];c.queue=self.finite_queue(c,pending,normal=False)
        class Worker:
            def join(_,timeout):self.assertEqual(timeout,5.)
            def is_alive(_):return True
        c._thread=Worker()
        with self.assertRaisesRegex(TimeoutError,'refusing concurrent drain'):c.stop()
        self.assertEqual(m._adds_total,0);self.assertEqual(len(pending),1);self.assertFalse(c._episode_indices)
        self.assertEqual(self.unexpected,[])


if __name__=='__main__':unittest.main()
