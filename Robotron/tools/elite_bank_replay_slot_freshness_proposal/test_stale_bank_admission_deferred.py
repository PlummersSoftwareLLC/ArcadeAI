"""Dormant CPU characterization of stale elite-bank slots; AUTHOR UNEXECUTED.

Future root invocation only after current full quality closure/freeze release.
No project modules are imported: exact authenticated method ASTs are extracted
with explicit small-ring dependencies. NumPy is the sole third-party runtime.
No torch, socket, mmap, replay load/save or actual worker thread is constructed.
Tests characterize the CURRENT bug; the token predicate is a design reference,
not a selected production correction or proof of atomic token publication.
"""
import ast, contextlib, copy, hashlib, io, json, queue, stat, threading, unittest
from collections import deque
from pathlib import Path
from types import SimpleNamespace
import numpy as np

HERE=Path(__file__).resolve().parent


def read_source(pin):
    path=Path(pin['path'])
    if path.suffix!='.py':raise AssertionError('Source text only')
    before=path.lstat();raw=path.read_bytes();after=path.lstat()
    def identity(info):
        return (info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns,
                stat.S_IMODE(info.st_mode),info.st_uid,info.st_nlink)
    if not (stat.S_ISREG(before.st_mode) and identity(before)==identity(after) and len(raw)==pin['bytes']
            and hashlib.sha256(raw).hexdigest()==pin['sha256']):
        raise AssertionError('Exact held source changed')
    return raw.decode()


def exact_nodes(raw,class_name,names,namespace):
    # Only root's deferred test executes this parse/compile. Whole original
    # selected AST method nodes/decorators are retained; no statement surgery.
    tree=ast.parse(raw)
    if class_name=='module':container=tree
    else:
        matches=[n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==class_name]
        if len(matches)!=1:raise AssertionError('Exact source class missing')
        container=matches[0]
    chosen=[n for n in container.body if isinstance(n,ast.FunctionDef) and n.name in names]
    if {n.name for n in chosen}!=set(names):raise AssertionError('Exact source methods missing')
    if any(isinstance(n,(ast.Import,ast.ImportFrom)) for method in chosen for n in ast.walk(method)):
        raise AssertionError('Selected methods cannot import a project/host fallback')
    if class_name=='module':body=chosen
    else:
        # Fixture classes retain methods only, with no original startup/base,
        # decorators, class assignments or module imports executed.
        body=[ast.ClassDef(name=class_name,bases=[],keywords=[],body=chosen,decorator_list=[])]
    program=ast.fix_missing_locations(ast.Module(body=body,type_ignores=[]))
    exec(compile(program,'<authenticated isolated methods>','exec'),namespace)


def fresh(token,epoch,completed,next_slot,capacity):
    """Reference contract only; production integration is not implemented.

    One serial per successful write, trusted same-epoch pointer progression.
    Called under the future production mutation/admission lock, never after it.
    """
    if (type(token) is not tuple or len(token)!=3 or token[0]!=epoch
        or type(epoch) is not str or not epoch
        or any(type(v) is not int for v in (*token[1:],completed,next_slot,capacity))
        or capacity<=0 or completed<0 or not 0<=next_slot<capacity):return False
    _,serial,index=token
    if serial<=0 or not 0<=index<capacity:return False
    age=completed-serial
    return 0<=age<capacity and index==(next_slot-1-age)%capacity


