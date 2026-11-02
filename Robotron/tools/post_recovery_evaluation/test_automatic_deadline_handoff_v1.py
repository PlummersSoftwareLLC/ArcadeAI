"""Original-owner races and one-attempt dispatch; fixtures never control live jobs."""
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from . import automatic_deadline_handoff_v1 as s


class AutomaticHandoffTests(unittest.TestCase):
    phases=['original_R1','prepare_review','review','qualify','prepare_continuation','continuation']

    def observation(self,**changes):
        value=dict(wrapper_alive=False,controller_alive=False,native_alive=False,
                   controller_result=dict(actual_exit=0,live_registration_errors=[]))
        value.update(changes);return value

    def test_only_original_owner_completion_allows_progress_not_unit_absence(self):
        self.assertTrue(s.original_R1_ready(self.observation()))
        for receipt in (None,dict(actual_exit=0,live_registration_errors=[]),dict(actual_exit=1,live_registration_errors=[])):
            for child in (True,False):
                self.assertFalse(s.original_R1_ready(self.observation(wrapper_alive=True,
                    controller_alive=child,native_alive=child,controller_result=receipt,unit_absent=True)))

    def test_missing_failed_boolean_or_unregistered_terminal_never_allows_retry(self):
        for receipt in (None,dict(actual_exit=1,live_registration_errors=[]),
                        dict(actual_exit=False,live_registration_errors=[]),dict(actual_exit=0,live_registration_errors=['failed'])):
            with self.subTest(receipt=receipt),self.assertRaises(ValueError):
                s.original_R1_ready(self.observation(controller_result=receipt))

    def test_live_original_children_after_wrapper_disappearance_stop_dispatch(self):
        for controller,native in ((True,False),(False,True),(True,True)):
            with self.subTest(controller=controller,native=native),self.assertRaises(ValueError):
                s.original_R1_ready(self.observation(controller_alive=controller,native_alive=native))

    def exercise(self,fail=None,stop=None):
        seen=[]
        def action(label,records):
            self.assertEqual(list(records),self.phases[:self.phases.index(label)])
            seen.append(label)
            if label==fail:raise ValueError('Original failed')
            return label
        def before(label):
            if label==stop:raise ValueError('Stop new actions')
        try:result=s.walk(*[lambda records,label=label:action(label,records)for label in self.phases],before)
        except ValueError:result=None
        return seen,result

    def test_one_original_review_then_qualified_continuation_exactly_once(self):
        seen,result=self.exercise();self.assertEqual(seen,self.phases)
        self.assertEqual(list(result),self.phases);self.assertEqual(len(seen),len(set(seen)))

    def test_every_original_failure_stops_all_later_actions_without_retry(self):
        for index,phase in enumerate(self.phases):
            seen,result=self.exercise(fail=phase)
            self.assertEqual(seen,self.phases[:index+1]);self.assertIsNone(result)

    def test_operator_stop_at_each_boundary_starts_nothing_later(self):
        for index,phase in enumerate(self.phases):
            seen,result=self.exercise(stop=phase)
            self.assertEqual(seen,self.phases[:index]);self.assertIsNone(result)

    def test_boot_canonical_source_and_operator_guards_prevent_new_actions(self):
        with tempfile.TemporaryDirectory()as temporary:
            root=Path(temporary);state=root/'state.json';state.write_text(json.dumps(dict(active_quality_job=dict(directory=str(root)))))
            instance=s.Handoff.__new__(s.Handoff);instance.output=root;instance.root=root
            keys=('source','review_preparer','continuation','projector','owned_helper')
            instance.job=dict(boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),**dict.fromkeys(keys,'ENGINEERING-pin'))
            checked=[];instance.h=SimpleNamespace(checked=lambda pin:checked.append(pin))
            with patch.object(s,'STATE',state):
                instance.check('review');self.assertEqual(len(checked),5)
                instance.job['boot_id']='ENGINEERING-wrong-boot'
                with self.assertRaisesRegex(ValueError,'boot'):instance.check('review')
                instance.job['boot_id']=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
                state.write_text('{"active_quality_job":{"directory":"ENGINEERING-other"}}')
                with self.assertRaisesRegex(ValueError,'Active original study'):instance.check('review')
                state.write_text(json.dumps(dict(active_quality_job=dict(directory=str(root)))))
                instance.h=SimpleNamespace(checked=lambda pin:(_ for _ in ()).throw(ValueError('Source changed')))
                with self.assertRaisesRegex(ValueError,'Source changed'):instance.check('review')
                (root/'stop-new-actions.json').write_text('{"stop_new_actions":true}')
                with self.assertRaisesRegex(ValueError,'Operator stopped'):instance.check('review')
        result=subprocess.run(['/usr/bin/python3','-I','-B',s.__file__],capture_output=True,text=True,timeout=10,check=True)
        self.assertEqual(result.stdout.strip(),'PLAN_ONLY_NO_READS_OR_ACTIONS')

    def test_callback_failure_still_reaps_same_original_Popen_once_and_seals_receipt(self):
        with tempfile.TemporaryDirectory()as temporary:
            root=Path(temporary);records={};waits=[]
            instance=s.Handoff.__new__(s.Handoff);instance.output=root
            def put(path,value):records[path.name]=value;return dict(path=str(path))
            instance.h=SimpleNamespace(put=put,pin=lambda path:dict(path=str(path)))
            instance.helper=SimpleNamespace(birth=lambda pid:987654)
            child=SimpleNamespace(pid=123456,wait=lambda:(waits.append('same-original')or 0))
            def callback(actual):
                self.assertIs(actual,child);raise ValueError('Metadata publication failed')
            with patch.object(s.subprocess,'Popen',return_value=child)as launch:
                instance.owned_program('ENGINEERING',['/ENGINEERING-never-executed'],callback)
            self.assertEqual(launch.call_count,1);self.assertEqual(waits,['same-original'])
            terminal=records['ENGINEERING-terminal.json'];self.assertEqual(terminal['actual_exit'],0)
            self.assertEqual(terminal['live_registration_errors'],["ValueError('Metadata publication failed')"])
            self.assertEqual((root/'ENGINEERING-stdout.txt').stat().st_mode&0o777,0o444)
            self.assertEqual((root/'ENGINEERING-stderr.txt').stat().st_mode&0o777,0o444)


if __name__=='__main__':unittest.main()
