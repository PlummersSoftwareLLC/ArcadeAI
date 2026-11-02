"""Reject backend drift before using frozen-game scores for policy decisions."""
import copy
import tempfile
from pathlib import Path
import unittest

from .compare_sidecar_measurements import compare_sidecars, sha256, validate_backend
from .test_compare_frozen_measurements import receipt


def sidecar(label):
    data = receipt(label)
    slots = list(range(4096, 4112))
    for index, row in enumerate(data["rows"]):
        row["client_slot"] = slots[index % len(slots)]
    data["boundary"]["actor_slots"] = slots
    data["job"] = dict(device="cuda", gpu_uuid="GPU-private", actors=16,
        actor_slots=slots, port=9999, cohort_s=60, timeout_s=180, wait_us=1000,
        epsilon=0, expert_ratio=0, difficulty=5, start_level=1, replay_enabled=False,
        fp16=False, mame="/test/mame", rompath="/test/roms", cpu_threads=2,
        boot_assets="/test/boot", inference_backend="inductor", inference_max_batch_size=16)
    data.update(inference_backend="inductor", numeric_policy=dict(
        autocast=False, weights="float32", inputs="float32", support="float32",
        compiled=True, backend="inductor", execution="torch.compile",
        suppress_errors=False, error_on_recompile=True,
        serving_thread_checked=True, warm_shapes=list(range(1, 17))),
        compile_report=dict(all_shapes_verified=list(range(1, 17)),
                            graph_state=dict(unique_graphs=2, graph_breaks=0, unimplemented=0)),
        runtime=dict(torch="test", gpu_name="test"), source_hashes=dict(source="test"),
        ended_source_hashes=dict(source="test"), checkpoint_sha256="a"*64,
        actor_timeout_logs={str(slot): 0 for slot in slots},
        actor_cleanup_timeout_logs={str(slot): 1 for slot in slots},
        boot_assets=dict(identity="boot", files={"nvram": {"sha256": "test"}}),
        boot_restores={str(slot): dict(identity="boot", files={"nvram": {"sha256": "test"}})
                       for slot in slots},
        socket_wait=dict(port=9999, wait_us=1000, sha256="wire",
                         actors={str(slot): dict(matching_activation=True) for slot in slots}))
    add_confirmed_fixture(data)
    return data


class SidecarComparisonTests(unittest.TestCase):
    def test_matching_full_cohorts_pass_without_mutating_or_dropping_cleanup_evidence(self):
        base, candidate = sidecar("base"), sidecar("candidate")
        original = copy.deepcopy((base, candidate))
        report = compare_sidecars(base, candidate, iterations=100)
        self.assertTrue(report["backend_validated"])
        self.assertEqual(report["score_ratio"], 1)
        self.assertEqual((base, candidate), original)

    def test_backend_drift_rejected_even_when_game_protocol_matches(self):
        for field, value in (("gpu_uuid", "GPU-other"), ("wait_us", 500),
                             ("cohort_s", 120), ("cpu_threads", 4),
                             ("boot_assets", "/different/boot")):
            with self.subTest(field=field):
                candidate = sidecar("candidate")
                candidate["job"][field] = value
                with self.assertRaises(ValueError):
                    compare_sidecars(sidecar("base"), candidate, iterations=100)
        for field in ("runtime", "numeric_policy", "source_hashes"):
            with self.subTest(field=field):
                candidate = sidecar("candidate")
                candidate[field]["extra"] = True
                if field == "source_hashes":
                    candidate["ended_source_hashes"] = dict(candidate[field])
                with self.assertRaises(ValueError):
                    compare_sidecars(sidecar("base"), candidate, iterations=100)

    def test_partial_cohorts_and_runtime_errors_rejected(self):
        for field, value in (("pending", 1), ("abandoned", 1), ("complete", False),
                             ("server_error", "disconnect"), ("inference_error", "failed"),
                             ("cleanup_errors", ["unowned process remains"]),
                             ("invalidity_reasons", ["source_changed"])):
            with self.subTest(field=field):
                data = sidecar("bad")
                data[field] = value
                with self.assertRaises(ValueError):
                    validate_backend(data)
        data = sidecar("bad")
        data["actor_timeout_logs"]["4096"] = 1
        with self.assertRaisesRegex(ValueError, "runtime timeouts"):
            validate_backend(data)

    def test_source_mutation_and_silent_compile_fallback_rejected(self):
        for field, value in (("compiled", False), ("suppress_errors", True),
                             ("error_on_recompile", False), ("serving_thread_checked", False),
                             ("warm_shapes", [1, 16])):
            with self.subTest(field=field):
                data = sidecar("bad")
                data["numeric_policy"][field] = value
                with self.assertRaises(ValueError):
                    validate_backend(data)
        data = sidecar("bad")
        data["ended_source_hashes"]["source"] = "changed"
        with self.assertRaisesRegex(ValueError, "source changed"):
            validate_backend(data)

    def test_unknown_backend_and_missing_graph_or_boot_evidence_rejected(self):
        for mutation in (
                lambda d: d["job"].update(inference_backend="unknown"),
                lambda d: d["numeric_policy"].update(backend="eager"),
                lambda d: d["numeric_policy"].update(execution="eager"),
                lambda d: d["compile_report"]["graph_state"].pop("unique_graphs"),
                lambda d: d["compile_report"]["graph_state"].update(unique_graphs=0),
                lambda d: d["boot_assets"].update(files=None)):
            data = sidecar("bad")
            mutation(data)
            with self.assertRaises(ValueError):
                validate_backend(data)

    def test_boot_and_wire_evidence_must_cover_every_actor(self):
        for mutation in (
                lambda d: d["boot_restores"].pop("4096"),
                lambda d: d["boot_restores"]["4096"].update(identity="other"),
                lambda d: d["socket_wait"]["actors"]["4096"].update(matching_activation=False),
                lambda d: d["socket_wait"]["actors"].pop("4096")):
            data = sidecar("bad")
            mutation(data)
            with self.assertRaises(ValueError):
                validate_backend(data)

    def test_overlap_is_rejected_as_a_replication(self):
        data = sidecar("same")
        with self.assertRaisesRegex(ValueError, "overlap"):
            compare_sidecars(data, copy.deepcopy(data), iterations=100)

    def test_optional_checkpoint_readback_detects_changed_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "checkpoint.pt"
            path.write_bytes(b"fixture")
            data = sidecar("base")
            data.update(checkpoint_path=str(path), checkpoint_sha256=sha256(path))
            validate_backend(data, verify_checkpoint=True)
            path.write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "checkpoint copy"):
                validate_backend(data, verify_checkpoint=True)


