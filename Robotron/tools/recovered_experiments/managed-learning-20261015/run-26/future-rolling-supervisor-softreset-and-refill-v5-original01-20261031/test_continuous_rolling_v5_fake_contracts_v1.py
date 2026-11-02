"""Root-only actual-method fake contracts. No production imports/processes/network.

Extracts only selected v5 constants, pure predicates and class definitions into
an isolated namespace. API, proc/TCP helper, Popen, clock, event persistence and
paths are FAKE collaborators. This establishes branch contracts, not kernel,
Main, fleet, throughput, scoring quality or runtime/deployment qualification.
"""
import argparse
import ast
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import sys
import time
from types import SimpleNamespace

SELECTED_SOURCE={'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-supervisor-softreset-and-refill-v5-original01-20261031/continuous_training_fleet_v5.py', 'sha256': '5687eb6b4927b3ddd71f251f4f3d042de5513ebcf0ff0cfe537a674dcca69814', 'bytes': 48472, 'identity': {'device': 2304, 'inode': 82604565, 'bytes': 48472, 'mtime_ns': 1793408872157346548, 'ctime_ns': 1793409015434420057, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}


def check(ok,reason):
    if not ok:raise AssertionError(reason)


def fullpin(path):
    p=Path(path);check(p.is_absolute()and p.resolve(strict=True)==p and not p.is_symlink(),'Canonical source')
    identity=lambda s:dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,
        ctime_ns=s.st_ctime_ns,mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink)
    before=p.stat();check(stat.S_ISREG(before.st_mode)and before.st_size<=100000,'Bounded source')
    raw=p.read_bytes();check(identity(before)==identity(p.stat()),'Source moved')
    return dict(path=str(p),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),identity=identity(before)),raw


class Clock:
    def __init__(self):self.mono=100.;self.wall=1000.
    def monotonic(self):return self.mono
    def time(self):return self.wall
    def monotonic_ns(self):return int(self.mono*1e9)
    def sleep(self,value):self.mono+=value;self.wall+=value


class Child:
    def __init__(self,pid=501,code=None):self.pid=pid;self.code=code;self.waited=[]
    def poll(self):return self.code
    def wait(self,timeout):self.waited.append(timeout);return self.code
    def terminate(self):raise AssertionError('No real/synthetic signal allowed here')
    def kill(self):raise AssertionError('No real/synthetic signal allowed here')


class VirtualPath:
    def __init__(self,value='virtual'):self.value=value
    def __truediv__(self,part):return VirtualPath(self.value+'/'+part)
    def mkdir(self,**kw):pass
    def open(self,*args,**kw):return self
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def exists(self):return False


