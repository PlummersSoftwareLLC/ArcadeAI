"""One NEW narrow predicate/resolution fixture; no old tests or live processes."""
import copy
from pathlib import Path
import tempfile
import types
import unittest

SOURCE=Path(__file__).resolve().with_name('run_owned192_usage_smoke_v3.py')
r=types.ModuleType('_empty_exec_image_test');r.__file__=str(SOURCE)
exec(compile(SOURCE.read_bytes(),str(SOURCE),'exec'),r.__dict__)


class Tests(unittest.TestCase):
    def test_exact_owned_known_empty_pair_only_and_original_usage_exit_resolution(self):
        known=dict(path='/usr/bin/env',identity=dict(inode=1))
        fixture=dict(launcher_contract=dict(stage_executables=dict(env=known)),actor_executable=dict(path='/usr/games/mame',identity=dict(inode=2)))
        prior=dict(pid=123,starttime_ticks=456,parent_pid=789,cgroup='/fixture',uids=[1001]*4,affinity=[0],command=['gate'],environment={'ROBOTRON_EVAL_MODE':'0'},executable=known,state='S')
        a=dict(prior,command=[''],environment={},state='R');b=copy.deepcopy(a)
        self.assertTrue(r.empty_exec_image_gap(fixture,a,b,prior))
        a0,b0=copy.deepcopy(a),copy.deepcopy(b);a0['command']=b0['command']=[]
        self.assertTrue(r.empty_exec_image_gap(fixture,a0,b0,prior))
        for fault in ('unknownexe','nonemptyargv','one_nonempty','nonemptyenv','pid','birth','parent','cgroup','uid','affinity','zombie'):
            first,second=copy.deepcopy(a),copy.deepcopy(b)
            if fault=='unknownexe':first['executable']=second['executable']=dict(path='/foreign',identity=dict(inode=3))
            if fault=='nonemptyargv':first['command']=second['command']=['/foreign']
            if fault=='one_nonempty':second['command']=['bash']
            if fault=='nonemptyenv':first['environment']=second['environment']={'ROBOTRON_EVAL_MODE':'1'}
            if fault=='pid':first['pid']=second['pid']=124
            if fault=='birth':first['starttime_ticks']=second['starttime_ticks']=457
            if fault=='parent':first['parent_pid']=second['parent_pid']=790
            if fault=='cgroup':first['cgroup']=second['cgroup']='/foreign'
            if fault=='uid':first['uids']=second['uids']=[1002]*4
            if fault=='affinity':first['affinity']=second['affinity']=[1]
            if fault=='zombie':first['state']=second['state']='Z'
            with self.subTest(fault=fault):self.assertFalse(r.empty_exec_image_gap(fixture,first,second,prior))
        with tempfile.TemporaryDirectory()as d:
            path=Path(d)/'slot-000.stdout';path.write_bytes(b'MAME showusage\n'+b'x'*1200)
            attempts=[dict(raw=dict(path='/EXPLICIT-SYNTHETIC-RAW-CAPTURE',sha256='SIMULATED'),pending_exec_image_gaps=[dict(slot='0',pid=123,birth=456,reason=r.EXEC_GAP,executable=known)])]
            terminal={'0':dict(pid=123,birth=456,actual_Popen_exit=0,original_birth_absent=True)}
            usage={'0':dict(positive_installed_usage_output=True,stdout=r.pin(path))};gates=dict(records={'0':dict(record=prior)})
            result=r.resolve_exec_image_gaps(attempts,terminal,usage,gates,fixture)
            self.assertEqual(len(result),1);self.assertTrue(result[0]['disposition'].startswith('UNACCEPTED_'))
            for fault in ('signal','wrongterminal','priorbirth','wrongexe','wrongreason','no_usage'):
                at,te,us,ga=copy.deepcopy(attempts),copy.deepcopy(terminal),copy.deepcopy(usage),copy.deepcopy(gates)
                if fault=='signal':te['0']['actual_Popen_exit']=-15
                if fault=='wrongterminal':te['0']['pid']=124
                if fault=='priorbirth':ga['records']['0']['record']['starttime_ticks']=457
                if fault=='wrongexe':at[0]['pending_exec_image_gaps'][0]['executable']=dict(path='/foreign')
                if fault=='wrongreason':at[0]['pending_exec_image_gaps'][0]['reason']='Unknown stable nonempty argv'
                if fault=='no_usage':us['0']['positive_installed_usage_output']=False
                with self.subTest(resolution=fault),self.assertRaises(ValueError):r.resolve_exec_image_gaps(at,te,us,ga,fixture)


if __name__=='__main__':unittest.main(verbosity=2)
