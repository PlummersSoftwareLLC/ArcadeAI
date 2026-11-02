"""Focused actual-source timing/sampling/CSV checks; no GPU/model/MAME imports."""
import ast
import csv
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest

HERE=Path(__file__).resolve().parent
G=Path('/home/dave/source/repos/ArcadeAI/Robotron')

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

M=load('_new_response_timing',HERE/'sources/response_telemetry.py')

class Clock:
    def __init__(self): self.w=0; self.c=0; self.calls=0
    def wall(self): self.calls+=1; return self.w
    def cpu(self): return self.c
    def step(self,w,c=0): self.w+=round(w*1e6); self.c+=round(c*1e6)

class Tests(unittest.TestCase):
    def measured(self):
        c=Clock(); r=M.ResponseTelemetry(wall_ns=c.wall,thread_cpu_ns=c.cpu)
        t=r.begin(49,163,1,True,connection_ns=123)
        c.step(20,1); t.mark('payload_wait'); c.step(5,.2); t.mark('parse_cache')
        t.queue_depth(63990,ingress=True); c.step(4,3); t.mark('classify')
        t.start('client_lock_wait'); c.step(30,.05); t.stop('client_lock_wait')
        t.start('client_lock_hold'); c.step(1,.7); t.stop('client_lock_hold'); t.mark('state')
        c.step(2,1); t.mark('journal'); c.step(1,.2); t.mark('metrics_aggregate')
        c.step(1,.1); t.mark('previous_step'); t.queue_depth(63999)
        t.start('enqueue_wait'); c.step(8,.1); t.stop('enqueue_wait'); t.queue_depth(63998)
        t.mark('choose_action'); t.mark('inference'); c.step(4,.3); t.mark('choose_action')
        c.step(.1,.05); t.mark('action_write'); c.step(.2,.1); t.finish('accepted',response_sent=True)
        t.finish('duplicate',response_sent=True)
        return c,r,r.snapshot()

    def test_exact_exclusive_response_and_nested_wait_accounting(self):
        _,r,s=self.measured(); g=s['groups']['selected']; p=g['phases']
        self.assertEqual(g['completed_sampled_frames'],1)
        self.assertAlmostEqual(p['response_total']['wall']['sum_ms'],51.3)
        self.assertAlmostEqual(p['response_total']['thread_cpu']['sum_ms'],5.6)
        self.assertEqual(p['header_wait']['wall']['sum_ms'],20)
        self.assertEqual(p['payload_wait']['wall']['sum_ms'],5)
        self.assertEqual(p['client_lock_wait']['wall']['sum_ms'],30)
        self.assertEqual(p['enqueue_wait']['wall']['sum_ms'],8)
        self.assertEqual(p['choose_action']['wall']['count'],1)
        self.assertEqual(g['phase_calls']['choose_action'],2)
        self.assertEqual(g['ingress_queue_depth_last'],63990)
        self.assertEqual(g['queue_depth_max'],63999)
        row=M.interval_summary(s);self.assertEqual(row['response_samples'],1)
        self.assertIn('51.30',M.format_interval_row(row))
        self.assertTrue(s['nested_spans_not_additive_to_response_total'])

    def test_sampling_discard_identity_changes_and_safe_queue_fault(self):
        c=Clock(); r=M.ResponseTelemetry(wall_ns=c.wall,thread_cpu_ns=c.cpu)
        before=c.calls
        self.assertIsNone(r.begin(2,4,2,False));self.assertEqual(c.calls,before)
        self.assertIsNotNone(r.begin(2,4,1,False));self.assertIsNotNone(r.begin(2,4,21,False))
        self.assertIsNotNone(r.begin(2,4,2,True))
        t=r.begin(2,4,3,True);t.discard();t.finish('idle');self.assertEqual(r.snapshot()['groups']['selected']['completed_sampled_frames'],0)
        t=r.begin(49,163,1,True,connection_ns=10);t.mark('parse_cache');c.step(1);t.finish('accepted',response_sent=True)
        old=r.snapshot();t=r.begin(49,163,1,True,connection_ns=11);t.mark('parse_cache');c.step(1);t.finish('accepted',response_sent=True)
        self.assertFalse(M.interval_summary(r.snapshot(),old)['available'])
        class BadQueue:
            def qsize(self): raise RuntimeError('injected observer read fault')
        class Buffer: queue=BadQueue()
        t=r.begin(49,163,2,True);t.observe_queue(Buffer());t.finish()
        self.assertFalse(r.snapshot()['available'])
        self.assertEqual(r.snapshot()['observer_errors'],1)
        t=r.begin(49,163,3,True);t.finish('not an unbounded output key')
        self.assertEqual(r.snapshot()['groups']['selected']['outcomes']['other'],1)

    def test_concurrent_actual_recorder_is_bounded_and_snapshot_readonly(self):
        r=M.ResponseTelemetry(); failures=[]
        def work(i):
            try:
                for n in range(25):
                    t=r.begin(i,i,n+1,True,connection_ns=i);t.mark('parse_cache');t.mark('inference');t.finish('accepted',response_sent=True)
            except Exception as e:failures.append(str(e))
        workers=[threading.Thread(target=work,args=(i,)) for i in range(8)]
        for t in workers:t.start()
        for t in workers:t.join(3);self.assertFalse(t.is_alive())
        self.assertEqual(failures,[]);s=r.snapshot();self.assertTrue(s['available'])
        self.assertEqual(s['groups']['selected']['completed_sampled_frames'],200)
        self.assertEqual(s['groups']['selected']['phases']['response_total']['wall']['count'],200)
        s['groups']['selected']['completed_sampled_frames']=999
        self.assertEqual(r.snapshot()['groups']['selected']['completed_sampled_frames'],200)

    def test_actual_server_gameplay_AST_unchanged_after_erasing_observer_only(self):
        parent=G/'logs/managed-learning-20261015/run-26/preview-selected-client-wallclock-original01-preparation-20261027/server-average-telemetry-global250ms-original01-preparation-20261027/socket_server_global250ms_candidate_v1.py'
        original=ast.parse(parent.read_text());candidate=ast.parse((HERE/'sources/socket_server.py').read_text())
        class Strip(ast.NodeTransformer):
            def visit_Try(self,node):
                if any(isinstance(n,ast.ImportFrom) and n.module=='response_telemetry' for n in ast.walk(node)):return None
                return self.generic_visit(node)
            def visit_FunctionDef(self,node):
                if node.name=='response_timing_snapshot':return None
                if node.name=='_cache_client_preview':node.args.kwonlyargs=[];node.args.kw_defaults=[]
                return self.generic_visit(node)
            def visit_Assign(self,node):
                targets=[ast.unparse(t) for t in node.targets]
                if any(t.startswith('_response_') or t=='self._response_timing' for t in targets):return None
                return self.generic_visit(node)
            def visit_AugAssign(self,node):
                if ast.unparse(node.target).startswith('_response_'):return None
                return self.generic_visit(node)
            def visit_If(self,node):
                if '_response_' in ast.unparse(node.test):return None
                return self.generic_visit(node)
            def visit_Call(self,node):
                node.keywords=[k for k in node.keywords if k.arg!='_response_trace']
                return self.generic_visit(node)
        stripped=Strip().visit(candidate)
        self.assertEqual(ast.dump(original,include_attributes=False),ast.dump(stripped,include_attributes=False))
        sends=[n for n in ast.walk(candidate) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='sendall']
        self.assertGreaterEqual(len(sends),5)

    def test_actual_writer_persists_fresh_response_CSV_and_rejects_old_schema(self):
        writer_module=load('_actual_existing_CSV_writer',G/'Scripts/dqn/run_telemetry.py')
        _,_,snapshot=self.measured();summary=M.interval_summary(snapshot);fields=M.report_fields(snapshot,summary)
        def reporter(directory):
            # Skip __init__ ONLY to avoid its GPU sampler; exercise REAL write().
            r=writer_module.RunTelemetry.__new__(writer_module.RunTelemetry)
            r.started=time.monotonic();r.directory=directory;r.path=directory/'training.csv'
            r.lock=threading.Lock();r.samples=[];r.error='';r.previous=None;r.previous_pipeline=None
            r.previous_pipeline_agent=None;r.fieldnames=None;r.last_pipeline_fields={}
            return r
        with tempfile.TemporaryDirectory(prefix='response fresh CSV ') as name:
            d=Path(name);r=reporter(d)
            r.write(dict(frames=100,optimized_samples=400,**fields),agent=None)
            with r.path.open(newline='') as f:rows=list(csv.DictReader(f))
            self.assertEqual(len(rows),1);row=rows[0]
            self.assertEqual(row['response_schema'],M.SCHEMA)
            self.assertAlmostEqual(float(row['response_selected_response_total_wall_mean_ms']),51.3)
            self.assertEqual(json.loads(row['response_snapshot_json'])['groups']['selected']['queue_depth_max'],63999)
        with tempfile.TemporaryDirectory(prefix='response old CSV ') as name:
            r=reporter(Path(name));r.path.write_text('utc,elapsed_s,frames,optimized_samples\n')
            before=r.path.read_bytes()
            with self.assertRaisesRegex(ValueError,'CSV schema changed'):
                r.write(dict(frames=100,optimized_samples=400,**fields),agent=None)
            self.assertEqual(r.path.read_bytes(),before)

if __name__=='__main__':unittest.main()
