"""Guard exact prepared original ABBA jobs without GPU leases or child work."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
N = Path(__file__).resolve().parent
P = N / 'future-evaluator-concurrency64-UNSELECTED-source-preparation-original02'
E = N / 'evaluator-count-active600-counterbalanced-engineering-original01'


def load(name, pin):
    path = Path(pin['path'])
    assert hashlib.sha256(path.read_bytes()).hexdigest() == pin['sha256']
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


hp = G / 'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py'
h = load('_actual_ABBA_guard_h', dict(path=str(hp), sha256='2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1'))
INDEX_PIN = h.pin(E / 'prepared-original-ABBA-jobs-NOT-LAUNCH-QUALIFIED.json')
assert INDEX_PIN['sha256'] == '7c28b3017eff24d47a2fa4e665d3b4ef11ac6da06d93cafb8394fee84f39da3f'
INDEX = json.loads(h.checked(INDEX_PIN).read_bytes())
CASES = []
for i, c in enumerate(INDEX['cases']):
    job = json.loads(h.checked(c['native_job']).read_bytes())
    runtime, controller = [load('_actual_ABBA_' + str(i) + '_' + key, c[key]) for key in ('runtime','native_controller')]
    family, protocol = [json.loads(h.checked(c[key]).read_bytes()) for key in ('source_family','main_health_protocol')]
    CASES.append((c, job, runtime, controller, family, protocol))


class ActualABBAGuards(unittest.TestCase):
    def test_01_four_native_modes_and_384_original_identity_widths(self):
        identities = []
        self.assertEqual([c['actor_count'] for c in INDEX['cases']], [32,64,64,32])
        for c, j, r, ctl, f, p in CASES:
            self.assertIs(j['initializer_fixture_only'], False)
            self.assertEqual(r.validate_job(j), Path(j['output']))
            self.assertFalse(Path(j['output']).exists())
            self.assertEqual(j['checkpoint']['sha256'], 'b23152ece3bb614831a278fe0572c07433f1bee59c5accef5a1ab7d3007af883')
            identities += [*j['sessions'].values(), *j['connections'].values()]
        self.assertEqual(len(identities), len(set(identities)))
        self.assertEqual(len(identities),384)
        self.assertTrue(all(len(v)==32 and all(ch in '0123456789abcdef' for ch in v) for v in identities))

    def test_02_actual_main_health_contract_for_both_shapes(self):
        for c, j, r, ctl, family, protocol in CASES:
            self.assertIsNone(r.validate_main_health_contract(j,protocol,family))
            for mutation in ['schema','binding','dependency','runtime','observer']:
                f, p = copy.deepcopy(family), copy.deepcopy(protocol)
                if mutation == 'schema':p['schema'] = 'wrong'
                elif mutation == 'binding':p['health_job']['binding']['sha256'] = 'a'*64
                elif mutation == 'dependency':p['health_job']['sources']['extra'] = {}
                elif mutation == 'runtime':f['runtime']['sha256'] = 'a'*64
                else:f['main_observer']['worker']['sha256'] = 'a'*64
                with self.subTest(case=c['case'],mutation=mutation), self.assertRaises(ValueError):
                    r.validate_main_health_contract(j,p,f)

    def test_03_unqualified_original_native_refuses_before_GPU_output_or_thread(self):
        for c, j, r, ctl, f, p in CASES:
            self.assertFalse(Path(j['prelaunch_family_guard_closeout']).exists())
            with patch.object(r.PrivateLease,'acquire',side_effect=AssertionError('GPU lease forbidden')) as lease, \
                 patch.object(r.subprocess,'run',side_effect=AssertionError('subprocess forbidden')) as proc, \
                 patch.object(r.subprocess,'Popen',side_effect=AssertionError('child forbidden')) as child, \
                 patch.object(r.threading.Thread,'start',side_effect=AssertionError('thread forbidden')) as thread:
                with self.assertRaises(FileNotFoundError):r.run(j,c['native_job'],h)
                lease.assert_not_called();proc.assert_not_called();child.assert_not_called();thread.assert_not_called()
            self.assertFalse(Path(j['output']).exists())

    def test_04_native_jobs_cannot_be_used_as_CPU_initializer_fixtures(self):
        for c, j, r, ctl, f, p in CASES:
            with self.assertRaises(ValueError):r.validate_job(j,cpu_initializer=True)
            bad = copy.deepcopy(j);bad['initializer_fixture_only'] = True
            with self.assertRaises(ValueError):r.validate_job(bad)

    def test_05_common_exact12CPU24GiB_controller_and_drift_refusals(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'config.json'
            for c, j, r, ctl, f, p in CASES:
                cfg=json.loads(h.checked(c['unqualified_controller_config']).read_bytes())
                self.assertEqual(ctl.checked_config(c['unqualified_controller_config']['path']),cfg)
                self.assertFalse(Path(cfg['output']).exists())
                for before,after in [('MemoryMax=24G','MemoryMax=16G'),('CPUQuota=1200%','CPUQuota=2400%'),
                                     ('RuntimeMaxSec=22260','RuntimeMaxSec=44400'),('SendSIGKILL=no','SendSIGKILL=yes')]:
                    bad=copy.deepcopy(cfg);bad['properties'][bad['properties'].index(before)]=after
                    path.write_text(json.dumps(bad))
                    with self.subTest(case=c['case'],mutation=before),self.assertRaises(ValueError):ctl.checked_config(path)

    def test_06_both_reviewer_derivations_preserve_full_original_checks(self):
        for role in ['A32','B64']:
            proof=json.loads((E/'reviewer-sources'/(role+'-reviewer-derivation.json')).read_text())
            text=h.checked(proof['derived']).read_text()
            for before,after in reversed(proof['exact_changes']):
                self.assertEqual(text.count(after),1);text=text.replace(after,before)
            self.assertEqual(text,h.checked(proof['parent']).read_text())

    def test_07_all_cases_bind_same_exact_fixed_math_and_new_readers(self):
        design=json.loads(h.checked(INDEX['design']).read_bytes())
        self.assertEqual(design['fixed_comparison_spec']['sha256'],'3401a7f7e0d22fe0b7ac219f8254b1030647e135cd46ea0d44db42692ac44356')
        for c,j,r,ctl,f,p in CASES:
            self.assertEqual(j['experiment_precommit'],INDEX['design'])
            self.assertEqual(f['experiment_precommit'],INDEX['design'])
            self.assertEqual(f['main_rate_reader'],j['main_rate_reader'])
            self.assertEqual(j['main_rate_reader']['sha256'],'dc3de334f4bb8a375d836b2a51401c2d0e12a754260145984deaaba89e5023ae')
            self.assertEqual(f['independent_measurement_reader']['sha256'],'773570fb5869142162afc1d8997738886b4da2e4c8480e88c12f9de7861abaca')
            self.assertEqual(p['health_job']['binding'],design['main_binding'])
            self.assertFalse(f['actual64_startup_verified'])

    def test_08_wrong_policy_and_geometry_are_refused(self):
        for c,j,r,ctl,f,p in CASES:
            for mutation in ['policy','shape','missing_slot','batch','clocks']:
                bad=copy.deepcopy(j)
                if mutation=='policy':bad['checkpoint']['sha256']='a'*64
                elif mutation=='shape':bad['capacity_shape']['games_per_slot']=3
                elif mutation=='missing_slot':bad['actor_slots'].pop()
                elif mutation=='batch':bad['capacity_shape']['inference_max_batch_size']=32
                else:bad['expected_policy_clocks']['training_steps']+=1
                with self.subTest(case=c['case'],mutation=mutation),self.assertRaises(ValueError):r.validate_job(bad)


def main():
    assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ActualABBAGuards))
    report=dict(schema='robotron-capacity64-actual-four-original-job-CPU-guard-results-v1',source=h.pin(__file__),
                prepared_original_jobs=INDEX_PIN,tests_run=result.testsRun,passed=result.wasSuccessful(),
                failures=len(result.failures),errors=len(result.errors),cases=[c for c,j,r,ctl,f,p in CASES],
                actual_GPU_lease_or_worker_or_Torch_or_MAME_started=False,native_launch_ready=False,
                actual64_startup_verified=False,quality_qualified=False)
    print(json.dumps(dict(report=h.put(E/'actual-job-source-family-guards-CPU-original01/actual-eight-CPU-job-guard-results.json',report),
                          tests_run=result.testsRun,passed=result.wasSuccessful())),flush=True)
    time.sleep(8)
    return 0 if result.wasSuccessful() else 1


if __name__=='__main__':
    raise SystemExit(main())
