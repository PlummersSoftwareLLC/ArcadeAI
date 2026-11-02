"""UNEXECUTED stdlib small-file phase/load tests; no checkpoint tensors."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

HERE=Path(__file__).parent
spec=importlib.util.spec_from_file_location("priority_phase_test_owned",HERE/"priority_phase.py")
phase=importlib.util.module_from_spec(spec)
spec.loader.exec_module(phase)


class PhaseContracts(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="priority-phase-small-")
        self.root=Path(self.temp.name).resolve()
        self.latest=self.root/"latest.pt"
        self.latest.write_bytes(b"NOT A MODEL; small source identity fixture only")
        self.pin=phase.file_pin(self.latest)
        self.record=dict(schema=phase.START_SCHEMA,phase_id="test-phase",metric="kl",action="start",
            previous_metric="unknown",checkpoint=self.pin,model_dir=str(self.root),root_precommit_sha256="a"*64)
        self.clock={key:1000 for key in phase.CLOCKS}

    def tearDown(self):self.temp.cleanup()

    def instance(self,record=None,**extra):
        record=record or self.record
        path=self.root/("phase-%d.json"%len(list(self.root.glob("phase-*.json"))))
        raw=(json.dumps(record,sort_keys=True)+"\n").encode();path.write_bytes(raw);path.chmod(0o444)
        env=dict(DQN_PRIORITY_PHASE_RECORD=str(path),DQN_PRIORITY_PHASE_RECORD_SHA256=hashlib.sha256(raw).hexdigest(),**extra)
        with mock.patch.dict(os.environ,env,clear=True):return phase.PriorityPhase(record["metric"],str(self.latest),str(self.root))

    def loaded(self):
        obj=self.instance();obj.before_load(str(self.latest),dict(self.clock));obj.finish_load(str(self.latest));return obj

    def test_start_records_actual_source_floor_and_unknown_tree_not_matched_anchor(self):
        obj=self.loaded();obj.require_ready("kl")
        saved=obj.snapshot()
        self.assertEqual(saved["started_from"],dict(self.pin,clocks=self.clock))
        self.assertIn("no per-leaf",saved["initial_tree"])
        self.assertEqual(saved["priority_update_calls"],0)

    def test_load_is_required_and_changed_source_is_rejected_before_ready(self):
        obj=self.instance()
        with self.assertRaises(RuntimeError):obj.require_ready("kl")
        obj.before_load(str(self.latest),dict(self.clock))
        self.latest.write_bytes(b"changed small source")
        with self.assertRaisesRegex(RuntimeError,"changed during restore"):obj.finish_load(str(self.latest))
        self.assertFalse(obj.loaded)

    def test_resume_retains_anchor_counts_and_binds_current_record_and_precommit(self):
        old=self.loaded();old.note_update("kl",4,[.01,.2,0.,0.,0.,1e-7,1e-8]);saved=old.snapshot()
        record=dict(self.record,action="resume",previous_metric="kl")
        obj=self.instance(record);obj.before_load(str(self.latest),dict(self.clock,priority_metric_phase=saved))
        obj.finish_load(str(self.latest))
        self.assertEqual(obj.snapshot()["started_from"],saved["started_from"])
        self.assertEqual(obj.snapshot()["priority_update_calls"],1)
        self.assertEqual(obj.snapshot()["last_resume_record_sha256"],obj.record_sha256)
        bad=self.instance(dict(record,root_precommit_sha256="b"*64))
        with self.assertRaisesRegex(RuntimeError,"resume must match"):
            bad.before_load(str(self.latest),dict(self.clock,priority_metric_phase=saved))

    def test_resume_unknown_metric_missing_phase_id_or_invalid_saved_phase_fails(self):
        saved=self.loaded().snapshot();record=dict(self.record,action="resume",previous_metric="kl")
        for key,value in (("schema","unknown"),("phase_id","other"),("metric","ce"),("valid",False),
                          ("priority_update_calls","not-a-counter")):
            with self.subTest(key=key):
                bad=copy.deepcopy(saved);bad[key]=value;obj=self.instance(record)
                with self.assertRaises(RuntimeError):obj.before_load(str(self.latest),dict(self.clock,priority_metric_phase=bad))

    def test_return_to_CE_requires_new_explicit_phase_and_preserves_predecessor(self):
        saved=self.loaded().snapshot()
        with self.assertRaises(RuntimeError):phase.require_checkpoint_phase({"priority_metric_phase":saved},"ce",None)
        record=dict(self.record,phase_id="return-ce",metric="ce",previous_metric="kl")
        obj=self.instance(record);obj.before_load(str(self.latest),dict(self.clock,priority_metric_phase=saved))
        obj.finish_load(str(self.latest));obj.require_ready("ce")
        self.assertEqual(obj.snapshot()["predecessor"]["phase_id"],saved["phase_id"])
        self.assertEqual(obj.snapshot()["metric"],"ce")

    def test_no_silent_hot_metric_or_invalid_phase_restart(self):
        obj=self.loaded()
        with self.assertRaises(RuntimeError):obj.require_ready("ce")
        obj.invalidate(RuntimeError("original failure"))
        with self.assertRaises(RuntimeError):obj.require_ready("kl")
        self.assertFalse(obj.snapshot()["valid"])
        self.assertEqual(obj.snapshot()["invalid_reason"],"original failure")

    def test_counter_is_visits_including_duplicates_not_unique_leaf_conversion(self):
        obj=self.loaded();obj.note_update("kl",4,[.01,.2,0.,0.,0.,1e-7,1e-8])
        obj.note_update("kl",4,[.02,.3,0.,0.,0.,1e-7,1e-8])
        self.assertEqual(obj.snapshot()["priority_update_calls"],2)
        self.assertEqual(obj.snapshot()["ring_rows_submitted"],8)

    def test_failed_raw_diagnostics_are_retained_without_nonfinite_JSON_numbers(self):
        obj=self.loaded();obj.reject_diagnostics([float("nan"),.2,1.,0.,-.001,.01,.001])
        saved=obj.snapshot();self.assertEqual(saved["last_rejected_diagnostics"]["signed_min"],"nan")
        self.assertEqual(saved["last_rejected_diagnostics"]["target_mass_error_max"],.01)
        json.dumps(saved,allow_nan=False)

    def test_capture_flags_and_wrong_startup_bytes_cannot_be_used_as_trial_start(self):
        with self.assertRaisesRegex(RuntimeError,"capture flags"):
            self.instance(DQN_RECOMPUTED_CE_CAPTURE_DIR="/unused")
        obj=self.instance(dict(self.record,checkpoint=dict(self.pin,sha256="f"*64)))
        with self.assertRaisesRegex(RuntimeError,"wrong actual newest"):
            obj.before_load(str(self.latest),dict(self.clock))

    def test_untagged_default_CE_needs_no_phase_record_or_file_reads(self):
        with mock.patch.object(phase,"file_pin",side_effect=AssertionError("read")):
            phase.require_checkpoint_phase({},"ce",None)
        with self.assertRaises(RuntimeError):phase.require_checkpoint_phase({},"kl",None)


if __name__=="__main__":unittest.main()
