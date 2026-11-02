"""UNEXECUTED proposal tests. Future runs use stdlib and private journals only.

No source application, trainer construction, sockets, Torch, MAME or live data.
The classifier checks execute its actual AST slice, not a rewritten classifier;
they do not certify the complete socket/HTTP/measurement lifecycle.
"""
import ast
import contextlib
import copy
import difflib
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch


HERE = Path(__file__).resolve().parent
GAME = HERE.parents[2]
PINS = {
    "socket_server.py": "8fe556f7507547a97839072bbcecc98384c2b395c8ae789ac8ee062f55bca721",
    "game_journal.py": "27c6143851aff73dd355db89e1ffaa65d90d215b91921406050387be5ad69029",
    "run_frozen_sidecar.py": "1b3610c23c0fc94075796259195840471f60575166223bc3a3da51484e863a2b",
    "run_quality_campaign.py": "2485394451ab9bbce5c0c55fa50f07fcbab793380c5f3b84a594c051e7874e63",
}
BASE_PATHS = {name: "Scripts/dqn/" + name for name in ("socket_server.py", "game_journal.py")}
BASE_PATHS.update({name: "tools/" + name for name in ("run_frozen_sidecar.py", "run_quality_campaign.py")})


def sources(name):
    raw = (GAME / BASE_PATHS[name]).read_bytes()
    if hashlib.sha256(raw).hexdigest() != PINS[name]:
        raise RuntimeError("Pinned source changed; review/rebase before any test: " + name)
    candidate = (HERE / name.replace(".py", "_candidate.py")).read_text()
    return raw.decode(), candidate


def method(tree, name):
    return next(node for node in ast.walk(tree)
                if isinstance(node, ast.FunctionDef) and node.name == name)


def classifier(source):
    """Run only the original classifier region from actual handle_client."""
    tree = ast.parse(source)
    handle = method(tree, "handle_client")
    loop = next(node for node in ast.walk(handle)
                if isinstance(node, ast.While) and isinstance(node.test, ast.BoolOp)
                and any(isinstance(term, ast.Attribute) and term.attr == "running"
                        for term in node.test.values))
    begin = next(index for index, node in enumerate(loop.body)
                 if isinstance(node, ast.Assign)
                 and any(isinstance(target, ast.Name) and target.id == "_verdict"
                         for target in node.targets))
    end = next(index for index, node in enumerate(loop.body[begin:], begin)
               if isinstance(node, ast.If) and isinstance(node.test, ast.Name)
               and node.test.id == "_wrap_note")
    wrapper = ast.parse("def classify(self, cid, frame):\n"
                        "    return dict(verdict=_verdict, new_game=_is_new_game,\n"
                        "                boundary_inputs=locals().get('_boundary_inputs'))\n").body[0]
    wrapper.body = copy.deepcopy(loop.body[begin:end]) + wrapper.body
    helper = copy.deepcopy(method(tree, "_continuous_play_score_dip"))
    module = ast.fix_missing_locations(ast.Module(body=[helper, wrapper], type_ignores=[]))
    config = SimpleNamespace(score_new_game_max=100000, score_wrap_modulus=100000000,
                             score_torn_read_tolerance=100000,
                             max_plausible_score_per_level=35000)
    namespace = dict(RL_CONFIG=config, _MAX_SCORE_JUMP=250000,
                     time=SimpleNamespace(time=lambda: 1000.0))
    exec(compile(module, "<private-actual-classifier-region>", "exec"), namespace)
    return namespace["classify"]


def journal_module(source):
    module = ModuleType("private_game_journal")
    exec(compile(source, "<private-game-journal>", "exec"), module.__dict__)
    return module


def frame(score=0, wave=1, alive=True, done=False, start=False, lives=3):
    return SimpleNamespace(game_score=score, level_number=wave, player_alive=alive,
                           done=done, start_pressed=start, lives=lives)