class Contracts:
    def __init__(self,raw):
        self.clock=Clock();self.stored={};self.serial=0;self.spawns=[]
        tree=ast.parse(raw);names={'MODE','CLEANUP_FLAGS','CONNECTION_FIELDS','ORIGINAL_FIELDS'}
        body=[n for n in tree.body if (isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id in names for t in n.targets))
            or isinstance(n,ast.FunctionDef)and n.name in ('require','closed_connection','train_refill_eligible','train_journal_binding')
            or isinstance(n,ast.ClassDef)and n.name=='ContinuousTrainingFleet']
        check(len(body)==9,'Exact extracted constants/helpers/class inventory')
        self.ns=dict(json=json,hashlib=hashlib,math=math,time=self.clock,
            os=SimpleNamespace(getuid=lambda:1001,environ={}),read=self.read,
            exclusive=lambda path,**kw:self.save(dict(raw=kw.get('raw'))),
            subprocess=SimpleNamespace(Popen=self.popen,STDOUT='FAKE_STDOUT'))
        exec(compile(ast.Module(body=body,type_ignores=[]),'<selected-v5-actual-methods>','exec'),self.ns)
        self.cls=self.ns['ContinuousTrainingFleet']
    def save(self,value):
        self.serial+=1;pin=dict(path='/FAKE/'+str(self.serial),sha256=str(self.serial))
        self.stored[pin['path']]=copy.deepcopy(value);return pin
    def read(self,pin):return copy.deepcopy(self.stored[pin['path']])
    def popen(self,*args,**kwargs):
        self.spawns.append((args,kwargs));return Child(600+len(self.spawns))
    def make(self,role=False):
        f=self.cls.__new__(self.cls);slot=100
        f.cfg=dict(trainer=dict(server_stamp=dict(pid=99,birth=88)),max_faults=3,startup_s=5,fault_cleanup_s=10,
            actor_common_environment={'SOURCE':'held'},mame_argv=['/usr/games/mame','robotron'],
            launch_argv=['/FAKE/wrapper','robotron'],parent_environment={},input_environment_keys=['ROBOTRON_CLIENT_SLOT'])
        f.owner=dict(pid=500,cgroup='/FAKE/owned');f.source={};f.root=VirtualPath()
        f.errors=['historical unrelated slot5 error'];f.stopping=False;f.roles={str(slot):role}
        f.policy_generation=0;f.binding_history={};f.binding_closures={};f.initial_bound=set();f.reaped_history=[]
        f.completed_train=f.completed_eval=f.partial_games=f.train_score_sum=f.unverified_train_games=0
        f.seen_jids=set();f.barrier=None;f.snapshot=lambda:None
        f.error_summary=lambda:dict(historical_errors_retained=True)
        f.original_membership=dict(immutable='FIRST_ORIGINAL_MEMBERSHIP')
        f.original_slots={str(slot):dict(original_binding='IMMUTABLE')};f.events=[]
        def event(kind,slot,inc,data):
            value=dict(kind=kind,slot=slot,incarnation=inc,unix_s=self.clock.time(),data=data)
            f.events.append(copy.deepcopy(value));return self.save(value)
        f.event=event
        old=dict(token='99:88:cleanup:1',client_id=100,client_slot=slot,eval_only=role,
                 connection_ns=10,socket_endpoints=dict(peer=['127.0.0.1',40001],server=['127.0.0.1',9998]))
        initial=self.save(dict(data=dict(connection=old)))
        intent=self.save(dict(unix_s=900,data={}))
        f.records={slot:dict(eval_only=role,incarnation=1,state='active_eval'if role else'active_train',
            original_child=dict(pid=501,birth=77,controlled_env={}),connection_binding=initial,
            spawn_intent=intent,closure=None,natural_result=None,prior_fault_closure=None,
            quarantine_reason=None,faults=0,original_child_receipt={})}
        f.children={slot:dict(child=Child(),incarnation=1,started=90,token=old['token'],tokens={old['token']},faults=0)}
        f.binding_history[slot]=[dict(binding=initial,connection=copy.deepcopy(old),authenticated_unix_s=900,
            incarnation=1,spawn_intent=intent)]
        current=dict(old,token='99:88:cleanup:2',client_id=192,connection_ns=20,
            socket_endpoints=dict(peer=['127.0.0.1',40002],server=['127.0.0.1',9998]))
        flags=self.ns['CLEANUP_FLAGS']
        cleanup=dict(old,schema='robotron-prospective-connection-cleanup-receipt-v2',server_stamp=f.cfg['trainer']['server_stamp'],
            observed_unix_s=999.,cleanup_error=None,ready_for_external_join=True,replay_admission_open=True,
            terminal_receipt=None,terminal_line_sha256=None,**{k:True for k in flags})
        f.cleanup_by_token={old['token']:cleanup};f.current=current;f.get_calls=[]
        policy=dict(schema='robotron-continuous-main-policy-v1',continuous_training_mode=True,
            main_measurement_entry_disabled=True,measurement_active=False,measurement_generation=0,
            ratchet_frozen=False,replay_admission_open=True,consumer_error=None,training_enabled=True)
        def get(path,query=None):
            f.get_calls.append((path,query))
            if path=='/api/connection_cleanup_token':return copy.deepcopy(f.cleanup_by_token[query['token']])
            if path=='/api/continuous_training_policy':return copy.deepcopy(policy)
            if path=='/api/continuous_training_connections':return dict(policy,connections=
                [copy.deepcopy(f.current)]if f.children[slot]['child'].poll()is None else[])
            raise AssertionError('Unexpected fake API path')
        f.get=get;f.owner_record=lambda:f.owner
        expected=dict(f.cfg['actor_common_environment'],ROBOTRON_CLIENT_SLOT=str(slot),ROBOTRON_ACTOR_ROUND='1',
            ROBOTRON_EVAL_MODE='1'if role else'2',ROBOTRON_RETIRE_AFTER_GAME='1'if role else'0',ROBOTRON_PREVIEW_CLIENT='0')
        f.actor=dict(pid=501,birth=77,parent=500,uid=1001,cgroup='/FAKE/owned',command=f.cfg['mame_argv'],
                     exe='/usr/games/mame',environment=expected)
        f.tcp_calls=[];f.actor_calls=0
        def actor(pid):f.actor_calls+=1;return copy.deepcopy(f.actor)
        def tcp(pid,endpoints):
            f.tcp_calls.append((pid,copy.deepcopy(endpoints)))
            return dict(inode=123,local=endpoints['peer'],remote=endpoints['server'])
        def birth(pid):
            if pid==501:raise FileNotFoundError('FAKE absent original')
            return dict(pid=pid,birth=100+pid,parent=500)
        f.physical=SimpleNamespace(actor=actor,tcp_binding=tcp,birth=birth,cgroup=lambda pid:'/FAKE/owned')
        f.journals=lambda:None
        f.tail=SimpleNamespace(pending=b'',path=VirtualPath(),position=0)
        return f,old,current,cleanup
    def reject(self,call,fragment=None):
        try:call()
        except (ValueError,AssertionError)as error:
            if fragment:check(fragment in str(error),'Unexpected rejection: '+str(error))
            return
        raise AssertionError('Expected rejection was accidentally accepted')
    def complete(self,f,slot=100):
        f.observe_train(slot,[copy.deepcopy(f.current)])
        check(len(f.binding_history[slot])==2 and f.children[slot]['child'].pid==501,'Rebind replaced or omitted actor')


