"""Describe every admitted game in the closed study; never launch or change jobs."""
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import statistics
import sys
import time


ROOT = Path(__file__).resolve().parents[2]
N = ROOT / 'logs/managed-learning-20261015/run-26/quality32-protected1741-vs-normal2259-after-JSON-original01-preparation-20261022'


def load(name, relative, sha):
    path = ROOT / relative
    assert hashlib.sha256(path.read_bytes()).hexdigest() == sha, relative
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            assert key not in result, ('duplicate key', key)
            result[key] = value
        return result

    def nonfinite(value):
        raise ValueError('Nonfinite JSON constant: ' + value)

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=nonfinite)


def summarize(rows):
    fields = ('score', 'max_level', 'playable_frames', 'observed_frames', 'deaths', 'duration_s')
    answer = {'count': len(rows)}
    for key in fields:
        values = [r[key] for r in rows]
        assert all(type(x) in (int, float) and math.isfinite(x) and x >= 0 for x in values), key
        answer[key] = dict(mean=statistics.mean(values), median=statistics.median(values),
                           min=min(values), max=max(values), sum=sum(values))
    playable = sum(r['playable_frames'] for r in rows)
    answer['aggregate_score_per_playable_frame'] = sum(r['score'] for r in rows) / playable
    answer['aggregate_deaths_per_1000_playable_frames'] = 1000 * sum(r['deaths'] for r in rows) / playable
    answer['score_quartiles_inclusive'] = statistics.quantiles([r['score'] for r in rows], n=4, method='inclusive')
    answer['all32_slot_mean_scores'] = {
        str(slot): statistics.mean(r['score'] for r in rows if r['client_slot'] == slot)
        for slot in range(4096, 4128)
    }
    return answer


def comparison(candidate, reference):
    result = {key + '_mean_percent_change': 100 * (candidate[key]['mean'] / reference[key]['mean'] - 1)
              for key in ('score', 'max_level', 'playable_frames', 'observed_frames', 'deaths', 'duration_s')}
    for key in ('aggregate_score_per_playable_frame', 'aggregate_deaths_per_1000_playable_frames'):
        result[key + '_percent_change'] = 100 * (candidate[key] / reference[key] - 1)
    result['slots_with_lower_candidate_mean'] = sum(
        candidate['all32_slot_mean_scores'][slot] < reference['all32_slot_mean_scores'][slot]
        for slot in reference['all32_slot_mean_scores'])
    return result


