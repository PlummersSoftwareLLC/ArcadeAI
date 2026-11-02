"""Pure simulated future HOT transition around retained actual232 metadata; no live API/control writes."""
import copy
import hashlib
import json
from pathlib import Path
import types
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
SOURCE = HERE/'prepare_hot_LR0625_registry_v1.py'
m = types.ModuleType('_HOT_registry_test'); m.__file__ = str(SOURCE)
exec(compile(SOURCE.read_bytes(),str(SOURCE),'exec'),m.__dict__)


class Tests(unittest.TestCase):
    def setUp(self):
        prior = json.loads(m.HOT_PRIOR.read_text())
        policy = json.loads(Path(prior['supervision_policy']['path']).read_text())
        capture = json.loads(Path(prior['actual_192_capture']['path']).read_text())
        plan_path = m.GAME/'logs/managed-learning-20261015/run-26/post-preview-next-learning-knob-LR0625-precommit-original02-20261027.json'
        plan = json.loads(plan_path.read_text())
        control_path = str(m.GAME/'models_dqn/learning_control.json')
        raw = Path(control_path).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),policy['source_files'][control_path]['sha256'])
        before = json.loads(raw); self.assertEqual(before['lr_scale'],.125)
        after = dict(before,lr_scale=.0625)
        def virtual(name,sha=None): return dict(path='/SIMULATED-HOT/'+name,sha256=sha or name)
        prior_pin = virtual('prior',m.HOT_PRIOR_SHA); prior_pin['path'] = str(m.HOT_PRIOR)
        before_pin = virtual('before',policy['source_files'][control_path]['sha256'])
        after_pin = virtual('after','SIMULATED-AFTER-SHA')
        current_after = copy.deepcopy(policy['source_files'][control_path]); current_after['sha256'] = after_pin['sha256']
        writer_pin = virtual('writer'); transition_pin = virtual('transition')
        plan_pin = virtual('plan','e1518cfd08485f0f74bfd42cc0562fdbc13287af778edca3956a0c5428e91186')
        base_ts = float(capture['api']['ts'])+20
        writer = dict(schema='robotron-owned-one-field-hot-LR-control-publication-v1',owner_before=prior['owner'],owner_after=prior['owner'],
            changed_fields=['lr_scale'],atomic_replace=True,weights_optimizer_scaler_replay_loaded_or_reset=False,phase_record_changed=False,
            before_current_control=policy['source_files'][control_path],after_current_control=current_after,
            publication_begin_unix_s=base_ts+1,publication_complete_unix_s=base_ts+2)
        proof = dict(schema='robotron-owned-one-field-hot-LR125-to-LR0625-transition-v1',root_plan=plan_pin,owner=prior['owner'],
            current_registry=prior_pin,before_control=before_pin,after_control=after_pin,writer_receipt=writer_pin)
        values = {prior_pin['path']:prior,prior['supervision_policy']['path']:policy,prior['actual_192_capture']['path']:capture,
            before_pin['path']:before,after_pin['path']:after,writer_pin['path']:writer,transition_pin['path']:proof,plan_pin['path']:plan}
        for i,label in enumerate(('before_API','first_applied_API','anchor_API')):
            api = copy.deepcopy(capture['api']); api['ts'] = base_ts+i*3; api['pipeline_snapshot_age_s'] = .01
            api['lr'] = 6.25e-6 if i == 0 else 3.125e-6
            for key in ('training_steps','optimized_samples','learner_frame_count','frame_count'): api[key] += i
            exposure=api['host_pipeline']['learning_exposure']; exposure['optimizer']['total']['applied'] += i
            exposure['replay']['accepted_total'] += i
            pin=virtual(label); values[pin['path']]=api
            proof[label]=dict(raw_API=pin,before_unix_s=api['ts'],after_unix_s=api['ts']+.1)
        current_pins = dict(policy['source_files']); current_pins[control_path] = current_after
        current_pins[prior['active_resume_phase_record']['path']] = prior['active_resume_phase_record']
        self.p=types.SimpleNamespace(read=lambda p:values[p['path']],pin=lambda path:current_pins[str(path)])
        self.pin=transition_pin; self.prior_pin=prior_pin; self.values=values; self.proof=proof; self.after=after; self.control_path=control_path
        original=Path.read_text
        self.patch=patch.object(Path,'read_text',lambda path,*a,**k:json.dumps(self.after) if str(path)==control_path else original(path,*a,**k))
        self.patch.start(); self.addCleanup(self.patch.stop)

    def test_actual_retained_context_and_metadata_only_preflight(self):
        result=m.validate_hot_transition(self.p,self.pin,self.prior_pin)
        self.assertEqual(result['prior']['held_hashes'],self.values[self.prior_pin['path']]['held_hashes'])
        output=HERE/'SIMULATED-UNCREATED-PREFLIGHT'
        self.assertFalse(output.exists())
        result=m.rebind_hot(self.p,self.pin,self.prior_pin,output,preflight=True)
        self.assertEqual(result['status'],'METADATA_PREFLIGHT_PASS'); self.assertEqual(result['source_count'],232)
        self.assertFalse(output.exists())

    def test_exact_field_and_later_applied_anchor_negatives(self):
        edits = (
            lambda: self.after.update(reason='UNAUTHORIZED-CHANGE'),
            lambda: self.after.update(lr_scale='0.0625'),
            lambda: self.values[self.proof['anchor_API']['raw_API']['path']]['host_pipeline']['learning_exposure']['optimizer']['total'].update(
                applied=self.values[self.proof['first_applied_API']['raw_API']['path']]['host_pipeline']['learning_exposure']['optimizer']['total']['applied']),
            lambda: self.values[self.proof['anchor_API']['raw_API']['path']]['host_pipeline']['learning_exposure']['replay'].update(accepted_total=0),
            lambda: self.values[self.proof['anchor_API']['raw_API']['path']]['host_pipeline']['learning_exposure']['optimizer'].update(epoch=2),
            lambda: self.values[self.proof['anchor_API']['raw_API']['path']].update(client_count=191),
            lambda: self.proof['anchor_API'].update(after_unix_s=self.proof['anchor_API']['before_unix_s']+6),
        )
        for edit in edits:
            with self.subTest(edit=edit.__code__.co_firstlineno):
                baseline=copy.deepcopy(self.values); edit()
                with self.assertRaises((ValueError,KeyError)): m.validate_hot_transition(self.p,self.pin,self.prior_pin)
                self.values.clear(); self.values.update(baseline); self.proof=self.values[self.pin['path']]
                self.after=self.values[self.proof['after_control']['path']]


if __name__=='__main__': unittest.main(verbosity=2)
