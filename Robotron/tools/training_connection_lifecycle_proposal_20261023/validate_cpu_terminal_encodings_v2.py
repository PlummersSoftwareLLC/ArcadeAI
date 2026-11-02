"""CPU signal-aware controller validation using authentic archived normal/timeout fields."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import time
import unittest


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true');p.add_argument('--job');p.add_argument('--job-sha256');p.add_argument('--source-sha256');a=p.parse_args()
    if not a.execute:print('PLAN_ONLY');return 0
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==a.source_sha256
    raw=Path(a.job).read_bytes();assert hashlib.sha256(raw).hexdigest()==a.job_sha256
    job=json.loads(raw);assert job['schema']=='robotron-CPU-terminal-encoding-contracts-v2'and os.environ.get('CUDA_VISIBLE_DEVICES')==''
    def load(n,pin):
        path=Path(pin['path']);assert hashlib.sha256(path.read_bytes()).hexdigest()==pin['sha256']
        spec=importlib.util.spec_from_file_location(n,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
    h=load('_term_h',job['helpers'])
    for pin in [v for v in job.values()if isinstance(v,dict)and 'path'in v]:h.checked(pin)
    c=load('_term_c',job['candidate']);negative=[]
    def fields(pin):return dict(line.split('=',1)for line in Path(pin['path']).read_text().splitlines()if '='in line)
    normal=fields(job['normal_show']);timeout=fields(job['timeout_show'])
    owners=[json.loads(Path(job[key]['path']).read_text())for key in ['normal_owner','timeout_owner']]
    class Contracts(unittest.TestCase):
        def test_authentic_normal_and_SIGTERM_timeout_fields_keep_distinct_encodings(self):
            c.original_terminal(normal,owners[0]);c.original_terminal(timeout,owners[1])
            self.assertEqual((normal['ExecMainCode'],normal['ExecMainStatus']),('1','0'))
            self.assertEqual((timeout['ExecMainCode'],timeout['ExecMainStatus'],timeout['Result']),('2','15','timeout'))
        def test_unknown_codes_signal_zero_and_changed_original_identity_reject(self):
            for name,change in [('unknown_exec_code',dict(ExecMainCode='4')),('signal_zero',dict(ExecMainStatus='0')),
                ('live_main_PID',dict(MainPID='1')),('foreign_invocation',dict(InvocationID='0'*32)),
                ('restarted_original',dict(NRestarts='1')),('foreign_ExecMainPID',dict(ExecMainPID='1'))]:
                value=dict(timeout,**change)
                with self.assertRaises(ValueError):c.original_terminal(value,owners[1])
                negative.append(name)
            with self.assertRaises(ValueError):c.original_terminal(dict(normal,ExecMainStatus='256'),owners[0])
            negative.append('invalid_normal_exit_encoding')
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Contracts))
    if not result.wasSuccessful():return 1
    out=Path(job['output']);out.mkdir(mode=0o700);h.put(out/'report.json',dict(status='SIGNAL_AWARE_CPU_CONTROLLER_AUTHENTIC_ENCODINGS_CONTRACTS_PASS_NOT_LIVE_TESTED',tests=result.testsRun,negative_checks=negative,source_sha256=a.source_sha256,job_sha256=a.job_sha256,quality_qualified=False,production_changed=False,created_unix_s=time.time()))
    print(json.dumps(dict(status='ENCODING_CONTRACTS_PASS',tests=result.testsRun,negative_checks=len(negative))),flush=True);return 0


if __name__=='__main__':raise SystemExit(main())
