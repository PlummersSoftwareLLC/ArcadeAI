"""Unexecuted focused stdlib guards; no real process/unit/GPU operations."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

SOURCE = Path(__file__).with_name('archive_and_release_trial02.py')
SPEC = importlib.util.spec_from_file_location('trial02_terminal_cleanup_guard_subject', SOURCE)
helper = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(helper)


class TerminalReleaseGuards(unittest.TestCase):
    def observed(self, label='trial_controller'):
        owner = helper.OWNERS[label]
        return dict(unit=owner['unit'], pid=owner['pid'], original_pid=owner['pid'],
            invocation=owner['invocation_id'], starttime_ticks=owner['starttime_ticks'],
            nrestarts='0', active='active', sub='running', result='success')

    def terminal(self, owner, exit_status='0'):
        return dict(LoadState='loaded', MainPID='0', ExecMainPID=str(owner['pid']),
            InvocationID=owner['invocation_id'], NRestarts='0', ControlGroup='',
            ExecMainCode='1', ExecMainStatus=exit_status, Result='success' if exit_status=='0' else 'exit-code')

    def test_PLAN_does_not_read_import_helpers_or_query_units(self):
        with (mock.patch.object(helper, 'read_file', side_effect=AssertionError('read')),
                mock.patch.object(helper, 'command', side_effect=AssertionError('command')),
                contextlib.redirect_stdout(io.StringIO())):
            self.assertEqual(helper.main([]), 0)

    def test_actual_observed_identity_shape_binds_exact_original_not_replacement(self):
        for label in helper.OWNERS:
            value = self.observed(label); bound = helper.bound_owner(label, value)
            self.assertEqual(set(bound), {'pid','starttime_ticks','unit','invocation_id','cgroup'})
            self.assertTrue(bound['cgroup'].endswith('/'+bound['unit']))
            value['invocation']='f'*32
            with self.assertRaisesRegex(RuntimeError,'observed identity'):
                helper.bound_owner(label,value)

    def test_failed_original_exit_is_preserved_but_running_or_replaced_original_refuses(self):
        owner=helper.bound_owner('trial_controller',self.observed())
        failed=self.terminal(owner,'7');helper.original_terminal(owner,failed)
        self.assertEqual((failed['ExecMainCode'],failed['ExecMainStatus']),('1','7'))
        for key,value in [('MainPID',str(owner['pid'])),('ExecMainPID','999'),('InvocationID','other'),('NRestarts','1')]:
            broken=dict(failed);broken[key]=value
            with self.assertRaises(RuntimeError):helper.original_terminal(owner,broken)

    def test_either_live_parent_blocks_initial_boundary_before_process_or_cgroup_checks(self):
        owners={k:helper.bound_owner(k,self.observed(k)) for k in helper.OWNERS}
        values=[(self.terminal(owners['trial_controller']),{}),
            (dict(self.terminal(owners['deadline']),MainPID=str(owners['deadline']['pid'])),{})]
        with (mock.patch.object(helper,'show',side_effect=values),
                mock.patch.object(helper,'process_start',side_effect=AssertionError('no probe needed')),
                mock.patch.object(helper,'cgroup_empty',side_effect=AssertionError('no probe needed'))):
            with self.assertRaisesRegex(RuntimeError,'retained terminal'):
                helper.parents_terminal(owners,require_absent=False)

    def completion(self):
        kl=dict(pid=3,starttime_ticks=4,unit='trainer.service',invocation_id='k'*32,cgroup='/trainer')
        ce=dict(kl,pid=5,starttime_ticks=6,invocation_id='c'*32)
        trial=dict(status='COMPLETE',manual_recovery_required=False,qualification_pass=False,
            candidate={'actual':'candidate'},retired_owner=kl)
        deadline=dict(status='RETIRED',absence=dict(elapsed_s=3599,proof=dict(state='ABSENT',
            old_process_present=False,cgroup_occupied=False)),adopted=dict(owner=kl))
        returned=dict(status='READY',manual_recovery_required=False,qualification_pass=False,owner=ce,
            startup_phase_proof=dict(phase=dict(expected=dict(metric='ce'))),
            first_resume=dict(failures=[]),final_resume=dict(failures=[]))
        return trial,deadline,returned,dict(owner=kl)

    def test_ONLY_complete_timely_absence_and_new_CE_can_pass(self):
        self.assertEqual(helper.check_trial(*self.completion())['pid'],5)
        for kind in ('failed','incomplete','late','occupied','unproven','old_ce','bad_ce','undo'):
            with self.subTest(kind=kind):
                trial,deadline,ce,activation=self.completion()
                if kind=='failed':trial['status']='FAILED'
                elif kind=='incomplete':trial['status']='INCOMPLETE_RETURNED_CE'
                elif kind=='late':deadline['absence']['elapsed_s']=3600.01
                elif kind=='occupied':deadline['absence']['proof']['cgroup_occupied']=True
                elif kind=='unproven':deadline['absence']['proof']['old_process_present']=True
                elif kind=='old_ce':ce['owner']=activation['owner']
                elif kind=='bad_ce':ce['status']='FAILED'
                else:ce['final_resume']['failures']=[{'pid':7}]
                with self.assertRaises(RuntimeError):helper.check_trial(trial,deadline,ce,activation)

    def test_explicit_empty_journal_has_full444_PIN_other_empty_archives_refuse(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            with self.assertRaises(RuntimeError):helper.write_bytes(root/'not-created',b'')
            pin=helper.write_bytes(root/'journal.txt',b'',allow_empty=True)
            self.assertEqual(pin['sha256'],hashlib.sha256(b'').hexdigest())
            self.assertEqual(pin['bytes'],0);self.assertEqual(pin['identity']['mode'],'0o444')
            self.assertEqual(set(pin),{'path','sha256','bytes','identity'})
            with self.assertRaises(FileExistsError):helper.write_bytes(root/'journal.txt',b'held')
            self.assertEqual((root/'journal.txt').read_bytes(),b'')

    def test_show_nonzero_is_allowed_ONLY_authoritative_notfound(self):
        for text,success in [('LoadState=not-found\n',True),('LoadState=loaded\n',False),('',False)]:
            with self.subTest(text=text),mock.patch.object(helper,'command',return_value=dict(returncode=1,stdout=text,stderr='gone')):
                if success:self.assertEqual(helper.show('bound.service')[0]['LoadState'],'not-found')
                else:
                    with self.assertRaises(RuntimeError):helper.show('bound.service')

    def test_release_is_exact_and_nonzero_stop_requires_exact_notloaded_classification(self):
        owners={k:helper.bound_owner(k,self.observed(k)) for k in helper.OWNERS}
        unit=owners['trial_controller']['unit'].removesuffix('.service')+'.timer'
        with mock.patch.object(helper,'parents_terminal') as parents,mock.patch.object(helper,'command') as command:
            with self.assertRaisesRegex(RuntimeError,'another unit'):
                helper.release_one('foreign.service',owners,[],mock.Mock())
            parents.assert_not_called();command.assert_not_called()
        for stderr,success in [(f'Failed to stop {unit}: Unit {unit} not loaded.',True),
                ('other failure',False),(f'Unit {unit} not loaded.\nUnrelated error',False)]:
            with (self.subTest(stderr=stderr),mock.patch.object(helper,'parents_terminal'),
                    mock.patch.object(helper,'show',side_effect=[({'LoadState':'loaded'},{}),
                        ({'LoadState':'not-found'},{}),({'LoadState':'not-found'},{})]),
                    mock.patch.object(helper,'command',return_value=dict(returncode=5,stderr=stderr,stdout='')) as command):
                if success:
                    result=helper.release_one(unit,owners,[],mock.Mock());self.assertEqual(result['actual_stop_returncode'],5)
                else:
                    with self.assertRaisesRegex(RuntimeError,'Exact stop failed'):
                        helper.release_one(unit,owners,[],mock.Mock())
                command.assert_called_once_with(['systemctl','--user','stop',unit],timeout=30)


if __name__ == '__main__':unittest.main()
