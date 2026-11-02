"""Synthetic actual-kernel A5 release guards; source-only until Root CPU mode.

No actual process, service, cgroup, API, native result, or score is observed.
Selected adapter functions and unchanged C218 lifecycle functions execute only
inside synthetic collaborators and temporary command-output files. This does not
qualify the still-future actual R1 outcome or release.
"""
import ast
import copy
import hashlib
import json
from pathlib import Path
import re
import tempfile
import types
import unittest

HERE = Path(__file__).resolve().parent
ADAPTER = HERE/'close_completed_A5_wrapper_v1.py'
ADAPTER_SHA = 'bf88d6438217082375831f35c4111eae13f7c5ce99887e780a62ab1a338cb066'
C218 = Path('/home/dave/source/repos/ArcadeAI/Robotron/tools/quality_capacity_proposal/control_quality32_review_v1.py')
C218_SHA = '218e7f861deb82c340527d218ed9f92ef5c5836c8cb9d32452c0598e61ff9a14'


def selected_functions(path, expected, functions, constants=()):
    body = path.read_bytes()
    if expected is None or hashlib.sha256(body).hexdigest() != expected:
        raise ValueError('Unfrozen/mismatched selected source')
    tree = ast.parse(body)
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in functions
             or isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in constants for t in node.targets)]
    actual = {node.name for node in nodes if isinstance(node, ast.FunctionDef)}
    if actual != set(functions):
        raise ValueError('Actual selected function inventory changed')
    namespace = dict(Path=Path, re=re, hashlib=hashlib)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), namespace)
    return namespace


class SyntheticCommands:
    def __init__(self, path, terminal, failure=None, linger=False):
        self.path = path; self.terminal = terminal; self.failure = failure
        self.linger = linger; self.absent = False; self.calls = []
        self.control = selected_functions(C218, C218_SHA,
            ['require', 'fields', 'original_terminal', 'release_original'])
        self.control['command'] = self.command

    def command(self, out, label, argv):
        self.calls.append(list(argv))
        code = 0; timed_out = False
        if argv[:3] == ['systemctl', '--user', 'show']:
            fields = dict(Id=argv[3], LoadState='not-found') if self.absent else self.terminal
            text = ''.join(k+'='+v+'\n' for k,v in fields.items())
            if label == 'original-A5-service-show' and self.failure == 'showfailure': code = 1
            if label == 'original-A5-service-show' and self.failure == 'showtimeout': code = None; timed_out = True
        elif argv[:3] == ['systemctl', '--user', 'stop']:
            self.absent = not self.linger; text = ''
        elif argv[:3] == ['systemctl', '--user', 'cat']:
            text = '[Service]\nType=exec\n'
            if self.failure == 'cat': code = 1
        elif argv[0] == 'journalctl':
            text = 'synthetic exact-invocation terminal log\n'
            if self.failure == 'journal': timed_out = True; code = None
        else:
            raise ValueError('Unexpected synthetic control command: '+repr(argv))
        dest = self.path/(label+'-'+str(len(self.calls))+'.txt')
        dest.write_text(text)
        return dict(argv=argv, exit=code, timed_out=timed_out,
                    stdout=dict(path=str(dest)), stderr=dict(path=str(dest)))

    def api(self):
        return types.SimpleNamespace(**{key:self.control[key]
            for key in ['fields','original_terminal','release_original']}, command=self.command)

    def stops(self):
        return [row for row in self.calls if row[:3] == ['systemctl','--user','stop']]