class StaleEliteBankCharacterization(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        manifest=json.loads((HERE/'source-pins.json').read_bytes())
        cls.raw={name:read_source(pin) for name,pin in manifest['source_pins'].items()}
        cls.unexpected=[]
        def forbidden(*args,**kwargs):
            cls.unexpected.append((args,kwargs));raise AssertionError('Forbidden startup/host fallback')
        class Telemetry:
            def __init__(self,enabled):
                if enabled is not False:forbidden(enabled)
        cfg=SimpleNamespace(hof_enabled=True,ephof_enabled=True,hof_max_episodes=2,ephof_max_episodes=2,
            hof_episode_stride=64,ephof_episode_stride=64,interesting_replay_bank_size=64,
            hof_min_game_score=50000,ephof_min_episode_score=25000,
            interesting_replay_min_score=.5,max_interesting_replay_fraction=.3,
            pre_death_base_penalty=0.,pre_death_danger_penalty=0.,pre_death_priority_boost=2.)
        ns=dict(np=np,threading=threading,deque=deque,queue=queue,RL_CONFIG=cfg,
            ACTOR_DQN=0,ACTOR_EPSILON=1,ACTOR_EXPERT=2,ACTOR_KIND_COUNT=3,
            NUM_MOVE=9,NUM_FIRE=9,NUM_JOINT=81,
            _native_propagate=None,_native_batch_update=None,exposure_enabled=lambda:False,
            ReplayInsertExposure=forbidden,stream_output_enabled=lambda:False,BankOutputTelemetry=Telemetry)
        for filename in ('model.py','replay_buffer.py','agent.py','socket_server.py'):
            for classname,names in manifest['selected_nodes'][filename].items():
                exact_nodes(cls.raw[filename],classname,names,ns)
        actor_tree=ast.parse(cls.raw['actor_tags.py'])
        actual={n.targets[0].id:ast.literal_eval(n.value) for n in actor_tree.body
                if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name)}
        if any(actual[k]!=ns[k] for k in ('ACTOR_DQN','ACTOR_EPSILON','ACTOR_EXPERT','ACTOR_KIND_COUNT')):
            raise AssertionError('Held actor constants differ')
        cls.ns=ns;cls.cfg=cfg

    def setUp(self):self.unexpected.clear()

    def scenario(self,foreign_count,callback='elite'):
        memory=self.ns['PrioritizedReplayBuffer'](64,4)
        agent=self.ns['RainbowAgent'].__new__(self.ns['RainbowAgent']);agent.memory=memory
        consumer=self.ns['AsyncReplayBuffer'].__new__(self.ns['AsyncReplayBuffer'])
        consumer.agent=agent;consumer.running=True;consumer.batch_size=1
        consumer._lookback=150;consumer._client_indices={};consumer._episode_indices={}
        consumer._recent_ep_scores=deque(maxlen=20);consumer._recent_ep_levels=deque(maxlen=20)
        threshold_calls=[]
        def thresholds(*args):
            threshold_calls.append(args);return float('inf'),float('inf')
        consumer._elite_thresholds=thresholds  # Unrelated priority-elite gate kept false.
        commands=[]
        def step(cid,marker,ordinal,done=False):
            state=np.array([marker,ordinal,0.,0.],dtype=np.float32)
            commands.append(('step',cid,(state,(0,0),float(marker),state+np.array([0.,0.,1.,0.]),done),
                dict(actor='dqn',horizon=1,priority_reward=float(marker))))
        for i in range(32):step('A',1,i)
        for i in range(foreign_count):step('B',2,i)
        if callback=='elite':
            step('A',1,32,True)
            commands.append(('elite','A',(100000,1,32.,33,60000,7001),None))
        elif callback=='boost':commands.append(('boost','A',None,None))
        elif callback!='none':raise AssertionError('Fixture callback unknown')
        class FiniteQueue:
            def get(_,timeout):
                if timeout!=.01:
                    self.unexpected.append('queue timeout');raise AssertionError('Unexpected queue call')
                if commands:return commands.pop(0)
                consumer.running=False;raise queue.Empty
            def get_nowait(_):
                self.unexpected.append('get_nowait');raise AssertionError('batch_size1 forbids extra queue read')
        consumer.queue=FiniteQueue()
        printed=io.StringIO()
        with contextlib.redirect_stdout(printed):consumer._consume()
        self.assertEqual(printed.getvalue(),'','Actual consumer cannot hide errors in printed exception handling')
        self.assertEqual(self.unexpected,[]);self.assertFalse(commands)
        self.assertEqual(memory._adds_total,32+foreign_count+(callback=='elite'))
        self.assertEqual(len(threshold_calls),2 if callback=='elite' else 0)
        return memory,consumer

    def bank_rows(self,memory,bank):
        n=int(getattr(memory,bank+'_ep_len')[0])
        self.assertEqual(n,33);self.assertEqual(getattr(memory,bank+'_ep_count'),1)
        self.assertEqual(getattr(memory,bank+'_ep_game')[0],7001)
        self.assertEqual(getattr(memory,bank+'_ep_score')[0],100000 if bank=='hof' else 60000)
        return getattr(memory,bank+'_states')[:n].copy()

    def test_no_overwrite_real_consumer_and_both_banks_preserve_A_rows(self):
        memory,consumer=self.scenario(0)
        for bank in ('hof','ephof'):
            rows=self.bank_rows(memory,bank)
            np.testing.assert_array_equal(rows[:,0],np.ones(33))
            np.testing.assert_array_equal(rows[:,1],np.arange(33))
        self.assertEqual(list(consumer._episode_indices['A']),[])

    def test_global_wrap_real_consumer_banks_B_rows_under_A_episode(self):
        memory,consumer=self.scenario(64)
        for bank in ('hof','ephof'):
            rows=self.bank_rows(memory,bank)
            np.testing.assert_array_equal(rows[:,0],np.r_[np.full(32,2.),1.])
            np.testing.assert_array_equal(rows[:32,1],np.arange(32,64))
            self.assertEqual(rows[-1,1],32)
        self.assertEqual(list(consumer._episode_indices['A']),[])

    def test_reference_token_rejects_actual_overwritten_episode_before_callbacks(self):
        memory,_=self.scenario(64)
        tokens=[('epochA',serial,(serial-1)%64) for serial in range(1,33)]+[('epochA',97,32)]
        valid=[fresh(t,'epochA',memory._adds_total,memory.tree.data_ptr,64) for t in tokens]
        self.assertEqual(valid,[False]*32+[True])
        self.assertFalse(all(valid),'Design policy rejects entire incomplete episode, never silently relabels a fresh tail complete')
        good,_=self.scenario(0)
        good_tokens=[('epochA',serial,serial-1) for serial in range(1,34)]
        self.assertTrue(all(fresh(t,'epochA',good._adds_total,good.tree.data_ptr,64) for t in good_tokens))

    def test_reference_token_exact_wrap_epoch_and_pointer_boundaries(self):
        self.assertTrue(fresh(('e',1,0),'e',64,0,64))  # age63 remains resident
        self.assertFalse(fresh(('e',1,0),'e',65,1,64)) # age64 overwritten
        self.assertFalse(fresh(('old',65,0),'new',65,1,64))
        self.assertFalse(fresh(('e',65,1),'e',65,1,64)) # forged wrong index
        self.assertFalse(fresh(('e',True,0),'e',1,1,64))
        self.assertFalse(fresh(('e',66,1),'e',65,1,64)) # future serial
        # A reset/load can reuse pointer/count: epoch, not modulo alone, is mandatory.
        self.assertFalse(fresh(('before-clear',1,0),'after-clear',1,1,64))

    def test_connected_predeath_callback_can_boost_foreign_slots(self):
        memory,consumer=self.scenario(64,'boost')
        np.testing.assert_array_equal(memory.states[:32,0],np.full(32,2.))
        # All unboosted leaf priorities were1 (reward1 A or reward2 B sets
        # 2**alpha for B); actual callback doubles B's live current leaves.
        baseline=2.**memory.alpha
        np.testing.assert_allclose(memory.tree.tree[64:96],np.full(32,2.*baseline))
        self.assertEqual(list(consumer._client_indices['A']),[])
        self.assertFalse(any(fresh(('e',s,s-1),'e',96,32,64) for s in range(1,33)))

    def test_extraction_and_scope_stay_pinned_and_small(self):
        memory,_=self.scenario(0)
        self.assertEqual(memory.capacity,64);self.assertEqual(memory.state_size,4)
        self.assertIsNone(memory._insert_exposure);self.assertIsNone(memory._mmap_dir)
        self.assertFalse(hasattr(memory,'_ring_freshness_epoch'),'No production fix is installed by this fixture')
        self.assertEqual(self.unexpected,[])


if __name__=='__main__':unittest.main()
