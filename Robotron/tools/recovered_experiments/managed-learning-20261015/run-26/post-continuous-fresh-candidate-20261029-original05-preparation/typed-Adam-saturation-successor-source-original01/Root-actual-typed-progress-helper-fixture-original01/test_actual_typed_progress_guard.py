import ast,copy,hashlib,json
from pathlib import Path
from types import SimpleNamespace
import unittest
Q=Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-continuous-fresh-candidate-20261029-original05-preparation')
S=Q/'typed-Adam-saturation-successor-source-original01/watch_replay_progress_typed_Adam_saturation_v3.py'
T=Q.parent/'post-continuous-fresh-candidate-20261029-original05/entry-typed-Adam-CPU-original01/endpoint-CPU.json'
class ActualProgressGuardTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  raw=S.read_bytes();assert hashlib.sha256(raw).hexdigest()=='98ffb7eee78101b91ea29e9252b9368b011bed2befa75504fa14c240ded945a5'
  nodes=[x for x in ast.parse(raw).body if isinstance(x,ast.FunctionDef) and x.name in ('ready','endpoint_progress_proof')];assert len(nodes)==2
  ns={};exec(compile(ast.Module(body=nodes,type_ignores=[]),str(S),'exec'),ns);cls.actual=staticmethod(ns['endpoint_progress_proof'])
 def data(self):
  e=json.loads(T.read_bytes());root=json.loads((Q/'Root-selected-fresh-continuous-window-original05.json').read_bytes())
  clocks=('frame_count','training_steps','optimized_samples','learner_frame_count');fields=('process_id','instance_monotonic_ns','epoch','epoch_reason')
  p=dict(thresholds=dict(applied_updates=5000,replay_inserts=1000000,elapsed_s=3600),expected_exposure_lineage=root['expected_exposure_lineage'],entry_Adam_step=e['Adam_step_min'],verifier=e['verification_source']['path'])
  a={k:e['clocks'][k]+(200*4096 if k=='optimized_samples' else 200) for k in clocks};t=copy.deepcopy(a)
  t['training_steps']+=5000;t['optimized_samples']+=5000*4096;t['frame_count']+=1000000;t['learner_frame_count']+=1000000
  def exp(applied,replay):
   x=copy.deepcopy(root['expected_exposure_lineage']);x['optimizer']['total']=dict(applied=applied,unavailable=0);x['replay']['accepted_total']=replay;return dict(learning_exposure=x)
  a['host_pipeline']=exp(100,1000);t['host_pipeline']=exp(5100,1001000)
  v=copy.deepcopy(e);v['clocks']={k:t[k] for k in clocks};added=dict(applied_updates=5000,replay_inserts=1000000,elapsed_s=3600)
  o=SimpleNamespace(CLOCKS=clocks,FIELDS=fields,exposure=lambda x:x['host_pipeline']['learning_exposure'])
  return [v,e,p,a,t,added,o]
 def test_actual_saturation_and_ordinary_positive_paths(self):
  args=self.data();self.assertEqual(self.actual(*args)['classification'],'EXACT_RAW_FLOAT32_2P24_Adam_SATURATION_WITH_OWN_APPLIED_DOSE')
  args=self.data();v,e,p=args[:3];p['entry_Adam_step']=100.;e['Adam_step_min']=e['Adam_step_max']=100.;v['Adam_step_min']=v['Adam_step_max']=101.
  for obj,num in ((e,100.),(v,101.)):
   raw=obj['Adam_raw_step_proof'];raw['raw_step_min']=raw['raw_step_max']=num;raw['all_raw_scalar_float32_exact_2p24']=False
  self.assertEqual(self.actual(*args)['classification'],'ORDINARY_STRICT_Adam_STEP_ADVANCE')
 def test_actual_malformed_or_insufficient_evidence_rejected(self):
  cases=('raw_dtype','vector_step','reset','wrong_raw_value','wrong_raw_count','postload_only','changed_betas','stale_endpoint','noninteger_clock','insufficient_applied','insufficient_replay','insufficient_time','wrong_epoch','unavailable_outcome','wrong_verifier','missing_raw_proof')
  for case in cases:
   with self.subTest(case=case):
    args=self.data();v,e,p,a,t,added,o=args;raw=v['Adam_raw_step_proof']
    if case=='raw_dtype':raw['raw_dtype_counts']={'torch.float64':81};raw['all_raw_scalar_float32']=False
    elif case=='vector_step':raw['all_steps_are_scalar_tensors']=False
    elif case=='reset':raw['counter_reset_or_optimizer_change']=True
    elif case=='wrong_raw_value':raw['raw_step_min']=16777215.
    elif case=='wrong_raw_count':raw['parameters']=80
    elif case=='postload_only':raw['inspected_before_optimizer_load_state_dict']=False
    elif case=='changed_betas':raw['parameter_group_flags'][0]['betas']=[.8,.999]
    elif case=='stale_endpoint':v['clocks']['optimized_samples']-=4096
    elif case=='noninteger_clock':v['clocks']['training_steps']=float(v['clocks']['training_steps'])
    elif case=='insufficient_applied':t['host_pipeline']['learning_exposure']['optimizer']['total']['applied']-=1
    elif case=='insufficient_replay':t['host_pipeline']['learning_exposure']['replay']['accepted_total']-=1
    elif case=='insufficient_time':added['elapsed_s']=3599
    elif case=='wrong_epoch':t['host_pipeline']['learning_exposure']['optimizer']['epoch']+=1
    elif case=='unavailable_outcome':t['host_pipeline']['learning_exposure']['optimizer']['total']['unavailable']=1
    elif case=='wrong_verifier':v['verification_source']['sha256']='0'*64
    elif case=='missing_raw_proof':v.pop('Adam_raw_step_proof')
    with self.assertRaises((AssertionError,KeyError)):self.actual(*args)
if __name__=='__main__':unittest.main(verbosity=2)