def server(enabled=False, **changes):
    client = dict(raw_score_prev=9800, raw_wave_prev=2, frames=99,
                  player_alive=True, last_start_frame=10, game_uid=96)
    client.update(changes)
    return SimpleNamespace(client_states={7: client}, client_lock=contextlib.nullcontext(),
                           _unwrap_stash={}, _game_uid_seq=96,
                           game_boundary_diagnostics=enabled)


def accept(function, owner, current):
    result = function(owner, 7, current)
    if result["verdict"] == "accept":
        client = owner.client_states[7]
        client["frames"] += 1
        client["player_alive"] = bool(current.player_alive)
    return result


def without_evidence(value):
    if isinstance(value, dict):
        return {key: without_evidence(item) for key, item in value.items()
                if key not in {"game_boundary_diagnostics", "_boundary_previous_accepted",
                               "first_play_not_wave_1_inputs"}}
    if isinstance(value, list):
        return [without_evidence(item) for item in value]
    return value


class BoundaryDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.original_socket, self.candidate_socket = sources("socket_server.py")
        self.original_journal, self.candidate_journal = sources("game_journal.py")

    def test_source_pins_exact_patch_and_unchanged_noninstrumented_methods(self):
        expected = ""
        for name in PINS:
            before, after = sources(name)
            expected += "".join(difflib.unified_diff(
                before.splitlines(keepends=True), after.splitlines(keepends=True),
                fromfile="a/Robotron/" + BASE_PATHS[name],
                tofile="b/Robotron/" + BASE_PATHS[name]))
        self.assertEqual((HERE / "unapplied.patch").read_text(), expected)
        for before, after, allowed in (
            (self.original_socket, self.candidate_socket,
             {"__init__", "handle_client", "_journal_observe"}),
            (self.original_journal, self.candidate_journal, {"_begin", "observe"}),
        ):
            left = ast.parse(before); right = ast.parse(after)
            remaining = [ast.dump(node) for node in ast.walk(right)
                         if isinstance(node, ast.FunctionDef)]
            for node in ast.walk(left):
                if isinstance(node, ast.FunctionDef) and node.name not in allowed:
                    self.assertIn(ast.dump(node), remaining, node.name)
                    remaining.remove(ast.dump(node))

    def test_optin_is_exact_startup_value_and_private_inference_only(self):
        # Select the SocketServer constructor, rather than an earlier helper.
        init = next(method(node, "__init__") for node in ast.parse(self.candidate_socket).body
                    if isinstance(node, ast.ClassDef) and node.name == "SocketServer")
        assignment = next(node for node in init.body if isinstance(node, ast.Assign)
                          and any(isinstance(target, ast.Attribute)
                                  and target.attr == "game_boundary_diagnostics"
                                  for target in node.targets))
        expression = compile(ast.Expression(assignment.value), "<private-optin>", "eval")
        for replay in (True, False):
            for value in ("", "0", "true", "yes", "1"):
                enabled = eval(expression, dict(self=SimpleNamespace(replay_enabled=replay),
                               os=SimpleNamespace(getenv=lambda *_: value)))
                self.assertEqual(enabled, not replay and value == "1")

    def test_actual_classifier_parity_with_diagnostics_off_and_on(self):
        baseline = classifier(self.original_socket)
        candidate = classifier(self.candidate_socket)
        cases = [
            (dict(), frame(9900, 2)),
            (dict(raw_score_prev=9900), frame(0, 2)),
            (dict(raw_score_prev=9900, last_start_frame=-1000), frame(0, 2)),
            (dict(raw_score_prev=9900), frame(9850, 2)),
            (dict(raw_score_prev=9900), frame(500000, 2)),
            (dict(raw_score_prev=2000000), frame(200000, 2)),
            (dict(raw_score_prev=99999950, last_start_frame=-1000), frame(50, 2)),
            (dict(raw_wave_prev=255, raw_score_prev=100, last_start_frame=-1000), frame(150, 0)),
            (dict(raw_score_prev=None, raw_wave_prev=None), frame(7000, 3)),
            (dict(raw_score_prev=9900), frame(0, 2, start=True)),
        ]
        for initial, wire in cases:
            for enabled in (False, True):
                with self.subTest(initial=initial, wire=vars(wire), enabled=enabled):
                    left, right = server(**initial), server(enabled, **initial)
                    lf, rf = copy.deepcopy(wire), copy.deepcopy(wire)
                    a, b = accept(baseline, left, lf), accept(candidate, right, rf)
                    self.assertEqual((a["verdict"], a["new_game"]), (b["verdict"], b["new_game"]))
                    self.assertEqual(vars(lf), vars(rf))
                    self.assertEqual(left._game_uid_seq, right._game_uid_seq)
                    self.assertEqual(without_evidence(left.client_states), without_evidence(right.client_states))
                    if not enabled:
                        self.assertIsNone(b["boundary_inputs"])
                        self.assertNotIn("_boundary_previous_accepted", right.client_states[7])

    def test_c2_like_reset_records_previous_wire_rejected_frame_and_start_timing(self):
        owner, function = server(True), classifier(self.candidate_socket)
        accept(function, owner, frame(9900, 2))
        rejected = accept(function, owner, frame(500000, 2))
        self.assertEqual(rejected["verdict"], "crash-jump")
        self.assertIsNone(rejected["boundary_inputs"])
        result = accept(function, owner, frame(0, 2, start=True))
        evidence = journal_module(self.candidate_journal)._boundary_start_evidence(
            result["boundary_inputs"], "score_reset")
        self.assertTrue(result["new_game"])
        self.assertEqual(owner.client_states[7]["game_uid"], 97)
        self.assertEqual(evidence["previous_accepted_wire"]["raw_score"], 9900)
        self.assertEqual(evidence["current_wire"]["raw_score"], 0)
        self.assertEqual(evidence["current_wire"]["raw_wave"], 2)
        self.assertTrue(evidence["current_wire"]["player_alive"])
        self.assertFalse(evidence["current_wire"]["done"])
        self.assertTrue(evidence["current_wire"]["start_pressed"])
        self.assertEqual((evidence["last_start_frame_before"], evidence["last_start_frame_after"]), (10, 100))
        self.assertEqual(evidence["current_wire"]["accepted_frames_before"], 100)
        self.assertTrue(evidence["recent_start"])
        self.assertEqual(evidence["classifier_previous"]["raw_score"], 9900)
        self.assertTrue(evidence["classifier_new_game"])
        json.dumps(evidence, allow_nan=False)

    def test_wire_sample_is_not_replaced_by_coerced_classifier_baseline(self):
        owner = server(True, raw_score_prev=9900, last_start_frame=-1000)
        wire = frame(0, 2)
        result = accept(classifier(self.candidate_socket), owner, wire)
        self.assertFalse(result["new_game"])
        self.assertEqual(wire.game_score, 9900)
        self.assertEqual(result["boundary_inputs"][1][0], 0)
        self.assertEqual(owner.client_states[7]["raw_score_prev"], 9900)
        self.assertEqual(owner.client_states[7]["_boundary_previous_accepted"][0], 0)
        wire.game_score = 123456
        self.assertEqual(result["boundary_inputs"][1][0], 0)

    def test_actual_journal_bridge_carries_actual_classifier_inputs_to_admission(self):
        owner, classify = server(True), classifier(self.candidate_socket)
        bridge_ast = ast.fix_missing_locations(ast.Module(
            body=[copy.deepcopy(method(ast.parse(self.candidate_socket), "_journal_observe"))],
            type_ignores=[]))
        namespace = dict(metrics=SimpleNamespace(measurement_active=True, measurement_generation=1))
        exec(compile(bridge_ast, "<private-actual-journal-bridge>", "exec"), namespace)
        with tempfile.TemporaryDirectory() as directory:
            owner.game_journal = journal_module(self.candidate_journal).GameJournal(directory, clock=lambda: 1000.0)
            owner._journal_experiment_label = lambda: "fixture"
            owner._journal_context = lambda _: dict(experiment="fixture", measurement_active=True,
                                                    measurement_generation=1)
            owner.replay_enabled = False
            owner._fail_inference_only = lambda reason: self.fail(reason)
            for current in (frame(9900, 2), frame(0, 2)):
                result = accept(classify, owner, current)
                namespace["_journal_observe"](owner, 7, current, owner.client_states[7], result["new_game"],
                                              boundary_inputs=result["boundary_inputs"])
            path = Path(directory) / "measurement_starts.jsonl"
            row = json.loads(path.read_text().strip())
            evidence = row["context"]["game_boundary_diagnostics"]
            self.assertEqual(row["game_uid"], 97)
            self.assertEqual(evidence["previous_accepted_wire"]["raw_score"], 9900)
            self.assertEqual(evidence["current_wire"]["raw_score"], 0)
            self.assertTrue(evidence["recent_start"])
            self.assertTrue(evidence["classifier_new_game"])
            self.assertEqual(evidence["last_start_frame_before"], 10)
            self.assertEqual(evidence["current_wire"]["accepted_frames_before"], 100)

    def run_journal(self, source, *, diagnostics, wave=1, zero=False):
        module = journal_module(source)
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        clock = [1000.0]
        journal = module.GameJournal(temporary.name, clock=lambda: clock[0])
        journal.run_id = "fixed-private-id"
        cs = dict(client_slot=4097, game_uid=96, journal_experiment="fixture",
                  journal_measurement_active=True, journal_measurement_generation=1)
        context = lambda: dict(experiment="fixture", measurement_active=True,
                               measurement_generation=1, epsilon=0.0, expert_ratio=0.0)
        write_paths = []
        original_write = journal._write
        def write(path, row):
            write_paths.append(path.name)
            return original_write(path, row)
        journal._write = write
        def observe(current, *, new_game=False, inputs=None):
            clock[0] += 1
            options = dict(new_game=new_game, context=context)
            if diagnostics:
                options["boundary_inputs"] = inputs
            journal.observe(7, current, cs, **options)
        observe(frame(9900, 2))
        cs["game_uid"] = 97
        inputs = ((9900, 2, True, False, False, 3, 99),
                  (0, wave, True, False, False, 3, 100), 9900, 2, True,
                  10, 10, True, True, "accept")
        observe(frame(0, wave), new_game=True, inputs=inputs)
        if zero:
            for life in range(3):
                observe(frame(0, wave, alive=False, done=True, lives=2-life))
                if life < 2:
                    observe(frame(0, wave, lives=2-life))
            observe(frame(0, wave, alive=False, start=True, lives=0))
            restart = (inputs[1], (0, wave, True, False, False, 0, 108),
                       0, wave, False, 107, 107, True, False, "accept")
            observe(frame(0, wave, lives=0), inputs=restart)
        else:
            for _ in range(17):
                observe(frame(10000, wave))
            observe(frame(10000, wave, alive=False, done=True, lives=0))
        clock[0] = 2000
        rows = lambda name: [json.loads(line) for line in (Path(temporary.name) / name).read_text().splitlines()]
        return journal, rows, write_paths

    def test_actual_journal_start_metadata_and_all_other_fields_writes_unchanged(self):
        before, br, bp = self.run_journal(self.original_journal, diagnostics=False)
        after, ar, ap = self.run_journal(self.candidate_journal, diagnostics=True)
        self.assertEqual(bp, ap)
        for name in ("games.jsonl", "lives.jsonl", "measurement_starts.jsonl"):
            self.assertEqual(br(name), without_evidence(ar(name)))
        self.assertEqual(before.cohort_status("fixture", 1002, 1002),
                         without_evidence(after.cohort_status("fixture", 1002, 1002)))
        start = ar("measurement_starts.jsonl")[0]
        self.assertEqual(start["context"]["game_boundary_diagnostics"]["current_wire"]["raw_score"], 0)
        self.assertNotIn("game_boundary_diagnostics", ar("games.jsonl")[0]["end_context"])
        self.assertTrue(ar("games.jsonl")[1]["eligible"])

    def test_wave2_reset_stays_abandoned_without_row_repair_or_rescue(self):
        before, _, _ = self.run_journal(self.original_journal, diagnostics=False, wave=2)
        after, rows, _ = self.run_journal(self.candidate_journal, diagnostics=True, wave=2)
        status = after.cohort_status("fixture", 1002, 1002)
        self.assertEqual(before.cohort_status("fixture", 1002, 1002), without_evidence(status))
        self.assertEqual((status["started"], status["abandoned"], status["count"]), (1, 1, 0))
        self.assertFalse(status["valid"])
        self.assertEqual(set(status["abandonment_reasons"].values()), {"measurement_start_not_wave_1"})
        evidence = rows("measurement_starts.jsonl")[0]["context"]["game_boundary_diagnostics"]
        self.assertEqual(evidence["previous_accepted_wire"]["raw_score"], 9900)
        self.assertEqual(evidence["current_wire"]["raw_wave"], 2)

    def test_zero_score_journal_restart_is_distinguished_from_classifier_reset(self):
        before, br, bp = self.run_journal(self.original_journal, diagnostics=False, zero=True)
        after, ar, ap = self.run_journal(self.candidate_journal, diagnostics=True, zero=True)
        self.assertEqual(bp, ap)
        self.assertEqual(br("measurement_starts.jsonl"), without_evidence(ar("measurement_starts.jsonl")))
        last = ar("measurement_starts.jsonl")[-1]
        self.assertEqual(last["start_reason"], "zero_score_restart")
        evidence = last["context"]["game_boundary_diagnostics"]
        self.assertEqual(evidence["journal_start_reason"], "zero_score_restart")
        self.assertFalse(evidence["classifier_new_game"])
        self.assertEqual(before.sequence, after.sequence)

    def test_normal_frames_and_valid_starts_expand_only_at_journal_begin(self):
        module = journal_module(self.candidate_journal)
        with tempfile.TemporaryDirectory() as directory:
            journal = module.GameJournal(directory, clock=lambda: 1000.0)
            context = lambda: dict(experiment="fixture", measurement_active=True, measurement_generation=1)
            cs = dict(game_uid=1, client_slot=4096)
            inputs = (None, (0, 1, True, False, False, 3, 0), None, None, False,
                      -10**9, -10**9, False, False, "accept")
            with patch.object(module, "_boundary_start_evidence", wraps=module._boundary_start_evidence) as expand:
                for _ in range(20):
                    journal.observe(7, frame(), cs, context=context, boundary_inputs=inputs)
                self.assertEqual(expand.call_count, 1)
                cs["game_uid"] = 2
                journal.observe(7, frame(), cs, new_game=True, context=context, boundary_inputs=inputs)
                self.assertEqual(expand.call_count, 2)

    def test_inactive_reset_then_bad_first_play_preserves_later_inputs_without_extra_write(self):
        module = journal_module(self.candidate_journal)
        with tempfile.TemporaryDirectory() as directory:
            journal = module.GameJournal(directory, clock=lambda: 1000.0)
            context = lambda: dict(experiment="fixture", measurement_active=True, measurement_generation=1)
            cs = dict(game_uid=97, client_slot=4097)
            reset = ((9900, 2, True, False, False, 3, 99),
                     (0, 0, False, False, False, 3, 100), 9900, 2, True, 10, 10, True, True, "accept")
            later = (reset[1], (100, 2, True, False, False, 3, 101),
                     0, 0, False, 10, 10, True, False, "accept")
            journal.observe(7, frame(0, 0, alive=False), cs, new_game=True,
                            context=context, boundary_inputs=reset)
            starts = Path(directory) / "measurement_starts.jsonl"
            original_admission_bytes = starts.read_bytes()
            with patch.object(journal, "_write", wraps=journal._write) as write:
                journal.observe(7, frame(100, 2), cs, context=context, boundary_inputs=later)
                write.assert_not_called()
            self.assertEqual(starts.read_bytes(), original_admission_bytes)
            status = journal.cohort_status("fixture", 1000, 1000)
            self.assertEqual(status["abandoned"], 1)
            self.assertEqual(set(status["abandonment_reasons"].values()), {"measurement_start_not_wave_1"})
            journal.disconnect(7, context)
            row = json.loads((Path(directory) / "games.jsonl").read_text())
            evidence = row["start_context"]["first_play_not_wave_1_inputs"]
            self.assertFalse(row["eligible"])
            self.assertEqual(row["first_play_level"], 2)
            self.assertEqual(evidence["previous_accepted_wire"]["raw_wave"], 0)
            self.assertFalse(evidence["previous_accepted_wire"]["player_alive"])
            self.assertEqual(evidence["current_wire"]["raw_wave"], 2)
            self.assertTrue(evidence["current_wire"]["player_alive"])
            self.assertFalse(evidence["classifier_new_game"])
            self.assertEqual(evidence["journal_start_reason"], "first_play_not_wave_1")


