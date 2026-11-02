"""Exercise the exact prospective raw-review protocol boundary; never rescue a failed study."""
import ast
import copy
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
N=Path(__file__).resolve().parent
Q=N/'future-coalescing-raw-reviewer-provenance-original01'
E=N/'evaluator-count-active600-counterbalanced-engineering-original05'

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec)
    sys.modules[name]=m;spec.loader.exec_module(m);return m

h=load('_chain_h',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
assert h.pin(h.__file__)['sha256']=='2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1'
reader=load('_chain_reader',G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py')
assert h.pin(reader.__file__)['sha256']=='c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071'
read=lambda p,as_json=True:reader.read_pin(p,as_json=as_json)
DP=h.pin(Q/'source-derivation-UNSELECTED.json')
assert DP['sha256']=='a797ca2e568fcdfe6e59a55f58d2f56d6bdc3ee71e4a057bd336c97246c6203f'
D=read(DP)
QUAL=read(h.pin(E/'qualified-original-ABBA-launch-configs.json'))
CASES=[]
for i,rec in enumerate(D['cases']):
    old=next(c for c in QUAL['cases']if c['role']==rec['role'])
    family=read(old['source_family'])
    m=load('_chain_'+str(i),h.checked(rec['derived']))
    CASES.append((rec,family,m))

class ChainGuards(unittest.TestCase):
    def test_01_original_failed_provenance_boundary_reproduced_without_any_native_replay(self):
        failure=read(h.pin(E/'original-engineering-campaign-invalid-disposition.json'))
        self.assertEqual(failure['status'],'INVALID_ORIGINAL05_A1_INDEPENDENT_REVIEW_FAILED')
        self.assertTrue(failure['no_original05_rate_reusable'])
        for rec,f,m in CASES:
            old=h.checked(rec['parent']).read_text()
            a=old.index("    RAM_contracts = read(family['RAM_control_components']['contracts'])")
            b=old.index('    quota_audit = load(',a)
            namespace={'ast':ast}
            exec(compile('def historical(family, read):\n'+old[a:b],'<original-failed-boundary>','exec'),namespace)
            with self.assertRaises(AssertionError):namespace['historical'](f,read)
            self.assertFalse((E/'01-A1-control/independent-original-capacity64-case-closeout.json').exists())

    def test_02_exact_future_both_shape_validators_execute_actual_immutable_chain(self):
        for rec,f,m in CASES:
            with patch.object(m.subprocess,'run',side_effect=AssertionError('No child/GPU process allowed'))as subprocess_call:
                result=m.validate_protocol_provenance(f,read)
                subprocess_call.assert_not_called()
            self.assertTrue(result['all_historical_derivations_and_retained_function_AST_verified'])
            self.assertTrue(result['selected_running_publisher_exact_source_and_guarded_behavior_verified'])
            self.assertEqual(result['selected_protocol'],f['main_observer']['protocol'])
            self.assertEqual(result['historical_RAM_codec']['sha256'],'f59df995a625ed534af1c2cb54a15c885a8e431ab84e3829e6a8b2c6ceb7bf10')
            self.assertNotEqual(result['historical_RAM_codec'],result['selected_protocol'])

    def test_03_exact_reverse_derivation_preserves_every_other_raw_review_byte(self):
        for rec,f,m in CASES:
            text=h.checked(rec['derived']).read_text()
            for before,after in reversed(rec['replacements']):
                self.assertEqual(text.count(after),1);text=text.replace(after,before)
            self.assertEqual(text,h.checked(rec['parent']).read_text())
            tree=ast.parse(h.checked(rec['derived']).read_text())
            main=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='main')
            calls=[n for n in ast.walk(main)if isinstance(n,ast.Call)and isinstance(n.func,ast.Name)and n.func.id=='validate_protocol_provenance']
            self.assertEqual(len(calls),1)
            self.assertEqual(calls[0].args[0].id,'family');self.assertEqual(calls[0].args[1].id,'read')
            self.assertNotIn('torch',sys.modules)

    def test_04_wrong_active_protocol_proof_context_and_historical_edges_refused(self):
        for rec,f,m in CASES:
            for kind in ['old_protocol','wrong_protocol','wrong_CPU','wrong_context','wrong_RAM_helper']:
                bad=copy.deepcopy(f)
                if kind=='old_protocol':bad['main_observer']['protocol']=read(f['transient_live_protocol_components']['source_provenance'])['prospective_protocol']
                elif kind=='wrong_protocol':bad['main_observer']['protocol']['sha256']='a'*64
                elif kind=='wrong_CPU':bad['coalescing_protocol_CPU']['sha256']='a'*64
                elif kind=='wrong_context':bad['current_component_main_binding']['sha256']='a'*64
                else:bad['main_live_control']['sha256']='a'*64
                with self.subTest(role=rec['role'],kind=kind),self.assertRaises((AssertionError,ValueError,KeyError)):
                    m.validate_protocol_provenance(bad,read)

    def test_05_corrupt_historical_and_current_data_proofs_refused(self):
        for rec,f,m in CASES:
            cpu=read(f['coalescing_protocol_CPU']);actual=read(f['coalescing_observer_component_CPU'])
            scenarios=[
                (f['RAM_control_components']['contracts'],lambda x:x.update(original_codec_guards=37)),
                (f['RAM_control_components']['source_provenance'],lambda x:x['codec'].update(sha256='a'*64)),
                (f['transient_live_protocol_components']['source_provenance'],lambda x:x['original_protocol'].update(sha256='a'*64)),
                (f['serialized_protocol_components']['source_provenance'],lambda x:x['prospective_protocol'].update(sha256='a'*64)),
                (f['coalescing_protocol_CPU'],lambda x:x.update(actual_tool_terminal_exit=1)),
                (f['coalescing_protocol_CPU'],lambda x:x.update(original_reader500ms_freshness_required_publications_and100ms_bounds_unchanged=False)),
                (cpu['report'],lambda x:x['protocol'].update(sha256='a'*64)),
                (cpu['report'],lambda x:x['coalescing'].update(required_terminal_and_start_publications_unchanged=False)),
                (f['coalescing_observer_component_CPU'],lambda x:x.update(maximum_observation_gap_s=.501)),
                (f['coalescing_observer_component_CPU'],lambda x:x.update(original_raw_main_samples=x['original_raw_main_samples']+1)),
                (f['coalescing_observer_component_CPU'],lambda x:x['running_projection_publication_stats'].update(errors=1)),
                (f['coalescing_observer_component_CPU'],lambda x:x.update(all_original_raw_indices_complete=False)),
                (actual['component_family'],lambda x:x['main_observer']['worker'].update(sha256='a'*64))]
            for index,(pin,mutate) in enumerate(scenarios):
                changed=copy.deepcopy(read(pin));mutate(changed)
                def corrupt(p,as_json=True):
                    return copy.deepcopy(changed)if as_json and p['path']==pin['path']else read(p,as_json)
                with self.subTest(role=rec['role'],case=index),self.assertRaises((AssertionError,ValueError,KeyError)):
                    m.validate_protocol_provenance(f,corrupt)

    def test_06_mutated_retained_reader_lock_and_active_publisher_source_refused(self):
        for rec,f,m in CASES:
            selected=f['main_observer']['protocol'];raw=read(selected,False)
            for before,after in [(b'<=.5',b'<=5.'),(b'LIVE_LOCK_WAIT_S=.1',b'LIVE_LOCK_WAIT_S=1.'),(b'return _publish_live_required_v5(path,value)',b'return None')]:
                self.assertEqual(raw.count(before),1)
                changed=raw.replace(before,after)
                def corrupt(p,as_json=True):
                    return changed if not as_json and p['path']==selected['path']else read(p,as_json)
                with self.subTest(role=rec['role'],mutation=before),self.assertRaises((AssertionError,ValueError,KeyError)):
                    m.validate_protocol_provenance(f,corrupt)

    def test_07_source_derivation_chain_must_reconstruct_current_publisher_exactly(self):
        for rec,f,m in CASES:
            cpu=read(f['coalescing_protocol_CPU']);rp=read(cpu['report'])['source_provenance'];changed=copy.deepcopy(read(rp));changed['exact_change'][1]+='\n# unknown publisher change\n'
            def corrupt(p,as_json=True):
                return copy.deepcopy(changed)if as_json and p['path']==rp['path']else read(p,as_json)
            with self.assertRaises(AssertionError):m.validate_protocol_provenance(f,corrupt)

    def test_08_failed_original_never_requalified_and_next_native_not_selected(self):
        for c in QUAL['cases'][1:]:
            j=read(c['native_job']);self.assertFalse(Path(j['output']).exists())
            self.assertFalse((E/c['case']/'execution-original01').exists())
        self.assertFalse((E/'01-A1-control/independent-original-capacity64-case-closeout.json').exists())
        self.assertFalse(D['native_launch_ready']);self.assertTrue(D['original05_failed_and_never_rescued'])

if __name__=='__main__':
    assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ChainGuards))
    report=h.put(Q/'CPU-provenance-boundary-original01/report.json',dict(schema='robotron-prospective-raw-reviewer-provenance-eight-CPU-guards-v1',source=h.pin(__file__),derivation=DP,tests_run=result.testsRun,passed=result.wasSuccessful(),failures=len(result.failures),errors=len(result.errors),actual_both_shapes_validator_boundary_executed=True,original05_unchanged_and_invalid=True,full_raw_native_review_executed=False,native_started=False,quality_qualified=False))
    print(json.dumps(dict(report=report,passed=result.wasSuccessful())),flush=True)
    time.sleep(8)
    raise SystemExit(0 if result.wasSuccessful()else 1)
