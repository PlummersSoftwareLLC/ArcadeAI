"""Cold execute the actual native import block on CPU, before any policy load."""
import argparse
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace

def load(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s)
    sys.modules[name]=m;s.loader.exec_module(m);return m

def main():
    p=argparse.ArgumentParser();p.add_argument('--native',type=Path,required=True)
    p.add_argument('--job',type=Path,required=True);p.add_argument('--expect-old-missing-drain',action='store_true');a=p.parse_args()
    assert os.environ['CUDA_VISIBLE_DEVICES']=='' and not sys._is_gil_enabled()
    runtime=load('_cold_native',a.native);h=runtime.helpers()
    job=json.loads(a.job.read_bytes());root,pins=h.package_inputs(job['source_package'])
    run=next(n for n in ast.parse(a.native.read_text()).body if isinstance(n,ast.FunctionDef)and n.name=='run')
    body=next(n.body for n in run.body if isinstance(n,ast.Try))
    first=next(i for i,n in enumerate(body)if ast.unparse(n)=="sys.path.insert(0, str(root / 'Scripts'))")
    last=next(i for i,n in enumerate(body)if isinstance(n,ast.Import)and any(z.asname=='quota_drain'for z in n.names))
    block=body[first:last+1]
    assert len(block)==13 and all(isinstance(n,(ast.Expr,ast.Import,ast.ImportFrom))for n in block)
    tail=next(n for n in body if isinstance(n,ast.ImportFrom)and n.module=='tail_ledger_v1')
    source=ast.Module(body=block+[tail],type_ignores=[]);ast.fix_missing_locations(source)
    with tempfile.TemporaryDirectory()as tmp:
        sidecar=runtime.load('_cold_sidecar',root/'tools/run_frozen_sidecar.py')
        sidecar.configure_environment(SimpleNamespace(directory=Path(tmp),gpu_uuid='',device='cpu',
            completion_policy='confirmed_reset_reserves_v1',game_boundary_diagnostics=True,cpu_threads=2))
        env=dict(root=root,HERE=runtime.HERE,COMPONENTS=runtime.COMPONENTS,BRIDGE_COMPONENTS=runtime.BRIDGE_COMPONENTS)
        try:exec(compile(source,str(a.native),'exec'),env)
        except ModuleNotFoundError as error:
            assert a.expect_old_missing_drain and error.name=='fixed_slot_cohort_drain_v1',repr(error)
            assert not env['torch'].cuda.is_initialized()
            print(json.dumps(dict(old_failure_reproduced=True,missing=error.name,native=str(a.native),
                native_sha256=hashlib.sha256(a.native.read_bytes()).hexdigest(),cuda_initialized=False)))
            return
        assert not a.expect_old_missing_drain
        torch=env['torch'];assert not torch.cuda.is_initialized()
        expected={'bridge':runtime.BRIDGE_COMPONENTS/'full_startup_proxy_quota64_v1.py',
            'authority':runtime.BRIDGE_COMPONENTS/'startup_handoff_v2.py',
            'quota_view':runtime.COMPONENTS/'fixed_slot_cohort_view_v1.py',
            'quota_drain':runtime.COMPONENTS/'fixed_slot_cohort_drain_v2.py'}
        actual={k:str(Path(env[k].__file__).resolve())for k in expected}
        assert actual=={k:str(v)for k,v in expected.items()},actual
        assert env['bridge'].authority is env['authority']
        assert env['quota_drain'].ACTOR_COUNT==runtime.ACTOR_COUNT
        assert Path(sys.modules['wire_codec_v2'].__file__)==runtime.BRIDGE_COMPONENTS/'wire_codec_v2.py'
        assert Path(sys.modules['tail_ledger_v1'].__file__)==runtime.BRIDGE_COMPONENTS/'tail_ledger_v1.py'
        assert env['quota_drain'].VIEW_SHA==h.pin(expected['quota_view'])['sha256']
        assert env['quota_drain'].COHORT_SELECTION==env['quota_view'].COHORT_SELECTION
        for name in ('dqn.config','dqn.inference_actor','dqn.managed_measurement','dqn.socket_server'):
            assert Path(sys.modules[name].__file__).is_relative_to(root/'Scripts')
        print(json.dumps(dict(passed=True,native=str(a.native),actual_module_paths=actual,
            actual_interpreter=sys.version,free_threaded=not sys._is_gil_enabled(),cuda_initialized=False,
            checkpoint_loaded=False,native_run_called=False,native_import_AST_sha256=hashlib.sha256(ast.dump(source).encode()).hexdigest())))

if __name__=='__main__':main()
