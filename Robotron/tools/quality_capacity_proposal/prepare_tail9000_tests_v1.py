"""Construct new synthetic fixtures without editing any existing source/test."""
import argparse
import hashlib
import json
import os
from pathlib import Path

H = Path(__file__).resolve().parent
P = H.parents[1]/'logs/managed-learning-20261015/run-26/quality32-fresh-candidate-5400-9000-protocol-proposal-20261019'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-new-tests', action='store_true')
    args = parser.parse_args()
    if not args.write_new_tests:
        print('PLAN_ONLY: no reads, outputs, tests or launches')
        return
    definitions = [
        ('test_closed_quality32_full_path_v5.py', 'test_closed_quality32_full_path_v6.py', [
            ('review_closed_quality32_v5', 'review_closed_quality32_v6'),
            ('from Robotron.tools import run_quality_campaign as campaign', 'from tail9000_test_support_v1 import campaign'),
            ('profile03/', 'profile04/'), ('7200', '9000'), ('8h 10min', '10h 10min'),
            ('all_slots=review.SLOTS.copy(),source_package=package)',
             'all_slots=review.SLOTS.copy(),source_package=package,same_whole_cohort_timeout_s=9000)')]),
        ('test_quality32_runtime_guard_v1.py', 'test_tail9000_runtime_guard_fixtures_v1.py', [
            ('quality32_runtime_guard_v1 as observer', 'quality32_runtime_guard_v5 as observer'),
            ('from Robotron.tools import run_quality_campaign as campaign', 'from tail9000_test_support_v1 import campaign'),
            ('audit_quality32_evidence_v1.py', 'audit_quality32_evidence_v2.py'),
            ('profile03/', 'profile04/'), ('7200', '9000'), ('29400', '36600'), ('30000', '37200')]),
        ('test_quality32_observer_integration_v4.py', 'test_quality32_observer_integration_v5.py', [
            ('quality32_runtime_guard_v4 as observer', 'quality32_runtime_guard_v5 as observer'),
            ('test_quality32_runtime_guard_v1 as gates', 'test_tail9000_runtime_guard_fixtures_v1 as gates'),
            ('test_closed_quality32_full_path_v5 as fixtures', 'test_closed_quality32_full_path_v6 as fixtures'),
            ('protect_quality32_winner_v3 as protect', 'protect_quality32_winner_v4 as protect'), ('7200', '9000')]),
        ('test_protect_quality32_winner_v4.py', 'test_protect_quality32_winner_v5.py', [
            ('protect_quality32_winner_v3 as protect', 'protect_quality32_winner_v4 as protect'),
            ('test_closed_quality32_full_path_v5 as full_fixture', 'test_closed_quality32_full_path_v6 as full_fixture')]),
        ('test_prepare_quality32_campaign_v3.py', 'test_prepare_quality32_campaign_v4.py', [
            ('prepare_quality32_campaign_v3 as prepare', 'prepare_quality32_campaign_v4 as prepare'),
            ('test_closed_quality32_full_path_v5 as fixtures', 'test_closed_quality32_full_path_v6 as fixtures'),
            ('29400', '36600')]),
        ('test_audit_quality32_evidence_v1.py', 'test_audit_quality32_evidence_v2.py', [
            ('audit_quality32_evidence_v1 as review', 'audit_quality32_evidence_v2 as review'),
            ('from Robotron.tools import run_quality_campaign as campaign', 'from tail9000_test_support_v1 import campaign'),
            ('config = replace(self.fixture.config, cohort_s=5400, timeout_s=7200,',
             'config = replace(campaign.Campaign(**vars(self.fixture.config)), cohort_s=5400, timeout_s=9000,')]),
        ('test_quality32_acquisition_v2.py', 'test_quality32_acquisition_v3.py', [
            ('quality32_acquisition_v1 as review', 'quality32_acquisition_v2 as review'),
            ('profile03/', 'profile04/'),
            ('all_slots=review.SLOTS.copy(), source_package=entry)',
             'all_slots=review.SLOTS.copy(), source_package=entry, same_whole_cohort_timeout_s=9000)')]),
        ('test_prepare_quality32_candidate_CPU_v2.py', 'test_prepare_quality32_candidate_CPU_v3.py', [
            ('prepare_quality32_candidate_CPU_v2 as prepare', 'prepare_quality32_candidate_CPU_v3 as prepare'),
            ('test_closed_quality32_full_path_v4 as fixtures', 'test_closed_quality32_full_path_v6 as fixtures'),
            ('profile03/', 'profile04/')]),
        ('test_monitor_supervised_quality32_v1.py', 'test_monitor_supervised_quality32_v2.py', [
            ('monitor_supervised_quality32_v1 as monitor', 'monitor_supervised_quality32_v2 as monitor'),
            ('quality32_runtime_guard_v4 as observer', 'quality32_runtime_guard_v5 as observer'),
            ('review_closed_quality32_v5 as reviewer', 'review_closed_quality32_v6 as reviewer')]),
        ('test_prepare_supervised_quality32_monitor_v1.py', 'test_prepare_supervised_quality32_monitor_v2.py', [
            ('prepare_supervised_quality32_monitor_v1 as prepare', 'prepare_supervised_quality32_monitor_v2 as prepare'),
            ('monitor_supervised_quality32_v1 as monitor', 'monitor_supervised_quality32_v2 as monitor'),
            ('test_monitor_supervised_quality32_v1 as fixtures', 'test_monitor_supervised_quality32_v2 as fixtures'),
            ('quality32_runtime_guard_v4.py', 'quality32_runtime_guard_v5.py'),
            ('review_closed_quality32_v5.py', 'review_closed_quality32_v6.py')])]
    outputs, provenance = {}, []
    for old, new, transitions in definitions:
        parent = H/old
        raw = parent.read_bytes()
        value = raw.decode()
        for before, after in transitions:
            assert before in value, (old, before)
            value = value.replace(before, after)
        target = H/new
        assert not target.exists(), new
        outputs[target] = value.encode()
        provenance.append(dict(parent=str(parent), parent_sha256=hashlib.sha256(raw).hexdigest(),
            target=str(target), target_sha256=hashlib.sha256(outputs[target]).hexdigest(),
            exact_transitions=transitions))
    target = P/'test-fixture-construction.json'
    assert not target.exists()
    for path, raw in outputs.items():
        fd = os.open(path, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o664)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    fd = os.open(target, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o444)
    with os.fdopen(fd, 'w') as stream:
        json.dump(dict(schema='robotron-tail9000-synthetic-fixtures-v1', files=provenance,
                       executed=False, scientific_inputs_changed=False), stream, indent=2)
        stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    print(json.dumps(dict(created=len(outputs), provenance=str(target), launched=False)))


if __name__ == '__main__':
    main()
