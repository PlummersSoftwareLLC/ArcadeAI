"""Passive closed-R1 evidence readback; no campaign decision or process changes."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import time

GAME = Path('/home/dave/source/repos/ArcadeAI/Robotron')
HERE = Path(__file__).resolve().parent
CAMPAIGN = GAME/'logs/managed-learning-20261015/quality-CE1059M-vs-joint-profile06-fresh-next8M-quality32-trial01-20261020'
OUTPUT = HERE/'R1-original-closed-cohort-independent-readback'


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def identity(info):
    return dict(device=info.st_dev, inode=info.st_ino, bytes=info.st_size,
                mtime_ns=info.st_mtime_ns, ctime_ns=info.st_ctime_ns,
                mode=oct(stat.S_IMODE(info.st_mode)), uid=info.st_uid,
                nlink=info.st_nlink)


def pin(path):
    raw = path.read_bytes()
    return dict(path=str(path), sha256=digest(raw), bytes=len(raw),
                identity=identity(path.stat()))


def write(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        os.fchmod(stream.fileno(), 0o664)
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
        os.fchmod(stream.fileno(), 0o444)
    return pin(path)


def load(path, expected, name):
    assert digest(path.read_bytes()) == expected
    assert identity(path.stat())['mode'] == '0o444'
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    assert digest(path.read_bytes()) == expected
    return module


def original_birth_live(owner):
    path = Path('/proc')/str(owner['pid'])/'stat'
    try:
        raw = path.read_text()
    except FileNotFoundError:
        return False
    return int(raw[raw.rfind(')')+2:].split()[19]) == owner['starttime_ticks']


def main():
    assert not OUTPUT.exists()
    OUTPUT.mkdir()
    cohorts = load(GAME/'tools/quality_capacity_proposal/audit_quality32_evidence_v4.py',
        'f07ccdd098cbf879c7ff98ef26e92e525b7a0ea951c38641fa2b5c0571fa50e3', '_R1_closed_cohorts')
    reviewer = load(GAME/'tools/quality_capacity_proposal/review_closed_quality32_v8.py',
        'fa7883223eca627e89663cede037e1787888080ce06b31fcf6f8462fadd28bdb', '_R1_closed_predicates')
    reader = reviewer.reader_module()
    monitor_job = json.loads((HERE/'root-live-monitor-job.json').read_bytes())
    assert digest((HERE/'root-live-monitor-job.json').read_bytes()) == 'f2a6ec8a27e54f2b6d47d5b2862d4cb40a605249a05c5777d3b0e51591d15dfd'
    binding = reader.read_pin(monitor_job['campaign_binding'])
    plan_path = CAMPAIGN/'plan.json'
    assert digest(plan_path.read_bytes()) == binding['campaign']['plan_sha256'] == '97b781ba8fc65d84ffb5d511a22c59391cd49e281afa059dbf1bebf2f81b73db'
    plan = json.loads(plan_path.read_bytes())
    game, backend, helpers, auditor = cohorts.dependencies()
    cohorts.validate_plan(plan, dict(binding['campaign'], checkpoints=plan['checkpoints']), game)
    native = reader.read_pin(monitor_job['native_owner'])
    evaluators = HERE/'runtime-bindings/leg-births'
    evaluator = json.loads((evaluators/'leg1-evaluator.json').read_bytes())
    actors = json.loads((evaluators/'leg1-actors.json').read_bytes())
    assert not original_birth_live(evaluator)
    assert all(not original_birth_live(actor) for actor in actors.values())
    status = json.loads((CAMPAIGN/'status.json').read_bytes())
    record = status['legs'][0]
    assert record['index'] == 1 and record['role'] == 'reference'
    assert record['state'] == 'finished' and record['returncode'] == 0
    assert status['current_leg'] >= 2
    captures = []
    for path in [CAMPAIGN/'01-reference/receipt.json',
                 CAMPAIGN/'01-reference/journal/games.jsonl',
                 CAMPAIGN/'01-reference/journal/measurement_starts.jsonl',
                 CAMPAIGN/'01-reference.console.log'] + [
                 CAMPAIGN/f'01-reference/actors/{slot}/console.log' for slot in range(4096,4128)]:
        with path.open('rb') as stream:
            before = identity(os.fstat(stream.fileno()))
            raw = stream.read()
            assert before == identity(os.fstat(stream.fileno()))
        archive = write(OUTPUT/'originals'/path.relative_to(CAMPAIGN), raw)
        captures.append(dict(original=dict(path=str(path), sha256=digest(raw),
                            bytes=len(raw), identity=before), archive=archive))
    campaign = __import__(backend.__package__+'.run_quality_campaign', fromlist=['load_leg'])
    receipt, validated, receipt_sha = campaign.load_leg(plan['legs'][0], plan)
    reviewer.validate_births(record, evaluator, actors, receipt, native)
    reviewer.validate_leg_scope(receipt, plan['legs'][0], record, binding)
    assert receipt['valid'] is True and receipt['complete'] is True
    assert receipt['count'] == receipt['started'] == 121
    assert receipt['pending'] == receipt['abandoned'] == 0
    registration = json.loads((GAME/'logs/managed-learning-20261015/state.json').read_bytes())
    admission_pin = registration['active_quality_job']['fixed_admission_closure_readback']
    assert admission_pin['path'] == str(HERE/'R1-fixed-admission-close-readback.json')
    admission = reader.read_pin(admission_pin)
    assert set(admission['frozen_admitted_ids']) == {row['journal_game_id'] for row in receipt['rows']}
    checked = cohorts.completed_cohort(receipt, CAMPAIGN/'01-reference', backend, helpers, auditor)
    console = helpers.console_lines((CAMPAIGN/'01-reference.console.log').read_text(),
        receipt, game, auditor, unused_expert_proof_validated=True)
    for capture in captures:
        assert pin(Path(capture['original']['path'])) == capture['original']
    assert 'torch' not in sys.modules
    report = dict(schema='robotron-profile06-closed-R1-independent-readback-v1',
        status='PASS_CLOSED_R1_ORIGINALS_ROM_RUNTIME_ONLY', observed_unix_s=time.time(),
        source=pin(Path(__file__)), plan=pin(plan_path), campaign_binding=monitor_job['campaign_binding'],
        original_record=record, original33_process_births_absent=True,
        original_native_owner=monitor_job['native_owner'],
        original_evaluator_birth=pin(evaluators/'leg1-evaluator.json'),
        original_actor_births=pin(evaluators/'leg1-actors.json'), admission_closure=admission_pin,
        receipt_sha256=receipt_sha, fixed_admission_ids_match=True,
        counts={key:receipt[key] for key in ('count','started','pending','abandoned')},
        cohort=checked, evaluator_console_classifications=console, captures=captures,
        qualified_policy=False, promotion=False, full_campaign_original_closed_review_still_required=True,
        fixed_reference_requires_both_fresh_reference_legs=True,
        original_final_reviewer_executed=False, numerical_runtime_imported=False)
    result = write(OUTPUT/'readback.json', (json.dumps(report, indent=2)+'\n').encode())
    print(json.dumps(dict(readback=result, status=report['status'], counts=report['counts'],
        statistics=checked['original_games']['statistics'])))


if __name__ == '__main__':
    main()
