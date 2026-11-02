"""Bounded publication JSON/stat audit: no model payload, Torch, GPU or controls."""
import datetime
import hashlib
import json
import math
import os
import pathlib
import stat
import statistics

D = pathlib.Path(__file__).resolve().parent
R = D.parents[2]
B = D.parent
EXPECTED = '5076199285752a8748ce9566bc74c6b67210a03ae7f04f132f92b786dea102da'
CAMP_SHA = '23f01f6e377dd1a34fb3a10ab9f2a14439b58ffd03fed4acccdcb7513349ecaa'
META_SHA = 'f5a0ef9c1c0c046abfcdf8c98456dd58644d38a9073ca2f601d140a034a94e09'
raws = {}
pins = []
def read(path, expected=None):
    path = pathlib.Path(path).absolute()
    assert path.suffix in ('.json', '.py'), 'Refuse non-small-evidence payload'
    assert not path.is_symlink() and path.is_file()
    if path not in raws:
        assert path.stat().st_size < 2_000_000
        raws[path] = path.read_bytes()
    digest = hashlib.sha256(raws[path]).hexdigest()
    if expected is not None:
        assert digest == expected, str(path)
        pins.append({'path': str(path), 'sha256': digest})
    return json.loads(raws[path]) if path.suffix == '.json' else None

def snapshot(path):
    path = pathlib.Path(path)
    s = path.stat()
    return {'size_bytes': s.st_size, 'mode': oct(stat.S_IMODE(s.st_mode)),
            'inode': s.st_ino, 'device': s.st_dev, 'mtime_ns': s.st_mtime_ns,
            'ctime_ns': s.st_ctime_ns, 'nlink': s.st_nlink,
            'regular_nonsymlink': stat.S_ISREG(s.st_mode) and not path.is_symlink()}

campaign_path = B / 'sidecar-fresh3-192M-confirmed-campaign.json'
model_path = R / 'models_dqn/managed-incumbents/fresh3-192M-confirmed.pt'
meta_path = model_path.with_suffix('.pt.json')
c, m = read(campaign_path, CAMP_SHA), read(meta_path, META_SHA)
analysis = read(c['comparison_report']['path'], c['comparison_report']['sha256'])
lineage = read(c['lineage']['path'], c['lineage']['sha256'])
prior = read(c['prior_byte_pins']['path'], c['prior_byte_pins']['sha256'])
history = read(c['completed_history_manifest']['path'], c['completed_history_manifest']['sha256'])
old128 = read(c['historical_segment']['path'], c['historical_segment']['sha256'])
read(c['analysis_code']['path'], c['analysis_code']['sha256'])
receipts = {s['label']: read(s['path'], s['sha256']) for s in c['sources'] + c['reference_sources']}
for row in c['additional_history']:
    read(row['path'], row['sha256'])
    for key in ('lineage', 'analysis', 'isolation_audit'):
        if key + '_path' in row:
            read(row[key + '_path'], row[key + '_sha256'])
audits = {label: read(row['path'], row['sha256']) for label, row in c['main_training_isolation_provenance'].items()}
retained = []
for item in prior['protected']:
    result = {'label': item['label'], 'artifacts': {}}
    for kind in ('checkpoint', 'metadata'):
        row = item[kind]
        info = snapshot(row['path'])
        assert info['regular_nonsymlink'] and all(info[k] == row[k] for k in info if k != 'regular_nonsymlink')
        if kind == 'metadata':
            read(row['path'], row['sha256'])
        result['artifacts'][kind] = info
    retained.append(result)
for row in prior['historical_campaigns']:
    read(row['path'], row['sha256'])
    info = snapshot(row['path'])
    assert all(info[k] == row[k] for k in info if k != 'regular_nonsymlink')

labels = ['sidecar-gpu0-192M-screen-01', 'sidecar-gpu0-192M-confirm-01']
scores = [row['score'] for label in labels for row in receipts[label]['rows']]
ids = [row['journal_game_id'] for label in labels for row in receipts[label]['rows']]
summary = dict(count=len(scores), mean=statistics.mean(scores), median=statistics.median(scores),
               sd=statistics.stdev(scores), se=statistics.stdev(scores) / math.sqrt(len(scores)))
