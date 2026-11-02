"""Current/candidate exact AST checks and small timing; no server/Torch import.

Synthetic192 states include >100M, zeros and negative levels. Real threading
locks and a forced16-caller collision test the shared double-check under3.14t.
"""
import ast
import copy
import json
from pathlib import Path
import statistics
import sys
import threading
import time
import types

HERE=Path(__file__).resolve().parent


def method(source,cls,name):
    tree=ast.parse(source)
    owner=next(n for n in tree.body if isinstance(n,ast.ClassDef)and n.name==cls)
    return next(n for n in owner.body if isinstance(n,ast.FunctionDef)and n.name==name)


def compile_method(node,namespace):
    code=ast.fix_missing_locations(ast.Module(body=[copy.deepcopy(node)],type_ignores=[]))
    exec(compile(code,'<EXACT-source-AST-'+node.name+'>','exec'),namespace)
    return namespace[node.name]


class States(dict):
    def __init__(self,values):super().__init__(values);self.values_calls=0
    def values(self):self.values_calls+=1;return super().values()


class Metrics:
    def __init__(self,avg,note):
        self.lock=threading.Lock();self.measurement_active=False;self.publications=0
        self.average_level=0.;self.average_game_score=0.;self.eval_now_level=0.
        self.peak_level=0;self.peak_game_score=0;self.rscr_bucket_frames=0;self.rscr_bucket_score=0.
        self.score_pushes=[];self.level_pushes=[]
        self._push_score_1m_locked=self.score_pushes.append
        self._push_level_1m_locked=self.level_pushes.append
        self.note_game_score=types.MethodType(note,self)
        def publish(level,score,peak=None):
            self.publications+=1;return avg(self,level,score,peak)
        self.note_game_state_averages=publish