class CompletedA5ReleaseGuards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.a = selected_functions(ADAPTER, ADAPTER_SHA,
            ['require','validate_scope','validate_recorded','require_original_births_absent',
             'archive_release_completed_A5'],
            ['FIXED','CURRENT_A5_UNIT','SCHEMA','SUCCESS','RESOURCE_FIELDS'])

    def synthetic(self):
        a = self.a; fixed = a['FIXED']; unit = a['CURRENT_A5_UNIT']
        selection = dict(schema='robotron-generic-physical-original-R1-launch-selection-v1',
            wrapper_unit=unit, sources=dict(wrapper=fixed['wrapper'],review_preparer=fixed['review_preparer']),
            original_attempt=1,no_retry=True,readiness={'synthetic':'readiness'},
            R1=dict(native_job={'synthetic':'job'},config={'synthetic':'config'},native_unit='synthetic-native.service'))
        props = dict(a['RESOURCE_FIELDS'], Id=unit, InvocationID='a'*32, MainPID='10001',
            ExecMainPID='10001',ActiveState='active',SubState='running',
            ControlGroup='/user.slice/user-1001.slice/user@1001.service/app.slice/'+unit,
            ExecStart=' '.join([fixed['wrapper']['path'],fixed['wrapper']['sha256'],
                fixed['selection']['path'],fixed['selection']['sha256'],'--run','--launch-selection',
                '--launch-selection-sha256','--expected-source-sha256']))
        intent = dict(launch_selection=fixed['selection'],source=fixed['wrapper'],readiness=selection['readiness'],
            exact_original_job=selection['R1']['native_job'],exact_original_config=selection['R1']['config'],
            original_attempt=1,no_retry=True,unit=unit,canonical_state_written=False,
            invocation_id='a'*32,actual_wrapper_pid=10001,actual_wrapper_birth=20001,actual_wrapper_scope=props)
        live = dict(wrapper_pid=10001,wrapper_birth=20001,wrapper_unit=unit,wrapper_invocation_id='a'*32,
            readiness=selection['readiness'],original_job=selection['R1']['native_job'],config=selection['R1']['config'],
            controller=dict(pid=10002,starttime_ticks=20002,observed_live=True),
            owner=dict(pid=10003,starttime_ticks=20003,observed_live=True,unit='synthetic-native.service'))
        terminal = dict(schema='robotron-owned-durable-R1-wrapper-terminal-v1',intent=fixed['intent'],
            wrapper_pid=10001,wrapper_birth=20001,original_attempt=1,no_retry=True,
            scientific_payload_retried=False,quality_qualified=False,promotion=False,
            status='NATIVE_CLOSED_REVIEW_PENDING',actual_controller_exit=0,live_registration_errors=[])
        identity = a['validate_recorded'](selection,intent,live,terminal,fixed['intent'])
        terminal_scope = dict(props,MainPID='0',SubState='exited',ExecMainCode='1',ExecMainStatus='0',Result='success',
                              ControlGroup='')  # Real RemainAfterExit terminal may omit the old cgroup.
        record = dict(archives=[],owned_release={},all_three_archives_succeeded=False,
            original_wrapper_exit=None,original_wrapper_birth_unit_and_captured_cgroup_absent=False,
            lifecycle_complete=False,status='OWNED_A5_RELEASE_INCOMPLETE_NO_RETRY')
        return selection,intent,live,terminal,identity,terminal_scope,record

    def test_01_exact_normal0_archives_before_owned_release_and_positive_absence(self):
        selection,intent,live,terminal,identity,scope,record = self.synthetic()
        with tempfile.TemporaryDirectory() as temp:
            c = SyntheticCommands(Path(temp),scope)
            self.a['archive_release_completed_A5'](Path(temp),identity,live,c.api(),lambda pid:None,lambda cg:False,record)
            self.assertEqual(record['status'],self.a['SUCCESS'])
            self.assertTrue(record['lifecycle_complete'])
            self.assertTrue(record['original_wrapper_birth_unit_and_captured_cgroup_absent'])
            self.assertEqual(c.stops(),[['systemctl','--user','stop',self.a['CURRENT_A5_UNIT']]])
            self.assertEqual([row[0] for row in c.calls[:3]],['systemctl','systemctl','journalctl'])
            self.assertEqual(c.calls[2][-1],'_SYSTEMD_INVOCATION_ID='+'a'*32)
            self.assertTrue(all(row[-1] == self.a['CURRENT_A5_UNIT'] for row in c.calls if row[0]=='systemctl'))

    def test_02_wrong_recorded_owner_selection_or_terminal_never_enters_controls(self):
        base = self.synthetic()
        for kind in ('selection','unit','invocation','wrapper_source','controller_nonzero','registration_error','wrong_intent'):
            s,i,l,t,owner,scope,record = copy.deepcopy(base)
            if kind=='selection': i['launch_selection']={'sha256':'0'*64}
            if kind=='unit': i['unit']='robotron-trainer.service'
            if kind=='invocation': l['wrapper_invocation_id']='b'*32
            if kind=='wrapper_source': s['sources']['wrapper']={'sha256':'0'*64}
            if kind=='controller_nonzero': t['actual_controller_exit']=1
            if kind=='registration_error': t['live_registration_errors']=['synthetic']
            if kind=='wrong_intent': t['intent']={'sha256':'0'*64}
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                self.a['validate_recorded'](s,i,l,t,self.a['FIXED']['intent'])

    def test_03_live_signal_nonzero_foreign_service_reject_before_stop(self):
        base = self.synthetic()
        for kind in ('live_wrapper','live_controller','live_native','service_live','exit7','signal','foreign_invocation','foreign_unit'):
            s,i,l,t,owner,scope,record = copy.deepcopy(base)
            actual_birth = {}
            if kind=='live_wrapper': actual_birth[10001]=20001
            if kind=='live_controller': actual_birth[10002]=20002
            if kind=='live_native': actual_birth[10003]=20003
            if kind=='service_live': scope.update(MainPID='10001',SubState='running')
            if kind=='exit7': scope['ExecMainStatus']='7'
            if kind=='signal': scope.update(ExecMainCode='2',ExecMainStatus='15')
            if kind=='foreign_invocation': scope['InvocationID']='b'*32
            if kind=='foreign_unit': owner['unit']='robotron-mame.service'
            with tempfile.TemporaryDirectory() as temp:
                c = SyntheticCommands(Path(temp),scope)
                with self.subTest(kind=kind), self.assertRaises(ValueError):
                    self.a['archive_release_completed_A5'](Path(temp),owner,l,c.api(),actual_birth.get,lambda cg:False,record)
                self.assertEqual(c.stops(),[])
                self.assertFalse(record['lifecycle_complete'])

    def test_04_archive_failure_never_releases_and_post_release_incomplete_stays_false(self):
        for kind in ('showfailure','showtimeout','cat','journal','unit_remains','cgroup_remains','birth_returns'):
            s,i,l,t,owner,scope,record = self.synthetic()
            with tempfile.TemporaryDirectory() as temp:
                c = SyntheticCommands(Path(temp),scope,failure=kind,linger=kind=='unit_remains')
                def birth(pid):
                    return 20001 if kind=='birth_returns' and c.stops() and pid==10001 else None
                api = c.api()
                if kind in ('showfailure','showtimeout'):
                    # A permissive parser cannot bypass the adapter's explicit command gate.
                    api.fields = lambda row: dict(x.split('=',1) for x in Path(row['stdout']['path']).read_text().splitlines() if '=' in x)
                with self.subTest(kind=kind), self.assertRaises(ValueError):
                    self.a['archive_release_completed_A5'](Path(temp),owner,l,api,birth,
                        lambda cg:kind=='cgroup_remains',record)
                self.assertFalse(record['lifecycle_complete'])
                self.assertFalse(record['original_wrapper_birth_unit_and_captured_cgroup_absent'])
                self.assertEqual(len(c.stops()),0 if kind in ('showfailure','showtimeout','cat','journal') else 1)
                self.assertLessEqual(len(c.stops()),1)
                self.assertTrue(record['archives'])


if __name__ == '__main__':
    unittest.main()