pool = c['descriptive_pools']['confirmed192M']
gate = c['gain_gate']
model_stat, source_stat = snapshot(model_path), snapshot(lineage['candidate']['path'])
checks = {
    'root_supplied_campaign_and_metadata_byte_pins_match': True,
    'all_referenced_small_evidence_pins_and_prior_statguards_match': True,
    'protected_model_expected_identity_attested_without_payload_read': m['sha256'] == c['policy_identity']['sha256'] == c['policy_identity']['protected_copy']['sha256'] == lineage['candidate']['sha256'] == EXPECTED,
    'new_model_metadata_campaign0444_nlink1_regular': all(s['regular_nonsymlink'] and s['mode'] == '0o444' and s['nlink'] == 1 for s in (model_stat, snapshot(meta_path), snapshot(campaign_path))),
    'new_model_independent_source_inode_and_expected_size': (model_stat['device'], model_stat['inode']) != (source_stat['device'], source_stat['inode']) and model_stat['size_bytes'] == source_stat['size_bytes'] == c['policy_identity']['protected_copy']['size_bytes'],
    'both_original_fulltails52_61_and113_unique_rows': [receipts[label]['count'] for label in labels] == [52, 61] and len(ids) == len(set(ids)) == 113 and all(r['valid'] is True and r['complete'] is True and r['started'] == r['count'] and r['pending'] == r['abandoned'] == 0 for label, r in receipts.items() if label in labels),
    '113_summaries_recomputed_match_publication_metadata_analysis': all(math.isclose(summary[k], pool[k], rel_tol=1e-13) and math.isclose(summary[k], analysis['pooled_candidate_vs_composite']['candidate'][k], rel_tol=1e-13) for k in summary) and all(math.isclose(summary[k], m['combined_' + q], rel_tol=1e-13) for k, q in [('count','n'),('mean','mean'),('median','median'),('se','se')]),
    'two_independent_mean105pct_and_median_gates_preserved': gate == m['gain_gate'] == analysis['management'] and gate['promotion_eligible'] is True and len(gate['each_leg']) == 2 and all(row['mean'] >= 1.05 * 206615.54054054053 and row['median'] >= 166112.5 and row['mean_gate'] is True and row['median_gate'] is True for row in gate['each_leg']) and gate['low_N_leg_labels'] == labels,
    'both_positive_cleanup_receipt_checkpoint_source_pins_match': c['main_training_isolation_provenance'] == m['main_training_isolation_provenance'] and all(a['pass'] is True and a['checks'] and all(v is True for v in a['checks'].values()) and all(a['checks'][key] is True for key in ('private_owned_processes_listener_released','private_GPU0_context_released','loaded_sources_unchanged')) and a['receipt_sha256'] == next(s['sha256'] for s in c['sources'] if s['label'] == label) and a['checkpoint_sha256'] == EXPECTED for label, a in audits.items()),
    'old128_original148_reference_and_protected_pair_retained': c['descriptive_pools']['composite128M']['count'] == gate['reference']['count'] == 148 and gate['reference']['mean'] == 206615.54054054053 and gate['reference']['median'] == 166112.5 and c['historical_segment']['sha256'] == '537975693dc67ae99366902908d8311e800e78121ad8d16969af80bdc64e6faf' and old128['policy_identity']['sha256'] == '70bf8218fa761de97bc89c30981dfd1d779484b459ec6837ed27213735e908f1' and len(retained) == 9 and retained[-1]['label'] == '128M' and c['policy_identity']['retained_previous_incumbents'] == prior['protected'],
    'global26_2613_unique_and_separate_completed_history24_2500': c['validation']['global_ids'] == analysis['global_ids'] == {'receipts': 26, 'games': 2613, 'overlaps': 0} and len(history['all_original_receipt_sources']) == 24,
    'metadata_policy_clock_optimizer_and_backend_preserved': m['saved_policy_clocks'] == m['saved_checkpoint_metadata'] == c['policy_identity']['saved_policy_clocks'] and all(v == lineage['candidate']['saved_metadata'][k] for k, v in m['saved_policy_clocks'].items()) and m['optimizer_exposure'] == lineage['candidate']['optimizer'] and m['backend'] == c['common_runtime'] and m['analysis'] == c['comparison_report'] and m['lineage'] == c['lineage'],
    'publication_itself_makes_no_state_or_control_promotion': c['promotion'] is False and c['managed_state_changed'] is False and m['state_or_control_changed'] is False,
    'prior_attestation_stat_only_limit_explicit': 'NO model payload read/hash' in c['prior_byte_pins']['scope'] and 'before this new stat baseline' in m['retained_prior_artifact_scope'],
}
proposal_path = D / 'collector4096-conditional-ABA-proposal.json'
proposal_raw = proposal_path.read_bytes()
proposal = json.loads(proposal_raw)
proposal_sha = hashlib.sha256(proposal_raw).hexdigest()
assert proposal_sha == '06fcf5cba1af303e2393c121bca2e8a87da24fe811628c27628db346e135580c'
report = {
    'schema': 'robotron-192M-publication-small-metadata-stat-independent-audit-v1',
    'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'pass': all(checks.values()), 'checks': checks,
    'campaign_sha256': CAMP_SHA, 'metadata_sha256': META_SHA, 'expected_new_model_sha256': EXPECTED,
    'model_stat': model_stat, 'source_model_stat': source_stat, 'summary113_recomputed': summary,
    'small_evidence_byte_pins': pins, 'retained_nine_prior_pairs_stat_verified': retained,
    'model_payload_hash_scope': 'NONE read or hashed by this audit, including the newly protected model. New payload SHA is carried from pinned final lineage/publication and root performs its independent new-payload hash. Prior payload SHA attestations are inherited with current full statguards and small metadata/campaign byte checks; stats do not exclude changes before the pinned baseline.',
    'collector_proposal_review': {'sha256': proposal_sha, 'verdict': 'GO for root prospective adoption after recording actual promotion/recipe-retention trigger; no launch authorized by this audit',
        'required_late_pins': proposal['root_late_pins'],
        'additional_concrete_adoption_requirements': [
            'Pin this exact proposal and actual192 analysis/campaign/both cleanup proofs plus separate root promotion and recipe-retention decision before choosing prospective A anchor.',
            'Record each full launch environment/argv and compare B/Areturn against A: collector1→0.5→1 and required run/output paths only. Record actual baseline512/batch4096/cap8/measurement inactive/current clock,192 owned identities and source20/private12.',
            'Pin A anchor before outcomes; for each restarted leg pin actual successful all192-connected time, wait90s, and select first eligible observation then first>=180s endpoint. A late manifest is its real timestamp, never backdated; retain any delay and all intervening rows.',
            'Pin raw observation coverage, GPU energy sample coverage, all full30s/endpoints and autosave/bank/other-work overlaps. Current-PID activation segments/baseline deltas must distinguish appended old MAME timeout lines.',
            'At each restart establish new process/epoch counter baselines; learner inserts=dqn+epsilon, separate eval/expert/unattributed/import/bank data; optimizer completed=applied+AMPskipped+unavailable, pending0or1 and unavailable0; logical saved clocks and actual Adam steps stay separate.',
            'Require safe Areturn before any B winner; decide only B>=1.05max(A,Areturn) plus original FPS/SPF/endpoints/all safety guards. Preserve correctly classified AMP skips and Inf-gradient rows; nonfinite loss/runtime/graph/native/read/drop/actor/bank faults invalidate; historical compilerB remains invalid.',
            'Model-only insurance and hot reversal cannot roll back evolved replay, learned state, actor trajectories or RNG. Record restart/downtime cost and resolve secondary GPU-only energy tradeoffs explicitly; no new energy veto or quality-equivalence claim.'
        ], 'scope': 'Source/fact review only. Proposal remains unadopted until root records adoption. No A/B/Areturn controls, source changes, model loads, GPU contexts or process actions.'},
    'scope': 'Standalone audit only; no canonical/state/control/process mutation, Torch/GPU or model payload access. No quality bootstrap rerun. Existing final evidence is byte-bound and113 original rows are recomputed descriptively.'}
output = D / 'quality192M-publication-independent-small-audit.json'
with output.open('x') as file:
    json.dump(report, file, indent=2, allow_nan=False)
    file.write('\n'); file.flush(); os.fchmod(file.fileno(), 0o444); os.fsync(file.fileno())
print(json.dumps({'pass': report['pass'], 'checks': len(checks), 'failed': [k for k, v in checks.items() if not v], 'sha256': hashlib.sha256(output.read_bytes()).hexdigest(), 'summary113': summary}, indent=2))