class ActivationBindingTests(unittest.TestCase):
    """Actual full stdlib sidecar/campaign modules, with explicit validator stubs.

    These narrow flag checks do not qualify existing backend/scoring validators
    or call any evaluator run, import Torch, discover processes or launch jobs.
    """
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="boundary-activation-")
        self.addCleanup(self.temporary.cleanup)
        self.work = Path(self.temporary.name)
        self.package_name = "boundary_activation_private_" + self.work.name.replace("-", "_")
        package = ModuleType(self.package_name)
        package.__path__ = []
        sys.modules[self.package_name] = package
        self.addCleanup(self.remove_modules)
        for name, attributes in (
            ("compare_frozen_measurements", dict(summarize=lambda leg: {})),
            ("compare_sidecar_measurements", dict(JOB_FIELDS=("device",), validate_backend=lambda *a, **k: None)),
        ):
            module = ModuleType(self.package_name + "." + name)
            module.__dict__.update(attributes)
            sys.modules[module.__name__] = module
            setattr(package, name, module)
        self.sidecar = self.load("run_frozen_sidecar")
        self.campaign = self.load("run_quality_campaign")

    def remove_modules(self):
        for name in list(sys.modules):
            if name == self.package_name or name.startswith(self.package_name + "."):
                sys.modules.pop(name, None)

    def load(self, name):
        _, source = sources(name + ".py")
        private = self.work / "Robotron" / "tools" / (name + ".py")
        private.parent.mkdir(parents=True, exist_ok=True)
        private.write_text(source)
        module = ModuleType(self.package_name + "." + name)
        module.__file__ = str(private)
        module.__package__ = self.package_name
        sys.modules[module.__name__] = module
        setattr(sys.modules[self.package_name], name, module)
        exec(compile(source, str(private), "exec"), module.__dict__)
        return module

    def job(self, enabled=False):
        return self.sidecar.Job(self.work / "input.pt", self.work / "output", "fixture", "cpu",
                                game_boundary_diagnostics=enabled)

    def test_job_plan_default_false_and_explicit_environment_override(self):
        self.assertIs(self.job().game_boundary_diagnostics, False)
        def private_maps(path):
            self.assertEqual(path, "/proc/self/maps")
            return SimpleNamespace(read_text=lambda: "")
        for enabled in (False, True):
            job = self.job(enabled)
            self.assertIs(job.plan()["game_boundary_diagnostics"], enabled)
            with patch.dict(os.environ, {"ROBOTRON_GAME_BOUNDARY_DIAGNOSTICS": "0" if enabled else "1"}, clear=True), \
                    patch.object(self.sidecar, "Path", side_effect=private_maps), \
                    patch.object(self.sidecar.subprocess, "Popen", side_effect=AssertionError("no process")):
                self.sidecar.configure_environment(job)
                self.assertEqual(os.environ["ROBOTRON_GAME_BOUNDARY_DIAGNOSTICS"], "1" if enabled else "0")
                self.assertEqual(os.environ["ROBOTRON_RUN_DIR"], str(job.directory / "journal"))
                self.assertFalse(job.directory.exists())

    def test_sidecar_cli_plan_binds_flag_without_launch_or_output_creation(self):
        argv = ["--checkpoint", str(self.work / "input.pt"), "--job-dir", str(self.work / "output"),
                "--label", "fixture", "--device", "cpu"]
        for enabled in (False, True):
            output = io.StringIO()
            with patch.object(self.sidecar.Job, "validate"), \
                    patch.object(self.sidecar, "run", side_effect=AssertionError("no launch")), \
                    contextlib.redirect_stdout(output):
                result = self.sidecar.main(argv + (["--game-boundary-diagnostics"] if enabled else []))
            self.assertEqual(result, 0)
            self.assertIs(json.loads(output.getvalue())["game_boundary_diagnostics"], enabled)
            self.assertFalse((self.work / "output").exists())

    def test_campaign_cli_and_all_four_job_commands_share_explicit_choice(self):
        argv = ["--reference-checkpoint", str(self.work / "reference.pt"),
                "--candidate-checkpoint", str(self.work / "candidate.pt"),
                "--output-dir", str(self.work / "campaign")]
        for enabled in (False, True):
            observed = []
            def plan(campaign):
                observed.append(campaign)
                return dict(legs=[dict(job=job.plan(), command=self.campaign.command(job))
                                  for _, job in campaign.jobs()])
            output = io.StringIO()
            with patch.object(self.campaign, "make_plan", side_effect=plan), \
                    patch.object(self.campaign, "run_campaign", side_effect=AssertionError("no launch")), \
                    contextlib.redirect_stdout(output):
                result = self.campaign.main(argv + (["--game-boundary-diagnostics"] if enabled else []))
            self.assertEqual(result, 0)
            self.assertIs(observed[0].game_boundary_diagnostics, enabled)
            legs = json.loads(output.getvalue())["legs"]
            self.assertEqual(len(legs), 4)
            for leg in legs:
                self.assertIs(leg["job"]["game_boundary_diagnostics"], enabled)
                self.assertEqual("--game-boundary-diagnostics" in leg["command"], enabled)
            self.assertFalse((self.work / "campaign").exists())

    def test_receipt_flag_must_match_precommit_and_legacy_missing_means_false(self):
        job = self.job().plan()
        receipt = dict(complete=True, active=False, cohort=dict(complete=True), job=job,
                       label=job["label"], checkpoint_sha256="checkpoint-fixture",
                       source_hashes={"source": "fixture"}, boot_assets={"identity": "fixture"})
        path = self.work / "receipt.json"
        spec = dict(receipt_path=str(path), role="reference", job=copy.deepcopy(job))
        plan = dict(checkpoints=dict(reference=dict(sha256="checkpoint-fixture")),
                    evaluator_source_hashes=receipt["source_hashes"], boot_assets=receipt["boot_assets"])
        leg = dict(expected_actor_slots=list(self.sidecar.SLOTS),
                   rows=[dict(client_slot=slot) for slot in self.sidecar.SLOTS])
        with patch.object(self.campaign, "validate_backend", return_value=leg):
            path.write_text(json.dumps(receipt))
            self.campaign.load_leg(spec, plan, verify_checkpoint=False)
            for bad in (True, 1, "0"):
                receipt["job"]["game_boundary_diagnostics"] = bad
                path.write_text(json.dumps(receipt))
                with self.assertRaisesRegex(ValueError, "Boundary diagnostics"):
                    self.campaign.load_leg(spec, plan, verify_checkpoint=False)
            receipt["job"].pop("game_boundary_diagnostics")
            spec["job"].pop("game_boundary_diagnostics")
            path.write_text(json.dumps(receipt))
            self.campaign.load_leg(spec, plan, verify_checkpoint=False)


if __name__ == "__main__":
    unittest.main()
