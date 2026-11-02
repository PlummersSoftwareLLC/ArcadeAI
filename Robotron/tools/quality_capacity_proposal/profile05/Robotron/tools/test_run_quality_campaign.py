"""CPU-only campaign tests: no emulator, GPU, socket, service, or learning changes."""
import contextlib
import copy
import io
import json
import os
from pathlib import Path
import signal
import tempfile
import unittest
from unittest.mock import patch

from . import run_quality_campaign as campaign
from .test_compare_sidecar_measurements import sidecar, add_confirmed_fixture, write_terminal_fixture


class CampaignTests(unittest.TestCase):
    actor_count = 16

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        reference, candidate = self.root / "reference.pt", self.root / "candidate.pt"
        reference.write_bytes(b"reference checkpoint")
        candidate.write_bytes(b"candidate checkpoint")
        self.boot = dict(identity="boot", files={"nvram": {"sha256": "test"}})
        self.boot_patch = patch.object(campaign.evaluator.boot_module(), "load_snapshot", return_value=self.boot)
        self.boot_patch.start()
        self.addCleanup(self.boot_patch.stop)
        self.config = campaign.Campaign(reference, candidate, self.root / "campaign",
            mame=Path("/bin/true"), rompath=self.root, boot_assets=self.root / "boot", actors=self.actor_count)
        self.plan = campaign.make_plan(self.config)

    def write_receipt(self, spec, scores=200, *, nested=True, count=50):
        if spec["job"]["actors"] == 32:
            from .test_eval_capacity import receipt32
            data = receipt32(spec["job"]["label"])
        else:
            data = sidecar(spec["job"]["label"])
        data["job"] = copy.deepcopy(spec["job"])
        data["source_hashes"] = dict(self.plan["evaluator_source_hashes"])
        data["ended_source_hashes"] = dict(data["source_hashes"])
        data["boot_assets"] = copy.deepcopy(self.boot)
        data["checkpoint_sha256"] = self.plan["checkpoints"][spec["role"]]["sha256"]
        path = Path(spec["receipt_path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        source = getattr(self.config, spec["role"])
        checkpoint = path.parent / "checkpoint.pt"
        checkpoint.write_bytes(source.read_bytes())
        data["checkpoint_path"] = str(checkpoint)
        rows = data["rows"]
        while len(rows) < count:
            row = copy.deepcopy(rows[len(rows) % 50])
            row["journal_game_id"] = f"{data['label']}:{len(rows)}"
            rows.append(row)
        del rows[count:]
        for index, row in enumerate(rows):
            row["score"] = scores[index] if isinstance(scores, list) else scores
        data["started"] = data["count"] = len(rows)
        data["boundary"]["acknowledged_client_ids"] = list(range(spec["job"]["actors"]))
        data["socket_wait"].update(port=spec["job"]["port"], wait_us=spec["job"]["wait_us"])
        add_confirmed_fixture(data)
        if nested:
            data["cohort"] = dict(rows=data.pop("rows"), pending=0, abandoned=0,
                started=len(rows), count=len(rows), valid=True, complete=True, closed=True,
                started_ids=[row["journal_game_id"] for row in rows])
        write_terminal_fixture(data, path.parent)
        path.write_text(json.dumps(data))
        return data

    def records(self):
        return [dict(index=spec["index"], returncode=0) for spec in self.plan["legs"]]

    def rewrite_clients(self, spec, data, mapping):
        """Keep original journals/terminal links coherent when changing identity."""
        rows = data.get('rows', data.get('cohort', {}).get('rows'))
        for index, row in enumerate(rows):
            row['client_id'] = mapping(index, row)
            data['terminal_successors'][row['journal_game_id']]['client_id'] = row['client_id']
        path = Path(spec['receipt_path'])
        write_terminal_fixture(data, path.parent)
        path.write_text(json.dumps(data))

    def test_distinct_permuted_client_ids_are_valid(self):
        for spec in self.plan['legs']:
            data = self.write_receipt(spec, 200 if spec['role']=='reference' else 220)
            data['boundary']['acknowledged_client_ids'] = [1000+i for i in range(self.actor_count)]
            self.rewrite_clients(spec, data,
                lambda index, row: 1000+self.actor_count-1-(row['client_slot']-4096))
        self.assertTrue(self.assess()['qualified_improvement'])

    def test_aliasing_two_slots_to_one_client_is_invalid(self):
        self.fill()
        spec = self.plan['legs'][1]
        data = json.loads(Path(spec['receipt_path']).read_text())
        self.rewrite_clients(spec, data,
            lambda index, row: 0 if row['client_slot']==4097 else row['client_slot']-4096)
        report = self.assess()
        self.assertEqual(report['outcome'], 'invalid')
        self.assertIn('Actor/client mapping', report['legs'][1]['error'])

    def test_remapping_one_slot_mid_cohort_is_invalid(self):
        self.fill()
        spec = self.plan['legs'][1]
        data = json.loads(Path(spec['receipt_path']).read_text())
        self.rewrite_clients(spec, data,
            lambda index, row: 999 if index==0 else row['client_slot']-4096)
        report = self.assess()
        self.assertEqual(report['outcome'], 'invalid')
        self.assertIn('Actor/client mapping', report['legs'][1]['error'])

    def test_duplicate_or_foreign_startup_clients_are_invalid(self):
        self.fill()
        spec = self.plan['legs'][1]
        path = Path(spec['receipt_path'])
        before = path.read_bytes()
        for clients in (list(range(self.actor_count))+[0],
                        list(range(self.actor_count-1))+[0],
                        list(range(self.actor_count-1))+[999]):
            with self.subTest(clients=clients):
                data = json.loads(before)
                data['boundary']['acknowledged_client_ids'] = clients
                path.write_text(json.dumps(data))
                self.assertEqual(self.assess()['outcome'], 'invalid')

    def test_boolean_or_negative_client_ids_are_invalid(self):
        self.fill()
        spec = self.plan['legs'][1]
        path = Path(spec['receipt_path'])
        before = path.read_bytes()
        for client in (True, -1):
            with self.subTest(client=client):
                data = json.loads(before)
                self.rewrite_clients(spec, data,
                    lambda index, row: client if index==0 else row['client_slot']-4096)
                self.assertEqual(self.assess()['outcome'], 'invalid')

    def assess(self):
        return campaign.assess_campaign(self.plan, self.records())

    def fill(self, scores=(200, 220, 200, 220)):
        return [self.write_receipt(spec, score) for spec, score in zip(self.plan["legs"], scores)]

    def test_long_profile_is_identical_for_all_four_legs_and_preserves_gates(self):
        config = campaign.Campaign(self.config.reference, self.config.candidate,
            self.config.directory, mame=self.config.mame, rompath=self.config.rompath,
            boot_assets=self.config.boot_assets, cohort_s=3600, timeout_s=6000, actors=self.actor_count)
        plan = campaign.make_plan(config)
        self.assertEqual([x['role'] for x in plan['legs']], ['reference','candidate','reference','candidate'])
        self.assertTrue(all(x['job']['cohort_s']==3600 and x['job']['timeout_s']==6000 for x in plan['legs']))
        self.assertEqual(plan['precommit']['candidate_gate'], self.plan['precommit']['candidate_gate'])
        self.assertEqual(plan['precommit']['min_full_games_per_leg'], 50)
        self.assertFalse(plan['precommit']['admission_extensions'])
        self.assertTrue(plan['precommit']['include_full_completion_tail'])
        self.assertFalse(config.directory.exists())

    def test_plan_has_fixed_defaults_new_jobs_hashes_and_no_side_effects(self):
        self.assertFalse(self.config.directory.exists())
        self.assertEqual([leg["role"] for leg in self.plan["legs"]], list(campaign.ORDER))
        self.assertEqual(len({leg["job"]["directory"] for leg in self.plan["legs"]}), 4)
        self.assertFalse(self.plan["precommit"]["historical_or_interrupted_receipts_used"])
        self.assertTrue(self.plan["precommit"]["include_full_completion_tail"])
        for leg in self.plan["legs"]:
            self.assertEqual(leg["job"]["cohort_s"], 1200)
            self.assertEqual(leg["job"]["timeout_s"], 2400)
            self.assertEqual(leg["job"]["gpu_uuid"], campaign.GPU0_UUID)
            self.assertEqual(leg["job"]["inference_backend"], "inductor")
            self.assertEqual(leg["job"]["actor_slots"], list(range(4096, 4096+self.actor_count)))
            self.assertIn("--launch", leg["command"])
            self.assertEqual(leg["command"][1:4], ["-Xgil=0", "-B", "-u"])
        with patch.object(campaign, "run_campaign") as run, contextlib.redirect_stdout(io.StringIO()):
            result = campaign.main(["--reference-checkpoint", str(self.config.reference),
                "--candidate-checkpoint", str(self.config.candidate), "--output-dir", str(self.config.directory),
                "--boot-assets", str(self.config.boot_assets), "--mame", "/bin/true", "--rompath", str(self.root)])
        self.assertEqual(result, 0)
        run.assert_not_called()
        self.assertFalse(self.config.directory.exists())

    def test_nested_full_tail_unequal_counts_are_all_used_and_receipts_unchanged(self):
        counts = (50, 57, 66, 51)
        for spec, count in zip(self.plan["legs"], counts):
            self.write_receipt(spec, 200 if spec["role"] == "reference" else 220, count=count)
        before = [Path(spec["receipt_path"]).read_bytes() for spec in self.plan["legs"]]
        report = self.assess()
        self.assertEqual(report["outcome"], "qualified_improvement")
        self.assertEqual(report["pooled_reference"]["count"], 116)
        self.assertEqual([len(leg["included_game_ids"]) for leg in report["legs"]], list(counts))
        self.assertGreater(report["legs"][1]["summary"]["observed_wall_span_s"], 60)
        self.assertEqual(before, [Path(spec["receipt_path"]).read_bytes() for spec in self.plan["legs"]])

    def test_each_candidate_must_beat_pooled_reference_not_candidate_pool(self):
        self.fill((100, 300, 300, 200))
        report = self.assess()
        self.assertEqual(report["pooled_reference"]["mean"], 200)
        self.assertEqual(report["outcome"], "not_improved")
        self.assertFalse(report["candidate_checks"][1]["mean_pass"])
        self.assertFalse(report["qualified_improvement"])

    def test_candidate_median_gate_and_exact_five_percent_boundary(self):
        self.fill((200, 210, 200, [150]*26 + [400]*24))
        report = self.assess()
        self.assertTrue(report["candidate_checks"][0]["mean_pass"])
        self.assertTrue(report["candidate_checks"][1]["mean_pass"])
        self.assertFalse(report["candidate_checks"][1]["median_pass"])
        self.assertEqual(report["outcome"], "not_improved")

    def test_missing_and_invalid_are_distinct_and_never_qualify(self):
        self.write_receipt(self.plan["legs"][0])
        self.assertEqual(self.assess()["outcome"], "incomplete")
        data = self.write_receipt(self.plan["legs"][0])
        data["complete"] = False
        Path(self.plan["legs"][0]["receipt_path"]).write_text(json.dumps(data))
        self.assertEqual(self.assess()["outcome"], "incomplete")
        self.fill()
        for mutate in (
            lambda d: d.update(server_error="disconnect"),
            lambda d: d.update(pending=1),
            lambda d: d.update(valid=False),
            lambda d: d["actor_timeout_logs"].update({"4096": 1}),
            lambda d: d["runtime"].update(torch="changed"),
            lambda d: d["job"].update(gpu_uuid="GPU-other"),
            lambda d: d.update(checkpoint_sha256="0"*64),
            lambda d: d["cohort"]["rows"][0].update(client_slot=123),
        ):
            with self.subTest(mutation=mutate):
                data = self.write_receipt(self.plan["legs"][1], 220)
                mutate(data)
                Path(self.plan["legs"][1]["receipt_path"]).write_text(json.dumps(data))
                report = self.assess()
                self.assertEqual(report["outcome"], "invalid")
                self.assertFalse(report["qualified_improvement"])

    def test_zero_reference_mean_never_qualifies_a_relative_gain(self):
        self.fill((0, 0, 0, 0))
        self.assertEqual(self.assess()["outcome"], "invalid")
        self.assertFalse(self.assess()["qualified_improvement"])

    def test_fewer_than_fifty_missing_slots_duplicate_ids_and_checkpoint_changes_rejected(self):
        self.fill()
        spec = self.plan["legs"][1]
        self.write_receipt(spec, 220, count=49)
        self.assertEqual(self.assess()["outcome"], "invalid")
        data = self.write_receipt(spec, 220)
        for row in data["cohort"]["rows"]:
            if row["client_slot"] == 4111:
                row["client_slot"] = 4110
        Path(spec["receipt_path"]).write_text(json.dumps(data))
        self.assertEqual(self.assess()["outcome"], "invalid")
        data = self.write_receipt(spec, 220)
        duplicate = json.loads(Path(self.plan["legs"][0]["receipt_path"]).read_text())["cohort"]["rows"][0]["journal_game_id"]
        data["cohort"]["rows"][0]["journal_game_id"] = duplicate
        data["cohort"]["started_ids"][0] = duplicate
        Path(spec["receipt_path"]).write_text(json.dumps(data))
        self.assertEqual(self.assess()["outcome"], "invalid")
        data = self.write_receipt(spec, 220)
        Path(data["checkpoint_path"]).write_bytes(b"mutated")
        self.assertEqual(self.assess()["outcome"], "invalid")

    def test_snapshots_remain_frozen_and_changes_after_precommit_fail_closed(self):
        self.config.directory.mkdir()
        campaign.snapshot_checkpoints(self.plan)
        snapshot = Path(self.plan["checkpoints"]["reference"]["snapshot"])
        original = snapshot.read_bytes()
        self.config.reference.write_bytes(b"later source change")
        self.assertEqual(snapshot.read_bytes(), original)
        self.assertEqual(snapshot.stat().st_mode & 0o222, 0)
        campaign.check_precommit(self.plan)
        snapshot.chmod(0o644)
        snapshot.write_bytes(b"changed snapshot")
        with self.assertRaisesRegex(ValueError, "snapshot changed"):
            campaign.check_precommit(self.plan)
        with self.assertRaisesRegex(ValueError, "new"):
            campaign.make_plan(self.config)

    def fake_popen(self, calls, *, failure=False, interrupt=False):
        test = self
        class Process:
            pid = 123456
            returncode = None
            signals = []
            def poll(self):
                return self.returncode
            def send_signal(self, signum):
                self.signals.append(signum)
            def wait(self, timeout=None):
                if interrupt:
                    os.kill(os.getpid(), signal.SIGTERM)
                self.returncode = 1 if failure or interrupt else 0
                return self.returncode
        def popen(arguments, **kwargs):
            spec = self.plan["legs"][len(calls)]
            self.assertEqual(arguments, spec["command"])
            self.assertTrue(kwargs["start_new_session"])
            process = Process()
            process.signals = []
            calls.append(process)
            if not failure and not interrupt:
                test.write_receipt(spec, 200 if spec["role"] == "reference" else 220)
            return process
        return popen

    def test_complete_runner_writes_plan_before_launch_progress_logs_and_summary(self):
        calls = []
        create = self.fake_popen(calls)
        def observed_popen(*args, **kwargs):
            plan_path = self.config.directory / "plan.json"
            self.assertTrue(plan_path.is_file())
            self.assertEqual(plan_path.stat().st_mode & 0o222, 0)
            self.assertTrue((self.config.directory / "checkpoints/reference.pt").is_file())
            return create(*args, **kwargs)
        with contextlib.redirect_stdout(io.StringIO()):
            result = campaign.run_campaign(self.config, popen=observed_popen)
        self.assertEqual(result, 0)
        self.assertEqual(len(calls), 4)
        report = json.loads((self.config.directory / "summary.json").read_text())
        status = json.loads((self.config.directory / "status.json").read_text())
        self.assertEqual(report["outcome"], "qualified_improvement")
        self.assertEqual(status["state"], "finished")
        self.assertEqual(status["plan_sha256"], campaign.evaluator.sha256(self.config.directory / "plan.json"))
        self.assertEqual(len(list(self.config.directory.glob("*.console.log"))), 4)
        self.assertFalse((self.config.directory / "status.json.tmp").exists())

    def test_subprocess_failure_stops_without_retry_or_extension(self):
        calls = []
        with contextlib.redirect_stdout(io.StringIO()):
            result = campaign.run_campaign(self.config, popen=self.fake_popen(calls, failure=True))
        self.assertEqual(result, 1)
        self.assertEqual(len(calls), 1)
        report = json.loads((self.config.directory / "summary.json").read_text())
        self.assertEqual(report["outcome"], "incomplete")
        self.assertFalse(report["qualified_improvement"])

    def test_sigterm_forwards_sigint_only_to_owned_child_and_waits(self):
        calls = []
        original = signal.getsignal(signal.SIGTERM)
        with contextlib.redirect_stdout(io.StringIO()):
            result = campaign.run_campaign(self.config, popen=self.fake_popen(calls, interrupt=True))
        self.assertEqual(result, 1)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].signals, [signal.SIGINT])
        self.assertEqual(signal.getsignal(signal.SIGTERM), original)
        report = json.loads((self.config.directory / "summary.json").read_text())
        self.assertEqual(report["outcome"], "incomplete")
        self.assertEqual(report["stop_signal"], signal.SIGTERM)


