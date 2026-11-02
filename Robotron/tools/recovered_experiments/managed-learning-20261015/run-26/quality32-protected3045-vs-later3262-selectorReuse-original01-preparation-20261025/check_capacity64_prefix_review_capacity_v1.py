"""CPU4GiB capacity check:64 sequential strict historical ROM1200 reviews.

Reuses32 historical subjects twice as a load fixture. This cannot establish
64 distinct live actors, certificates, startup, or a new experimental result.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
N = Path(__file__).resolve().parent
P = N / 'future-evaluator-concurrency64-UNSELECTED-source-preparation-original02'


def load(name, path, digest=None):
    if digest:
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def main():
    assert os.environ.get('CUDA_VISIBLE_DEVICES') == ''
    h = load('_prefix64_capacity_h', G / 'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py',
             '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1')
    reader = load('_prefix64_capacity_reader', G / 'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py',
                  'c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071')
    root = N / 'selector-active600-counterbalanced-engineering-original01/02-B1-proposal'
    proof_pin = h.pin(root / 'independent-original-active600-all-scopes-raw-and-measurement-closeout.json')
    proof = reader.read_pin(proof_pin)
    assert proof['all_three_original_scope_descriptors_resources_argv_pins_birth_absence_and_release_verified'] is True
    result = reader.read_pin(proof['native_result'])
    job = reader.read_pin(proof['native_job'])
    assert len(result['original_slots']) == 32 and result['quality_qualified'] is False
    index = reader.read_pin(h.pin(P / 'CPU-fixture-index-v2.json'))
    wire_pin = next(c for c in index['cases'] if c['role'] == 'B64')['sources']['wire']
    wire = load('_actual_B64_wire_capacity', h.checked(wire_pin), wire_pin['sha256'])
    wire.dependencies()
    assert wire.ACTOR_COUNT == len(wire.SLOTS) == 64 and wire.GAMES_PER_SLOT == 1
    started = time.monotonic()
    results = []
    for iteration in range(64):
        slot = 4096 + iteration % 32
        entry = result['original_slots'][str(slot)]
        assert entry['actual_exit'] == 0 and entry['outputs_sealed_after_original_writer_closure'] is True
        producer_pin, proxy_pin = entry['files']['producer.jsonl'], entry['files']['proxy.jsonl']
        rows = wire.games_audit.lines(reader.read_pin(producer_pin, as_json=False))
        subject = dict(slot=slot, session=job['sessions'][str(slot)], connection=job['connections'][str(slot)])
        assert all(all(row[k] == v for k,v in subject.items()) for row in rows)
        chunks = [r for r in rows if r['kind'] == 'raw_ROM_chunk']
        assert [r['offset'] for r in chunks] == list(range(0,102400,128))
        image = b''.join(bytes.fromhex(r['data_hex']) for r in chunks)
        assert len(image) == 102400 and hashlib.sha256(image).hexdigest() == job['loaded_rom_sha256']
        raw_wire = wire.games_audit.lines(reader.read_pin(proxy_pin, as_json=False))
        assert [r['proxy_event'] for r in raw_wire] == list(range(1,len(raw_wire)+1))
        ledger = wire.audit_prefix_ledger(raw_wire, rows, subject, job['loaded_rom_sha256'], entry)
        assert ledger['raw_prefix_ledger_recomputed'] is True
        results.append(dict(iteration=iteration, historical_subject_slot=slot, producer=producer_pin,
                            proxy=proxy_pin, ledger=ledger, original_ROM_and1200_pairs_checked=True))
        del rows, raw_wire, chunks, image
        if iteration % 8 == 7:
            print(json.dumps(dict(checked_prefixes=iteration+1, elapsed_s=time.monotonic()-started)), flush=True)
    assert len(results) == 64 and 'torch' not in sys.modules
    report = dict(schema='robotron-capacity64-bounded-CPU-prefix-reader-load-proof-v1', source=h.pin(__file__),
                  source_wire_auditor=wire_pin, original_historical_case_closeout=proof_pin,
                  prefix_reviews=len(results), raw_startup_frame_pairs_reviewed=64*1200,
                  historical_distinct_subjects=32, historical_repetitions_each=2, results=results,
                  actual_elapsed_s=time.monotonic()-started, only_one_prefix_resident_at_once=True,
                  native_jobs_launched=False, actual64_distinct_live_startup_verified=False,
                  new_experiment_measurements_supplied=False, quality_qualified=False,
                  native_launch_ready=False,
                  limits='CPU load capacity only:32 real original subjects are read twice. Actual64 distinct-slot startup/certificate/ROM/proxy joins remain mandatory in originalB1/B2 native reviews.')
    target = P / 'CPU64-prefix-review-capacity-original01' / 'actual64-prefix-review-capacity.json'
    print(json.dumps(dict(report=h.put(target,report), prefix_reviews=64)),flush=True)
    time.sleep(8)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
