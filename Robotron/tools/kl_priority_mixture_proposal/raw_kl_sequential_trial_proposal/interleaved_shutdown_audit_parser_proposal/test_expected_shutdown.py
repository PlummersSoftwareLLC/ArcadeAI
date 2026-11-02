"""Authored/unexecuted stdlib guards over frozen actualC1 metadata and private text variants."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest
HERE=Path(__file__).parent
spec=importlib.util.spec_from_file_location('_expected_shutdown_test',HERE/'expected_shutdown.py')
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)
ACTUAL=Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/CE543M-quality-original-row-leg02-audit')
SOCKET_PATH='/home/dave/source/repos/ArcadeAI/Robotron/Scripts/dqn/socket_server.py'

class InterleavedShutdownGuards(unittest.TestCase):
    def setUp(self):
        self.console=(HERE/'fixture-C1-console.log').read_text()
        self.receipt=json.loads((HERE/'fixture-C1-receipt-projection.json').read_text())
        self.socket=(ACTUAL/'bound-source-07-socket_server.py').read_bytes()
        self.sidecar=(ACTUAL/'bound-source-00-run_frozen_sidecar.py').read_bytes()
    def check(self,console=None,receipt=None,**kwargs):
        args=dict(socket_source=self.socket,sidecar_source=self.sidecar,expected_socket_path=SOCKET_PATH);args.update(kwargs)
        return M.reconcile_expected_shutdown(self.console if console is None else console,self.receipt if receipt is None else receipt,**args)
    def test_actual_original6trace_case_fully_accounts_for_failed_auditor_lines(self):
        value=self.check();self.assertTrue(value['accepted']);self.assertEqual(value['stop_line'],57)
        self.assertEqual(value['counts']['clients'],6);self.assertEqual(value['owned_client_ids'],[7,10,4,1,11,14])
        self.assertTrue({58,59,64,65,66,67,68,69,74,86,88,93,95,104}<=set(value['accounted_line_numbers']))
    def test_console_size_and_line_count_bounded(self):
        for text in ('x'*(1<<20)+'x','\n'*4097):
            with self.subTest(length=len(text)),self.assertRaises(ValueError):self.check(text)
    def test_source_hash_or_expected_frame_path_mismatch_refused(self):
        for kwargs in (dict(socket_source=self.socket+b'\n'),dict(sidecar_source=self.sidecar+b'\n'),dict(expected_socket_path='/foreign/socket_server.py')):
            with self.subTest(keys=list(kwargs)),self.assertRaises(ValueError):self.check(**kwargs)
    def test_missing_or_duplicate_owned_stop_boundary_refused(self):
        for text in (self.console.replace(M.STOP,'foreign stop'),self.console.replace(M.STOP,M.STOP+'\n'+M.STOP)):
            with self.assertRaises(ValueError):self.check(text)
    def test_pre_stop_trace_or_runtime_error_never_reconciled(self):
        for text in ('Traceback (most recent call last):\n'+self.console,'RuntimeError: '+M.ERROR+'\n'+self.console):
            with self.assertRaises(ValueError):self.check(text)
    def test_foreign_frame_and_mixed_concatenated_exception_refused(self):
        for text in (self.console.replace('line 995, in infer','line 994, in foreign',1),self.console.replace('completionClient 10','completionRuntimeError: foreignClient 10',1),self.console.replace('raise RuntimeError(error)','raise ValueError(error)',1)):
            with self.assertRaises(ValueError):self.check(text)
    def test_missing_raise_or_extra_ending_cannot_balance(self):
        for text in (self.console.replace('    raise RuntimeError(error)\n','',1),self.console.replace('RuntimeError: '+M.ERROR,'RuntimeError: '+M.ERROR+'RuntimeError: '+M.ERROR,1)):
            with self.assertRaises(ValueError):self.check(text)
    def test_unknown_or_repeated_client_ID_refused(self):
        for text in (self.console.replace('Client 7 error:','Client 999 error:',1),self.console.replace('Client 10 error:','Client 7 error:',1)):
            with self.assertRaises(ValueError):self.check(text)
    def test_invalid_pending_fatal_or_measured_timeout_receipt_refused(self):
        for field,value in (('valid',False),('pending',1),('server_error','fatal'),('cleanup_errors',['failed']),('actor_timeout_logs',{'4096':1})):
            receipt=copy.deepcopy(self.receipt);receipt[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):self.check(receipt=receipt)
    def test_missing_tail_or_tail_after_shutdown_refused(self):
        for wrong in ('coverage','end'):
            receipt=copy.deepcopy(self.receipt)
            if wrong=='coverage':receipt['rows'].pop()
            else:receipt['rows'][0]['end_unix_s']=receipt['timeout_snapshot_unix_s']+1
            with self.assertRaises(ValueError):self.check(receipt=receipt)
    def test_foreign_poststop_diagnostic_or_final_summary_mismatch_refused(self):
        for text in (self.console.replace(M.STOP,M.STOP+'\nGPU dispatch timed out'),self.console.replace('"count": 59','"count": 58')):
            with self.assertRaises(ValueError):self.check(text)
    def test_one_complete_noninterleaved_known_trace_is_accounted(self):
        lines=self.console.splitlines();prefix=lines[:57]
        block=['Client 7 error: '+M.ERROR,lines[63],lines[69],lines[70],lines[71],lines[72],lines[73],'RuntimeError: '+M.ERROR]
        value=self.check('\n'.join(prefix+block+[lines[-1]])+'\n')
        self.assertEqual(value['counts']['clients'],1);self.assertEqual(value['counts']['raises'],1)

if __name__=='__main__':unittest.main()
