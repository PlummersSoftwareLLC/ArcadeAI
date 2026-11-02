"""New operational one-use controller, nonzero-exit and stop-projection guards."""
import ast
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

B=Path(__file__).resolve().parent
G=B.parents[1]

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module

seq=load('_new_quality_sequence_control',B/'sequence_quality32_campaign_v2.py')
h=load('_sequence_control_guard_helpers',B/'run_full_policy_startup_v3.py')
ctl=load('_sequence_control_guard_CPU_controller',G/'tools/quality_capacity_proposal/control_quality32_review_v1.py')
rd=load('_sequence_control_guard_immutable_reader',G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py')
rt=load('_sequence_control_guard_archived_closure',G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py')

class QualitySequenceControlV1(unittest.TestCase):
    def directory(self):
        value=tempfile.TemporaryDirectory(prefix='quality32-new-sequence-guard-')
        self.addCleanup(value.cleanup);return Path(value.name)

    def test_actual_owned_controller_negative17_exit_archives_and_closes_once_without_normalization(self):
        root=self.directory();payload=root/'owned-negative17.py'
        payload.write_text("import time\nprint('owned negative17 fixture',flush=True)\ntime.sleep(2)\nraise SystemExit(17)\n")
        payload.chmod(0o444)
        cfg=dict(unit='robotron-quality32-sequence-owned-negative17-original01-20261022.service',
            output=str(root/'original-controller-output'),argv=['/usr/bin/python3.12','-I','-B',str(payload)],
            properties=['CPUQuota=200%','MemoryMax=4G','MemorySwapMax=0','RuntimeMaxSec=180',
                'TasksMax=256','TimeoutStopSec=5','SendSIGKILL=no'],pins=[ctl.pin(payload)],observation_s=240)
        cp=h.put(root/'controller-config.json',cfg);source=h.pin(ctl.__file__);observed=[]
        result_pin=seq.invoke_controller_once(root,'',source,cp,h,lambda owner,child:observed.append((owner,child)))
        read=lambda entry,as_json=True:rd.read_pin(entry,as_json=as_json)
        result=read(result_pin);self.assertEqual(result['actual_exit'],17)
        self.assertEqual(result['live_registration_errors'],[])
        evidence=seq.verify_closed_scope(root,'',cp,h,read,rt,ctl,exit_zero=False)
        self.assertEqual(evidence['fields']['ExecMainStatus'],'17')
        self.assertEqual(evidence['fields']['Result'],'exit-code')
        self.assertTrue(read(evidence['closure'])['lifecycle_complete'])
        self.assertEqual(result_pin,h.pin(root/'controller-original-result.json'))
        with self.assertRaises(ValueError):seq.verify_closed_scope(root,'',cp,h,read,rt,ctl,exit_zero=True)
        with self.assertRaises(ValueError):seq.invoke_controller_once(root,'',source,cp,h)
        self.assertEqual(result_pin,h.pin(root/'controller-original-result.json'))
        self.assertEqual(ctl.show(cfg['unit'])['LoadState'],'not-found')
        self.assertTrue(observed)

    def test_operator_stop_preserves_a_live_original_scope_and_schedules_no_new_action(self):
        root=self.directory();campaign=root/'campaign';campaign.mkdir()
        (campaign/'events').mkdir();(campaign/'sequence-state-backups-original01').mkdir()
        child=subprocess.Popen(['/usr/bin/python3.12','-I','-B','-c','import time; time.sleep(30)'],
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            owner=dict(pid=child.pid,starttime_ticks=seq.birth(child.pid),unit='synthetic-owned-live.service',invocation_id='c'*32)
            state=root/'state.json'
            state.write_text(json.dumps(dict(active_quality_job=dict(directory=str(campaign),current_leg=1),
                optimization_goal=dict(active_quality_job=dict(directory=str(campaign),current_leg='R1',actual_scope=owner),
                    actual_running_wait=dict(scope_pid=child.pid,scope_birth=owner['starttime_ticks'])))))
            fixture=object.__new__(seq.CampaignSequence)
            fixture.root=campaign;fixture.events=campaign/'events';fixture.h=h;fixture.count=0;fixture.ready_pin={'sha256':'a'*64}
            with patch.object(seq,'R',root/'run-26'):
                fixture.register('SEQUENCING_STOPPED_REQUESTED','campaign',terminal=True)
                result=json.loads(state.read_text())
                self.assertEqual(result['optimization_goal']['actual_running_wait']['scope_pid'],child.pid)
                self.assertTrue(result['optimization_goal']['actual_running_wait']['sequencing_halted'])
                self.assertEqual(result['active_quality_job']['current_leg'],1)
                (campaign/'sequencing-control.json').write_text('{"stop_new_actions":true}')
                with self.assertRaises(seq.StopNewActions):fixture.check_new_actions()
            self.assertIsNone(child.poll())
        finally:
            child.terminate();child.wait(timeout=10)

    def test_controller_launch_wait_archive_functions_stay_identical_and_default_cli_is_inert(self):
        def functions(path):return {n.name:ast.dump(n,include_attributes=False)
            for n in ast.parse(path.read_text()).body if isinstance(n,ast.FunctionDef)}
        before=functions(B/'sequence_quality32_campaign_v1.py');after=functions(Path(seq.__file__))
        self.assertEqual(before['invoke_controller_once'],after['invoke_controller_once'])
        self.assertEqual(before['verify_closed_scope'],after['verify_closed_scope'])
        result=subprocess.run(['/usr/bin/python3.12','-I','-B',seq.__file__],capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0);self.assertEqual(result.stdout.strip(),'PLAN_ONLY')
        self.assertEqual(result.stderr,'');self.assertNotIn('torch',sys.modules)

if __name__=='__main__':unittest.main(verbosity=2)
