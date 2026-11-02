"""Construct new prospective5400/9000 sources; default invocation is inert.

Only writes new paths. No numerical imports, model capture, runtime launch,
existing source edit, qualification or policy publication occurs.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import time

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
H = G/'tools/quality_capacity_proposal'
DESIGN = G/'logs/managed-learning-20261015/run-26/quality32-fresh-candidate-5400-9000-protocol-proposal-20261019/design-and-required-source-scope.json'
DESIGN_SHA = '1a209e7fe356515dfeb6c650cb1c102cc1766e0f7a407baa412fb19c908b5321'
PARENT_SHA = '40a9fc7148764623c723dc9b8f3ae2368ee5a4c29a39e353e3975371c79d04a1'


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def reader_module():
    path = G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py'
    require(digest(path.read_bytes()) == 'c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071', 'Exact reader required')
    spec = importlib.util.spec_from_file_location('_tail9000_preparation_reader', path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def encode(value):
    return (json.dumps(value, indent=2, allow_nan=False)+'\n').encode()


def construct(reader):
    design_pin = reader.pin(DESIGN)
    require(design_pin['sha256'] == DESIGN_SHA, 'Exact prospective design required')
    design = reader.read_pin(design_pin)
    parent_pin = reader.pin(H/'profile03/runtime-source-package.json')
    require(parent_pin['sha256'] == PARENT_SHA, 'Exact unchanged parent profile required')
    parent = reader.read_pin(parent_pin)
    root = H/'profile04/Robotron'
    require(not root.parent.exists(), 'New profile directory required')
    changes, outputs = [], {}
    for relative, sha in parent['files'].items():
        path = Path(parent['root'])/relative; raw = path.read_bytes()
        require(digest(raw) == sha, 'Parent source differs: '+relative)
        if relative == 'tools/run_frozen_sidecar.py':
            require(raw.count(b'7200') == 2, 'Exact evaluator ceiling scope required')
            raw = raw.replace(b'7200', b'9000')
        elif relative == 'tools/test_frozen_sidecar.py':
            require(raw.count(b'timeout_s=7200') == 1 and raw.count(b'(3600,7201)') == 1,
                    'Exact copied ceiling fixture scope required')
            raw = raw.replace(b'timeout_s=7200', b'timeout_s=9000').replace(b'(3600,7201)', b'(3600,9001)')
        if digest(raw) != sha:
            changes.append(relative)
        outputs[root/relative] = raw
    require(set(changes) == {'tools/run_frozen_sidecar.py', 'tools/test_frozen_sidecar.py'}, 'Only ceiling and copied fixture may differ')
    manifest = dict(parent)
    manifest.update(schema='robotron-prospective-tail9000-profile-v1', root=str(root), parent_manifest=parent_pin,
                    files={relative:digest(outputs[root/relative]) for relative in parent['files']},
                    byte_count=sum(len(raw) for raw in outputs.values()), changed_parent_files=changes,
                    launch_selected=False, independent_quality_auditor32_ready=False,
                    same_admission_s=5400, same_total_runtime_s=9000,
                    minimum_last_admission_drain_s=3600,
                    fixture_correction='Only the copied runtime-ceiling fixture follows the new9000s maximum.')
    manifest_path = root.parent/'runtime-source-package.json'
    outputs[manifest_path] = encode(manifest); package_sha = digest(outputs[manifest_path])
    original_pins = {Path(value['original_source']['path']).name:value['original_source'] for value in design['source_inventory']}
    extra = {'quality32_acquisition_v1.py':'f3dce1d0cba21e6a1efdf85e3350edd673a7515145ede338dbff1b4eb2d7fac4',
             'prepare_quality32_candidate_CPU_v2.py':'812cf5ae2a785601a7f9102c25de6c60503a0966dd42f86ebaea9acdae89d59a',
             'prepare_supervised_quality32_monitor_v1.py':'06c066b298ae705205f303001d6cc52b4dabcfac91f3987ac195c4629656d28b'}
    for name, sha in extra.items():
        pin = reader.pin(H/name); require(pin['sha256'] == sha, 'Exact additional parent required: '+name)
        original_pins[name] = pin
    for pin in original_pins.values():
        reader.read_pin(pin, as_json=False)
    transformed = {}

    def make(old, new, replacements):
        text = reader.read_pin(original_pins[old], as_json=False).decode()
        applied = []
        for before, after in replacements:
            require(before in text, 'Missing declared source transition: '+old+' '+before)
            count = text.count(before); text = text.replace(before, after)
            applied.append(dict(before=before, after=after, occurrences=count))
        target = H/new; require(not target.exists(), 'New source version required: '+new)
        outputs[target] = text.encode(); transformed[new] = dict(parent=original_pins[old], replacements=applied)
        return digest(outputs[target])

    acquisition_sha = make('quality32_acquisition_v1.py', 'quality32_acquisition_v2.py',
        [(PARENT_SHA,package_sha), ('same_whole_cohort_timeout_s=7200','same_whole_cohort_timeout_s=9000')])
    make('prepare_quality32_candidate_CPU_v2.py', 'prepare_quality32_candidate_CPU_v3.py', [(PARENT_SHA,package_sha)])
    cohorts_sha = make('audit_quality32_evidence_v1.py', 'audit_quality32_evidence_v2.py',
        [(PARENT_SHA,package_sha), ('profile03/runtime-source-package.json','profile04/runtime-source-package.json'),
         ("job['timeout_s'] == 7200", "job['timeout_s'] == 9000")])
    reviewer_sha = make('review_closed_quality32_v5.py', 'review_closed_quality32_v6.py',
        [('audit_quality32_evidence_v1.py','audit_quality32_evidence_v2.py'),
         ('5b8388c5a8aa37979209c89c14a91d015f65f6463e975947c42042dfed611a33',cohorts_sha),
         ('quality32_acquisition_v1.py','quality32_acquisition_v2.py'),
         ('f3dce1d0cba21e6a1efdf85e3350edd673a7515145ede338dbff1b4eb2d7fac4',acquisition_sha),
         ('profile03/Robotron','profile04/Robotron'),('7500','9300'),('29400','36600')])
    observer_sha = make('quality32_runtime_guard_v4.py', 'quality32_runtime_guard_v5.py',
        [('review_closed_quality32_v5.py','review_closed_quality32_v6.py'),
         ('9e76234a91eb69ff8c62fd0be0189f4a532bb3f0ad994457eb94dadc0d83d279',reviewer_sha),
         ('profile03/Robotron','profile04/Robotron'),("('--timeout-s','7200')","('--timeout-s','9000')"),
         ('30000','37200'),('29400','36600')])
    make('prepare_quality32_campaign_v3.py', 'prepare_quality32_campaign_v4.py',
        [('quality32_acquisition_v1.py','quality32_acquisition_v2.py'),
         ('f3dce1d0cba21e6a1efdf85e3350edd673a7515145ede338dbff1b4eb2d7fac4',acquisition_sha),
         ('audit_quality32_evidence_v1.py','audit_quality32_evidence_v2.py'),
         ('5b8388c5a8aa37979209c89c14a91d015f65f6463e975947c42042dfed611a33',cohorts_sha),
         ('quality32_runtime_guard_v4.py','quality32_runtime_guard_v5.py'),
         ('a226fa3c4231c4021a83cf4690e125825f734b3484a3363432a7b89c3ef134e0',observer_sha),
         ('review_closed_quality32_v5.py','review_closed_quality32_v6.py'),
         ('9e76234a91eb69ff8c62fd0be0189f4a532bb3f0ad994457eb94dadc0d83d279',reviewer_sha),
         ('29400','36600'),('30000','37200'),('30600','37800')])
    make('protect_quality32_winner_v3.py', 'protect_quality32_winner_v4.py',
        [('9e76234a91eb69ff8c62fd0be0189f4a532bb3f0ad994457eb94dadc0d83d279',reviewer_sha)])
    make('monitor_supervised_quality32_v1.py', 'monitor_supervised_quality32_v2.py',
        [('quality32_runtime_guard_v4.py','quality32_runtime_guard_v5.py'),
         ('a226fa3c4231c4021a83cf4690e125825f734b3484a3363432a7b89c3ef134e0',observer_sha),
         ('review_closed_quality32_v5.py','review_closed_quality32_v6.py'),
         ('9e76234a91eb69ff8c62fd0be0189f4a532bb3f0ad994457eb94dadc0d83d279',reviewer_sha)])
    make('prepare_supervised_quality32_monitor_v1.py', 'prepare_supervised_quality32_monitor_v2.py',
        [('monitor_supervised_quality32_v1.py','monitor_supervised_quality32_v2.py'),
         ('quality32_runtime_guard_v4.py','quality32_runtime_guard_v5.py'),
         ('review_closed_quality32_v5.py','review_closed_quality32_v6.py')])
    require(all(not path.exists() for path in outputs), 'All construction outputs must be new')
    return outputs, dict(schema='robotron-tail9000-source-construction-v1', unix_s=time.time(), design=design_pin,
                         parent_profile=parent_pin, new_profile_manifest=str(manifest_path),
                         new_profile_manifest_sha256=package_sha, changed_profile_files=changes,
                         transformed_sources=transformed, source_hashes={str(path):digest(raw) for path,raw in outputs.items()},
                         status='WRITTEN_UNSEALED_NOT_CPU_VALIDATED_NOT_LAUNCH_READY',
                         production_changed=False, numerical_parser_Lua_ingestion_unchanged=True,
                         quality_qualified=False, candidate_captured=False)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-new-sources', action='store_true')
    args = parser.parse_args(argv)
    if not args.write_new_sources:
        print('PLAN_ONLY: no source/model reads, outputs, launches or policy changes')
        return 0
    reader = reader_module(); outputs, report = construct(reader)
    target = DESIGN.parent/'source-construction.json'
    require(not target.exists(), 'Construction is one new publication only')
    for path, raw in outputs.items():
        path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        fd = os.open(path, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o664)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    fd = os.open(target, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o444)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(encode(report)); stream.flush(); os.fsync(stream.fileno())
    print(json.dumps(dict(report=str(target), profile=report['new_profile_manifest'],
                          sources=len(outputs), launch_ready=False)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
