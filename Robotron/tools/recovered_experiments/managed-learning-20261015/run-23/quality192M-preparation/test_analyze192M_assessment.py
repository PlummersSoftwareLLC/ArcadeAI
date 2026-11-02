"""Fixture-only checks; no real future checkpoint/receipt is opened or created."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
GAME = HERE.parents[3]
sys.path.insert(0, str(GAME))
from tools.compare_sidecar_measurements import compare_sidecars, validate_backend, JOB_FIELDS
from tools.compare_frozen_measurements import validate_receipt
from tools.sidecar_boot import _identity, load_snapshot, REQUIRED_PATHS
from tools.test_compare_sidecar_measurements import sidecar


def imported(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


guard = imported("guard192_under_test", HERE / "analyze192M_assessment.py")
math_helper = imported("guard192_math_test", HERE.parents[1] / "run-14/compare64M_composite.py")


def saved_meta(*, updates=907399, samples=2269118464, learner=132631504):
    return dict(engine_version=28, state_size=11128, single_frame_state_size=2782,
        frame_stack=4, baseline_batch_size=512, training_steps=updates,
        optimized_samples=samples, total_training_steps=updates,
        learner_frame_count=learner, frame_count=learner * 2,
        measurement_frame_count=100, last_target_update_samples=samples - 2048, epsilon=.1, expert_ratio=.1, lr_gear="climb", lr_anchor_step=0.0)


class Fixture:
    """Private fake bytes + real official validators and boot loader."""
    def __init__(self, directory):
        self.root = Path(directory)
        self.game = self.root / "Robotron"
        self.campaign = self.game / "logs/campaign"
        self.run = self.campaign / "run-23/quality192M-preparation"
        self.run.mkdir(parents=True)
        self.reference_meta = saved_meta()
        self.candidate_meta = saved_meta(updates=1100000, samples=2269118464 + (1100000-907399)*4096, learner=196629100)
        self.reference_file = self.game / "models_dqn/managed-checkpoints/fresh3-128M.pt"
        self.candidate_file = self.game / "models_dqn/managed-checkpoints/fresh3-192M.pt"
        self.write(self.reference_file, b"reference checkpoint fixture")
        self.write(self.candidate_file, b"future checkpoint fixture")
        self.source_hashes = {}
        for index in range(12):
            relative = f"sources/frozen-{index}.py"
            self.source_hashes[relative] = self.write(self.game / relative, f"fixture{index}".encode())
        self.wire = self.game / "wire-fixture.so"
        self.wire_sha = self.write(self.wire, b"synthetic wire bytes")
        self.boot = self.game / "boot"
        self.make_boot()
        self.ref_labels = ["reference-screen", "reference-confirm"]
        self.labels = ["sidecar-gpu0-192M-screen-01",
                       "sidecar-gpu0-192M-confirm-01"]
        self.ref_rows = []
        self.ref_sources = []
        for count, label in zip((74, 74), self.ref_labels):
            row = self.receipt(label, self.reference_meta, self.reference_file, count=count)
            self.ref_rows.extend(row["rows"])
            path = self.campaign / label / "receipt.json"
            self.ref_sources.append(dict(label=label, path=str(path), sha256=self.write_json(path, row)))
        # An older published leg is outside current backend but still validated
        # and included in the global game-ID denominator.
        historic = sidecar("older-history")
        old_receipt = self.campaign / "older-history/receipt.json"
        old_source = dict(label=historic["label"], path=str(old_receipt), sha256=self.write_json(old_receipt, historic))
        old_campaign = self.campaign / "old-campaign.json"
        old_sha = self.write_json(old_campaign, dict(sources=[old_source]))
        campaign = self.campaign / "confirmed64-campaign.json"
        campaign_sha = self.write_json(campaign, dict(sources=self.ref_sources,
            historical_segment=dict(path=str(old_campaign), sha256=old_sha)))
        protected = self.game / "models_dqn/managed-incumbents/fresh3-128M-confirmed.pt"
        protected_sha = self.write(protected, self.reference_file.read_bytes())
        metadata = Path(str(protected) + ".json")
        metadata_sha = self.write_json(metadata, dict(fixture=True))
        baseline = guard.summarize(self.ref_rows)
        self.plan = dict(candidate=dict(labels=self.labels, replacement_labels=["sidecar-gpu0-192M-screen-opretry-01", "sidecar-gpu0-192M-confirm-opretry-01"]), reference=dict(campaign=str(campaign),
            campaign_sha256=campaign_sha, sources=self.ref_sources, count=148,
            mean=baseline["mean"], median=baseline["median"], saved_clocks=self.reference_meta,
            checkpoint=dict(path=str(protected), sha256=protected_sha, metadata_path=str(metadata),
                            metadata_sha256=metadata_sha)),
            precommitted_decisions=dict(mean_alarm_below=.9 * baseline["mean"],
                median_alarm_below=.9 * baseline["median"], severe_mean_below=.8 * baseline["mean"], mean_at_least_each_leg=1.05 * baseline["mean"], median_at_least_each_leg=baseline["median"]),
            history=dict(expected_receipts=3, expected_unique_games=198), reporting=["Fixture repeated-look caveat"], followup_learning_trial={"action":"root judgement only"})
        self.plan_sha = self.write_json(self.run / "quality192M-assessment-plan.json", self.plan)
        self.old_lineage_sha = self.write_json(self.campaign / "run-23/fresh3-128M-checkpoint-lineage.json",
            dict(candidate=dict(sha256=protected_sha, saved_metadata=self.reference_meta,
                optimizer=dict(state_count=81, all_tensors_CPU=True, step_values=[907002.0], groups=[dict(lr=.000025,betas=[.9,.999])]))))
        self.resume_sha = self.write_json(self.run / "final-resume-checkpoint.json", dict(cpu_only=True,
            cuda_initialized=False, saved_metadata=saved_meta(updates=724620, samples=1520455680, learner=84949637)))
        gate_path = self.run / "future-gate.json"
        gate = dict(tag="fresh3-192M", target=196629023, experiment=guard.EXPERIMENT, checkpoint=str(self.candidate_file))
        gate_sha = self.write_json(gate_path, gate)
        self.lineage = dict(schema="robotron-192M-checkpoint-lineage-v1", PASS=True, proposal_only=False, root_verification=dict(status="PASS",CUDA_initialized=False),
            checks=dict(CPU_only=True, architecture_matches128M=True, saved_learner_gate_passed=True),
            candidate=dict(path=str(self.candidate_file), sha256=guard.digest(self.candidate_file),
                saved_metadata=self.candidate_meta, stat=guard.file_stat(self.candidate_file),
                optimizer=dict(state_count=81, all_tensors_CPU=True, step_values=[1099741.0], groups=[dict(lr=.000025,betas=[.9,.999])])),
            trigger_gate=dict(path=str(gate_path), sha256=gate_sha, record=gate),
            branch_provenance=dict(experiment=guard.EXPERIMENT,unchanged4096_after128M=True,compile_mode="default",exposure_counters_enabled=True),
            actual_recorded_batch_exposure=dict(since128M=dict(recorded_batch_size=4096,
                logical_updates_delta=1100000-907399,optimized_samples_delta=(1100000-907399)*4096,
                learner_frames_delta=196629100-132631504)))
        self.lineage_path = self.run / "future-lineage.json"
        self.lineage_sha = self.write_json(self.lineage_path, self.lineage)
        additional = []
        for index, stage in enumerate((96,160,160)):
            label = f"past-{stage}-{index}"
            meta = saved_meta(updates=950000, samples=2269118464+(950000-907399)*4096, learner=150000000)
            source_file = self.game / f"models_dqn/managed-checkpoints/past-{index}.pt"
            self.write(source_file, f"past fixture {index}".encode())
            past_lineage = copy.deepcopy(self.lineage)
            past_lineage.update(schema=f"robotron-{stage}M-checkpoint-lineage-v1")
            past_lineage["candidate"].update(path=str(source_file), sha256=guard.digest(source_file),
                saved_metadata=meta,stat=guard.file_stat(source_file))
            past_lineage["candidate"]["optimizer"]["step_values"] = [949900.0]
            lineage_path = self.run / f"past-{index}-lineage.json"
            lineage_sha = self.write_json(lineage_path,past_lineage)
            receipt_path=self.campaign/label/"receipt.json"
            receipt_sha=self.write_json(receipt_path,self.receipt(label,meta,source_file,count=50))
            analysis_path=self.run/f"past-{index}-analysis.json"
            src=dict(label=label,path=str(receipt_path),sha256=receipt_sha)
            analysis_sha=self.write_json(analysis_path,dict(promotion=False,management=dict(reference_rebased=False),sources=[src]))
            additional.append(dict(src,lineage_path=str(lineage_path),lineage_sha256=lineage_sha,
                analysis_path=str(analysis_path),analysis_sha256=analysis_sha))
        all_sources = self.ref_sources + [old_source] + [{k:x[k] for k in ("label","path","sha256")} for x in additional]
        final_path=self.run/"past160-final-analysis.json"
        final_sha=self.write_json(final_path,dict(schema="robotron-160M-regression-analysis-v1",promotion=False,
            management=dict(reference_rebased=False,maximum_valid_legs_reached=True),
            global_ids=dict(receipts=6,games=348,overlaps=0),sources=all_sources))
        for index, source in enumerate(additional[1:],1):
            audit_path=self.run/f"past160-{index}-audit.json"
            record=dict(pass_=True) # Python reserved keyword written explicitly below.
            record={"pass":True,"receipt_sha256":source["sha256"],
                "checkpoint_sha256":guard.digest(self.game/f"models_dqn/managed-checkpoints/past-{index}.pt"),
                "checks":dict(private_owned_processes_listener_released=True,
                    private_GPU0_context_released=True,loaded_sources_unchanged=True)}
            source.update(analysis_path=str(final_path),analysis_sha256=final_sha,
                isolation_audit_path=str(audit_path),isolation_audit_sha256=self.write_json(audit_path,record))
        self.manifest=dict(schema="robotron-192M-completed-history-manifest-v1",complete=True,
            base_campaign=str(campaign),base_campaign_sha256=campaign_sha,
            completed160_sources=additional[1:],additional_history=additional,
            final160_analysis=dict(path=str(final_path),sha256=final_sha),all_original_receipt_sources=all_sources)
        self.manifest_path=self.run/"history-manifest.final.json"
        self.manifest_sha=self.write_json(self.manifest_path,self.manifest)
        self.plan["history"]=dict(complete=True,manifest_path=str(self.manifest_path),
            manifest_sha256=self.manifest_sha,expected_receipts=6,expected_unique_games=348)
        self.plan_sha=self.write_json(self.run/"quality192M-assessment-plan.json",self.plan)
        for label in self.labels:
            self.write_json(self.campaign / label / "receipt.json",
                self.receipt(label, self.candidate_meta, self.candidate_file, count=64))
        self.analysis_iterations = []

    def write(self, path, raw):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        return hashlib.sha256(raw).hexdigest()

    def write_json(self, path, value):
        return self.write(path, (json.dumps(value, sort_keys=True) + "\n").encode())

    def make_boot(self):
        values = (bytes(1024), b'<mameconfig version="10"><system name="robotron"/></mameconfig>', b"fixture=1\n")
        files = {}
        for relative, raw in zip(REQUIRED_PATHS, values):
            files[relative] = dict(bytes=len(raw), sha256=self.write(self.boot / relative, raw))
        manifest = dict(schema="robotron-sidecar-boot-v1", created_utc="fixture", files=files,
            source_files={relative: {} for relative in REQUIRED_PATHS}, writer_checks={})
        manifest["identity"] = _identity(manifest)
        self.write_json(self.boot / "manifest.json", manifest)
        for current, _, names in os.walk(self.boot, topdown=False):
            for name in names:
                (Path(current) / name).chmod(0o444)
            Path(current).chmod(0o555)
        self.boot_manifest = load_snapshot(self.boot)

    def receipt(self, label, metadata, source, *, count=64):
        value = sidecar(label)
        rows = []
        for index in range(count):
            row = copy.deepcopy(value["rows"][index % 50])
            row.update(journal_game_id=f"{label}:{index}", client_slot=guard.SLOTS[index % 16],
                start_unix_s=100 + index, end_unix_s=120 + index, duration_s=20,
                score=1000 + index * 100, boundary_reason="wire_lives_exhausted")
            for context in (row["start_context"], row["end_context"]):
                context.update(training_steps=metadata["training_steps"], optimized_samples=metadata["optimized_samples"],
                    learner_frames=metadata["learner_frame_count"])
            rows.append(row)
        # Keep one legitimate tail after admission closes, never truncate it.
        rows[-1].update(end_unix_s=725, duration_s=725 - rows[-1]["start_unix_s"])
        value.update(rows=rows, count=count, started=count, close_ts=700, phase="finished", reason=None,
            receipt_validator="passed", ended_unix_s=730, checkpoint_metadata=copy.deepcopy(metadata),
            source_checkpoint_path=str(source), checkpoint_sha256=guard.digest(source),
            source_hashes=dict(self.source_hashes), ended_source_hashes=dict(self.source_hashes))
        value["checkpoint_metadata"]["defaulted_metadata_fields"] = []
        value["job"].update(checkpoint=str(source), cohort_s=600, timeout_s=1200, boot_assets=str(self.boot))
        value["clocks"] = {key: metadata[key] for key in guard.CORE_CLOCKS}
        value["clocks"].update(total_training_steps=metadata["training_steps"], total_optimized_samples=metadata["optimized_samples"])
        value["boundary"].update(clients=16, expected=16, acknowledged=16, requested_generation=1)
        copy_path = self.campaign / label / "checkpoint.pt"
        self.write(copy_path, source.read_bytes())
        value["checkpoint_path"] = str(copy_path)
        value["boot_assets"] = copy.deepcopy(self.boot_manifest)
        value["boot_restores"] = {str(slot): copy.deepcopy(self.boot_manifest) for slot in guard.SLOTS}
        value["socket_wait"].update(library=str(self.wire), sha256=self.wire_sha)
        for actor in value["socket_wait"]["actors"].values():
            actor["activation_count"] = 1
        value.update(guard.summarize(rows))
        return value

    def analysis(self, reference, candidate, ref_labels, cand_labels, iterations):
        self.analysis_iterations.append(iterations)
        # Exercise the exact pinned math with bounded fixture draws. Production
        # always passes10000 and has no runtime option to reduce that number.
        return math_helper.analyze_rows(reference, candidate, ref_labels, cand_labels, 10)

    def context(self):
        return patch.multiple(guard, RUN=self.run, CAMPAIGN=self.campaign, GAME=self.game,
            PLAN_SHA=self.plan_sha, REFERENCE_LINEAGE_SHA=self.old_lineage_sha,
            dependencies=lambda evidence: SimpleNamespace(validate_backend=validate_backend,
                validate_receipt=validate_receipt, compare_sidecars=compare_sidecars,
                load_snapshot=load_snapshot, analyze_rows=self.analysis, JOB_FIELDS=JOB_FIELDS))

    def cleanup_permissions(self):
        for current, _, _ in os.walk(self.boot):
            Path(current).chmod(0o700)


class Assessment192Tests(unittest.TestCase):
    def fixture(self):
        temporary = tempfile.TemporaryDirectory()
        value = Fixture(temporary.name)
        self.addCleanup(temporary.cleanup)
        self.addCleanup(value.cleanup_permissions)
        return value

    def test_import_and_help_inert_and_no_torch(self):
        with patch.object(Path, 'read_bytes', side_effect=AssertionError('opened evidence at import')):
            imported('assessment192_inert',HERE/'analyze192M_assessment.py')
        result=subprocess.run([sys.executable,str(HERE/'analyze192M_assessment.py'),'--help'],
            capture_output=True,text=True,timeout=5,env=dict(os.environ,CUDA_VISIBLE_DEVICES=''))
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('--lineage-sha256',result.stdout)
        self.assertNotIn('torch',guard.__dict__)

    def test_actual_plan_arithmetic_matches_exact_executable_gate(self):
        plan=guard.Evidence().json(HERE/'quality192M-assessment-plan.json',guard.PLAN_SHA)
        reference=plan['reference'];thresholds=plan['precommitted_decisions']
        self.assertEqual(thresholds['mean_at_least_each_leg'],1.05*reference['mean'])
        self.assertEqual(thresholds['median_at_least_each_leg'],reference['median'])
        self.assertEqual(thresholds['mean_alarm_below'],.9*reference['mean'])
        self.assertEqual(thresholds['median_alarm_below'],.9*reference['median'])
        self.assertEqual(thresholds['severe_mean_below'],.8*reference['mean'])
        self.assertTrue(thresholds['second_leg_required_regardless_first_quality'])
        self.assertEqual(plan['candidate']['target_global_learner_frames'],guard.TARGET)

    def test_fixed_second_leg_regardless_first_gain_alarm_or_count(self):
        rows=lambda x,n=64:[dict(score=x) for _ in range(n)]
        for x,n in ((100,64),(120,64),(60,64),(110,50)):
            d=guard.decisions(rows(100),{'first':rows(x,n)})
            self.assertTrue(d['confirmation_still_needed'])
            self.assertFalse(d['promotion_eligible'])
        d=guard.decisions(rows(100),{'first':rows(105,50),'second':rows(105,50)})
        self.assertTrue(d['promotion_eligible'])
        self.assertEqual(d['low_N_leg_labels'],['first','second'])
        self.assertFalse(d['third_valid_cohort_authorized'])
        with self.assertRaises(ValueError):
            guard.decisions(rows(100),{'first':rows(105),'second':rows(105),'third':rows(105)})

    def test_no_pooled_rescue_or_automatic_plateau_futility_or_knob(self):
        rows=lambda x:[dict(score=x) for _ in range(64)]
        d=guard.decisions(rows(100),{'first':rows(200),'second':rows(104.99)})
        self.assertFalse(d['promotion_eligible'])
        self.assertFalse(d['plateau_declared'])
        self.assertFalse(d['learning_knob_change_authorized'])
        self.assertEqual(d['status'],'two_fixed_legs_complete_root_assesses_evidence_no_automatic_plateau')
        self.assertFalse(d['promotion']);self.assertFalse(d['reference_rebased'])

    def test_regression_strict_same_criterion_and_severe_rules(self):
        rows=lambda x,n=64:[dict(score=x) for _ in range(n)]
        self.assertFalse(guard.decisions(rows(100),{'first':rows(90),'second':rows(90)})['repeated_same_criterion_alarm'])
        d=guard.decisions(rows(100),{'first':rows(79),'second':rows(89)})
        self.assertTrue(d['repeated_mean_alarm']);self.assertTrue(d['repeated_median_alarm'])
        self.assertEqual(d['severe_leg_labels'],['first'])
        a=rows(100,33)+rows(0,31); b=rows(80,33)+rows(120,31)
        d=guard.decisions(rows(100),{'first':a,'second':b})
        self.assertFalse(d['repeated_same_criterion_alarm'])
        self.assertFalse(d['promotion_eligible'])

    def test_pending_history_rejected_before_future_lineage_access(self):
        f=self.fixture();f.plan['history']['complete']=False
        f.plan_sha=f.write_json(f.run/'quality192M-assessment-plan.json',f.plan)
        with f.context(),self.assertRaisesRegex(ValueError,'before any192 data access'):
            guard.build(f.labels[:1],f.run/'ABSENT-future-lineage.json','0'*64)

    def test_full_two_leg_build_original_reference_history_fulltails_fixed10000(self):
        f=self.fixture()
        with f.context():report,evidence=guard.build(f.labels,f.lineage_path,f.lineage_sha)
        self.assertEqual(report['global_ids'],dict(receipts=8,games=476,overlaps=0))
        self.assertEqual(report['management']['reference']['count'],148)
        self.assertEqual([x['count'] for x in report['additional_history']],[50,50,50])
        self.assertTrue(all(not x['pooled_into_reference'] for x in report['additional_history']))
        self.assertEqual(f.analysis_iterations,[10000,10000,10000])
        self.assertEqual(len(report['official_pair_validation']),6)
        self.assertTrue(all(x['completed_tails_after_admission']==1 for x in report['full_leg_denominators']))
        self.assertFalse(report['protection']);self.assertFalse(report['promotion'])
        self.assertTrue(report['no_fabricated_measurement_receipt'])
        p=f.run.parent/'quality192M-fixture-analysis.json'
        with f.context():guard.publish(report,evidence,p)
        with f.context(),self.assertRaises(ValueError):guard.publish(report,evidence,p)
        with f.context(),self.assertRaises(ValueError):guard.publish(report,evidence,f.run.parent/'state.json')

    def test_history_cleanup_finality_and_registry_rejected(self):
        f=self.fixture()
        for modify in (lambda x:x.update(complete=False),
            lambda x:x.update(completed160_sources=x['completed160_sources'][:1]),
            lambda x:x['all_original_receipt_sources'][0].update(sha256='0'*64)):
            altered=copy.deepcopy(f.manifest);modify(altered)
            f.plan['history']['manifest_sha256']=f.write_json(f.manifest_path,altered)
            f.plan_sha=f.write_json(f.run/'quality192M-assessment-plan.json',f.plan)
            with f.context(),self.assertRaises(ValueError):guard.build(f.labels[:1],f.lineage_path,f.lineage_sha)
        f.plan['history']['manifest_sha256']=f.write_json(f.manifest_path,f.manifest)
        source=f.manifest['completed160_sources'][0];audit_path=Path(source['isolation_audit_path'])
        audit=json.loads(audit_path.read_bytes());audit['checks']['private_GPU0_context_released']=False
        source['isolation_audit_sha256']=f.write_json(audit_path,audit)
        f.plan['history']['manifest_sha256']=f.write_json(f.manifest_path,f.manifest)
        f.plan_sha=f.write_json(f.run/'quality192M-assessment-plan.json',f.plan)
        with f.context(),self.assertRaisesRegex(ValueError,'positive completed160 audit'):
            guard.build(f.labels[:1],f.lineage_path,f.lineage_sha)

    def test_final_root_lineage_exact_gate_branch_recipe_and4096_math(self):
        f=self.fixture()
        for modify in (lambda x:x.update(proposal_only=True),
            lambda x:x['root_verification'].update(status='PENDING'),
            lambda x:x['root_verification'].update(CUDA_initialized=True),
            lambda x:x['branch_provenance'].update(compile_mode='max-autotune'),
            lambda x:x['branch_provenance'].update(unchanged4096_after128M=False),
            lambda x:x['candidate']['saved_metadata'].update(learner_frame_count=196629022),
            lambda x:x['candidate']['saved_metadata'].update(optimized_samples=x['candidate']['saved_metadata']['optimized_samples']+1),
            lambda x:x['trigger_gate']['record'].update(target=164629023),
            lambda x:x['actual_recorded_batch_exposure']['since128M'].update(recorded_batch_size=2048)):
            row=copy.deepcopy(f.lineage);modify(row)
            with self.assertRaises(ValueError):guard.lineage_identity(row,f.candidate_file,f.reference_meta)

    def test_runtime_tail_numeric_backend_and_checkpoint_drift_fail_closed(self):
        f=self.fixture();p=f.campaign/f.labels[0]/'receipt.json';original=json.loads(p.read_bytes())
        for mutate in (lambda x:x.update(pending=1),
            lambda x:x['actor_timeout_logs'].update({'4096':1}),
            lambda x:x['rows'][-1].update(boundary_reason='life_lost'),
            lambda x:x['runtime'].update(gpu_name='different GPU'),
            lambda x:x['numeric_policy'].update(suppress_errors=True),
            lambda x:x['checkpoint_metadata'].update(training_steps=f.candidate_meta['training_steps']+1)):
            row=copy.deepcopy(original);mutate(row);f.write_json(p,row)
            with f.context(),self.assertRaises(ValueError):guard.build(f.labels[:1],f.lineage_path,f.lineage_sha)

    def test_older_guard_global_id_collision_not_removed_or_pooled(self):
        f=self.fixture();p=f.campaign/f.labels[0]/'receipt.json';row=json.loads(p.read_bytes())
        row['rows'][0]['journal_game_id']='past-160-2:0';f.write_json(p,row)
        with f.context(),self.assertRaisesRegex(ValueError,'global game ID overlap'):
            guard.build(f.labels[:1],f.lineage_path,f.lineage_sha)

    def test_operational_replacement_requires_root_invalid_original_fixed_slot_and_no_outcome_selection(self):
        f=self.fixture();sha=f.lineage['candidate']['sha256'];original=f.campaign/f.labels[0]/'receipt.json'
        invalid=json.loads(original.read_bytes());invalid.update(valid=False,reason='actual operational failure')
        invalid_sha=f.write_json(original,invalid)
        label=f.plan['candidate']['replacement_labels'][0]
        replacement=f.receipt(label,f.candidate_meta,f.candidate_file,count=64);replacement.update(start_ts=100,started_unix_s=95)
        f.write_json(f.campaign/label/'receipt.json',replacement)
        cert=dict(schema='root-corrected-operational-replacement-v1',assigned_leg=1,root_authorized=True,
            outcome_or_count_based_selection=False,recorded_before_launch=True,checkpoint_sha256=sha,
            cause='runtime',corrective_action='corrected independently verified operational fault',
            rationale='root records causal operational reason, never quality/count selection',
            original_label=f.labels[0],replacement_label=label,recorded_unix_s=90,
            invalid_original=dict(path=str(original),sha256=invalid_sha))
        cp=f.run/'root-authorization.json';cs=f.write_json(cp,cert)
        with f.context():r,_=guard.build([label],f.lineage_path,f.lineage_sha,[(cp,cs)])
        self.assertEqual(r['assigned_legs'][0]['selected_label'],label)
        self.assertTrue(r['management']['confirmation_still_needed'])
        for mutate in (lambda x:x.update(outcome_or_count_based_selection=True),
            lambda x:x.update(recorded_before_launch=False),lambda x:x.update(recorded_unix_s=97),lambda x:x.update(recorded_unix_s=101),
            lambda x:x.update(cause='low_game_count'),lambda x:x.update(assigned_leg=2)):
            row=copy.deepcopy(cert);mutate(row);new=f.write_json(cp,row)
            with f.context(),self.assertRaises(ValueError):guard.build([label],f.lineage_path,f.lineage_sha,[(cp,new)])
        for stamp in (None,True,float('inf')):
            row=copy.deepcopy(replacement)
            if stamp is None:row.pop('started_unix_s')
            else:row['started_unix_s']=stamp
            f.write_json(f.campaign/label/'receipt.json',row)
            cs=f.write_json(cp,cert)
            with f.context(),self.assertRaises(ValueError):
                guard.build([label],f.lineage_path,f.lineage_sha,[(cp,cs)])
        with f.context(),self.assertRaisesRegex(ValueError,'authorization'):
            guard.build([label],f.lineage_path,f.lineage_sha)
        with self.assertRaises(ValueError):guard.assigned_labels([f.labels[1]],f.plan,[],guard.Evidence(),sha)
        with self.assertRaises(ValueError):guard.assigned_labels(f.labels+[label],f.plan,[],guard.Evidence(),sha)

    def test_single_snapshot_prepublish_recheck_and_exclusive_output(self):
        f=self.fixture()
        with f.context():report,evidence=guard.build(f.labels[:1],f.lineage_path,f.lineage_sha)
        p=f.campaign/f.labels[0]/'receipt.json';raw=p.read_bytes();p.write_bytes(raw+b' ')
        out=f.run.parent/'quality192M-no-output-analysis.json'
        with f.context(),self.assertRaisesRegex(ValueError,'changed before publication'):guard.publish(report,evidence,out)
        self.assertFalse(out.exists());p.write_bytes(raw)
        f.boot.chmod(0o755)
        with f.context(),self.assertRaisesRegex(ValueError,'immutable'):guard.publish(report,evidence,out)
        self.assertFalse(out.exists())

    def test_actual_deferred_validator_modules_and_duplicate_json_rejection(self):
        e=guard.Evidence();before=set(sys.modules);tools=guard.dependencies(e)
        self.assertEqual(tools.JOB_FIELDS,JOB_FIELDS)
        self.assertFalse(any(n=='torch' or n.startswith('torch.') for n in set(sys.modules)-before))
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bad.json'
            for raw in (b'{"a":1,"a":2}',b'{"a":NaN}'):
                p.write_bytes(raw)
                with self.assertRaises(ValueError):guard.Evidence().json(p)

if __name__=='__main__':unittest.main()