def main():
    assert sys.argv[1:] == ['--describe-closed-original-once'], 'Explicit descriptive invocation required'
    h = load('_describe2259_helpers', 'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py',
             '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1')
    reader = load('_describe2259_reader', 'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py',
                  'c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071')
    closure_pin = h.pin(N / 'closed-four-leg-campaign-independent-root-readback-original01/readback.json')
    assert closure_pin['sha256'] == 'b0d2ef58e8347fde5ec7a7b9b9bee788bbb73c8ab3ece6f15d52f5d524a38093'
    closure = strict_json(reader.read_pin(closure_pin, as_json=False))
    scores = strict_json(reader.read_pin(closure['all368_original_admitted_game_rows_retained'], as_json=False))
    projected, inputs, summaries = {}, {}, {}
    for role, count in [('R1', 90), ('C1', 92), ('R2', 90), ('C2', 96)]:
        inp = closure['original_leg_inputs'][role]
        result = strict_json(reader.read_pin(inp['original_native_result'], as_json=False))
        reader.read_pin(inp['root_closed_readback'], as_json=False)
        reviewed = strict_json(reader.read_pin(inp['original_independent_review'], as_json=False))
        games_pin = result['journal']['games.jsonl']
        journal = [strict_json(line) for line in reader.read_pin(games_pin, as_json=False).splitlines()]
        by_id = {r['journal_game_id']: r for r in journal}
        assert len(by_id) == len(journal)
        admitted = scores[role]
        assert len(admitted) == count
        ids = {r['journal_game_id'] for r in admitted}
        assert len(ids) == count
        cohort = result['before_intentional_stop']
        assert ids == set(reviewed['original_games']['admitted_ids'])
        assert ids == {r['journal_game_id'] for r in cohort['rows']}
        assert ids == {r['journal_game_id'] for r in journal if r.get('eligible') is True
                       and cohort['start_ts'] <= r['start_unix_s'] < cohort['close_ts']}
        rows = []
        for score in admitted:
            row = by_id[score['journal_game_id']]
            assert all(row.get(k) is True for k in ('eligible', 'complete', 'known_start', 'eval_only'))
            assert not row.get('excluded_reason')
            assert row['score'] == score['score'] and row['client_slot'] == score['client_slot']
            rows.append({key: row[key] for key in ('journal_game_id', 'client_slot', 'score', 'max_level',
                         'playable_frames', 'observed_frames', 'deaths', 'duration_s')})
        assert {r['client_slot'] for r in rows} == set(range(4096, 4128))
        projected[role] = rows
        inputs[role] = dict(**inp, original_games_journal=games_pin,
                           fixed_admission_open=cohort['start_ts'], fixed_admission_close=cohort['close_ts'],
                           total_original_journal_rows=len(journal), admitted_completed_rows=count)
        summaries[role] = summarize(rows)
        original = closure['original_per_leg_statistics'][role]
        assert summaries[role]['score']['mean'] == original['mean']
        assert summaries[role]['score']['median'] == original['median']
        assert summaries[role]['score']['sum'] == original['score_sum']
    reference = summarize(projected['R1'] + projected['R2'])
    assert reference['count'] == 180
    assert reference['score']['mean'] == closure['fixed_fresh_R1_R2_reference']['mean']
    assert reference['score']['median'] == closure['fixed_fresh_R1_R2_reference']['median']
    comparisons = {role: comparison(summaries[role], reference) for role in ('C1', 'C2')}
    out = N / 'readonly-all368-role-separated-game-shape-original01'
    assert not out.exists(), 'Never replace or retry a prior original output'
    out.mkdir(mode=0o700)
    projection_pin = h.put(out / 'all368-original-game-projection-by-role.json', projected)
    report = dict(schema='robotron-descriptive-closed-four-cohort-game-shape-v1',
        classification='DESCRIPTIVE_ALL368_RETAINED_CANDIDATES_SEPARATE_NO_NEW_QUALITY_DECISION',
        source=h.pin(Path(__file__).resolve()), closed_original_campaign=closure_pin,
        prior_ad_hoc_probe_failure=h.pin(Path(__file__).resolve().parent / 'descriptive2259-admission-contract-correction-original01/record.json'),
        inputs=inputs, all_original_rows_projection=projection_pin,
        summaries=summaries, fixed_R1_R2_reference_summary=reference,
        independent_candidate_comparisons_to_fixed_reference=comparisons,
        reference_repeat_R2_vs_R1=comparison(summaries['R2'], summaries['R1']),
        limitations=[
            'Secondary journal fields are descriptive and have not been independently audited against every wire frame.',
            'Slots are not matched random seeds. No paired significance or causal mechanism is inferred.',
            'Wall duration depends on runtime and does not establish training throughput.',
            'No candidate pool, original scientific review retry, requalification, or new admitted game was used.',
            'These fields cannot identify a replay, learning-rate, architecture, or priority cause by themselves.'
        ], interpretation='Compare registered trajectory lengths and progression with scoring rate; select subsequent research using separate learning evidence.',
        quality_qualified=False, promotion=False, learning_speed_gain_verified=False,
        throughput_gain_verified=False, main_runtime_changed=False, treatment_selected_or_deployed=False,
        created_unix_s=time.time())
    receipt = h.put(out / 'readback.json', report)
    print(json.dumps(dict(receipt=receipt, comparisons=comparisons,
                         reference_repeat=report['reference_repeat_R2_vs_R1']), allow_nan=False))


if __name__ == '__main__':
    main()
