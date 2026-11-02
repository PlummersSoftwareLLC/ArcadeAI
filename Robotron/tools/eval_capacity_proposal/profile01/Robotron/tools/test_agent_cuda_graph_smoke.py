"""CPU-only fail-closed preflight tests for the isolated agent wiring smoke."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from smoke_agent_cuda_graphs import validate_sources,GAME


class AgentSmokePreflightTests(unittest.TestCase):
    def test_unreviewed_source_digest_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'differs from reviewed'):
            validate_sources(GAME/'Scripts/dqn/agent.py','0'*64,'0'*64)

    def test_candidate_outside_robotron_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            candidate=Path(directory)/'agent.py';candidate.write_text('raise RuntimeError("must not run")\n')
            with self.assertRaisesRegex(ValueError,'Robotron source'):
                validate_sources(candidate,'0'*64,'0'*64)

    def test_import_has_no_numerical_or_constructor_sideeffects(self):
        script=Path(__file__).with_name('smoke_agent_cuda_graphs.py')
        source="import runpy,sys;sys.path.insert(0,sys.argv[1]);runpy.run_path(sys.argv[2]);assert 'torch' not in sys.modules;assert 'numpy' not in sys.modules;assert 'dqn.agent' not in sys.modules"
        subprocess.run([sys.executable,'-c',source,str(script.parent),str(script)],check=True,timeout=5)


if __name__=='__main__':unittest.main()
