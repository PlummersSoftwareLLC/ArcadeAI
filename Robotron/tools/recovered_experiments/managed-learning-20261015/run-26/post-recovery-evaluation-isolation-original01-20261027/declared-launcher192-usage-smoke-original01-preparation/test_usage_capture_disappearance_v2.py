"""One new changed-branch test; no old fixture/suite/fork/process action."""
import copy
from pathlib import Path
import tempfile
import types
import unittest

SOURCE=Path(__file__).resolve().with_name('run_owned192_usage_smoke_v2.py')
r=types.ModuleType('_usage_disappearance_test');r.__file__=str(SOURCE)
exec(compile(SOURCE.read_bytes(),str(SOURCE),'exec'),r.__dict__)


class Tests(unittest.TestCase):
    def test_only_original_normal_usage_exit_resolves_unaccepted_disappearance(self):
        with tempfile.TemporaryDirectory()as d:
            path=Path(d)/'slot-000.stdout';path.write_bytes(b'MAME showusage\n'+b'x'*1200)
            attempts=[dict(raw=dict(path='/EXPLICIT-SYNTHETIC-RAW-CAPTURE',sha256='SIMULATED'),pending_disappearances=[dict(slot='0',pid=123,birth=456,reason=r.DISAPPEARED)])]
            terminal={'0':dict(pid=123,birth=456,actual_Popen_exit=0,original_birth_absent=True)}
            usage={'0':dict(positive_installed_usage_output=True,stdout=r.pin(path))}
            result=r.resolve_disappearances(attempts,terminal,usage)
            self.assertEqual(len(result),1);self.assertEqual(result[0]['original_unaccepted_raw_capture'],attempts[0]['raw'])
            self.assertEqual(result[0]['disposition'],'UNACCEPTED_CAPTURE_RESOLVED_BY_ORIGINAL_NORMAL_USAGE_EXIT')
            for fault in ('signal','nonzero','bool_exit','pid','birth','still_alive','not_usage','wrong_exception'):
                a,t,u=copy.deepcopy(attempts),copy.deepcopy(terminal),copy.deepcopy(usage)
                if fault=='signal':t['0']['actual_Popen_exit']=-15
                if fault=='nonzero':t['0']['actual_Popen_exit']=1
                if fault=='bool_exit':t['0']['actual_Popen_exit']=False
                if fault=='pid':t['0']['pid']+=1
                if fault=='birth':t['0']['birth']+=1
                if fault=='still_alive':t['0']['original_birth_absent']=False
                if fault=='not_usage':u['0']['positive_installed_usage_output']=False
                if fault=='wrong_exception':a[0]['pending_disappearances'][0]['reason']='Unknown stable executable'
                with self.subTest(fault=fault),self.assertRaises(ValueError):r.resolve_disappearances(a,t,u)
            path.write_bytes(b'No usage output '+b'x'*1200);usage['0']['stdout']=r.pin(path)
            with self.assertRaisesRegex(ValueError,'actual pinned positive usage'):r.resolve_disappearances(attempts,terminal,usage)


if __name__=='__main__':unittest.main(verbosity=2)
