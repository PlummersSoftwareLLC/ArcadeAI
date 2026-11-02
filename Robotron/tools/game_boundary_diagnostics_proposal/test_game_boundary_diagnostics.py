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
import json
from pathlib import Path
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch


HERE = Path(__file__).resolve().parent
GAME = HERE.parents[1]
PINS = {
    "socket_server.py": "8fe556f7507547a97839072bbcecc98384c2b395c8ae789ac8ee062f55bca721",
    "game_journal.py": "27c6143851aff73dd355db89e1ffaa65d90d215b91921406050387be5ad69029",
}


def sources(name):
    raw = (GAME / "Scripts" / "dqn" / name).read_bytes()
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
                if key not in {"game_boundary_diagnostics", "_boundary_previous_accepted"}}
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
                fromfile="a/Robotron/Scripts/dqn/" + name,
                tofile="b/Robotron/Scripts/dqn/" + name))
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

    def test_evidence_expansion_occurs_only_on_actual_journal_begin(self):
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


if __name__ == "__main__":
    unittest.main()
