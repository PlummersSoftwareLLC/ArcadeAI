"""Synthetic/temp-only prospective publisher tests; no future128M data reads."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock, patch


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("prospective128_publication", HERE / "build_confirmed128M_campaign.py")
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


class PublisherTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        for name, value in {
            "GAME": self.root, "SOURCE": self.root / "models/checkpoints/future.pt",
            "DESTINATION": self.root / "models/protected/new.pt",
            "PUBLICATION": self.root / "campaign/new.json",
        }.items():
            if name != "GAME":
                value.parent.mkdir(parents=True, exist_ok=True)
            p = patch.object(builder, name, value)
            p.start(); self.addCleanup(p.stop)

    def report(self):
        legs = [dict(label=label, count=100, mean=170000., median=150000.,
                     mean_pass=True, median_pass=True, passes_each_criterion=True) for label in builder.LABELS]
        labels = [*builder.REFERENCE_LABELS, builder.GUARD_LABEL, *builder.LABELS,
                  *["historical-" + str(n) for n in range(17)]]
        sources = [dict(label=label, path=str(self.root / (label + ".json")),
                        sha256=hashlib.sha256(label.encode()).hexdigest()) for label in labels]
        return dict(schema="robotron-128M-promotion-analysis-v1", utc="fake",
            management=dict(status="two_legs_pass_root_promotion_review", promotion_eligible=True,
                promotion=False, reference_rebased=False, third_valid_cohort_authorized=False,
                reference=dict(count=217, mean=152123.27188940093, median=146575.),
                thresholds=dict(mean=builder.MEAN_FLOOR, median=builder.MEDIAN_FLOOR), each_leg=legs),
            fixed_bootstrap_iterations=10000, all_source_receipts_separately_validated=True,
            no_fabricated_measurement_receipt=True,
            lineage=dict(path=str(self.root / "lineage.json"), sha256="b"*64),
            policy_identity=dict(candidate=dict(path=str(builder.SOURCE), sha256="a"*64,
                metadata=dict(training_steps=1000, optimized_samples=4096000, learner_frame_count=133000000))),
            sources=sources, global_ids=dict(receipts=22, games=2437, overlaps=0),
            pooled_candidate_vs_composite=dict(reference=dict(count=217, mean=152123.27188940093),
                candidate=dict(count=200, mean=170000., median=150000., se=100.), mean_ratio=1.1175),
            matched_frozen_backend={}, full_leg_denominators=[], official_pair_validation={},
            each_candidate_vs_composite={}, clocks_separate=[], caveats=["fake rows only"],
            promotion=False, protection=False, state_or_control_changes=False)

    def args(self):
        return SimpleNamespace(publish=True, analysis=self.root / "analysis.json", analysis_sha256="c"*64,
            lineage=self.root / "lineage.json", lineage_sha256="b"*64, checkpoint_sha256="a"*64,
            screen_audit=self.root / "screen-audit.json", screen_audit_sha256="d"*64,
            confirm_audit=self.root / "confirm-audit.json", confirm_audit_sha256="e"*64)

    def fixture(self, *, provided=None, fresh=None, cleanup=True):
        provided = self.report() if provided is None else provided
        fresh = copy.deepcopy(provided) if fresh is None else fresh
        lineage = dict(candidate=dict(sha256="a"*64, saved_metadata=dict(learner_frame_count=133000000), optimizer={}),
            root_verification=dict(verifier_sha256=builder.ROOT_VERIFIER_SHA, precommit_sha256=builder.ROOT_PRECOMMIT_SHA),
            branch_provenance=dict(compiler_and_instrumentation_chronology=[]), counter_exposure_evidence={})
        plan = dict(candidate=dict(labels=list(builder.LABELS), checkpoint=str(builder.SOURCE)),
                    reference=dict(saved_clocks={}, campaign="old64-campaign.json", campaign_sha256="f"*64),
                    additional_history=[dict(label=builder.GUARD_LABEL, pooled_into_reference=False)])
        calls = []
        class Evidence:
            def file(self, *args):
                return Path(args[0])
            def json(self, path, expected):
                name = Path(path).name
                if name == "analysis.json":
                    return provided
                if name == "lineage.json":
                    return lineage
                label = builder.LABELS[0] if name == "screen-audit.json" else builder.LABELS[1]
                source = next(row for row in fresh["sources"] if row["label"] == label)
                return dict(pass_=True, checks={}, receipt_sha256=source["sha256"])
            def recheck(self):
                calls.append("byte recheck")
        initial, evidence = Evidence(), Evidence()
        def read(path, expected):
            name = Path(path).name
            if name == "analysis.json":
                return provided
            if name == "lineage.json":
                return lineage
            label = builder.LABELS[0] if name == "screen-audit.json" else builder.LABELS[1]
            source = next(row for row in fresh["sources"] if row["label"] == label)
            return {"pass":True, "checks":dict(private_owned_processes_listener_released=cleanup,
                private_GPU0_context_released=True, loaded_sources_unchanged=True),
                "receipt_sha256":source["sha256"], "checkpoint_sha256":"a"*64}
        initial.json = read
        analyzer = SimpleNamespace(Evidence=Mock(return_value=initial), lineage_identity=Mock(),
            build=Mock(side_effect=lambda *args: calls.append("strict analysis") or (fresh,evidence)))
        protected = dict(path=str(builder.DESTINATION), sha256="a"*64, metadata_sha256="1"*64)
        with patch.dict(os.environ, CUDA_VISIBLE_DEVICES=""), \
                patch.object(builder,"pinned_json",return_value=plan), \
                patch.object(builder,"load_analyzer",return_value=analyzer), \
                patch.object(builder,"verify_prior",side_effect=lambda *args:calls.append("prior bytes") or dict(protected=[{}]*8)), \
                patch.object(builder,"protect_checkpoint",side_effect=lambda *args:calls.append("protect") or protected) as protect, \
                patch.object(builder,"publish_json",side_effect=lambda *args:calls.append("campaign")) as publish:
            try:
                result = builder.publish_campaign(self.args())
            except (ValueError,KeyError) as error:
                result = error
        return result, analyzer, protect, publish, calls

    def test_import_and_default_plan_do_not_open_future_data_or_change_environment(self):
        before = dict(os.environ)
        with patch.object(Path,"read_bytes",side_effect=AssertionError("future opened")), \
                patch.object(Path,"open",side_effect=AssertionError("future opened")):
            spec=importlib.util.spec_from_file_location("inert128",HERE/"build_confirmed128M_campaign.py")
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            with patch("sys.argv",["publisher"]),patch("builtins.print"):
                module.main()
        self.assertEqual(dict(os.environ),before)

    def test_missing_SHA_or_publish_cannot_open_evidence(self):
        for key in ("publish","analysis_sha256","lineage_sha256","checkpoint_sha256","screen_audit_sha256","confirm_audit_sha256"):
            args=self.args();setattr(args,key,False if key=="publish" else "PLACEHOLDER")
            with self.subTest(key=key),patch.dict(os.environ,CUDA_VISIBLE_DEVICES=""), \
                    patch.object(builder,"pinned_json",side_effect=AssertionError("data opened")), \
                    self.assertRaises(ValueError):
                builder.publish_campaign(args)

    def test_two_individual_gates_not_a_pooled_rescue_or_single_leg(self):
        report=self.report();builder.confirmed_gate(report,"a"*64,self.root/"lineage.json","b"*64)
        for field in ("mean","median","missing","ids","reference","checkpoint"):
            broken=copy.deepcopy(report)
            if field=="mean":broken["management"]["each_leg"][0]["mean"]=builder.MEAN_FLOOR-1
            elif field=="median":broken["management"]["each_leg"][1]["median"]=builder.MEDIAN_FLOOR-1
            elif field=="missing":broken["management"]["each_leg"].pop()
            elif field=="ids":broken["global_ids"]["overlaps"]=1
            elif field=="reference":broken["management"]["reference"]["count"]=298
            else:broken["policy_identity"]["candidate"]["sha256"]="0"*64
            with self.subTest(field=field),self.assertRaises(ValueError):
                builder.confirmed_gate(broken,"a"*64,self.root/"lineage.json","b"*64)

    def test_low_N_leg_is_precision_only_not_an_added_promotion_gate(self):
        report=self.report()
        for row in report["management"]["each_leg"]:
            row["count"]=16
        report["global_ids"]["games"]=2237+32
        report["pooled_candidate_vs_composite"]["candidate"]["count"]=32
        result,_,protect,publish,_=self.fixture(provided=report)
        self.assertIsInstance(result,dict,result)
        self.assertEqual(result["descriptive_pools"]["confirmed128M"]["count"],32)
        protect.assert_called_once();publish.assert_called_once()
        for invalid in (0,-1,True,16.0):
            broken=copy.deepcopy(report)
            broken["management"]["each_leg"][0]["count"]=invalid
            with self.subTest(count=invalid),self.assertRaises(ValueError):
                builder.confirmed_gate(broken,"a"*64,self.root/"lineage.json","b"*64)

    def test_full_fake_validation_precedes_protection_current_sources_only_two(self):
        result,analyzer,protect,publish,calls=self.fixture()
        self.assertIsInstance(result,dict,result)
        self.assertEqual([row["label"] for row in result["sources"]],list(builder.LABELS))
        self.assertEqual([row["label"] for row in result["reference_sources"]],list(builder.REFERENCE_LABELS))
        self.assertEqual(result["additional_history"][0]["label"],builder.GUARD_LABEL)
        self.assertNotIn("valid",result)
        self.assertFalse(result["promotion"])
        self.assertFalse(result["managed_state_changed"])
        self.assertEqual(analyzer.build.call_args.args[0],list(builder.LABELS))
        self.assertLess(calls.index("strict analysis"),calls.index("protect"))
        self.assertLess(calls.index("byte recheck"),calls.index("protect"))
        self.assertLess(calls.index("protect"),calls.index("campaign"))
        protect.assert_called_once();publish.assert_called_once()

    def test_invalid_analysis_cleanup_or_changed_fresh_evidence_never_protects(self):
        missing=self.report();missing["management"]["each_leg"].pop()
        changed=self.report();changed["matched_frozen_backend"]={"drift":True}
        for kwargs in (dict(provided=missing),dict(fresh=changed),dict(cleanup=False)):
            result,_,protect,publish,_=self.fixture(**kwargs)
            self.assertIsInstance(result,ValueError)
            protect.assert_not_called();publish.assert_not_called()

    def test_all_existing_or_partial_destination_files_are_rejected(self):
        for path in (builder.DESTINATION,builder.DESTINATION.with_suffix(".pt.json"),builder.PUBLICATION):
            path.write_bytes(b"retain")
            with self.assertRaises(ValueError):builder.new_destinations()
            self.assertEqual(path.read_bytes(),b"retain");path.unlink()

    def test_checked_copy_is_new_readonly_inode_and_original_unchanged(self):
        source,destination=self.root/"source",self.root/"copy.pt";source.write_bytes(b"tiny synthetic data")
        old=(source.read_bytes(),source.stat().st_mode,source.stat().st_ino)
        result=builder.protect_checkpoint(source,destination,dict(sha256=builder.digest(source)),lambda:None)
        self.assertTrue(result["independent_source_inode"])
        self.assertNotEqual(source.stat().st_ino,destination.stat().st_ino)
        for path in (destination,destination.with_suffix(".pt.json")):
            self.assertEqual(path.stat().st_mode & 0o777,0o444);self.assertEqual(path.stat().st_nlink,1)
        with self.assertRaises(FileExistsError):builder.protect_checkpoint(source,destination,dict(sha256=builder.digest(source)),lambda:None)
        self.assertEqual((source.read_bytes(),source.stat().st_mode,source.stat().st_ino),old)

    def test_copy_hash_or_evidence_drift_cannot_publish_model_or_metadata(self):
        source,destination=self.root/"source",self.root/"copy.pt";source.write_bytes(b"original")
        with self.assertRaisesRegex(ValueError,"Copied checkpoint SHA"):
            builder.protect_checkpoint(source,destination,dict(sha256="0"*64),lambda:None)
        self.assertFalse(destination.exists());self.assertFalse(destination.with_suffix(".pt.json").exists())
        def changed():raise ValueError("evidence changed")
        with self.assertRaisesRegex(ValueError,"evidence changed"):
            builder.protect_checkpoint(source,destination,dict(sha256=builder.digest(source)),changed)
        self.assertFalse(destination.exists())
        self.assertEqual(source.read_bytes(),b"original")

    def test_json_rejects_duplicate_keys_and_never_replaces_existing_publication(self):
        path=self.root/"bad.json";path.write_bytes(b'{"a":1,"a":2}')
        with self.assertRaisesRegex(ValueError,"Duplicate JSON"):
            builder.pinned_json(path,builder.digest(path))
        path.write_bytes(b"keep")
        with self.assertRaises(FileExistsError):builder.publish_json(path,{"new":True},lambda:None)
        self.assertEqual(path.read_bytes(),b"keep")

    def test_all_eight_prior_pairs_and_four_campaigns_are_readonly_byte_mode_guards(self):
        def record(path):
            info=path.stat()
            return dict(path=str(path),sha256=builder.digest(path),size_bytes=info.st_size,
                        mode=oct(info.st_mode & 0o777),inode=info.st_ino,device=info.st_dev)
        pairs=[]
        for index in range(8):
            pair={}
            for kind in ("checkpoint","metadata"):
                path=self.root/(str(index)+kind);path.write_bytes((str(index)+kind).encode())
                pair[kind]=record(path)
            pairs.append(pair)
        campaigns=[]
        for index in range(4):
            path=self.root/(str(index)+"campaign.json");path.write_text("{}")
            campaigns.append(record(path))
        pins=dict(protected=pairs,historical_campaigns=campaigns)
        class Evidence:
            def json(self,*args):return pins
            def file(self,path,expected):
                path=Path(path)
                builder.require(builder.digest(path)==expected,"Changed byte pin")
                return path
        original={str(path):path.read_bytes() for path in self.root.iterdir() if path.is_file()}
        self.assertIs(builder.verify_prior(Evidence()),pins)
        self.assertEqual(original,{str(path):path.read_bytes() for path in self.root.iterdir() if path.is_file()})
        path=Path(pairs[4]["checkpoint"]["path"]);old=path.read_bytes()
        path.write_bytes(b"X"*len(old))
        with self.assertRaisesRegex(ValueError,"Changed byte pin"):builder.verify_prior(Evidence())
        path.write_bytes(old)
        path.chmod((path.stat().st_mode & 0o777)^0o200)
        with self.assertRaisesRegex(ValueError,"identity/mode/size"):builder.verify_prior(Evidence())


if __name__=="__main__":unittest.main()
