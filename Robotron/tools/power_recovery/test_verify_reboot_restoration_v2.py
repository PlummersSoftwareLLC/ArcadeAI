import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from . import verify_reboot_restoration_v2 as r


class RecoveryRecipeTests(unittest.TestCase):
    def test_existing_recipe_is_explicit_before_any_numerical_import(self):
        with patch.dict(os.environ,{},clear=True):
            r.configure_recipe(dict(batch_size=4096,n_step=3,max_samples_per_frame=8))
            self.assertEqual(dict(os.environ),dict(DQN_BATCH_SIZE='4096',DQN_N_STEP='3',DQN_MAX_SAMPLES_PER_FRAME='8'))

    def test_changed_or_implicit_recipe_is_rejected_without_environment_mutation(self):
        for recipe in ({},dict(batch_size=2048,n_step=3,max_samples_per_frame=8),
                       dict(batch_size=4096,n_step=1,max_samples_per_frame=8),
                       dict(batch_size=4096,n_step=3,max_samples_per_frame=12)):
            with patch.dict(os.environ,{},clear=True),self.assertRaises(ValueError):
                r.configure_recipe(recipe)
            self.assertNotIn('torch',r.__dict__)

    def test_default_invocation_is_inert(self):
        result=subprocess.run(['/usr/bin/python3','-I','-B',str(Path(r.__file__))],capture_output=True,text=True,check=True,timeout=10)
        self.assertEqual(result.stdout.strip(),'PLAN_ONLY_NO_READS_OR_ACTIONS')


if __name__=='__main__':unittest.main()