class Campaign32Tests(CampaignTests):
    """Run the same full R/C/R/C and rejection cases with all32 slots."""
    actor_count = 32

    def test_all_four_native_commands_explicitly_request32_actors(self):
        self.assertEqual(self.plan['precommit']['all_actor_slots'], list(range(4096,4128)))
        for spec in self.plan['legs']:
            argv = spec['command']
            self.assertEqual(argv[argv.index('--actors')+1], '32')
            self.assertEqual(spec['job']['actors'], 32)
            self.assertEqual(spec['job']['inference_max_batch_size'], 16)
        self.assertFalse(self.config.directory.exists())

    def test_cli32_plan_does_not_launch_or_create_outputs(self):
        stream = io.StringIO()
        with patch.object(campaign, 'run_campaign') as launch, contextlib.redirect_stdout(stream):
            code = campaign.main(['--reference-checkpoint',str(self.config.reference),
                '--candidate-checkpoint',str(self.config.candidate),'--output-dir',str(self.config.directory),
                '--boot-assets',str(self.config.boot_assets),'--mame','/bin/true','--rompath',str(self.root),
                '--actors','32'])
        self.assertEqual(code,0)
        self.assertTrue(all(x['job']['actors']==32 for x in json.loads(stream.getvalue())['legs']))
        launch.assert_not_called()
        self.assertFalse(self.config.directory.exists())

    def test_unsupported_actor_counts_cannot_change_a_campaign(self):
        from dataclasses import replace
        for count in (0,1,15,17,31,33,64,True,16.0,32.0,'32',None):
            with self.subTest(count=count), self.assertRaises(ValueError):
                campaign.make_plan(replace(self.config,actors=count))

    def test_missing_highest_slot_and_wrong_precommit_never_qualify(self):
        self.fill()
        spec = self.plan['legs'][3]
        data = self.write_receipt(spec,220)
        for row in data['cohort']['rows']:
            if row['client_slot']==4127:
                row['client_slot']=4126
        Path(spec['receipt_path']).write_text(json.dumps(data))
        self.assertEqual(self.assess()['outcome'],'invalid')
        self.fill()
        self.plan['precommit']['all_actor_slots']=list(range(4096,4112))
        self.assertEqual(self.assess()['outcome'],'invalid')


if __name__ == "__main__":
    unittest.main()
