"""Build a private source tree for CPU review; never install or launch anything."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
GAME = HERE.parents[1]
OUTPUT = HERE/'quality_integration_reviewed4'


def change(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Expected one exact integration anchor: ' + repr(old))
    return text.replace(old, new)


def main():
    OUTPUT.mkdir()
    private = OUTPUT/'Robotron'
    (private/'tools').mkdir(parents=True)
    (private/'Scripts/dqn').mkdir(parents=True)
    originals = {}
    for folder, pattern in (('tools', '*.py'), ('Scripts/dqn', '*.py'), ('Scripts', '*.lua'), ('Scripts', '*.c')):
        for source in (GAME/folder).glob(pattern):
            relative = source.relative_to(GAME)
            raw = source.read_bytes()
            (private/relative).write_bytes(raw)
            originals[str(relative)] = hashlib.sha256(raw).hexdigest()
    (private/'Scripts/dqn/game_journal.py').write_bytes((HERE/'game_journal_candidate_reviewed3.py').read_bytes())
    (private/'tools/confirmed_terminal_evidence.py').write_bytes((HERE/'confirmed_terminal_evidence_reviewed4.py').read_bytes())
    # Bind the same policy in plans, environment, evaluator and backend validator.
    path = private/'tools/run_frozen_sidecar.py'
    text = path.read_text()
    text = change(text, '    game_boundary_diagnostics: bool = False',
                  '    game_boundary_diagnostics: bool = True\n    completion_policy: str = "confirmed_reset_reserves_v1"')
    text = change(text, '        if type(self.game_boundary_diagnostics) is not bool:',
                  '        if self.completion_policy != "confirmed_reset_reserves_v1" or self.game_boundary_diagnostics is not True:\n            raise ValueError("Confirmed full-game resets and boundary diagnostics are required")\n        if type(self.game_boundary_diagnostics) is not bool:')
    text = change(text, '                    game_boundary_diagnostics=self.game_boundary_diagnostics,',
                  '                    game_boundary_diagnostics=self.game_boundary_diagnostics,\n                    completion_policy=self.completion_policy,')
    text = change(text, '    # Bind the plan\'s explicit choice; inherited environment never opts in.',
                  '    os.environ["ROBOTRON_GAME_COMPLETION_POLICY"] = job.completion_policy\n    # Bind the plan\'s explicit choice; inherited environment never opts in.')
    text = change(text, '    paths = [Path(__file__), GAME / "tools/sidecar_boot.py",',
                  '    paths = [Path(__file__), GAME / "tools/sidecar_boot.py",\n             GAME / "tools/confirmed_terminal_evidence.py",')
    text = change(text, '            validate_receipt(result)\n', '''            validate_receipt(result)
            try:
                from .confirmed_terminal_evidence import collect_successors, validate_receipt_terminals
            except ImportError:
                from confirmed_terminal_evidence import collect_successors, validate_receipt_terminals
            rows = result.get("rows", result.get("cohort", {}).get("rows", []))
            def read_original(name):
                raw = (job.directory / "journal" / name).read_bytes()
                if raw and not raw.endswith(b"\\n"):
                    raise ValueError("Partial original terminal journal")
                return [json.loads(line) for line in raw.splitlines()]
            result["terminal_successors"] = collect_successors(rows,
                read_original("games.jsonl"), read_original("measurement_starts.jsonl"))
            result["terminal_journal_sha256"] = {name: sha256(job.directory / "journal" / name)
                for name in ("games.jsonl", "measurement_starts.jsonl")}
            validate_receipt_terminals(result, rows)
''')
    text = change(text, '        except ValueError as error:\n            result.update(valid=False, reason="receipt_validation_failed"',
                  '        except (OSError, ValueError, TypeError, KeyError) as error:\n            result.update(valid=False, reason="receipt_validation_failed"')
    text = change(text, 'parser.add_argument("--game-boundary-diagnostics", action="store_true",',
                  'parser.add_argument("--game-boundary-diagnostics", action="store_true", default=True,')
    path.write_text(text)
    path = private/'tools/compare_sidecar_measurements.py'
    text = path.read_text()
    text = change(text, '    "cpu_threads", "boot_assets", "inference_backend", "inference_max_batch_size",',
                  '    "cpu_threads", "boot_assets", "inference_backend", "inference_max_batch_size",\n    "completion_policy", "game_boundary_diagnostics",')
    text = change(text, '    leg = validate_receipt(receipt)', '''    leg = validate_receipt(receipt)
    try:
        from .confirmed_terminal_evidence import validate_receipt_terminals
    except ImportError:
        from confirmed_terminal_evidence import validate_receipt_terminals
    rows = receipt.get("rows", receipt.get("cohort", {}).get("rows", []))
    validate_receipt_terminals(receipt, rows)''')
    path.write_text(text)
    path = private/'tools/run_quality_campaign.py'
    text = path.read_text()
    text = change(text, '    game_boundary_diagnostics: bool = False', '    game_boundary_diagnostics: bool = True')
    text = change(text, 'parser.add_argument("--game-boundary-diagnostics", action="store_true",',
                  'parser.add_argument("--game-boundary-diagnostics", action="store_true", default=True,')
    text = change(text, '    expected = spec["job"]', '\n'.join([
        '    try:',
        '        from .confirmed_terminal_evidence import verify_original_journal_bytes',
        '    except ImportError:',
        '        from confirmed_terminal_evidence import verify_original_journal_bytes',
        '    journal = Path(spec["job"]["directory"]) / "journal"',
        '    verify_original_journal_bytes(receipt, {name: (journal / name).read_bytes()',
        '        for name in ("games.jsonl", "measurement_starts.jsonl")})',
        '    expected = spec["job"]']))
    path.write_text(text)
    # Existing numerical gates retain their bodies. Small synthetic fixtures gain
    # explicit terminal proofs; they are never scientific evaluation evidence.
    path = private/'tools/test_compare_sidecar_measurements.py'
    text = path.read_text()
    text = change(text, '    return data\n', '    add_confirmed_fixture(data)\n    return data\n')
    text += '\n' + (HERE/'terminal_test_fixture_reviewed4.py').read_text()
    # Definitions must precede unittest.main for direct execution too.
    marker = '\nif __name__ == "__main__":\n    unittest.main()\n'
    text = change(text, marker, '') + marker
    path.write_text(text)
    path = private/'tools/test_run_quality_campaign.py'
    text = path.read_text()
    text = change(text, 'from .test_compare_sidecar_measurements import sidecar',
                  'from .test_compare_sidecar_measurements import sidecar, add_confirmed_fixture')
    text = change(text, '        if nested:\n', '        add_confirmed_fixture(data)\n        if nested:\n')
    text = change(text, 'from .test_compare_sidecar_measurements import sidecar, add_confirmed_fixture', 'from .test_compare_sidecar_measurements import sidecar, add_confirmed_fixture, write_terminal_fixture')
    text = change(text, '        path.write_text(json.dumps(data))', '        write_terminal_fixture(data, path.parent)\n        path.write_text(json.dumps(data))')
    path.write_text(text)
    changes = []
    patch = []
    for relative in ('Scripts/dqn/game_journal.py', 'tools/run_frozen_sidecar.py',
                     'tools/run_quality_campaign.py', 'tools/compare_sidecar_measurements.py',
                     'tools/confirmed_terminal_evidence.py', 'tools/test_compare_sidecar_measurements.py',
                     'tools/test_run_quality_campaign.py'):
        source = GAME/relative
        before = source.read_text() if source.exists() else ''
        after = (private/relative).read_text()
        changes.append(dict(path=relative, before_sha256=originals.get(relative),
                            after_sha256=hashlib.sha256(after.encode()).hexdigest()))
        patch.extend(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                                        fromfile='a/Robotron/'+relative, tofile='b/Robotron/'+relative))
    (OUTPUT/'proposed-integration.patch').write_text(''.join(patch))
    (OUTPUT/'manifest.json').write_text(json.dumps(dict(status='PRIVATE_REVIEW_ONLY',
        installed_source_changed=False, changes=changes, original_copied_sources=originals,
        validation_only=True, qualification=False, promotion=False), indent=2)+'\n')
    print(json.dumps(dict(private_tree=str(private), changed_files=len(changes),
                         installed_source_changed=False)))


if __name__ == '__main__':
    main()
