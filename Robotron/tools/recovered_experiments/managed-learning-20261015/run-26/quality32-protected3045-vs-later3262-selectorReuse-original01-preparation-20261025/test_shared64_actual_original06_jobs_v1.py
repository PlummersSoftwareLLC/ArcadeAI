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
E = N / 'evaluator-count-active600-counterbalanced-engineering-original06'


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
assert INDEX_PIN['sha256'] == '21152d92ddb3ffdc5a7870258364971aea96a668742c6ffd1470af4ab40f8350'
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


    def test_09_all384_new_identities_disjoint_from_all_five_previous_experiments(self):
        old=set()
        for experiment in ('original01','original02','original03','original04','original05'):
            previous=json.loads((N/('evaluator-count-active600-counterbalanced-engineering-'+experiment)/'qualified-original-ABBA-launch-configs.json').read_text())
            for c in previous['cases']:
                j=json.loads(h.checked(c['native_job']).read_bytes());old.update(j['sessions'].values());old.update(j['connections'].values())
        new=set()
        for c,j,r,ctl,f,p in CASES:new.update(j['sessions'].values());new.update(j['connections'].values())
        self.assertEqual(len(new),384);self.assertFalse(new&old)
        design=json.loads(h.checked(INDEX['design']).read_bytes())
        self.assertFalse(design['prior_A1_rate_adopted']);self.assertTrue(design['all_four_original_cases_fresh'])

    def test_10_actual_jobs_pin_and_import_the_corrected_shared64_family(self):
        shared=N/'future-capacity64-shared-slot-domain-UNSELECTED-original01'
        for c,j,r,ctl,f,p in CASES:
            self.assertEqual(r.BRIDGE_COMPONENTS,shared)
            self.assertEqual(r.COMPONENTS,Path(j['runtime']['path']).parent)
            self.assertEqual(j['quota64_source_pins']['bridge']['path'],str(shared/'full_startup_proxy_quota64_v1.py'))
            pins={v['path']:v for v in j['inputs']}
            for filename in ('wire_codec_v2.py','startup_handoff_v2.py','boot_readiness_v3.py','tail_ledger_v1.py'):
                self.assertEqual(pins[str(shared/filename)],h.pin(shared/filename))
            proof=json.loads(h.checked(f['complete_family_CPU8']).read_bytes())
            self.assertTrue(proof['actual32_and64_pre_MAME_seed_and_proxy_constructor_loops_passed'])
            self.assertTrue(proof['real32_64_controller_view_drain_certification_and_raw64_terminal_checks_passed'])

    def test_11_each_exact_job_runtime_is_the_actual_cold_imported_and_SHA_verified_source(self):
        for c,j,r,ctl,f,p in CASES:
            proof=json.loads(h.checked(f['complete_family_CPU9']).read_bytes())
            self.assertTrue(proof['actual_free_threaded_cold_native_imports32_and64_verified'])
            self.assertEqual(proof['tests_run'],10)
            payload=json.loads(h.checked(proof['report']).read_bytes())
            candidates=[x for x in payload['actual_free_threaded_cold_imports']if x.get('passed') and x['native']==j['runtime']['path']]
            self.assertEqual(len(candidates),1)
            actual=candidates[0]
            self.assertFalse(actual['cuda_initialized']);self.assertFalse(actual['checkpoint_loaded'])
            self.assertTrue(actual['free_threaded']);self.assertFalse(actual['native_run_called'])
            self.assertEqual(actual['native_sha256'] if 'native_sha256'in actual else h.pin(actual['native'])['sha256'],j['runtime']['sha256'])
            self.assertEqual(actual['actual_module_paths']['quota_drain'],str(r.COMPONENTS/'fixed_slot_cohort_drain_v2.py'))
            self.assertEqual(c['runtime'],j['runtime'])

    def test_12_common_coalescing_protocol_and_actual_lossless_raw_observer_proofs(self):
        design=json.loads(h.checked(INDEX['design']).read_bytes())
        self.assertTrue(design['common_running_projection_coalescence_stats_required'])
        proof=json.loads(h.checked(design['observer_component_CPU']).read_bytes())
        self.assertEqual(proof['actual_tool_terminal_exit'],0)
        self.assertTrue(proof['live_control_coalesced_without_losing_raw'])
        self.assertEqual(proof['original_raw_main_samples'],127)
        self.assertLessEqual(proof['maximum_observation_gap_s'],.5)
        self.assertEqual(proof['running_projection_publication_stats'],dict(attempts=127,published=121,coalesced_busy_reader=6,errors=0))
        self.assertEqual(proof['actual_protocol']['sha256'],'0ec8510b82783b6d47cad99ba63c59045f32e5b9acf6dbfa128b308f9641d2b9')
        for c,j,r,ctl,f,p in CASES:
            self.assertEqual(f['main_observer']['protocol'],proof['actual_protocol'])
            self.assertEqual(f['coalescing_observer_component_CPU'],design['observer_component_CPU'])
            self.assertEqual(f['coalescing_protocol_CPU'],design['observer_protocol_CPU'])
            self.assertTrue(f['running_projection_stats_required'])
            self.assertEqual(r.OBSERVER_DEPENDENCIES,{k:v['sha256']for k,v in f['main_observer'].items()})
            worker=h.checked(f['main_observer']['worker']).read_text()
            reviewer=h.checked(f['main_observer']['reviewer']).read_text()
            self.assertIn('running_projection_publication_stats=publication_stats',worker)
            self.assertIn("publication_stats['errors']==0",reviewer)
            self.assertIn("len(closed['samples'])==outcome['observed_samples']",reviewer)



    def test_13_all_exact_jobs_bind_new_verified_slot2_context_and_monitor(self):
        design=json.loads(h.checked(INDEX['design']).read_bytes())
        self.assertEqual(design['current_main_context_CPU'],design['observer_component_CPU'])
        self.assertEqual(design['current_main_context_CPU']['sha256'],'1ea379b440a56a28de41cf334b2a64ccfee40a959b50fce373bbff9e3e8b7bfc')
        proof=json.loads(h.checked(design['current_main_context_CPU']).read_bytes())
        self.assertEqual(proof['current_main_binding'],design['main_binding'])
        self.assertEqual(proof['current_main_monitor'],design['current_main_monitor'])
        self.assertEqual(design['main_binding']['sha256'],'d22c93b618b45d98fdf256f5f1cd29a117dacd841b540c10a5a0adcc81818804')
        self.assertTrue(proof['original500ms_freshness_and_max_gap_limits_unchanged'])
        self.assertTrue(proof['all_original_raw_indices_complete'])
        self.assertTrue(proof['all6_descriptors_resources_argv_pins_birth_units_cgroups_release_verified'])
        binding=json.loads(h.checked(design['main_binding']).read_bytes())
        self.assertEqual(len(binding['actors']),192)
        self.assertEqual(len(binding['held_hashes']),197)
        self.assertFalse(binding['historical_study_binding_or_receipts_changed'])
        transition=json.loads(h.checked(binding['verified_between_study_actor_transition']).read_bytes())
        self.assertTrue(design['all_original01_02_03_04_05_IDs_must_be_excluded'])
        for c,j,r,ctl,f,p in CASES:
            self.assertEqual(j['main_binding'],design['main_binding'])
            self.assertEqual(p['health_job']['binding'],design['main_binding'])
            self.assertEqual(f['current_component_main_binding'],design['main_binding'])
            self.assertEqual(f['current_main_context_CPU'],design['current_main_context_CPU'])
            pins={v['path']:v for v in j['inputs']}
            for pin in [design['main_binding'],design['current_main_monitor'],design['current_main_context_CPU'],binding['supervision_policy']]:
                self.assertEqual(pins[pin['path']],pin)
            self.assertEqual(r.validate_main_health_contract(j,p,f),None)



    def test_14_exact_selected_raw_reviewer_executes_guarded_protocol_chain_for_both_shapes(self):
        design=json.loads(h.checked(INDEX['design']).read_bytes())
        pin=design['raw_reviewer_protocol_chain_CPU'];proof=json.loads(h.checked(pin).read_bytes())
        self.assertEqual(proof['actual_tool_terminal_exit'],0);self.assertEqual(proof['tests_run'],8)
        self.assertTrue(proof['actual_A32_B64_raw_reviewer_protocol_boundary_executed'])
        self.assertFalse(proof['full_raw_native_review_verified'])
        self.assertTrue(proof['original05_still_invalid'])
        report=json.loads(h.checked(proof['report']).read_bytes())
        self.assertEqual(report['derivation'],design['reviewer_source_derivation'])
        guarded=json.loads(h.checked(design['reviewer_source_derivation']).read_bytes())
        sources={x['role']:x['derived']for x in guarded['cases']}
        reader=load('_native14_reader',h.pin(G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py'))
        read=lambda p,as_json=True:reader.read_pin(p,as_json=as_json)
        for i,(c,j,r,ctl,f,p) in enumerate(CASES):
            self.assertEqual(f['raw_reviewer_protocol_chain_CPU'],pin)
            self.assertEqual(f['reviewer'],c['reviewer'])
            self.assertEqual(h.checked(c['reviewer']).read_bytes(),h.checked(sources[c['role']]).read_bytes())
            reviewer=load('_native14_reviewer_'+str(i),c['reviewer'])
            self.assertEqual(reviewer.ACTOR_COUNT,c['actor_count'])
            self.assertEqual(reviewer.GAMES_PER_SLOT,2 if c['role']=='A32'else 1)
            actual=reviewer.validate_protocol_provenance(f,read)
            self.assertTrue(actual['all_historical_derivations_and_retained_function_AST_verified'])
            self.assertTrue(actual['selected_running_publisher_exact_source_and_guarded_behavior_verified'])
            self.assertEqual(actual['current_context_observer_CPU'],design['current_main_context_CPU'])
        self.assertEqual(design['prior_original_experiment_failure']['sha256'],'ae1ae37dce0e8dde9056a82411a43cc142fce50961a8435d22036efb2627b7a5')


def main():
    assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ActualABBAGuards))
    report=dict(schema='robotron-capacity64-actual-four-original-job-CPU-guard-results-v1',source=h.pin(__file__),
                prepared_original_jobs=INDEX_PIN,tests_run=result.testsRun,passed=result.wasSuccessful(),
                failures=len(result.failures),errors=len(result.errors),cases=[c for c,j,r,ctl,f,p in CASES],
                actual_GPU_lease_or_worker_or_Torch_or_MAME_started=False,native_launch_ready=False,
                actual64_startup_verified=False,quality_qualified=False)
    print(json.dumps(dict(report=h.put(E/'actual-job-source-family-guards-CPU-original01/actual-fourteen-CPU-job-guard-results.json',report),
                          tests_run=result.testsRun,passed=result.wasSuccessful())),flush=True)
    time.sleep(8)
    return 0 if result.wasSuccessful() else 1


if __name__=='__main__':
    raise SystemExit(main())