def main():
    assert sys.version_info[:2]==(3,14)and not sys._is_gil_enabled()
    proof=json.loads((HERE/'exact-source-transform-definitions.json').read_text())
    old_server=Path(proof['server_parent']).read_text();old_config=Path(proof['config_parent']).read_text()
    new_server=Path(proof['server_candidate']).read_text();new_config=Path(proof['config_candidate']).read_text()
    assert old_server.replace(*proof['server_exact_replacement'],1)==new_server
    assert old_config.replace(*proof['config_exact_replacement'],1)==new_config
    avg=compile_method(method(old_config,'MetricsData','note_game_state_averages'),{})
    old_note=compile_method(method(old_config,'MetricsData','note_game_score'),{})
    new_note=compile_method(method(new_config,'MetricsData','note_game_score'),{})
    old_calc_node=method(old_server,'SocketServer','_calc_avg_game_state')
    new_calc_node=method(new_server,'SocketServer','_calc_avg_game_state')
    state_values={str(i):dict(game_score=(0 if i%17==0 else 100_000_000+i*100 if i%5==0 else i*1234),
        level_number=(-1 if i%31==0 else i+1),eval_only=i%5==1)for i in range(192)}
    def setup(node,note,values=None):
        clock=types.SimpleNamespace(now=0.)
        metric=Metrics(avg,note)
        namespace=dict(metrics=metric,time=types.SimpleNamespace(monotonic=lambda:clock.now))
        function=compile_method(node,namespace)
        obj=types.SimpleNamespace(client_lock=threading.Lock(),client_states=States(copy.deepcopy(values or state_values)))
        return function,obj,metric,clock,namespace
    # Correctness uses independent statistics.mean and full192 denominator.
    calc,obj,m,clock,namespace=setup(new_calc_node,new_note)
    calc(obj)
    expected_score=statistics.mean(v['game_score']for v in state_values.values())
    levels=[v['level_number']for v in state_values.values()if v['level_number']>=0 and v['game_score']>0]
    eval_levels=[v['level_number']for v in state_values.values()if v['eval_only']and v['game_score']>0]
    assert m.average_game_score==expected_score and m.average_level==statistics.mean(levels)
    assert m.eval_now_level==statistics.mean(eval_levels)and m.publications==1 and obj.client_states.values_calls==3
    before=m.average_game_score;obj.client_states['1']['game_score']=345_678_901
    clock.now=.249;calc(obj);assert m.publications==1 and m.average_game_score==before
    clock.now=.250;calc(obj)
    assert m.publications==2 and m.average_game_score==statistics.mean(v['game_score']for v in obj.client_states.values())
    # Actual accepted-frame guard/call from handle_client, not a reimplementation.
    handler=method(new_server,'SocketServer','handle_client')
    guard=next(n for n in ast.walk(handler)if isinstance(n,ast.If)
        and any(isinstance(v,ast.Call)and isinstance(v.func,ast.Attribute)and v.func.attr=='note_game_score'for v in ast.walk(n))
        and ast.unparse(n.test)=='not getattr(metrics, \'measurement_active\', False)')
    accepted=ast.FunctionDef(name='accepted_frame',args=ast.arguments(posonlyargs=[],args=[ast.arg('frame'),ast.arg('cs')],kwonlyargs=[],kw_defaults=[],defaults=[]),body=[guard],decorator_list=[])
    accepted_fn=compile_method(accepted,namespace)
    accepted_fn(types.SimpleNamespace(game_score=106_000_000,level_number=9000),dict(last_game_score=106_000_000))
    assert m.peak_level==9000
    obj.client_states['1'].update(game_score=0,level_number=0)
    clock.now=.30;calc(obj);clock.now=.50;calc(obj);assert m.peak_level==9000
    # Freeze both the global scan and the accepted-frame peak publication.
    m.measurement_active=True;count=m.publications;scans=obj.client_states.values_calls;peak=m.peak_level
    clock.now=1.;calc(obj)
    accepted_fn(types.SimpleNamespace(game_score=200_000_000,level_number=9999),dict(last_game_score=200_000_000))
    assert(m.publications,obj.client_states.values_calls,m.peak_level)==(count,scans,peak)
    # Real16-thread collision: every call passes outercheck before first lock.
    concurrent,c,cm,cc,_=setup(new_calc_node,new_note);cc.now=10.
    barrier=threading.Barrier(16);lock=threading.Lock()
    class Gate:
        def __enter__(self):barrier.wait(timeout=5);lock.acquire()
        def __exit__(self,*args):lock.release()
    c.client_lock=Gate();threads=[threading.Thread(target=concurrent,args=(c,))for _ in range(16)]
    for t in threads:t.start()
    for t in threads:t.join(timeout=6);assert not t.is_alive()
    assert cm.publications==1 and c.client_states.values_calls==3
    # Measurement starts after the outercheck but before the locked check.
    raced,r,rm,rc,_=setup(new_calc_node,new_note)
    class FreezeGate:
        def __enter__(self):rm.measurement_active=True
        def __exit__(self,*args):pass
    r.client_lock=FreezeGate();raced(r);assert rm.publications==0 and r.client_states.values_calls==0
    # Same1000calls/s synthetic schedule over10s; wall/CPU measured for actual AST.
    timing=[]
    for name,node,note in [('current',old_calc_node,old_note),('global250ms',new_calc_node,new_note)]:
        fn,s,metric,timer,_=setup(node,note)
        cpu=time.process_time_ns();wall=time.perf_counter_ns()
        for call in range(10000):timer.now=call/1000;fn(s)
        timing.append(dict(name=name,calls=10000,synthetic_seconds=10.,publications=metric.publications,
            fleet_scans=s.client_states.values_calls//3,CPU_ms=(time.process_time_ns()-cpu)/1e6,
            wall_ms=(time.perf_counter_ns()-wall)/1e6))
    assert timing[0]['fleet_scans']==10000 and timing[1]['fleet_scans']==40
    # O(1) peak arithmetic overhead in the existing lock, ring observers identical.
    peak_timing=[]
    for name,note in [('current',old_note),('accepted_frame_peak',new_note)]:
        metric=Metrics(avg,note);cpu=time.process_time_ns()
        for i in range(10000):metric.note_game_score(106_000_000,1234)
        peak_timing.append(dict(name=name,accepted_calls=10000,CPU_ms=(time.process_time_ns()-cpu)/1e6))
    report=dict(schema='robotron-global250ms-average-and-accepted-frame-peak-AST-CPU-v1',
        actual_python=sys.version,actual_free_threaded=not sys._is_gil_enabled(),
        exact_two_source_replacements_verified=True,full192_unwrapped_score_mean_correct=True,
        independent_statistics_mean=expected_score,global_nominal_refresh_boundary_s=.25,
        brief_peak_then_reset_preserved=True,measurement_freeze_and_inner_race_guard_pass=True,
        forced16_thread_doublecheck_exactly_one_global_scan=True,timing=timing,peak_timing=peak_timing,
        no_Torch_server_or_model_import_no_live_actions=True,
        limits='Synthetic192 states; sameactualAST/real3.14tlocks but no realhandler, GPU, replay or network. No live FPS gain claim.')
    p=HERE/'actual314t-average-cadence-and-peak-CPU-original01.json'
    with p.open('x')as f:json.dump(report,f,sort_keys=True,indent=2);f.write('\n')
    p.chmod(0o444);print(json.dumps(report,indent=2))


if __name__=='__main__':main()