def run_groups(c):
    results=[]
    def group(name,fn):fn();results.append(dict(name=name,status='PASS'))
    def success():
        f,old,new,cleanup=c.make();baseline=copy.deepcopy((f.original_membership,f.original_slots,f.binding_history))
        c.complete(f)
        check(f.children[100]['token']==new['token']and f.children[100]['tokens']=={old['token'],new['token']},'Token history')
        check(len(f.tcp_calls)==2 and f.actor_calls==4,'Both physical proofs required')
        check((f.original_membership,f.original_slots)==baseline[:2]and f.binding_history[100][0]==baseline[2][100][0],
              'Original membership/history mutated')
        check(f.records[100]['state']=='active_train'and old['token']in f.binding_closures,'Successful rebind state')
        check(f.errors and not c.spawns,'Unrelated errors erased or a child spawned')
    group('01_same_owned_process_rebind_and_immutable_originals',success)
    def incomplete():
        for flag in c.ns['CLEANUP_FLAGS']+('ready_for_external_join','replay_admission_open'):
            f,old,new,_=c.make();f.cleanup_by_token[old['token']][flag]=False
            f.observe_train(100,[new]);check(len(f.binding_history[100])==1 and f.records[100]['state']=='reconnecting_train','Incomplete primitive accepted')
        for flag in c.ns['CLEANUP_FLAGS']:
            f,old,new,_=c.make();f.cleanup_by_token[old['token']][flag]=1
            c.reject(lambda:f.observe_train(100,[new]),'Typed cleanup')
            f,old,new,_=c.make();del f.cleanup_by_token[old['token']][flag]
            c.reject(lambda:f.observe_train(100,[new]),'Complete typed cleanup')
    group('02_false_missing_nonbool_cleanup_never_authenticates',incomplete)
    def cleanup_faults():
        for key,value in [('token','wrong'),('client_id',55),('client_slot',5),('eval_only',True),
                          ('connection_ns',9),('socket_endpoints',{}),('server_stamp',{}),('cleanup_error','late ACK error')]:
            f,old,new,_=c.make();f.cleanup_by_token[old['token']][key]=value
            c.reject(lambda:f.observe_train(100,[new]));check(len(f.binding_history[100])==1,'Fault appended binding')
    group('03_exact_old_token_identity_source_and_error',cleanup_faults)
    def physical():
        for key,value in [('pid',502),('birth',78),('parent',499),('uid',0),('cgroup','/other'),
                          ('exe','/other'),('command',['other']),('environment',{})]:
            f,old,new,_=c.make();f.actor[key]=value;c.reject(lambda:f.observe_train(100,[new]),'Actual MAME')
        f,old,new,_=c.make()
        def badtcp(*args):raise ValueError('No unique actual process socket')
        f.physical.tcp_binding=badtcp;c.reject(lambda:f.observe_train(100,[new]),'No unique')
        f,old,new,_=c.make();counter=[0]
        def aba(pid):
            counter[0]+=1;value=copy.deepcopy(f.actor)
            if counter[0]==2:value['birth']+=1
            return value
        f.physical.actor=aba;c.reject(lambda:f.observe_train(100,[new]),'Original actor changed')
    group('04_actual_actor_environment_TCP_and_birth_ABA_refusals',physical)
    def candidates():
        f,old,new,_=c.make();c.reject(lambda:f.observe_train(100,[new,new]),'Ambiguous')
        f,old,new,_=c.make();bad=dict(new,eval_only=True);c.reject(lambda:f.observe_train(100,[bad]),'changed TRAIN role')
        for patch in [dict(token=old['token']),dict(connection_ns=old['connection_ns']),dict(client_id=True)]:
            f,old,new,_=c.make();bad=dict(new,**patch);c.reject(lambda:f.observe_train(100,[bad]),'Fresh never-used')
        f,old,new,_=c.make();f.children[100]['child'].code=0;c.reject(lambda:f.observe_train(100,[new]),'Live owned TRAIN')
        f,old,new,_=c.make(role=True);c.reject(lambda:f.observe_train(100,[new]),'Live owned TRAIN')
    group('05_no_duplicate_role_token_PID_or_EVAL_adoption',candidates)
    def repeat_and_deadline():
        f,old,new,_=c.make();f.current=dict(new,token='changed-again')
        c.reject(lambda:f.observe_train(100,[new]),'changed during kernel proof')
        f,old,new,_=c.make();base=f.physical.tcp_binding;count=[0]
        def tcp(*args):
            count[0]+=1;value=base(*args)
            if count[0]==2:value['inode']+=1
            return value
        f.physical.tcp_binding=tcp;c.reject(lambda:f.observe_train(100,[new]),'physical identity/TCP changed')
        f,old,new,_=c.make();f.observe_train(100,[]);c.clock.mono+=15.001
        c.reject(lambda:f.observe_train(100,[new]),'within declared');check(len(f.binding_history[100])==1,'Expired bind')
        c.clock.mono=100
        f,old,new,_=c.make();base=f.physical.tcp_binding
        def slow(*args):c.clock.mono+=8;return base(*args)
        f.physical.tcp_binding=slow;c.reject(lambda:f.observe_train(100,[new]),'exceeded declared')
        c.clock.mono=100
    group('06_repeated_API_TCP_and_total_gap_deadline',repeat_and_deadline)
    def history():
        f,old,new,_=c.make();c.complete(f)
        context=dict(measurement_generation=0,measurement_active=False,ratchet_frozen=False)
        row=dict(client_id=192,client_slot=100,eval_only=False,start_unix_s=1001.,end_unix_s=1010.,
            start_context=context,end_context=context,score=1000,journal_game_id='game1',
            complete=True,eligible=True,known_start=True,boundary_reason='score_reset')
        choose=c.ns['train_journal_binding'];pick=lambda r:choose(r,f.binding_history[100],f.binding_closures,0)
        check(pick(row)['connection']['token']==new['token'],'New CID did not join authenticated history')
        f.journal_row(row,b'FAKE_VALID_JSON_LINE\n');check(f.completed_train==1 and f.train_score_sum==1000,'Verified count')
        pre=dict(row,journal_game_id='preauth',start_unix_s=999.)
        f.journal_row(pre,b'FAKE_PREAUTH_JSON_LINE\n');check(f.completed_train==1 and f.unverified_train_games==1,'Preauth credited')
        f.records[100]['quarantine_reason']='Local identity rejected'
        f.journal_row(dict(row,journal_game_id='quarantined'),b'FAKE_QUARANTINED_LINE\n')
        check(f.completed_train==1 and f.unverified_train_games==2,'Locally quarantined identity credited')
        f.records[100]['quarantine_reason']=None
        reused=dict(f.binding_history[100][-1],authenticated_unix_s=1020.,connection=dict(new,token='third'))
        h=f.binding_history[100]+[reused]
        check(choose(row,h,f.binding_closures,0)is None,'Delayed same-CID row attributed to earlier token')
        check(pick(dict(row,client_id=77))is None,'Unknown CID adopted')
        c.reject(lambda:pick(dict(row,client_slot=5)),'binding role/slot differs')
        wrongrole=dict(row,journal_game_id='wrong-role',eval_only=True)
        c.reject(lambda:f.journal_row(wrongrole,b'FAKE_WRONG_ROLE_LINE\n'),'Durable journal role changed')
        check(pick(dict(row,client_id=100,start_unix_s=950.,end_unix_s=1001.))is None,
              'Old-token game ending after complete cleanup was credited')
        for ctx in ('start_context','end_context'):
            bad=copy.deepcopy(row);bad[ctx]=dict(context,measurement_generation=1);c.reject(lambda:pick(bad),'policy differs')
        for key,value in [('start_unix_s',float('nan')),('end_unix_s',float('inf')),('start_unix_s',True)]:
            bad=dict(row,**{key:value});c.reject(lambda:pick(bad),'clock/policy')
    group('07_new_and_reused_CID_journal_intervals_no_retroactive_credit',history)
    def closure():
        f,old,new,_=c.make();c.complete(f)
        current_cleanup=dict(f.cleanup_by_token[old['token']],**new,observed_unix_s=1011.)
        f.cleanup_by_token[new['token']]=current_cleanup;f.children[100]['child'].code=0
        check(f.close_original(100)is True,'Owned closure refused')
        close=c.read(f.records[100]['closure'])['data']
        check(close['actual_exit']==0 and close['original_wait_reaped']is True
            and close['original_birth_absent']is True and len(close['connection_cleanup'])==2,'Missing full closure')
        check(f.records[100]['state']=='fault_cleanup'and f.records[100]['faults']==1,'Closure counter')
        blocked,old,new,_=c.make();blocked.children[100]['unbound_candidate_token']='unproved'
        blocked.children[100]['child'].code=0;c.reject(lambda:blocked.close_original(100),'unbound token')
        check(c.ns['train_refill_eligible'](f.records[100],3)and f.errors,'Slot-local eligibility depends on unrelated errors')
        for badtoken in (old['token'],new['token']):
            blocked,first,last,_=c.make();c.complete(blocked)
            blocked.cleanup_by_token[last['token']]=dict(blocked.cleanup_by_token[first['token']],**last,observed_unix_s=1011.)
            blocked.cleanup_by_token[badtoken]['FIFO_reset_executed']=False
            blocked.children[100]['child'].code=0
            check(blocked.close_original(100)is False and blocked.records[100]['closure']is None,
                  'An old/new token without ACK allowed refill closure')
    group('08_positive_Popen_reap_birth_absence_all_token_cleanup',closure)
    def refill():
        for previous_faults in (0,1):
            f,old,new,cleanup=c.make();f.records[100]['faults']=previous_faults
            f.children[100]['child'].code=0
            check(f.close_original(100),'Original close')
            check(f.records[100]['faults']==previous_faults+1,'Fault counter before refill')
            before=len(c.spawns);f.spawn(100)
            check(len(c.spawns)==before+1 and f.records[100]['incarnation']==2
                and f.children[100]['child'].pid==600+len(c.spawns),'No local new incarnation at fault1/2')
            check(f.errors and f.original_slots["100"]==dict(original_binding='IMMUTABLE'),'History erased')
        f,old,new,_=c.make();f.records[100]['state']='quarantined'
        f.records[100]['quarantine_reason']='Local physical identity mismatch'
        f.children[100]['child'].code=0
        check(f.close_original(100)is True and f.records[100]['closure']is not None,'Local quarantine lost actual closure')
        check(f.records[100]['state']=='quarantined'and not c.ns['train_refill_eligible'](f.records[100],3),
              'Positive closure erased local identity quarantine')
        before=len(c.spawns);c.reject(lambda:f.spawn(100));check(len(c.spawns)==before,'Local quarantine spawned')
        for change in [dict(eval_only=True),dict(closure=None),dict(faults=3),dict(state='quarantined'),
                       dict(quarantine_reason='local identity rejected')]:
            f,old,new,_=c.make();f.records[100].update(state='fault_cleanup',faults=1,closure=c.save(dict(data={})))
            f.records[100].update(change);before=len(c.spawns);c.reject(lambda:f.spawn(100))
            check(len(c.spawns)==before,'Illegal new child created')
    group('09_actual_spawn_fault1_and_fault2_despite_errors_fault3_EVAL_refused',refill)
    def bootstrap_and_unchanged():
        f,old,new,_=c.make();f.children={};f.records={};f.get=lambda *args,**kw:dict(connections=[old])
        before=len(c.spawns);c.reject(f.run,'zero old/unowned connections')
        check(len(c.spawns)==before,'Live old cohort adopted')
        f,old,new,_=c.make();before=copy.deepcopy((f.binding_history,f.binding_closures));f.observe_train(100,[old])
        check((f.binding_history,f.binding_closures)==before and not f.tcp_calls,'Stable token incorrectly rebound')
        # A durable natural EVAL row must be drained before a missing TCP row
        # can be misclassified. Exercise the actual run/journal/closure methods.
        f,old,new,cleanup=c.make(role=True);f.records[100]['state']='active_eval'
        oldget=f.get
        def get(path,query=None):
            if path=='/api/continuous_training_connections':
                return dict(connections=[],continuous_training_mode=True,main_measurement_entry_disabled=True)
            return oldget(path,query)
        f.get=get;drained=[False]
        context=dict(measurement_generation=0,measurement_active=False,ratchet_frozen=False)
        result=dict(journal_game_id='EVAL-first',client_slot=100,eval_only=True,client_id=100,
            start_unix_s=950.,end_unix_s=999.,start_context=context,end_context=context,
            score=123,complete=True,eligible=True,known_start=True,boundary_reason='score_reset')
        def drain():
            if drained[0]:return
            drained[0]=True;f.journal_row(result,b'FAKE_EVAL_NATURAL_LINE\n')
            cleanup=f.cleanup_by_token[old['token']];cleanup['terminal_receipt']=result
            cleanup['terminal_line_sha256']=c.read(f.records[100]['natural_result'])['data']['raw_line']['sha256']
            f.children[100]['child'].code=0;f.stopping=True
        f.journals=drain
        def error(*args,**kwargs):raise AssertionError('EVAL drain ordering produced a slot error')
        f.record_error=error;f.run()
        check(f.completed_eval==1 and f.records[100]['state']=='closed_eval','EVAL natural terminal ordering/closure')
    group('10_fresh_bootstrap_refuses_live_takeover_stable_token_unchanged',bootstrap_and_unchanged)
    return results


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',required=True)
    p.add_argument('--source-sha256',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    started=time.monotonic();selected,raw=fullpin(a.source)
    check(SELECTED_SOURCE is not None and selected==SELECTED_SOURCE and selected['sha256']==a.source_sha256,'Exact frozen selected supervisor')
    output=Path(a.output);check(output.is_absolute()and not output.exists(),'Fresh explicit Root output required')
    output.mkdir(mode=0o700)
    def audit(event,args):
        if event.startswith(('socket.','subprocess.'))or event in ('os.system','ctypes.dlopen'):
            raise AssertionError('Forbidden runtime effect '+event)
        if event=='open':
            name=args[0]
            if isinstance(name,(str,bytes)):
                path=os.fsdecode(name)
                if path.startswith(('/proc/','/sys/'))or path.endswith(('.pt','.npy','.npz','.jsonl')):
                    raise AssertionError('Forbidden runtime/model/journal read')
        if event=='import'and str(args[0]).split('.')[0]in ('torch','numpy','socket','subprocess','urllib'):
            raise AssertionError('Forbidden runtime module import')
    sys.addaudithook(audit)
    cases=run_groups(Contracts(raw))
    after,_=fullpin(a.source);check(after==selected,'Selected source changed')
    report=dict(schema='robotron-rolling-supervisor-v5-fake-contract-report-v1',status='PASS_ENGINEERING_ONLY',
        tests=len(cases),failures=0,cases=cases,source=selected,elapsed_s=time.monotonic()-started,
        all_collaborators_fake=True,production_imported=False,proc_API_network_subprocess_model_reads=False,
        actual_kernel_TCP_or_Main_or_fleet_proved=False,deployment_or_quality_qualified=False)
    path=output/'report.json'
    with path.open('x')as stream:
        json.dump(report,stream,indent=2,allow_nan=False);stream.write('\n');stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
    print(json.dumps(dict(status=report['status'],tests=len(cases),report=str(path))))


if __name__=='__main__':main()