"""Synthetic unit-test proof construction; never original evaluation evidence."""
def add_confirmed_fixture(data):
    import copy
    mode = 'confirmed_reset_reserves_v1'
    data['job'].update(completion_policy=mode, game_boundary_diagnostics=True)
    successors = {}
    for index, row in enumerate(data['rows']):
        zero = row['score'] == 0
        reason = 'zero_score_restart' if zero else 'score_reset'
        uid = index + 1
        next_uid = uid if zero else uid + 10000
        row.update(client_id=index % 16, game_uid=uid, completion_policy=mode,
                   boundary_reason=reason, start_reason='score_reset')
        row['start_context']['complete_game_boundary_policy'] = mode
        diagnostic = dict(schema='robotron-game-boundary-inputs-v1',
            journal_start_reason=reason, classifier_verdict='accept', classifier_new_game=not zero,
            classifier_previous=dict(raw_score=row['score'] % 100_000_000, raw_wave=1, player_alive=False),
            previous_accepted_wire=dict(raw_score=row['score'] % 100_000_000, accepted_frames_before=5),
            current_wire=dict(raw_score=0, accepted_frames_before=6))
        next_id = row['journal_game_id'] + ':next'
        row['terminal_confirmation'] = dict(schema='robotron-confirmed-game-reset-v1',
            reason=reason, previous_score=row['score'], next_score=0,
            previous_game_uid=uid, next_game_uid=next_uid, previous_raw_reserves=0,
            next_raw_reserves=2, next_wave=1, next_alive=False, restart_pulse=True,
            classifier_new_game=not zero, next_journal_game_id=next_id,
            ingest_boundary_inputs=diagnostic)
        successors[row['journal_game_id']] = dict(journal_game_id=next_id,
            client_id=row['client_id'], client_slot=row['client_slot'], game_uid=next_uid,
            known_start=True, start_reason=reason, start_unix_s=row['end_unix_s']+.01,
            start_frame=dict(score=0, level=1, player_alive=False, raw_reserves=2),
            context=dict(complete_game_boundary_policy=mode,
                         game_boundary_diagnostics=copy.deepcopy(diagnostic)))
    data['terminal_successors'] = successors


def write_terminal_fixture(data, directory):
    """Write synthetic originals only in unit-test temporary directories."""
    import copy
    import hashlib
    import json
    rows = data.get('rows', data.get('cohort', {}).get('rows'))
    games, starts = copy.deepcopy(rows), []
    for row in games:
        row.setdefault('start_frame', dict(score=0, level=1, player_alive=False, raw_reserves=2))
    # The receipt and synthetic original game records share the same start field.
    for original, receipt_row in zip(games, rows):
        receipt_row['start_frame'] = copy.deepcopy(original['start_frame'])
    for successor in data['terminal_successors'].values():
        game = {key: copy.deepcopy(value) for key, value in successor.items() if key != 'context'}
        game['start_context'] = copy.deepcopy(successor['context'])
        game.update(complete=False, eligible=False)
        games.append(game)
    for game in games:
        start = {key: copy.deepcopy(game[key]) for key in ('journal_game_id', 'client_id',
            'client_slot', 'game_uid', 'known_start', 'start_reason', 'start_unix_s', 'start_frame')}
        start['context'] = copy.deepcopy(game['start_context'])
        starts.append(start)
    directory = directory/'journal'
    directory.mkdir(exist_ok=True)
    data['terminal_journal_sha256'] = {}
    for name, records in (('games.jsonl', games), ('measurement_starts.jsonl', starts)):
        raw = b''.join((json.dumps(row)+'\n').encode() for row in records)
        (directory/name).write_bytes(raw)
        data['terminal_journal_sha256'][name] = hashlib.sha256(raw).hexdigest()

if __name__ == "__main__":
    unittest.main()
